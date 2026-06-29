# TaxFlow Pro v3.11.6 — Track 10 Branch Spec (B8 Phase 2 Bank Parser Expansion)

**Base branch:** `v3.11.6-dev` (HEAD `18807ed`)

---

## Branch

```
v3.11.6-dev-PHASE6-TRACK10-bank-parser-expansion
```

---

## Lifecycle

### 1. Cut branch

```bash
git checkout v3.11.6-dev
git pull origin v3.11.6-dev
git checkout -b v3.11.6-dev-PHASE6-TRACK10-bank-parser-expansion
git push -u origin v3.11.6-dev-PHASE6-TRACK10-bank-parser-expansion
```

### 2. Work in branch

Parser expansion only. Avoid touching core bookkeeping code unless tests reveal a real bug.

### 3. Pre-merge checklist

- [ ] `data/docuclipper-institutions.json` committed with ≥100 institutions
- [ ] Family parser modules committed and tested
- [ ] `backend/tests/test_bank_parsers.py` ≥70 tests, all green
- [ ] Full SQLite regression passes
- [ ] Full PostgreSQL regression passes (`TEST_DATABASE_URL`)
- [ ] Detection registry updated
- [ ] Commit history clean and meaningful
- [ ] Branch pushed to origin

### 4. Merge

```bash
git checkout v3.11.6-dev
git merge v3.11.6-dev-PHASE6-TRACK10-bank-parser-expansion --no-ff -m "Merge Track 10 (B8 Phase 2 Bank Parser Expansion) into v3.11.6-dev

Includes:
- DocuClipper institution registry (100+ institutions)
- Layout-family parser modules for CSV, OFX, PDF tables, credit card, brokerage
- Expanded detection registry
- 70+ bank parser tests"
git push origin v3.11.6-dev
```

---

## Commit Message Convention

```
feat(v3.11.6/B8.Ph2): scrape and normalize DocuClipper institution list
feat(v3.11.6/B8.Ph2): add layout family parser skeletons
feat(v3.11.6/B8.Ph2): expand institution detection registry to 100+ banks
test(v3.11.6/B8.Ph2): add synthetic fixtures and expand bank parser suite
```

---

## Risk Mitigation

| Risk | Mitigation |
|------|------------|
| Heavy new dependencies | Reuse existing dependencies; add only after approval |
| PDF table extraction fragile | Start with regex/text fallback; table extraction is a stretch goal |
| Test count grows large but shallow | Require at least one happy-path test per family + edge cases |
| Institution name ambiguity | Use lowercase normalized matching with keyword fallback |

---

## Authority

- Jane executes.
- James approves merge to `v3.11.6-dev`.
- Josh has final go/no-go.
