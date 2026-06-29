import re, json
from pathlib import Path

root = Path(__file__).resolve().parents[3]
routers_dir = root / 'backend' / 'routers'
frontend_dir = root / 'frontend' / 'src'

# ── Helpers ──────────────────────────────────────────────────────────────────

def _path_to_regex(path: str) -> re.Pattern:
    """Convert a FastAPI-style path with {params} to a matching regex."""
    # Escape everything, then replace \{param\} with [^/]+
    escaped = re.escape(path)
    escaped = re.sub(r'\\\{[^}]+\\\}', r'[^/]+', escaped)
    return re.compile(f'^{escaped}$')


def _path_matches(fp: str, fc: str) -> bool:
    """Check if frontend route fc matches backend path fp (with {params})."""
    # Direct match
    if fc == fp:
        return True
    # Frontend route is prefix of backend path (collection covers detail)
    if fp.startswith(fc + '/'):
        return True
    # Backend path has {params} — check if frontend route matches the pattern
    if '{' in fp:
        pat = _path_to_regex(fp)
        if pat.match(fc):
            return True
        # Also check if the collection prefix (strip /{param}) matches
        base = re.sub(r'/\{[^}]+\}.*$', '', fp)
        if fc == base or fc.startswith(base + '/'):
            return True
    return False

# ── Endpoint discovery ───────────────────────────────────────────────────────

endpoints = []
for f in sorted(routers_dir.glob('*.py')):
    if f.name in ('__init__.py',):
        continue
    mod = f.stem
    text = f.read_text(encoding='utf-8', errors='ignore')
    prefix_match = re.search(r'prefix\s*=\s*"([^"]+)"', text)
    if not prefix_match:
        prefix_match = re.search(r"prefix\s*=\s*'([^']+)'", text)
    raw_prefix = prefix_match.group(1) if prefix_match else f'/{mod}'
    prefix = ('/api' + raw_prefix).replace('//', '/')

    method_pattern = re.compile(
        r'@router\.(get|post|put|patch|delete|head|options)\(\s*"([^"]*)"',
        re.IGNORECASE,
    )
    for m, path in method_pattern.findall(text):
        full = (prefix + path).replace('//', '/')
        endpoints.append({
            'module': mod,
            'method': m.upper(),
            'path': path or '/',
            'full_path': full,
            'has_frontend': False,
        })
    method_pattern2 = re.compile(
        r"@router\.(get|post|put|patch|delete|head|options)\(\s*'([^']*)'",
        re.IGNORECASE,
    )
    for m, path in method_pattern2.findall(text):
        full = (prefix + path).replace('//', '/')
        endpoints.append({
            'module': mod,
            'method': m.upper(),
            'path': path or '/',
            'full_path': full,
            'has_frontend': False,
        })

frontend_calls = set()
for f in frontend_dir.rglob('*'):
    if not f.is_file() or f.suffix not in ('.ts', '.tsx', '.js', '.jsx'):
        continue
    text = f.read_text(encoding='utf-8', errors='ignore')
    for match in re.findall(r'["\'`](/api/[a-zA-Z0-9_/{}.-]+)', text):
        frontend_calls.add(match.rstrip('/'))

for ep in endpoints:
    fp = ep['full_path'].rstrip('/')
    for fc in frontend_calls:
        if _path_matches(fp, fc):
            ep['has_frontend'] = True
            ep['matched_frontend_route'] = fc
            break

# Group by module
covered = sorted({e['full_path'] for e in endpoints if e['has_frontend']})
uncovered = sorted({e['full_path'] for e in endpoints if not e['has_frontend']})
modules = {}
for e in endpoints:
    modules.setdefault(e['module'], []).append(e)

# Markdown matrix
lines = [
    "# Backend → Frontend Coverage Map",
    "",
    f"**Generated:** 2026-06-29",
    "",
    "## Summary",
    "",
    f"- Total backend endpoints: **{len(endpoints)}**",
    f"- Covered by frontend code: **{len(covered)}**",
    f"- Backend-only (no frontend consumer): **{len(uncovered)}**",
    f"- Unique frontend API routes found: **{len(frontend_calls)}**",
    "",
    "## Legend",
    "",
    "- ✅ = Frontend calls this endpoint (string match in `frontend/src/**`)",
    "- ❌ = No frontend consumer found",
    "",
    "## By Module",
    "",
    "| Module | Endpoint | Method | Frontend |",
    "|--------|----------|--------|----------|",
]
for mod in sorted(modules):
    seen = set()
    for e in modules[mod]:
        key = (e['method'], e['full_path'])
        if key in seen:
            continue
        seen.add(key)
        flag = '✅' if e['has_frontend'] else '❌'
        lines.append(f"| {mod} | `{e['method']} {e['full_path']}` | {e['method']} | {flag} |")

lines += [
    "",
    "## Backend-only Endpoints (no frontend consumer)",
    "",
]
for ep in uncovered:
    lines.append(f"- `{ep}`")

lines += [
    "",
    "## Frontend Routes Found",
    "",
]
for route in sorted(frontend_calls):
    lines.append(f"- `{route}`")

md_path = root / 'shared' / 'tasks' / 'v3.11.6' / 'BACKEND_FRONTEND_COVERAGE_MAP.md'
md_path.write_text('\n'.join(lines), encoding='utf-8')

json_path = root / 'shared' / 'tasks' / 'v3.11.6' / 'BACKEND_FRONTEND_COVERAGE_MAP.json'
coverage = {
    'generated_at': '2026-06-29',
    'total_endpoints': len(endpoints),
    'frontend_covered': len(covered),
    'uncovered': len(uncovered),
    'frontend_routes_found': sorted(frontend_calls),
    'endpoints': endpoints,
}
json_path.write_text(json.dumps(coverage, indent=2), encoding='utf-8')

print(f"Wrote {md_path}")
print(f"Wrote {json_path}")
print(f"Total endpoints: {len(endpoints)}")
print(f"Frontend covered: {len(covered)}")
print(f"Uncovered: {len(uncovered)}")
print(f"Frontend routes found: {len(frontend_calls)}")
