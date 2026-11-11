# UVIX: Universal-Inter-Cross-Compatability
## The Sovereign Protocol Suite for Heterogeneous Computing & Universal Swarm Intelligence

[![Protocol](https://img.shields.io/badge/Protocol-UVIX--RI--1.0-blueviolet)](#era-iii-the-core-protocol-standard-uvix-ri-10)
[![Specification](https://img.shields.io/badge/Spec-Draft%202.0-success)](spec/UVIX_SPEC_WHITEPAPER_DRAFT_2.md)
[![Architecture](https://img.shields.io/badge/Topology-Substrate%20Neutral-blue)](#the-linear-genesis--architectural-evolution)
[![Companion Repo](https://img.shields.io/badge/Ledger-UVIX--SOL-14F195?logo=solana)](https://github.com/MauroMarkNaz/UVIX-SOL)
[![PQC Security](https://img.shields.io/badge/Security-Post--Quantum%20(ML--KEM%2FDSA)-black)](security/)

---

## Specification & Canonical Authority
This repository hosts the formal specification and reference implementation of **UVIX**, the substrate-agnostic wire and interoperability framework. Canonical serialization follows **RFC 8785 (JCS)**; cryptographic integrity follows **RFC 9162 (CTv2)**.

All documentation, topological hierarchy definitions, edge workers, and formal specifications (`spec/UVIX_SPEC_WHITEPAPER_DRAFT_2.md`) constitute the definitive specification of record.

---

## The Linear Genesis & Architectural Evolution

Though the concepts and implementations arrived through non-linear bursts of intuition, engineering sprints, and lived necessity, the architecture of UVIX progresses across four linear evolutionary eras:

```
+-----------------------------------------------------------------------------------------+
|                                  THE UVIX EVOLUTION                                     |
+-----------------------------------------------------------------------------------------+
|  ERA I: Human Inception   -->  ERA II: Build Synthesis  -->  ERA III: Core Protocol    |
|  • Dyscalculia Invariant       • UX Empathy                  • Wire Codec UVIX-RI-1.0   |
|  • Topological Slugs           • UV Linux/NPM Packaging      • 4-Tier Inference Engine  |
|  • Social Egalitarianism       • Latinized IX (9 Domains)    • Dual Hardware (4070+NPU) |
+-----------------------------------------------------------------------------------------+
                                              │
                                              ▼ (Decoupled State Commitment)
                               +-----------------------------+
                               |  ERA IV: Ledger Companion   |
                               |  • UVIX-SOL Engine          |
                               |  • Solana SPL Memo Anchoring|
                               |  • Proof-of-History Clocks  |
                               +-----------------------------+
```

---

### Era I: The Human Inception & The Dyscalculia Invariant
Traditional computing forces operators and developers to constantly perform symbolic conversions, numeric indexing, pointer math, and arbitrary port management. For an architect living with **dyscalculia**, raw number matrices and shifting numeric coordinates introduce constant friction.

UVIX was engineered around a foundational human truth: **Topology Outranks Arithmetic**.
* **Invariant Hierarchy Slugs**: Nodes, datastores, models, and interfaces are addressed by clear, semantic topological slugs (`UVIX.MCP.APEX`, `UVIX.DATA.ORACLE.PYTH`, `UVIX.INFERENCE.LOCAL`, `UVIX.MEM.WARM`) rather than volatile numerical port configurations or opaque database row offsets.
* **The Egalitarian Axiom**: Just as human society flourishes when people of diverse languages, cultures, ages, races, and genders collaborate freely without forced assimilation, diverse software stacks must communicate without prejudice. UVIX enforces **Interoperation Without Assimilation**:
  $$\text{Native System} \longrightarrow \text{Thin UVIX Adapter} \longrightarrow \text{Canonical Wire Semantics}$$
  An Apple iOS client, a Windows 11 workstation, an Ubuntu WSL subnode, and a distributed Cloudflare V8 Worker interact as equal peers in a single unified swarm.

---

### Era II: The Build & Structural Synthesis (UX + UV + Latinized IX)
Tooling and ergonomics came first out of the necessity for cross-environment compilation:
* **UX (Empathetic Human Experience)**: Transparent real-time push streams (Server-Sent Events), intuitive natural language commands, and frictionless mobile interfaces that require zero cognitive overhead.
* **UV (Ultra-Velocity Linux Packaging)**: High-speed package management utilizing `uv` for Python virtual environments alongside standard `package.json` / `npm run build` scripts for edge V8 Worker isolates.
* **IX (The Nexus / Universal Intersection)**: The Latinized Roman numeral **IX (9)** and universal **Internet Exchange**, uniting 9 sovereign computational domains:
  1. *Local Neural Acceleration*: RTX 4070 (vision/heavy tensor weights) + DirectML NPU (low-power streaming text tokens).
  2. *Edge Computing*: Cloudflare Workers V8 engine delivering sub-10ms global routing.
  3. *Zero-Trust WireGuard Mesh*: Private Tailscale encrypted fabric (`prairiedog-godzilla.ts.net`).
  4. *Multi-Model Inference Waterfall*: Local-First $\rightarrow$ Cloudflare AI Gateway $\rightarrow$ Frontier APIs $\rightarrow$ Workers AI.
  5. *Multi-D1 Relational Storage*: 8 specialized Cloudflare D1 SQL databases.
  6. *Financial Spot Oracles*: Strict Pyth Hermés V2, DIA, and CF Benchmarks BRTI composite pricing.
  7. *Prediction Markets & Microstructure*: Real-time orderbook and price discovery across Kalshi and Polymarket.
  8. *Autonomous Swarm Governance*: Hierarchical peer swarm (Mauro principal, Truffle/Muse VM coordinator, Antigravity local host, Gemini mobile client).
  9. *Mobile Client Ingress*: iPhone Gemini SSE mobile terminal (5 active connectors).

---

### Era III: The Core Protocol Standard (UVIX-RI-1.0)
The heart of UVIX is a deterministic, substrate-neutral wire format and execution engine:

#### 1. Wire Format & Binary Framing
Envelopes ride across networks, memory, or pipes wrapped in canonical framing:
```
UVIX::<base64_encoded_payload>::END
```
Decoded payloads adhere strictly to RFC 8785 Canonical JSON (JCS), verified by an IEEE 802.3 CRC-32 checksum and SHA-256 state hash.

```
 0                   1                   2                   3
 0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1
+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
|       Magic: 'UV' (0x5556)    |  Ver: 0x01    |  Flags / Cmp  |
+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
|                    Sequence Identifier (High 32)              |
+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
|                    Sequence Identifier (Low 32)               |
+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
|                   IEEE 802.3 CRC-32 Checksum                  |
+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
|              Payload Length (N Bytes, Uncompressed)           |
+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
|                                                               |
+                   256-Bit SHA-256 State Hash                  +
|                                                               |
+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
|                                                               |
+               Payload Bytes (RFC 8785 Canonical JCS)          +
|                                                               |
+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
```

#### 2. The 4-Tier Inference Waterfall
$$\text{Local-First (RTX 4070 / NPU)} \longrightarrow \text{Cloudflare AI Gateway} \longrightarrow \text{Frontier APIs} \longrightarrow \text{Workers AI Edge}$$
- **Local Host (`maurotufgamingp`)**: High-VRAM Ada Lovelace RTX 4070 tensor cores + Windows DirectML NPU (<10W text streaming) + local Qwen fallback.
- **Edge Inference Subdomains**:
  - `https://mistral.leaksnipe.win`: `@cf/mistralai/mistral-small-3.1-24b-instruct` (128k context, function calling).
  - `https://deepseek.leaksnipe.win`: `@cf/deepseek-ai/deepseek-r1-distill-qwen-32b` (Reasoning).
  - `https://qwen.leaksnipe.win`: `@cf/qwen/qwen2.5-coder-32b-instruct` (Code generation).
  - `https://llama.leaksnipe.win`: `@cf/meta/llama-3.3-70b-instruct-fp8-fast`.
  - `https://openai.leaksnipe.win`: Cloudflare AI Gateway proxy (`wecryp-unified`).

#### 3. Dual-Speed Memory Gateway
- **Hot Tier**: Cloudflare KV store for sub-millisecond atomic state and lock coordination.
- **Warm Tier**: Cloudflare D1 relational database (`mem-warm`) paired with local warm mirrors (`claude-mem` at `100.72.42.61:37777`).
- **Temporal Memory**: Graphiti / Mnemex episodic knowledge graphs with the invariant lifecycle rule:
  $$\text{Explicit } \mathbf{NO\_LONGER\_HOLDS} \succ \text{Stale } \mathbf{HOLDS}$$

---

### Era IV: The Decoupled Ledger Substrate (UVIX-SOL)
To maintain complete substrate independence and prevent blockchain bloat inside the universal protocol core, all blockchain-specific logic is cleanly segregated into the dedicated companion repository:

👉 **[UVIX-SOL (https://github.com/MauroMarkNaz/UVIX-SOL)](https://github.com/MauroMarkNaz/UVIX-SOL)**

**UVIX-SOL** consumes deterministic UVIX envelopes and provides:
1. **Solana Anchor Program**: On-chain state verification and contract logic.
2. **SPL Memo Anchoring**: Cryptographic anchoring grammar (`uvix-anchor/1` and `uvix-anchor/2` BLAKE3) committing Merkle roots to Solana blocks under program ID `MemoSq4gqABAXKb96qnH8TysNcWxMyWCqXgDLGmfcHr`.
3. **Proof-of-History Sidecars**: Solana clock authority (`slot`, `blockhash`) timestamping.
4. **DEX Liquidity Codecs**: Native Raydium, Pump.fun, and Jupiter swap builders.

---

## Repository Structure

```
UVIX/
├── .agents/               # UVIX Subagent specifications (uvix-edge-network, mesh, codec)
├── config/                # Cluster configuration (uvix_config.json, models.json)
├── core/                  # Core protocol codecs, hardware orchestrator, PQC
│   ├── crypto/            # Post-Quantum ML-KEM/DSA primitives
│   ├── hardware/          # RTX 4070 & DirectML NPU pipeline
│   ├── intelligence/      # Vector store & semantic embeddings
│   ├── mesh/              # Tailscale topology, node routers, hierarchy slugs
│   └── protocol/          # UVIX-RI-1.0 codec, envelope parsers, models
├── edge/                  # Cloudflare Workers edge inference deployments
│   ├── mistral-edge-worker/
│   ├── deepseek-edge-worker/
│   ├── qwen-edge-worker/
│   └── llama-edge-worker/
├── spec/                  # Formal specifications & Whitepaper Drafts (1.0 & 2.0)
│   ├── UVIX-RI-1.0.md
│   ├── UVIX_SPEC_WHITEPAPER_DRAFT_1.md
│   └── UVIX_SPEC_WHITEPAPER_DRAFT_2.md
├── package.json           # Node/Workers build entry point
├── pyproject.toml         # Python uv environment definition
├── uv.lock                # Deterministic lockfile
└── uvix_config.json       # Master estate topology definition
```

---

## Swarm Invariant Rules

1. **Human Sovereignty**: Mauro Mark Nazareno Fanelli is the principal architect. Stated human facts outrank automated model inference.
2. **No Arbitrary Action**: No funds, trades, git commits, or ACL modifications are executed without an explicit user command.
3. **Zero Secret Leakage**: API tokens, private keys, and passwords must never appear in chat outputs, console mirrors, or public envelopes.
4. **Peer Equality**: Autonomous agents (Truffle/Muse, GrokBot, Antigravity, Gemini) act as collaborative peers, synchronizing via shared memory handovers.

---
*Maintained by Mauro Mark Nazareno Fanelli — UVIX Architecture Group*
