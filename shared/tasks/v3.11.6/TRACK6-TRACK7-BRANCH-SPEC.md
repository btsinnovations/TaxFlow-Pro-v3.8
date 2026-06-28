# TaxFlow Pro v3.11.6 — Branch & Merge Specification (Tracks 6 & 7)

**Base branch:** `v3.11.6-dev` (current HEAD: `5a61772` after Track 5 merge)

---

## New Branches

| Track | Branch name | Cut from | Scope |
|-------|-------------|----------|-------|
| 6 | `v3.11.6-dev-PHASE3-TRACK6-financial-operations` | `v3.11.6-dev` | B4: reconciliation, reports, tax exports, budget |
| 7 | `v3.11.6-dev-PHASE3-TRACK7-invoicing-ap-ar` | `v3.11.6-dev` | B5: invoices, bills, payments, aging |

---

## Naming Convention

```
v3.11.6-dev-PHASE{phase}-TRACK{track}-{short-theme}
```

- Phase 3 = B4 + B5 (Financial Operations)
- Tracks 6 and 7 are independent and may be merged in either order

---

## Branch Lifecycle

### 1. Cut the branches

```bash
git checkout v3.11.6-dev
git pull origin v3.11.6-dev

git checkout -b v3.11.6-dev-PHASE3-TRACK6-financial-operations
git push -u origin v3.11.6-dev-PHASE3-TRACK6-financial-operations

git checkout v3.11.6-dev
git checkout -b v3.11.6-dev-PHASE3-TRACK7-invoicing-ap-ar
git push -u origin v3.11.6-dev-PHASE3-TRACK7-invoicing-ap-ar
```

### 2. Work in isolation

Each builder works on their track branch only. No cross-track commits.

### 3. Pre-merge checklist (per track)

- [ ] All module tests pass (`backend/tests/test_*.py`)
- [ ] Full `backend/tests` regression passes (target: 0 failures)
- [ ] `frontend` build passes (`npm run build`)
- [ ] Alembic single head confirmed (`alembic heads` returns one line)
- [ ] API contract updated (`shared/tasks/v3.11.6/API-CONTRACT.md`)
- [ ] Commit history is clean and meaningful
- [ ] Branch pushed to origin

### 4. Merge strategy

Because Tracks 6 and 7 may both add Alembic migrations, use **merge-order checks**:

```bash
# After first track merges
git checkout v3.11.6-dev
git merge v3.11.6-dev-PHASE3-TRACK6-financial-operations --no-ff -m "..."
git push origin v3.11.6-dev

# Rebase or merge second track from updated v3.11.6-dev
git checkout v3.11.6-dev-PHASE3-TRACK7-invoicing-ap-ar
git merge origin/v3.11.6-dev  # resolve any migration conflicts here
# run tests
# then merge back:
git checkout v3.11.6-dev
git merge v3.11.6-dev-PHASE3-TRACK7-invoicing-ap-ar --no-ff -m "..."
git push origin v3.11.6-dev
```

If both tracks add migrations, merge one first, then refresh the second track's migration `down_revision` to the new head before merging.

### 5. Post-merge

- Delete remote track branches after successful merge (optional but recommended)
- Update `V3.11.6-TASKS.md` statuses
- Update daily memory log

---

## Commit Message Convention

```
feat(v3.11.6/B4.01): bank reconciliation auto-match and status endpoints
test(v3.11.6/B4.01): add reconciliation API tests
docs(v3.11.6/B4): update API contract with finalized endpoints
fix(v3.11.6/B5): correct invoice status transitions on partial payment
```

---

## Risk Mitigation

| Risk | Mitigation |
|------|------------|
| Alembic multi-head when both tracks add migrations | Merge one track first; refresh second track migration head before second merge |
| Status field collision between B5 invoices and B2 transactions | Use separate `Invoice.status` enum; never overload `Transaction.status` |
| Reports depend on B5 aging | Not required for Track 6; defer to B6 frontend or later integration |
| Time/scope creep | Strictly defer frontend UI, real bank statement OCR, and payment gateway integration |

---

## Authority

- Jane executes both tracks under these specs.
- James reviews and approves each merge.
- Josh has final go/no-go on merge to `v3.11.6-dev`.
