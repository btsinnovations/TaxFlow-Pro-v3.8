from .graph import TransactionGraph
from .split import should_split, apply_split
from .tax import apply_tax
from .memo import apply
from .invariants import validate

def run(transactions):
    graph = TransactionGraph()

    # Ingestion + split (graph mutation)
    for i, txn in enumerate(transactions):
        if should_split(txn):
            apply_split(graph, txn, i)
        else:
            graph.add(txn)

    # Transformation passes
    apply_tax(graph)
    apply(graph)

    # Final validation
    validate(graph)

    return graph