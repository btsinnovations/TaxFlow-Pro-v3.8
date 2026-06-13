from typing import Dict, List
from .models import Transaction

class TransactionGraph:
    def __init__(self):
        self.nodes: Dict[str, Transaction] = {}
        self.children: Dict[str, List[str]] = {}

    def add(self, txn: Transaction):
        if txn.txn_uid in self.nodes:
            raise ValueError(f"Duplicate txn_uid: {txn.txn_uid}")
        self.nodes[txn.txn_uid] = txn
        if txn.parent_txn_uid:
            self.children.setdefault(txn.parent_txn_uid, []).append(txn.txn_uid)

    def get_children(self, uid: str) -> List[Transaction]:
        return [self.nodes[c] for c in self.children.get(uid, [])]

    def all(self) -> List[Transaction]:
        return list(self.nodes.values())

    def live(self) -> List[Transaction]:
        return [t for t in self.nodes.values() if not t.is_tombstone]

    def roots(self) -> List[Transaction]:
        """Return transactions with no parent (original source rows)."""
        return [t for t in self.nodes.values() if t.parent_txn_uid is None]

    def validate_orphans(self):
        for parent in self.children:
            if parent not in self.nodes:
                raise ValueError(f"Orphan parent: {parent}")
