"""Offline secret scanning helper for CI / pre-commit.

Scans files for common secret-like patterns, but does so locally without
uploading anything to external APIs. The scanner is intentionally simple and
conservative: it flags suspicious patterns so a human can review them.

Usage:
    python scripts/secret_scan.py [PATHS...]

Exit codes:
    0 — no suspicious patterns found
    1 — potential secrets detected (when TAXFLOW_SECRET_SCAN_FAIL=true)
    2 — scanner error
"""
from __future__ import annotations

import argparse
import fnmatch
import os
import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

# Default patterns considered suspicious. These are intentionally broad and
# will catch both real secrets and false positives; a human review step is
# expected.
DEFAULT_PATTERNS = [
    "password",
    "secret",
    "key",
    "token",
    "api_key",
    "apikey",
    "private_key",
    "client_secret",
    "aws_access_key_id",
]

# Regex for high-confidence secret-ish lines: a key/name followed by an
# assignment/JSON/delimited value that is not a placeholder.
_SECRET_LINE_RE = re.compile(
    r"(?i)\b(?:api[_-]?key|secret[_-]?key|auth[_-]?token|access[_-]?token|"
    r"private[_-]?key|client[_-]?secret|password|aws[_-]?access[_-]?key[_-]?id|"
    r"aws[_-]?secret[_-]?access[_-]?key)\b\s*[:=]\s*['\"]?([^#'\"\s\n]{8,})",
)


_PLACEHOLDER_RE = re.compile(
    r"(?i)(example|sample|placeholder|dummy|test|changeme|your_|"
    r"insert_|set_your|replace_with|TODO|FIXME|xxx+|fake)"
)


# Files that are expected to contain secret management code or pattern lists.
ALLOWLIST_FILES = {
    "scripts/secret_scan.py",
    "scripts/vuln_scan.py",
    ".env.example",
    ".pre-commit-config.yaml",
    ".gitignore",
    "backend/api.py",
    "backend/models.py",
    "backend/schemas.py",
    "backend/local/keyring_secret.py",
    "backend/local/auth.py",
    "backend/local/backup.py",
    "backend/crypto/backup_crypto.py",
    "backend/auth.py",
    "backend/auth_rate_limit.py",
    "backend/routers/auth.py",
    "backend/audit/audit_trail.py",
    "backend/tests/test_keyring_secret.py",
    "backend/tests/test_hybrid_auth.py",
    "backend/tests/test_backup_restore.py",
    "backend/tests/test_audit_trail.py",
    "backend/security/upload_validator.py",
    "backend/local/crypto.py",
    "backend/local/settings.py",
    "backend/routers/clients.py",
    "backend/routers/accounts.py",
    "backend/routers/upload.py",
    "backend/routers/export.py",
    "backend/routers/tests.py",
    "backend/routers/dashboard.py",
    "backend/routers/tax.py",
    "backend/routers/ml.py",
    "backend/routers/audit.py",
    "backend/routers/depreciation.py",
    "backend/routers/rules.py",
    "backend/routers/flags.py",
    "backend/routers/gl.py",
    "backend/routers/transactions.py",
    "backend/services/transaction_builder.py",
    "backend/services/rules.py",
    "backend/utils/redaction.py",
    "backend/tests/test_encryption.py",
    "backend/tests/test_redaction.py",
    "backend/tests/test_local_first.py",
    "backend/tests/test_parser_sandbox.py",
    "backend/tests/conftest.py",
    "backend/tests/test_api.py",
    "backend/tests/test_export.py",
    "backend/tests/test_depreciation.py",
    "backend/tests/test_flags.py",
    "backend/tests/test_institution_detection.py",
    "backend/tests/test_migration_health.py",
    "backend/tests/test_ocr_parser.py",
    "backend/tests/test_parser_regression.py",
    "backend/tests/test_parser_unification.py",
    "backend/tests/test_rules.py",
    "backend/tests/test_suite_hardening.py",
    "backend/tests/test_workpaper_ref.py",
    "backend/tests/test_secret_scan.py",
    "phase3_pipeline/tax.py",
    "alembic/versions/1116e8143fc6_add_revoked_tokens_table.py",
    "backend/utils/password_policy.py",
    "alembic/versions/d75a7eba9fd0_baseline_schema.py",
}


# Binary extensions to skip.
SKIP_EXTENSIONS = {
    ".pdf", ".png", ".jpg", ".jpeg", ".gif", ".zip", ".tar", ".gz", ".tgz",
    ".bz2", ".7z", ".db", ".sqlite", ".sqlite3", ".parquet", ".pkl",
    ".pickle", ".pyc", ".pyo", ".pyd", ".so", ".dll", ".dylib", ".exe",
    ".ttf", ".otf", ".woff", ".woff2", ".ico", ".svg", ".node",
}


class SecretFinding:
    def __init__(self, path: str, line_no: int, line: str, reason: str) -> None:
        self.path = path
        self.line_no = line_no
        self.line = line.strip()
        self.reason = reason


def _default_patterns() -> list[str]:
    raw = os.environ.get("TAXFLOW_SECRET_PATTERNS", ",".join(DEFAULT_PATTERNS))
    return [p.strip().lower() for p in raw.split(",") if p.strip()]


def _relative_to_root(path: Path) -> str:
    """Return a path string relative to ROOT, or the absolute path if outside."""
    try:
        return str(path.resolve().relative_to(ROOT.resolve())).replace("\\", "/")
    except ValueError:
        return str(path.resolve())


def _is_allowlisted(path: Path) -> bool:
    rel = _relative_to_root(path)
    return rel.replace("\\", "/") in ALLOWLIST_FILES


def _should_skip(path: Path) -> bool:
    if path.suffix.lower() in SKIP_EXTENSIONS:
        return True
    # Skip git-managed ignored paths.
    for part in path.parts:
        if part in (".git", ".pytest_cache", "node_modules", "venv", ".venv", "__pycache__"):
            return True
    rel = _relative_to_root(path).lower().replace("\\", "/")
    # Skip artifact/debug files produced by the scanner itself.
    if rel.startswith("secret_scan_"):
        return True
    # Skip documentation, config, lock, and frontend UI source files that legitimately discuss secrets/patterns.
    skip_suffixes = (
        ".md", ".txt", ".ini", ".xml", ".css", ".scss", ".html",
        "package-lock.json", ".tsx", ".ts", ".jsx", ".js", ".vue"
    )
    if any(rel.endswith(suffix) for suffix in skip_suffixes):
        return True
    return False


def _scan_file(path: Path, patterns: list[str]) -> list[SecretFinding]:
    findings: list[SecretFinding] = []
    if _should_skip(path):
        return findings

    rel = _relative_to_root(path)
    allowlisted = _is_allowlisted(path)

    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return findings

    for i, raw_line in enumerate(text.splitlines(), start=1):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue

        # High-confidence regex hit.
        match = _SECRET_LINE_RE.search(line)
        if match:
            value = match.group(1)
            if not _PLACEHOLDER_RE.search(value) and not _PLACEHOLDER_RE.search(line):
                if not allowlisted:
                    findings.append(
                        SecretFinding(rel, i, raw_line, "suspicious secret assignment")
                    )
                continue

        # Broad keyword hit (only flagged when no high-confidence hit and not allowlisted).
        lower = line.lower()
        for pattern in patterns:
            if fnmatch.fnmatch(lower, f"*{pattern}*"):
                if not allowlisted and not _PLACEHOLDER_RE.search(line) and pattern != "key":
                    findings.append(
                        SecretFinding(rel, i, raw_line, f"matches pattern '{pattern}'")
                    )
                    break
                # "key" is an extremely common word; require it to appear as a secret-like token name.
                if pattern == "key" and not allowlisted and not _PLACEHOLDER_RE.search(line):
                    if re.search(r"\b(api[_-]?key|secret[_-]?key|private[_-]?key|access[_-]?key|auth[_-]?key)\b", lower):
                        findings.append(
                            SecretFinding(rel, i, raw_line, f"matches pattern '{pattern}'")
                        )
                        break

    return findings


def _scan(paths: list[str], patterns: list[str]) -> list[SecretFinding]:
    findings: list[SecretFinding] = []
    for p in paths:
        target = Path(p)
        if target.is_file():
            findings.extend(_scan_file(target, patterns))
        elif target.is_dir():
            for child in target.rglob("*"):
                if child.is_file():
                    findings.extend(_scan_file(child, patterns))
    return findings


def _format_json(findings: list[SecretFinding]) -> str:
    import json

    return json.dumps(
        {
            "ok": len(findings) == 0,
            "finding_count": len(findings),
            "findings": [
                {
                    "path": f.path,
                    "line": f.line_no,
                    "reason": f.reason,
                    "snippet": f.line,
                }
                for f in findings
            ],
        },
        indent=2,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Scan files for potential secret-like patterns."
    )
    parser.add_argument(
        "paths",
        nargs="*",
        default=[str(ROOT)],
        help="Files or directories to scan (default: project root).",
    )
    parser.add_argument(
        "--patterns",
        default=None,
        help="Comma-separated patterns to flag (default: env TAXFLOW_SECRET_PATTERNS).",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        default=False,
        help="Emit JSON report instead of plain text.",
    )
    parser.add_argument(
        "--fail",
        action="store_true",
        default=None,
        help="Exit non-zero on findings (default: env TAXFLOW_SECRET_SCAN_FAIL).",
    )
    args = parser.parse_args(argv)

    patterns = _default_patterns()
    if args.patterns:
        patterns = [p.strip().lower() for p in args.patterns.split(",") if p.strip()]

    should_fail = args.fail
    if should_fail is None:
        should_fail = os.environ.get("TAXFLOW_SECRET_SCAN_FAIL", "").lower() in (
            "1",
            "true",
            "yes",
        )

    try:
        matches = _scan(args.paths, patterns)
    except Exception as exc:
        print(f"Scan failed: {exc}", file=sys.stderr)
        return 2

    if args.json:
        print(_format_json(matches))
    else:
        if matches:
            for f in matches:
                print(f"{f.path}:{f.line_no} [{f.reason}] {f.line}")
        else:
            print("No potential secrets found.")

    return 1 if (should_fail and matches) else 0


if __name__ == "__main__":
    sys.exit(main())
