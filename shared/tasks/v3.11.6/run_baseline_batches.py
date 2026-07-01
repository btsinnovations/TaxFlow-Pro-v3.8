"""Run backend/tests in batches to isolate hangs/failures and capture UTF-8 logs."""
import json, os, subprocess, sys, time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
LOG_DIR = ROOT / "shared" / "tasks" / "v3.11.6" / "baseline_test_logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)

env = os.environ.copy()
env.update({
    "TAXFLOW_SINGLE_USER": "true",
    "TAXFLOW_RUNTIME_MODE": "offline",
    "TAXFLOW_TESTING": "true",
    "TAXFLOW_GLOBAL_RATE_LIMIT": "10000/second",
    "TAXFLOW_GLOBAL_BURST_LIMIT": "10000",
    "PYTHONIOENCODING": "utf-8",
})

def collect_tests(exclude=None):
    cmd = [sys.executable, "-m", "pytest", "backend/tests", "--collect-only", "-q"]
    if exclude:
        for e in exclude:
            cmd += ["--ignore", e]
    r = subprocess.run(cmd, cwd=ROOT, env=env, capture_output=True, text=True, timeout=120)
    nodes = []
    for line in r.stdout.splitlines():
        if line.startswith("backend/tests/test_") and "::" in line:
            nodes.append(line.strip())
    return nodes

def run_batch(nodes, idx):
    t0 = time.perf_counter()
    cmd = [sys.executable, "-m", "pytest", "-q", "--tb=short", "--disable-warnings", "--timeout=120"] + nodes
    log_out = LOG_DIR / f"batch_{idx:04d}.log"
    try:
        r = subprocess.run(cmd, cwd=ROOT, env=env, capture_output=True, text=True, timeout=600)
        elapsed = time.perf_counter() - t0
        ok = r.returncode == 0
        log_out.write_text(r.stdout + "\n" + r.stderr, encoding="utf-8")
        summary = ""
        for line in (r.stdout + r.stderr).splitlines():
            if "passed" in line or "failed" in line or "error" in line or " in " in line:
                if "test session starts" not in line and "=" not in line[:5]:
                    summary = line.strip()
        return {"ok": ok, "rc": r.returncode, "elapsed": round(elapsed,2), "summary": summary, "log": str(log_out)}
    except subprocess.TimeoutExpired as exc:
        elapsed = time.perf_counter() - t0
        log_out.write_text((exc.stdout or "") + "\nTIMEOUT\n" + (exc.stderr or ""), encoding="utf-8")
        return {"ok": False, "rc": -1, "elapsed": round(elapsed,2), "summary": "TIMEOUT", "log": str(log_out)}
    except Exception as e:
        return {"ok": False, "rc": -1, "elapsed": 0, "summary": str(e), "log": str(log_out)}

def main(batch_size=50):
    print("Collecting tests...")
    nodes = collect_tests(exclude=["backend/tests/test_alembic_migrations.py", "backend/tests/test_migration_health.py"])
    print(f"Collected {len(nodes)} tests")
    results = []
    total_elapsed = 0
    for i in range(0, len(nodes), batch_size):
        batch = nodes[i:i+batch_size]
        print(f"Batch {i//batch_size+1}/{(len(nodes)-1)//batch_size+1} ({len(batch)} tests)...")
        res = run_batch(batch, i//batch_size+1)
        results.append(res)
        total_elapsed += res["elapsed"]
        print(f"  -> ok={res['ok']} rc={res['rc']} elapsed={res['elapsed']}s summary={res['summary']}")
        if not res["ok"]:
            print("  Stopping due to failure/timeout.")
            break
    summary = {"total_collected": len(nodes), "batches_run": len(results), "total_elapsed": round(total_elapsed,2), "all_ok": all(r["ok"] for r in results), "results": results}
    (LOG_DIR / "batch_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))

if __name__ == "__main__":
    main(batch_size=int(sys.argv[1]) if len(sys.argv) > 1 else 50)
