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

Add dedicated statement parsers for **every single institution identified in the Stage 1 research** AND for every institution on DocuClipper's published supported-banks list. The research-derived 23 parsers are implemented first (Phase 1 Track 3). The full DocuClipper list is scraped and implemented at the **end of the v3.11.6 cycle** so core bookkeeping work is not interrupted.

**Initial parsers delivered in Phase 1:** 23 institutions (research-derived).  
**Final target:** 100+ institutions (exact count determined after scraping DocuClipper's list at end of cycle).

---

## Full Research-Derived Target List

| # | Institution | Tier | Priority | Notes |
|---|-------------|------|----------|-------|
| 1 | **Bank of America** | 1 | High | Very common; checking + credit card layouts. |
| 2 | **Chase** | 1 | High | Very common; multiple layout variants. |
| 3 | **Wells Fargo** | 1 | High | Common; checking/savings/credit. |
| 4 | **Navy Federal** | 1 | High | Credit union; running balance column. |
| 5 | **U.S. Bank** | 1 | High | Multi-column statements. |
| 6 | **Citibank** | 1 | Medium | Checking vs credit ambiguity; needs primary source fixture. |
| 7 | **PNC Bank** | 1 | Medium | Virtual Wallet vs standard checking. |
| 8 | **Ally Bank** | 1 | Medium | Online-only bank; simpler layout. |
| 9 | **BECU** | 1 | Medium | Credit union share-draft layout. |
| 10 | **SoFi** | 1 | Medium | Neobank; SoFi Money layout. |
| 11 | **Truist** | 1 | Medium | Possible legacy BB&T/SunTrust markers. |
| 12 | **Discover Bank** | 1 | Medium | Credit-card-first terminology. |
| 13 | **Marcus by Goldman Sachs** | 1 | Low | Sparse high-yield savings statements. |
| 14 | **Cash App** | Legacy | Medium | Port from phase3 pipeline. |
| 15 | **American Express** | 2 | Medium | Investigated; 403/blocked sources; needs primary-source fixture. |
| 16 | **USAA** | 2 | Medium | Investigated; sources limited; military-focused bank. |
| 17 | **PenFed** | 2 | Medium | Pentagon Federal Credit Union; credit union layout. |
| 18 | **Alliant Credit Union** | 2 | Medium | Online credit union. |
| 19 | **Synchrony Bank** | 2 | Medium | Online savings / co-branded credit cards. |
| 20 | **Huntington Bank** | 2 | Medium | Regional Midwest bank. |
| 21 | **Citizens Bank** | 2 | Medium | Regional Northeast bank. |
| 22 | **Capital One** | 2 | Medium | 360 checking/savings + credit cards. |
| 23 | **Charles Schwab Bank** | 2 | Medium | Brokerage-linked checking. |

### Tier definitions
- **Tier 1:** Explicitly recommended in Stage 1 research as primary v3.9+ targets.
- **Tier 2:** Investigated during Stage 1 but deferred due to 403/404/lack of public samples. Added to v3.11.6 to ensure no parser is missed from research.
- **Legacy:** Existing phase3 parser that needs backend port.

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

### Step 4 — Build Tier 2 parsers
- `backend/parsers/amex.py`
- `backend/parsers/usaa.py`
- `backend/parsers/penfed.py`
- `backend/parsers/alliant.py`
- `backend/parsers/synchrony.py`
- `backend/parsers/huntington.py`
- `backend/parsers/citizens.py`
- `backend/parsers/capitalone.py`
- `backend/parsers/schwab.py`

Tier 2 parsers may be more conservative: they must detect the institution and parse a known/simple layout, but may raise `ParserError` for ambiguous layouts where no public sample pattern exists.

### Step 5 — Update institution detection registry
- Add Tier 2 detection strings to `backend/parsers/institution.py`.
- Add account-type hints where known (checking, savings, credit card).

### Step 6 — Wire parsers into dispatch
- Update dispatch table so `parse_statement_pdf()` calls the correct dedicated parser.
- Fall back to `GenericPDFParser` only when the dedicated parser raises `ParserError` or returns empty.

### Step 7 — Add synthetic fixtures
Create one synthetic fixture per parser in `backend/tests/fixtures/statements/`:
- `bankofamerica_checking.txt`
- `chase_checking.txt`
- `wellsfargo_checking.txt`
- `navyfederal_share_draft.txt`
- `usbank_checking.txt`
- `citibank_checking.txt`
- `pnc_checking.txt`
- `ally_checking.txt`
- `sofi_checking.txt`
- `truist_checking.txt`
- `becu_share_draft.txt`
- `discover_checking.txt`
- `marcus_savings.txt`
- `cashapp.txt`
- `amex_credit.txt`
- `usaa_checking.txt`
- `penfed_share_draft.txt`
- `alliant_checking.txt`
- `synchrony_savings.txt`
- `huntington_checking.txt`
- `citizens_checking.txt`
- `capitalone_checking.txt`
- `schwab_checking.txt`

### Step 8 — Test matrix
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
| `backend/parsers/amex.py` | American Express parser |
| `backend/parsers/usaa.py` | USAA parser |
| `backend/parsers/penfed.py` | PenFed parser |
| `backend/parsers/alliant.py` | Alliant Credit Union parser |
| `backend/parsers/synchrony.py` | Synchrony Bank parser |
| `backend/parsers/huntington.py` | Huntington Bank parser |
| `backend/parsers/citizens.py` | Citizens Bank parser |
| `backend/parsers/capitalone.py` | Capital One parser |
| `backend/parsers/schwab.py` | Charles Schwab Bank parser |
| `backend/tests/test_bank_parsers.py` | Unified bank parser test suite |
| `backend/tests/fixtures/statements/*.txt` | Synthetic statement fixtures |

---

## Acceptance Criteria

- [ ] All 23 new parsers exist and are importable.
- [ ] Institution detection registry updated with Tier 2 detection strings.
- [ ] At least one synthetic fixture test passes for each parser.
- [ ] `parse_statement_pdf()` dispatches correctly for all detected institutions.
- [ ] Full backend suite still passes: 0 failures.
- [ ] Generic parser fallback still works for unknown institutions.
- [ ] No real customer statements or credentials used in tests or fixtures.
- [ ] `backend/tests/test_bank_parsers.py` has ≥70 tests total.

---

## Phase Placement

This workstream runs **in parallel with Phase 1** (test harness + B1 Foundation) because it is parser-only and does not depend on the new bookkeeping data model. However, it must follow the same branch protocol and merge only after James approval.

**Suggested owner:** Jane (builder) with a specialist subagent if needed.  
**Suggested validator:** glm-5.1 reviews parser accuracy and edge cases.

---

## Risk Notes

- Synthetic fixtures may not match every real-world layout variant. Document known limitations per parser.
- Tier 2 institutions (Amex, USAA, PenFed, Alliant, Synchrony, Huntington, Citizens, Capital One, Schwab) had limited public sources. Their parsers will start conservative and raise `ParserError` for ambiguous layouts.
- Citibank, PNC, and BECU already had open layout questions in Tier 1 research. Same conservative approach applies.
- No live credentials or real statements will be used.
- Total parser work is large; consider splitting into two validator passes (Tier 1 first, then Tier 2).
