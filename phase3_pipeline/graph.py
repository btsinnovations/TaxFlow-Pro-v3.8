from typing import Dict, List
from .models import Transaction

class TransactionGraph:
    def __init__(self):
        self.nodes: Dict[str, Transaction] = {}
        self.children: Dict[str, List[str]] = {}
<<<<<<< HEAD

    def add(self, txn: Transaction):
        if txn.txn_uid in self.nodes:
            raise ValueError(f"Duplicate txn_uid: {txn.txn_uid}")
        self.nodes[txn.txn_uid] = txn
=======
        # Track every added transaction so that duplicate UIDs can be detected
        # later by invariants rather than silently discarded.
        self._all_nodes: List[Transaction] = []

    def add(self, txn: Transaction):
        # Keep first occurrence in nodes dict for lookup, but record every add
        # so invariants can validate duplicate txn_uid issues.
        if txn.txn_uid not in self.nodes:
            self.nodes[txn.txn_uid] = txn
        self._all_nodes.append(txn)
>>>>>>> 588d8c5a4de15c1eb158d8c0e2f7ffb66336b9fd
        if txn.parent_txn_uid:
            self.children.setdefault(txn.parent_txn_uid, []).append(txn.txn_uid)

    def get_children(self, uid: str) -> List[Transaction]:
        return [self.nodes[c] for c in self.children.get(uid, [])]

    def all(self) -> List[Transaction]:
<<<<<<< HEAD
        return list(self.nodes.values())

    def live(self) -> List[Transaction]:
        return [t for t in self.nodes.values() if not t.is_tombstone]

    def roots(self) -> List[Transaction]:
        """Return transactions with no parent (original source rows)."""
        return [t for t in self.nodes.values() if t.parent_txn_uid is None]
=======
        return list(self._all_nodes)

    def live(self) -> List[Transaction]:
        return [t for t in self._all_nodes if not t.is_tombstone]

    def roots(self) -> List[Transaction]:
        """Return transactions with no parent (original source rows)."""
        return [t for t in self._all_nodes if t.parent_txn_uid is None]
>>>>>>> 588d8c5a4de15c1eb158d8c0e2f7ffb66336b9fd

    def validate_orphans(self):
        for parent in self.children:
            if parent not in self.nodes:
                raise ValueError(f"Orphan parent: {parent}")
