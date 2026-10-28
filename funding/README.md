# Funding Layer — USDC Micropayments for Inference

Design specification for the UVIX-SOL funding layer (README §12).
**Status: design. Nothing built, no wallets created, no funds moved.**

## Purpose

Meter inference across the fleet and pay for it in USDC micro-amounts on
Circle's rails, instead of flat subscriptions and opaque plan quotas.
Every agent's inference cost becomes explicit, capped, and payable
agent-to-agent.

## Operating mode: devnet-first

- Settlement cluster during development and day-to-day fleet use:
  **Solana devnet**, with Circle test USDC.
- A dedicated funding wallet holds a working **float**. Calls draw against
  the float; the float is topped up from the faucet on a schedule, never
  per call. No inference ever waits on funding.
- Devnet is the proving ground for the economics: price table, caps, and
  burn rate are measured where mistakes are free. Mainnet promotion is a
  gate (C4), not a default.

## Call flow

1. **Quote** — the funding service prices the request from the price table
   (per model class, in USDC micro-units; 1 USDC = 1,000,000 units).
2. **Authorize** — the quote is checked against the caller's budget caps
   (per-call cap, per-agent daily cap, kill switch). Authorization is
   local and immediate.
3. **Dispatch** — inference runs on the selected backend class (local
   inference nodes, hosted model APIs, gateway model classes). Dispatch
   does **not** wait for a settlement confirmation.
4. **Meter** — actual usage (tokens, wall time, model class) is recorded
   against the quote; variance is settled in the caller's favor by rule,
   not by dispute.
5. **Settle** — payments batch out of the float on a fixed cadence.
   Batching keeps per-call overhead near zero and is what makes the layer
   fast enough to use on every call, always.
6. **Receipt** — each paid call emits a UVIX-RI-1.0 receipt slug (quote,
   payment reference, model class, payload hash), appended to the
   proof-of-history chain. Spend history inherits the chain's
   verification: any node can recompute what was spent, by whom, on what.

## Budget policy

- **Per-call cap:** no single call may exceed the cap for its model class.
- **Per-agent daily cap:** an agent that reaches its cap stops spending for
  the day. Local (unpaid) work continues; paid work queues.
- **Kill switch:** one operator action freezes all settlement. Metering
  and receipts continue, so the freeze itself is on the record.
- Caps are operator-set numbers. This document defines the mechanisms,
  not the values.

## Custody

- The funding wallet is dedicated to this layer and holds nothing else.
- Keys live in the operator's credential vault, never in this repository,
  never in configuration, never in chat.
- Devnet keys and mainnet keys are different wallets, created at different
  gates. Nothing about the devnet wallet grants anything on mainnet.

## Gates

| Gate | What | Why it's a gate |
|---|---|---|
| C1 | Confirm the settlement rail: Solana devnet USDC as the development default; mainnet chain choice (Solana vs an EVM chain, CCTP if cross-chain) deferred to C4 | Picks the money path the code is written against |
| C2 | Create the devnet funding wallet and fund the first float from the Circle faucet | First credential + first (test) funds |
| C3 | Set the budget policy values: per-call caps, per-agent daily caps, float size, settlement cadence | These are the operator's money rules, even in test units |
| C4 | Mainnet promotion: new wallet, real USDC, first live micro-payment for a real inference call | First real funds movement — flagged the hour it happens, like every movement |

## Relationship to the rest of the suite

- The funding layer **consumes** UVIX-RI-1.0 (receipts are slugs) and the
  proof-of-history chain (receipts are entries). It changes neither.
- It is independent of the cross-chain export layer (§11): CCIP moves
  state roots, data-only. The funding layer moves value. The two never
  share a message.
