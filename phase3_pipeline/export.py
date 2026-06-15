def export(graph):
    """Return list of dicts for all live (non‑tombstone) transactions."""
    return [t.to_dict() for t in graph.live()]