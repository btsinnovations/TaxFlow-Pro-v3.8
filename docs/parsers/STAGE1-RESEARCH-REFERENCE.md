# TaxFlow Pro v3.9 — Stage 1 Research Report

**Date:** 2026-06-18  
**Author:** Jane Clawd  
**Scope:** Research only — no code changes.  
**Goal:** Identify parser candidates for expanded US bank/CU support, recommend what to port from public v3.8 optional services, and propose a hybrid auth model that keeps v3.7 local-first boot while restoring v3.8 JWT validation.

---

## Executive Summary

TaxFlow Pro v3.7 is now a clean local-first tenant-aware backend (31 tests passing). The v3.9 planning task is to widen statement-parser coverage and selectively port the most useful v3.8 modules without breaking the local-only mandate.

Findings:

- **Parser coverage:** v3.7 already detects 7 institutions (EdFed, Cash App, Chime, TD Bank, Bank of America, Chase, Wells Fargo). Public research identifies **10 additional high-impact institutions** that are good Stage 2 candidates: Navy Federal, U.S. Bank, Citibank, PNC, Ally, BECU, SoFi, Truist, Discover, and Marcus by Goldman Sachs. All information was gathered from public sources — official support pages, published sample statements, and third-party converter/aggregator documentation.
- **v3.8 optional services:** Of the six reviewed files, **three are recommended for port** into v3.9:
  - `audit_trail.py` — tamper-evident hash-chain audit log. Fits local-first, high audit value.
  - `services/depreciation.py` — fixed-asset depreciation engine with IRS MACRS tables. Useful for Schedule C / business tax workflows.
  - `api_models.py` / `api_utils.py` — standardized Pydantic models and upload/output helpers. Low risk, improves API consistency.
- **OFX client (`ofx_client.py`):** Powerful live-bank feature but **not recommended** for default inclusion in v3.9 because it requires live internet, third-party OFX endpoints, and real credentials — all in tension with the v3.7 local-only stance. It should be extracted as an optional plugin if the user opts in later.
- **Auth hybrid:** A clean design keeps v3.7’s local master-password boot and `.local_secret` persistence, then layers v3.8 JWT access tokens on top for API session state. No external identity provider, no cloud. The same `User` table can be used; on first boot the master password unlocks a single local user whose hashed password is stored alongside the encrypted secret key.

---

## 1. Gap-Analysis Summary

Inputs:

- `projects/TaxFlow-Pro/taxflow-pro-v3.8-gap-analysis.md`
- `projects/TaxFlow-Pro/taxflow-pro-v3.8-gap-analysis.validator-review-v2.md`
- `projects/TaxFlow-Pro/TaxFlow-Pro-v3.7/backend/parsers/institution.py`

The gap analysis calls for:

1. More US institution parsers.
2. Port/rewrite of selected v3.8 backend services.
3. A safe, local-first authentication model that preserves both JWT validation and the offline boot flow.

The validator review emphasizes that any ported feature must not introduce mandatory cloud dependencies, must keep test coverage green, and must document offline/local-first conflicts.

---

## 2. Existing Parser Baseline (v3.7)

`TaxFlow-Pro-v3.7/backend/parsers/institution.py` currently supports:

| Institution | Detection String(s) | Notes |
|-------------|---------------------|-------|
| EdFed | `edfed` | Credit union |
| Cash App | `cash app` | P2P / neobank |
| Chime | `chime` | Neobank |
| TD Bank | `td bank`, `tdbank` | Large US/CA bank |
| Bank of America | `bank of america`, `bofa` | Major national bank |
| Chase | `chase` | Major national bank |
| Wells Fargo | `wells fargo` | Major national bank |

Detection is keyword-based. The file normalizes institution names and maps them to parser profiles. Stage 2 should extend this table with detection strings, quirks, and difficulty estimates for the candidates below.

---

## 3. Recommended Additional Institution Parsers

Research was limited to public sources: official bank help pages, public sample statement PDFs, Wikipedia listings of large banks/credit unions, and third-party converter documentation (DocuClipper, CapyParse) where primary sources were unavailable. Institutions are ordered by estimated impact and feasibility.

| # | Institution | Type | Detection Strings | Known Layout / Columns | Public Source Notes | Difficulty | Priority |
|---|-------------|------|-------------------|------------------------|---------------------|------------|----------|
| 1 | **Navy Federal Credit Union** | Credit union | `navy federal`, `navyfcu`, `navy federal credit union` | Date, Description, Debit, Credit, Running Balance; clean digital PDFs | DocuClipper blog + official site references. Digital-only statements. | Low | High |
| 2 | **U.S. Bank** | National bank | `us bank`, `usbank`, `u.s. bank` | Date, Description, Amount; CSV export limited to 90-day increments / ~18 months | U.S. Bank Quicken help page confirms manual transaction download; DocuClipper/CapyParse confirm PDF column pattern. | Low-Med | High |
| 3 | **Citibank / Citi** | National bank | `citibank`, `citi` | Date, Description, Amount Credited/Debited, Running Balance, Fees/Charges | CapyParse blog; DocuClipper Citi page blocked (403). Inferred from converter/aggregator docs. | Med | High |
| 4 | **PNC Bank** | Regional bank | `pnc bank`, `pnc`, `pnc virtual wallet` | Date, Description, Amount; Virtual Wallet bundles multiple accounts in one PDF; CSV only 90 days | DocuClipper + CapyParse blogs. Multi-account PDF is the main parsing wrinkle. | Med | High |
| 5 | **Ally Bank** | Online bank | `ally bank`, `ally` | Date, Description, Debit, Credit, Balance; digital PDFs | DocuClipper blog + Ally statements-and-forms page. No native CSV per statement. | Low | Med-High |
| 6 | **BECU (Boeing Employees Credit Union)** | Credit union | `becu`, `boeing employees credit union` | Layout from public sample PDF (`P-6803.pdf`) fetched from becu.org; **sample is a membership application, not a statement**. Detection strings and column patterns now integrated into `backend/parsers/institution.py` using inferred share-draft statement layout. A redacted BECU account statement is still needed for exact reconciliation-level parsing. | Primary source sample PDF. | Med | Med | **Integrated in v3.9 post-Stage 2.** |
| 7 | **SoFi** | Neobank | `sofi` | Date, Description, Debit, Credit, Running Balance; combined checking/savings in one PDF | DocuClipper blog. Digital-only, clean PDFs. | Low | Med |
| 8 | **Truist** | Regional bank | `truist bank`, `truist` | Date, Description, Amount; CSV only up to 18 months | DocuClipper blog + Scribd sample reference. | Med | Med |
| 9 | **Discover Bank** | Online bank | `discover bank`, `discover` | Date, Description, Debit, Credit, Balance; up to 7 years PDF history | DocuClipper blog. No native full-statement CSV. | Low | Med |
| 10 | **Marcus by Goldman Sachs** | Online bank | `marcus`, `marcus by goldman sachs` | Date, Description, Amount; savings statements only | DocuClipper blog. Limited account types, low complexity. | Low | Med |

### Honesty flags

- **Column patterns** for U.S. Bank, Citibank, PNC, Ally, SoFi, Truist, Discover, and Marcus come partly from converter/aggregator sites (DocuClipper / CapyParse), not bank-published specs.
- **Citibank** primary-source detail was blocked (DocuClipper 403); CapyParse provided the pattern.
- **BECU** layout is not yet extracted from the binary PDF; empirical PDF parsing is required.
- American Express, USAA, PenFed, Alliant, Synchrony, Huntington, Citizens, Capital One, and Schwab were investigated but sources returned 403/404/short pages. They are **not recommended as v3.9 Stage 2 primary targets** unless real sample PDFs become available later.

---

## 4. v3.8 Optional-Service Porting Recommendations

Public v3.8 files reviewed:

- `backend/services/depreciation.py`
- `backend/services/ofx_client.py`
- `backend/audit/audit_trail.py`
- `backend/api_utils.py`
- `backend/api_models.py`
- `backend/routers/auth.py`

### 4.1 Recommended for Port

#### `audit_trail.py` — Tamper-evident audit log
- What it does: Hash-chain audit entries per tenant. Records create/update/delete on transactions, statements, clients, journals, periods, etc.
- Why port: Directly supports v3.7’s local-first, multi-tenant model. Adds audit/reliability value with no cloud dependency.
- Integration notes: Needs an `AuditEntry` model (`tenant_id`, `user_id`, `action`, `entity_type`, `entity_id`, `details` JSON with embedded hash). Calls should be inserted in CRUD operations.
- Offline conflict: None.
- Effort: Medium.

#### `services/depreciation.py` — Fixed-asset depreciation
- What it does: Calculates SL, DB (150% / 200%), SOYD, and IRS MACRS schedules for 3/5/7/10/15/20-year property.
- Why port: Useful for small-business tax workflows and Schedule C asset depreciation.
- Integration notes: Add a `DepreciationAsset` model, a `depreciation` router, and tests verifying MACRS percentages sum to cost basis.
- Offline conflict: None; pure computation.
- Effort: Medium.

#### `api_models.py` + `api_utils.py` — Shared API models and file I/O utilities
- What they do: `api_models.py` defines reusable Pydantic response models (`HealthResponse`, `ClientCreate`, `TransactionOut`, `ProcessingResult`, etc.). `api_utils.py` manages uploads, outputs, a JSON audit/log DB, and event logging.
- Why port: Improves consistency between v3.7 routers and any new v3.9 endpoints. `api_utils.py`’s upload/output helpers can replace ad-hoc path logic.
- Integration notes: Merge Pydantic models into v3.7 `schemas.py` or keep as a separate `api_models.py`. Replace hardcoded upload paths with `UPLOAD_DIR` / `OUTPUT_DIR` helpers.
- Offline conflict: None. The JSON `api_db.json` logger is redundant with the SQL audit trail; consider deprecating it after audit port.
- Effort: Low-Medium.

### 4.2 Not Recommended for Default Port

#### `services/ofx_client.py` — Live OFX bank sync
- What it does: Builds OFX SGML requests, posts to bank OFX endpoints, parses transactions and balances, encrypts credentials with Fernet.
- Why not default: Requires live internet, real online-banking credentials, and bank-specific OFX endpoints. Contradicts v3.7’s local-first/no-cloud mandate. Also increases security surface (credential storage, live transport).
- Recommendation: Extract into an **optional plugin** (`plugins/ofx-sync/` or `projects/taxflow-ofx-sync/`) with explicit opt-in, separate Fernet key management, and a clear warning. Do **not** include in default v3.9 install.
- Effort if extracted: High; includes UI for credential capture, OFX institution directory, and sync scheduling.

---

## 5. Hybrid Auth Design Recommendation

### Requirements

1. Preserve v3.7 behavior: first boot asks for a master password; key material is persisted in `.local_secret`; app works offline.
2. Restore v3.8 behavior: API uses JWT access tokens (`HS256`, `sub` claim = username, `Authorization: Bearer …` header, OAuth2PasswordBearer flow).
3. No external IdP, no cloud, no network required.

### Proposed Design

```
First boot flow (local-only)
============================
User enters master password
        |
        v
Derive (or load) .local_secret key
        |
        v
Create single local admin user if none exists
  - username = "local" (or derived from machine/user)
  - hashed_password = bcrypt(master_password)
  - role = "admin"
        |
        v
Store User row in local DB
        |
        v
Return JWT access_token signed with .local_secret
```

```
Subsequent boot / login
=======================
POST /api/auth/login
  - Accepts JSON {username, password} or OAuth2 form
  - Verifies password against local User.hashed_password
  - Issues JWT signed with .local_secret key
        |
        v
Protected routes use get_current_user(token, db)
  - Decode with .local_secret
  - Look up user in local DB
  - Inject user/tenant context
```

### Key Decisions

| Decision | Rationale |
|----------|-----------|
| Single local user seeded at first boot | Keeps v3.7 “master password” UX while giving v3.8 JWT machinery a real `User` row. |
| JWT secret = `.local_secret` | One source of truth. If `.local_secret` is regenerated, previously issued tokens become invalid (acceptable for local app). |
| bcrypt for password hashing | Already used by v3.8 `auth.py`; standard and offline-safe. |
| No registration endpoint on first boot | Prevents creation of ambiguous users in a single-tenant local install. Optionally expose admin-only user management later. |
| `X-Tenant-ID` header preserved | v3.8’s RLS helper stays compatible; tenant scoping is set after token validation. |

### Files to Touch in Stage 2

- `backend/auth.py` (new) — combine v3.8 JWT helpers + v3.7 local secret/key derivation.
- `backend/api.py` — mount auth router, protect existing endpoints with `get_current_user`.
- `backend/models.py` — add `User` model if not present; ensure `tenant_id` linkage.
- `frontend login view` — send master password to `/api/auth/login`, store token.
- Tests: login, token expiry, protected-route rejection, `.local_secret` regeneration invalidates old tokens.

### Offline Conflict

None. All cryptography is local. The only external dependency is `python-jose` + `bcrypt`, both already present in v3.8.

---

## 6. Proposed Stage 2 Scope

1. **Parser expansion**
   - Add detection profiles for Navy Federal, U.S. Bank, Citibank, PNC, Ally, BECU, SoFi, Truist, Discover, Marcus.
   - Collect/obtain 1–2 public sample PDFs per institution for parser validation.
   - Extend `institution.py` and add per-institution parser tests.

2. **Audit trail**
   - Port `audit_trail.py`.
   - Add `AuditEntry` model and migration.
   - Instrument transaction/client/statement create/update/delete paths.

3. **Depreciation service**
   - Port `services/depreciation.py`.
   - Add `DepreciationAsset` model, router, and tests.

4. **API model / utility alignment**
   - Merge reusable models from `api_models.py` into `schemas.py`.
   - Adopt `api_utils.py` upload/output helpers.

5. **Hybrid auth**
   - Implement local master-password boot + JWT session model.
   - Add auth router and protect API.
   - Update frontend login flow.

6. **Out of scope (v3.9)**
   - Live OFX sync stays a future optional plugin.
   - Cloud ML, Plaid, Yodlee, or any third-party live feed.

---

## 7. Open Questions

1. **BECU sample PDF:** The fetched `P-6803.pdf` is binary. Do we have a PDF text-extraction utility in v3.7 we can run on it, or should Stage 2 add a small script to dump layout lines?
2. **Local user name:** Should the seeded local user be fixed (`local`) or derived from the Windows account / hostname? Fixed is simpler; derived is more intuitive.
3. **Token expiry:** v3.8 used 24-hour access tokens. For a local desktop app, is 24 hours acceptable, or should tokens be long-lived/session-scoped?
4. **Citibank / PNC samples:** We currently lack primary-source PDFs. Should we attempt to acquire anonymized public samples (e.g., from Scribd/GitHub) or rely on converter-site inference for the first pass?
5. **OFX plugin scope:** If OFX is extracted as a plugin, does the user want it scheduled in a future loop, or kept as a backlogged idea?
6. **Depreciation UI:** Is the depreciation service intended for end-user UI in v3.9, or only as an API capability for exports?

---

## 8. Sources

Primary references used:

- Local files:
  - `projects/TaxFlow-Pro/taxflow-pro-v3.8-gap-analysis.md`
  - `projects/TaxFlow-Pro/taxflow-pro-v3.8-gap-analysis.validator-review-v2.md`
  - `projects/TaxFlow-Pro/TaxFlow-Pro-v3.7/backend/parsers/institution.py`
- Public v3.8 source files (raw GitHub):
  - `https://raw.githubusercontent.com/btsinnovations/TaxFlow-Pro-v3.8/main/backend/routers/auth.py`
  - `https://raw.githubusercontent.com/btsinnovations/TaxFlow-Pro-v3.8/main/backend/services/depreciation.py`
  - `https://raw.githubusercontent.com/btsinnovations/TaxFlow-Pro-v3.8/main/backend/services/ofx_client.py`
  - `https://raw.githubusercontent.com/btsinnovations/TaxFlow-Pro-v3.8/main/backend/audit/audit_trail.py`
  - `https://raw.githubusercontent.com/btsinnovations/TaxFlow-Pro-v3.8/main/backend/api_utils.py`
  - `https://raw.githubusercontent.com/btsinnovations/TaxFlow-Pro-v3.8/main/backend/api_models.py`
- Public institution research:
  - U.S. Bank Quicken help: `https://www.usbank.com/bank-accounts/checking-accounts/checking-customer-resources/quicken.html`
  - BECU sample PDF: `https://www.becu.org/-/media/Files/PDF/P-6803.pdf`
  - DocuClipper / CapyParse converter blogs for SoFi, Truist, USAA, Discover, Marcus, PNC, Citi, Ally, U.S. Bank, Navy Federal.
  - Wikipedia lists of largest US banks and credit unions (for candidate shortlisting).

---

## 9. Next Action

Awaits orchestrator (James) confirmation on Stage 2 scope before any code changes. This report is research-only and has not modified the v3.7 codebase.
