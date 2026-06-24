"""SBOM generator for TaxFlow Pro (TASK-032).

Generates a deterministic CycloneDX JSON SBOM from ``requirements.txt`` using
``cyclonedx_py`` and writes it to ``shared/sbom/taxflow-pro-sbom.json``.

Usage:
    python scripts/sbom_generate.py [--requirements PATH] [--output PATH]

Exit codes:
    0 - SBOM generated successfully
    1 - generation failed
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from datetime import datetime, timezone


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_REQUIREMENTS = ROOT / "requirements.txt"
DEFAULT_OUTPUT = ROOT / "shared" / "sbom" / "taxflow-pro-sbom.json"


def generate_sbom(requirements_path: Path, output_path: Path) -> int:
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # cyclonedx_py writes reproducible JSON; we then canonicalize sort order.
    tmp_output = output_path.with_suffix(".tmp.json")
    cmd = [
        sys.executable,
        "-m",
        "cyclonedx_py",
        "requirements",
        str(requirements_path),
        "--output-reproducible",
        "--of",
        "JSON",
        "-o",
        str(tmp_output),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, cwd=ROOT)
    if result.returncode != 0:
        print(f"SBOM generation failed: {result.stderr}", file=sys.stderr)
        return 1

    bom = json.loads(tmp_output.read_text(encoding="utf-8"))
    tmp_output.unlink(missing_ok=True)

    # Sort components by name for stable diffs.
    components = bom.get("components", [])
    bom["components"] = sorted(components, key=lambda c: c.get("name", "").lower())

    # Add deterministic metadata if missing.
    metadata = bom.setdefault("metadata", {})
    metadata.setdefault(
        "timestamp",
        datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
    )
    tool_info = metadata.setdefault("tools", {}).setdefault("components", [])
    if not any(c.get("name") == "cyclonedx-py" for c in tool_info):
        tool_info.append(
            {
                "type": "application",
                "name": "cyclonedx-py",
                "publisher": "CycloneDX",
            }
        )

    output_path.write_text(json.dumps(bom, indent=2) + "\n", encoding="utf-8")
    print(f"SBOM written to {output_path}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Generate a CycloneDX JSON SBOM from requirements.txt."
    )
    parser.add_argument(
        "--requirements",
        type=Path,
        default=DEFAULT_REQUIREMENTS,
        help=f"Path to requirements file (default: {DEFAULT_REQUIREMENTS}).",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help=f"Path for the SBOM output (default: {DEFAULT_OUTPUT}).",
    )
    args = parser.parse_args(argv)

    if not args.requirements.exists():
        print(f"Requirements file not found: {args.requirements}", file=sys.stderr)
        return 1

    return generate_sbom(args.requirements, args.output)


if __name__ == "__main__":
    sys.exit(main())
