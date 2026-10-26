# UVIX-SOL: Post-Quantum Cryptography & Solana On-Chain Verification

[![Solana Program](https://img.shields.io/badge/Solana-Anchor%201.2.1-14F195?logo=solana)](https://solana.com)
[![IDL Registry](https://img.shields.io/badge/IDL-wecrytpo.app.leaksnipe.idl.win-0052FF)](https://wecrytpo.app.leaksnipe.idl.win)
[![PQC Security](https://img.shields.io/badge/Security-Post--Quantum%20(Kyber%2FDilithium)-black)](PQC_SECURITY.md)
[![Mesh Protocol](https://img.shields.io/badge/Mesh-UVIX--RI--1.0-blueviolet)](https://uvix.leaksnipe.win/uvix)

UVIX-SOL provides the Solana on-chain anchoring layer and post-quantum cryptographic (PQC) validation pipeline for the **LeakSnipe / WeCrypto** estate. It combines on-chain Proof-of-History state commits, calibrated predictive market settlement with Brier scoring, token forensic verification, and lattice-based cryptographic signing.

---

## 1. Solana On-Chain Program: `WeCrypto`

* **Program ID**: `9HLcTyxqXTimBXj9RvP2dZtTwZsNdzdiGRNRdUTTUp5B`
* **Canonical IDL**: [`idl/wecrypto.json`](idl/wecrypto.json) and [`solana/wecrypto/app/idl/wecrypto.json`](solana/wecrypto/app/idl/wecrypto.json)
* **Hosted IDL URI**: `https://wecrytpo.app.leaksnipe.idl.win/idl/wecrypto.json`
* **Framework**: Anchor `1.2.1` / Agave SDK `v3.1+` / Rust `1.89+`

### Instructions

| Instruction | Accounts & Discriminator | Purpose |
| :--- | :--- | :--- |
| `initialize` | `[payer, config, system_program]` | Initializes the singleton `GlobalConfig` PDA with admin authority and canonical IDL endpoint. |
| `record_turn_proof` | `[payer, config, turn_anchor, system_program]` | Commits a strictly monotonic state turn hash (`[u8; 32]`) anchored to Cloudflare D1 proof turns and Solana slot height. |
| `commit_prediction` | `[payer, config, commitment, system_program]` | Cryptographically commits market probability forecasts (touch/settle basis points) before expiration horizons. |
| `resolve_prediction` | `[authority, config, commitment]` | Records realized market settlement outcomes, settlement price, and quadratic Brier score loss. |
| `log_token_signal` | `[payer, config, signal_record, system_program]` | Stores on-chain forensic assessment (risk score, LP burn/lock status, bundle cluster detection, metadata hash). |
| `update_config` | `[authority, config]` | Administrative pause controls, authority migration, and IDL URI updates. |

### Program Derived Addresses (PDAs)

```rust
// Global configuration singleton
[b"global_config"]

// Proof-of-History turn state commits
[b"poh_turn", sequence.to_le_bytes().as_ref()]

// Horizon prediction commitments
[b"prediction", sequence.to_le_bytes().as_ref()]

// Token security & rugcheck forensics
[b"token_signal", token_mint.as_ref()]
```

---

## 2. Directory Structure

```
UVIX-SOL/
├── idl/
│   └── wecrypto.json           # Canonical Anchor IDL with metadata origin
├── solana/
│   └── wecrypto/               # Complete Anchor Rust program suite
│       ├── programs/wecrypto/  # Program source (instructions, state, error, constants)
│       ├── tests/              # LiteSVM automated unit/integration tests
│       ├── Anchor.toml         # Anchor configuration pointing to 9HLcTyxq...
│       └── Cargo.toml          # Workspace manifest
├── pqc.py                      # Post-quantum cryptographic algorithms (Kyber/Dilithium)
├── pqc_api.py                  # PQC REST API & verification routes
├── pqc_files.py                # Encrypted key storage and payload packaging
├── ai_processor.py             # Neural strategy & feature generation
├── ai_router.py                # Model inference routing & fallback
├── dossier_manager.py          # Opponent intelligence and state profiling
├── equity_sim.py               # Monte Carlo game tree simulation
├── nash_train.py               # CFR+ Nash equilibrium solver
├── poker_engine.py             # Real-time state evaluation engine
└── server.py                   # Local orchestration daemon
```

---

## 3. Local Development & Compilation

### Requirements
* Solana CLI / Agave `v2.2+`
* Rust `1.89+` (`x86_64-unknown-linux-gnu`)
* Anchor CLI `1.2.1`

### Building the Program
```bash
cd solana/wecrypto
anchor build
```

The compiled SBF binary is generated at `target/deploy/wecrypto.so` and the refreshed IDL at `target/idl/wecrypto.json`.

### LiteSVM In-Memory Test Suite
```bash
cargo test --package wecrypto
```

---

## 4. Security & Compliance

* Zero live private keys or mnemonic phrases stored in version control.
* Non-reverting fail-closed checks on all monotonic sequence counters and state transitions.
* IDL authenticated against canonical origin `@ wecrytpo.app.leaksnipe.idl.win`.
