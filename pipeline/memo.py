from .models import Transaction

def build_memo(txn: Transaction) -> str:
    if txn.is_tombstone:
        # For QIF export, we don't want "TOMBSTONE" in the memo.
        # Use the original description instead.
        return txn.description

    parts = []

    # Tax tag
    if txn.tax_category and txn.tax_category != "uncategorized":
        parts.append(f"tax:{txn.tax_category}")

    # Schedule line
    if txn.tax_line:
        parts.append(txn.tax_line)

    # Deductible flag
    if txn.tax_deductible:
        parts.append("(deductible)")

    # Original raw description (if different from normalized description)
    if txn.raw_description and txn.raw_description != txn.description:
        parts.append(f"orig: {txn.raw_description}")

    # The normalized description as anchor (if not already represented)
    if txn.description and txn.description not in "".join(parts):
        parts.append(txn.description)

    return " | ".join(parts)

def apply(graph):
    for txn in graph.all():
        txn.memo = build_memo(txn)
