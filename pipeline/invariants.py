from decimal import Decimal

def validate(graph):
    seen = set()

    # Unique IDs
    for t in graph.all():
        if t.txn_uid in seen:
            raise ValueError(f"Duplicate txn_uid: {t.txn_uid}")
        seen.add(t.txn_uid)

    # Split group integrity
    for parent_uid, children_uids in graph.children.items():
        if len(children_uids) < 2:
            raise ValueError(f"Invalid split group: {parent_uid} has {len(children_uids)} children")

        children = [graph.nodes[uid] for uid in children_uids]
        original = children[0].original_amount
        if original is None:
            raise ValueError(f"Missing original_amount for group {parent_uid}")

        total = sum(c.amount for c in children)
        if total != original:
            raise ValueError(f"Split mismatch for {parent_uid}: total {total} != original {original}")

    # Orphan parents
    graph.validate_orphans()