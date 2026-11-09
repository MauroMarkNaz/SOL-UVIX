# UVIX Mesh — WSL (Ubuntu-24.04) Operational Runbook

**Environment:** WSL 2 (`Ubuntu-24.04`)  
**Host:** Windows 11 (`maurotufgamingp`, IP `100.72.42.61`)  
**WSL Node:** `maurotufgamingp-wsl` (Tailscale IP `100.81.150.124`)  
**Primary Tree:** `G:\Truffflezz_UVIX-SOL` (WSL: `/mnt/g/Truffflezz_UVIX-SOL`)  

---

## 1. Runtimes & Python Environments

| Environment | Binary Path | Purpose |
| :--- | :--- | :--- |
| **System Python 3.12** | `/usr/bin/python3` (Python 3.12.3) | Canonical mesh execution & tests |
| **Pytest** | `/usr/bin/pytest` (pytest 7.4.4) | Test runner (`tests/test_*.py`) |
| **Node.js** | `/usr/local/bin/node` (v22.18.0) | Cross-runtime envelope verification (`tests/test_roundtrip.js`) |
| **Bridge Virtualenv** | `/mnt/g/WECRYP/jdwalkaz-bridge/.venv/bin/python` | Cascade & bridge services |
| **Oracle Virtualenv** | `/mnt/g/dev/wecryp-oracle/.venv/bin/python` | WeCryp Oracle agent |

---

## 2. Active Bridge Ports & Sockets (`ss -tlnp` Verified)

```
State   Recv-Q  Send-Q   Local Address:Port   Service / Process
LISTEN  0       2048          0.0.0.0:8040   Bridge Server (PID 2510, python server.py)
LISTEN  0       2048          0.0.0.0:8002   WeCryp Oracle Agent (PID 2514, python agent.py)
LISTEN  0       128           0.0.0.0:8004   Jdwalkaz Cascade Bridge (PID 2511, python jdwalkaz_cascade_bridge.py)
LISTEN  0       2048        127.0.0.1:8005   Gemini MCP Server (PID 2509, python gemini_mcp_server.py)
LISTEN  0       5           127.0.0.1:8765   Poker DB API (PID 3832, python3 poker-db-api.py)
LISTEN  0       5           127.0.0.1:8766   Local Exec MCP (PID 2512, python3 local_exec_mcp.py)
LISTEN  0       511           0.0.0.0:8788   Cloudflare Worker Wrangler (PID 2515, node)
LISTEN  0       5           127.0.0.1:8794   Kalshi Markets Bridge (PID 3587, python3 kalshi-markets.py)
LISTEN  0       5           127.0.0.1:8797   AI Handoff Hub (PID 2501, python3 ai_handoff.py)
LISTEN  0       4096        127.0.0.1:11434  Ollama Local LLM Daemon
LISTEN  0       511         127.0.0.1:18789  OpenClaw Gateway Service (PID 2513)
LISTEN  0       4096        127.0.0.1:20241-20245 Cloudflared Origin Tunnels (PIDs 2505-2508)
LISTEN  0       4096   100.81.150.124:443    Tailscale HTTPS RPC Ingress
LISTEN  0       4096   100.81.150.124:8444   Tailscale Service Port
LISTEN  0       4096        127.0.0.1:6379   Redis Core Instance
LISTEN  0       4096          0.0.0.0:6380   Redis Auxiliary Instance
LISTEN  0       4096        127.0.0.1:3000   Local Web / Next.js Dashboard
```

---

## 3. Standard Verification Commands

### Check Listening Ports
```bash
wsl -d Ubuntu-24.04 bash -c "ss -tlnp"
```

### Run Mesh & Codec Unit Tests
```bash
wsl -d Ubuntu-24.04 bash -c "cd /mnt/g/Truffflezz_UVIX-SOL && python3 -m pytest tests/test_codec.py tests/test_neural_mesh.py -v"
```

### Run Cross-Runtime V8 Envelope Verification
```bash
# In WSL:
wsl -d Ubuntu-24.04 bash -c "cd /mnt/g/Truffflezz_UVIX-SOL && node tests/test_roundtrip.js"

# On Windows:
node G:\Truffflezz_UVIX-SOL\tests\test_roundtrip.js
```

### Tailscale Node Health Check
```bash
wsl -d Ubuntu-24.04 bash -c "tailscale status"
```

---

## 4. Seam Wiring Invariants

1. **Envelope Flow (`codec.py` <-> `router.py` <-> `MeshNode`):**
   - Framing: `UVIX::<base64>::END`
   - Canonical Hashing: RFC 8785 deterministic JSON serialization (`separators=(',', ':')`, `sort_keys=True`) hashed via SHA-256.
   - Envelopes carry `source_platform`, `target_platform`, `compatibility_layer`, `payload_hash`, and `raw_payload`.

2. **Route Delegation (`EdgeNetwork.route_task` <-> `NeuralMeshTopology.find_optimal_route`):**
   - Dijkstra shortest neural weight path using composite loss function:
     $$\text{Loss} = 0.35 \times \ln(1 + \text{latency}) + 0.35 \times \frac{1}{1.01 - \text{load}} + 0.20 \times \text{affinity\_penalty} + 0.10 \times \text{error\_penalty}$$
   - Strict inactive node pruning: inactive sources or workers are never routed through or selected.

3. **Node Types & Tailnet Ingestion (`tailnet.json` <-> `load_tailnet_topology`):**
   - Machine `role` takes precedence over generic tags:
     - `solana_validator_worker` $\rightarrow$ `NodeType.SOLANA_VALIDATOR` (`specialties: ['solana_tx', 'rpc', 'token', 'amm']`)
     - `antigravity_autonomous_core` $\rightarrow$ `NodeType.GATEWAY` (`specialties: ['gateway', 'coordination']`)
   - AMD tags are scoped to host NPU when `wsl` tag is absent.
   - NodeCapacity ingests `npu_tops` and `vram_mb` directly from machine `hardware` configuration.
