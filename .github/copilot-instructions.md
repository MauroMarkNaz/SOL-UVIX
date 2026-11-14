# UVIX Copilot Instructions

## Project shape

UVIX is the substrate-neutral protocol and orchestration repository. The Solana
Anchor ledger/program implementation lives in the companion `UVIX-SOL` repository;
keep chain-specific program logic there rather than duplicating it here.

The Python implementation is organized under `core/`: protocol code defines the
shared envelope and bridge APIs, mesh code models nodes and routes work, and
intelligence code coordinates poker analysis, inference, dossiers, and vector
storage. Hardware orchestration dispatches text/embedding work to the NPU and
video/raster work to the GPU. Cloudflare Worker entry points under `edge/` are a
separate deployment surface; do not confuse them with the in-process mesh router.
Root-level Python modules remain compatibility entry points for the reorganized
`core/` modules.

## Build, test, and lint

Python 3.10+ is required. The CI installation and test commands are:

```bash
python -m pip install --upgrade pip
pip install -e ".[dev]"
python -m pytest tests/ -v
```

Run one Python test by node ID, for example:

```bash
python -m pytest tests/test_slug_topology.py::test_uvix_uri_parsing -v
```

The Node.js 20 CI check verifies cross-runtime envelope compatibility:

```bash
node tests/test_roundtrip.js
```

The GitLab package job builds the Python distribution with:

```bash
python -m pip install build
python -m build
```

## Protocol and mesh contracts

- `core/protocol/codec.py` is the canonical UVIX envelope implementation. Keep
  the `UVIX::<base64>::END` framing and deterministic compact, key-sorted JSON
  hashing compatible across Python and JavaScript. If the wire format or hash
  changes, update the normative spec and cross-runtime test vectors together.
- Keep malformed-envelope errors distinct from integrity failures. Decoding
  with integrity verification enabled must reject a hash mismatch rather than
  return a best-effort payload.
- Mesh route selection belongs to `NeuralMeshTopology.find_optimal_route`;
  `EdgeNetwork.route_task` and `NeuralMeshRouter` should delegate to it rather
  than implement competing path logic. Preserve task-affinity checks, inactive
  node pruning, hop limits, and the existing mesh-status shape (add fields
  without removing or renaming existing ones).
- Tailnet configuration uses explicit node type/role/tag classification.
  Reject unknown node types instead of silently mapping them to another type.
- The `.github/agents/` UVIX specialists document subsystem-specific seams and
  invariants. Resolve their file paths relative to the repository being edited.

## Python and configuration conventions

- Keep package implementations under `core/`; preserve root compatibility
  entry points and the existing import fallbacks where modules support both
  package and direct-script use.
- Use `pathlib.Path` for filesystem paths and preserve the existing typed,
  dataclass-based APIs and return shapes when extending them.
- Public modules use descriptive docstrings with runnable usage examples.
  Raise specific errors for invalid input and preserve established exception
  types, especially protocol format versus integrity errors.
- Inference provider settings and model routing live in `config/models.json`.
  Credentials are read from environment variables named by that configuration;
  do not place credential values in config files, source, logs, or envelopes.
- `config/tailnet.template.json` is the checked-in template. Mesh code may load
  a local `config/tailnet.json` or the path named by `TAILNET_CONFIG_PATH`;
  avoid committing machine-specific tailnet data.

## Cryptography and operational safety

- Preserve the PQC design: ML-KEM/ML-DSA via `quantcrypt` where available,
  HKDF-derived keys, and AES-GCM for bulk encryption. `core/crypto/pqc.py` has
  an X25519/Ed25519 compatibility fallback when `quantcrypt` is unavailable;
  do not describe that fallback as FIPS post-quantum protection.
- Runtime private keys belong in `~/.pqc-keys`; repository security artifacts
  are public keys only. Never log, commit, or expose private key material.
- Follow `.cursor/rules/solana-mcp.mdc` for Solana documentation and Rust
  program work; the on-chain program itself belongs in the companion repository.
- Treat routes, simulations, and analysis as non-authorizing. Do not execute
  trades, on-chain writes, commits, or ACL changes without an explicit user
  command in the current task.
