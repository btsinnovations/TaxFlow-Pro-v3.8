# TASK-036 — Pre-Implementation Audit Report

**Status:** Report-only; no fixes applied  
**Auditor:** Jane  
**Date:** 2026-06-22  
**Scope:** Determine what Phase 1/2 cleanup and Phase 3/v3.9.1 work already exists in `TaxFlow-Pro-v3.9/` before TASK-036 begins.

---

## Executive Summary

1. **Phase 1/2 cleanup is partially complete.** `.env.example` and parser unification exist; PostgreSQL/RLS live validation and merchant alias configuration are not done.
2. **A large v3.9.1 patch release is already in the tree.** `CHANGES.md` documents it as sections 14–23 (server-side token revocation, column-level encryption, backup/restore, migration health, password policy, PII redaction, brute-force protection, CI/CD, parser expansion, etc.). Many of these features correspond to items in `docs/TODO_FIRST.md` sections 3.4a–3.4g.
3. **I did not execute all of this work in the current session.** My recent documented work is TASK-032 (SAST/SBOM, touched `backend/local/backup.py` for Bandit fix), TASK-034 (timing-safe auth), and TASK-035 (temp file cleanup + v3.9 canonical reconciliation). The auth, encryption, backup/restore, redaction, migration health, parser expansion, and CI/CD additions pre-date today or were done in prior sessions not fully logged in my current short-term memory.
4. **Current tests pass:** `python -m pytest backend/tests tests -q` → **346 passed, 97 warnings, 0 failed** in 3m 34s.

---

## 1. Phase 1 / Loop 1 Gaps

| # | Task | Status | Evidence |
|---|------|--------|----------|
| 1.1 | Add `.env.example` | ✅ Present | `.env.example` exists; `git status` shows `M .env.example` |
| 1.2 | Validate baseline migration against live PostgreSQL | ❌ Not done | Migration `d75a7eba9fd0_baseline_schema.py` exists; no evidence of live Postgres run |
| 1.3 | Make merchant alias matching configurable | ❌ Not done | `phase3_pipeline/categorizer.py` still uses hardcoded start-of-string behavior |

---

## 2. Phase 2 Gaps

| # | Task | Status | Evidence |
|---|------|--------|----------|
| 2.1 | Validate PostgreSQL RLS policies end-to-end | ❌ Not done | `backend/rls.py`, RLS migration `b9f4e2c8d310`, and `backend/tests/test_rls.py` exist, but tests run on SQLite |
| 2.2 | Complete parser unification | ✅ Done | `backend/parsers/` canonical API + `phase3_pipeline/pdf_parser.py` wrapper; `test_parser_unification.py` passes |
| 2.3 | Exercise `/api` + `X-Tenant-ID` under real Postgres | ❌ Not done | No evidence of Postgres-backed smoke test |

---

## 3. Phase 3 / v3.9.1 Work Already in Tree

The following files are untracked (`??` in `git status`) or modified after the initial v3.7-only commit. They map to v3.9.1 patch-release sections in `CHANGES.md` and/or `docs/TODO_FIRST.md` Phase 3 items.

### 3.1 Local-first / local-auth modules (`backend/local/`, `backend/crypto/`)

| File | Last Write | Maps to |
|------|------------|---------|
| `backend/local/__init__.py` | 6/15 5:56 AM | Phase 3 scaffold |
| `backend/local/offline.py` | 6/15 5:58 AM | TODO 3.2 / offline self-test |
| `backend/local/guards.py` | 6/15 6:23 AM | TODO 3.4e / hardening |
| `backend/local/ml_pipeline.py` | 6/15 6:18 AM | TODO 3.6 / local ML retrain |
| `backend/local/settings.py` | 6/19 6:13 PM | TODO 3.4f / `.local_secret` storage |
| `backend/local/crypto.py` | 6/20 2:24 PM | CHANGES §16 / TODO 3.3 encryption |
| `backend/local/column_encryption.py` | 6/20 2:24 PM | CHANGES §16 |
| `backend/local/migration_health.py` | 6/20 7:57 PM | CHANGES §21 / TODO 3.4 health |
| `backend/local/keyring_secret.py` | 6/21 4:48 AM | CHANGES §16 / local secret keyring |
| `backend/local/backup.py` | 6/22 2:26 AM | CHANGES §21 / TODO 3.8 backup |
| `backend/local/auth.py` | 6/22 4:56 AM | CHANGES §15/20 / TODO 3.7 local auth |
| `backend/crypto/backup_crypto.py` | 6/21 5:10 AM | CHANGES §21 encrypted backup |

### 3.2 Auth, rate-limit, and security modules

| File | Last Write | Maps to |
|------|------------|---------|
| `backend/auth.py` | 6/22 4:56 AM | CHANGES §15/16/20 hybrid/local auth |
| `backend/auth_rate_limit.py` | 6/20 10:55 PM | CHANGES §23 brute-force protection |
| `backend/rate_limit.py` | 6/21 9:56 PM | CHANGES §23 global rate limiting |
| `backend/routers/auth.py` | 6/22 5:48 AM | CHANGES §15/16/20/23 |
| `backend/utils/password_policy.py` | 6/21 10:11 PM | CHANGES §20 password policy |
| `backend/utils/redaction.py` | 6/20 5:22 PM | CHANGES §20 PII redaction |

### 3.3 Audit / append-only / signatures

| File | Last Write | Maps to |
|------|------------|---------|
| `backend/audit/__init__.py` | 6/21 8:19 AM | CHANGES §20 / audit logging |
| `backend/audit/append_only.py` | 6/21 8:24 AM | CHANGES §20 / append-only trigger |
| `backend/audit/audit_trail.py` | 6/21 10:23 PM | CHANGES §20 / signed audit trail |
| `backend/security/audit_sign.py` | 6/21 10:26 PM | CHANGES §20 Ed25519 signatures |

### 3.4 Alembic migrations (all untracked)

| Migration | Last Write | Purpose |
|-----------|------------|---------|
| `c3a1f7e9d220_add_local_auth_columns_to_users.py` | 6/15 6:03 AM | Local auth columns |
| `d2e3f4a5b6c7_add_date_columns_and_cascade_constraints.py` | 6/19 6:18 PM | Date cols / cascades |
| `e8b7c1d5f3a2_add_audit_entries_and_depreciation_assets.py` | 6/19 7:35 AM | Audit + depreciation tables |
| `a1b2c3d4e5f6_add_stage3_rules_flags_gl_workpaper.py` | 6/19 3:49 PM | Stage3 rules/flags/GL/workpaper |
| `377bb18e5f7c_merge_local_auth_and_v3_9_services_heads.py` | 6/19 7:37 AM | Merge heads |
| `f2a9b8c1d4e5_add_refresh_tokens_table.py` | 6/21 10:32 AM | Refresh tokens |
| `842bfa1713f4_merge_audit_chain_hash_and_refresh_.py` | 6/21 10:33 AM | Merge heads |
| `c4062c0c95ff_add_audit_chain_hash.py` | 6/21 5:00 AM | Audit chain hash |
| `1116e8143fc6_add_revoked_tokens_table.py` | 6/20 2:20 PM | Token revocation |
| `4f0bb0ee4bff_add_audit_entry_ed25519_signature_column.py` | 6/21 10:24 PM | Ed25519 sigs |
| `2227f9254a8b_add_audit_description_and_redaction_support.py` | 6/20 5:24 PM | Audit description + redaction |

### 3.5 Backup/restore scripts

| File | Last Write | Maps to |
|------|------------|---------|
| `scripts/backup.py` | unknown (untracked) | CHANGES §21 / TODO 3.8 |
| `scripts/restore.py` | unknown (untracked) | CHANGES §21 / TODO 3.8 |
| `scripts/sqlcipher_spike.py` | unknown (untracked) | CHANGES §16 spike |

### 3.6 Security / SAST / SBOM scripts

| File | Last Write | Maps to |
|------|------------|---------|
| `scripts/sast_scan.py` | 6/22 2:34 AM | TASK-032 / CHANGES §? |
| `scripts/sbom_generate.py` | 6/22 2:34 AM | TASK-032 |
| `scripts/vuln_scan.py` | 6/21 7:40 AM | TASK-032 |
| `scripts/secret_scan.py` | 6/21 7:43 AM | Security pipeline |
| `scripts/build_bloom_filter.py` | 6/21 10:10 PM | CHANGES §? breach bloom |
| `.github/workflows/security.yml` | 6/22 2:34 AM | TASK-032 CI |
| `.github/workflows/ci.yml` | 6/22 2:14 AM | CHANGES §22 CI/CD |
| `.pre-commit-config.yaml` | 6/22 2:14 AM | CHANGES §22 |

### 3.7 Tests covering Phase 3 / v3.9.1 features

- `backend/tests/test_hybrid_auth.py` — local/JWT hybrid auth, revocation, brute-force (CHANGES §15, §20, §23)
- `backend/tests/test_encryption.py` — column encryption (CHANGES §16)
- `backend/tests/test_backup_restore.py` — backup/restore (CHANGES §21)
- `backend/tests/test_migration_health.py` — migration health (CHANGES §21)
- `backend/tests/test_redaction.py` — PII redaction (CHANGES §20)
- `backend/tests/test_local_first.py` — offline / local-first behavior
- `backend/tests/test_refresh_tokens.py` — refresh tokens
- `backend/tests/test_keyring_secret.py` — keyring secret storage
- `backend/tests/test_append_only.py`, `test_audit_trail.py`, `test_audit_sign.py` — audit chain
- `backend/tests/test_breach_bloom.py` — breach bloom filter
- `backend/tests/test_global_rate_limit.py` — rate limiting

---

## 4. Origin Assessment

- **Documented in `CHANGES.md` as v3.9.1:** Sections 14–23 describe most of the above work as a coordinated patch release. This suggests the work was done under a v3.9.1 plan, not ad-hoc.
- **My recent memory log (`memory/2026-06-22.md`) only documents TASK-032 (SAST/SBOM).** It explicitly does **not** list auth, encryption, backup/restore, redaction, or migration health as work I performed today.
- **Some files I did touch:** `backend/local/backup.py` (Bandit fix in TASK-032), `backend/parsers/generic_pdf.py` (Bandit fix in TASK-032), `backend/security/timing_safe.py` (TASK-034), `backend/utils/temp_file_cleanup.py` / `backend/routers/upload.py` / `backend/parsers/ocr_parser.py` (TASK-035).
- **Conclusion:** A substantial v3.9.1 feature set is already present, but I cannot confirm from my own memory that every piece was executed with explicit Josh approval. The canonical `CHANGES.md` treats it as approved v3.9.1 scope.

---

## 5. Current Test Results

```bash
cd ~/.openclaw/workspace/projects/TaxFlow-Pro/TaxFlow-Pro-v3.9
python -m pytest backend/tests tests -q
346 passed, 97 warnings in 214.21s (0:03:34)
```

Alembic head after `upgrade head`:
```text
2227f9254a8b -> add_audit_description_and_redaction_support (head)
```

---

## 6. Recommendations

1. **Do not treat the tree as unapproved junk.** `CHANGES.md` presents a coherent v3.9.1 release narrative, and all tests pass. The risk is approval traceability, not technical incoherence.
2. **Confirm with Josh whether v3.9.1 as documented was approved.** If yes, TASK-036 can be reframed as "close remaining Phase 1/2 gaps and validate v3.9.1 release readiness."
3. **If v3.9.1 was not approved, roll back to the last approved baseline** (likely pre-v3.9.1, around the initial v3.7 → v3.9 reconciliation / TASK-035 state). That would mean removing or reverting sections 14–23 of `CHANGES.md` and the associated files.
4. **Regardless, complete the Phase 1/2 gaps before any new Phase 3 work:**
   - Validate migrations against live PostgreSQL.
   - Validate RLS end-to-end under PostgreSQL.
   - Make merchant alias matching configurable.
   - Add a Postgres-backed `/api` + `X-Tenant-ID` smoke test.

---

## 7. Files Changed in This Audit (Report Only)

- `shared/tasks/TASK-036-AUDIT.md` (this file)

No source code was modified.
