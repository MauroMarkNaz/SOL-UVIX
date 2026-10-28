#!/usr/bin/env node
// uvix-solana-persistence.js — UVIX per-node append-only hash chain.
// Rebuilt by Truffle 2026-10-25 from Mauro's deployment spec (Grok's original
// 251-line artifact never transferred; this build's format is CANONICAL).
//
// Record format (UVIX-RI-1.0): hash = SHA-256 of the deterministic
// key-sorted JSON of {node, prevHash, seq, text, ts}. Same canonical form
// is used for the D1 uvix_poh_persistence envelope + state_sha256.
//
// Design (per spec + failover addendum):
//  - Local append-only JSONL chain; every write recomputes the hash and
//    verifies the previous-hash link; write refused on failure.
//  - Witness failover tiers, in order: validator -> primary -> peers
//    (UVIX_PEER_URLS fan-out, 5s timeout each). No witness available ->
//    entry appended locally and FLAGGED in a sidecar (chain lines are
//    immutable); a reconcile pass re-witnesses flagged entries later.
//    UVIX_REQUIRE_WITNESS=1 -> a write with insufficient witnesses is
//    REFUSED (nothing appended); majority required when peers exist.
//  - Solana root every 50 entries only when UVIX_SOLANA_RPC and
//    UVIX_SOLANA_KEYPAIR are set; otherwise the root goes to a side file.
//  - Sorted index array (ts + byte offset) kept chronological by
//    insertion; range queries binary-search the bounds. (Red-black tree
//    rejected for v1; revisit past ~100K entries.)
"use strict";
const fs = require("fs");
const path = require("path");
const os = require("os");
const http = require("http");
const crypto = require("crypto");

// ---------- UVIX-RI-1.0 canonical JSON + hashing ----------
function canon(v) {
  if (v === null || typeof v !== "object") return JSON.stringify(v);
  if (Array.isArray(v)) return "[" + v.map(canon).join(",") + "]";
  return "{" + Object.keys(v).sort().map((k) => JSON.stringify(k) + ":" + canon(v[k])).join(",") + "}";
}
const sha256 = (s) => crypto.createHash("sha256").update(s, "utf8").digest("hex");
function entryHash(e) {
  return sha256(canon({ node: e.node, prevHash: e.prevHash, seq: e.seq, text: e.text, ts: e.ts }));
}

// ---------- Config ----------
const CHAIN_PATH = process.env.UVIX_CHAIN_PATH || path.join(__dirname, "uvix-chain.jsonl");
const FLAGS_PATH = CHAIN_PATH + ".flags.json";
const ROOT_PATH = CHAIN_PATH + ".root.json";
const WITNESS_LOG = CHAIN_PATH + ".witnesses.jsonl";
const NODE_ID = process.env.UVIX_NODE_ID || os.hostname();
const PEER_URLS = (process.env.UVIX_PEER_URLS || "").split(",").map((s) => s.trim()).filter(Boolean);
const VALIDATOR_URL = process.env.UVIX_VALIDATOR_URL || "";
const PRIMARY_URL = process.env.UVIX_PRIMARY_URL || "";
const REQUIRE_WITNESS = process.env.UVIX_REQUIRE_WITNESS === "1";
const ROOT_EVERY = 50;

// ---------- Chain state ----------
// `chain` mirrors Grok's snippet: the current head entry object, or a
// GENESIS sentinel before the first write. Full entries live in `entries`.
let entries = [];
let index = []; // {ts, offset} — offset = byte offset of the line in the chain file
let chain = { hash: "GENESIS" };

function loadChain() {
  entries = []; index = [];
  chain = { hash: "GENESIS" };
  if (!fs.existsSync(CHAIN_PATH)) return;
  const buf = fs.readFileSync(CHAIN_PATH);
  let off = 0;
  for (const line of buf.toString("utf8").split("\n")) {
    if (!line.trim()) { off += Buffer.byteLength(line) + 1; continue; }
    const e = JSON.parse(line);
    entries.push(e);
    index.push({ ts: e.ts, offset: off });
    off += Buffer.byteLength(line) + 1;
  }
  if (entries.length) chain = entries[entries.length - 1];
}
function loadFlags() {
  try { return JSON.parse(fs.readFileSync(FLAGS_PATH, "utf8")); } catch { return {}; }
}
function saveFlags(f) { fs.writeFileSync(FLAGS_PATH, JSON.stringify(f, null, 1)); }

function verifyChain() {
  let prev = "GENESIS";
  for (const e of entries) {
    if (e.prevHash !== prev) return { ok: false, at: e.seq, why: "prev link mismatch" };
    if (entryHash(e) !== e.hash) return { ok: false, at: e.seq, why: "hash mismatch" };
    prev = e.hash;
  }
  return { ok: true, count: entries.length, head: prev };
}

// Existing local hash-chain logic (from the failover addendum): recompute
// hash, check prev link, refuse on mismatch.
function appendLocal(entry) {
  const prev = chain || { hash: "GENESIS" };
  const node = { ...entry, prevHash: prev.hash, seq: entries.length, node: NODE_ID };
  node.hash = entryHash(node);
  const check = verifyChain();
  if (!check.ok) throw new Error("chain link broken — refusing write (" + check.why + " at seq " + check.at + ")");
  if (entries.length && prev.hash !== entries[entries.length - 1].hash)
    throw new Error("chain link broken — refusing write (head moved)");
  const line = JSON.stringify(node);
  const offset = fs.existsSync(CHAIN_PATH) ? fs.statSync(CHAIN_PATH).size : 0;
  fs.appendFileSync(CHAIN_PATH, line + "\n");
  entries.push(node);
  index.push({ ts: node.ts, offset });
  chain = node;
  return node;
}

// ---------- Witness failover (validator -> primary -> local flagged) ----------
async function witnessOnce(url, entry, timeoutMs) {
  const res = await fetch(url.replace(/\/$/, "") + "/witness", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(entry),
    signal: AbortSignal.timeout(timeoutMs),
  });
  if (!res.ok) throw new Error("witness HTTP " + res.status);
  return res.json();
}

async function appendWithFailover(entry, { validatorUrl = VALIDATOR_URL, primaryUrl = PRIMARY_URL, timeoutMs = 5000 } = {}) {
  // Build the candidate entry first — witnesses ack THIS hash.
  const prev = chain || { hash: "GENESIS" };
  const candidate = { ...entry, prevHash: prev.hash, seq: entries.length, node: NODE_ID, ts: entry.ts || Date.now() };
  candidate.hash = entryHash(candidate);

  const attempts = [
    { role: "validator", url: validatorUrl },
    { role: "primary", url: primaryUrl },
    ...PEER_URLS.map((url) => ({ role: "peer", url })),
  ].filter((a) => a.url);
  const needed = REQUIRE_WITNESS ? (attempts.length ? Math.floor(attempts.length / 2) + 1 : 1) : 1;

  const settled = await Promise.allSettled(
    attempts.map(async (a) => ({ role: a.role, witness: await witnessOnce(a.url, candidate, timeoutMs) }))
  );
  const acks = settled.filter((s) => s.status === "fulfilled").map((s) => s.value);

  if (acks.length >= needed && acks.length > 0) {
    const local = appendLocal(candidate);
    return { status: "witnessed", role: acks[0].role, witness: acks[0].witness, witnesses: acks.map((a) => a.role), entry: local };
  }
  if (REQUIRE_WITNESS) {
    throw new Error("witness requirement unmet (" + acks.length + "/" + needed + ") — write refused, nothing appended");
  }
  // No witness available. Append locally but flag it for reconciliation.
  const local = appendLocal(candidate);
  const flags = loadFlags();
  flags[local.seq] = { flagged: true, flagReason: "no_witness_available", at: Date.now() };
  saveFlags(flags);
  return { status: "local_flagged", entry: { ...local, flagged: true, flagReason: "no_witness_available" } };
}

// Reconciliation sweep: re-witness flagged entries; clear flags on ack.
async function reconcile({ timeoutMs = 5000 } = {}) {
  const flags = loadFlags();
  const targets = [
    ...(VALIDATOR_URL ? [{ role: "validator", url: VALIDATOR_URL }] : []),
    ...(PRIMARY_URL ? [{ role: "primary", url: PRIMARY_URL }] : []),
    ...PEER_URLS.map((url) => ({ role: "peer", url })),
  ];
  if (!targets.length) return { rewitnessed: 0, stillFlagged: Object.keys(flags).length, note: "no witness endpoints configured" };
  let cleared = 0;
  for (const seq of Object.keys(flags)) {
    const e = entries[Number(seq)];
    if (!e) { delete flags[seq]; cleared++; continue; }
    const settled = await Promise.allSettled(targets.map((t) => witnessOnce(t.url, e, timeoutMs)));
    if (settled.some((s) => s.status === "fulfilled")) { delete flags[seq]; cleared++; }
  }
  saveFlags(flags);
  return { rewitnessed: cleared, stillFlagged: Object.keys(flags).length };
}

// ---------- Roots ----------
function currentRoot() {
  const rootHash = sha256(entries.map((e) => e.hash).join(""));
  return { node: NODE_ID, count: entries.length, head: entries.length ? entries[entries.length - 1].hash : "GENESIS", root: rootHash, ts: Date.now() };
}

// Solana memo-tx publish (only when RPC + KEYPAIR are set). Stdlib-only:
// legacy transaction serialization + Ed25519 via node:crypto.
const B58 = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz";
function b58decode(s) {
  const bytes = [0];
  for (const ch of s) {
    let carry = B58.indexOf(ch);
    if (carry < 0) throw new Error("bad base58");
    for (let i = 0; i < bytes.length; i++) { carry += bytes[i] * 58; bytes[i] = carry & 0xff; carry >>= 8; }
    while (carry) { bytes.push(carry & 0xff); carry >>= 8; }
  }
  let zeros = 0; while (zeros < s.length && s[zeros] === "1") zeros++;
  return Buffer.concat([Buffer.alloc(zeros), Buffer.from(bytes.reverse())]);
}
function b58encode(buf) {
  const digits = [0];
  for (const b of buf) {
    let carry = b;
    for (let i = 0; i < digits.length; i++) { carry += digits[i] << 8; digits[i] = carry % 58; carry = (carry / 58) | 0; }
    while (carry) { digits.push(carry % 58); carry = (carry / 58) | 0; }
  }
  let zeros = 0; while (zeros < buf.length && buf[zeros] === 0) zeros++;
  return "1".repeat(zeros) + digits.reverse().map((d) => B58[d]).join("");
}
function shortvec(n) {
  const out = [];
  for (;;) { const b = n & 0x7f; n >>= 7; if (n) out.push(b | 0x80); else { out.push(b); break; } }
  return Buffer.from(out);
}
async function solanaPublishRoot(rootObj) {
  const rpc = process.env.UVIX_SOLANA_RPC;
  const kp = JSON.parse(fs.readFileSync(process.env.UVIX_SOLANA_KEYPAIR, "utf8"));
  const secret = Buffer.from(kp.slice(0, 32));
  const pub = Buffer.from(kp.slice(32, 64));
  const der = Buffer.concat([Buffer.from("302e020100300506032b657004220420", "hex"), secret]);
  const key = crypto.createPrivateKey({ key: der, format: "der", type: "pkcs8" });
  const rpcCall = async (method, params) => {
    const r = await fetch(rpc, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ jsonrpc: "2.0", id: 1, method, params }) });
    const j = await r.json();
    if (j.error) throw new Error("solana rpc: " + JSON.stringify(j.error));
    return j.result;
  };
  const bh = await rpcCall("getLatestBlockhash", [{ commitment: "finalized" }]);
  const memoProg = b58decode("MemoSq4gqABAXKb96qnH8TysNcWxMyWCqXgDLGmfcHr");
  const data = Buffer.from("UVIX-ROOT " + rootObj.root + " n=" + rootObj.count, "utf8");
  const msg = Buffer.concat([
    Buffer.from([1, 0, 1]),                       // header: 1 signer, 0 readonly signed, 1 readonly unsigned
    shortvec(2), pub, memoProg,                    // account keys
    b58decode(bh.value.blockhash),                 // recent blockhash
    shortvec(1), Buffer.from([1]), shortvec(0), shortvec(data.length), data, // 1 instruction: program idx 1, no accounts, data
  ]);
  const sig = crypto.sign(null, msg, key);
  const tx = Buffer.concat([shortvec(1), sig, msg]);
  const res = await rpcCall("sendTransaction", [tx.toString("base64"), { encoding: "base64" }]);
  return res; // signature (base58 tx id)
}

async function publishRoot() {
  const r = currentRoot();
  if (process.env.UVIX_SOLANA_RPC && process.env.UVIX_SOLANA_KEYPAIR) {
    const sig = await solanaPublishRoot(r);
    return { ...r, published: "solana", signature: sig };
  }
  fs.writeFileSync(ROOT_PATH, JSON.stringify(r, null, 1));
  return { ...r, published: "sidefile", file: ROOT_PATH };
}
async function maybeAutoRoot() {
  if (entries.length && entries.length % ROOT_EVERY === 0) {
    try { await publishRoot(); } catch (e) { console.error("auto-root failed:", e.message); }
  }
}

// ---------- Range history via sorted index (binary search bounds) ----------
function lowerBound(ts) { let lo = 0, hi = index.length; while (lo < hi) { const m = (lo + hi) >> 1; if (index[m].ts < ts) lo = m + 1; else hi = m; } return lo; }
function upperBound(ts) { let lo = 0, hi = index.length; while (lo < hi) { const m = (lo + hi) >> 1; if (index[m].ts <= ts) lo = m + 1; else hi = m; } return lo; }
function history(fromMs = 0, toMs = Number.MAX_SAFE_INTEGER) {
  return entries.slice(lowerBound(fromMs), upperBound(toMs));
}

// ---------- Simple write mutex (single process) ----------
let queue = Promise.resolve();
function enqueue(fn) { const run = queue.then(fn, fn); queue = run.catch(() => {}); return run; }

// ---------- CLI ----------
async function main() {
  loadChain();
  const [cmd, arg] = process.argv.slice(2);
  if (cmd === "record") {
    const out = await enqueue(() => appendWithFailover({ text: arg || "", ts: Date.now() }));
    await maybeAutoRoot();
    console.log(JSON.stringify(out, null, 1));
  } else if (cmd === "verify") {
    console.log(JSON.stringify(verifyChain(), null, 1));
  } else if (cmd === "root") {
    console.log(JSON.stringify(currentRoot(), null, 1));
  } else if (cmd === "publish-root") {
    console.log(JSON.stringify(await publishRoot(), null, 1));
  } else if (cmd === "history") {
    const [f, t] = process.argv.slice(3).map(Number);
    console.log(JSON.stringify(history(f || 0, t || Number.MAX_SAFE_INTEGER), null, 1));
  } else if (cmd === "len") {
    console.log(JSON.stringify({ node: NODE_ID, count: entries.length, head: chain.hash }));
  } else if (cmd === "reconcile") {
    console.log(JSON.stringify(await reconcile(), null, 1));
  } else if (cmd === "serve") {
    serve();
  } else {
    console.log("usage: record \"turn text\" | verify | root | publish-root | history [fromMs toMs] | len | reconcile | serve");
    process.exit(cmd ? 1 : 0);
  }
}

// ---------- HTTP API ----------
function serve() {
  const port = Number(process.env.UVIX_PORT || 8787);
  const bind = process.env.UVIX_BIND || "0.0.0.0";
  const server = http.createServer(async (req, res) => {
    const send = (code, obj) => { res.writeHead(code, { "Content-Type": "application/json" }); res.end(JSON.stringify(obj)); };
    const body = await new Promise((resolve) => { let d = ""; req.on("data", (c) => (d += c)); req.on("end", () => resolve(d)); });
    const u = new URL(req.url, "http://x");
    try {
      if (req.method === "POST" && u.pathname === "/record") {
        const { text } = JSON.parse(body || "{}");
        const out = await enqueue(() => appendWithFailover({ text: String(text || ""), ts: Date.now() }));
        await maybeAutoRoot();
        return send(200, out);
      }
      if (req.method === "POST" && u.pathname === "/witness") {
        const e = JSON.parse(body || "{}");
        if (entryHash(e) !== e.hash) return send(400, { ok: false, why: "hash does not recompute" });
        fs.appendFileSync(WITNESS_LOG, JSON.stringify({ at: Date.now(), from: e.node, seq: e.seq, hash: e.hash }) + "\n");
        return send(200, { ok: true, node: NODE_ID, ackFor: e.hash, ts: Date.now() });
      }
      if (req.method === "GET" && u.pathname === "/verify") return send(200, verifyChain());
      if (req.method === "GET" && u.pathname === "/root") return send(200, currentRoot());
      if (req.method === "GET" && u.pathname === "/len") return send(200, { node: NODE_ID, count: entries.length, head: chain.hash, flagged: Object.keys(loadFlags()).length });
      if (req.method === "GET" && u.pathname === "/history") {
        const f = Number(u.searchParams.get("from") || 0), t = Number(u.searchParams.get("to") || Number.MAX_SAFE_INTEGER);
        return send(200, history(f, t));
      }
      if (req.method === "POST" && u.pathname === "/reconcile") return send(200, await reconcile());
      if (req.method === "GET" && u.pathname === "/health") return send(200, { ok: true, node: NODE_ID, count: entries.length });
      return send(404, { error: "not found" });
    } catch (e) {
      return send(422, { error: e.message || String(e) });
    }
  });
  server.listen(port, bind, () => console.log("uvix-persistence serving on " + bind + ":" + port + " node=" + NODE_ID + " chain=" + CHAIN_PATH));
}

if (require.main === module) main().catch((e) => { console.error(e.message || String(e)); process.exit(1); });
module.exports = { canon, sha256, entryHash };
