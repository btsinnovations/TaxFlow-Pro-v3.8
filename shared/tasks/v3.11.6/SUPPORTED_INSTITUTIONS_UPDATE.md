# Draft: Supported Institutions Update for v3.11.6

TaxFlow Pro v3.11.6 supports bank and credit-card statement import from the institutions below.
Input formats: **PDF**, **CSV**, and **OFX/QFX**.

## Specific parsers (27)

| Institution | Type | Specific parser file | Notes |
|-------------|------|----------------------|-------|
| Alliant | Credit Union | `alliant.py` | Standard share-draft layout. |
| Ally Bank | Online Bank | `ally.py` | Simple Date/Description/Debit/Credit/Balance. |
| American Express | Credit Card | `amex.py` | Statement credit / charge layout. |
| Bank of America | Bank / Credit | `bankofamerica.py` | Multi-column statements; generic fallback common. |
| BECU | Credit Union | `becu.py` | Share-draft and credit-card statements. |
| Capital One | Bank / Credit | `capitalone.py` | Credit-card and 360 checking layouts. |
| Cash App | Digital Wallet | `cashapp.py` | Single-column amount with To/From semantics. |
| Chase | Bank / Credit | `chase.py` | Checking + credit card layouts differ by product. |
| Chime | Neobank / Credit | `chime.py` | Credit Builder differs from checking. |
| Citibank | Bank / Credit | `citibank.py` | Layout ambiguity between checking and credit card. |
| Citizens Bank | Bank | `citizens.py` | Standard checking layout. |
| Discover Bank | Bank / Credit | `discover.py` | Credit-card-first terminology. |
| Educational Federal Credit Union (EdFed) | Credit Union | `edfed.py` | Share-draft and credit-card statements. |
| Huntington | Bank | `huntington.py` | Regional bank standard layout. |
| Marcus by Goldman Sachs | Online Savings | `marcus.py` | Sparse high-yield savings statements. |
| Navy Federal | Credit Union | `navyfederal.py` | Transaction/balance row style. |
| OFX / QFX | Open Standard | `ofx.py` | Universal OFX/QFX parser. |
| PNC Bank | Bank | `pnc.py` | Virtual Wallet vs standard checking layout. |
| PenFed | Credit Union | `penfed.py` | Standard credit union layout. |
| Queensborough National Bank | Regional Bank | `queensborough.py` | Standard Date/Description/Amount. |
| Schwab | Brokerage / Bank | `schwab.py` | Brokerage + investor checking. |
| SoFi | Neobank | `sofi.py` | SoFi Money multi-column layout. |
| Synchrony | Bank / Credit | `synchrony.py` | Online savings + retail credit cards. |
| TD Bank | Bank / Credit | `tdbank.py` | Checking + credit layouts supported. |
| Truist | Bank | `truist.py` | Post-merger brand; legacy BB&T/SunTrust markers. |
| U.S. Bank | Bank | `usbank.py` | Quicken/QuickBooks-style columns. |
| USAA | Bank / Credit | `usaa.py` | Military-focused bank + credit card. |
| Wells Fargo | Bank / Credit | `wellsfargo.py` | Debit/credit column orientation varies. |

## Generic fallback

If an uploaded statement does not match any specific institution, the app falls back to `generic_pdf.py` plus OCR extraction (`ocr_parser.py`).

## Adding a new institution

1. Add detection markers and column keywords to `backend/parsers/institution.py`.
2. Add a synthetic fixture to `backend/tests/fixtures/` covering the new statement layout.
3. Run `python -m pytest backend/tests/test_institution_detection.py` to verify detection.
4. If transaction extraction needs custom logic, add a parser plugin under `backend/parsers/` and register it in the dispatch table.
