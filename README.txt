TaxFlow Pro v3.8
================

TaxFlow Pro is a local-first application for uploading PDF bank statements,
extracting transactions, categorizing them, and exporting tax-ready reports.

QUICK START
-----------

1. Run the bootstrap script from the project root:
   ./start.sh

   start.sh creates the Python virtual environment, installs dependencies,
   prepares the database, installs frontend packages, and starts both the
   backend and frontend dev servers.

2. Open your browser:
   http://localhost:3000

3. Drag a PDF bank statement into "Upload Statements" and click Process.

That's it. One terminal, one command, both servers.

To stop: Press Ctrl+C in the same terminal.

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
