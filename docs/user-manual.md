# TaxFlow Pro v3.11.6 — User Manual

**Local-first, offline-capable financial document processing for individuals and small businesses.**

Version: 3.11.6  
Last updated: 2026-07-01

---

## Table of Contents

1. [Introduction](#1-introduction)
2. [Installation & First Launch](#2-installation--first-launch)
3. [The Main Window](#3-the-main-window)
4. [Dashboard & Health Check](#4-dashboard--health-check)
5. [Clients](#5-clients)
6. [Uploading Statements](#6-uploading-statements)
7. [Reviewing Transactions](#7-reviewing-transactions)
8. [Accounts & Chart of Accounts](#8-accounts--chart-of-accounts)
9. [Categorization Rules](#9-categorization-rules)
10. [Tax Rules](#10-tax-rules)
11. [Reconciliation](#11-reconciliation)
12. [General Ledger](#12-general-ledger)
13. [Reports](#13-reports)
14. [Exporting Data](#14-exporting-data)
15. [Tax Filing Exports](#15-tax-filing-exports)
16. [Depreciation](#16-depreciation)
17. [Fixed Assets, Inventory & Liabilities](#17-fixed-assets-inventory--liabilities)
18. [Vendors & Invoicing](#18-vendors--invoicing)
19. [Mileage Log](#19-mileage-log)
20. [Recurring Transactions](#20-recurring-transactions)
21. [Checks & Registers](#21-checks--registers)
22. [Multi-Currency](#22-multi-currency)
23. [Investments](#23-investments)
24. [Machine Learning Categorization](#24-machine-learning-categorization)
25. [Audit Trail](#25-audit-trail)
26. [Backup & Restore](#26-backup--restore)
27. [System Health & Security](#27-system-health--security)
28. [Offline Mode](#28-offline-mode)
29. [Troubleshooting](#29-troubleshooting)
30. [Keyboard Shortcuts](#30-keyboard-shortcuts)
31. [Glossary](#31-glossary)

---

## 1. Introduction

TaxFlow Pro ingests bank statements and financial documents, extracts transactions, categorizes them, and produces tax-ready exports. Everything runs on your own computer. By default, no bank credentials, transaction data, documents, or trained models leave the device.

### What you can do

- Import PDF, CSV, OFX, and QFX statements.
- Automatically detect your bank or credit union from the statement layout.
- Categorize transactions with rules or a locally trained ML model.
- Maintain a chart of accounts, general ledger, and trial balance.
- Reconcile accounts against statement balances.
- Track assets, depreciation, inventory, liabilities, vendors, invoices, and mileage.
- Export to CSV, Excel, JSON, QIF, QBO, Xero, Parquet, and PDF summary.
- Generate tax-form exports such as Schedule C, Schedule E, 1065, 1120-S, 8825, and 4562.
- Keep an immutable, tamper-evident audit trail.

### Privacy promise

TaxFlow Pro is local-first. Your statements, transactions, credentials, model weights, and backups stay on your machine unless you explicitly enable an optional cloud feature.

---

## 2. Installation & First Launch

### 2.1 System requirements

- Windows 10/11, macOS 11+, or a modern Linux distribution (Ubuntu 22.04+ recommended).
- 4 GB RAM minimum (8 GB recommended for OCR and large statement batches).
- 500 MB free disk space for the application; additional space for your data.
- Optional but recommended: Tesseract OCR and Poppler for scanned PDFs.

### 2.2 Install the application

**Windows**

1. Download `TaxFlowPro-Setup.exe`.
2. Run the installer. Windows may show a SmartScreen warning because the executable is not signed. Click **More info** then **Run anyway**.
3. The installer creates a start-menu shortcut and places data in your local application data folder.

**macOS**

1. Download `TaxFlowPro.dmg`.
2. Open the DMG and drag `TaxFlowPro.app` to Applications.
3. On first launch, right-click the app and choose **Open** to bypass Gatekeeper.

**Linux**

1. Download the `.deb` package.
2. Install it from a terminal:

   ```bash
   sudo dpkg -i taxflow-pro_3.11.6_amd64.deb
   sudo apt --fix-broken install -y
   ```

3. Launch from any terminal with `taxflow-pro`.

### 2.3 First boot

When you open TaxFlow Pro for the first time:

1. The application runs a quick self-test to confirm the database, parser, and optional OCR tools are ready.
2. You are asked to create a **master password**. This password protects your local data and, if you enable it, unlocks the encrypted database.
3. Choose whether to enable **database encryption**. Encryption protects your data file if your computer is lost or stolen.
4. The main window opens on the dashboard.

> **Tip:** Write down your master password and store it somewhere safe. If you enable SQLCipher encryption and forget the password, the data file cannot be recovered.

### 2.4 Updates

TaxFlow Pro does not auto-update. When a new version is available, download and install it the same way. Your data is preserved between versions.

---

## 3. The Main Window

The application opens as a single-page web interface served locally by the embedded backend. The top navigation bar contains grouped menus:

- **Overview** — Dashboard, Health
- **Transactions** — Upload, Imports, Reconciliation, Check Register, Recurring, Flags
- **Accounting** — General Ledger, Chart of Accounts, Reports, Budget/Forecast, Periods, Year-End
- **Entities** — Clients, Vendors, Invoicing
- **Tax** — Tax Rules, Tax Exports, Sales Tax
- **Assets** — Depreciation, Investments, Inventory, Liabilities, Mileage
- **System** — Audit, Backup, Export, Rules, Multi-Currency, Register

Each menu opens a dropdown of links. Click any link to open that section.

The landing page also shows several information sections:

- Hero / introduction
- Upload statements
- Dashboard overview
- Client management
- Tax rules
- Audit trail
- Machine learning training
- Export formats
- Multi-account linking
- Test suite
- Processed files
- Footer with version

---

## 4. Dashboard & Health Check

### 4.1 Dashboard

The dashboard shows live cards for:

- Documents processed
- Active clients
- Current pipeline status
- Recent audit activity

Below the cards, a pipeline status table lists each stage:

- PDF ingestion
- OCR extraction
- Transaction parsing
- ML categorization
- Tax rule engine
- Export generation

Status colors indicate Active, Idle, Warning, or Error.

### 4.2 Health check

Open **Overview → Health** to run the built-in bootstrap test. It checks:

- Database connectivity
- Alembic migration status
- Parser sandbox readiness
- Optional Tesseract OCR availability
- Optional Poppler PDF tools availability
- Local secret and token store

Each check returns a status icon and a short message. If a check fails, the message tells you what to install or fix.

---

## 5. Clients

A client is a bookkeeping entity. You can manage one personal set of books or many small-business clients.

### 5.1 Add a client

1. Go to **Entities → Clients**.
2. Click **Add Client**.
3. Enter the client name, entity type, and contact information.
4. Entity types include Individual, Sole Proprietorship, LLC, S-Corp, C-Corp, Partnership, and Trust.
5. Save the client.

### 5.2 Edit or delete a client

- Click the pencil icon to edit.
- Click the trash icon to delete. Deletion is blocked if the client still has transactions or accounts.

### 5.3 Switch active client

Most screens show a client selector. Select a client before uploading statements or running reports so the data is recorded under the right entity.

---

## 6. Uploading Statements

TaxFlow Pro accepts **PDF**, **CSV**, **OFX**, and **QFX** statements from more than 100 institutions.

### 6.1 Supported institutions

Dedicated parsers are tuned for the most common banks and credit unions, including:

Alliant, Ally, American Express, Bank of America, BECU, Capital One, Cash App, Chase, Chime, Citibank, Citizens, Discover, EdFed, Huntington, Marcus by Goldman Sachs, Navy Federal, PenFed, PNC, Queensborough National Bank, Schwab, SoFi, Synchrony, TD Bank, Truist, U.S. Bank, USAA, Wells Fargo.

If your bank is not in the dedicated list, one of six generic layout-family parsers usually handles it.

### 6.2 Upload from the landing page

1. Scroll to **Upload Statements** or click **Transactions → Upload**.
2. Choose a client from the dropdown.
3. Pick an output format: QIF, CSV, or JSON.
4. Toggle options:
   - **Fast Mode** — skips OCR and extracts text directly. Use this for digital PDFs.
   - **Use OCR** — forces Tesseract OCR. Use this for scanned or image-based PDFs.
5. Drag and drop one or more files, or click to select them.
6. Processing starts automatically.

### 6.3 OFX and QFX uploads

Use the **OFX Upload** panel inside the Upload section. OFX/QFX files contain structured transaction data and usually parse perfectly without OCR.

### 6.4 After upload

A results card appears for each file showing:

- Institution detected
- Number of transactions extracted
- Reconciliation status (PASS, FAIL, or pending)
- Any warnings
- A download button for the processed output

If parsing fails, check the file type and try toggling OCR on or off.

---

## 7. Reviewing Transactions

### 7.1 Transaction list

Go to **Transactions** routes to view imported transactions. Each row shows:

- Date
- Description
- Amount
- Type (debit/credit)
- Category
- Associated account
- Workpaper reference
- Flag status

### 7.2 Categorize manually

Click a transaction to edit it. Choose a category, assign a GL account, add a memo, and set a workpaper reference.

### 7.3 Flags

Flag transactions that need review:

1. Select a transaction.
2. Add a flag with a reason such as "missing receipt" or "confirm amount."
3. Resolve the flag after the issue is cleared.

Flagged transactions are excluded from final tax summaries until resolved.

---

## 8. Accounts & Chart of Accounts

### 8.1 Chart of accounts (COA)

The chart of accounts is the master list of buckets where money is recorded. Go to **Accounting → COA**.

Each account has:

- Code
- Name
- Type (asset, liability, equity, income, expense)
- Sub-type
- Tax line mapping
- Description

You can add, edit, merge, hide, and import/export accounts.

### 8.2 Bank accounts

Go to **Entities → Accounts** to add the real-world bank, credit card, loan, and investment accounts you import statements from. Link each account to a client.

Fields include:

- Institution
- Account number (masked in exports)
- Account type
- Currency
- Opening balance
- Fragility score

### 8.3 Multi-account linking

The **Multi-Account** section lets you link several accounts for one client and see a fragility score that estimates how likely the connection is to break when a statement layout changes.

---

## 9. Categorization Rules

Rules automatically label incoming transactions based on words in their descriptions.

### 9.1 Create a rule

1. Go to **System → Rules**.
2. Click **Add Rule**.
3. Enter a name and a pattern, for example `STARBUCKS`.
4. Pick a category, such as "Meals & Entertainment."
5. Optionally map the rule to a GL account.
6. Set a priority. Higher numbers win when several rules match.
7. Enable or disable the rule.

### 9.2 How matching works

When a statement is imported, TaxFlow Pro checks every transaction description. If the description contains the rule pattern, the rule wins. When multiple rules match, the highest-priority rule is applied.

### 9.3 Best practices

- Use specific merchant names with high priority.
- Use broad terms such as "RESTAURANT" with low priority.
- After editing rules, re-upload a statement to recategorize its transactions.

---

## 10. Tax Rules

Tax rules map descriptions to tax forms and lines.

### 10.1 Search tax rules

Go to **Tax → Tax Rules**. Search by pattern, form, or line. Sort by priority or creation date.

### 10.2 Create a tax rule

1. Click **Add Rule**.
2. Enter the description pattern.
3. Select the tax form and line, for example Schedule C, Line 18 (Office expense).
4. Link the rule to a GL account.
5. Save.

During tax-export generation, TaxFlow Pro uses these rules to assign transactions to the correct tax form lines.

---

## 11. Reconciliation

Reconciliation compares your imported transactions against the ending balance on the bank statement.

### 11.1 Start reconciliation

1. Go to **Transactions → Reconciliation**.
2. Select an account and statement period.
3. Enter the statement ending balance and date.
4. Match cleared transactions.
5. Mark the reconciliation complete when the difference is zero.

### 11.2 Locking

After a period is reconciled, the transactions for that period are locked to prevent accidental edits. You can unlock with an explicit action, which is recorded in the audit trail.

---

## 12. General Ledger

The general ledger is the official bookkeeping record behind your reports.

### 12.1 View the GL

Go to **Accounting → GL**. Each entry shows:

- Date
- Description
- Debit account
- Credit account
- Amount
- Memo
- Workpaper reference

### 12.2 Add journal entries

1. Click **Add Entry**.
2. Select the debit and credit accounts.
3. Enter the amount and date.
4. Add a memo and workpaper reference.
5. Save.

Debits must equal credits for every entry.

### 12.3 Adjusting entries

Use adjusting entries for accruals, depreciation, and period corrections. These are separate from imported transactions and are included in financial reports.

---

## 13. Reports

TaxFlow Pro can generate several standard reports.

### 13.1 Available reports

- Profit & Loss
- Balance Sheet
- Trial Balance
- Cash Flow (cash or accrual basis)
- General Ledger Detail
- Reconciliation Report
- Audit Report

### 13.2 Run a report

1. Go to **Accounting → Reports**.
2. Choose the report type.
3. Select the client, date range, and basis.
4. Click **Generate**.
5. View on screen or export to CSV, Excel, or PDF.

---

## 14. Exporting Data

### 14.1 Export formats

TaxFlow Pro can export transactions, the general ledger, trial balance, profit and loss, and balance sheet to:

- CSV
- Excel
- JSON
- QIF
- QBO
- Xero-compatible format
- Parquet
- PDF summary

### 14.2 Export from the landing page

Scroll to **Export Formats**. The available formats light up once at least one statement has been processed.

### 14.3 Export from a report

Most report screens have an **Export** button that downloads the current view in your chosen format.

### 14.4 Signed exports

For audit and tax submission, you can generate a signed export. The file includes an HMAC signature so recipients can verify it has not been altered since it left TaxFlow Pro.

---

## 15. Tax Filing Exports

### 15.1 Available tax exports

TaxFlow Pro produces outputs aligned to common U.S. tax forms:

- Schedule C — Sole proprietor business income
- Schedule E — Rental real estate and pass-through income
- Form 1065 — Partnership return
- Form 1120-S — S corporation return
- Form 8825 — Rental real estate income for partnerships/S-corps
- Form 4562 — Depreciation and amortization

### 15.2 Generate a tax export

1. Go to **Tax → Tax Exports**.
2. Select the client and tax year.
3. Choose the forms you need.
4. Map any categories that are not already linked.
5. Download the generated workbook or CSV.

> These exports summarize your bookkeeping data. Always review them with a qualified tax preparer before filing.

---

## 16. Depreciation

### 16.1 Add an asset

1. Go to **Assets → Depreciation**.
2. Click **Add Asset**.
3. Enter the asset name, purchase date, cost, recovery period, and placed-in-service date.
4. Choose the method: MACRS, straight-line, or Section 179/bonus.

### 16.2 View schedules

TaxFlow Pro computes annual depreciation and shows a schedule with beginning basis, depreciation, and ending basis for each year.

### 16.3 Tax form link

Depreciation data feeds into Form 4562 exports automatically.

---

## 17. Fixed Assets, Inventory & Liabilities

### 17.1 Inventory

Go to **Assets → Inventory** to track items you buy and sell. Record quantities, unit costs, and descriptions. Inventory movements update cost-of-goods-sold calculations.

### 17.2 Liabilities

Go to **Assets → Liabilities** to track loans, credit cards, and other debts. Record balances, interest rates, payment schedules, and linked accounts.

### 17.3 Investments

Go to **Assets → Investments** to record brokerage cash transactions, buys, sells, dividends, and interest. Use the dedicated Schwab parser or the generic brokerage family parser for statement imports.

---

## 18. Vendors & Invoicing

### 18.1 Vendors

Go to **Entities → Vendors** to maintain a vendor list. Vendor names help with 1099 tracking and payee normalization.

### 18.2 Invoicing

Go to **Entities → Invoicing** to create simple customer invoices. Record line items, amounts, tax, payment status, and due dates.

---

## 19. Mileage Log

### 19.1 Record trips

1. Go to **Assets → Mileage**.
2. Click **Add Trip**.
3. Enter the date, start and end odometer readings, purpose, and client.
4. Mark whether the trip was business or personal.

### 19.2 Reports

Mileage reports show total business miles, estimated reimbursement, and trips by client or vehicle.

---

## 20. Recurring Transactions

### 20.1 Create a recurring rule

1. Go to **Transactions → Recurring**.
2. Click **Add Recurring**.
3. Enter the description, amount, frequency, start date, and category.
4. Link it to an account.

### 20.2 Generate occurrences

TaxFlow Pro can project upcoming occurrences and alert you when an expected transaction is missing.

---

## 21. Checks & Registers

### 21.1 Check register

Go to **Transactions → Check Register** to record paper checks, deposits, and withdrawals. Each entry includes check number, payee, amount, and cleared status.

### 21.2 Running balance

The register shows a running balance so you can compare it to your bank balance at any time.

---

## 22. Multi-Currency

### 22.1 Enable currencies

Go to **System → Multi-Currency**. Add the currencies you need. TaxFlow Pro stores the original amount and exchange rate.

### 22.2 FX gain/loss

For transfers between currency accounts, TaxFlow Pro can calculate realized and unrealized foreign-exchange gains and losses.

---

## 23. Investments

### 23.1 Brokerage imports

Use the Schwab parser or the generic brokerage PDF family parser for cash transaction statements. TaxFlow Pro records buys, sells, dividends, interest, and fees.

### 23.2 Investment reports

Reports show realized gains/losses, dividend income, and cost-basis summaries.

---

## 24. Machine Learning Categorization

### 24.1 What it does

The Machine Learning feature looks at transaction descriptions you have already categorized and tries to guess the right category for new transactions. It runs entirely on your computer.

### 24.2 When it is trustworthy

Machine learning needs examples. A brand-new model trained on only a handful of transactions is basically guessing. This is normal, not a bug.

Use this rule of thumb:

- **Under 50 labeled transactions:** Do not rely on ML. Use categorization rules and manual review.
- **50–100 labeled transactions:** ML may help, but review its suggestions closely.
- **100–500 labeled transactions:** ML is usually reliable for common, repeated merchants.
- **500+ labeled transactions:** ML can handle most routine categorization.

Accuracy also matters. Look at the **Overall Accuracy** shown in the ML Model Management panel:

- **Below 60%:** The model is not useful yet. Label more transactions and retrain.
- **60–80%:** Useful but error-prone. Use it as a helper, not the final word.
- **Above 80%:** Generally reliable for day-to-day categorization.
- **Above 90%:** Good enough to run with minimal review.

### 24.3 How to build a good model

1. Import and categorize real transactions by hand.
2. Make sure every category you care about has many examples.
3. Go to **System → ML Model Management**.
4. Click **Train Now**.
5. Review the accuracy and category breakdown.
6. If accuracy is low, label more transactions and train again.

> **Tip:** Rules should do the heavy lifting at first. ML improves over time as you label more data.

### 24.4 How it works technically

TaxFlow Pro trains a TF-IDF + LogisticRegression classifier on your own labeled transactions. No cloud AI service is used. The model is saved locally as `local_model.pkl` and protected by a SHA-256 hash manifest.

### 24.5 Enable or disable

Toggle ML categorization on or off at any time. When disabled, only rule-based categorization runs.

### 24.6 Model safety

Trained models are hashed and stored locally. Imported model files are verified before loading to prevent tampering.

---

## 25. Audit Trail

### 25.1 What is logged

Every significant action is recorded:

- File uploads and processing
- Rule changes
- User logins and logouts
- Exports
- Backup and restore operations
- Transaction edits
- GL edits

### 25.2 View the log

Go to **System → Audit**. Filter by severity, event type, or search terms. Export the log to a CSV file.

### 25.3 Tamper detection

The audit log is stored as a hash chain signed with a local Ed25519 key. Use the **Verify** action to confirm the chain is intact. If any row is altered, verification fails.

---

## 26. Backup & Restore

### 26.1 Create a backup

1. Go to **System → Backup**.
2. Click **Create Backup**.
3. Choose the destination folder.
4. If encryption is enabled, the backup is encrypted with the same key.

### 26.2 Restore a backup

1. Go to **System → Backup**.
2. Click **Restore Backup**.
3. Select the backup file and any required salt sidecar or keyfile.
4. Confirm. The current database is replaced by the backup.

> **Warning:** Restore replaces all current data. Make a fresh backup first if you are unsure.

---

## 27. System Health & Security

### 27.1 Password policy

The master password must:

- Be at least 12 characters long.
- Have enough entropy (roughly 50 bits or more).
- Not contain the word "password" or your username.
- Not be in the common-password list.

### 27.2 Token lifetimes

- Access tokens last 15 minutes.
- Refresh tokens last 30 days.
- Tokens are invalidated when you log out.

### 27.3 Security headers

The local API sends security headers on every response, including content-type options, frame protection, referrer policy, and permissions policy.

### 27.4 Request size limits

The default upload limit is 32 MB. The default general request body limit is 10 MB. Large requests receive a 413 error.

---

## 28. Offline Mode

TaxFlow Pro defaults to offline mode. Features that work without the internet include:

- PDF/CSV/OFX upload and parsing
- Rule and ML categorization
- Bank reconciliation
- General ledger and reports
- Depreciation, inventory, liabilities, investments
- Exports and backups
- Audit trail

Features that remain disabled unless you explicitly opt in:

- Plaid / live bank feeds
- Stripe billing
- SMTP email
- OAuth login
- Telemetry
- Cloud ML inference
- Auto-update checks

To enable an online feature, set the corresponding environment variable and restart the application.

---

## 29. Troubleshooting

### 29.1 Application will not start

- Confirm your `.env` file exists and contains a valid `DATABASE_URL`.
- Run `python -m alembic upgrade head` from the project directory.
- Check that the local data directory is writable.

### 29.2 PDF fails to parse

- Make sure the file is a real PDF.
- For scanned PDFs, install Tesseract and Poppler.
- Try toggling OCR on or off.
- Check the logs directory for parser error details.

### 29.3 401 Unauthorized on API routes

You need a valid access token. Log out and log back in. If you are using curl or another client, include `Authorization: Bearer <token>`.

### 29.4 SQLite locked errors

Do not open the same database file from two TaxFlow Pro processes. Restarting the backend usually clears a temporary lock.

### 29.5 PostgreSQL connection errors

Verify PostgreSQL is running and the `DATABASE_URL` is correct. Confirm `psycopg2-binary` is installed.

---

## 30. Keyboard Shortcuts

- **F1** — Open this user manual (when bundled)
- **Ctrl+K** — Focus the navigation search (if available)
- **Ctrl+Enter** — Submit a form or save an entry
- **Esc** — Close modals and drawers

---

## 31. Glossary

- **ARV** — After Repair Value (real-estate term, not used in TaxFlow Pro).
- **COA** — Chart of Accounts.
- **CSV** — Comma-Separated Values file.
- **GL** — General Ledger.
- **JWT** — JSON Web Token, used for local authentication.
- **MAO** — Maximum Allowable Offer (real-estate term, not used in TaxFlow Pro).
- **ML** — Machine Learning.
- **OCR** — Optical Character Recognition.
- **OFX/QFX** — Open Financial Exchange formats exported by many banks.
- **PDF** — Portable Document Format.
- **P&L** — Profit & Loss report.
- **QIF/QBO** — Quicken interchange formats.
- **RLS** — Row-Level Security.
- **SQLCipher** — Encrypted SQLite database engine.
- **Tenant** — A client or isolated data boundary.
- **WAL** — Write-Ahead Logging (SQLite performance mode).

---

*TaxFlow Pro v3.11.6 — Local-first bookkeeping for individuals and small businesses.*
