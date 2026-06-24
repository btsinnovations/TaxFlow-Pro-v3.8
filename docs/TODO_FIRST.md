# TaxFlow Pro — TODO First List (Pre-Phase 3 Completion)

**Status:** Draft — awaiting Josh approval  
**Purpose:** Address all known gaps from Phases 1, 2, and Phase 3 first half before proceeding with remaining Phase 3 work.  
**Created:** 2026-06-15  

---

## 0. Context

Phases 1 and 2 are code-complete on SQLite but contain unvalidated PostgreSQL/RLS paths and deferred items.  
Phase 3 is approved and specced in `CHANGES.md` section 13, but implementation has not started.  
This list consolidates every gap so they can be closed before the remainder of Phase 3 is built.

---

## 1. Phase 1 / Loop 1 Gaps

| # | Task | Why It Blocks | Files/Notes |
|---|------|---------------|-------------|
| 1.1 | **Add `.env.example`** | Production deployments need documented env vars (`DATABASE_URL`, `TAXFLOW_SECRET_KEY`). | Root `.env.example` |
| 1.2 | **Validate baseline migration against live PostgreSQL** | Migration has only been tested on SQLite. Need a real Postgres instance to confirm tenant columns, FKs, and indexes deploy cleanly. | `alembic/versions/d75a7eba9fd0_baseline_schema.py` |
| 1.3 | **Make merchant alias matching configurable** | Current start-of-string alias match may over-truncate descriptions. Add per-merchant config to opt into strict start-match vs substring replacement. | `phase3_pipeline/categorizer.py`, `categories.yaml` |

---

## 2. Phase 2 Gaps

| # | Task | Why It Blocks | Files/Notes |
|---|------|---------------|-------------|
| 2.1 | **Validate PostgreSQL RLS policies end-to-end** | RLS migration, middleware, and helpers are written but not exercised against real Postgres. Test `X-Tenant-ID` enforcement across all tables. | `backend/rls.py`, `backend/database.py`, `backend/api.py`, `alembic/versions/b9f4e2c8d310_enable_postgresql_row_level_security.py` |
| 2.2 | **Complete parser unification** | `backend/parsers/generic_pdf.py` and `phase3_pipeline/pdf_parser.py` still diverge in behavior and institution support. Move institution-specific logic into the canonical backend parser or a shared plugin registry. | `backend/parsers/`, `phase3_pipeline/parsers/`, `phase3_pipeline/pdf_parser.py` |
| 2.3 | **Exercise `/api` + `X-Tenant-ID` integration under real Postgres** | Frontend/backend alignment is validated on SQLite only. Need a Postgres-backed smoke test of the full upload/export flow. | `backend/api.py`, frontend `useAPI.ts` |

---

## 3. Phase 3 — First Half (Not Started)

These items are from `CHANGES.md` section 13 and must be built before Phase 3 is considered complete.

| # | Task | Why It Matters | Proposed Location |
|---|------|--------------|-------------------|
| 3.1 | **Audit every external dependency** | Replace or vendor anything that phones home at runtime. Must confirm no cloud API calls on startup or during processing. | `scripts/dependency_audit.py` or `backend/local/offline.py` | | ✅ Complete — see `docs/CLOUD_CODE_AUDIT.md` and `docs/DEPENDENCY_AUDIT.md` |
| 3.2 | **Add offline startup self-test** | Detect missing Tesseract, Poppler, models, or DB and report locally without network. | `backend/local/bootstrap.py` | | ✅ Complete — `backend/local/bootstrap.py` + `/api/health/bootstrap` + `backend/tests/test_bootstrap.py` |
| 3.3 | **Implement local encryption layer** | User master password derives key for optional data-at-rest encryption. | `backend/local/sqlcipher_engine.py`, `backend/database.py`, `backend/local/settings.py` | ✅ Complete — SQLCipher via `sqlcipher3-wheels`; see `docs/ENCRYPTION.md` |
| 3.4 | **Make SQLite bulletproof** | WAL mode, automatic backups on every import, idempotent imports, integrity checks, crash recovery. | `backend/database.py`, `backend/local/backup.py` | | ✅ Complete — WAL, integrity check, auto-backup, recovery helper, `backend/tests/test_recovery.py` |
| 3.4a | **Define idempotent import contract** | Prevent duplicate transactions when the same statement is re-uploaded or a sync retry fires. Use deterministic `txn_uid` (institution + account + date + amount + normalized description) and upsert on conflict. | `backend/routers/upload.py`, `phase3_pipeline/identity.py`, `backend/models.py` | ✅ Complete — `generate_transaction_uid` + `_upsert_transactions` with unique index |
| 3.4b | **Add PII masking for audit logs and exports** | Mask full account numbers, card numbers, and sensitive raw descriptions in audit logs, signed exports, and any generated summary files. Keep full data in the DB; redact only in output/audit surfaces. | `backend/routers/audit.py`, `backend/routers/export.py`, `backend/local/guards.py` | ✅ Complete — `backend/utils/redaction.py`, `_mask_text_fields`, audit/export routers updated |
| 3.4c | **Bind local server to `127.0.0.1` by default** | README and packaging currently show `--host 0.0.0.0`, which exposes the API to the LAN. Default to loopback and make LAN bind opt-in via env flag. | `README.md`, `BUILDER_MANUAL.md`, `start.sh`, `backend/api.py` (startup note) |
| 3.4d | **Add ML model artifact integrity checks** | `joblib.load()` on user-provided or locally trained models can execute arbitrary code. Add SHA-256 manifest, optional signature verification, and a warning before loading imported models. Training must only regenerate from local user data. | `phase3_pipeline/ml_categorizer.py`, `backend/local/ml_train.py`, `backend/models.py` (model registry table) |
| 3.4e | **Harden PDF parser sandbox** | A malicious PDF could exploit `pdfplumber`/`PyMuPDF`/OCR. Add file size/page limits, run parser in a subprocess with no network, reject PDFs with embedded JS/scripts. | `backend/parsers/generic_pdf.py`, `backend/routers/upload.py`, `backend/local/guards.py` | ✅ Complete — `backend/parsers/pdf_guard.py`, parent/sandbox checks, parser page limits, extended tests |
| 3.4f | **Harden `.local_secret` storage** | Local JWT signing key is written to a flat file with no permission check. Set restrictive filesystem permissions (e.g., 600 on Unix) and store adjacent to DB inside local root, not project root. | `backend/routers/auth.py`, `backend/local/settings.py` |
| 3.4g | **Replace placeholder session token acceptance with real session validation** | `_get_current_user` now validates tokens against a server-side `Session` table; tokens are bound at boot/login/refresh and revoked on logout. | `backend/auth.py`, `backend/models.py`, `backend/routers/auth.py`, `alembic/versions/53e636150d46_add_server_side_sessions.py` | ✅ Complete |
| 3.4h | **Fix 3.4f Windows ACL fallback bug** | `win32security.GetUserName()` does not exist; use `win32api.GetUserName()` for owner-only DACL on the fallback secret file. | `backend/local/keyring_secret.py` | ✅ Complete |
| 3.5 | **Remove or gate all cloud/API code** | No Plaid, no SMTP, no telemetry, no update checks unless explicitly enabled. | Audit across `backend/`, `frontend/`, `scripts/` |
| 3.6 | **Local model training pipeline** | User can retrain the categorizer on their own data with no external ML APIs. | `backend/local/ml_train.py` or extend `phase3_pipeline/ml_categorizer.py` | ✅ Complete — integrity hashing, safe loading, model registry; see Section 36 of `CHANGES.md` |
| 3.7 | **Local user/auth system** | Master password + optional keyfile, local Argon2 hashes, local session tokens. No OAuth/network validation. | `backend/local/auth.py` | ✅ Complete — keyfile support wired in `backend/routers/auth.py`; see Section 35 of `CHANGES.md` |
| 3.8 | **Local backup/restore/export** | Encrypted snapshots the user controls. Restore from snapshot. | `backend/local/backup.py`, `backend/tests/test_backup_restore.py` | ✅ SQLCipher-aware encrypted backup/restore complete |
| 3.9 | **Graceful degradation specs** | Document what works offline, what is disabled, and messaging for disabled features. | `docs/OFFLINE_BEHAVIOR.md` |
| 3.10 | **Hardened test suite** | Property-based tests, corruption tests, recovery tests, offline-mode tests. | `backend/tests/test_offline.py`, `test_recovery.py`, `test_crypto.py` | ✅ Complete — added `test_crypto.py`, `test_pdf_fuzz.py`, `test_keyring_secret.py`, recovery stress tests, and local-first/security property tests; see Section 38 of `CHANGES.md` |
| 3.10a | **Weak-entropy audit** | Ensure no stdlib `random` is used for tokens, keys, salts, nonces, or session identifiers; security-critical modules use `secrets` via `backend.local.security_random`. | `backend/tests/test_entropy_audit.py`, `backend/local/security_random.py` | ✅ Complete — TASK-038-Entropy-Audit; all security modules use `secrets`, no `random` imports found |
| 3.12 | **YAML safe-load hardening** | Centralize on `backend.local.yaml_safe` safe loaders and reject `!!python/object` payloads; replace `yaml.safe_load` in pipeline config loaders. | `backend/local/yaml_safe.py`, `backend/tests/test_yaml_safety.py`, `phase3_pipeline/categorizer.py`, `phase3_pipeline/category_loader.py`, `phase3_pipeline/profile_manager.py` | ✅ Complete — TASK-039; `safe_load_yaml_file` used everywhere, pre-commit hook added |
## 4. Packaging & Deployment (Phase 3 Continuation)

| # | Task | Why It Matters | Proposed Approach |
|---|------|--------------|-------------------|
| 4.1 | **Self-contained installer/package** | One-click install on Windows, macOS, Linux. Bundles Python runtime, Tesseract, Poppler, frontend assets. | PyInstaller/PEX/cx_Freeze + vendored binaries |
| 4.2 | **Browser + local server default** | Use existing FastAPI/Vite setup; keep LAN multi-seat possible. | Same stack, auto-launch browser on start |
| 4.3 | **First-run setup wizard** | Create master password, optional encryption, self-test on initial launch. | Frontend onboarding flow calling `bootstrap.py` endpoints |

---

## 5. Blocking Dependencies / Open Questions

- **Josh approval required** before any implementation begins (per `AGENTS.md` destructive/config rules; Phase 3 includes local auth and encryption changes). **APPROVED by Josh via `btsinnovations` on 2026-06-22 for full TASK-037 implementation.**
- **Live PostgreSQL instance** — used to validate 1.2, 2.1, and 2.3 in TASK-036; no longer required for remaining work unless additional PG validation is requested.
- **Encryption library choice** for 3.3 — resolved: SQLCipher via `sqlcipher3-wheels` with Argon2id key derivation and public salt sidecar. Details in `docs/ENCRYPTION.md`. ✅ Complete.
- **Auth model choice** for 3.7: implementing master-password-only with optional keyfile support later.

---

## 6. Suggested Execution Order

1. ✅ Close Phase 1/2 gaps (completed in TASK-036).
2. ✅ 3.3 / 3.8 encryption + SQLCipher-aware backup/restore completed in TASK-038.
3. Continue: 3.4a / 3.4b / 3.4d / 3.4e / 3.4 remainder as needed.
5. Enable bulletproof SQLite (3.4 remainder) and local backup/restore (3.8).
6. Audit dependencies and gate cloud code (3.1, 3.5), then add offline self-test (3.2).
7. Implement local ML retrain pipeline (3.6).
8. Write graceful degradation docs (3.9) and hardened tests (3.10).
9. ✅ Simplify single-user default (3.11) — `TAXFLOW_SINGLE_USER=true` default, `X-Tenant-ID` optional on SQLite, multi-entity PostgreSQL header enforcement preserved, `backend/tests/test_single_user_mode.py` passing.
10. Build packaging (4.x).

---

*Updated 2026-06-22 — TASK-037 approved and in progress.*
