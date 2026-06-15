TaxFlow Pro v3.7
================

TaxFlow Pro is a local-first application for uploading PDF bank statements,
extracting transactions, categorizing them, and exporting tax-ready reports.

QUICK START
-----------

1. Install Python dependencies:
   python -m pip install -r requirements.txt

2. Install frontend dependencies:
   npm install

3. Start the backend:
   python -m uvicorn backend.api:app --host 0.0.0.0 --port 8000

4. Start the frontend in a second terminal:
   npm run dev

5. Open your browser:
   http://localhost:5173

DOCUMENTATION
-------------

- BUILDER_MANUAL.md    Full architecture and build guide
- GETTING_STARTED.md   First-time setup walkthrough
- TROUBLESHOOTING.md   Common issues and fixes
- MIGRATIONS.md        Database migration guide
- CHANGES.md           Change log

PRIVACY
-------

TaxFlow Pro runs on your own machine. Your bank statements and transaction
data stay local unless you choose to connect to a remote backend.
