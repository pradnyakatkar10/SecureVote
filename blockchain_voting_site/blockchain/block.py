"""
blockchain/block.py
--------------------
A Block holds a single vote transaction:
    { tx_id, voter_hash, candidate_id, election_id }

Only a SHA-256 hash of the voter's identity is ever stored here -- never
their name, student ID, or email. That personal information lives only
in the SQL database (see database/db.py), which itself never records
*who a voter chose*. The blockchain and the database each hold half of
the picture; only together (and only for the voter themself, via their
own voter_hash) could the two be linked.
"""

import hashlib
import json
import time


class Block:
    def __init__(self, index, data, previous_hash, timestamp=None, nonce=0):
        self.index = index
        self.timestamp = timestamp if timestamp is not None else time.time()
        self.data = data  # dict: tx_id, voter_hash, candidate_id, election_id
        self.previous_hash = previous_hash
        self.nonce = nonce
        self.hash = self.compute_hash()

    def compute_hash(self):
        block_string = json.dumps(
            {
                "index": self.index,
                "timestamp": self.timestamp,
                "data": self.data,
                "previous_hash": self.previous_hash,
                "nonce": self.nonce,
            },
            sort_keys=True,
            default=str,
        )
        return hashlib.sha256(block_string.encode()).hexdigest()

    def to_dict(self):
        return {
            "index": self.index,
            "timestamp": self.timestamp,
            "data": self.data,
            "previous_hash": self.previous_hash,
            "nonce": self.nonce,
            "hash": self.hash,
        }

    @classmethod
    def from_dict(cls, d):
        obj = cls.__new__(cls)
        obj.index = d["index"]
        obj.timestamp = d["timestamp"]
        obj.data = d["data"]
        obj.previous_hash = d["previous_hash"]
        obj.nonce = d["nonce"]
        obj.hash = d["hash"]  # preserved as-is, even if stale/tampered
        return obj

    def __repr__(self):
        return f"Block#{self.index} | hash={self.hash[:12]}... | prev={self.previous_hash[:12]}..."
