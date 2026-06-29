# TaxFlow Pro v3.11.6 — B8 Phase 2: Full Bank Parser Expansion

## Objective

Scrape DocuClipper's supported-banks list, classify institutions by statement layout family, and implement dedicated parsers for the remaining institutions beyond the 23 already covered by B8 Phase 1. This phase expands automated bank-statement import coverage from ~23 core US banks to 100+ institutions.

## Scope

1. Scrape and normalize the DocuClipper supported-banks list.
2. Define layout families and classify each institution.
3. Implement parser skeletons per family.
4. Add synthetic fixtures and expand `test_bank_parsers.py`.
5. Integrate new parsers into the institution detection registry and dispatch pipeline.

## Success Criteria

- `data/docuclipper-institutions.json` contains ≥100 institutions with family tags.
- Each layout family has a dedicated parser module in `backend/parsers/banks/families/`.
- Detection registry maps institution name variations to family parsers.
- `test_bank_parsers.py` contains ≥70 tests covering Phase 1 + Phase 2 institutions.
- Full backend regression still passes on SQLite and PostgreSQL.

## Layout Families

| Family | Format | Examples | Strategy |
|--------|--------|----------|----------|
| `csv_standard` | CSV export | Chase, BofA, Wells Fargo | Header-row detection, column mapping |
| `ofx_qfx` | OFX/QFX | Most major banks | `ofxparse` or custom OFX parser |
| `pdf_table_simple` | Single-page PDF table | Regional banks, credit unions | Camelot/tabula-style table extraction or regex |
| `pdf_table_multi` | Multi-page PDF table | Larger regional banks | Page-aware table stitching |
| `credit_card_pdf` | Credit-card statement PDF | Amex, Discover, Chase Sapphire | Specialized date/posting/amount handling |
| `brokerage_pdf` | Brokerage statement PDF | Schwab, Fidelity, Ameritrade | Holdings + cash + transaction tables |

## Institutions (Phase 1 Core — Already Implemented)

Ally, Bank of America, BECU, Capital One, Charles Schwab, Chase, Citibank, Citizens, Discover, Huntington, Marcus, Navy Federal, PenFed, PNC, SoFi, Synchrony, Truist, U.S. Bank, USAA, Wells Fargo, Ally Bank, Cash App, American Express.

## Institutions (Phase 2 Target — Sample from DocuClipper)

1st Century Bank, 1st National Bank, 42 North Private Bank, Abacus Federal Savings Bank, Abbeville Building & Loan, AbbyBank, Academy Bank, Access Bank, Achieva Credit Union, ACNB Bank, Adirondack Bank, ADP Trust Company, Alerus Financial, Alliant Bank, Alpine Bank, Amalgamated Bank, America First Credit Union, American Express National Bank, Ameriprise Bank, Ameris Bank, Amplify Credit Union, Arvest Bank, Associated Bank, Atlantic Capital Bank, Austin Bank, Axos Bank, Banc of California, BancFirst, BancorpSouth, Bangor Savings Bank, Bank of Hawaii, Banner Bank, BB&T, BBVA, BECU, Benchmark Bank, BMO Harris, Bremer Bank, Byline Bank, Cadence Bank, California Bank & Trust, Cambridge Savings Bank, Canadian Imperial Bank of Commerce, Capital Bank, Cathay Bank, Centennial Bank, Central Bank, CIBC, CIT Bank, City National Bank, Comerica, Commerce Bank, Community Bank, ConnectOne Bank, Consumers Credit Union, Cooperativa, Credit Human, Customers Bank, Delta Community Credit Union, Dollar Bank, Eastern Bank, Elements Financial, Emigrant Bank, Ent Credit Union, Equity Bank, EverBank, First American Bank, First Bank, First Citizens Bank, First Commonwealth Bank, First Community Bank, First Entertainment Credit Union, First Financial Bank, First Hawaiian Bank, First Horizon Bank, First Interstate Bank, First Merchants Bank, First Midwest Bank, First National Bank of Omaha, First National Bank of Pennsylvania, First Republic Bank, FirstBank, Five Star Bank, Flagstar Bank, Flushing Bank, FNBO, Fremont Bank, Fulton Bank, Gate City Bank, Glacier Bank, Goldman Sachs Bank, Great Western Bank, Greenwood Credit Union, Guaranty Bank & Trust, Gulf Coast Bank & Trust, Hanmi Bank, HarborOne Bank, Hawaii National Bank, Heartland Bank, Heritage Bank, Hilltop National Bank, HomeStreet Bank, Horizon Bank, HSBC, IberiaBank, Idaho Central Credit Union, Indepen