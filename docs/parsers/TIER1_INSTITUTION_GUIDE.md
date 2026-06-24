# Tier 1 Institution Parser Guide

Source: embedded from `STAGE1-RESEARCH.md` (v3.9 Stage 1 research).

## Institutions Added in v3.9

| Institution | Detection Strings | Expected Columns | Source / Confidence | Known Quirk / Open Question |
|-------------|-------------------|------------------|---------------------|-----------------------------|
| Navy Federal | `navy federal`, `navyfcu` | transaction, withdrawal, deposit, balance | Aggregator-inferred from DocuClipper/CapyParse blogs | Credit-union statements often list running balance per row |
| U.S. Bank | `u.s. bank`, `us bank`, `usbank` | description, debit, credit, balance | https://www.usbank.com/bank-accounts/checking-accounts/checking-customer-resources/quicken.html | Quicken docs imply Date/Description/Debit/Credit/Balance |
| Citibank | `citibank`, `citi` | description, debit, credit, balance | Converter-site inference only — no public sample PDF acquired | **OPEN**: checking vs credit card layout ambiguity; v3.9 assumes multi-column pending primary-source fixture |
| PNC Bank | `pnc bank`, `pncbank` | description, debit, credit, balance | Converter-site inference only — no public sample PDF acquired | **OPEN**: Virtual Wallet vs standard checking layouts differ; detection only in v3.9 |
| Ally Bank | `ally bank`, `ally` | description, debit, credit, balance | Aggregator-inferred from online-bank guides | Online-only bank; simple multi-column statements |
| SoFi | `sofi` | description, debit, credit, balance | Aggregator-inferred from DocuClipper/CapyParse blogs | Neobank; SoFi Money statements often single-account, multi-column |
| Truist | `truist` | description, debit, credit, balance | Aggregator-inferred from converter blogs | Post-merger brand; legacy BB&T/SunTrust markers possible |
| Discover Bank | `discover bank`, `discover` | description, purchase, payment, balance | Aggregator-inferred | Credit-card-first brand; uses purchase/payment terminology |
| Marcus by Goldman Sachs | `marcus by goldman sachs`, `marcus` | description, debit, credit, balance | Aggregator-inferred from HYS statement guides | High-yield savings; statements are sparse |
| BECU | `becu`, `boeing employees credit union`, `member share savings`, `member advantage` | transaction date, description, withdrawal, deposit, balance | Primary source sample PDF `P-6803.pdf` (membership application, not statement) | Sample is membership app, not account statement; column layout inferred from typical credit-union share-draft statements. | **Integrated post-Stage 2.** |

## Dropped Institutions

- **BECU** — dropped from v3.9 scope for lack of a validated primary-source sample.

## Fixture Strategy

Synthetic PDFs are generated in `backend/tests/test_institution_detection.py`.
No real account statements are stored. Primary-source PDFs should be redacted
(account numbers, names, addresses removed) before inclusion in future parser
hardening passes.

## Future Work

- Acquire redacted primary-source PDFs for Citibank and PNC to move beyond
detection to full reconciliation-level parsing.
- Add account-type-specific parsers (checking vs credit card) where layouts
  diverge (TD Bank credit, Chime checking, Discover credit).
