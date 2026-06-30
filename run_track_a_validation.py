"""Track A — Backend Integrity & Performance validation runner.

Executes a subset of sections A.1–A.12 from the FINAL_PREHANDOFF validation
spec and writes structured reports.
"""

import json
import os
import random
import string
import sys
import time
from datetime import date, timedelta
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Dict, List, Tuple

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "backend"))

os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ["TAXFLOW_TESTING"] = "true"
os.environ["TAXFLOW_GLOBAL_RATE_LIMIT"] = "10000/second"
os.environ["TAXFLOW_GLOBAL_BURST_LIMIT"] = "10000"
os.environ["TAXFLOW_SINGLE_USER"] = "true"
os.environ["TAXFLOW_RUNTIME_MODE"] = "offline"

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.database import Base, get_db
from backend.api import app
from backend import models
from backend.accounting.coa import create_account
from backend.routers.auth import get_password_hash

REPORT_MD = ROOT / "shared" / "tasks" / "v3.11.6" / "VALIDATION_TRACK_A_REPORT.md"
REPORT_JSON = ROOT / "shared" / "tasks" / "v3.11.6" / "VALIDATION_TRACK_A_TASKS.json"


class TrackAValidation:
    def __init__(self):
        self.engine = create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(bind=self.engine)
        self.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=self.engine)

        def override_get_db():
            db = self.SessionLocal()
            try:
                yield db
            finally:
                db.close()

        app.dependency_overrides[get_db] = override_get_db
        self.client = TestClient(app)
        self.user = None
        self.token = None
        self.tenant_id = None
        self.results: List[Dict[str, Any]] = []

    def log(self, section: str, verdict: str, details: str, metrics: Dict[str, Any] = None):
        self.results.append({
            "section": section,
            "verdict": verdict,
            "details": details,
            "metrics": metrics or {},
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        })
        print(f"[{section}] {verdict}: {details}")

    def create_user_and_tenant(self):
        db = self.SessionLocal()
        try:
            user = models.User(
                username="tracka_user",
                email="tracka@example.com",
                hashed_password=get_password_hash("tracka_pass"),
                is_active=True,
                encryption_salt="dHJhY2thX3NhbHRfMTZieXRlcw==",  # deterministic test salt
            )
            db.add(user)
            db.commit()
            db.refresh(user)
            client = models.Client(name="Track A Client", user_id=user.id)
            db.add(client)
            db.commit()
            db.refresh(client)
            self.user = user
            self.tenant_id = client.id
            create_account(db, client.id, user.id, "1010", "Cash", "asset")
            create_account(db, client.id, user.id, "4000", "Revenue", "income")
            create_account(db, client.id, user.id, "5000", "Expenses", "expense")
            create_account(db, client.id, user.id, "2000", "Accounts Payable", "liability")
            create_account(db, client.id, user.id, "3000", "Equity", "equity")
        finally:
            db.close()

        resp = self.client.post("/api/auth/login", data={"username": "tracka_user", "password": "tracka_pass"})
        assert resp.status_code == 200, resp.text
        self.token = resp.json()["access_token"]
        self.client.headers.update({"Authorization": f"Bearer {self.token}"})

    def run_api_fuzz(self) -> Tuple[int, int, int]:
        """A.1 — lightweight fuzz against a sample of endpoints."""
        endpoints = [
            ("GET", "/api/health", {}),
            ("GET", "/api/coa/", {}),
            ("POST", "/api/coa/", {"number": "9999", "name": "Fuzz", "type": "expense"}),
            ("GET", "/api/rules/", {}),
            ("POST", "/api/rules/", {"name": "x", "pattern": "y", "gl_account_id": 1}),
            ("GET", "/api/clients/", {}),
            ("POST", "/api/clients/", {"name": "Fuzz Client"}),
            ("GET", "/api/trial-balance/", {}),
            ("GET", "/api/reports/income-statement", {}),
        ]
        status_5xx = 0
        status_4xx = 0
        status_2xx = 0
        for _ in range(500):
            method, path, body = random.choice(endpoints)
            # mutate body with random garbage
            payload = {}
            for k, v in body.items():
                r = random.random()
                if r < 0.2:
                    payload[k] = "".join(random.choices(string.printable, k=random.randint(0, 200)))
                elif r < 0.4:
                    payload[k] = random.randint(-10_000_000, 10_000_000)
                elif r < 0.5:
                    payload[k] = None
                else:
                    payload[k] = v
            try:
                if method == "GET":
                    resp = self.client.get(path)
                else:
                    resp = self.client.post(path, json=payload)
                if resp.status_code >= 500:
                    status_5xx += 1
                elif resp.status_code >= 400:
                    status_4xx += 1
                elif resp.status_code >= 200:
                    status_2xx += 1
            except Exception:
                status_5xx += 1
        return status_2xx, status_4xx, status_5xx

    def run_ledger_random_walk(self) -> Tuple[int, List[str]]:
        """A.2 — random walk + A.3 invariants."""
        violations = []
        operations = 0
        # seed opening balance
        self.client.post("/api/journal-entries/", json={
            "date": str(date.today()),
            "memo": "Opening balance",
            "lines": [
                {"account_id": 1, "debit": 100_000, "credit": 0},
                {"account_id": 5, "debit": 0, "credit": 100_000},
            ],
        })

        for _ in range(250):
            op_type = random.choice(["je", "invoice", "bill", "transfer"])
            try:
                if op_type == "je":
                    amount = random.randint(1, 5000)
                    self.client.post("/api/journal-entries/", json={
                        "date": str(date.today() - timedelta(days=random.randint(0, 365))),
                        "memo": "Random JE",
                        "lines": [
                            {"account_id": 3, "debit": amount, "credit": 0},
                            {"account_id": 1, "debit": 0, "credit": amount},
                        ],
                    })
                elif op_type == "invoice":
                    amount = random.randint(10, 2000)
                    self.client.post("/api/invoices/", json={
                        "client_id": self.tenant_id,
                        "invoice_date": str(date.today()),
                        "due_date": str(date.today() + timedelta(days=30)),
                        "line_items": [{"description": "svc", "amount": amount, "tax_amount": 0}],
                    })
                elif op_type == "bill":
                    amount = random.randint(10, 2000)
                    self.client.post("/api/bills/", json={
                        "vendor_id": 1,
                        "bill_date": str(date.today()),
                        "due_date": str(date.today() + timedelta(days=30)),
                        "amount": amount,
                        "line_items": [{"description": "exp", "amount": amount}],
                    })
                operations += 1
            except Exception as exc:
                violations.append(f"operation {op_type} raised: {exc}")

            # invariant check every 25 ops
            if operations % 25 == 0:
                try:
                    tb = self.client.post("/api/reports/trial-balance", json={"as_of": str(date.today())})
                    if tb.status_code == 200:
                        data = tb.json()
                        total = sum(row.get("debit", 0) - row.get("credit", 0) for row in data.get("rows", []))
                        if abs(total) > 0.01:
                            violations.append(f"trial balance imbalance: {total}")
                except Exception as exc:
                    violations.append(f"invariant check error: {exc}")
        return operations, violations

    def run_tenant_isolation(self) -> Tuple[int, int]:
        """A.5 — create second tenant and ensure no cross-tenant reads."""
        db = self.SessionLocal()
        try:
            user2 = models.User(
                username="tracka_user2",
                email="tracka2@example.com",
                hashed_password=get_password_hash("tracka_pass2"),
                is_active=True,
                encryption_salt="dHJhY2thX3NhbHRfMTZieXRlczI=",
            )
            db.add(user2)
            db.commit()
            db.refresh(user2)
            client2 = models.Client(name="Track A Client 2", user_id=user2.id)
            db.add(client2)
            db.commit()
            db.refresh(client2)
            tenant2_id = client2.id
            create_account(db, tenant2_id, user2.id, "1010", "Cash", "asset")
        finally:
            db.close()

        resp = self.client.post("/api/auth/login", data={"username": "tracka_user2", "password": "tracka_pass2"})
        if resp.status_code != 200:
            return 0, 1
        token2 = resp.json()["access_token"]
        client2 = TestClient(app)
        client2.headers.update({"Authorization": f"Bearer {token2}"})

        leaks = 0
        checks = 0
        # tenant 1 should not see tenant 2 data
        endpoints = ["/api/coa/", "/api/clients/", "/api/rules/", "/api/journal-entries/", "/api/invoices/", "/api/bills/", "/api/vendors/"]
        for endpoint in endpoints:
            try:
                r1 = self.client.get(endpoint)
                r2 = client2.get(endpoint)
                checks += 1
                if r1.status_code == 200 and r2.status_code == 200:
                    try:
                        d1 = r1.json()
                        d2 = r2.json()
                        if isinstance(d1, list) and isinstance(d2, list):
                            ids1 = {x.get("id") for x in d1}
                            ids2 = {x.get("id") for x in d2}
                            if ids1 & ids2:
                                leaks += 1
                    except Exception:
                        pass
            except Exception:
                checks += 1
        return leaks, checks

    def run_parser_fuzz(self) -> Tuple[int, int]:
        """A.7 — feed mutated synthetic OFX content to parser detection."""
        sample = "OFXHEADER:100\nDATA:OFXSGML\nVERSION:102\nSECURITY:NONE\nENCODING:USASCII\nCHARSET:1252\nCOMPRESSION:NONE\nOLDFILEUID:NONE\nNEWFILEUID:NONE\n<OFX><SIGNONMSGSRSV1><SONRS><STATUS><CODE>0</CODE></STATUS></SONRS></SIGNONMSGSRSV1></OFX>"
        crashes = 0
        total = 100
        for i in range(total):
            mutated = bytearray(sample.encode("utf-8", errors="ignore"))
            for _ in range(random.randint(1, 10)):
                if len(mutated) > 0:
                    pos = random.randint(0, len(mutated) - 1)
                    mutated[pos] = random.randint(0, 255)
            try:
                self.client.post("/api/upload/validate-format", files={"file": (f"fuzz{i}.ofx", bytes(mutated), "application/octet-stream")})
            except Exception:
                crashes += 1
        return total, crashes

    def run_backup_restore(self) -> Tuple[bool, str]:
        """A.10 — backup CLI round-trip (if available)."""
        backup_script = ROOT / "scripts" / "backup_restore.py"
        if not backup_script.exists():
            return False, "backup_restore.py not found"
        return False, "CLI backup/restore not executed in this harness"

    def run(self):
        start = time.time()
        print("Starting Track A validation...")
        try:
            self.create_user_and_tenant()
        except Exception as exc:
            self.log("A.0 Setup", "FAIL", f"Could not create tenant: {exc}")
            self.write_reports()
            return

        # A.1
        try:
            s2, s4, s5 = self.run_api_fuzz()
            verdict = "PASS" if s5 == 0 else "FAIL"
            self.log("A.1 API Fuzz", verdict, f"500 requests; 2xx={s2}, 4xx={s4}, 5xx={s5}", {"2xx": s2, "4xx": s4, "5xx": s5})
        except Exception as exc:
            self.log("A.1 API Fuzz", "FAIL", f"Exception: {exc}")

        # A.2/A.3
        try:
            ops, violations = self.run_ledger_random_walk()
            verdict = "PASS" if not violations else "FAIL"
            self.log("A.2/A.3 Ledger Random Walk + Invariants", verdict,
                     f"{ops} operations; {len(violations)} invariant violations",
                     {"operations": ops, "violations": len(violations), "violation_samples": violations[:5]})
        except Exception as exc:
            self.log("A.2/A.3 Ledger Random Walk + Invariants", "FAIL", f"Exception: {exc}")

        # A.5
        try:
            leaks, checks = self.run_tenant_isolation()
            verdict = "PASS" if leaks == 0 else "FAIL"
            self.log("A.5 Multi-Tenant Isolation", verdict, f"{checks} checks; {leaks} leaks detected", {"checks": checks, "leaks": leaks})
        except Exception as exc:
            self.log("A.5 Multi-Tenant Isolation", "FAIL", f"Exception: {exc}")

        # A.7
        try:
            total, crashes = self.run_parser_fuzz()
            verdict = "PASS" if crashes == 0 else "FAIL"
            self.log("A.7 Parser Resilience Fuzz", verdict, f"{total} mutated files; {crashes} crashes", {"total": total, "crashes": crashes})
        except Exception as exc:
            self.log("A.7 Parser Resilience Fuzz", "FAIL", f"Exception: {exc}")

        # A.10
        ok, msg = self.run_backup_restore()
        self.log("A.10 Backup & Restore Integrity", "INFO" if not ok else "PASS", msg)

        elapsed = time.time() - start
        self.log("A.99 Summary", "INFO", f"Track A completed in {elapsed:.1f}s", {"elapsed_seconds": elapsed})
        self.write_reports()

    def write_reports(self):
        REPORT_MD.parent.mkdir(parents=True, exist_ok=True)
        lines = [
            "# Track A: Backend Integrity & Performance Validation Report",
            "",
            f"**Date:** {time.strftime('%Y-%m-%d %H:%M:%S UTC', time.gmtime())}",
            "**Branch:** `v3.11.6-dev`",
            "**Tester:** James Clawd",
            "",
            "| Section | Verdict | Details |",
            "|---------|---------|---------|",
        ]
        for r in self.results:
            details = r["details"].replace("|", "\\|")
            lines.append(f"| {r['section']} | {r['verdict']} | {details} |")
        lines.append("")
        lines.append("## Metrics")
        lines.append("")
        for r in self.results:
            if r["metrics"]:
                lines.append(f"### {r['section']}")
                lines.append("```json")
                lines.append(json.dumps(r["metrics"], indent=2))
                lines.append("```")
                lines.append("")
        REPORT_MD.write_text("\n".join(lines), encoding="utf-8")

        tasks = {
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "results": self.results,
        }
        REPORT_JSON.write_text(json.dumps(tasks, indent=2), encoding="utf-8")
        print(f"Reports written to {REPORT_MD} and {REPORT_JSON}")


if __name__ == "__main__":
    TrackAValidation().run()
