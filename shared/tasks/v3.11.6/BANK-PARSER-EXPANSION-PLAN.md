# TaxFlow Pro v3.11.6 — Bank Parser Expansion Plan

**Owner:** Jane Clawd  
**Validator:** glm-5.1  
**Branch:** `v3.11.6-dev`  
**Feature branch:** `v3.11.6-dev-BANK-PARSER-EXPANSION`  

---

## Current State in v3.11.5

### Institution detection (18 institutions)
`backend/parsers/institution.py` detects:
1. TD Bank
2. Bank of America
3. Chase
4. Chime
5. EdFed
6. Queensborough National Bank
7. Wells Fargo
8. Cash App
9. Navy Federal
10. U.S. Bank
11. Citibank
12. PNC Bank
13. Ally Bank
14. SoFi
15. Truist
16. BECU
17. Discover Bank
18. Marcus by Goldman Sachs

### Concrete PDF parsers in backend
Only 4 institution-specific parsers exist:
- `tdbank.py` — TD Bank
- `chime.py` — Chime
- `edfed.py` — EdFed
- `queensborough.py` — Queensborough National Bank

### Legacy phase3 pipeline parsers
- Cash App, Chime, EdFed, TD Bank, plus a generic parser.

### Result
**14 institutions have detection but no dedicated parser.** They fall back to `GenericPDFParser` or OCR, which causes lower accuracy and more manual cleanup for users.

---

## v3.11.6 Goal

Add dedicated statement parsers for **all remaining detected institutions** so that every bank in the registry has a real parser path, not just generic fallback.

---

## Target Institutions for New Parsers

| # | Institution | Priority | Notes |
|---|-------------|----------|-------|
| 1 | **Bank of America** | High | Very common; checking + credit card layouts. |
| 2 | **Chase** | High | Very common; multiple layout variants. |
| 3 | **Wells Fargo** | High | Common; checking/savings/credit. |
| 4 | **Navy Federal** | High | Credit union; running balance column. |
| 5 | **U.S. Bank** | High | Multi-column statements. |
| 6 | **Cash App** | Medium | Already in phase3; port to backend. |
| 7 | **Citibank** | Medium | Checking vs credit ambiguity; needs primary source fixture. |
| 8 | **PNC Bank** | Medium | Virtual Wallet vs standard checking. |
| 9 | **Ally Bank** | Medium | Online-only bank; simpler layout. |
| 10 | **SoFi** | Medium | Neobank; SoFi Money layout. |
| 11 | **Truist** | Medium | Possible legacy BB&T/SunTrust markers. |
| 12 | **BECU** | Medium | Credit union share-draft layout. |
| 13 | **Discover Bank** | Medium | Credit-card-first terminology. |
| 14 | **Marcus by Goldman Sachs** | Low | Sparse high-yield savings statements. |

---

## Implementation Plan

### Step 1 — Port Cash App parser
- Port `phase3_pipeline/parsers/cashapp.py` to `backend/parsers/cashapp.py`.
- Add tests with synthetic Cash App statement fixtures.

### Step 2 — Build the "Big 5" bank parsers
Create dedicated parsers for the five most common institutions:
- `backend/parsers/bankofamerica.py`
- `backend/parsers/chase.py`
- `backend/parsers/wellsfargo.py`
- `backend/parsers/navyfederal.py`
- `backend/parsers/usbank.py`

Each parser must:
- Accept a validated PDF file path.
- Extract raw text safely (reuse `pdf_guard` / `validate_pdf_safety`).
- Identify checking vs credit card vs savings statement subtype.
- Return a list of transaction dicts with:
  - `date` (YYYY-MM-DD or ISO)
  - `description`
  - `amount` (signed decimal)
  - `tx_type` (`debit`/`credit`/`payment`)
  - `account_hint` (optional)
  - `running_balance` (optional)
- Handle missing/ambiguous columns gracefully.
- Raise a typed `ParserError` for unsupported layouts instead of returning garbage.

### Step 3 — Build remaining Tier 1 parsers
- `backend/parsers/citibank.py`
- `backend/parsers/pnc.py`
- `backend/parsers/ally.py`
- `backend/parsers/sofi.py`
- `backend/parsers/truist.py`
- `backend/parsers/becu.py`
- `backend/parsers/discover.py`
- `backend/parsers/marcus.py`

### Step 4 — Wire parsers into institution.py dispatch
- Update `_INSTITUTION_REGISTRY` or a new dispatch table so `parse_statement_pdf()` calls the correct dedicated parser.
- Fall back to `GenericPDFParser` only when the dedicated parser raises `ParserError` or returns empty.

### Step 5 — Add synthetic fixtures
Create one synthetic PDF-text fixture per parser in `backend/tests/fixtures/statements/`:
- `bankofamerica_checking.txt`
- `chase_checking.txt`
- `wellsfargo_checking.txt`
- `navyfederal_share_draft.txt`
- `usbank_checking.txt`
- etc.

Each fixture must be representative of the institution's typical statement layout.

### Step 6 — Test matrix
For each parser, tests must cover:
- Parse valid statement → returns expected transactions.
- Detect correct institution.
- Handle empty statement → no crash.
- Handle unsupported layout → typed error.
- Amount sign conventions (debit negative, credit positive, or explicit tx_type).
- Date format normalization.

---

## File Additions

| File | Purpose |
|------|---------|
| `backend/parsers/bankofamerica.py` | Bank of America parser |
| `backend/parsers/chase.py` | Chase parser |
| `backend/parsers/wellsfargo.py` | Wells Fargo parser |
| `backend/parsers/navyfederal.py` | Navy Federal parser |
| `backend/parsers/usbank.py` | U.S. Bank parser |
| `backend/parsers/cashapp.py` | Cash App parser (port from phase3) |
| `backend/parsers/citibank.py` | Citibank parser |
| `backend/parsers/pnc.py` | PNC parser |
| `backend/parsers/ally.py` | Ally Bank parser |
| `backend/parsers/sofi.py` | SoFi parser |
| `backend/parsers/truist.py` | Truist parser |
| `backend/parsers/becu.py` | BECU parser |
| `backend/parsers/discover.py` | Discover Bank parser |
| `backend/parsers/marcus.py` | Marcus parser |
| `backend/tests/test_bank_parsers.py` | Unified bank parser test suite |
| `backend/tests/fixtures/statements/*.txt` | Synthetic statement fixtures |

---

## Acceptance Criteria

- [ ] All 14 new parsers exist and are importable.
- [ ] `parse_statement_pdf()` dispatches to the correct parser for all 18 detected institutions.
- [ ] At least one synthetic fixture test passes for each new parser.
- [ ] `backend/tests/test_bank_parsers.py` has ≥40 tests total.
- [ ] Full backend test suite still passes: 0 failures.
- [ ] Generic parser fallback still works for unknown institutions.
- [ ] No real customer statements or credentials used in tests or fixtures.

---

## Phase Placement

This workstream runs **in parallel with Phase 1** (test harness + B1 Foundation) because it is parser-only and does not depend on the new bookkeeping data model. However, it must follow the same branch protocol and merge only after James approval.

**Suggested owner:** Jane (builder) with a specialist subagent if needed.  
**Suggested validator:** glm-5.1 reviews parser accuracy and edge cases.

---

## Risk Notes

- Synthetic fixtures may not match every real-world layout variant. Document known limitations.
- PNC Virtual Wallet and Citibank checking vs credit have open layout questions; initial parsers may be conservative and raise `ParserError` for ambiguous layouts.
- No live credentials or real statements will be used.
