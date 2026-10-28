# UVIX-SOL — Status

Verified live Oct 28, 2026 (~16:13 EDT), checked firsthand from this node — not relayed.

## PoH persistence chain (node "muse", :8787)

- Format: UVIX-RI-1.0 — hash = SHA-256 of key-sorted canon({node, prevHash, seq, text, ts})
- Count: **4 entries** (seq 0 genesis · 1 corrected estate snapshot, Oct 25 ·
  2 cache-refresh + quickread anchor, Oct 27 · 3 deduped archive anchor, Oct 28)
- Head: `b24a51a0bfbd82d5d38db5ff9e28d68f83a3d4959b79f4c2d52db99d42b81e56`
- Root: `fa10d11f18e63aa072c4f6cbe724b72e1eb0d92bd7208ba23b17aeee9b06da17`
- All 4 entries local-flagged: peer nodes (glap/TUF) not yet joined, by design.
  Solana memo root every 50 entries only when RPC + keypair envs are set (currently unset).

## Emergency system archive (anchored at seq 3)

- `truffle-system-dedup-2026-10-27.tar.gz` — 343 MB, 73,371 files,
  sha256 `96ab5055df0e298fcf4da3440bb285ecfd68633ddb4f2eae2fb928aa8f995384`
- Transfer to G: still pending — no live path from this VM to the TUF.

## wecrypto Solana program

- Program: `9HLcTyxqXTimBXj9RvP2dZtTwZsNdzdiGRNRdUTTUp5B`
- IDL is genuine Anchor output; three registries (prediction commitments,
  PoH turn proofs, token signals). See `program/ANALYSIS.md`.
- **Not deployed** on mainnet, devnet, or testnet. Authority key is the trust root;
  no close instruction (rent not reclaimable). Verification continues after deployment.

## Mesh

- UVIX edge router live (`uvix-edge-router` on uvix.leaksnipe.win); D1 `uvix` seeded.
- Mesh proxy inert (manifest target normalization is Mauro's call); auth gate global.

## Open items

- Peer witness nodes (glap/TUF) not joined → entries stay local-flagged until then.
- Program deployment (then on-chain config vs IDL diff).
- Archive copy to G: when a TUF path exists.
