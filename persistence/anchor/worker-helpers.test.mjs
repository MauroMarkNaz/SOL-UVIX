// Checks the JS the patcher INSERTS into uvix-core.js (WebCrypto, async) against uvix-anchor.mjs,
// and checks isReadOnlySql against known bypasses of the old isWriteSql denylist.
import { execFileSync } from "node:child_process";
import { readFileSync } from "node:fs";
import * as A from "./uvix-anchor.mjs";
const py = `import importlib.util,json;s=importlib.util.spec_from_file_location('p','patch_global_cloudflare_mcp.py');m=importlib.util.module_from_spec(s);s.loader.exec_module(m);print(json.dumps([m.IS_READ_ONLY_SQL_JS,m.ANCHOR_HELPERS_JS]))`;
const pyCmd = process.platform === "win32" ? "python" : "python3";
const [ROS, HELP] = JSON.parse(execFileSync(pyCmd, ["-c", py]).toString());
const H = new Function(ROS + HELP + "; return { isReadOnlySql, computeRfc9162MerkleRoot, encodeUvixAnchorMemo, decodeUvixAnchorMemo, uvixAnchorLink, handleUvixAnchorMemo };")();
let pass = 0, fail = 0; const t = (n, c) => { c ? pass++ : (fail++, console.log("FAIL " + n)); };
// roots: compare to node:crypto module for n = 0..40 over synthetic entry hashes
for (let n = 0; n <= 40; n++) {
  const hs = Array.from({ length: n }, (_, i) => A.toHex(A.sha256(A.utf8("e" + i))));
  t("root n=" + n, (await H.computeRfc9162MerkleRoot(hs)) === A.toHex(A.mthFromLeafHashes(hs.map((h) => A.leafHash(A.fromHex(h))))));
}
// real snapshot
const snap = readFileSync("vectors/uvix-chain-snapshot-2026-10-28.jsonl", "utf8").split("\n").filter(Boolean).map(JSON.parse);
t("snapshot root", (await H.computeRfc9162MerkleRoot(snap.map((e) => e.hash))) === "6d2e6dc12b3c783886f1cf964659214950362281f1f30f61532f76b56d05c52c");
// memo + link identical to module
const f = { cluster: "mainnet", node: "muse", wStart: 1794225600, wEnd: 1794247200, from: 6, to: 8, root: "5dc9da79a70659a9ad559cb701ded9a2ab9d823aad2f4960cfe370eff4604328", prev: "0".repeat(64) };
const m1 = H.encodeUvixAnchorMemo(f), m2 = A.encodeMemo(f);
t("memo identical", m1 === m2);
t("link identical", (await H.uvixAnchorLink(f.prev, m1)) === A.toHex(A.anchorLink(new Uint8Array(32), m2)));
// uvix-anchor/2 (BLAKE3) memo & handler
const f2 = { version: "uvix-anchor/2", cluster: "devnet", node: "muse", wStart: 1794225600, wEnd: 1794247200, from: 0, to: 4, root: "0".repeat(64), prev: "0".repeat(64) };
const m2_1 = H.encodeUvixAnchorMemo(f2), m2_2 = A.encodeMemo(f2);
t("uvix-anchor/2 memo identical", m2_1 === m2_2);
t("uvix-anchor/2 decode version", H.decodeUvixAnchorMemo(m2_1).version === "uvix-anchor/2");
const r2 = await H.handleUvixAnchorMemo({ version: "uvix-anchor/2", cluster: "devnet", node: "muse", window_end: 1794247200, from: 0, entry_hashes: snap.map((e) => e.hash), prev_link: "0".repeat(64) });
t("handler uvix-anchor/2 output", r2.memo.startsWith("uvix-anchor/2|") && r2.fee_lamports === 5000 && r2.sent === false);
// handler: errors on missing input, never falls back to Date.now()
for (const k of ["cluster", "node", "window_end", "from", "entry_hashes", "prev_link"]) {
  const args = { cluster: "devnet", node: "muse", window_end: 1794247200, from: 0, entry_hashes: snap.map((e) => e.hash), prev_link: "0".repeat(64) };
  delete args[k];
  let threw = false; try { await H.handleUvixAnchorMemo(args); } catch (e) { threw = /missing required/.test(e.message); }
  t("handler rejects missing " + k, threw);
}
const r = await H.handleUvixAnchorMemo({ cluster: "devnet", node: "muse", window_end: 1794247200, from: 0, entry_hashes: snap.map((e) => e.hash), prev_link: "0".repeat(64) });
t("handler output: fee_lamports only, sent=false, no usd", r.fee_lamports === 5000 && r.sent === false && !JSON.stringify(r).toLowerCase().includes("usd"));
t("handler memo decodes in module", A.decodeMemo(r.memo).to === 4);
// isReadOnlySql
const allow = ["SELECT 1", "select * from t where a = 'x'", "SELECT 1;", "  WITH x AS (SELECT 1) SELECT * FROM x", "EXPLAIN QUERY PLAN SELECT * FROM t", "SELECT * FROM t; "];
const deny = ["/* c */ DELETE FROM t", "-- c\nDROP TABLE t", "WITH x AS (SELECT 1) DELETE FROM t", "PRAGMA table_info(t)", "ATTACH DATABASE 'x' AS y",
  "SELECT 1; DROP TABLE t", "SELECT '--'; DROP TABLE t", "SELECT 1;\nDELETE FROM t", "INSERT INTO t VALUES(1)", "REPLACE INTO t VALUES(1)", "", "   ", null, 42,
  "WITH x AS (SELECT 1) INSERT INTO t SELECT * FROM x", "select 1 /* */", "VACUUM", "UPDATE t SET a=1", "CREATE TABLE t(a)", "SAVEPOINT a", "BEGIN"];
allow.forEach((q) => t("allow " + JSON.stringify(q), H.isReadOnlySql(q) === true));
deny.forEach((q) => t("deny " + JSON.stringify(q), H.isReadOnlySql(q) === false));
console.log(`WORKER-HELPERS TOTAL: ${pass} passed, ${fail} failed`);
process.exit(fail ? 1 : 0);
