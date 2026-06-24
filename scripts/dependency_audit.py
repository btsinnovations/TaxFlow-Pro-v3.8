"""
dependency_audit.py — TaxFlow Pro v3.9 runtime dependency audit helper.

Run from project root:
    python scripts/dependency_audit.py

Produces:
    audit_output/dependency_report.json
    audit_output/dependency_audit.md

Logic:
1. Parse direct imports from project source files.
2. Map imports to installed packages via importlib.metadata.
3. Cross-reference with requirements.txt.
4. Classify each package as safe, network-opt-in, or needs-review based on
   known package metadata and minimal source sampling.
5. For network-capable packages, sample the package source for actual
   outbound call patterns.
"""
from __future__ import annotations

import ast
import importlib.metadata as distmeta
import json
import re
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
OUTPUT_DIR = PROJECT_ROOT / "audit_output"

SOURCE_DIRS = [
    PROJECT_ROOT / "backend",
    PROJECT_ROOT / "phase3_pipeline",
    PROJECT_ROOT / "scripts",
    PROJECT_ROOT / "frontend" / "src",
]

# Outbound call patterns we care about.
NETWORK_CALL_PATTERNS = [
    re.compile(r"requests\.(get|post|put|delete|patch|request|head|options)\("),
    re.compile(r"urllib\.request\.urlopen\("),
    re.compile(r"urllib\.request\.Request\("),
    re.compile(r"http\.client\.HTTPConnection\("),
    re.compile(r"http\.client\.HTTPSConnection\("),
    re.compile(r"socket\.create_connection\("),
    re.compile(r"httpx\.(get|post|put|delete|patch|request|head|options)\("),
    re.compile(r"aiohttp\.(ClientSession|get|post)\b"),
]

TELEMETRY_KEYWORDS = [
    re.compile(r"\b(sentry|segment|mixpanel|amplitude|posthog|intercom|fullscreen)\b", re.I),
]

UPDATE_CHECK_PATTERNS = [
    re.compile(r"\b(check.?for.?updates?|update.?check|version.?check|latest.?version)\b", re.I),
]

# Known safe / local-first packages.
SAFE_CATEGORIES = {
    "fastapi": "Web framework (local server only)",
    "uvicorn": "ASGI server (local)",
    "starlette": "ASGI toolkit (local)",
    "sqlalchemy": "ORM (local DB bindings)",
    "alembic": "Migration tool (local DB)",
    "psycopg2-binary": "PostgreSQL driver (connects only to configured DB)",
    "sqlcipher3-wheels": "SQLCipher binding (local encryption)",
    "sqlcipher3": "SQLCipher binding (local encryption)",
    "bcrypt": "Password hashing (local)",
    "cryptography": "Crypto primitives (local)",
    "python-jose": "JWT handling (local)",
    "python-multipart": "Form parser (local)",
    "pydantic": "Validation (local)",
    "pydantic-core": "Validation (local)",
    "pillow": "Image processing (local)",
    "pdfplumber": "PDF text extraction (local)",
    "pypdf2": "PDF text extraction (local)",
    "fpdf2": "PDF generation (local)",
    "pdf2image": "PDF→image wrapper (local, calls local poppler)",
    "pytesseract": "OCR wrapper (local, calls local Tesseract)",
    "pandas": "Data frames (local)",
    "pyarrow": "Columnar data (local)",
    "numpy": "Numeric computing (local)",
    "scikit-learn": "ML (local)",
    "joblib": "ML serialization (local)",
    "scipy": "Math/ML utilities (local)",
    "openpyxl": "Excel read/write (local)",
    "pyyaml": "YAML parser (local)",
    "python-dotenv": "Env loader (local file)",
    "keyring": "Credential store (local OS API)",
    "click": "CLI framework (local)",
    "python-dateutil": "Date parsing (local)",
    "pyasn1": "ASN.1 encoding (local)",
    "rsa": "RSA crypto (local)",
    "ecdsa": "ECDSA crypto (local)",
    "six": "Python 2/3 compat shim (local)",
    "typing_extensions": "Typing backports (local)",
    "typing-inspection": "Typing utilities (local)",
    "packaging": "Version parsing (local)",
    "markupsafe": "Template safety (local)",
    "jinja2": "Templating (local)",
    "mako": "Templating (local, alembic)",
    "greenlet": "Coroutine support (local)",
    "h11": "HTTP/1.1 parser (local, uvicorn)",
    "idna": "IDN encoding (local)",
    "certifi": "Certificate bundle (static data)",
    "charset-normalizer": "Encoding detection (local)",
    "colorama": "Terminal colors (local)",
    "rich": "Terminal UI (local)",
    "pygments": "Syntax highlighting (local)",
    "mdurl": "Markdown URL parsing (local)",
    "pywin32-ctypes": "Windows API ctypes wrappers (local)",
    "more-itertools": "Iterator utilities (local)",
    "jaraco-classes": "Windows credential helpers (local)",
    "jaraco-context": "Context managers (local)",
    "jaraco-functools": "Functional helpers (local)",
    "platformdirs": "Local directories (local)",
    "threadpoolctl": "BLAS thread control (local)",
    "tqdm": "Progress bars (local)",
    "tzdata": "Timezone data (static)",
    " blinker": "Signal dispatch (local)",
    "anyio": "Async compatibility layer (local, uvicorn uses it)",
    "annotated-types": "Type metadata (local)",
    "pyparsing": "Parser generator (local)",
    "sortedcontainers": "Sorted collections (local)",
    "filelock": "File locking (local)",
}

# Network-capable packages that require explicit verification.
NETWORK_OPT_IN = {
    "requests": "HTTP client. Verify no import in backend runtime source.",
    "urllib3": "HTTP client. Verify no import in backend runtime source.",
    "httpx": "HTTP client. Verify only used by tests/dev tooling.",
    "httpcore": "HTTP transport. Verify only used by tests.",
    "aiohttp": "Async HTTP client/server. Verify no import.",
}


def normalize_pkg_name(name: str) -> str:
    return name.lower().replace("-", "_").replace(".", "_")


def find_distribution(name: str):
    norm = normalize_pkg_name(name)
    for d in distmeta.distributions():
        if normalize_pkg_name(d.metadata.get("Name", "")) == norm:
            return d
    return None


def module_to_package(module_name: str) -> str | None:
    """Map a Python module import to its top-level distribution package."""
    top = module_name.split(".")[0]
    try:
        dists = distmeta.packages_distributions().get(top)
        if dists:
            return dists[0]
    except Exception:
        pass
    return None


def extract_imports_from_file(path: Path) -> set[str]:
    imports: set[str] = set()
    try:
        source = path.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return imports
    try:
        tree = ast.parse(source)
    except SyntaxError:
        # Regex fallback for JS/TS or malformed Python
        for line in source.splitlines():
            for m in re.finditer(r"(?:^|\s)import\s+([A-Za-z_][A-Za-z0-9_.]*)|(?:^|\s)from\s+([A-Za-z_][A-Za-z0-9_.]*)\s+import", line):
                imports.add(m.group(1) or m.group(2))
        return imports

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.add(alias.name)
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                imports.add(node.module)
    return imports


def collect_project_imports() -> set[str]:
    imports: set[str] = set()
    for src_dir in SOURCE_DIRS:
        if not src_dir.exists():
            continue
        for path in src_dir.rglob("*"):
            if path.is_file() and path.suffix in {".py", ".ts", ".tsx", ".js", ".jsx", ".mjs"}:
                imports |= extract_imports_from_file(path)
    return imports


def sample_package_source(package_name: str) -> dict:
    """Sample a few source files for network patterns."""
    d = find_distribution(package_name)
    if d is None:
        return {"found": False, "matches": []}
    loc = d.locate_file("")
    if loc is None:
        return {"found": False, "matches": []}
    root = Path(loc).resolve()
    if root.suffix == ".dist-info":
        for candidate in (root.parent / package_name, root.parent / package_name.replace("-", "_")):
            if candidate.exists():
                root = candidate
                break
    if not root.exists() or not root.is_dir():
        return {"found": False, "matches": []}

    matches: list[dict] = []
    py_files = [p for p in root.rglob("*.py")]
    # Sample up to 100 files to keep it fast
    for path in py_files[:100]:
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue
        rel = path.relative_to(root).as_posix()
        for pat in NETWORK_CALL_PATTERNS + TELEMETRY_KEYWORDS + UPDATE_CHECK_PATTERNS:
            for m in pat.finditer(text):
                line = text[:m.start()].count("\n") + 1
                matches.append({
                    "file": rel,
                    "line": line,
                    "kind": "network_call" if pat in NETWORK_CALL_PATTERNS else ("telemetry" if pat in TELEMETRY_KEYWORDS else "update_check"),
                    "pattern": pat.pattern,
                    "snippet": text[m.start():m.end()].strip(),
                })
        if len(matches) >= 20:
            break
    return {"found": True, "location": str(root), "matches": matches}


def classify(package_name: str, used_in_project: bool, scan: dict) -> dict:
    name = package_name.lower()
    if name in SAFE_CATEGORIES:
        return {"category": "safe", "reason": SAFE_CATEGORIES[name]}
    if name in NETWORK_OPT_IN:
        return {"category": "network-opt-in", "reason": NETWORK_OPT_IN[name], "action": "Confirm no project import or gate usage"}
    if scan.get("matches"):
        return {"category": "needs-review", "reason": "Source samples contain network/telemetry/update-check patterns"}
    if used_in_project:
        return {"category": "safe", "reason": "Imported by project; no suspicious patterns in sampled source"}
    return {"category": "unused", "reason": "Not imported by project source"}


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    json_path = OUTPUT_DIR / "dependency_report.json"
    md_path = OUTPUT_DIR / "dependency_audit.md"

    project_imports = collect_project_imports()
    project_packages: set[str] = set()
    for imp in project_imports:
        pkg = module_to_package(imp)
        if pkg:
            project_packages.add(pkg)

    # Parse requirements.txt
    req_packages: set[str] = set()
    req_file = PROJECT_ROOT / "requirements.txt"
    if req_file.exists():
        for line in req_file.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#"):
                m = re.match(r"([A-Za-z0-9_.-]+)", line)
                if m:
                    req_packages.add(m.group(1))

    all_packages = req_packages | project_packages

    results = []
    for pkg in sorted(all_packages):
        scan = sample_package_source(pkg)
        used = pkg in project_packages
        classification = classify(pkg, used, scan)
        dist = find_distribution(pkg)
        version = dist.metadata.get("Version", "") if dist else ""
        results.append({
            "name": pkg,
            "version": version,
            "imported_by_project": used,
            "in_requirements": pkg in req_packages,
            "found_installed": scan.get("found", False),
            "location": scan.get("location"),
            **classification,
            "matches": scan.get("matches", []),
        })

    flagged = [r for r in results if r["category"] == "needs-review"]
    network_opt_in = [r for r in results if r["category"] == "network-opt-in"]
    unused = [r for r in results if r["category"] == "unused"]

    report = {
        "python_version": sys.version.split()[0],
        "total_packages_reviewed": len(results),
        "project_imports_count": len(project_imports),
        "safe_count": sum(1 for r in results if r["category"] == "safe"),
        "needs_review_count": len(flagged),
        "network_opt_in_count": len(network_opt_in),
        "unused_count": len(unused),
        "flagged": flagged,
        "network_opt_in": network_opt_in,
        "unused": unused,
        "packages": results,
    }

    json_path.write_text(json.dumps(report, indent=2), encoding="utf-8")

    md = ["# Dependency Audit Report (TASK-038.8)\n"]
    md.append(f"Generated: 2026-06-23  ")
    md.append(f"Python: {report['python_version']}  ")
    md.append(f"Total packages reviewed: {report['total_packages_reviewed']}  ")
    md.append(f"Project imports parsed: {report['project_imports_count']}  ")
    md.append(f"Safe: {report['safe_count']} | Needs review: {report['needs_review_count']} | Network opt-in: {report['network_opt_in_count']} | Unused: {report['unused_count']}\n")

    md.append("## Packages Flagged for Review\n")
    if flagged:
        md.append("| Package | Version | Reason | Match Count |\n|---|---|---|---|\n")
        for r in flagged:
            md.append(f"| {r['name']} | {r['version']} | {r['reason']} | {len(r['matches'])} |\n")
    else:
        md.append("None.\n")

    md.append("\n## Network-Capable Packages (verify no ungated use)\n")
    if network_opt_in:
        md.append("| Package | Version | Reason | Action |\n|---|---|---|---|\n")
        for r in network_opt_in:
            md.append(f"| {r['name']} | {r['version']} | {r['reason']} | {r.get('action', '')} |\n")
    else:
        md.append("None.\n")

    md.append("\n## All Reviewed Packages\n")
    md.append("| Package | Version | Category | Reason | Imported | In requirements |\n|---|---|---|---|---|---|\n")
    for r in results:
        md.append(f"| {r['name']} | {r['version']} | {r['category']} | {r['reason']} | {'Yes' if r['imported_by_project'] else 'No'} | {'Yes' if r['in_requirements'] else 'No'} |\n")

    md_path.write_text("".join(md), encoding="utf-8")

    print(f"JSON: {json_path}")
    print(f"Markdown: {md_path}")
    print(f"Needs review: {len(flagged)}")
    print(f"Network opt-in: {len(network_opt_in)}")
    print(f"Unused: {len(unused)}")


if __name__ == "__main__":
    main()
