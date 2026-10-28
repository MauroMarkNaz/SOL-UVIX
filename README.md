# UVIX-SOL

[![Protocol](https://img.shields.io/badge/Protocol-UVIX--RI--1.0-blueviolet)](#5-the-envelope-uvix-ri-10)
[![Solana Program](https://img.shields.io/badge/Solana-Anchor-14F195?logo=solana)](#10-the-on-chain-program)
[![PQC Security](https://img.shields.io/badge/Security-Post--Quantum%20(ML--KEM%2FDSA)-black)](#9-post-quantum-core)
[![License: Proprietary](https://img.shields.io/badge/License-Proprietary-red.svg)](LICENSE)

**UVIX-SOL** is a modular protocol suite for verifiable state across untrusted
machines: a Solana on-chain program holding three registries, an append-only
proof-of-history chain that remembers what the mesh agreed on, a deterministic
wire envelope that lets three languages check each other's work, lattice-based
post-quantum cryptography, and a neural routing layer that decides where work
goes without being told twice.

What it runs on, where it runs, and who runs it are not documented here.
That is deliberate. This document describes the machine, not its keeper.

---

## 1. A note on names

Three related things share one root, and this document keeps them distinct:

- **UVIX** — the project's internal interoperability namespace and canonical
  slug format, short for **Universal-Inter_compatability**. The spelling is
  canonical: it is part of the identity, not a typo to be corrected. UVIX
  is **not an external standard** — not IETF, not ISO, not Solana. It began
  as the common identifier and build/runtime convention of the project's
  Node tooling, and later became the namespace under which the UVIX-RI
  protocol family is defined.
- **`uvix`** — the internal build entry point used by the Node workflow.
  The convention came first; the protocol grew out of it.
- **UVIX-RI-1.0** — the first versioned wire/envelope protocol defined
  under the UVIX namespace (see §5). It claims no standards body's
  authority and needs none: its authority is that independent
  implementations can check each other, byte for byte.
- **UVIX-SOL** — the larger system that applies UVIX-RI-1.0 to Solana,
  persistence, cryptography, routing, and decoding. UVIX is the namespace;
  UVIX-SOL is one system built under it.

---

## 2. Design principles

- **Determinism over trust.** Every cross-node claim is packaged so any other
  node — in any runtime — can recompute it byte-for-byte and say yes or no.
  Nothing is believed because of who sent it.
- **Append-only memory.** History is a hash chain. Entries are never edited,
  only superseded by later entries that say so. A disagreement about the past
  is settled by recomputation, not by authority.
- **Commit before outcome.** Predictions are sealed on-chain before their
  horizons expire and scored after the fact, in the open, by formula. The
  ledger does not let anyone remember being right.
- **Opacity is a feature.** The repository ships templates, schemas, and
  proofs. It does not ship topology, membership, endpoints, or operator
  detail. A reader can verify everything about how the system works and
  learn nothing about where it sleeps.

---

## 3. What the suite does

| Layer | Responsibility |
| :--- | :--- |
| **On-chain program** | Three registries: prediction commitments, proof-of-history turn proofs, token forensic signals |
| **PoH persistence** | Hash-chained, append-only log of mesh state with witness failover and periodic on-chain root anchoring |
| **Envelope protocol** | Canonical-JSON slugs with deterministic SHA-256 integrity hashes, identical across Python, TypeScript, and Rust |
| **Neural mesh** | Dynamic routing over a weighted loss matrix — latency, load, affinity, error history |
| **Funding layer** | USDC micropayments that pay for inference across the fleet — devnet-first, metered per call |
| **PQC core** | ML-KEM key encapsulation, ML-DSA signatures, hybrid classical fallback |
| **Decoders** | Versioned transactions, Token-2022 TLV extensions, bonding-curve and AMM pool math |

---

## 4. Repository map

```
UVIX-SOL/
├── core/
│   ├── mesh/            # Neural topology, routing graph, loss matrix, envelope dispatch
│   ├── crypto/          # ML-KEM / ML-DSA, hybrid fallback, sealed key storage
│   ├── intelligence/    # Reasoning, dossier profiling, Monte Carlo equity, CFR+ solver
│   ├── hardware/        # Heterogeneous workload split across accelerator classes
│   └── protocol/        # Wire codec, transaction & token decoders, RPC / PubSub clients
├── persistence/         # Proof-of-history chain node (UVIX-RI-1.0) & operator runbook
├── funding/             # USDC micropayment layer for inference (devnet-first)
├── sol_uvix/            # Facade & backward-compatibility package
├── edge/                # Edge runtime: request router & telemetry sink
├── solana/wecrypto/     # The on-chain program (Anchor / Rust)
├── idl/                 # Canonical program IDL schemas
├── config/              # Topology schemas & sanitized configuration templates
├── scripts/             # Setup & automation
└── tests/               # Pytest + Node.js cross-runtime verification
```

---

## 5. The envelope: UVIX-RI-1.0

Every message, state snapshot, and result that crosses a node boundary is
wrapped as a **slug**:

```
UVIX::Base64( CanonicalJSON(Slug) )::END
```

Canonical JSON means lexicographically sorted keys and the fixed separators
`,` and `:` (no whitespace) — the same logical object serializes to the same
bytes in every runtime.

Each slug carries a `payload_hash`, defined precisely over the payload only:

```
payload_hash = SHA-256( UTF-8( CanonicalJSON(raw_payload) ) )
```

The hash domain is the slug's `raw_payload` object and nothing else: the
envelope metadata (protocol version, source/target platforms, compatibility
layer) and `payload_hash` itself are **outside** the hash, so the definition
is not circular. A SHA-256 hash proves integrity of the payload bytes; it
does not, by itself, authenticate a sender.

Verification begins with canonicalization and integrity. The receiver
reconstructs the hash domain and recomputes `payload_hash`; malformed or
mismatched envelopes are rejected before authentication is evaluated. Where
authentication is required, signature verification follows integrity
verification.

Interoperability under UVIX-RI-1.0 means exactly one thing: for the same
protocol object, implementations in different runtimes produce the
identical canonical representation and the identical verification result.
Nothing weaker counts as interoperable.

---

## 6. Proof-of-history persistence

UVIX proof-of-history persistence is the suite's application-level
append-only hash-chain mechanism and is distinct from Solana's Proof of
History consensus clock.

The mesh keeps its memory as a chain, one entry per agreed fact:

```
entry  = { node, prevHash, seq, text, ts }
hash   = SHA-256( CanonicalJSON(entry) )
```

- `seq` is monotonic per node; `prevHash` binds each entry to the one before
  it, back to a genesis entry. Break any link and every later hash fails.
- **Witness model:** entries are validated, then witnessed — a primary
  witness countersigns, peers witness in failover order. An entry no witness
  has seen is *local-flagged*: valid, but marked as not yet corroborated,
  and swept up by periodic reconciliation.
- **Anchoring:** at fixed intervals the chain's root hash is committed to
  Solana in a memo, so the mesh's memory acquires an external timestamp it
  cannot forge after the fact.
- **Verification is total:** any holder of the chain can recompute every
  hash from genesis and confirm the head. There is no trusted checkpoint.

The chain is young. Its first seals are set; its witnesses are still
gathering. That is the correct order — memory first, corroboration second,
anchoring when the cadence calls for it.

---

## 7. Neural mesh routing

Work is routed by a multi-factor loss function evaluated per task class:

$$
\text{Cost} = w_1\ln(1+\text{Latency}) + w_2\frac{1}{1.01-\text{Load}} + w_3\text{AffinityPenalty} + w_4\text{ErrorPenalty}
$$

Task classes carry affinities — text and embedding work gravitates to one
accelerator class, raster and video to another, chain instructions to
validator-adjacent nodes, signatures to the cryptographic signer class,
game-theoretic solving to the solver class. The matrix is re-weighted by
observed latency and error history; the mesh learns which of its limbs are
fast and reliable.

Node classes, capacities, and membership are runtime facts. They are
discovered through the overlay, never published in this repository.

---

## 8. Protocol decoders

- **Versioned transactions (v0):** full wire decoding — address lookup
  tables, signer/writable permission maps, compute-budget and priority-fee
  extraction.
- **SPL Token-2022:** raw TLV extension parsing, including
  `TransferFeeConfig` (with epoch-scheduled fee changes),
  `InterestBearingConfig`, `PermanentDelegate`, and `TokenMetadata` —
  decoded from bytes, not from anyone's API summary.
- **Market structures:** bonding-curve mathematics and constant-product
  pool simulation for launchpad and AMM venues, computed locally from
  first principles.

---

## 9. Post-quantum core

- **ML-KEM (Kyber):** quantum-resistant key encapsulation for node-to-node
  key exchange.
- **ML-DSA (Dilithium):** lattice signatures authenticating state turn
  proofs.
- **Hybrid fallback:** X25519 / Ed25519 with AES-256-GCM sealed payloads,
  for peers and paths where the lattice suite is not yet negotiated.

Keys live in sealed, authenticated storage. Key material, like topology,
is never in this repository — only the mathematics that uses it.

---

## 10. The on-chain program

A single Anchor program holds the suite's public memory:

- **Program ID:** `9HLcTyxqXTimBXj9RvP2dZtTwZsNdzdiGRNRdUTTUp5B`
- **Canonical IDL:** [`idl/wecrypto.json`](idl/wecrypto.json)

| Instruction | Semantics |
| :--- | :--- |
| `initialize` | Creates the singleton `GlobalConfig`; establishes the authority |
| `commit_prediction` | Seals a market probability forecast *before* its expiration horizon |
| `resolve_prediction` | Records the realized outcome; scores the commitment by quadratic (Brier) loss |
| `record_turn_proof` | Anchors a monotonic state hash to a proof turn and slot height |
| `log_token_signal` | Stores a forensic assessment: risk score, LP burn/lock status, bundle detection |
| `update_config` | Administrative pause controls and authority migration |

Three registries, one program: what was predicted, what was proven, what
was flagged. Commitments cannot be backdated, resolutions cannot be
un-scored, and signals cannot be quietly removed.

The program's deployment state is a fact of the chain, not of this
document. Consult the chain.

---

## 11. Cross-chain export

The mesh's memory does not have to stay on the chain where it was written.
**Chainlink CCIP** is the suite's designated cross-chain transport: PoH
root anchors and exported state — inference results, memory-state roots —
leave their home chain as CCIP messages and arrive verifiable on the
destination under the same rule as everything else here. The payload is
canonical, the hash is recomputed on arrival, and the envelope does not
care which chain it lands on.

- **Lanes:** the routes that matter — Solana ↔ EVM, both directions,
  testnet and mainnet — are confirmed in Chainlink's own directory, not
  assumed.
- **Double verification:** CCIP's security layer attests to the transport;
  the UVIX `payload_hash` attests to the content. A root is checkable
  twice, by two systems that owe each other nothing.
- **CRE:** Chainlink's Runtime Environment is under evaluation as an
  external compute and verification environment for these exports — a
  place where workflows can react to anchored state without any mesh node
  having to be awake for it.

Status, stated plainly: designated and lane-verified, not yet
load-bearing. The memo anchor (§6) is what runs today. CCIP is where the
roots go when they start to travel.

---

## 12. Funding layer: USDC micropayments for inference

Work in the mesh is not free, and the suite accounts for it in the open.
Inference is metered per call and paid in **USDC micro-amounts** on Circle's
rails — sub-cent to cents per call, priced by model class from a published
table (1 USDC = 1,000,000 micro-units).

- **Devnet-first.** Development and day-to-day fleet use run on Solana
  devnet with Circle test USDC. A dedicated funding wallet holds a working
  float, so no call ever waits on a faucet run or a funding transfer. The
  economics — price table, caps, burn rate — are proven where mistakes are
  free; mainnet is a promotion, not a starting point.
- **Fast at call time.** A call never blocks on a settlement confirmation.
  Dispatch is optimistic against the funded float and the caller's budget
  caps; metering is local and immediate, and settlement batches on a
  cadence. The chain confirms history; it does not gate it.
- **Receipts are slugs.** Every paid call produces a UVIX-RI-1.0 receipt —
  quote, payment reference, model class, payload hash — recorded in the
  proof-of-history chain (§6) like any other agreed fact. What the fleet
  spent is therefore as verifiable as anything else it remembers.
- **Budget policy is explicit.** Per-call caps, per-agent daily caps, and a
  kill switch bound the float. An agent that hits its cap stops spending,
  not thinking — local work continues, paid work queues.

Status: design. The full specification — price-table shape, settlement
cadence, wallet custody, and the gates on the way to mainnet — lives in
[`funding/`](funding/).

---

## 13. Tracks: separate routes, one protocol

The suite's work runs on separate tracks. Each track is its own route —
its own deployment, cadence, and failure domain — and all of them speak
the same envelope (§5) and register in the same manifest. Routes multiply;
formats don't.

| Track | Carries | Character |
|---|---|---|
| **Data** | Market feeds, oracle data feeds, price proxies | Read-only, cacheable, hot |
| **Interop** | Cross-chain export (§11), on-chain anchors (§6) | Data-only, batch cadence |
| **Value** | The funding layer (§12) — the only track that moves money | Capped, pausable, gated |
| **Memory** | Proof-of-history persistence and root publication | Append-only |
| **Inference** | Model backends, paid per call by the value track | Routed (§7), metered (§12) |

The separation is the safety property. Each track fails differently, so
no track's failure is allowed to become another's: the value track can be
frozen by its kill switch while data keeps flowing; the interop track can
lag a batch while memory keeps appending; a data feed can die without
taking inference with it. What never forks is the layer underneath — one
slug namespace, one registry, one chain. A new capability joins the suite
by taking a route on the appropriate track, not by moving into a
neighbor's.

---

## 14. Configuration philosophy

The repository contains templates — `config/` holds topology *schemas*,
the edge runtime ships a sanitized configuration *template*. Real
configuration is assembled at deployment time, elsewhere, from material
that never enters version control. If you are reading this repository to
find the network, you are reading the wrong artifact: everything here is
the *shape* of the system, none of it is the system.

## 15. Tests

```bash
py -3.13 -m pytest -v          # unit & protocol suites
node tests/test_roundtrip.js   # cross-runtime envelope verification
```

The roundtrip test protects UVIX's foundational interoperability invariant:
the same logical slug, canonicalized independently in every supported
runtime, must produce the same bytes and the same hash. Cryptographic
verification, chain continuity, decoder correctness, routing behavior, and
on-chain state transitions are tested as independent invariants built on top
of that common representation.

## 16. Status

Under active development by its maintainers. The envelope is stable at
UVIX-RI-1.0. The chain remembers. The program awaits its day on-chain.
Further detail is available to those who already know where to ask.

---

## 17. License and trademarks

UVIX-SOL is proprietary software. **All rights reserved.**

UVIX-SOL is not distributed under an open-source license. Access to
the source code does not by itself grant permission to copy, modify,
redistribute, sublicense, sell, commercially exploit, or create
derivative works from it.

See LICENSE for the complete software licensing terms.

UVIX™, UVIX-SOL™, UVIX-RI™, UVIX-RI-1.0™, and
Universal-Inter_compatability™ are project names and source identifiers.
Trademark rights are separate from the software copyright license.

See TRADEMARKS.md for the trademark notice.

Third-party components remain subject to their respective licenses
and notices.
