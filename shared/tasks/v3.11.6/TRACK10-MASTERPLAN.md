TaxFlow Pro v3.11.6 — Track 10 Masterplan (B8 Phase 2 Full Bank Parser Expansion)

**Branch:** `v3.11.6-dev-PHASE6-TRACK10-bank-parser-expansion`  
**Cut from:** `v3.11.6-dev` (HEAD `18807ed`)  
**Goal:** Expand bank-statement parser coverage from 23 Phase 1 institutions to 100+ using DocuClipper's supported-banks list.

---

## Why Track 10 Exists

B8 Phase 1 implemented the 23 most common US banks and credit unions. Track 10 covers the long tail: regional banks, credit unions, brokerage/credit-card statements, and international English-language institutions listed by DocuClipper.

---

## Modules & Acceptance Criteria

### B8.02 Phase 2 — Scrape Institution List

**Files:**
- `scripts/scrape_docuclipper.py`
- `data/docuclipper-institutions.json`
- `shared/tasks/v3.11.6/DOCS/B8-PHASE2-ROADMAP.md`

**Requirements:**
- Scrape `https://www.docuclipper.com/docs/supported-banks/`
- Normalize institution names (trim whitespace, remove duplicates, collapse case)
- Tag each with an initial layout family guess based on name/type and known keywords
- Persist to `data/docuclipper-institutions.json` as a stable registry

**Acceptance:**
- JSON file contains ≥100 institutions
- Each entry has `name`, `family`, `country`, `phase` fields
- Script is idempotent (can re-run without duplicating)

---

### B8.02 Phase 2 — Layout Family Parsers

**Files:**
- `backend/parsers/banks/families/csv_standard.py` (new)
- `backend/parsers/banks/families/ofx_qfx.py` (new)
- `backend/parsers/banks/families/pdf_table_simple.py` (new)
- `backend/parsers/banks/families/pdf_table_multi.py` (new)
- `backend/parsers/banks/families/credit_card_pdf.py` (new)
- `backend/parsers/banks/families/brokerage_pdf.py` (new)

**Requirements:**
- Each family parser accepts raw statement bytes/content and returns a list of standardized transactions
- Standard fields: `date`, `description`, `amount`, `type` (debit/credit), `balance` (optional), `account` (optional)
- CSV family uses header detection and column mapping
- OFX/QFX family uses existing OFX parsing or a lightweight implementation
- PDF families use regex/table extraction with graceful fallback to generic text parsing
- Brokerage/credit-card families handle specialized date/posting logic

**Acceptance:**
- Each family parser has unit tests in `backend/tests/test_bank_parsers.py`
- Synthetic fixtures exist for at least one representative institution per family
- All family parsers return consistent `TransactionCandidate` shape

---

### B8.02 Phase 2 — Institution Detection Registry

**Files:**
- `backend/parsers/banks/institution_registry.py` (update)
- `backend/parsers/banks/dispatch.py` (update)

**Requirements:**
- Merge Phase 1 detection strings with Phase 2 institution names
- Map name variations to family parsers
- Add confidence scoring (exact match > keyword match > fallback)
- Expose a `detect_institution(content_or_name)` function

**Acceptance:**
- Detection tests cover Phase 1 and Phase 2 institutions
- Unknown institution falls back to family-based detection from statement content

---

### B8.02 Phase 2 — Expanded Test Suite

**Files:**
- `backend/tests/test_bank_parsers.py` (expand)
- `backend/tests/fixtures/bank_statements/` (new synthetic fixtures)

**Requirements:**
- ≥70 total tests across Phase 1 + Phase 2
- Each new family has at least 3 tests
- Each Phase 1 parser still passes
- Synthetic fixtures are small, deterministic, and version-controlled

**Acceptance:**
- `python -m pytest backend/tests/test_bank_parsers.py` passes
- Full backend regression still passes

---

## Suggested Execution Order

1. Scrape and normalize institution list → `data/docuclipper-institutions.json`
2. Implement layout family parser skeletons
3. Add detection registry entries for Phase 2 institutions
4. Create synthetic fixtures and expand tests
5. Run full regression and fix any collateral issues

---

## Technical Notes

- Do not add heavy PDF/table dependencies unless already present. Check `pyproject.toml` first.
- Keep parser family logic reusable; avoid per-institution hardcoding unless a bank truly has a unique layout.
- Synthetic fixtures should be small enough to commit (~few KB each).
- Country of origin matters for normalizing date formats; include `country` in registry entries.
- Brokerage statements may contain holdings tables that are out of scope for v3.11.6; focus on cash/money-market transactions only.

---

## Definition of Done

- `data/docuclipper-institutions.json` committed with ≥100 institutions
- Family parser modules committed and tested
- Detection registry updated
- `test_bank_parsers.py` ≥70 tests, all green
- Full backend regression passes on SQLite
- Full backend regression passes on PostgreSQL (`TEST_DATABASE_URL`)
- Branch pushed to origin
- No merge to `v3.11.6-dev` without James approval

---

## Assignment

- **Primary builder:** Jane Clawd
- **Validator:** glm-5.2:cloud for final review
- **Orchestrator approval:** James before merge
