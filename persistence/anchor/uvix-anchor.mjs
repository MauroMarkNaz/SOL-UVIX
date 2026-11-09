// uvix-anchor.mjs — UVIX Merkle-root anchoring layer, reference implementation.
// Spec: HANDOFF.md (same folder). ESM, zero dependencies beyond node:crypto.
// Cloudflare Workers: works with the `nodejs_compat` compatibility flag
// (node:crypto createHash). Pure functions only: this module never touches
// the network, a keypair, or any chain. It only computes and checks bytes.
//
// Hash: SHA-256 for uvix-anchor/1; BLAKE3 for uvix-anchor/2 (Mauro ruling 9 Nov 2026).
import { createHash } from "node:crypto";
import { blake3, blake3Hex } from "./blake3.mjs";
export { blake3, blake3Hex };

// ---------------------------------------------------------------- bytes ----
export const HASH_LEN = 32;
export const TAG_LEAF = 0x00;        // RFC 9162 leaf prefix
export const TAG_NODE = 0x01;        // RFC 9162 interior-node prefix
export const TAG_ANCHOR_LINK = 0x02; // UVIX anchor-to-anchor chain link
export const GENESIS_ANCHOR_LINK = new Uint8Array(32); // 32 zero bytes

const enc = new TextEncoder();
export const utf8 = (s) => enc.encode(s);

export function sha256(...parts) {
  const h = createHash("sha256");
  for (const p of parts) h.update(p);
  return new Uint8Array(h.digest());
}
export function toHex(b) { return Buffer.from(b).toString("hex"); }
export function fromHex(h) {
  if (typeof h !== "string" || !/^([0-9a-f]{2})*$/.test(h)) throw new Error("bad hex (lowercase, even length required)");
  return new Uint8Array(Buffer.from(h, "hex"));
}
export function bytesEqual(a, b) {
  if (!a || !b || a.length !== b.length) return false;
  let d = 0; for (let i = 0; i < a.length; i++) d |= a[i] ^ b[i];
  return d === 0;
}
const is32 = (b) => b instanceof Uint8Array && b.length === HASH_LEN;

// --------------------------------------------- RFC 8785 JCS canonical JSON --
// Deterministic: object keys sorted by UTF-16 code units, no whitespace,
// ECMAScript number serialisation, JSON.stringify string escaping.
// Rejects anything JCS/I-JSON can't represent so two machines never disagree.
export function jcs(v) {
  if (v === null) return "null";
  switch (typeof v) {
    case "boolean": return v ? "true" : "false";
    case "number":
      if (!Number.isFinite(v)) throw new Error("JCS: non-finite number");
      return JSON.stringify(v); // ES Number::toString == RFC 8785 §3.2.2.3
    case "string":
      if (!v.isWellFormed()) throw new Error("JCS: lone surrogate in string");
      return JSON.stringify(v);
    case "object": {
      if (Array.isArray(v)) return "[" + v.map(jcs).join(",") + "]";
      const proto = Object.getPrototypeOf(v);
      if (proto !== Object.prototype && proto !== null) throw new Error("JCS: only plain objects");
      const keys = Object.keys(v).sort(); // default sort = UTF-16 code-unit order
      return "{" + keys.map((k) => {
        if (!k.isWellFormed()) throw new Error("JCS: lone surrogate in key");
        if (v[k] === undefined) throw new Error("JCS: undefined value at key " + JSON.stringify(k));
        return JSON.stringify(k) + ":" + jcs(v[k]);
      }).join(",") + "}";
    }
    default: throw new Error("JCS: unsupported type " + typeof v);
  }
}
export const jcsBytes = (v) => utf8(jcs(v));

// ------------------------------------- existing UVIX-RI-1.0 entry chain ----
// UNCHANGED from Truffle's uvix-solana-persistence.js: the anchoring layer is
// additive and must reproduce existing hashes byte-for-byte.
//   entry.hash = hex(SHA256(JCS({node, prevHash, seq, text, ts})))
//   prevHash of seq 0 = the ASCII string "GENESIS"
export const RI1_GENESIS = "GENESIS";
export function entryHashRI1(e) {
  return toHex(sha256(jcsBytes({ node: e.node, prevHash: e.prevHash, seq: e.seq, text: e.text, ts: e.ts })));
}
export function verifyChainRI1(entries) {
  let prev = RI1_GENESIS;
  for (let i = 0; i < entries.length; i++) {
    const e = entries[i];
    if (e.seq !== i) return { ok: false, at: i, why: "seq gap/reorder" };
    if (e.prevHash !== prev) return { ok: false, at: i, why: "prev link mismatch" };
    if (entryHashRI1(e) !== e.hash) return { ok: false, at: i, why: "hash mismatch" };
    prev = e.hash;
  }
  return { ok: true, count: entries.length, head: prev };
}
// Merkle leaf DATA for an entry = the 32 raw bytes of its RI-1.0 hash.
// (That hash already commits to text, ts, node, seq AND prevHash.)
export function leafDataFromEntry(e) {
  if (entryHashRI1(e) !== e.hash) throw new Error("entry " + e.seq + ": stored hash does not recompute");
  return fromHex(e.hash);
}

// ----------------------------------------------------- RFC 9162 Merkle ----
export const leafHash = (data) => sha256(Uint8Array.of(TAG_LEAF), data);
export function nodeHash(l, r) {
  if (!is32(l) || !is32(r)) throw new Error("nodeHash: 32-byte children required");
  return sha256(Uint8Array.of(TAG_NODE), l, r);
}
// largest power of two strictly less than n (n >= 2)
export function splitPoint(n) { let k = 1; while (k * 2 < n) k *= 2; return k; }

// MTH over already-hashed leaves (array of 32-byte leaf hashes).
export function mthFromLeafHashes(lh) {
  const n = lh.length;
  if (n === 0) return sha256(new Uint8Array(0)); // RFC 9162 §2.1: MTH({}) = SHA-256()
  if (n === 1) return lh[0];
  const k = splitPoint(n);
  return nodeHash(mthFromLeafHashes(lh.slice(0, k)), mthFromLeafHashes(lh.slice(k)));
}
export const merkleRoot = (leafDatas) => mthFromLeafHashes(leafDatas.map(leafHash));

// Alternative bottom-up builder: pair adjacent nodes, PROMOTE an odd last node
// unchanged (never duplicate it — duplication is the Bitcoin CVE-2012-2459 bug).
// Proven equal to the RFC split rule by the tests.
export function rootByOddPromotion(lh) {
  if (lh.length === 0) return sha256(new Uint8Array(0));
  let level = lh.slice();
  while (level.length > 1) {
    const next = [];
    for (let i = 0; i + 1 < level.length; i += 2) next.push(nodeHash(level[i], level[i + 1]));
    if (level.length % 2) next.push(level[level.length - 1]);
    level = next;
  }
  return level[0];
}

// RFC 9162 §2.1.1 PATH(m, D[n]) — audit path, leaf-to-root order.
export function inclusionProof(lh, m) {
  const n = lh.length;
  if (!(Number.isInteger(m) && m >= 0 && m < n)) throw new Error("inclusionProof: index out of range");
  if (n === 1) return [];
  const k = splitPoint(n);
  return m < k
    ? [...inclusionProof(lh.slice(0, k), m), mthFromLeafHashes(lh.slice(k))]
    : [...inclusionProof(lh.slice(k), m - k), mthFromLeafHashes(lh.slice(0, k))];
}

// RFC 9162 §2.1.3.2 verification. Returns true/false, never throws on bad input.
export function verifyInclusion(index, size, leaf, proof, root) {
  try {
    if (!Number.isSafeInteger(index) || !Number.isSafeInteger(size) || index < 0 || index >= size) return false;
    if (!is32(leaf) || !is32(root) || !Array.isArray(proof) || !proof.every(is32)) return false;
    let fn = BigInt(index), sn = BigInt(size - 1), r = leaf;
    for (const p of proof) {
      if (sn === 0n) return false;
      if ((fn & 1n) === 1n || fn === sn) {
        r = nodeHash(p, r);
        if ((fn & 1n) === 0n) while ((fn & 1n) === 0n && fn !== 0n) { fn >>= 1n; sn >>= 1n; }
      } else {
        r = nodeHash(r, p);
      }
      fn >>= 1n; sn >>= 1n;
    }
    return sn === 0n && bytesEqual(r, root);
  } catch { return false; }
}

// RFC 9162 §2.1.2 PROOF(m, D[n]) via SUBPROOF.
export function consistencyProof(lh, m) {
  const n = lh.length;
  if (!(Number.isInteger(m) && m >= 1 && m <= n)) throw new Error("consistencyProof: need 1 <= m <= n");
  if (m === n) return [];
  return subproof(m, lh, true);
}
function subproof(m, d, b) {
  const n = d.length;
  if (m === n) return b ? [] : [mthFromLeafHashes(d)];
  const k = splitPoint(n);
  return m <= k
    ? [...subproof(m, d.slice(0, k), b), mthFromLeafHashes(d.slice(k))]
    : [...subproof(m - k, d.slice(k), false), mthFromLeafHashes(d.slice(0, k))];
}

const isPow2 = (x) => x > 0n && (x & (x - 1n)) === 0n;
// RFC 9162 §2.1.4.2 verification (strict: size1 = 0 rejected; size1 = size2
// requires an empty proof and equal roots).
export function verifyConsistency(size1, size2, root1, root2, proof) {
  try {
    if (!Number.isSafeInteger(size1) || !Number.isSafeInteger(size2)) return false;
    if (!is32(root1) || !is32(root2) || !Array.isArray(proof) || !proof.every(is32)) return false;
    if (size1 < 1 || size2 < size1) return false;
    if (size1 === size2) return proof.length === 0 && bytesEqual(root1, root2);
    if (proof.length === 0) return false;
    let path = proof;
    if (isPow2(BigInt(size1))) path = [root1, ...proof];
    let fn = BigInt(size1 - 1), sn = BigInt(size2 - 1);
    while ((fn & 1n) === 1n) { fn >>= 1n; sn >>= 1n; }
    let fr = path[0], sr = path[0];
    for (const c of path.slice(1)) {
      if (sn === 0n) return false;
      if ((fn & 1n) === 1n || fn === sn) {
        fr = nodeHash(c, fr); sr = nodeHash(c, sr);
        if ((fn & 1n) === 0n) while ((fn & 1n) === 0n && fn !== 0n) { fn >>= 1n; sn >>= 1n; }
      } else {
        sr = nodeHash(sr, c);
      }
      fn >>= 1n; sn >>= 1n;
    }
    return sn === 0n && bytesEqual(fr, root1) && bytesEqual(sr, root2);
  } catch { return false; }
}

// ------------------------------------------------------ batch windows -----
// Fixed 6-hour UTC windows: [00,06) [06,12) [12,18) [18,24). Seconds since epoch.
export const WINDOW_SEC = 21600;
export function windowOf(tsMs) {
  const s = Math.floor(tsMs / 1000);
  const start = s - (s % WINDOW_SEC);
  return { start, end: start + WINDOW_SEC };
}
// Tree size committed by the anchor for the window ending at endSec:
// the number of leading entries with ts < endSec*1000. Entries must be
// ts-monotonic (non-decreasing) or we refuse — an anchor must never commit to
// an ambiguous cut.
export function treeSizeAtWindowEnd(entries, endSec) {
  const cutMs = endSec * 1000;
  let n = 0;
  for (let i = 0; i < entries.length; i++) {
    if (i > 0 && entries[i].ts < entries[i - 1].ts) throw new Error("ts not monotonic at seq " + i + " — refuse to cut");
    if (entries[i].ts < cutMs) n = i + 1; else break;
  }
  return n;
}

// -------------------------------------------------------- memo format -----
// uvix-anchor/1|c=<cluster>|node=<id>|w=<startSec>-<endSec>|i=<from>-<to>|r=<root hex>|p=<prev link hex>
//   c    : mainnet | devnet         (which cluster this memo claims to live on)
//   node : [a-z0-9-]{1,32}          (UVIX node id, e.g. muse, tuf, glap)
//   w    : 6h UTC window, start % 21600 == 0, end = start + 21600
//   i    : half-open leaf range [from, to) newly covered; to = tree size n of root r; to >= 1
//   r    : RFC 9162 root (SHA-256) of leaves [0, to)
//   p    : anchor link of the previous anchor of this node (64 zero hex for the first)
// All ASCII; fixed field order; no spaces; lowercase hex. Length 192–257 bytes.
export const MEMO_VERSION = "uvix-anchor/1";
export const MEMO_VERSIONS = ["uvix-anchor/1", "uvix-anchor/2"];
export const MEMO_MAX_BYTES = 272; // own cap; grammar worst case is 257 bytes (Solana tx limit is 1232 bytes total)
const MEMO_RE = /^uvix-anchor\/(1|2)\|c=(mainnet|devnet)\|node=([a-z0-9-]{1,32})\|w=(0|[1-9][0-9]{0,11})-(0|[1-9][0-9]{0,11})\|i=(0|[1-9][0-9]{0,14})-(0|[1-9][0-9]{0,14})\|r=([0-9a-f]{64})\|p=([0-9a-f]{64})$/;

function checkFields(f) {
  if (f.wEnd - f.wStart !== WINDOW_SEC || f.wStart % WINDOW_SEC !== 0) throw new Error("memo: window must be one UTC-aligned 6h window");
  if (!(f.from <= f.to) || f.to < 1) throw new Error("memo: need from <= to and to >= 1");
  if (!Number.isSafeInteger(f.to) || !Number.isSafeInteger(f.wEnd)) throw new Error("memo: integer overflow");
}
export function encodeMemo({ version = "uvix-anchor/1", cluster, node, wStart, wEnd, from, to, root, prev }) {
  if (!MEMO_VERSIONS.includes(version)) throw new Error("memo: unsupported version: " + version);
  const rootHex = typeof root === "string" ? root : toHex(root);
  const prevHex = typeof prev === "string" ? prev : toHex(prev);
  const s = `${version}|c=${cluster}|node=${node}|w=${wStart}-${wEnd}|i=${from}-${to}|r=${rootHex}|p=${prevHex}`;
  const parsed = decodeMemo(s); // round-trip = single source of validation
  if (parsed.root !== rootHex || parsed.prev !== prevHex) throw new Error("memo: round-trip mismatch");
  return s;
}
export function decodeMemo(s) {
  if (typeof s !== "string") throw new Error("memo: not a string");
  if (utf8(s).length > MEMO_MAX_BYTES) throw new Error("memo: too long");
  const m = MEMO_RE.exec(s);
  if (!m) throw new Error("memo: does not match uvix-anchor grammar");
  const f = { version: "uvix-anchor/" + m[1], cluster: m[2], node: m[3], wStart: +m[4], wEnd: +m[5], from: +m[6], to: +m[7], root: m[8], prev: m[9] };
  checkFields(f);
  return f;
}
// anchorLink_k = SHA256(0x02 || anchorLink_{k-1} || UTF8(memo_k)); link_{-1} = 32 zero bytes.
export function anchorLink(prevLink, memoStr) {
  if (!is32(prevLink)) throw new Error("anchorLink: 32-byte prev required");
  return sha256(Uint8Array.of(TAG_ANCHOR_LINK), prevLink, utf8(memoStr));
}

// Build the next anchor for one node from its RI-1.0 entries.
// prevAnchor = null for the first anchor, else { memo, link: Uint8Array }.
// Returns { memo, link, n, root, skipped } — skipped=true when n==0 (never anchor an empty tree).
export function buildAnchor({ entries, cluster, node, windowEndSec, prevAnchor = null }) {
  const chk = verifyChainRI1(entries);
  if (!chk.ok) throw new Error(`chain invalid at seq ${chk.at}: ${chk.why} — refusing to anchor`);
  const n = treeSizeAtWindowEnd(entries, windowEndSec);
  const prevTo = prevAnchor ? decodeMemo(prevAnchor.memo).to : 0;
  if (n < prevTo) throw new Error("tree shrank since previous anchor — refusing");
  if (n === 0) return { skipped: true, reason: "empty tree", n };
  const lh = entries.slice(0, n).map((e) => leafHash(leafDataFromEntry(e)));
  const root = mthFromLeafHashes(lh);
  const prevLink = prevAnchor ? prevAnchor.link : GENESIS_ANCHOR_LINK;
  const memo = encodeMemo({ cluster, node, wStart: windowEndSec - WINDOW_SEC, wEnd: windowEndSec, from: prevTo, to: n, root, prev: prevLink });
  return { skipped: false, memo, link: anchorLink(prevLink, memo), n, root: toHex(root), heartbeat: n === prevTo };
}

// Outside-party check of a node's ordered anchor memos against its entries.
// Verifies: grammar, p-links, contiguous ranges, increasing windows, every root
// recomputes from the entries, and RFC 9162 consistency between successive roots.
export function verifyAnchors({ entries, memos, node, cluster }) {
  const chk = verifyChainRI1(entries);
  if (!chk.ok) return { ok: false, why: `chain invalid at seq ${chk.at}: ${chk.why}` };
  const lh = entries.map((e) => leafHash(fromHex(e.hash)));
  let link = GENESIS_ANCHOR_LINK, prev = null;
  for (let k = 0; k < memos.length; k++) {
    let f;
    try { f = decodeMemo(memos[k]); } catch (e) { return { ok: false, at: k, why: e.message }; }
    if (f.node !== node || f.cluster !== cluster) return { ok: false, at: k, why: "node/cluster mismatch" };
    if (f.prev !== toHex(link)) return { ok: false, at: k, why: "prev anchor link mismatch (gap, fork or reorder)" };
    if (f.from !== (prev ? prev.to : 0)) return { ok: false, at: k, why: "leaf range not contiguous" };
    if (prev && f.wStart < prev.wEnd) return { ok: false, at: k, why: "window not increasing" };
    if (f.to > lh.length) return { ok: false, at: k, why: "memo commits to more leaves than the log has" };
    const root = mthFromLeafHashes(lh.slice(0, f.to));
    if (toHex(root) !== f.root) return { ok: false, at: k, why: "root does not recompute from log" };
    if (prev) {
      const proof = consistencyProof(lh.slice(0, f.to), prev.to);
      if (!verifyConsistency(prev.to, f.to, fromHex(prev.root), root, proof)) return { ok: false, at: k, why: "consistency proof failed" };
    }
    link = anchorLink(link, memos[k]);
    prev = f;
  }
  return { ok: true, anchors: memos.length, headLink: toHex(link) };
}
