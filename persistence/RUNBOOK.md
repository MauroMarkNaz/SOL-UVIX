# UVIX Persistence — Runbook (built 2026-10-25, Truffle)

Canonical implementation: `uvix-solana-persistence.js` in this directory.
Grok's original 251-line artifact never transferred; this rebuild from
Mauro's spec is the canonical one. Record format (UVIX-RI-1.0):
`hash = SHA-256(canon({node, prevHash, seq, text, ts}))`, canon =
deterministic key-sorted JSON. The D1 `uvix_poh_persistence.envelope` +
`state_sha256` use the same canon + hash.

## Live state
- Node `muse` (this VM): serve on 127.0.0.1:8787 via run-node.sh
  (flock + pidfile), watchdog cron `uvix-persistence-watchdog` (15m).
  Chain: `uvix-chain.jsonl` here. Genesis entry recorded 2026-10-25.
  No peers configured yet -> entries are local_flagged by design;
  reconcile clears them once a peer exists.
- D1 (wecrypto = wecryp-market-data 4f534c4a): tables
  `uvix_poh_persistence` + `gpump_signal_ledger` created via CF API
  (the d1-connector MCP is READ-ONLY for d1_query — installers that
  CREATE through it will fail with -32603).
- pump.leaksnipe.win (pumpfun-helper v2, additive): POST /api/evaluate
  (candidate mastery heuristics, `record:true` writes a ledger row),
  GET /api/ledger, GET|POST /api/poh. Old routes untouched; D1 binding
  WECRYPTO_D1; standards re-applied + verified after deploy
  (set_standard.py pumpfun-helper --smart — flag goes AFTER the name).

## Add a node (glap / TUF)
1. Copy `uvix-solana-persistence.js` to the machine (single file, Node
   stdlib only, no npm install).
2. Run: `UVIX_NODE_ID=<name> UVIX_PORT=8787 UVIX_PEER_URLS=http://100.115.113.70:8787 node uvix-solana-persistence.js serve`
   (muse's tailnet IP is proxy-only inbound-blocked from this VM's side;
   peer URLs between glap/TUF/muse get set per direction as each node's
   reachability is proven — flagged entries + reconcile bridge the gaps.)
3. Optional tailnet exposure: `tailscale serve --service=svc:leaksnipe --https=443 http://127.0.0.1:8787` style lines per the mesh work.
4. Reconcile after joining: `curl -X POST localhost:8787/reconcile`.

## Solana roots
Every 50 entries (and on `publish-root`): if UVIX_SOLANA_RPC +
UVIX_SOLANA_KEYPAIR (JSON array keypair file, Mauro's own) are set, the
root goes on-chain as a Memo tx; otherwise to `<chain>.root.json`.
No keypair is configured anywhere yet — Mauro's step when he wants it.

## NOT done — gated / missing (do not improvise)
- leaksnipe-suite bridge tool (`gpump_full_token_audit`): needs a suite
  redeploy; the suite is rollback-gated on Mauro's explicit word.
  Corrected wiring when it happens: dex = GET
  https://dex.leaksnipe.win/api/check?q=<mint> (NOT /check/<mint>);
  pump = POST https://pump.leaksnipe.win/api/evaluate (workers.dev
  subdomain for pumpfun-helper is DISABLED — use the custom domain);
  D1/mem/oracle via cloudflare-mcp-d1-connector (d1_query read-only).
- PM2 `uvix-gpump-orchestrator`: the package's ecosystem fragment points
  at `~/wecrypto/uvix_tailnet_orchestrator.py`, a file that was never
  delivered. Nothing to register until it exists.
- Ledger calibration: gpump_signal_ledger starts EMPTY on purpose.
  Seed only with real mints/figures from Mauro's actual trades.
