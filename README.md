# SOL-UVIX: Solana Stack & UVIX-RI-1.0 Interoperability Protocol

[![CI](https://github.com/johndawalka/SOL-UVIX/actions/workflows/ci.yml/badge.svg)](https://github.com/johndawalka/SOL-UVIX/actions)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Protocol](https://img.shields.io/badge/Protocol-UVIX--RI--1.0-blue.svg)](https://uvix.leaksnipe.win/uvix)

High-performance cryptographic bridge, SDK, and edge runtime for encapsulating the Solana blockchain stack into the canonical **UVIX Slug Protocol (`UVIX-RI-1.0`)**.

Enables deterministic, zero-trust telemetry streaming and cross-agent execution across **Solana RPCs**, **Pump.fun bonding curves**, **Raydium AMMs**, **Cloudflare Workers**, **Discord bots**, and real-time **Parallel CFR game-theoretic solvers**.

---

## 🌟 Key Features

- **UVIX-RI-1.0 Envelope Framing**: Canonical `UVIX::<base64>::END` formatting with deterministic SHA-256 payload integrity hashing (`payload_hash`).
- **Solana On-Chain Decoders**:
  - **Versioned Transactions (v0 & Legacy)**: Wire-level deserialization, Address Lookup Table (ALT) address resolution, instruction permission mapping (signer/writable), and ComputeBudget priority fee extraction.
  - **Address Lookup Table (ALT) Accounts**: Decoding `AddressLookupTab1e1111111111111111111111111` binary accounts, extracting authorities, and indexing dynamically resolved addresses.
  - **Pump.fun Bonding Curves** (`6EF8rrecthR5Dkzon8Nwu78hRvfCKubJ14M5uBEwF6P`): Binary account decoding, virtual reserve ratios, SOL pricing, migration tracking, and constant-product swap simulations (`simulate_buy`, `simulate_sell`).
  - **Raydium V4 AMM Pools** (`675kPX9MHTjS2zt1qfr1NYHuzeLXfQM9H24wFSUt1Mp8`): Constant-product pool reserves, depth calculations, price updates, and swap simulations (`simulate_swap`).
  - **SPL Token & Token-2022**: Base 82-byte mint and 165-byte account layout decoding, TLV extension support (`TransferFeeConfig`, `TransferFeeAmount`, `InterestBearingConfig`, `TokenMetadata`, `MetadataPointer`), and epoch-based fee math.
- **Edge-Ready Cloudflare Worker**: Built-in edge handler (`uvix.leaksnipe.win/uvix`) that verifies payload integrity hashes in V8 and streams telemetry into Cloudflare D1 (`wecrypto`, `scalper`).
- **Multi-Agent Coordination & Mesh Handoffs**: Standardized payloads for inter-agent context handoffs across Tailscale mesh nodes (`maurotufgamingp`, `glap_wsl`, `mariphone`).
- **Polyglot Verification**: Dual Python 3.10+ and Node.js/TypeScript implementations ensuring strict 1:1 cross-language deterministic JSON sorting and SHA-256 validation.

---

## 📐 Architecture & Flow

```mermaid
flowchart LR
    A["Solana Mainnet-Beta<br/>RPC / WebSockets"] -->|Account Data| B["sol_uvix Client"]
    C["Pump.fun / Raydium<br/>On-Chain Events"] -->|Binary State| D["PumpFunDecoder / RaydiumDecoder"]
    
    B --> E["Canonical Hash & Frame<br/>UVIX::<base64>::END"]
    D --> E
    
    E -->|HTTPS POST| F["Cloudflare Edge Worker<br/>uvix.leaksnipe.win"]
    F -->|Verify SHA-256| G{"Integrity Check"}
    G -->|Valid| H[("Cloudflare D1<br/>wecrypto / scalper")]
    G -->|Valid| I["Tailscale Mesh<br/>MauroTUF & Glap-WSL"]
    G -->|Valid| J["Discord Bot<br/>LeakSnipe #3936"]
```

---

## 📦 Installation

### Python
```bash
git clone https://github.com/johndawalka/SOL-UVIX.git
cd SOL-UVIX
pip install -e .
```

### Node.js / Edge Worker
```bash
npm install
npm test
```

---

## 🚀 Quickstart

### 1. Encode a Solana State into a UVIX Slug

```python
from sol_uvix import encode_uvix_slug

payload = {
    "mint": "DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263",
    "symbol": "BONK",
    "sol_price": 0.000000021,
    "slot": 284910283
}

# Generates canonical UVIX::<base64>::END envelope with SHA-256 integrity hash
envelope = encode_uvix_slug(
    payload,
    source_platform="Solana-Mainnet",
    target_platform="UVIX-Mesh-MultiAgent"
)

print(envelope)
# Output: UVIX::eyJjb21wYXRpYmlsaXR5X2xheWVyIjoic29sYW5hLXV2aXgtdjEiLC...::END
```

### 2. Decode and Verify Slug Integrity

```python
from sol_uvix import decode_uvix_slug, UVIXIntegrityError

try:
    slug = decode_uvix_slug(envelope, verify_integrity=True)
    print("Source:", slug.source_platform)
    print("Payload Hash:", slug.payload_hash)
    print("Data:", slug.raw_payload)
except UVIXIntegrityError as e:
    print("Tampered envelope detected!", e)
```

### 3. Pump.fun Bonding Curve Decoding

```python
from sol_uvix import PumpFunDecoder

# Decode raw account bytes directly from getAccountInfo RPC
curve_state = PumpFunDecoder.decode_account_data(
    raw_account_bytes,
    mint="6EF8rrecthR5Dkzon8Nwu78hRvfCKubJ14M5uBEwF6P"
)

print(f"Price: {curve_state.price_in_sol:.9f} SOL")
print(f"Progress to Raydium: {curve_state.progress_percent}%")

# Wrap directly to UVIX slug for multi-agent dispatch
slug = PumpFunDecoder.to_uvix_slug(curve_state)

# Simulate a 1 SOL buy
simulation = PumpFunDecoder.simulate_buy(curve_state, sol_amount_lamports=1_000_000_000)
print(f"Tokens Out: {simulation['tokens_out']}")
print(f"Price Impact: {simulation['price_impact_pct']}%")
```

### 4. VersionedTransaction (v0) & Address Lookup Table Parsing

```python
from sol_uvix import VersionedTransaction, AddressLookupTableAccount

# Deserialize wire-format transaction (Base64 or raw bytes)
tx = VersionedTransaction.from_base64(raw_base64_tx)

# Resolve addresses dynamically against Address Lookup Tables
resolved_keys = tx.resolve_addresses(lookup_tables={
    "AddressLookupTablePubkey...": ["Address0...", "Address1..."]
})

# Extract ComputeBudget priority fees & limits
cb = tx.extract_compute_budget()
print(f"Compute Limit: {cb.unit_limit} CUs")
print(f"Priority Fee: {cb.priority_fee_lamports} lamports ({cb.priority_fee_sol:.6f} SOL)")

# Wrap directly to canonical UVIX envelope
slug = tx.to_uvix_slug()
```

### 5. SPL Token-2022 Transfer Fees & Mint Extensions

```python
from sol_uvix import SPLTokenDecoder

# Parse binary mint account with Token-2022 TLV extensions
mint = SPLTokenDecoder.decode_mint_data(raw_mint_bytes)

if mint.is_token_2022 and mint.transfer_fee_config:
    fee = mint.calculate_transfer_fee(amount=100_000, current_epoch=250)
    print(f"Transfer fee: {fee} token units")

# Wrap state into canonical UVIX envelope
slug = mint.to_uvix_slug()
```

---

## 🌐 CLI Usage

```bash
# Query an on-chain account and output its canonical UVIX slug
sol-uvix account DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263

# Decode an envelope from stdin
sol-uvix decode "UVIX::...::END"

# Parse a Versioned Transaction and print its UVIX slug
sol-uvix tx "AQAAAA..."

# Decode a Token-2022 mint account buffer
sol-uvix token "AQAAAA..." --type mint

# Query local Solana CLI configuration & cluster status
sol-uvix config
sol-uvix status
sol-uvix balance
```

---

## 🛡️ Protocol Specification (`UVIX-RI-1.0`)

An envelope is framed as:
```text
UVIX::<BASE64(CanonicalJSON(UVIXSlug))>::END
```

The canonical JSON object contains:
| Field | Type | Description |
|---|---|---|
| `protocol_version` | `string` | Version identifier (e.g. `"1.0"`) |
| `source_platform` | `string` | Originating subsystem (e.g. `"Solana-Stack"`) |
| `target_platform` | `string` | Destination service (e.g. `"UVIX-Mesh-MultiAgent"`) |
| `payload_hash` | `string` | SHA-256 hexadecimal hash of deterministic canonical JSON of `raw_payload` |
| `compatibility_layer`| `string` | Target protocol binding (e.g. `"solana-uvix-v1"`) |
| `raw_payload` | `object` | Arbitrary JSON payload data |

---

## 🤝 Repositories & Sync

- **GitHub**: [`https://github.com/johndawalka/SOL-UVIX`](https://github.com/johndawalka/SOL-UVIX)
- **GitLab**: [`https://gitlab.com/maurofanellijr/SOL-UVIX`](https://gitlab.com/maurofanellijr/SOL-UVIX)

---

## 📜 License

MIT © [Mauro Fanelli](mailto:maurofanellijr@gmail.com) & [JohnDaWalka](https://github.com/johndawalka).
