<<<<<<< HEAD
TaxFlow Pro v3.6 — One-Terminal Install
========================================

1. EXTRACT this folder.

2. OPEN ONE TERMINAL.

3. RUN:
   cd Financial\ ETL
   ./start.sh

4. WAIT for "BOTH SERVERS RUNNING" message.

5. OPEN BROWSER:
   http://localhost:3000

6. DRAG a PDF bank statement into "Upload Statements" and click Process.

That's it. One terminal, one command, both servers.

To stop: Press Ctrl+C in the same terminal.
=======
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
>>>>>>> 588d8c5a4de15c1eb158d8c0e2f7ffb66336b9fd
