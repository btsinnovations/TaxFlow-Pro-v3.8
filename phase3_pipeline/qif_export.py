# phase3_pipeline/qif_export.py
from datetime import datetime
from decimal import Decimal
from typing import TextIO
from .graph import TransactionGraph

# HomeBank expects DD/MM/YYYY; adjust if needed.
QIF_DATE_FORMAT = "%d/%m/%Y"

def _format_qif_amount(amount: Decimal) -> str:
    """Format a Decimal amount for QIF, which expects a period as decimal separator."""
    return f"{amount:.2f}".replace(',', '.')

def write_qif(graph: TransactionGraph, output_file: TextIO) -> None:
    """
    Write all transactions from the graph to a QIF file.
    Handles split transactions: parent entry with total amount,
    and split lines (S, $, E) for each child.
    """
    output_file.write("!Type:Bank\n")

    for root_txn in graph.roots():
        children = graph.get_children(root_txn.txn_uid)

        # Convert date string (YYYY-MM-DD) to QIF format
        try:
            dt = datetime.strptime(root_txn.date, "%Y-%m-%d")
            date_str = dt.strftime(QIF_DATE_FORMAT)
        except (ValueError, TypeError, AttributeError):
            date_str = root_txn.date  # fallback

        output_file.write(f"D{date_str}\n")
        output_file.write(f"T{_format_qif_amount(root_txn.amount)}\n")
        output_file.write(f"P{root_txn.description}\n")
        output_file.write(f"M{root_txn.memo}\n")

        if children:
            # Parent has splits – write an empty L line, then each split
            output_file.write("L\n")
            for child in children:
                if child.is_tombstone:
                    continue
                # Determine category: use tax_category if meaningful, else fallback to category
                cat = None
                if child.tax_category and child.tax_category != "uncategorized":
                    cat = child.tax_category
                elif child.category:
                    cat = child.category
                if cat:
                    output_file.write(f"S{cat}\n")
                output_file.write(f"${_format_qif_amount(child.amount)}\n")
                if child.description:
                    output_file.write(f"E{child.description}\n")
        else:
            # Single (non‑split) transaction: write category directly
            cat = None
            if root_txn.tax_category and root_txn.tax_category != "uncategorized":
                cat = root_txn.tax_category
            elif root_txn.category:
                cat = root_txn.category
            output_file.write(f"L{cat or ''}\n")

        output_file.write("^\n")
