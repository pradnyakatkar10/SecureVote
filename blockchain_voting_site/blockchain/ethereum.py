"""Ethereum/Ganache integration for the voting application."""

import json
import os

from dotenv import load_dotenv
from web3 import Web3


# Project root
APP_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Load .env BEFORE reading environment variables
load_dotenv(os.path.join(APP_DIR, ".env"))

ABI_PATH = os.path.join(APP_DIR, "contracts", "VotingSystem_abi.json")


class EthereumVoting:

    def __init__(self):

        # Ganache connection
        self.rpc_url = os.getenv(
            "GANACHE_RPC_URL",
            "http://127.0.0.1:7545"
        )

        # Deployed Solidity contract
        self.contract_address = os.getenv(
            "CONTRACT_ADDRESS",
            ""
        )

        # Ganache account private key
        self.private_key = os.getenv(
            "GANACHE_PRIVATE_KEY",
            ""
        )

        # Connect Web3 to Ganache
        self.w3 = Web3(
            Web3.HTTPProvider(self.rpc_url)
        )

        self.contract = None
        self.account = None

        # Load contract ABI
        if os.path.exists(ABI_PATH) and self.contract_address:

            with open(ABI_PATH, "r", encoding="utf-8") as f:
                abi = json.load(f)

            self.contract = self.w3.eth.contract(
                address=Web3.to_checksum_address(
                    self.contract_address
                ),
                abi=abi
            )

        # Load Ganache account
        if self.private_key:

            self.account = self.w3.eth.account.from_key(
                self.private_key
            )

    def ready(self):
        return bool(
            self.contract
            and self.account
            and self.w3.is_connected()
        )

    def _send(self, fn):

        if not self.ready():
            raise RuntimeError(
                "Ethereum is not configured. "
                "Check GANACHE_RPC_URL, "
                "GANACHE_PRIVATE_KEY and CONTRACT_ADDRESS."
            )

        nonce = self.w3.eth.get_transaction_count(
            self.account.address
        )

        tx = fn.build_transaction({
            "from": self.account.address,
            "nonce": nonce,
            "gas": 500000,
            "gasPrice": self.w3.eth.gas_price,
            "chainId": self.w3.eth.chain_id,
        })

        signed = self.w3.eth.account.sign_transaction(
            tx,
            self.private_key
        )

        tx_hash = self.w3.eth.send_raw_transaction(
            signed.raw_transaction
        )

        receipt = self.w3.eth.wait_for_transaction_receipt(
            tx_hash
        )

        return tx_hash.hex(), receipt

    def create_election(self, name):
        return self._send(
            self.contract.functions.createElection(name)
        )[0]

    def add_candidate(self, name, party):
        return self._send(
            self.contract.functions.addCandidate(
                name,
                party
            )
        )[0]

    def start_election(self):
        return self._send(
            self.contract.functions.startElection()
        )[0]

    def end_election(self):
        return self._send(
            self.contract.functions.endElection()
        )[0]

    def vote(self, voter_hash_hex, candidate_id):

        voter_hash = bytes.fromhex(voter_hash_hex)

        return self._send(
            self.contract.functions.vote(
                voter_hash,
                int(candidate_id)
            )
        )[0]

    def has_voted(self, voter_hash_hex):

        voter_hash = bytes.fromhex(voter_hash_hex)

        return self.contract.functions.hasVoted(
            voter_hash
        ).call()

    def results(self):

        names, counts = self.contract.functions.getResults().call()

        return list(
            zip(
                names,
                [int(x) for x in counts]
            )
        )

    def status(self):

        if not self.contract:
            return "Not configured"

        return int(
            self.contract.functions.state().call()
        )


ethereum = EthereumVoting()