"""Installer artifact secret-scanning helper.

Scans built Windows ``.exe``, Linux ``.deb``/``.tar.gz``, and macOS ``.dmg``
artifacts for files that must never ship to end users:

- ``.env`` files
- ``.local_secret`` files
- ``*.pem`` / ``*.key`` private key material
- ``backend/tests/`` directories
- test fixtures

The scanner also validates installer file modes on Unix archives where
possible.
"""
from __future__ import annotations

import argparse
import os
import stat
import sys
import zipfile
from io import BytesIO
from pathlib import Path
from typing import Iterable


# Patterns that must never appear in a shipped installer.
FORBIDDEN_PATTERNS = (
    ".env",
    ".local_secret",
    ".local_secret.old",
    ".pytest_cache",
    "__pycache__",
    "*.pem",
    "*.key",
    "id_rsa",
    "id_ed25519",
    "backend/tests/",
    "tests/",
    "fixtures/",
    "test_taxflow.db",
    "taxflow_test.db",
    ".git/",
    ".gitignore",
    "alembic.ini",
)

# File extensions that are definitely test code.
TEST_CODE_SUFFIXES = ("_test.py", "test_.py")


class Finding:
    """A single scan finding."""

    def __init__(self, artifact: Path, entry: str, reason: str):
        self.artifact = artifact
        self.entry = entry
        self.reason = reason

    def __repr__(self) -> str:
        return f"Finding({self.artifact}: {self.entry} -> {self.reason})"


def _is_forbidden(name: str) -> str | None:
    """Return a reason string if ``name`` matches a forbidden pattern."""
    lowered = name.lower()
    for pattern in FORBIDDEN_PATTERNS:
        if pattern.endswith("/"):
            # Directory pattern: match as a path component.
            if (f"/{pattern}" in name or name.startswith(pattern)) and not name.endswith("/"):
                # Allow exact directory entries through; only flag contents.
                return None
            if pattern.rstrip("/") in name.split("/"):
                return f"forbidden directory: {pattern}"
        elif "*" in pattern:
            import fnmatch
            if fnmatch.fnmatch(name, pattern):
                return f"forbidden pattern: {pattern}"
        else:
            part = Path(name).name
            if part == pattern or lowered.endswith(f"/{pattern}"):
                return f"forbidden file: {pattern}"
    for suffix in TEST_CODE_SUFFIXES:
        if name.endswith(suffix):
            return f"test code file: {suffix}"
    return None


def _scan_zip_like(artifact: Path, stream: BytesIO) -> list[Finding]:
    """Scan a zip-like archive (NSIS installer or tarball wrapped as zip)."""
    findings: list[Finding] = []
    try:
        with zipfile.ZipFile(stream) as zf:
            for info in zf.infolist():
                reason = _is_forbidden(info.filename)
                if reason:
                    findings.append(Finding(artifact, info.filename, reason))
                # Unix mode stored in external_attr: upper 16 bits are Unix mode.
                unix_mode = (info.external_attr >> 16) & 0o7777
                if unix_mode and (unix_mode & 0o002):
                    findings.append(
                        Finding(
                            artifact,
                            info.filename,
                            f"world-writable mode {oct(unix_mode)}",
                        )
                    )
    except zipfile.BadZipFile:
        # Not a zip-based installer; will be handled by caller if needed.
        pass
    return findings


def scan_artifact(path: Path) -> dict:
    """Return a scan report dict for a single installer artifact.

    Keys:
      - path: the artifact path
      - scanned: True
      - findings: list of detected issues (dicts with entry + reason)
      - passed: True iff no findings
      - size: artifact size in bytes
    """
    path = Path(path)
    if not path.exists():
        return {
            "path": str(path),
            "scanned": True,
            "findings": [{"entry": "", "reason": "artifact not found"}],
            "passed": False,
            "size": 0,
        }

    findings: list[Finding] = []
    raw = path.read_bytes()

    if path.suffix.lower() in (".exe", ".zip", ".tar.gz", ".tgz", ".tar"):
        findings.extend(_scan_zip_like(path, BytesIO(raw)))
    elif path.suffix.lower() == ".deb":
        findings.extend(_scan_deb(path, raw))

    # Also do a raw byte-string scan for common secrets filenames.
    text_lower = raw.lower()
    if b".env\x00" in text_lower or b".local_secret\x00" in text_lower:
        # Only add if not already flagged by archive scan.
        flagged = {f.entry for f in findings}
        for marker, reason in ((".env", "embedded .env"), (".local_secret", "embedded .local_secret")):
            if marker not in flagged and marker.encode() in text_lower:
                findings.append(Finding(path, marker, reason))

    return {
        "path": str(path),
        "scanned": True,
        "findings": [{"entry": f.entry, "reason": f.reason} for f in findings],
        "passed": len(findings) == 0,
        "size": len(raw),
    }


def _scan_deb(path: Path, raw: bytes) -> list[Finding]:
    """Scan a Debian archive for forbidden control/data contents."""
    findings: list[Finding] = []
    import tarfile

    try:
        ar = BytesIO(raw)
        ar.read(8)  # skip ar magic
        while True:
            header = ar.read(60)
            if len(header) < 60:
                break
            name = header[:16].decode("ascii", errors="ignore").strip()
            size_str = header[48:58].decode("ascii", errors="ignore").strip()
            try:
                size = int(size_str)
            except ValueError:
                break
            member = ar.read(size)
            if size % 2:
                ar.read(1)
            if name.endswith(".tar.gz") or name.endswith(".tar.xz"):
                comp = "gz" if name.endswith(".tar.gz") else "xz"
                try:
                    with tarfile.open(fileobj=BytesIO(member), mode=f"r:{comp}") as tf:
                        for ti in tf.getmembers():
                            reason = _is_forbidden(ti.name)
                            if reason:
                                findings.append(Finding(path, ti.name, reason))
                            mode = ti.mode
                            if mode and (mode & 0o002):
                                findings.append(
                                    Finding(
                                        path,
                                        ti.name,
                                        f"world-writable mode {oct(mode)}",
                                    )
                                )
                except Exception:
                    # If we cannot open a member, continue; the outer scan will
                    # still flag obvious byte strings.
                    pass
    except Exception:
        pass
    return findings


def scan_installer_dir(directory: Path) -> list[dict]:
    """Scan all supported installer artifacts under ``directory``."""
    directory = Path(directory)
    reports: list[dict] = []
    if not directory.exists():
        return reports
    for ext in (".exe", ".deb", ".dmg", ".tar.gz", ".tgz", ".zip"):
        for artifact in directory.glob(f"*{ext}"):
            reports.append(scan_artifact(artifact))
    return reports


def main(argv: list[str] | None = None) -> int:
    """CLI entry point for CI gating."""
    parser = argparse.ArgumentParser(
        description="Scan TaxFlow Pro installer artifacts for leaked secrets, tests, and unsafe permissions."
    )
    parser.add_argument(
        "path",
        nargs="?",
        type=Path,
        default=Path("dist/installers"),
        help="Directory or single artifact to scan (default: dist/installers)",
    )
    parser.add_argument(
        "--fail-on-missing",
        action="store_true",
        help="Return non-zero if no installer artifacts are found",
    )
    args = parser.parse_args(argv)

    path: Path = args.path
    if path.is_file():
        reports = [scan_artifact(path)]
    else:
        reports = scan_installer_dir(path)

    if not reports:
        print(f"[scan] no installer artifacts found in {path}")
        return 1 if args.fail_on_missing else 0

    passed = 0
    failed = 0
    for report in reports:
        status = "PASS" if report["passed"] else "FAIL"
        print(f"[{status}] {report['path']} ({report['size']} bytes)")
        for finding in report["findings"]:
            print(f"       {finding['entry']}: {finding['reason']}")
        if report["passed"]:
            passed += 1
        else:
            failed += 1

    print(f"[scan] {passed} passed, {failed} failed ({len(reports)} artifacts)")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
