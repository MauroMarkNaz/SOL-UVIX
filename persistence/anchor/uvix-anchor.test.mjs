// Run: node uvix-anchor.test.mjs   (exit code 0 = all pass)
import { readFileSync, readdirSync, statSync } from "node:fs";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";
import * as A from "./uvix-anchor.mjs";

const HERE = dirname(fileURLToPath(import.meta.url));
const V = join(HERE, "vectors");
const deviations = [];
let pass = 0, fail = 0; const fails = []; const groups = {};
function t(group, name, cond) {
  groups[group] ??= { pass: 0, fail: 0 };
  if (cond) { pass++; groups[group].pass++; } else { fail++; groups[group].fail++; fails.push(group + " :: " + name); }
}
const b64 = (s) => new Uint8Array(Buffer.from(s ?? "", "base64"));
const hx = A.toHex, fh = A.fromHex;
const walk = (d) => readdirSync(d).flatMap((f) => { const p = join(d, f); return statSync(p).isDirectory() ? walk(p) : p.endsWith(".json") ? [p] : []; });

// ---- 1. RFC 9162 hasher known answers (transparency-dev rfc9162_test.go) ----
t("hasher", "empty root", hx(A.mthFromLeafHashes([])) === "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855");
t("hasher", "empty leaf", hx(A.leafHash(new Uint8Array(0))) === "6e340b9cffb37a989ca544e6bb780a2c78901d3fb33738768511a30617afa01d");
t("hasher", "leaf L123456", hx(A.leafHash(A.utf8("L123456"))) === "395aa064aa4c29f7010acfe3f25db9485bbd4b91897b6ad7ad547639252b4d56");
t("hasher", "node N123|N456", hx(A.sha256(Uint8Array.of(1), A.utf8("N123"), A.utf8("N456"))) === "aa217fe888e47007fa15edab33c2b492a722cb106c64667fc2b044444de66bbb");

// ---- 2. Tree vectors from transparency-dev testonly/constants.go ----
const go = readFileSync(join(V, "td-constants.go"), "utf8");
const block = (fn) => go.slice(go.indexOf("func " + fn)).split("\n}\n")[0];
const hds = (s) => [...s.matchAll(/hd\("([0-9a-f]*)"\)/g)].map((m) => m[1]);
const LEAVES = hds(block("LeafInputs")).map(fh);
const ROOTS = ["e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855", ...hds(block("RootHashes"))];
const NODES0 = hds(block("NodeHashes")).slice(0, 8);
t("td-vectors", "parsed 8 leaves / 9 roots", LEAVES.length === 8 && ROOTS.length === 9);
const LH = LEAVES.map(A.leafHash);
LH.forEach((h, i) => t("td-vectors", "leaf hash " + i, hx(h) === NODES0[i]));
for (let n = 0; n <= 8; n++) {
  t("td-vectors", "root size " + n, hx(A.merkleRoot(LEAVES.slice(0, n))) === ROOTS[n]);
  t("td-vectors", "odd-promotion root size " + n, hx(A.rootByOddPromotion(LH.slice(0, n))) === ROOTS[n]);
}

// ---- 3. transparency-dev inclusion + consistency probes (incl. wantErr) ----
for (const f of walk(join(V, "inclusion"))) {
  const p = JSON.parse(readFileSync(f, "utf8"));
  const ok = A.verifyInclusion(p.leafIdx, p.treeSize, b64(p.leafHash), (p.proof ?? []).map(b64), b64(p.root));
  t("td-inclusion-probes", f.slice(V.length) + " (" + p.desc + ")", ok === !p.wantErr);
}
for (const f of walk(join(V, "consistency"))) {
  const p = JSON.parse(readFileSync(f, "utf8"));
  const ok = A.verifyConsistency(p.size1, p.size2, b64(p.root1), b64(p.root2), (p.proof ?? []).map(b64));
  // Deliberate deviation: this one reference probe passes 12-byte "don't care" roots with
  // size1==size2 and expects success. We are stricter (every hash must be 32 bytes), so we
  // expect rejection here and count it as a documented deviation, not a silent pass.
  if (f.endsWith("sizes-are-equal-one-and-proof-is-empty.json")) { t("td-consistency-probes", "DEVIATION(strict 32-byte roots) " + p.desc, ok === false); deviations.push(f.slice(V.length)); continue; }
  t("td-consistency-probes", f.slice(V.length) + " (" + p.desc + ")", ok === !p.wantErr);
}
// Our GENERATED proofs must be byte-identical to the valid reference probes.
for (const f of walk(join(V, "inclusion"))) {
  const p = JSON.parse(readFileSync(f, "utf8"));
  if (p.wantErr || p.treeSize > 8 || hx(b64(p.root)) !== ROOTS[p.treeSize] || hx(b64(p.leafHash)) !== hx(LH[p.leafIdx] ?? new Uint8Array())) continue;
  const mine = A.inclusionProof(LH.slice(0, p.treeSize), p.leafIdx).map(hx);
  t("td-generated-match", "incl " + f.slice(V.length), JSON.stringify(mine) === JSON.stringify((p.proof ?? []).map((x) => hx(b64(x)))));
}
for (const f of walk(join(V, "consistency"))) {
  const p = JSON.parse(readFileSync(f, "utf8"));
  if (p.wantErr || p.size2 > 8 || p.size1 < 1 || hx(b64(p.root1)) !== ROOTS[p.size1] || hx(b64(p.root2)) !== ROOTS[p.size2]) continue;
  const mine = A.consistencyProof(LH.slice(0, p.size2), p.size1).map(hx);
  t("td-generated-match", "cons " + f.slice(V.length), JSON.stringify(mine) === JSON.stringify((p.proof ?? []).map((x) => hx(b64(x)))));
}

// ---- 4. Self-consistency, edge sizes, odd-promotion equivalence ----
const mk = (n) => Array.from({ length: n }, (_, i) => A.leafHash(A.utf8("leaf-" + i)));
for (const n of [0, 1, 2, 3, 7, 8, 9]) {
  const lh = mk(n), root = A.mthFromLeafHashes(lh);
  t("edge-sizes", `n=${n} odd-promotion == RFC split`, A.bytesEqual(root, A.rootByOddPromotion(lh)));
  for (let m = 0; m < n; m++) t("edge-sizes", `n=${n} incl m=${m}`, A.verifyInclusion(m, n, lh[m], A.inclusionProof(lh, m), root));
  for (let m = 1; m <= n; m++) t("edge-sizes", `n=${n} cons m=${m}`, A.verifyConsistency(m, n, A.mthFromLeafHashes(lh.slice(0, m)), root, A.consistencyProof(lh, m)));
}
t("edge-sizes", "n=1 root == leaf hash", A.bytesEqual(A.mthFromLeafHashes(mk(1)), mk(1)[0]));
t("edge-sizes", "n=0 inclusion rejected", A.verifyInclusion(0, 0, mk(1)[0], [], A.mthFromLeafHashes([])) === false);
t("edge-sizes", "consistency from size 0 rejected", A.verifyConsistency(0, 3, A.mthFromLeafHashes([]), A.mthFromLeafHashes(mk(3)), []) === false);
{ let bad = 0; for (let n = 0; n <= 300; n++) { const lh = mk(n); if (!A.bytesEqual(A.mthFromLeafHashes(lh), A.rootByOddPromotion(lh))) bad++; }
  t("odd-promotion", "RFC split == odd promotion for n=0..300", bad === 0); }
{ let bad = 0; for (let n = 1; n <= 64; n++) { const lh = mk(n), r = A.mthFromLeafHashes(lh);
    for (let m = 0; m < n; m++) if (!A.verifyInclusion(m, n, lh[m], A.inclusionProof(lh, m), r)) bad++;
    for (let m = 1; m <= n; m++) if (!A.verifyConsistency(m, n, A.mthFromLeafHashes(lh.slice(0, m)), r, A.consistencyProof(lh, m))) bad++; }
  t("exhaustive", "all inclusion+consistency proofs n<=64", bad === 0); }

// ---- 5. Tamper tests ----
{
  const n = 9, lh = mk(n), root = A.mthFromLeafHashes(lh), m = 5, pr = A.inclusionProof(lh, m);
  const flip = (b, i) => { const c = b.slice(); c[i >> 3] ^= 1 << (i & 7); return c; };
  let leafBits = 0, proofBits = 0, rootBits = 0;
  for (let i = 0; i < 256; i++) {
    if (!A.verifyInclusion(m, n, flip(lh[m], i), pr, root)) leafBits++;
    if (!A.verifyInclusion(m, n, lh[m], pr, flip(root, i))) rootBits++;
    for (let j = 0; j < pr.length; j++) if (!A.verifyInclusion(m, n, lh[m], pr.map((x, k) => (k === j ? flip(x, i) : x)), root)) proofBits++;
  }
  t("tamper", "every leaf bit flip rejected", leafBits === 256);
  t("tamper", "every root bit flip rejected", rootBits === 256);
  t("tamper", "every proof bit flip rejected", proofBits === 256 * pr.length);
  t("tamper", "wrong index rejected", !A.verifyInclusion(4, n, lh[m], pr, root));
  // NOTE: size n+1 (=10) has the same path shape as 9, so the proof "verifies" against R9:
  // inclusion proofs do not bind tree size by themselves — the verifier MUST take size
  // from the anchored memo (i=..-to), never from the prover. Shape-changing sizes fail:
  t("tamper", "same-shape size n+1 is NOT detected by proof alone (documented)", A.verifyInclusion(m, n + 1, lh[m], pr, root) === true);
  t("tamper", "shape-changing wrong size rejected", !A.verifyInclusion(m, 8, lh[m], pr, root) && !A.verifyInclusion(m, 17, lh[m], pr, root));
  t("tamper", "extra proof node rejected", !A.verifyInclusion(m, n, lh[m], [...pr, lh[0]], root));
  t("tamper", "missing proof node rejected", !A.verifyInclusion(m, n, lh[m], pr.slice(0, -1), root));
  t("tamper", "reordered proof rejected", !A.verifyInclusion(m, n, lh[m], [...pr].reverse(), root));
  t("tamper", "31-byte hash rejected", !A.verifyInclusion(m, n, lh[m].slice(1), pr, root));
  const cp = A.consistencyProof(lh, 4), r4 = A.mthFromLeafHashes(lh.slice(0, 4));
  t("tamper", "consistency ok baseline", A.verifyConsistency(4, n, r4, root, cp));
  t("tamper", "consistency with rewritten history rejected", !A.verifyConsistency(4, n, A.mthFromLeafHashes(mk(4).map((x, i) => (i === 2 ? lh[3] : x))), root, cp));
  t("tamper", "consistency size1==size2 non-empty proof rejected", !A.verifyConsistency(n, n, root, root, [lh[0]]));
  // domain separation: a 64-byte leaf equal to l||r must not hash like the node
  t("tamper", "leaf/node domain separation", !A.bytesEqual(A.leafHash(new Uint8Array([...lh[0], ...lh[1]])), A.nodeHash(lh[0], lh[1])));
}

// ---- 6. RFC 8785 JCS vectors (cyberphone/json-canonicalization) ----
for (const f of readdirSync(join(V, "jcs", "input"))) {
  const input = readFileSync(join(V, "jcs", "input", f), "utf8");
  const want = readFileSync(join(V, "jcs", "output", f), "utf8").replace(/\n$/, "");
  t("jcs-rfc8785", f, A.jcs(JSON.parse(input)) === want);
}
t("jcs-rfc8785", "rejects NaN", (() => { try { A.jcs({ a: NaN }); return false; } catch { return true; } })());
t("jcs-rfc8785", "rejects lone surrogate", (() => { try { A.jcs({ a: "\ud800" }); return false; } catch { return true; } })());
t("jcs-rfc8785", "rejects undefined", (() => { try { A.jcs({ a: undefined }); return false; } catch { return true; } })());

// ---- 7. Compatibility with the live UVIX-RI-1.0 chain (Truffle snapshot) ----
const snap = readFileSync(join(V, "uvix-chain-snapshot-2026-10-28.jsonl"), "utf8").split("\n").filter(Boolean).map(JSON.parse);
const truffleCanon = (v) => v === null || typeof v !== "object" ? JSON.stringify(v) : Array.isArray(v) ? "[" + v.map(truffleCanon).join(",") + "]" : "{" + Object.keys(v).sort().map((k) => JSON.stringify(k) + ":" + truffleCanon(v[k])).join(",") + "}";
t("ri1-compat", "snapshot chain verifies (" + snap.length + " entries)", A.verifyChainRI1(snap).ok);
snap.forEach((e) => t("ri1-compat", "jcs == Truffle canon, seq " + e.seq, A.jcs({ node: e.node, prevHash: e.prevHash, seq: e.seq, text: e.text, ts: e.ts }) === truffleCanon({ node: e.node, prevHash: e.prevHash, seq: e.seq, text: e.text, ts: e.ts })));
{ const bad = snap.map((e) => ({ ...e })); bad[1].text += " "; t("ri1-compat", "edited text detected", !A.verifyChainRI1(bad).ok); }

// ---- 8. Memo format ----
const ROOT_EX = A.merkleRoot(LEAVES); // 8-leaf reference root 5dc9...4328
const EX = { cluster: "mainnet", node: "muse", wStart: 1794225600, wEnd: 1794247200, from: 6, to: 8, root: ROOT_EX, prev: A.sha256(A.utf8("example previous anchor link")) };
const memo = A.encodeMemo(EX);
console.log("EXAMPLE MEMO:", memo);
console.log("EXAMPLE MEMO BYTES:", A.utf8(memo).length);
t("memo", "round trip", JSON.stringify(A.decodeMemo(memo)) === JSON.stringify({ version: "uvix-anchor/1", cluster: "mainnet", node: "muse", wStart: EX.wStart, wEnd: EX.wEnd, from: 6, to: 8, root: hx(ROOT_EX), prev: hx(EX.prev) }));
const maxMemo = A.encodeMemo({ ...EX, node: "a".repeat(32), cluster: "mainnet", wStart: 999999972000, wEnd: 999999993600, from: 999999999999998, to: 999999999999999 });
t("memo", "worst-case length == 257 (" + A.utf8(maxMemo).length + ")", A.utf8(maxMemo).length === 257);
const rej = (s) => { try { A.decodeMemo(s); return false; } catch { return true; } };
  t("memo", "rejects > 272 bytes", rej(maxMemo + "x".repeat(20)));
t("memo", "rejects uppercase hex", rej(memo.replace(/r=([0-9a-f]{4})/, (m, g) => "r=" + g.toUpperCase())));
t("memo", "rejects trailing field", rej(memo + "|x=1"));
t("memo", "rejects trailing newline", rej(memo + "\n"));
t("memo", "rejects space", rej(memo.replace("|node=", "| node=")));
t("memo", "rejects other version", rej(memo.replace("/1|", "/3|")));
t("memo", "accepts uvix-anchor/2", !rej(memo.replace("/1|", "/2|")));
t("memo", "rejects misaligned window", rej(memo.replace("w=1794225600-1794247200", "w=1794225601-1794247201")));
t("memo", "rejects 12h window", rej(memo.replace("w=1794225600-1794247200", "w=1794225600-1794268800")));
t("memo", "rejects from>to", rej(memo.replace("i=6-8", "i=9-8")));
t("memo", "rejects to=0", rej(memo.replace("i=6-8", "i=0-0")));
t("memo", "rejects leading zero", rej(memo.replace("i=6-8", "i=06-8")));
t("memo", "rejects old TUF format", rej("UVIX-ROOT " + hx(ROOT_EX) + " n=8"));
t("memo", "rejects old script format", rej("uvix:memo:v1:" + hx(ROOT_EX)));
t("memo", "rejects old Truffle format", rej("leaksnipe-anchor-v1|rules=" + "0".repeat(64)));

// ---- 9. End-to-end anchors over the real snapshot ----
{
  const node = snap[0].node, cluster = "devnet";
  const w0 = A.windowOf(snap[0].ts), wLast = A.windowOf(snap[snap.length - 1].ts);
  const memos = []; let prevAnchor = null, heartbeats = 0;
  for (let end = w0.end; end <= wLast.end + A.WINDOW_SEC; end += A.WINDOW_SEC) {
    const a = A.buildAnchor({ entries: snap, cluster, node, windowEndSec: end, prevAnchor });
    if (a.skipped) continue;
    if (a.heartbeat) heartbeats++;
    memos.push(a.memo); prevAnchor = { memo: a.memo, link: a.link };
  }
  const v = A.verifyAnchors({ entries: snap, memos, node, cluster });
  console.log(`E2E: ${memos.length} anchors over ${snap.length} real entries (${heartbeats} heartbeats); head link ${v.headLink}`);
  t("e2e", "anchors verify", v.ok && A.decodeMemo(memos.at(-1)).to === snap.length);
  t("e2e", "dropped anchor detected", memos.length < 2 || !A.verifyAnchors({ entries: snap, memos: [memos[0], ...memos.slice(2)], node, cluster }).ok);
  t("e2e", "reordered anchors detected", memos.length < 2 || !A.verifyAnchors({ entries: snap, memos: [memos[1], memos[0], ...memos.slice(2)], node, cluster }).ok);
  const ed = snap.map((e) => ({ ...e })); ed[0].text = ed[0].text.replace("live", "LIVE");
  t("e2e", "edited entry text detected", !A.verifyAnchors({ entries: ed, memos, node, cluster }).ok);
  const rehashed = ed.reduce((acc, e, i) => { const x = { ...e, prevHash: i ? acc[i - 1].hash : "GENESIS" }; x.hash = A.entryHashRI1(x); acc.push(x); return acc; }, []);
  t("e2e", "fully re-hashed forged chain detected by anchors", !A.verifyAnchors({ entries: rehashed, memos, node, cluster }).ok);
  t("e2e", "wrong node rejected", !A.verifyAnchors({ entries: snap, memos, node: "tuf", cluster }).ok);
  t("e2e", "wrong cluster rejected", !A.verifyAnchors({ entries: snap, memos, node, cluster: "mainnet" }).ok);
  t("e2e", "truncated log detected", !A.verifyAnchors({ entries: snap.slice(0, -1), memos, node, cluster }).ok);
  t("e2e", "empty tree never anchored", A.buildAnchor({ entries: snap, cluster, node, windowEndSec: w0.start }).skipped === true);
  t("e2e", "non-monotonic ts refused", (() => { try { A.treeSizeAtWindowEnd([{ ts: 5 }, { ts: 4 }], 10); return false; } catch { return true; } })());
}

// ---- summary ----
console.log("\nGROUP RESULTS");
for (const [g, r] of Object.entries(groups)) console.log(`  ${g.padEnd(24)} pass ${r.pass}  fail ${r.fail}`);
console.log(`\nTOTAL: ${pass} passed, ${fail} failed; documented deviations: ${deviations.length} ${deviations.join(", ")}`);
if (fail) { console.log("FAILURES:\n  " + fails.join("\n  ")); process.exit(1); }
