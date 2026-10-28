> Repo note (Oct 28, 2026): the IDL analyzed here lives in this repo under `idl/` and `solana/wecrypto`; this doc is the Oct 27 audit of it.

# wecrypto — Solana Program IDL Analysis
Program: `9HLcTyxqXTimBXj9RvP2dZtTwZsNdzdiGRNRdUTTUp5B` · IDL v0.1.0 (Anchor spec 0.1.0)
"WeCrypto Solana On-Chain PoH & Predictor Anchor Program"
Analyzed 2026-10-27 by Truffle from the IDL Mauro pasted (canonical copies on his
G: drive: G:\WECRYP\idl\wecrypto.json + .min.json; binary G:\WECRYP\solana\wecrypto\target\deploy\wecrypto.so).
Local copy of the IDL: idl.json alongside this file (one transcription fix logged:
commit_prediction.touch_prob_bps restored to u16 per the original + account struct).

## Verification results (live, 2026-10-27 ~04:05 EDT)
- **Program account does NOT exist on mainnet, devnet, or testnet.** Checked via
  getAccountInfo on all three public clusters; mainnet control query (Token
  program) returned normally through the identical code path, so the negative is
  real. Conclusion: as of this check the program is built but not deployed to any
  public cluster — or it lives behind a custom/local RPC endpoint only.
- **IDL is genuine, internally consistent Anchor output.** All 6 instruction
  discriminators equal sha256("global:<name>")[..8] and all 4 account
  discriminators equal sha256("account:<Name>")[..8]. PDA seed constants decode
  to clean ASCII: "global_config", "prediction", "poh_turn", "token_signal".
- Because nothing is deployed, there is no on-chain IDL account to diff against
  and no GlobalConfig to read yet. Those checks rerun the moment it deploys.

## What the program is
Three append-mostly registries under one authority key, all state in PDAs:
1. **Prediction commitments** — WECFM calls written on-chain BEFORE expiry and
   resolved after settlement, with a Brier score stored at resolution. This is a
   tamper-evident, timestamped track record: the PDA can only be created by a
   real transaction at commit time, so a prediction cannot be backdated, and
   there is no instruction that edits one (resolve is one-way; error 6004 if
   attempted twice).
2. **PoH turn anchors** — the on-chain twin of the UVIX hash chain (UVIX-RI-1.0).
   Each turn stores turn_hash + prev_hash; the program enforces strictly
   monotonic sequence (6002) and prev-hash linkage (6003). The hashes themselves
   are computed off-chain and stored as opaque bytes — the chain enforces the
   LINKAGE, not the content. Each anchor also carries d1_source_id, tying the
   on-chain entry back to the D1 row it mirrors.
3. **Token signal registry** — the dex/rug verdict store: per-mint PDA holding
   risk_verdict, risk_score_bps, bundle_cluster_detected, lp_burned_or_locked,
   and a details_hash pointing at the full off-chain evaluation. This record is
   LATEST-STATE: re-logging the same mint updates the same PDA (updated_at_slot),
   so history lives off-chain (D1), not on-chain.

## Instructions (plain English)
- `initialize(idl_uri?)` — one-time: creates the GlobalConfig PDA, caller becomes
  authority, optionally stores where the IDL lives.
- `update_config(new_authority?, new_idl_uri?, paused?)` — authority-only:
  rotate the authority key, move the IDL pointer, or pause the program.
- `commit_prediction(market_id, sequence, market_type, regime, strike_or_band,
  touch_prob_bps, settle_prob_bps, expiry_at, spot_at_commit)` — authority-signed.
  Creates PDA ["prediction", market_id, sequence]. Probabilities in basis points,
  >10000 rejected (6005). String caps: market_id 64 (6006), regime 32 (6007).
- `resolve_prediction(realized_outcome, settlement_price, brier_score_e4)` —
  authority-only; fills the outcome fields once. Config is read-only here.
- `record_turn_proof(sequence, turn_hash, prev_hash, timestamp, emitter_id,
  d1_source_id)` — authority-signed; creates PDA ["poh_turn", sequence].
- `log_token_signal(token_mint, risk_verdict, risk_score_bps,
  bundle_cluster_detected, lp_burned_or_locked, details_hash)` — authority-signed;
  creates-or-updates PDA ["token_signal", token_mint].

Every write requires TWO signers: `payer` (funds the new account's rent) and
`authority` (must match GlobalConfig.authority, enforced via the IDL's
relations/has_one). Separation is real, but in practice the committing service
needs both keys available at write time.

## Costs (rent-exempt deposits, locked per account — no close instruction exists)
Approx account sizes at max string lengths, rent at (bytes+128) x 6,960 lamports:
- GlobalConfig ~198 B -> ~0.0023 SOL (once)
- PredictionCommitment ~180 B -> ~0.0021 SOL **per prediction, permanent**
- PoHTurnAnchor ~241 B -> ~0.0026 SOL **per turn, permanent**
- TokenSignalRecord ~94 B -> ~0.0016 SOL per mint (reused on updates)
At any real prediction/turn cadence this accumulates locked SOL with no reclaim
path in the IDL. Permanence is the point of the design — just price it in.

## Flags (honest, from the IDL alone)
1. **Not deployed** anywhere public yet (see verification). The registration-form
   network choice (devnet/mainnet/custom) is still just a form field until a
   deploy lands.
2. **idl_uri typo in the metadata**: origin and idlUrl read
   `wecrytpo.app.leaksnipe.idl.win` — "wecrytpo", and the host sits under
   leaksnipe.idl.win rather than his leaksnipe.win zone. If `initialize` stored
   that URI into GlobalConfig, SDK clients resolving the IDL through the config
   pointer will chase a typo'd host. Fix the URI before initializing, or fix it
   after with update_config.
3. **No timing errors in the error enum** (6000–6010): nothing named for
   commit-after-expiry or resolve-before-expiry. The IDL cannot prove the
   program checks the chain Clock against expiry_at — that guarantee, if it
   exists, lives in the .so/source, not the interface. Worth confirming in the
   Rust source, because the whole anti-backdating story is stronger with it.
4. **Single authority key is the trust root.** A leaked authority key can't
   rewrite history (old PDAs are immutable, PoH linkage is enforced), but it CAN
   write fake future predictions/turns/signals until rotated via update_config.
5. **What the IDL does not do** (the general rule): it fully specifies encoding,
   accounts, and constraints an SDK needs — Anchor TS / anchorpy / Codama
   clients generate directly from it — and it certifies nothing about whether
   the program logic behind the interface is correct.
