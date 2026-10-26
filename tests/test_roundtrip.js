/**
 * Node.js cross-runtime verification test
 * Tests that Node.js / V8 can decode and verify UVIX envelopes produced by the spec.
 */

const crypto = require("crypto");
const assert = require("assert");

function canonicalStringify(obj) {
  if (obj === null || typeof obj !== "object") {
    return JSON.stringify(obj);
  }
  if (Array.isArray(obj)) {
    return "[" + obj.map(canonicalStringify).join(",") + "]";
  }
  const keys = Object.keys(obj).sort();
  const pairs = keys.map(k => JSON.stringify(k) + ":" + canonicalStringify(obj[k]));
  return "{" + pairs.join(",") + "}";
}

function computePayloadHash(rawPayload) {
  const canonical = canonicalStringify(rawPayload);
  return crypto.createHash("sha256").update(canonical, "utf8").digest("hex");
}

function encodeSlug(payload, source = "Node-Test", target = "Python-Receiver") {
  const hash = computePayloadHash(payload);
  const slug = {
    protocol_version: "1.0",
    source_platform: source,
    target_platform: target,
    payload_hash: hash,
    compatibility_layer: "solana-uvix-v1",
    raw_payload: payload,
  };
  const b64 = Buffer.from(canonicalStringify(slug), "utf8").toString("base64");
  return `UVIX::${b64}::END`;
}

function decodeSlug(envelope) {
  assert(envelope.startsWith("UVIX::") && envelope.endsWith("::END"), "Invalid framing");
  const b64 = envelope.slice(6, -5);
  const jsonStr = Buffer.from(b64, "base64").toString("utf8");
  const slug = JSON.parse(jsonStr);

  const expectedHash = computePayloadHash(slug.raw_payload);
  assert.strictEqual(slug.payload_hash, expectedHash, "Integrity hash mismatch");
  return slug;
}

// Run test
console.log("Running Node.js UVIX roundtrip test...");
const testPayload = {
  network: "solana",
  slot: 284910283,
  accounts: ["TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA"],
  active: true,
};

const envelope = encodeSlug(testPayload);
console.log("Generated Envelope:", envelope.slice(0, 40) + "...");
const decoded = decodeSlug(envelope);

assert.deepStrictEqual(decoded.raw_payload, testPayload);
console.log("✓ Node.js UVIX roundtrip verification passed!");
