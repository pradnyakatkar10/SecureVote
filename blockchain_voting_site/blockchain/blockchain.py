"""
blockchain/blockchain.py
-------------------------
The ledger of vote transactions. One block is mined per cast vote.
Persisted to a JSON file (data/blockchain_data.json) separately from the
relational database, because a ledger's job -- an append-only, hash-linked
sequence -- is a different shape of data than the relational tables in
database/db.py.
"""

import json
import os

from .block import Block

DIFFICULTY = 2  # number of leading zero hex digits required (kept low so voting feels instant)


class Blockchain:
    def __init__(self, path):
        self.path = path
        self.chain = []
        self._load()

    # ---------------- Persistence ----------------
    def _load(self):
        if os.path.exists(self.path):
            try:
                with open(self.path, "r") as f:
                    raw = json.load(f)
                if raw:
                    self.chain = [Block.from_dict(b) for b in raw]
                    return
            except Exception:
                pass
        genesis = self._mine(Block(0, {"note": "Genesis Block"}, "0" * 64))
        self.chain = [genesis]
        self._save()

    def _save(self):
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        with open(self.path, "w") as f:
            json.dump([b.to_dict() for b in self.chain], f, indent=2)

    # ---------------- Mining ----------------
    def _mine(self, block):
        target = "0" * DIFFICULTY
        while not block.hash.startswith(target):
            block.nonce += 1
            block.hash = block.compute_hash()
        return block

    @property
    def latest(self):
        return self.chain[-1]

    def add_vote(self, vote_data):
        block = Block(index=self.latest.index + 1, data=vote_data, previous_hash=self.latest.hash)
        mined = self._mine(block)
        self.chain.append(mined)
        self._save()
        return mined

    # ---------------- Queries ----------------
    def votes_for_voter(self, voter_hash, election_id):
        return [
            b for b in self.chain
            if b.data.get("voter_hash") == voter_hash and b.data.get("election_id") == election_id
        ]

    def tally(self, election_id):
        counts = {}
        for b in self.chain:
            if b.data.get("election_id") == election_id:
                cid = b.data.get("candidate_id")
                counts[cid] = counts.get(cid, 0) + 1
        return counts

    # ---------------- Integrity ----------------
    def is_valid(self):
        target = "0" * DIFFICULTY
        for i in range(1, len(self.chain)):
            cur, prev = self.chain[i], self.chain[i - 1]
            if cur.hash != cur.compute_hash():
                return False, f"Block {cur.index}'s data no longer matches its stored hash.", cur.index
            if cur.previous_hash != prev.hash:
                return False, f"Block {cur.index} is no longer correctly linked to Block {prev.index}.", cur.index
            if not cur.hash.startswith(target):
                return False, f"Block {cur.index} fails its proof-of-work check.", cur.index
        return True, f"Blockchain verified: all {len(self.chain)} blocks are correctly hashed and linked. No tampering detected.", None

    # ---------------- Demo-only tampering ----------------
    def tamper(self, block_index, new_candidate_id):
        """Deliberately edits a sealed vote WITHOUT re-mining, to demonstrate
        that is_valid() detects it. For classroom demonstration only."""
        if block_index <= 0 or block_index >= len(self.chain):
            raise ValueError("No such votable block.")
        self.chain[block_index].data["candidate_id"] = new_candidate_id
        self._save()
