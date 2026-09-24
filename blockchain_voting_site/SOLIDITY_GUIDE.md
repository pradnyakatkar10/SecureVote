# VotingSystem.sol — Solidity Smart Contract

A real Ethereum smart-contract version of the same election rules used in
the Flask/Python part of this project. Where the Python `blockchain/block.py`
implementation hand-builds hashing and chain-linking to get tamper-evidence,
this version gets that property natively from Ethereum itself — every state
change here is a transaction on a real (or test) blockchain, secured by the
network's own consensus rather than code this project wrote.

## ⚠️ Important — please read before your viva

**This environment has no internet access, so I was not able to run an actual
Solidity compiler (`solc`) here.** I wrote the contract carefully against
standard, extremely well-established Solidity patterns (this general shape of
voting contract is one of the most common teaching examples for Solidity, so
the syntax and structure are patterns I'm confident about) and checked its
brackets/structure programmatically, but **you should compile it yourself in
Remix (2 minutes, no install) before presenting it** — see below. If there's a
typo I can't see without a compiler, Remix will tell you exactly which line.

## What it does

Mirrors the rules already enforced in `app.py` / `voting_system.py`:

| Rule | Where it's enforced here |
|---|---|
| Only the admin can add candidates / start / end the election | `onlyAdmin` modifier |
| Candidates can only be added before the election starts | `inState(ElectionState.Created)` |
| Need at least 2 candidates to start | `require(candidatesCount >= 2, ...)` in `startElection()` |
| A voter can cast exactly one vote | `require(!sender.hasVoted, ...)` in `vote()` |
| Results are tallied from the actual votes, not a separate counter | `getResults()` reads `candidates[i].voteCount` directly |

**Key difference from the Python version:** there, `blockchain/blockchain.py`
manually computes SHA-256 hashes and links blocks together to make tampering
detectable, because it's running as an ordinary Python program with no
blockchain underneath it. Here, there's nothing to hand-build — every
`vote()` call is itself a transaction permanently recorded on the chain, and
tampering with it after the fact isn't a matter of "editing a JSON file and
re-verifying a hash" (as the Python tamper-demo does) — it's not possible at
all without controlling the network's consensus.

## Compiling it yourself (2 minutes, no installation)

1. Go to **[remix.ethereum.org](https://remix.ethereum.org)** in any browser.
2. In the file explorer (left sidebar), create a new file named
   `VotingSystem.sol` and paste in the contract.
3. Click the **Solidity Compiler** tab (left icon that looks like an "S").
   Set the compiler version to **0.8.19** or higher, then click
   **Compile VotingSystem.sol**.
4. A green checkmark means it compiled successfully. Any error will point to
   the exact line — happy to help fix anything Remix flags.

## Deploying and testing it (still in Remix, still free)

1. Click the **Deploy & Run Transactions** tab.
2. Environment: choose **Remix VM (Cancun)** — this gives you a free, instant,
   fake blockchain in your browser with 10 pre-funded test accounts. No real
   ETH, no testnet faucet, no MetaMask needed for a quick demo.
3. Next to **Deploy**, type an election name (e.g. `"College Council 2026"`)
   in the constructor field, then click **Deploy**.
4. Your deployed contract appears at the bottom. Expand it to see every
   function as a clickable button.

### A demo sequence to try (mirrors the Flask app's demo flow)

1. `addCandidate("Alice Sharma", "Progress Party")`
2. `addCandidate("Bob Verma", "Unity Front")`
3. `startElection()`
4. Switch the **Account** dropdown (top of the Deploy panel) to a *different*
   account than the one you deployed with — this simulates a separate voter.
5. `registerVoter()`
6. `vote(1)` — votes for candidate 1 (Alice)
7. Try `vote(2)` again from the same account → it **reverts** with
   "This address has already voted" — shown in red in Remix's console.
8. Switch to a third account, `registerVoter()`, then `vote(2)`.
9. Switch back to your original (admin) account, call `endElection()`.
10. Call `getResults()` and `getWinner()` to see the tally.
11. Open the **console log** at the bottom of Remix and expand any past
    transaction — you'll see the `VoteCast`, `CandidateAdded`, etc. events,
    which is the on-chain, permanent record equivalent to the Python
    project's "Ledger" page.

### Optional: deploying to a real testnet

If your instructor wants to see it on an actual public test network (e.g.
Sepolia): install the MetaMask browser extension, get free Sepolia test ETH
from a faucet (search "Sepolia faucet"), switch Remix's environment to
**Injected Provider - MetaMask**, and deploy the same way. This costs no real
money but does require a few extra setup steps beyond Remix VM.

## How this fits into the project as a whole

The written report's **Future Scope** section already names "port the
vote-recording logic to a Solidity smart contract on a test Ethereum
network" as a natural next step — this file *is* that step, delivered as a
working companion piece rather than only a suggestion. It's reasonable to
present both: the Flask/Python system as the actual working, submittable
application (registration, sessions, admin dashboard, SQLite — things a
smart contract alone doesn't give you), and this contract as the piece that
demonstrates real Solidity/Ethereum knowledge directly, which is very
likely what your instructor is checking for by asking for Solidity code
specifically in a "Blockchain Technologies" course.
