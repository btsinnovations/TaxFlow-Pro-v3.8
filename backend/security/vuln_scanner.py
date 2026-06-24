"""Offline dependency vulnerability scanner for TaxFlow Pro.

TaxFlow Pro is designed to run offline. This module provides a local scanner
that checks installed Python packages against a user-supplied vulnerability
database (e.g. an exported OSV or Safety JSON file) and reports any matches.

It is NOT a live network scanner and will never call external APIs unless
explicitly configured with ``TAXFLOW_RUNTIME_MODE=online``.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


def _installed_packages() -> dict[str, str]:
    """Return a mapping of installed distribution name -> version."""
    try:
        from importlib.metadata import distributions
    except Exception:  # pragma: no cover
        return {}

    result: dict[str, str] = {}
    for dist in distributions():
        name = dist.metadata.get("Name", "").lower()
        version = dist.metadata.get("Version", "")
        if name and version:
            result[name] = version
    return result


@dataclass(frozen=True)
class VulnMatch:
    package: str
    installed_version: str
    vuln_id: str
    affected_ranges: list[str]
    aliases: list[str]
    severity: str | None
    summary: str | None


def _parse_version(version: str) -> tuple[int, ...]:
    """Normalise a version string into a comparable tuple of ints."""
    parts: list[int] = []
    for part in version.split("."):
        # Strip any non-numeric suffixes (e.g. dev0, rc1).
        numeric = ""
        for char in part:
            if char.isdigit():
                numeric += char
            else:
                break
        if numeric:
            parts.append(int(numeric))
        else:
            parts.append(0)
    return tuple(parts)


def _version_in_range(version: str, ranges: list[str]) -> bool:
    """Check if ``version`` satisfies any of the simple affected ranges.

    Supports OSV-style compact ranges:
      - ">=1.0,<2.0"
      - "<=3.0"
      - ">=2.0"
      - "==1.2.3"
    """
    v = _parse_version(version)
    for rng in ranges:
        low_op, low_ver, high_op, high_ver = None, None, None, None
        parts = [p.strip() for p in rng.split(",")]
        if len(parts) == 1:
            part = parts[0]
            if part.startswith("=="):
                return _parse_version(part[2:].strip()) == v
            if part.startswith(">="):
                if not (v >= _parse_version(part[2:].strip())):
                    return False
                return True
            if part.startswith("<="):
                if not (v <= _parse_version(part[2:].strip())):
                    return False
                return True
            continue
        if len(parts) == 2:
            left, right = parts[0], parts[1]
            if left.startswith(">="):
                low_op, low_ver = ">=", _parse_version(left[2:].strip())
            elif left.startswith(">"):
                low_op, low_ver = ">", _parse_version(left[1:].strip())
            if right.startswith("<="):
                high_op, high_ver = "<=", _parse_version(right[2:].strip())
            elif right.startswith("<"):
                high_op, high_ver = "<", _parse_version(right[1:].strip())

        if low_op and low_ver is not None:
            if low_op == ">=" and not (v >= low_ver):
                continue
            if low_op == ">" and not (v > low_ver):
                continue
        if high_op and high_ver is not None:
            if high_op == "<=" and not (v <= high_ver):
                continue
            if high_op == "<" and not (v < high_ver):
                continue
        return True
    return False


def _load_vuln_db(path: str | Path) -> list[dict]:
    p = Path(path)
    if not p.exists():
        return []
    data = json.loads(p.read_text(encoding="utf-8"))
    if isinstance(data, dict):
        return data.get("vulns", data.get("results", []))
    if isinstance(data, list):
        return data
    return []


def scan_dependencies(vuln_db_path: str | Path | None = None) -> list[VulnMatch]:
    """Scan installed packages against a local vulnerability database.

    If ``vuln_db_path`` is not provided, the function looks for a default
    ``data/vuln-db.json`` in the project root.
    """
    installed = _installed_packages()
    if not installed:
        return []

    if vuln_db_path is None:
        root = Path(__file__).resolve().parents[2]
        vuln_db_path = root / "data" / "vuln-db.json"

    db = _load_vuln_db(vuln_db_path)
    matches: list[VulnMatch] = []

    for entry in db:
        pkg_name = (entry.get("package", {}).get("name") or entry.get("package_name") or "").lower()
        if not pkg_name or pkg_name not in installed:
            continue
        installed_version = installed[pkg_name]
        affected = entry.get("affected", [])
        if not affected:
            affected = entry.get("ranges", [])
        if not affected and entry.get("vulnerable_versions"):
            affected = [entry["vulnerable_versions"]]

        for aff in affected:
            if isinstance(aff, dict):
                ranges = aff.get("ranges", [])
                versions = aff.get("versions", [])
                # Convert OSV range objects to simple strings.
                range_strings: list[str] = []
                if isinstance(ranges, list):
                    introduced = ""
                    fixed = ""
                    for r in ranges:
                        if r.get("type") == "GIT":
                            continue
                        if r.get("introduced"):
                            introduced = r["introduced"]
                        if r.get("fixed"):
                            fixed = r["fixed"]
                            break
                    if introduced and fixed:
                        range_strings.append(f">={introduced},<{fixed}")
                if not range_strings:
                    range_strings = [str(v) for v in versions if v]
            else:
                range_strings = [str(aff)]

            if range_strings and not _version_in_range(installed_version, range_strings):
                continue

            aliases = entry.get("aliases", [])
            if isinstance(aliases, str):
                aliases = [aliases]
            matches.append(
                VulnMatch(
                    package=pkg_name,
                    installed_version=installed_version,
                    vuln_id=entry.get("id") or entry.get("cve_id") or "UNKNOWN",
                    affected_ranges=range_strings,
                    aliases=aliases,
                    severity=entry.get("severity") or entry.get("database_specific", {}).get("severity"),
                    summary=entry.get("summary") or entry.get("details"),
                )
            )

    return matches


def format_report(matches: Iterable[VulnMatch]) -> dict:
    """Return a JSON-serializable report dict for CLI/CI use."""
    items = [
        {
            "package": m.package,
            "installed_version": m.installed_version,
            "vuln_id": m.vuln_id,
            "severity": m.severity,
            "aliases": m.aliases,
            "affected_ranges": m.affected_ranges,
            "summary": m.summary,
        }
        for m in matches
    ]
    return {
        "ok": len(items) == 0,
        "vulnerable_count": len(items),
        "matches": items,
    }
