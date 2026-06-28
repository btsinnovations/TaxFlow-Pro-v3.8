# TaxFlow Pro v3.11.6 — Track 8 Branch Spec (B6 Frontend UI Shell)

**Base branch:** `v3.11.6-dev` (HEAD `675af7c`)

---

## Branch

```
v3.11.6-dev-PHASE4-TRACK8-frontend-ui-shell
```

---

## Lifecycle

### 1. Cut branch

```bash
git checkout v3.11.6-dev
git pull origin v3.11.6-dev
git checkout -b v3.11.6-dev-PHASE4-TRACK8-frontend-ui-shell
git push -u origin v3.11.6-dev-PHASE4-TRACK8-frontend-ui-shell
```

### 2. Work in branch

All frontend changes stay in this branch. Backend changes are out of scope unless a frontend discovery requires an API contract adjustment.

### 3. Pre-merge checklist

- [ ] `npm run build` passes
- [ ] `npm run test` passes
- [ ] `npm run lint` passes
- [ ] Backend regression still passes (quick smoke: `python -m pytest backend/tests`)
- [ ] API contract updated if endpoint shapes changed
- [ ] Commit history clean and meaningful
- [ ] Branch pushed to origin

### 4. Merge

```bash
git checkout v3.11.6-dev
git merge v3.11.6-dev-PHASE4-TRACK8-frontend-ui-shell --no-ff -m "Merge Track 8 (B6 Frontend UI Shell) into v3.11.6-dev

Includes:
- TanStack Table register scaffolding
- Unified register component
- COA tree component
- Reports center with charts and CSV export
- Reconciliation UI
- Tax export UI
- Inventory center
- Profile roles UI"
git push origin v3.11.6-dev
```

---

## Commit Message Convention

```
feat(v3.11.6/B6.01): TanStack Table scaffolding and transaction hook
test(v3.11.6/B6.02): register component tests
docs(v3.11.6/B6): update API contract for reports endpoint shape
fix(v3.11.6/B6.04): chart rendering on empty report data
```

---

## Risk Mitigation

| Risk | Mitigation |
|------|------------|
| Frontend build breaks from stale backend contract | Read `API-CONTRACT.md` first; verify endpoints with curl/TestClient if uncertain |
| Scope creep into full app routing | Keep components route-ready; do not implement full navigation/routing unless trivial |
| Missing shared component library | Reuse existing shadcn/ui or plain Tailwind; do not add new UI frameworks |
| Backend changes needed | If discovered, propose to James; do not modify backend without approval |

---

## Authority

- Jane executes.
- James approves merge to `v3.11.6-dev`.
- Josh has final go/no-go.
