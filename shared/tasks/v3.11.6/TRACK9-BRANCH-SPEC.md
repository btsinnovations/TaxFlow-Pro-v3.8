# TaxFlow Pro v3.11.6 — Track 9 Branch Spec (B7 Packaging & Platform Hardening)

**Base branch:** `v3.11.6-dev` (HEAD `4822447`)

---

## Branch

```
v3.11.6-dev-PHASE5-TRACK9-packaging-hardening
```

---

## Lifecycle

### 1. Cut branch

```bash
git checkout v3.11.6-dev
git pull origin v3.11.6-dev
git checkout -b v3.11.6-dev-PHASE5-TRACK9-packaging-hardening
git push -u origin v3.11.6-dev-PHASE5-TRACK9-packaging-hardening
```

### 2. Work in branch

Packaging/hardening changes only. Avoid touching backend business logic unless a test discovery requires it.

### 3. Pre-merge checklist

- [ ] B7.01 tests pass (`backend/tests/test_single_instance.py`)
- [ ] Backend regression passes (SQLite): `python -m pytest backend/tests tests -q`
- [ ] Frontend build passes: `npm run build`
- [ ] Trust-signal docs updated
- [ ] macOS build scripts committed (smoke test if host available)
- [ ] Commit history clean and meaningful
- [ ] Branch pushed to origin

### 4. Merge

```bash
git checkout v3.11.6-dev
git merge v3.11.6-dev-PHASE5-TRACK9-packaging-hardening --no-ff -m "Merge Track 9 (B7 Packaging & Platform Hardening) into v3.11.6-dev

Includes:
- Single-instance enforcement on port 8000
- macOS .app / DMG build scripts
- Staged trust-signal documentation for Windows, Linux, and macOS"
git push origin v3.11.6-dev
```

---

## Commit Message Convention

```
feat(v3.11.6/B7.01): add single-instance enforcement on port 8000
test(v3.11.6/B7.01): single-instance detection and replacement tests
docs(v3.11.6/B7.03): document staged trust signals for Windows/Linux/macOS
feat(v3.11.6/B7.02): macOS .app and DMG build scripts
```

---

## Risk Mitigation

| Risk | Mitigation |
|------|------------|
| macOS smoke test unavailable | Deliver scripts; document deferred runtime validation |
| Single-instance logic breaks server startup | Keep existing startup path intact; only add pre-flight check |
| Trust-signal env vars cause build failures | Make all signing env vars optional with clear defaults |

---

## Authority

- Jane executes.
- James approves merge to `v3.11.6-dev`.
- Josh has final go/no-go.
