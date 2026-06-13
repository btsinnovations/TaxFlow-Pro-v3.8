#!/usr/bin/env python3
"""
Phase 3.5.3 CLI – Process PDF or CSV statements to QIF/CSV.
Usage: python -m phase3_pipeline.main input output [csv|qif] [--verbose] [--quiet]
"""

import sys
import csv
import argparse
import logging
from pathlib import Path
from decimal import Decimal
from typing import List
from .models import Transaction
from .identity import IdentityService
from .pipeline import run
from .export import export
from .qif_export import write_qif
from .pdf_parser import pdf_to_transactions
from .logger import Logger
from .normalization import normalize_amount
from .ledger_guard import validate_raw_transactions
from .reconciliation import reconcile_transactions, StatementReconciler
from .profile_manager import ProfileManager
from .ml_categorizer import MLCategorizer

logger = Logger("main")

def load_csv(path: Path, profile: str = "personal") -> List[Transaction]:
    transactions = []
    with open(path, "r", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for idx, row in enumerate(reader):
            date = row.get("date", "").strip()
            desc = row.get("description", "").strip()
            raw_amount = row.get("amount", "0")
            amount = normalize_amount(raw_amount)
            txn = Transaction(
                date=date,
                description=desc,
                raw_description=row.get("raw_description", desc),
                amount=amount,
                category=row.get("category"),
                payee=row.get("payee"),
                institution=row.get("institution"),
                txn_uid=IdentityService.generate(date, desc, amount, row.get("institution"), idx),
            )
            transactions.append(txn)
    logger.info(f"Loaded {len(transactions)} transactions from CSV")
    return transactions

def main():
    parser = argparse.ArgumentParser(description="Financial ETL Pipeline")
    parser.add_argument("input", help="Input PDF or CSV file")
    parser.add_argument("output", help="Output file (.qif or .csv)")
    parser.add_argument("format", nargs="?", default="csv", choices=["csv", "qif"], help="Output format")
    parser.add_argument("--verbose", action="store_true", help="Enable debug logging")
    parser.add_argument("--quiet", action="store_true", help="Disable info logging (errors only)")
    args = parser.parse_args()

    if args.verbose:
        logger.setLevel(logging.DEBUG)
    elif args.quiet:
        logger.setLevel(logging.ERROR)

    input_path = Path(args.input)
    output_path = Path(args.output)
    output_format = args.format

    prof_manager = ProfileManager()
    profile = prof_manager.resolve_profile(filename=input_path.name)
    logger.info(f"Using profile: {profile}")

    # Load transactions
    if input_path.suffix.lower() == ".pdf":
        logger.info("PDF detected, extracting...")
        transactions, raw_text = pdf_to_transactions(input_path, profile=profile)
    else:
        transactions = load_csv(input_path, profile=profile)
        raw_text = ""

    # Deduplicate
    seen_uids = set()
    unique_txns = []
    for txn in transactions:
        if txn.txn_uid not in seen_uids:
            seen_uids.add(txn.txn_uid)
            unique_txns.append(txn)
    if len(unique_txns) != len(transactions):
        logger.warning(f"Removed {len(transactions)-len(unique_txns)} duplicate transactions")
    transactions = unique_txns

    if not validate_raw_transactions(transactions):
        logger.error("Raw transaction validation failed")
        sys.exit(1)

    # Run graph pipeline
    graph = run(transactions)

    # ML categorizer – only if USE_ML and model exists
    USE_ML = False
    try:
        from .config import USE_ML as USE_ML_CONFIG
        USE_ML = USE_ML_CONFIG
    except ImportError:
        pass

    ml_cat = None
    if USE_ML:
        try:
            ml_cat = MLCategorizer()
            logger.info("ML categorizer initialized")
        except Exception as e:
            logger.warning(f"ML categorizer failed to load: {e}. Falling back to rules only.")
            ml_cat = None
    else:
        logger.info("ML categorizer disabled (USE_ML=False)")

    # Instantiate rule categorizer once (outside loop)
    rule_cat = None
    if ml_cat is None:
        from .categorizer import PriorityCategorizer
        yaml_path = Path(__file__).parent.parent / "categories.yaml"
        try:
            rule_cat = PriorityCategorizer(str(yaml_path))
            logger.info("Rule categorizer loaded (ML disabled)")
        except Exception as e:
            logger.error(f"Failed to load categories.yaml: {e}")
            sys.exit(1)

    live_txns = graph.live()
    for txn in live_txns:
        if ml_cat:
            cat, conf, method = ml_cat.predict(txn.description, getattr(txn, 'payee', ''))
        else:
            cat = rule_cat.categorize(txn.description, getattr(txn, 'payee', ''))
            method = "rule"
            conf = 1.0
        if cat and not txn.category:
            txn.category = cat
            logger.debug(f"Category: {cat} (method={method}, conf={conf:.2f})")
        if txn.tax_category == "uncategorized" and txn.category:
            txn.tax_category = txn.category

    # Apply payee normalization (profile manager)
    for txn in live_txns:
        txn.payee = prof_manager.normalize_payee(txn.description, profile)

    # Export
    if output_format == "qif":
        with open(output_path, "w", encoding="utf-8") as f:
            write_qif(graph, f)
    else:
        out_data = export(graph)
        if not out_data:
            logger.error("No live transactions to export")
            sys.exit(1)
        with open(output_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=out_data[0].keys())
            writer.writeheader()
            writer.writerows(out_data)

    # Reconciliation
    opening_balance, closing_balance = StatementReconciler.extract_balances_from_text(raw_text)
    report = reconcile_transactions(live_txns, opening_balance, closing_balance)
    logger.info(f"Reconciliation: {report.message} ({report.status})")
    print(report.to_dict())

    logger.info(f"Exported {len(live_txns)} transactions to {output_path}")

if __name__ == "__main__":
    main()
