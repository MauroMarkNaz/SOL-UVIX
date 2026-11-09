# UVIX-RI-1.0 — Wire Envelope and Integrity Protocol

| Field | Value |
|---|---|
| Status | Working Draft 0.1 |
| Date | 2026-11-07 |
| Applies to | `core/protocol/codec.py`, `sol_uvix/codec.py`, `tests/test_roundtrip.js`, `edge/worker.ts`, `persistence/uvix-solana-persistence.js` |

## Foreword

This document specifies the UVIX-RI-1.0 envelope: the canonical slug format,
integrity rule, and framing used for every claim that crosses a node boundary.
It is written in the style of an ISO/IEC standard so that independent
implementations in any runtime can check each other byte for byte. It claims no
standards body's authority; its authority is reproducibility.

Open decisions are recorded in Annex B. Nothing marked as a decision record is
normative until resolved.

## Introduction

Three languages check each other's work. A sender wraps a payload as a *slug*,
seals it with a SHA-256 integrity hash computed over a canonical JSON form, and
frames it as ASCII text. A receiver recomputes the hash from the same canonical
form and rejects anything malformed or mismatched before any further
processing. A hash proves integrity of the payload bytes; it does not by itself
authenticate a sender.

---

## 1. Scope

This document defines:

- the UVIX slug data model (§5);
- the canonical JSON serialization (§6);
- the payload integrity hash (§7);
- the envelope framing (§8);
- the encode and decode procedures (§9);
- the error model (§10);
- conformance requirements and test vectors (§11, Annex A).

Out of scope: key management, authentication and signatures, transport
bindings, the proof-of-history chain, the `compatibility_layer` value registry,
and any protocol version other than `1.0`.

## 2. Normative references

The following documents are indispensable for the application of this document:

- RFC 2119 / RFC 8174 — Key words for use in RFCs (MUST, MUST NOT, REQUIRED,
  SHALL, SHALL NOT, SHOULD, SHOULD NOT, RECOMMENDED, MAY, OPTIONAL).
- RFC 8259 — The JavaScript Object Notation (JSON) Data Interchange Format.
- RFC 8785 — JSON Canonicalization Scheme (JCS).
- RFC 9162 — Certificate Transparency Version 2.0 (CTv2), upgrading and
  replacing obsolete RFC 6962 for Merkle Tree Hashing.
- RFC 4648 §4 — The Base16, Base32, and Base64 Data Encodings (standard
  alphabet with padding).
- RFC 3629 — UTF-8, a transformation format of ISO 10646.
- FIPS 180-4 — Secure Hash Standard (SHA-256).

Informative: `README.md` §6 (The envelope: UVIX-RI-1.0) and White Paper
*UVIX: Origin and Interoperation Without Assimilation* (9 November 2026).

## 3. Terms and definitions

- **slug**: the six-field protocol object defined in §5.
- **raw payload**: the application data carried by a slug; the sole input to
  the integrity hash.
- **canonical JSON**: the deterministic serialization defined in §6.
- **payload hash**: the lowercase hexadecimal SHA-256 digest defined in §7.
- **envelope**: the framed ASCII text `UVIX::` + base64 + `::END` defined in §8.
- **encoder**: software that produces envelopes from payloads.
- **decoder**: software that parses envelopes and verifies integrity.
- **verify**: recomputation of the payload hash and comparison against the
  sealed value, failing closed on mismatch.

## 4. Conformance

A *conforming encoder* implements §5–§8 and the encode procedure in §9.
A *conforming decoder* implements §5–§8 and the decode procedure in §9.
An implementation MAY conform as an encoder only, a decoder only, or both.

Interoperability invariant (normative): for the same logical payload,
conforming implementations in different runtimes MUST produce the identical
canonical representation (§6) and the identical verification result (§9).
Anything weaker does not count as interoperable.

## 5. Slug data model

A slug is a JSON object with exactly the following required fields:

| Field | Type | Meaning |
|---|---|---|
| `protocol_version` | string | Protocol version. The only value defined by this document is `"1.0"`. |
| `source_platform` | string | Opaque sender identifier. |
| `target_platform` | string | Opaque recipient identifier. |
| `payload_hash` | string | Lowercase hex SHA-256 per §7. |
| `compatibility_layer` | string | Opaque layer tag. Observed values include `"solana-uvix-v1"` and `"neural-mesh-v1"`; no registry is defined in 1.0. |
| `raw_payload` | object | Application data. The sole hash input. |

Rules:

- R5.1: A conforming encoder MUST emit all six fields on the wire. Default
  values for the opaque strings are an implementation choice; the wire format
  has no defaults.
- R5.2: A conforming decoder MUST reject a slug missing any required field
  (format error, §10). A decoder MUST ignore unknown fields (forward
  compatibility).
- R5.3: A conforming encoder MUST emit `raw_payload` as a JSON object.
  Decoders MUST still apply integrity verification if a received `raw_payload`
  is of another type.
- R5.4: A conforming decoder MUST accept `protocol_version` `"1.0"`.
  Envelopes bearing any other version MUST be rejected unless the
  implementation explicitly supports that version (see DR-006).

## 6. Canonical JSON

The canonical form C(J) of a JSON value J is defined recursively:

- C6.1 (objects): `{` + members sorted by key in ascending order of Unicode
  scalar value, each rendered `string(key) + ":" + C(value)`, joined with `,`
  + `}`. No whitespace. Encoders MUST NOT emit duplicate keys (see DR-003
  for the sort-unit decision).
- C6.2 (arrays): elements in order, each rendered C(element), joined with `,`,
  wrapped in `[` `]`. No whitespace.
- C6.3 (strings): JSON string syntax with minimal escaping: `"`, `\`, and
  control characters (U+0000–U+001F) escaped; all other characters emitted as
  raw UTF-8 (see DR-001 — this rule is PROVISIONAL).
- C6.4 (numbers): integers in base 10 with no leading zeros and no `+`.
  Non-integer numbers use shortest round-trip decimal form; negative zero is
  rendered `0`; NaN and infinities MUST NOT be emitted (see DR-002 — this
  rule is PROVISIONAL).
- C6.5 (literals): `true`, `false`, `null` in lowercase.
- C6.6: The canonical form is encoded as UTF-8 octets (RFC 3629) before
  hashing or framing.

NOTE — C6.3 and C6.4 are provisional because the shipped Python and
JavaScript implementations disagree on them today (Annex B). ASCII-only
payloads with integer numbers are unaffected and fully normative.

## 7. Integrity

- R7.1: `payload_hash = lowercase_hex( SHA-256( UTF-8( C(raw_payload) ) ) )`,
  where C is the canonical form from §6.
- R7.2: The hash domain is the slug's `raw_payload` object and nothing else.
  Envelope metadata and `payload_hash` itself are outside the hash; the
  definition is not circular.
- R7.3: `payload_hash` MUST be 64 lowercase hexadecimal characters.

## 8. Envelope framing

- R8.1: An envelope is the ASCII text `UVIX::` + B + `::END`, where B is the
  RFC 4648 §4 standard-alphabet base64 encoding (with `=` padding) of the
  UTF-8 octets of C(slug), the canonical form of the complete six-field slug
  object.
- R8.2: A conforming decoder MUST remove leading and trailing ASCII
  whitespace (space, tab, CR, LF) before checking framing, then require the
  exact prefix `UVIX::` and suffix `::END`.
- R8.3: The base64 body MUST contain only characters of the standard alphabet
  plus up to two trailing `=` padding characters. Decoders MUST reject any
  other content as a format error (strict alphabet; see Annex C).

## 9. Procedures

### 9.1 Encode

Given application data P (a JSON object) and the four opaque/version strings:

1. Compute H = payload hash of P per §7.
2. Build the six-field slug object (§5) with `payload_hash` = H.
3. Serialize C(slug) per §6, UTF-8 encode, base64 encode, and frame per §8.

Invariant E1 (normative): an encoder MUST NOT emit an envelope whose sealed
`payload_hash` differs from the recomputation over the emitted `raw_payload`.
An encoder that accepts pre-built slug input MUST re-verify or recompute the
hash so that E1 holds (see DR-005).

### 9.2 Decode

Given input text T and a verification flag V (default: verify):

1. Reject non-string input (format error).
2. Strip surrounding ASCII whitespace; require exact `UVIX::` … `::END`
   framing (format error).
3. Base64-decode the body to an octet sequence using the strict alphabet
   (format error on any violation).
4. UTF-8-decode the octets to text (format error on invalid UTF-8).
   NOTE: decoders MUST decode base64 to bytes first; binary-string shortcuts
   corrupt multi-byte characters (see Annex C).
5. Parse the text as JSON (format error).
6. Require all six slug fields (format error on any missing field); ignore
   unknown fields.
7. Check `protocol_version` per R5.4 (format error).
8. If V is set: recompute the payload hash per §7 and compare against the
   sealed value; on mismatch raise an integrity error and return nothing
   (fail closed). If V is unset, return the slug without verification.

Rule D1: conforming decoders MUST verify by default; skipping verification
MUST require an explicit caller choice.

## 10. Error model

Two failure classes, one hierarchy:

| Condition | Class | Raised at decode step |
|---|---|---|
| Non-string input | format | 1 |
| Framing mismatch | format | 2 |
| Base64 alphabet/padding violation | format | 3 |
| Invalid UTF-8 | format | 4 |
| JSON parse failure | format | 5 |
| Missing required field | format | 6 |
| Unsupported `protocol_version` | format | 7 |
| Hash mismatch (V set) | **integrity** | 8 |
| Unsupported input type at encode | format | — (encode) |

- R10.1: Integrity failures MUST be distinguishable from format failures
  (distinct error types, e.g. `UVIXIntegrityError` vs `UVIXFormatError`
  under a common `UVIXError` base).
- R10.2: Evaluation order is framing → base64 → UTF-8 → JSON → shape →
  version → integrity. The first failure encountered determines the class.
- R10.3: New error cases MUST reuse this hierarchy; implementations MUST NOT
  invent parallel exception trees.

## 11. Interoperability verification

An implementation demonstrates conformance by:

1. Reproducing every normative vector in Annex A byte for byte (canonical
   form, hash, and envelope).
2. Cross-runtime check: decoding at least one Annex A envelope produced by a
   different runtime's implementation and obtaining a successful verification.
3. Failing closed on the negative cases in §10 (tampered payload → integrity
   error; bad framing → format error).

Annex A vectors were generated by executing the shipped Python implementation
and independently verified by executing the shipped JavaScript algorithm
(V1–V3: canonical forms identical, hashes identical, `VERIFY-OK`).

---

## Annex A (normative) — Test vectors

Vector parameters: `protocol_version` `"1.0"`, `source_platform` `"VectorGen"`,
`target_platform` `"VectorGen"`, `compatibility_layer` `"uvix-vectors-v1"`.
The envelope embeds the canonically serialized slug (keys sorted); decode the
base64 body to inspect it.

### A.1 Vector V1 — empty payload

Payload: `{}`

Canonical: `{}`

Hash: `44136fa355b3678a1146ad16f7e8649e94fb4fc21fe77e8310c060f61caaff8a`

Envelope:

```text
UVIX::eyJjb21wYXRpYmlsaXR5X2xheWVyIjoidXZpeC12ZWN0b3JzLXYxIiwicGF5bG9hZF9oYXNoIjoiNDQxMzZmYTM1NWIzNjc4YTExNDZhZDE2ZjdlODY0OWU5NGZiNGZjMjFmZTc3ZTgzMTBjMDYwZjYxY2FhZmY4YSIsInByb3RvY29sX3ZlcnNpb24iOiIxLjAiLCJyYXdfcGF5bG9hZCI6e30sInNvdXJjZV9wbGF0Zm9ybSI6IlZlY3RvckdlbiIsInRhcmdldF9wbGF0Zm9ybSI6IlZlY3RvckdlbiJ9::END
```

### A.2 Vector V2 — Solana slot snapshot

Payload (logical): `{"network":"solana","slot":284910283,"accounts":["TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA"],"active":true}`

Canonical: `{"accounts":["TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA"],"active":true,"network":"solana","slot":284910283}`

Hash: `27aa6168b06a9a889f21c2d66515dbba7d9ffe023677dc5841dd21f4495cb86a`

Envelope:

```text
UVIX::eyJjb21wYXRpYmlsaXR5X2xheWVyIjoidXZpeC12ZWN0b3JzLXYxIiwicGF5bG9hZF9oYXNoIjoiMjdhYTYxNjhiMDZhOWE4ODlmMjFjMmQ2NjUxNWRiYmE3ZDlmZmUwMjM2NzdkYzU4NDFkZDIxZjQ0OTVjYjg2YSIsInByb3RvY29sX3ZlcnNpb24iOiIxLjAiLCJyYXdfcGF5bG9hZCI6eyJhY2NvdW50cyI6WyJUb2tlbmtlZ1FmZVp5aU53QUpiTmJHS1BGWENXdUJ2ZjlTczYyM1ZRNURBIl0sImFjdGl2ZSI6dHJ1ZSwibmV0d29yayI6InNvbGFuYSIsInNsb3QiOjI4NDkxMDI4M30sInNvdXJjZV9wbGF0Zm9ybSI6IlZlY3RvckdlbiIsInRhcmdldF9wbGF0Zm9ybSI6IlZlY3RvckdlbiJ9::END
```

### A.3 Vector V3 — token record

Payload (logical): `{"mint":"EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v","symbol":"USDC","decimals":6,"features":["spl-token","verified"]}`

Canonical: `{"decimals":6,"features":["spl-token","verified"],"mint":"EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v","symbol":"USDC"}`

Hash: `6225c0870e098c9e5606d1c7c2e8a100e820cf0cb51a6c4e9f7628526fd2a0df`

Envelope:

```text
UVIX::eyJjb21wYXRpYmlsaXR5X2xheWVyIjoidXZpeC12ZWN0b3JzLXYxIiwicGF5bG9hZF9oYXNoIjoiNjIyNWMwODcwZTA5OGM5ZTU2MDZkMWM3YzJlOGExMDBlODIwY2YwY2I1MWE2YzRlOWY3NjI4NTI2ZmQyYTBkZiIsInByb3RvY29sX3ZlcnNpb24iOiIxLjAiLCJyYXdfcGF5bG9hZCI6eyJkZWNpbWFscyI6NiwiZmVhdHVyZXMiOlsic3BsLXRva2VuIiwidmVyaWZpZWQiXSwibWludCI6IkVQakZXZGQ1QXVmcVNTcWVNMnFOMXh6eWJhcEM4RzR3RUdHa1p3eVREdDF2Iiwic3ltYm9sIjoiVVNEQyJ9LCJzb3VyY2VfcGxhdGZvcm0iOiJWZWN0b3JHZW4iLCJ0YXJnZXRfcGxhdGZvcm0iOiJWZWN0b3JHZW4ifQ==::END
```

---

## Annex B (informative) — Known divergences and decision record

The provisional vectors below PROVE the current cross-runtime breaks. Each was
produced by executing both shipped implementations. Code points are written
explicitly to avoid encoding ambiguity.

### B.1 V4 — unicode strings (DR-001)

Payload: `{"note": "h<U+00E9>llo w<U+00F6>rld <U+2713>", "nested": {"arr": [1, 2, {"k": "v"}]}}`

- Python canonical (`ensure_ascii` escaping):
  `{"nested":{"arr":[1,2,{"k":"v"}]},"note":"h\u00e9llo w\u00f6rld \u2713"}`
  → hash `e9b81928b414ca05899d7b5986900177977b0d408d5e86090270c062c3db7078`
- JavaScript canonical (raw UTF-8, minimal escaping):
  `{"nested":{"arr":[1,2,{"k":"v"}]},"note":"h<U+00E9>llo w<U+00F6>rld <U+2713>"}`
  (non-ASCII emitted as UTF-8 bytes)
  → hash `4d7711c14ef6bed06e01339f697d9aeaf343d35aacc355d245806e69dbea0162`

**DR-001 — Unicode rule. Recommendation: raw UTF-8 with minimal escaping
(C6.3 as drafted).** Three of four shipped implementations already behave this
way (`test_roundtrip.js`, `edge/worker.ts`, `persistence/…js`); only the Python
`json.dumps` default escapes. ASCII payloads hash identically either way, so
adopting the recommendation changes no existing ASCII hash. Requires a Python
codec change (`ensure_ascii=False` plus an audit for lone surrogates).

### B.2 V5 — numbers (DR-002)

Payload (logical): `{"balance_sol": 100.0, "count": 100, "negzero": -0.0}`

- Python canonical: `{"balance_sol":100.0,"count":100,"negzero":-0.0}`
  → hash `03c7ca5f29250f05f84572f1766f5639a26f0a8ec124020b2bef748c66a3741c`
- JavaScript canonical: `{"balance_sol":100,"count":100,"negzero":0}`
  → hash `589c55051e7e7a269f8cc6200803487e48bb6a92ef2054d829b16b59f0d55397`

**DR-002 — Number rule. Recommendation: shortest round-trip decimal form with
`-0` rendered `0`, and NaN/infinities prohibited (C6.4 as drafted).** Matches
the JavaScript behavior; Python needs a custom float renderer. Note Python
today emits `NaN`/`Infinity` tokens, which are not valid JSON — prohibition
also fixes that.

### B.3 Further decision records

- **DR-003 — Key sort unit.** Python sorts keys by Unicode scalar value; JS
  `Array.sort` sorts by UTF-16 code unit. The two orders differ for keys
  containing astral characters. Recommendation: scalar value (C6.1 as
  drafted); JS implementations need an astral-aware comparator.
- **DR-004 — Canonical source file.** `core/protocol/codec.py` and
  `sol_uvix/codec.py` are byte-identical today (SHA-256
  `c85559903b246f48…`, verified 2026-11-07) but tests import only the latter
  while agent briefs home the former. Recommendation: declare one canonical
  and make the other re-export it; point tests at the canonical copy.
- **DR-005 — Pre-sealed encoder input.** The Python encoder re-frames dicts
  carrying `protocol_version` + `payload_hash` without recomputing or
  verifying the hash, so a stale hash can be sealed into an envelope.
  Recommendation: invariant E1 as drafted (verify-or-recompute; never emit a
  stale hash).
- **DR-006 — Version enforcement on decode.** The Python decoder accepts any
  `protocol_version` string without checking. Recommendation: R5.4 as drafted
  (accept `"1.0"`, reject others unless supported). No current producer emits
  anything but `"1.0"`, so this breaks nothing today.

## Annex C (informative) — Implementation notes

- **C.1 — Base64 strictness.** Python's `base64.b64decode` with default
  settings silently discards non-alphabet characters. R8.3 requires the
  strict alphabet; implementations MUST enable validation (e.g.
  `validate=True`) or pre-check the body.
- **C.2 — Binary-string decoding.** `edge/worker.ts` uses `atob()` then
  `JSON.parse`, which corrupts multi-byte UTF-8. Decode base64 to bytes,
  then UTF-8-decode to text (§9.2 step 4).
- **C.3 — Envelope body slicing.** `UVIX::` is 6 characters, `::END` is 5.
  Implementations that slice rather than strip affixes MUST use these widths.
- **C.4 — Duplicate JSON keys on decode.** Encoders MUST NOT emit them (C6.1).
  Most parsers keep the last occurrence; calling that out so no implementation
  depends on it.
- **C.5 — Timestamps are data.** `ts`/`timestamp` fields inside payloads are
  ordinary payload content; they affect the hash like any other field. Clock
  skew does not affect verification, only application semantics.

## Document history

| Version | Date | Change |
|---|---|---|
| 0.1 WD | 2026-11-07 | Initial draft from shipped implementations; V1–V3 cross-verified Python↔Node; DR-001…DR-006 open. |
| 0.2 WD | 2026-11-09 | Formally adopted RFC 8785 (JCS) resolving DR-001, DR-002, DR-003 with UTF-16 code-unit ordering; adopted RFC 9162 CTv2 upgrading RFC 6962; ratified dual-codec Solana anchor (uvix-anchor/1 and uvix-anchor/2) with 6h heartbeat; codified Main Slug Topology and The Six Contracts. |
