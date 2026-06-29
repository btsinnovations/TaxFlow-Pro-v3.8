# Supported Institutions

TaxFlow Pro v3.11.6 supports statement import from **100+ financial institutions** across the United States, Canada, and the United Kingdom. Coverage is provided through two layers:

1. **27 dedicated institution parsers** — tuned for the most common banks and credit unions.
2. **6 layout-family parsers** — generic PDF/CSV/OFX extraction engines that cover an additional **~80 institutions** from the DocuClipper registry (`data/docuclipper-institutions.json`).

Input formats: **PDF**, **CSV**, **OFX/QFX**.

---

## Coverage Summary

| Layer | Count | Source |
|-------|-------|--------|
| Dedicated institution parsers | 27 | `backend/parsers/*.py` |
| Layout-family parsers | 6 | `backend/parsers/banks/families/` |
| Institutions in registry | 103 | `data/docuclipper-institutions.json` |
| Phase 1 (dedicated parser) institutions | 22 | Registry subset |
| Family-covered institutions | 81 | Registry subset |

---

## Dedicated Institution Parsers (27)

These parsers are optimized for the specific statement layouts of their institutions.

| Institution | Type(s) | Module | Notes |
|-------------|---------|--------|-------|
| Alliant | Credit Union | `alliant.py` | Standard share-draft layout. |
| Ally | Online Bank | `ally.py` | Simple Date/Description/Debit/Credit/Balance. |
| American Express | Credit Card | `amex.py` | Statement credit / charge layout. |
| Bank of America | Bank / Credit | `bankofamerica.py` | Multi-column statements; generic fallback common. |
| BECU | Credit Union | `becu.py` | Share-draft and credit-card statements. |
| Capital One | Bank / Credit | `capitalone.py` | Credit-card and 360 checking layouts. |
| Cash App | Digital Wallet | `cashapp.py` | Single-column amount with To/From semantics. |
| Chase | Bank / Credit | `chase.py` | Checking + Sapphire/Freedom/Ink/Slate cards. |
| Chime | Neobank / Credit | `chime.py` | Credit Builder differs from checking. |
| Citibank | Bank / Credit | `citibank.py` | Layout ambiguity between checking and credit card. |
| Citizens | Bank | `citizens.py` | Standard checking layout. |
| Discover | Bank / Credit | `discover.py` | Credit-card-first terminology. |
| EdFed | Credit Union | `edfed.py` | Educational Federal CU share-draft and credit cards. |
| Huntington | Bank | `huntington.py` | Regional bank standard layout. |
| Marcus by Goldman Sachs | Online Savings | `marcus.py` | Sparse high-yield savings statements. |
| Navy Federal | Credit Union | `navyfederal.py` | Transaction/balance row style. |
| PenFed | Credit Union | `penfed.py` | Standard credit union layout. |
| PNC | Bank | `pnc.py` | Virtual Wallet vs standard checking layout. |
| Queensborough National Bank | Regional Bank | `queensborough.py` | Standard Date/Description/Amount. |
| Schwab | Brokerage / Bank | `schwab.py` | Brokerage + investor checking cash transactions. |
| SoFi | Neobank | `sofi.py` | SoFi Money multi-column layout. |
| Synchrony | Bank / Credit | `synchrony.py` | Online savings + retail co-brand cards. |
| TD Bank | Bank / Credit | `tdbank.py` | Checking + credit layouts supported. |
| Truist | Bank | `truist.py` | Post-merger brand; legacy BB&T/SunTrust markers. |
| U.S. Bank | Bank | `usbank.py` | Quicken/QuickBooks-style columns. |
| USAA | Bank / Credit | `usaa.py` | Military-focused bank + credit card. |
| Wells Fargo | Bank / Credit | `wellsfargo.py` | Debit/credit column orientation varies. |

---

## Layout-Family Parsers (6)

When no dedicated parser matches, TaxFlow falls back to a layout-family parser. These cover the remaining institutions in the registry based on statement structure.

| Family | Module | Best For | Institutions Covered |
|--------|--------|----------|----------------------|
| `csv_standard` | `banks/families/csv_standard.py` | Generic CSV exports | 5 (Axos, BMO Harris, BECU, CIT Bank, EverBank, etc.) |
| `ofx_qfx` | `banks/families/ofx_qfx.py` | OFX/QFX exports | All OFX/QFX providers (Chase, Schwab, many others) |
| `pdf_table_simple` | `banks/families/pdf_table_simple.py` | Single-page PDF tables | 94 regional/community banks/CUs |
| `pdf_table_multi` | `banks/families/pdf_table_multi.py` | Multi-page PDF tables | HSBC, other multi-page statements |
| `credit_card_pdf` | `banks/families/credit_card_pdf.py` | Credit-card PDFs | Amex National, other card issuers |
| `brokerage_pdf` | `banks/families/brokerage_pdf.py` | Brokerage cash statements | Ameriprise, Goldman Sachs, Fidelity, TD Ameritrade, E*Trade |

The registry source is `data/docuclipper-institutions.json` (scraped from DocuClipper). Note: DocuClipper states it supports **any English-language PDF statement**; the registry is a "we have seen this one" list, not a hard whitelist.

---

## Adding a New Institution

1. If the institution is common enough, add a dedicated parser to `backend/parsers/` and register it in `backend/parsers/__init__.py`.
2. Otherwise, add the institution name + family to `data/docuclipper-institutions.json`.
3. Add a synthetic fixture to `backend/tests/fixtures/` covering the new statement layout.
4. Run `python -m pytest backend/tests/test_institution_detection.py` to verify detection.

---

## Generic Fallbacks

If neither a dedicated parser nor a layout-family parser matches:

- `generic_pdf.py` attempts regex-based extraction.
- `ocr_parser.py` runs OCR on image-based PDFs.
- `ofx.py` handles OFX/QFX standard exports.
