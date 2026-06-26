# Supported Financial Institutions

TaxFlow Pro v3.11 supports bank and credit-card statement import from the institutions below.
Input formats: **PDF**, **CSV**, and **OFX/QFX**.

## Detection overview

The app uses `POST /api/imports/detect` to identify the institution from uploaded statement text. Detection relies on institution-specific strings and expected column keywords. After detection, the appropriate parser (specific or generic fallback) extracts transactions.

## Institution list

| Institution | Type | Specific parser | Notes |
|-------------|------|-----------------|-------|
| TD Bank | Bank / Credit | ✅ | Checking + credit layouts supported. |
| Bank of America | Bank / Credit | ✅ | Multi-column statements; generic fallback common. |
| Chase | Bank / Credit | ✅ | Checking + credit card layouts differ by product. |
| Chime | Neobank / Credit | ✅ | Credit Builder layout differs from checking. |
| EdFed (Educational Federal Credit Union) | Credit Union | ✅ | Share-draft and credit-card statements. |
| Queensborough National Bank | Regional Bank | ✅ | Standard Date/Description/Amount. |
| Wells Fargo | Bank / Credit | ✅ | Debit/credit column orientation varies. |
| Cash App | Digital Wallet | ✅ | Single-column amount with To/From semantics. |
| Navy Federal | Credit Union | ✅ | Transaction/balance row style. |
| U.S. Bank | Bank | ✅ | Quicken/QuickBooks-style columns. |
| Citibank | Bank / Credit | ⚠️ detection + generic fallback | Layout ambiguity between checking and credit card. |
| PNC Bank | Bank | ⚠️ detection + generic fallback | Virtual Wallet vs standard checking layout deferred. |
| Ally Bank | Online Bank | ✅ | Simple Date/Description/Debit/Credit/Balance. |
| SoFi | Neobank | ✅ | SoFi Money multi-column layout. |
| Truist | Bank | ✅ | Post-merger brand; may carry legacy BB&T/SunTrust markers. |
| BECU | Credit Union | ⚠️ detection + generic fallback | Sample PDF is a membership application; exact statement parser pending. |
| Discover Bank | Bank / Credit | ✅ | Credit-card-first terminology (purchase/payment). |
| Marcus by Goldman Sachs | Online Savings | ✅ | Sparse high-yield savings statements. |

## Adding a new institution

1. Add detection markers and column keywords to `backend/parsers/institution.py`.
2. Add a synthetic fixture to `backend/tests/fixtures/` covering the new statement layout.
3. Run `python -m pytest backend/tests/test_institution_detection.py` to verify detection.
4. If transaction extraction needs custom logic, add a parser plugin under `backend/parsers/institutions/` and register it in the dispatch table.
