"""
Edge Network Orchestrator & Tailnet Neural Mesh Overlay
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Manages the distributed edge network overlay, discovery, and inter-node peering
across Cloudflare Edge Workers, local accelerators (NPU/GPU), and Tailscale mesh nodes.
"""

from typing import Dict, Any, List, Optional
import os
import json
import time
from .node import MeshNode, NodeType, NodeCapacity, NodeTelemetry
from .topology import NeuralMeshTopology


class EdgeNetwork:
    """
    Manages edge nodes, local hardware accelerators, and overlay routing topology.
    Supports dynamic tailnet discovery and zero-trust peer ingestion.
    """

    def __init__(self, network_name: str = "uvix-neural-edge"):
        self.network_name = network_name
        self.topology = NeuralMeshTopology()
        self._init_default_cluster()

    def _init_default_cluster(self):
        """Initializes canonical local + edge nodes in the neural topology."""
        # 1. Edge Router Node (Cloudflare Worker runtime)
        edge_router = MeshNode(
            node_id="edge-worker-01",
            node_type=NodeType.EDGE_ROUTER,
            endpoint=os.environ.get("UVIX_EDGE_ENDPOINT", "https://edge.uvix-sol.network/uvix"),
            capacity=NodeCapacity(bandwidth_mbps=10_000, compute_type="v8_isolate", specialties=["edge_route", "d1_sync"]),
            telemetry=NodeTelemetry(latency_ms=12.0, current_load=0.15),
            metadata={"environment": "production", "runtime": "cloudflare_workers"}
        )
        self.topology.add_node(edge_router)

        # 2. Local NPU Accelerator (AMD XDNA 2, 50 TOPS)
        npu_node = MeshNode(
            node_id="local-xdna2-npu",
            node_type=NodeType.NPU_ACCELERATOR,
            endpoint="ipc://npu-directml",
            capacity=NodeCapacity(tops=50.0, compute_type="directml_npu", specialties=["text", "nlp", "embedding", "llm"]),
            telemetry=NodeTelemetry(latency_ms=0.5, current_load=0.08),
            metadata={"device": "AMD Ryzen AI 9 HX 370", "driver": "IpuMcdmDriver"}
        )
        self.topology.add_node(npu_node)

        # 3. Local GPU Compute Node (NVIDIA RTX 4070 Laptop GPU, 8GB VRAM)
        gpu_node = MeshNode(
            node_id="local-rtx4070-gpu",
            node_type=NodeType.GPU_COMPUTE,
            endpoint="ipc://cuda-nvenc",
            capacity=NodeCapacity(vram_mb=8188, compute_type="cuda_nvenc", specialties=["video", "transcode", "raster", "render"]),
            telemetry=NodeTelemetry(latency_ms=1.2, current_load=0.12),
            metadata={"device": "NVIDIA GeForce RTX 4070 Laptop GPU", "driver": "616.92"}
        )
        self.topology.add_node(gpu_node)

        # 4. Neural Solver Node (CFR / Nash / Strategy)
        solver_node = MeshNode(
            node_id="neural-solver-01",
            node_type=NodeType.NEURAL_SOLVER,
            endpoint="ipc://neural-cfr",
            capacity=NodeCapacity(compute_type="cpu_vector", specialties=["cfr", "nash", "dossier", "simulation"]),
            telemetry=NodeTelemetry(latency_ms=2.0, current_load=0.20),
            metadata={"algorithms": ["CFR+", "Nash", "MonteCarlo"]}
        )
        self.topology.add_node(solver_node)

        # 5. PQC Signer Node (Kyber / Dilithium)
        pqc_node = MeshNode(
            node_id="pqc-signer-01",
            node_type=NodeType.PQC_SIGNER,
            endpoint="ipc://pqc-lattice",
            capacity=NodeCapacity(compute_type="lattice_crypto", specialties=["pqc", "sign", "verify", "encapsulate"]),
            telemetry=NodeTelemetry(latency_ms=1.0, current_load=0.05),
            metadata={"schemes": ["ML-KEM", "ML-DSA", "AES-256-GCM"]}
        )
        self.topology.add_node(pqc_node)

        # 6. Solana RPC / Validator Node
        solana_node = MeshNode(
            node_id="solana-rpc-01",
            node_type=NodeType.SOLANA_VALIDATOR,
            endpoint=os.environ.get("SOLANA_RPC_URL", "https://api.devnet.solana.com"),
            capacity=NodeCapacity(bandwidth_mbps=2_500, compute_type="solana_validator", specialties=["solana_tx", "rpc", "token", "amm"]),
            telemetry=NodeTelemetry(latency_ms=45.0, current_load=0.35),
            metadata={"network": "solana"}
        )
        self.topology.add_node(solana_node)

        # Connect default star mesh
        self.topology.add_edge("edge-worker-01", "local-xdna2-npu")
        self.topology.add_edge("edge-worker-01", "local-rtx4070-gpu")
        self.topology.add_edge("edge-worker-01", "neural-solver-01")
        self.topology.add_edge("edge-worker-01", "pqc-signer-01")
        self.topology.add_edge("edge-worker-01", "solana-rpc-01")
        self.topology.add_edge("local-xdna2-npu", "local-rtx4070-gpu")
        self.topology.add_edge("local-xdna2-npu", "neural-solver-01")
        self.topology.add_edge("local-rtx4070-gpu", "neural-solver-01")
        self.topology.add_edge("pqc-signer-01", "solana-rpc-01")

        # Auto-load private tailnet configuration if present
        tailnet_path = os.environ.get("TAILNET_CONFIG_PATH", "config/tailnet.json")
        if os.path.exists(tailnet_path):
            self.load_tailnet_topology(tailnet_path)

    def register_peer(self, node: MeshNode, connect_to: Optional[List[str]] = None):
        """Registers a remote or local peer into the mesh."""
        self.topology.add_node(node)
        connections = connect_to or ["edge-worker-01"]
        for peer_id in connections:
            if peer_id in self.topology.nodes:
                self.topology.add_edge(node.node_id, peer_id)

    def load_tailnet_topology(self, config_or_path: Any):
        """
        Ingests tailnet topology definitions and registers mesh peers according to their tags.
        """
        if isinstance(config_or_path, str):
            with open(config_or_path, "r", encoding="utf-8") as f:
                data = json.load(f)
        else:
            data = config_or_path

        machines = data.get("machines", [])
        for m in machines:
            name = m.get("name")
            ip = m.get("ip", "127.0.0.1")
            tags = [t.lower() for t in m.get("tags", [])]
            os_name = m.get("os", "unknown").lower()

            # Infer node type from tags
            if any(t in tags for t in ["amd", "npu"]):
                ntype = NodeType.NPU_ACCELERATOR
                specialties = ["text", "nlp", "llm", "embedding"]
            elif any(t in tags for t in ["gpu", "render", "video"]):
                ntype = NodeType.GPU_COMPUTE
                specialties = ["video", "transcode", "raster"]
            elif any(t in tags for t in ["validator", "solana", "wecrypto"]):
                ntype = NodeType.SOLANA_VALIDATOR
                specialties = ["solana_tx", "rpc", "token", "amm"]
            elif any(t in tags for t in ["ai", "core", "trading"]):
                ntype = NodeType.NEURAL_SOLVER
                specialties = ["cfr", "nash", "dossier", "simulation"]
            elif any(t in tags for t in ["custody", "sensitive"]):
                ntype = NodeType.PQC_SIGNER
                specialties = ["pqc", "sign", "verify", "encapsulate"]
            else:
                ntype = NodeType.EDGE_ROUTER
                specialties = ["edge_route"]

            peer_node = MeshNode(
                node_id=name,
                node_type=ntype,
                endpoint=f"tailscale://{ip}",
                capacity=NodeCapacity(
                    bandwidth_mbps=1_000,
                    compute_type=f"tailnet_{os_name}",
                    specialties=specialties,
                ),
                telemetry=NodeTelemetry(
                    latency_ms=m.get("latency_ms", 5.0),
                    current_load=m.get("load", 0.1),
                ),
                metadata={"tags": tags, "os": os_name, "tailscale_ip": ip}
            )

            self.topology.add_node(peer_node)
            # Mesh peering
            self.topology.add_edge("edge-worker-01", name)
            if "local-xdna2-npu" in self.topology.nodes:
                self.topology.add_edge("local-xdna2-npu", name)

    def route_task(self, task_type: str, source_node: str = "edge-worker-01") -> Optional[Dict[str, Any]]:
        """Calculates optimal neural route and target executor node for a given task."""
        path = self.topology.find_optimal_route(source_node, task_type)
        if not path:
            return None

        target_node_id = path[-1]
        target_node = self.topology.nodes[target_node_id]

        return {
            "task_type": task_type,
            "route_path": path,
            "hop_count": len(path) - 1,
            "target_node": target_node.to_dict(),
            "timestamp": time.time(),
        }

    def get_mesh_status(self) -> Dict[str, Any]:
        """Returns comprehensive telemetry of the entire edge neural mesh."""
        return {
            "network_name": self.network_name,
            "total_nodes": len(self.topology.nodes),
            "active_nodes": sum(1 for n in self.topology.nodes.values() if n.active),
            "nodes": {nid: node.to_dict() for nid, node in self.topology.nodes.items()},
            "topology_edges": {nid: list(neighbors) for nid, neighbors in self.topology.adj.items()},
        }
