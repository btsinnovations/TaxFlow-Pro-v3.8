# v3.11.0 Merge + Tag Checklist

**Use this when Bundle 4 is complete and full test suites are green.**

---

## Pre-merge verification

- [ ] `git status` clean on `v3.11-dev`
- [ ] Backend full suite passes: `python -m pytest backend/tests/ tests/`
  - Expected: 660+ passed, 1 skipped
- [ ] Frontend build passes: `cd frontend && npm run build`
- [ ] Frontend tests pass: `cd frontend && npm test`
- [ ] Alembic upgrade test passes on fresh SQLite DB
- [ ] Alembic upgrade test passes on simulated v3.10 DB
- [ ] Backup import test passes with synthetic v3.10 JSON
- [ ] `backend/version.py` == `"3.11.0"`
- [ ] `frontend/package.json` version == `"3.11.0"`
- [ ] `CHANGES.md` Sections 57–63 are complete and accurate
- [ ] `docs/SUPPORTED_INSTITUTIONS.md` exists and lists 18 institutions
- [ ] No `frontend/dist` committed (should be in `.gitignore`)
- [ ] No test-only routers exposed in production builds

---

## Merge steps

1. Fetch latest `main`:
   ```bash
   git fetch origin
   ```
2. Switch to main and merge:
   ```bash
   git checkout main
   git merge --no-ff v3.11-dev -m "release(v3.11.0): complete bookkeeping platform + parser expansion + OFX import"
   ```
3. Push main:
   ```bash
   git push origin main
   ```
4. Tag release:
   ```bash
   git tag -a v3.11.0 -m "TaxFlow Pro v3.11.0"
   git push origin v3.11.0
   ```

---

## Post-tag packaging (v3.11.5 scope, not v3.11)

- [ ] Windows installer built from `v3.11.0` tag
- [ ] Ubuntu `.deb` built from `v3.11.0` tag
- [ ] macOS `.app` + DMG built and notarized (deferred until Apple host available)

---

## Public distribution (deferred until general-public release)

- [ ] Microsoft Defender file submission for installer
- [ ] Code signing certificate purchased and applied
- [ ] Linux `.deb` GPG-signed or published to PPA
- [ ] macOS notarization completed

---

## Notes

- Do not merge without explicit Josh approval.
- Do not tag `v3.11.0` until the full backend + frontend test suites pass.
- Public trust/code-signing work stays in v3.11.5 per Josh directive.
