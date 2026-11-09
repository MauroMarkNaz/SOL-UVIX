#!/usr/bin/env python3
r"""
patch_global_cloudflare_mcp.py  -  CORRECTED version (rewritten 2026-11-09 from Mauro's review).

DEFAULT IS DRY-RUN. Nothing is written unless you pass --apply.
This script never deploys, never runs wrangler, never touches git history,
never signs or sends anything to any chain. Deploy + first on-chain memo
need Mauro's explicit go (see HANDOFF.md section 7).

Run (TUF, PowerShell):
    python patch_global_cloudflare_mcp.py                       # dry-run: report + previews
    python patch_global_cloudflare_mcp.py --apply               # only after Mauro reviewed the dry-run
Optional:
    --d1-line N                 pick the d1_query isWriteSql() call nearest line N (if >1 call)
    --r2-binding NAME --r2-bucket BUCKET   add the R2 binding to wrangler.json (Mauro's call; skipped if omitted)
    --allow-dirty               skip the "git working tree must be clean" guard (backups still made)
    --copy PATH (repeatable)    override the copy targets list below

Every step prints exactly one of:
    MATCHED   edit found exactly where expected and will be / was applied
    SKIPPED   already applied (idempotent) or optional and not requested
    MANUAL    must be done by hand; script shows where
    MISSING   anchor not found / ambiguous -> the whole run ABORTS, nothing written
"""
import argparse, datetime, difflib, json, os, re, shutil, subprocess, sys, tempfile

# ----------------------------------------------------------------- paths ----
CORE     = r"G:\LeakSnipe\mcp-server\src\lib\uvix-core.js"
WORKER   = r"G:\LeakSnipe\mcp-server\src\mcp-worker.js"
WRANGLER = r"G:\WECRYP\cloudflare\cloudflare-mcp-d1-connector\wrangler.json"
# CONFIRM these three before --apply (paths reported by Antigravity, base dirs not verified):
COPIES = [
    r"G:\WECRYP\cloudflare\shared\uvix-core.js",
    r"G:\WECRYP\cloudflare\cloudflare-mcp-d1-connector\src\uvix-core.js",
    r"G:\WECRYP\cloudflare\uvix-edge-router\src\uvix-core.js",
]
# The ONLY divergence a copy may have from CORE (pre-patch): the d1-connector's label line.
ALLOWED_COPY_DIVERGENCE = {
    "cloudflare-mcp-d1-connector": re.compile(r"""label\s*:\s*["']truffle["']"""),
}

# ---------------------------------------------------------- JS to insert ----
IS_READ_ONLY_SQL_JS = r'''
// isReadOnlySql: ALLOWLIST replacement for the bypassable isWriteSql prefix denylist.
// Fail-closed: anything it cannot prove read-only is rejected. Real enforcement
// still belongs in a read-only D1 credential/binding; this is defence in depth.
function isReadOnlySql(sql) {
  if (typeof sql !== "string") return false;
  let s = sql.trim();
  if (!s) return false;
  if (s.includes("--") || s.includes("/*") || s.includes("*/")) return false; // no comments at all (they hide payloads)
  s = s.replace(/;\s*$/, "");                 // one trailing semicolon is tolerated
  if (s.includes(";")) return false;          // stacked statements
  const u = s.toUpperCase();
  if (!/^(SELECT|WITH|EXPLAIN)\b/.test(u)) return false;
  if (/\b(INSERT|UPDATE|DELETE|REPLACE|UPSERT|MERGE|DROP|ALTER|CREATE|ATTACH|DETACH|PRAGMA|VACUUM|REINDEX|ANALYZE|TRUNCATE|GRANT|REVOKE|SAVEPOINT|RELEASE|BEGIN|COMMIT|ROLLBACK|LOAD_EXTENSION)\b/.test(u)) return false;
  return true;
}
'''

ANNOT_RW_JS = r'''
// MCP tool annotations are HINTS for clients, not enforcement. (CONFIRM values vs original script.)
const RW_ANNOT = Object.freeze({ readOnlyHint: false, destructiveHint: false, idempotentHint: false, openWorldHint: true });
'''
ANNOT_AI_JS = r'''
const AI_ANNOT = Object.freeze({ readOnlyHint: true, destructiveHint: false, idempotentHint: false, openWorldHint: true });
'''

# Workers-side anchoring helpers. Byte-identical semantics to uvix-anchor.mjs
# (tested on the box against the same vectors - see HANDOFF.md section 5).
ANCHOR_HELPERS_JS = r'''
// ---- UVIX anchoring helpers: uvix-anchor/1 (SHA-256) & uvix-anchor/2 (BLAKE3). Inserted by patch_global_cloudflare_mcp.py ----
// Never signs or sends: produces memo TEXT only. Sending is a separate, Mauro-approved step.
const UVIX_MEMO_PROGRAM_ID = "MemoSq4gqABAXKb96qnH8TysNcWxMyWCqXgDLGmfcHr";
const UVIX_BASE_FEE_LAMPORTS = 5000; // per signature, solana.com/docs/core/fees
const UVIX_WINDOW_SEC = 21600;
const UVIX_MEMO_RE = /^uvix-anchor\/(1|2)\|c=(mainnet|devnet)\|node=([a-z0-9-]{1,32})\|w=(0|[1-9][0-9]{0,11})-(0|[1-9][0-9]{0,11})\|i=(0|[1-9][0-9]{0,14})-(0|[1-9][0-9]{0,14})\|r=([0-9a-f]{64})\|p=([0-9a-f]{64})$/;

function uvixHexToBytes(h) {
  if (typeof h !== "string" || !/^([0-9a-f]{2})*$/.test(h)) throw new Error("bad hex (lowercase, even length)");
  const out = new Uint8Array(h.length / 2);
  for (let i = 0; i < out.length; i++) out[i] = parseInt(h.slice(2 * i, 2 * i + 2), 16);
  return out;
}
function uvixBytesToHex(b) { return Array.from(b, (x) => x.toString(16).padStart(2, "0")).join(""); }
async function sha256Bytes(...parts) {
  let len = 0; for (const p of parts) len += p.length;
  const buf = new Uint8Array(len); let o = 0;
  for (const p of parts) { buf.set(p, o); o += p.length; }
  return new Uint8Array(await crypto.subtle.digest("SHA-256", buf));
}

// Pure JS BLAKE3 implementation for Workers/Node
const B3_IV = new Uint32Array([0x6a09e667, 0xbb67ae85, 0x3c6ef372, 0xa54ff53a, 0x510e527f, 0x9b05688c, 0x1f83d9ab, 0x5be0cd19]);
const B3_PERM = [2, 6, 3, 10, 7, 0, 4, 13, 1, 11, 12, 5, 9, 14, 15, 8];
function b3Rotr(w, r) { return (w >>> r) | (w << (32 - r)); }
function b3G(s, a, b, c, d, mx, my) {
  s[a] = (s[a] + s[b] + mx) | 0; s[d] = b3Rotr(s[d] ^ s[a], 16);
  s[c] = (s[c] + s[d]) | 0;      s[b] = b3Rotr(s[b] ^ s[c], 12);
  s[a] = (s[a] + s[b] + my) | 0; s[d] = b3Rotr(s[d] ^ s[a], 8);
  s[c] = (s[c] + s[d]) | 0;      s[b] = b3Rotr(s[b] ^ s[c], 7);
}
function b3Round(s, m) {
  b3G(s, 0, 4, 8, 12, m[0], m[1]); b3G(s, 1, 5, 9, 13, m[2], m[3]);
  b3G(s, 2, 6, 10, 14, m[4], m[5]); b3G(s, 3, 7, 11, 15, m[6], m[7]);
  b3G(s, 0, 5, 10, 15, m[8], m[9]); b3G(s, 1, 6, 11, 12, m[10], m[11]);
  b3G(s, 2, 7, 8, 13, m[12], m[13]); b3G(s, 3, 4, 9, 14, m[14], m[15]);
}
function b3Compress(cv, block, blockLen, counter, flags) {
  const s = new Uint32Array(16); s.set(cv, 0); s.set(B3_IV, 8);
  s[12] = counter & 0xffffffff; s[13] = (counter / 0x100000000) & 0xffffffff;
  s[14] = blockLen; s[15] = flags;
  let m = new Uint32Array(16);
  const v = new DataView(block.buffer, block.byteOffset, block.byteLength);
  for (let i = 0; i < 16; i++) m[i] = i * 4 < blockLen ? v.getUint32(i * 4, true) : 0;
  for (let r = 0; r < 7; r++) {
    b3Round(s, m);
    const n = new Uint32Array(16);
    for (let i = 0; i < 16; i++) n[i] = m[B3_PERM[i]];
    m = n;
  }
  const out = new Uint32Array(8);
  for (let i = 0; i < 8; i++) out[i] = s[i] ^ s[i + 8];
  return out;
}
function blake3Bytes(input) {
  let b = typeof input === "string" ? new TextEncoder().encode(input) : (input instanceof Uint8Array ? input : new Uint8Array(input));
  if (b.length === 0) {
    const cv = b3Compress(B3_IV, new Uint8Array(64), 0, 0, 3);
    const out = new Uint8Array(32); const dv = new DataView(out.buffer);
    for (let i = 0; i < 8; i++) dv.setUint32(i * 4, cv[i], true);
    return out;
  }
  const chunkCount = Math.ceil(b.length / 1024) || 1;
  function hashChunk(cBytes, cIdx, isRoot) {
    let cv = B3_IV;
    const bCount = Math.ceil(cBytes.length / 64) || 1;
    for (let i = 0; i < bCount; i++) {
      const st = i * 64, en = Math.min(st + 64, cBytes.length);
      const blk = new Uint8Array(64); blk.set(cBytes.subarray(st, en));
      let f = 0;
      if (i === 0) f |= 1;
      if (i === bCount - 1) f |= 2;
      if (isRoot && i === bCount - 1) f |= 8;
      cv = b3Compress(cv, blk, en - st, cIdx, f);
    }
    const out = new Uint8Array(32); const dv = new DataView(out.buffer);
    for (let i = 0; i < 8; i++) dv.setUint32(i * 4, cv[i], true);
    return out;
  }
  if (chunkCount === 1) return hashChunk(b, 0, true);
  let cvs = [];
  for (let c = 0; c < chunkCount; c++) {
    cvs.push(hashChunk(b.subarray(c * 1024, Math.min((c + 1) * 1024, b.length)), c, false));
  }
  while (cvs.length > 1) {
    const next = [];
    for (let i = 0; i < cvs.length; i += 2) {
      if (i + 1 < cvs.length) {
        const isRoot = (cvs.length === 2);
        const blk = new Uint8Array(64); blk.set(cvs[i], 0); blk.set(cvs[i + 1], 32);
        const cv = b3Compress(B3_IV, blk, 64, 0, 4 | (isRoot ? 8 : 0));
        const out = new Uint8Array(32); const dv = new DataView(out.buffer);
        for (let j = 0; j < 8; j++) dv.setUint32(j * 4, cv[j], true);
        next.push(out);
      } else { next.push(cvs[i]); }
    }
    cvs = next;
  }
  return cvs[0];
}

// entryHashesHex: UVIX-RI-1.0 entry hashes (64 lowercase hex) in seq order.
// leaf = SHA256(0x00 || raw32(entry.hash)); node = SHA256(0x01 || L || R); split at largest power of 2 < n.
async function computeRfc9162MerkleRoot(entryHashesHex, version = "uvix-anchor/1") {
  if (!Array.isArray(entryHashesHex)) throw new Error("entry_hashes must be an array");
  const isBlake3 = (version === "uvix-anchor/2");
  const leaves = [];
  for (const h of entryHashesHex) {
    if (typeof h !== "string" || !/^[0-9a-f]{64}$/.test(h)) throw new Error("each entry hash must be 64 lowercase hex");
    const raw = uvixHexToBytes(h);
    if (isBlake3) {
      const d = new Uint8Array(1 + raw.length); d[0] = 0x00; d.set(raw, 1);
      leaves.push(blake3Bytes(d));
    } else {
      leaves.push(await sha256Bytes(Uint8Array.of(0x00), raw));
    }
  }
  const mth = async (l) => {
    if (l.length === 0) return isBlake3 ? blake3Bytes(new Uint8Array(0)) : sha256Bytes(new Uint8Array(0));
    if (l.length === 1) return l[0];
    let k = 1; while (k * 2 < l.length) k *= 2;
    const left = await mth(l.slice(0, k)), right = await mth(l.slice(k));
    if (isBlake3) {
      const d = new Uint8Array(1 + left.length + right.length); d[0] = 0x01; d.set(left, 1); d.set(right, 1 + left.length);
      return blake3Bytes(d);
    }
    return sha256Bytes(Uint8Array.of(0x01), left, right);
  };
  return uvixBytesToHex(await mth(leaves));
}
// Backwards compatibility alias
const computeRfc6962MerkleRoot = computeRfc9162MerkleRoot;


function decodeUvixAnchorMemo(s) {
  if (typeof s !== "string") throw new Error("memo must be a string");
  if (new TextEncoder().encode(s).length > 272) throw new Error("memo too long");
  const m = UVIX_MEMO_RE.exec(s);
  if (!m) throw new Error("memo does not match uvix-anchor grammar");
  const f = { version: "uvix-anchor/" + m[1], cluster: m[2], node: m[3], wStart: +m[4], wEnd: +m[5], from: +m[6], to: +m[7], root: m[8], prev: m[9] };
  if (f.wEnd - f.wStart !== UVIX_WINDOW_SEC || f.wStart % UVIX_WINDOW_SEC !== 0) throw new Error("window must be one UTC-aligned 6h window");
  if (!(f.from <= f.to) || f.to < 1) throw new Error("need from <= to and to >= 1");
  return f;
}
function encodeUvixAnchorMemo({ version = "uvix-anchor/1", cluster, node, wStart, wEnd, from, to, root, prev }) {
  if (version !== "uvix-anchor/1" && version !== "uvix-anchor/2") throw new Error("version must be uvix-anchor/1 or uvix-anchor/2");
  const s = `${version}|c=${cluster}|node=${node}|w=${wStart}-${wEnd}|i=${from}-${to}|r=${root}|p=${prev}`;
  decodeUvixAnchorMemo(s);
  return s;
}
async function uvixAnchorLink(prevLinkHex, memo, version = "uvix-anchor/1") {
  if (version === "uvix-anchor/2") {
    const rawPrev = uvixHexToBytes(prevLinkHex);
    const memoBytes = new TextEncoder().encode(memo);
    const d = new Uint8Array(1 + rawPrev.length + memoBytes.length);
    d[0] = 0x02; d.set(rawPrev, 1); d.set(memoBytes, 1 + rawPrev.length);
    return uvixBytesToHex(blake3Bytes(d));
  }
  return uvixBytesToHex(await sha256Bytes(Uint8Array.of(0x02), uvixHexToBytes(prevLinkHex), new TextEncoder().encode(memo)));
}
// MCP handler: builds (does NOT send) the next anchor memo. Errors on any missing input -
// never substitutes Date.now() or defaults for data that must be committed.
async function handleUvixAnchorMemo(args) {
  const a = args || {};
  const need = ["cluster", "node", "window_end", "from", "entry_hashes", "prev_link"];
  const missing = need.filter((k) => a[k] === undefined || a[k] === null || a[k] === "");
  if (missing.length) throw new Error("uvix_anchor_memo: missing required input(s): " + missing.join(", "));
  const wEnd = Number(a.window_end), from = Number(a.from);
  if (!Number.isSafeInteger(wEnd) || !Number.isSafeInteger(from)) throw new Error("window_end and from must be integers");
  if (!/^[0-9a-f]{64}$/.test(a.prev_link)) throw new Error("prev_link must be 64 lowercase hex (64 zeros for the first anchor)");
  const version = a.version || "uvix-anchor/1";
  if (version !== "uvix-anchor/1" && version !== "uvix-anchor/2") throw new Error("version must be uvix-anchor/1 or uvix-anchor/2");
  const root = await computeRfc9162MerkleRoot(a.entry_hashes, version);
  const memo = encodeUvixAnchorMemo({ version, cluster: a.cluster, node: a.node, wStart: wEnd - UVIX_WINDOW_SEC, wEnd, from, to: a.entry_hashes.length, root, prev: a.prev_link });
  return {
    memo, memo_bytes: new TextEncoder().encode(memo).length, root, tree_size: a.entry_hashes.length,
    anchor_link: await uvixAnchorLink(a.prev_link, memo, version),
    program_id: UVIX_MEMO_PROGRAM_ID, fee_lamports: UVIX_BASE_FEE_LAMPORTS,
    sent: false, note: "Memo text only. Not signed, not sent. Sending requires Mauro's explicit go.",
  };
}
// ---- end UVIX anchoring helpers ----
'''

# Patterns that must NOT survive in the patched sources (post-check).
FORBIDDEN = [
    (r"sol_reference_price", "hardcoded SOL price field"),
    (r"\b86\.6\d?\b", "hardcoded SOL price"),
    (r"usd_cost|cost_usd|\busd\s*:", "USD cost field in memo output (fee_lamports only)"),
    (r"uvix:memo:v1:", "legacy memo format (script)"),
    (r"UVIX-ROOT ", "legacy memo format (TUF)"),
    (r"leaksnipe-anchor-v1", "legacy memo format (Truffle)"),
    (r"sha256\w*\(\s*[^)]*Date\.now\(\)", "hashing Date.now() as a fallback"),
]

# ----------------------------------------------------------- machinery ----
RESULTS = []          # (step, status, detail)
def rec(step, status, detail=""):
    RESULTS.append((step, status, detail))
    print(f"  [{status:<7}] {step}: {detail}")

def line_of(text, idx): return text.count("\n", 0, idx) + 1

def read(path):
    with open(path, "r", encoding="utf-8", newline="") as f:
        return f.read()

def find_function_block(text, name):
    """Top-level `function name(...) { ... }` whose closing brace is at column 0."""
    m = re.compile(r"^(?:async\s+)?function\s+" + re.escape(name) + r"\s*\([^)]*\)\s*\{.*?^\}[^\n]*\n", re.M | re.S).search(text)
    return m

def step_is_read_only_sql(core):
    if re.search(r"\bfunction\s+isReadOnlySql\s*\(", core):
        rec("S1 isReadOnlySql", "SKIPPED", "already defined"); return core
    m = find_function_block(core, "isWriteSql")
    if not m:
        rec("S1 isReadOnlySql", "MISSING", "top-level `function isWriteSql(...)` block not found"); return core
    # optional esbuild `__name(isWriteSql, "isWriteSql");` line right after
    end = m.end()
    nm = re.compile(r"[ \t]*__name\(isWriteSql,[^\n]*\n").match(core, end)
    if nm: end = nm.end()
    rec("S1 isReadOnlySql", "MATCHED", f"insert after isWriteSql (ends line {line_of(core, end)})")
    return core[:end] + IS_READ_ONLY_SQL_JS + core[end:]          # <- FIX: keeps the rest of the file

def step_d1_check(core, d1_line):
    calls = [m for m in re.finditer(r"isWriteSql\(\s*([A-Za-z_$][\w$.]*)\s*\)", core)
             if not re.match(r"\s*\{", core[m.end():m.end()+3]) and "function" not in core[max(0, m.start()-10):m.start()]]
    if "!isReadOnlySql(" in core:
        rec("S2 d1_query check", "SKIPPED", "already uses !isReadOnlySql"); return core
    if not calls:
        rec("S2 d1_query check", "MISSING", "no isWriteSql(<var>) call found"); return core
    if len(calls) > 1:
        lines = [line_of(core, c.start()) for c in calls]
        if d1_line is None:
            rec("S2 d1_query check", "MISSING", f"{len(calls)} isWriteSql() calls at lines {lines}; rerun with --d1-line N"); return core
        calls = [min(calls, key=lambda c: abs(line_of(core, c.start()) - d1_line))]
        if abs(line_of(core, calls[0].start()) - d1_line) > 5:
            rec("S2 d1_query check", "MISSING", f"no call within 5 lines of --d1-line {d1_line} (calls at {lines})"); return core
    c = calls[0]
    pre = core[max(0, c.start()-1):c.start()]
    if pre == "!":
        rec("S2 d1_query check", "MISSING", f"line {line_of(core, c.start())}: call is negated (!isWriteSql) - fix by hand"); return core
    rec("S2 d1_query check", "MATCHED", f"line {line_of(core, c.start())}: isWriteSql({c.group(1)}) -> !isReadOnlySql({c.group(1)})")
    return core[:c.start()] + f"!isReadOnlySql({c.group(1)})" + core[c.end():]

def step_sha256hex_present(core):
    if re.search(r"(?:\bfunction\s+sha256Hex\s*\(|\b(?:const|let|var)\s+sha256Hex\s*=)", core):
        rec("S3 sha256Hex exists", "MATCHED", "found"); return
    rec("S3 sha256Hex exists", "MISSING", "sha256Hex not defined in uvix-core.js - existing handlers that call it would crash")

def insert_after_isreadonly(core, block, marker_re, step):
    if re.search(marker_re, core):
        rec(step, "SKIPPED", "already present"); return core
    m = find_function_block(core, "isReadOnlySql")
    if not m:
        rec(step, "MISSING", "isReadOnlySql block not found (S1 must succeed first)"); return core
    rec(step, "MATCHED", f"insert after isReadOnlySql (line {line_of(core, m.end())})")
    return core[:m.end()] + block + core[m.end():]

def step_inference_chat(core):
    m = re.search(r"""name\s*:\s*["']uvix_inference_chat["']""", core)
    if not m:
        rec("S7 uvix_inference_chat -> AI_ANNOT", "MISSING", "tool definition not found"); return core
    nxt = re.compile(r"""\bname\s*:\s*["']""").search(core, m.end())
    blk_end = nxt.start() if nxt else min(len(core), m.end() + 4000)
    blk = core[m.end():blk_end]
    if re.search(r"annotations\s*:\s*AI_ANNOT\b", blk):
        rec("S7 uvix_inference_chat -> AI_ANNOT", "SKIPPED", "already AI_ANNOT"); return core
    a = re.search(r"annotations\s*:\s*RW_ANNOT\b", blk)
    if a:
        s = m.end() + a.start(); e = m.end() + a.end()
        rec("S7 uvix_inference_chat -> AI_ANNOT", "MATCHED", f"line {line_of(core, s)}: RW_ANNOT -> AI_ANNOT")
        return core[:s] + "annotations: AI_ANNOT" + core[e:]
    if re.search(r"\bannotations\s*:", blk):
        rec("S7 uvix_inference_chat -> AI_ANNOT", "MISSING", f"line {line_of(core, m.start())}: has other annotations - edit by hand"); return core
    rec("S7 uvix_inference_chat -> AI_ANNOT", "MATCHED", f"line {line_of(core, m.start())}: add annotations: AI_ANNOT")
    return core[:m.end()] + ", annotations: AI_ANNOT" + core[m.end():]

def scan(label, text, pattern, status, why):
    hits = [line_of(text, x.start()) for x in re.finditer(pattern, text)]
    if hits: rec(label, status, f"{why} at lines {hits}")
    return hits

def wrangler_step(path, binding, bucket):
    step = "S10 wrangler.json R2 binding"
    if not (binding and bucket):
        rec(step, "SKIPPED", "no --r2-binding/--r2-bucket given (adding R2 is Mauro's call)"); return None
    raw = read(path)
    def no_dupes(pairs):
        keys = [k for k, _ in pairs]
        d = {k for k in keys if keys.count(k) > 1}
        if d: raise ValueError("duplicate JSON keys: " + ", ".join(sorted(d)))
        return dict(pairs)
    try:
        cfg = json.loads(raw, object_pairs_hook=no_dupes)
    except ValueError as e:
        rec(step, "MISSING", f"wrangler.json is not strict JSON ({e}). If it has // or /* */ comments or trailing commas, "
            f"add by hand: \"r2_buckets\": [{{\"binding\": \"{binding}\", \"bucket_name\": \"{bucket}\"}}] (merge into an existing r2_buckets array, never a second key)")
        return None
    r2 = cfg.get("r2_buckets", [])
    if not isinstance(r2, list):
        rec(step, "MISSING", "r2_buckets exists but is not a list"); return None
    for b in r2:
        if b.get("binding") == binding:
            if b.get("bucket_name") == bucket:
                rec(step, "SKIPPED", "binding already present"); return None
            rec(step, "MISSING", f"binding {binding} exists with a different bucket ({b.get('bucket_name')})"); return None
    r2.append({"binding": binding, "bucket_name": bucket})
    cfg["r2_buckets"] = r2
    new = json.dumps(cfg, indent=2, ensure_ascii=False) + "\n"
    json.loads(new)  # must round-trip
    rec(step, "MATCHED", f"append {binding} -> {bucket} (file re-serialised with indent=2; key order preserved)")
    return new

def copies_step(core_orig, core_new, targets):
    out = {}
    for t in targets:
        step = f"S11 copy -> {t}"
        if not os.path.exists(t):
            rec(step, "MISSING", "file not found (confirm path)"); continue
        cp = read(t)
        a, b = core_orig.splitlines(keepends=True), cp.splitlines(keepends=True)
        sm = difflib.SequenceMatcher(a=a, b=b, autojunk=False)
        diffs = [op for op in sm.get_opcodes() if op[0] != "equal"]
        if not diffs:
            rec(step, "MATCHED", "identical to pre-patch core; will receive patched core"); out[t] = core_new; continue
        allow = next((rx for key, rx in ALLOWED_COPY_DIVERGENCE.items() if key in t.replace("\\", "/")), None)
        if allow and len(diffs) == 1 and diffs[0][0] == "replace" and (diffs[0][2]-diffs[0][1]) == 1 and (diffs[0][4]-diffs[0][3]) == 1 \
                and allow.search(b[diffs[0][3]]):
            core_line, copy_line = a[diffs[0][1]], b[diffs[0][3]]
            if core_new.count(core_line) != 1:
                rec(step, "MISSING", "allowed label line can't be re-applied uniquely after patch"); continue
            rec(step, "MATCHED", f"only the allowed divergence ({copy_line.strip()[:60]}) - patched core + that line re-applied")
            out[t] = core_new.replace(core_line, copy_line, 1); continue
        sample = "".join(difflib.unified_diff(a, b, "core(pre-patch)", t, n=0))[:1500]
        rec(step, "MISSING", f"copy has diverged beyond the allowed label line ({len(diffs)} hunks) - reconcile by hand first:\n{sample}")
    return out

def git_clean(path):
    d = os.path.dirname(os.path.abspath(path))
    try:
        r = subprocess.run(["git", "-C", d, "status", "--porcelain", "--", os.path.basename(path)], capture_output=True, text=True, timeout=30)
    except Exception as e:
        return None, f"git not runnable ({e})"
    if r.returncode != 0: return None, "not a git repo"
    return (r.stdout.strip() == ""), r.stdout.strip()

def node_check(path):
    node = shutil.which("node")
    if not node: return None, "node not on PATH"
    r = subprocess.run([node, "--check", path], capture_output=True, text=True)
    return r.returncode == 0, (r.stderr or r.stdout).strip()[:800]

# ----------------------------------------------------------------- main ----
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--d1-line", type=int)
    ap.add_argument("--r2-binding"); ap.add_argument("--r2-bucket")
    ap.add_argument("--allow-dirty", action="store_true")
    ap.add_argument("--copy", action="append")
    ap.add_argument("--core", default=CORE); ap.add_argument("--worker", default=WORKER); ap.add_argument("--wrangler", default=WRANGLER)
    ap.add_argument("--preview-dir", default=os.path.join(os.getcwd(), "patch-preview"))
    args = ap.parse_args()
    targets = args.copy or COPIES
    mode = "APPLY" if args.apply else "DRY-RUN (no files changed; pass --apply to write)"
    print(f"patch_global_cloudflare_mcp.py  mode: {mode}\n")

    for p in (args.core, args.worker):
        if not os.path.exists(p):
            print(f"ABORT: {p} not found"); sys.exit(2)
    core0 = read(args.core); worker0 = read(args.worker)
    core = core0; worker = worker0

    print("uvix-core.js")
    core = step_d1_check(core, args.d1_line)   # first, so --d1-line refers to ORIGINAL line numbers
    core = step_is_read_only_sql(core)
    step_sha256hex_present(core)
    core = insert_after_isreadonly(core, ANCHOR_HELPERS_JS, r"\basync\s+function\s+computeRfc9162MerkleRoot\s*\(", "S4 anchoring helpers")
    core = insert_after_isreadonly(core, ANNOT_RW_JS, r"\b(?:const|let|var)\s+RW_ANNOT\b", "S5 RW_ANNOT")
    core = insert_after_isreadonly(core, ANNOT_AI_JS, r"\b(?:const|let|var)\s+AI_ANNOT\b", "S6 AI_ANNOT (independent of RW_ANNOT)")
    if re.search(r"\b(?:const|let|var)\s+AI_ANNOT\b", core):
        core = step_inference_chat(core)
    else:
        rec("S7 uvix_inference_chat -> AI_ANNOT", "MISSING", "AI_ANNOT not defined - refusing to reference it")

    print("\nmanual items (reported, not auto-edited)")
    for name, text in (("uvix-core.js", core), ("mcp-worker.js", worker)):
        scan(f"S8 memo handler [{name}]", text, r"uvix:memo:v1:|UVIX-ROOT |leaksnipe-anchor-v1|sol_reference_price|\b86\.6\d?\b",
             "MANUAL", "old memo handler: replace its body with `return handleUvixAnchorMemo(args)` and delete legacy fields")
        scan(f"S9 google_db_query [{name}]", text, r"google_db_query", "MANUAL", "remove tool definition + handler + dispatch case BY HAND")
    print("  [NOTE   ] S12: registration-loop and tools/list edits from your ORIGINAL script are NOT in this file "
          "(reviewer never had their text in machine-readable form). Re-apply them by hand or add Edit steps here, then rerun dry-run.")

    print("\nwrangler.json")
    wr_new = wrangler_step(args.wrangler, args.r2_binding, args.r2_bucket) if os.path.exists(args.wrangler) else rec("S10 wrangler.json", "MISSING", "not found")

    print("\ncopies")
    copies = copies_step(core0, core, targets)

    print("\npost-checks on patched text")
    for name, text in (("uvix-core.js", core), ("mcp-worker.js", worker)):
        for pat, why in FORBIDDEN:
            hits = [line_of(text, x.start()) for x in re.finditer(pat, text)]
            if hits: rec(f"POST {name}", "MANUAL", f"{why} still present at lines {hits}")
    d = re.search(r"\b(?:const|let|var)\s+AI_ANNOT\b", core); u = re.search(r"""name\s*:\s*["']uvix_inference_chat["']""", core)
    if d and u and d.start() > u.start():
        rec("POST AI_ANNOT order", "MISSING", f"AI_ANNOT defined at line {line_of(core, d.start())} AFTER its use at line {line_of(core, u.start())} (TDZ ReferenceError)")
    os.makedirs(args.preview_dir, exist_ok=True)
    pv = os.path.join(args.preview_dir, "uvix-core.patched.js")
    with open(pv, "w", encoding="utf-8", newline="") as f: f.write(core)
    ok, msg = node_check(pv)
    if ok is None: rec("POST node --check", "MANUAL", msg)
    elif ok: rec("POST node --check", "MATCHED", "patched uvix-core.js parses")
    else: rec("POST node --check", "MISSING", "patched uvix-core.js does NOT parse: " + msg)
    with open(os.path.join(args.preview_dir, "uvix-core.diff"), "w", encoding="utf-8") as f:
        f.writelines(difflib.unified_diff(core0.splitlines(True), core.splitlines(True), args.core, args.core + " (patched)"))
    print(f"  previews + diff written to {args.preview_dir}")

    missing = [r for r in RESULTS if r[1] == "MISSING"]
    manual = [r for r in RESULTS if r[1] == "MANUAL"]
    print(f"\nSUMMARY: {sum(r[1]=='MATCHED' for r in RESULTS)} MATCHED, {sum(r[1]=='SKIPPED' for r in RESULTS)} SKIPPED, "
          f"{len(manual)} MANUAL, {len(missing)} MISSING")
    if missing:
        print("ABORT: at least one MISSING. Nothing was written."); sys.exit(1)
    if not args.apply:
        print("Dry-run complete. Review patch-preview/uvix-core.diff, then rerun with --apply."); return

    # ---- APPLY: guard, back up, then write everything atomically ----
    writes = {args.core: core}
    if wr_new is not None: writes[args.wrangler] = wr_new
    writes.update(copies)
    writes = {p: t for p, t in writes.items() if read(p) != t}
    if not args.allow_dirty:
        for p in writes:
            clean, info = git_clean(p)
            if clean is False:
                print(f"ABORT: {p} has uncommitted changes:\n{info}\nCommit first (or --allow-dirty)."); sys.exit(1)
            if clean is None:
                print(f"ABORT: cannot confirm git state for {p} ({info}). Commit/backup first, or --allow-dirty."); sys.exit(1)
    stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    for p in writes:
        bak = f"{p}.bak-{stamp}"
        shutil.copy2(p, bak); print(f"  backup {bak}")
    for p, t in writes.items():
        fd, tmp = tempfile.mkstemp(dir=os.path.dirname(p), prefix=".patchtmp-")
        with os.fdopen(fd, "w", encoding="utf-8", newline="") as f: f.write(t)
        os.replace(tmp, p); print(f"  wrote  {p}")
    print("APPLIED. Next: wrangler deploy --dry-run per worker (HANDOFF.md section 7). Do NOT deploy without Mauro's go.")

if __name__ == "__main__":
    main()
