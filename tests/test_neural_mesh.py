"""
Neural Mesh Topology & Edge Network Tests
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Validates the dynamic routing matrix, node telemetry, hardware affinity weights,
and canonical UVIX-RI-1.0 slug dispatch through the edge network.
"""

try:
    import pytest
except ImportError:
    pytest = None
from core.mesh import (
    MeshNode,
    NodeType,
    NodeCapacity,
    NodeTelemetry,
    NeuralMeshTopology,
    EdgeNetwork,
    NeuralMeshRouter,
)
from core.protocol.codec import decode_uvix_slug


ESTATE_TAILNET = {
    "machines": [
        {
            "name": "maurotufgamingp",
            "ip": "198.51.100.10",
            "tags": ["amd", "gpu"],
            "hardware": {"npu_tops": 50.0, "vram_mb": 8188},
        },
        {
            "name": "maurotufgamingp-wsl",
            "ip": "198.51.100.11",
            "role": "solana_validator_worker",
            "tags": ["wsl", "amd", "ai"],
            "latency_ms": 1.5,
        },
        {
            "name": "mariphone-27-2-4",
            "ip": "198.51.100.12",
            "tags": ["mobile", "edge"],
        },
        {
            "name": "muse-1",
            "ip": "198.51.100.13",
            "role": "solana_validator_worker",
            "latency_ms": 20.0,
        },
        {
            "name": "antigravity-agent",
            "ip": "198.51.100.14",
            "role": "antigravity_autonomous_core",
        },
    ]
}


def _estate_network():
    net = EdgeNetwork()
    net.load_tailnet_topology(ESTATE_TAILNET)
    return net


def test_mesh_node_initialization_and_telemetry():
    node = MeshNode(
        node_id="test-npu-01",
        node_type=NodeType.NPU_ACCELERATOR,
        endpoint="ipc://test-npu",
        capacity=NodeCapacity(tops=50.0, compute_type="directml_npu", specialties=["text", "nlp"]),
    )
    assert node.node_id == "test-npu-01"
    assert node.node_type == NodeType.NPU_ACCELERATOR
    assert node.capacity.tops == 50.0

    # Update telemetry
    node.update_telemetry(latency_ms=2.5, load=0.45, error=False)
    assert node.telemetry.current_load == 0.45
    assert node.telemetry.latency_ms > 0


def test_neural_weight_affinity_and_penalty():
    topology = NeuralMeshTopology()

    npu_node = MeshNode(
        node_id="npu-01",
        node_type=NodeType.NPU_ACCELERATOR,
        endpoint="ipc://npu",
        capacity=NodeCapacity(tops=50.0, specialties=["text", "llm"]),
        telemetry=NodeTelemetry(latency_ms=1.0, current_load=0.1),
    )
    gpu_node = MeshNode(
        node_id="gpu-01",
        node_type=NodeType.GPU_COMPUTE,
        endpoint="ipc://gpu",
        capacity=NodeCapacity(vram_mb=8188, specialties=["video", "raster"]),
        telemetry=NodeTelemetry(latency_ms=1.5, current_load=0.1),
    )

    topology.add_node(npu_node)
    topology.add_node(gpu_node)

    # For a text task: NPU weight should be significantly lower (cheaper) than GPU weight
    npu_text_weight = topology.compute_neural_weight(npu_node, "text")
    gpu_text_weight = topology.compute_neural_weight(gpu_node, "text")
    assert npu_text_weight < gpu_text_weight

    # For a video task: GPU weight should be significantly lower than NPU weight
    npu_video_weight = topology.compute_neural_weight(npu_node, "video")
    gpu_video_weight = topology.compute_neural_weight(gpu_node, "video")
    assert gpu_video_weight < npu_video_weight


def test_edge_network_routing_paths():
    net = EdgeNetwork(network_name="test-cluster")
    status = net.get_mesh_status()
    assert status["total_nodes"] >= 6
    assert "edge-worker-01" in status["nodes"]

    # Route text task: should land on local-xdna2-npu
    text_route = net.route_task("text", source_node="edge-worker-01")
    assert text_route is not None
    assert text_route["target_node"]["node_id"] == "local-xdna2-npu"
    assert text_route["route_path"] == ["edge-worker-01", "local-xdna2-npu"]

    # Route video task: should land on local-rtx4070-gpu
    video_route = net.route_task("video", source_node="edge-worker-01")
    assert video_route is not None
    assert video_route["target_node"]["node_id"] == "local-rtx4070-gpu"

    # Route CFR task: should land on neural-solver-01
    cfr_route = net.route_task("cfr", source_node="edge-worker-01")
    assert cfr_route is not None
    assert cfr_route["target_node"]["node_id"] == "neural-solver-01"


def test_neural_mesh_router_slug_dispatch():
    router = NeuralMeshRouter()
    result = router.dispatch_workload(
        task_type="text",
        payload_data={"query": "Solana account state batch", "tokens": 64},
        source_node="edge-worker-01"
    )

    assert result["status"] == "DISPATCHED"
    assert "slug" in result
    slug = result["slug"]
    assert slug.startswith("UVIX::")
    assert slug.endswith("::END")

    # Verify slug integrity and contents
    decoded = decode_uvix_slug(slug, verify_integrity=True)
    assert decoded.compatibility_layer == "neural-mesh-v1"
    assert decoded.raw_payload["task_type"] == "text"
    assert decoded.raw_payload["target_node"] == "local-xdna2-npu"
    assert decoded.raw_payload["data"]["tokens"] == 64

def test_neural_weight_determinism():
    topology = NeuralMeshTopology()
    node = MeshNode(
        node_id="det-npu-01",
        node_type=NodeType.NPU_ACCELERATOR,
        endpoint="ipc://det-npu",
        capacity=NodeCapacity(tops=50.0, specialties=["text", "nlp"]),
        telemetry=NodeTelemetry(latency_ms=1.23, current_load=0.45, error_rate=0.02)
    )
    topology.add_node(node)

    weight_1 = topology.compute_neural_weight(node, "text")
    weight_2 = topology.compute_neural_weight(node, "text")
    weight_3 = topology.compute_neural_weight(node, "text")
    assert weight_1 == weight_2 == weight_3
    assert isinstance(weight_1, float)


def test_node_capacity_and_telemetry_tracking():
    node = MeshNode(
        node_id="cap-gpu-01",
        node_type=NodeType.GPU_COMPUTE,
        endpoint="ipc://cap-gpu",
        capacity=NodeCapacity(vram_mb=8188, bandwidth_mbps=2500.0, specialties=["video", "render"]),
        telemetry=NodeTelemetry(latency_ms=10.0, current_load=0.1, error_rate=0.0)
    )

    # Initial check
    d = node.to_dict()
    assert d["capacity"]["vram_mb"] == 8188
    assert d["capacity"]["bandwidth_mbps"] == 2500.0
    assert d["telemetry"]["current_load"] == 0.1
    assert d["telemetry"]["latency_ms"] == 10.0

    # EMA update: 0.8 * 10.0 + 0.2 * 20.0 = 12.0
    node.update_telemetry(latency_ms=20.0, load=0.5, error=True)
    assert abs(node.telemetry.latency_ms - 12.0) < 1e-5
    assert node.telemetry.current_load == 0.5
    assert node.telemetry.error_rate == 0.05

    # Error recovery
    node.update_telemetry(error=False)
    assert abs(node.telemetry.error_rate - (0.05 * 0.95)) < 1e-5


def test_route_optimization_hop_limit_and_node_removal():
    topo = NeuralMeshTopology()

    # Create linear topology: router -> bridge -> solver
    router = MeshNode("edge-r1", NodeType.EDGE_ROUTER, "ipc://r1", NodeCapacity())
    bridge = MeshNode("bridge-01", NodeType.EDGE_ROUTER, "ipc://b1", NodeCapacity())
    solver = MeshNode("solver-01", NodeType.NEURAL_SOLVER, "ipc://s1", NodeCapacity(specialties=["cfr"]))

    topo.add_node(router)
    topo.add_node(bridge)
    topo.add_node(solver)

    topo.add_edge("edge-r1", "bridge-01")
    topo.add_edge("bridge-01", "solver-01")

    # 1. 2-hop route should succeed with max_hops=2
    route_2 = topo.find_optimal_route("edge-r1", "cfr", max_hops=2)
    assert route_2 == ["edge-r1", "bridge-01", "solver-01"]

    # 2. Strict hop limit: max_hops=1 cannot reach solver-01 (2 hops away)
    route_1 = topo.find_optimal_route("edge-r1", "cfr", max_hops=1)
    assert route_1 is None

    # 3. Direct edge addition: edge-r1 -> solver-01 (1 hop)
    topo.add_edge("edge-r1", "solver-01")
    route_direct = topo.find_optimal_route("edge-r1", "cfr", max_hops=1)
    assert route_direct == ["edge-r1", "solver-01"]

    # 4. Remove solver-01 node: route must be None and never return removed node
    topo.remove_node("solver-01")
    assert "solver-01" not in topo.nodes
    assert "solver-01" not in topo.adj["edge-r1"]
    route_removed = topo.find_optimal_route("edge-r1", "cfr", max_hops=5)
    assert route_removed is None

    # 5. Unsupported task type returns None
    route_unsupported = topo.find_optimal_route("edge-r1", "nonexistent_task_xyz")
    assert route_unsupported is None


def test_graph_mutation_adjacency_and_metrics():
    topo = NeuralMeshTopology()
    assert len(topo.nodes) == 0
    assert len(topo.adj) == 0

    n1 = MeshNode("n1", NodeType.EDGE_ROUTER, "ipc://n1", NodeCapacity())
    n2 = MeshNode("n2", NodeType.NPU_ACCELERATOR, "ipc://n2", NodeCapacity(specialties=["text"]))
    n3 = MeshNode("n3", NodeType.GPU_COMPUTE, "ipc://n3", NodeCapacity(specialties=["video"]))

    topo.add_node(n1)
    topo.add_node(n2)
    topo.add_node(n3)

    assert len(topo.nodes) == 3
    assert set(topo.nodes.keys()) == {"n1", "n2", "n3"}

    # Add edges
    topo.add_edge("n1", "n2")
    topo.add_edge("n2", "n3")

    assert topo.adj["n1"] == {"n2"}
    assert topo.adj["n2"] == {"n1", "n3"}
    assert topo.adj["n3"] == {"n2"}

    # Remove intermediate node n2
    topo.remove_node("n2")
    assert len(topo.nodes) == 2
    assert "n2" not in topo.nodes
    assert "n2" not in topo.adj
    assert "n2" not in topo.adj["n1"]
    assert "n2" not in topo.adj["n3"]
    assert len(topo.adj["n1"]) == 0
    assert len(topo.adj["n3"]) == 0



def test_tailnet_topology_role_and_hardware_ingestion():
    net = _estate_network()
    assert "maurotufgamingp-wsl" in net.topology.nodes
    wsl_node = net.topology.nodes["maurotufgamingp-wsl"]
    # Role 'solana_validator_worker' must map to SOLANA_VALIDATOR, not NPU
    assert wsl_node.node_type == NodeType.SOLANA_VALIDATOR
    assert "solana_tx" in wsl_node.capacity.specialties

    # Check hardware capacity ingestion for host
    host_node = net.topology.nodes["maurotufgamingp"]
    assert host_node.capacity.tops == 50.0
    assert host_node.capacity.vram_mb == 8188

    # Check antigravity-agent gateway classification
    ag_node = net.topology.nodes["antigravity-agent"]
    assert ag_node.node_type == NodeType.GATEWAY

    # Verify solana_tx routes to local WSL validator (1.5ms latency), not remote muse-1 (20ms)
    solana_route = net.route_task("solana_tx", source_node="edge-worker-01")
    assert solana_route is not None
    assert solana_route["target_node"]["node_id"] == "maurotufgamingp-wsl"


def test_inactive_source_and_node_pruning():
    topo = NeuralMeshTopology()
    router = MeshNode("router-01", NodeType.EDGE_ROUTER, "ipc://r", NodeCapacity())
    worker = MeshNode("worker-01", NodeType.NPU_ACCELERATOR, "ipc://w", NodeCapacity(specialties=["text"]))
    topo.add_node(router)
    topo.add_node(worker)
    topo.add_edge("router-01", "worker-01")

    # When worker is active, route works
    assert topo.find_optimal_route("router-01", "text") == ["router-01", "worker-01"]

    # When worker is inactive, route must return None
    worker.active = False
    assert topo.find_optimal_route("router-01", "text") is None

    # When router (source) is inactive, route must return None
    worker.active = True
    router.active = False
    assert topo.find_optimal_route("router-01", "text") is None


def test_end_to_end_mesh_envelope_dispatch_roundtrip():
    router = NeuralMeshRouter()
    workloads = [
        ("text", {"model": "llama-3-8b", "prompt": "analyze solana block"}),
        ("video", {"codec": "h265", "frames": 1200}),
        ("cfr", {"scenario": "poker_holdem_turn", "iterations": 50000}),
        ("solana_tx", {"instruction": "transfer", "lamports": 1000000}),
    ]

    for task_type, payload in workloads:
        dispatch_result = router.dispatch_workload(task_type, payload, source_node="edge-worker-01")
        assert dispatch_result["status"] == "DISPATCHED"
        assert "slug" in dispatch_result
        slug = dispatch_result["slug"]

        # Decode and verify integrity
        decoded = decode_uvix_slug(slug, verify_integrity=True)
        assert decoded.protocol_version == "1.0"
        assert decoded.compatibility_layer == "neural-mesh-v1"
        assert decoded.raw_payload["task_type"] == task_type
        assert decoded.raw_payload["data"] == payload
        assert decoded.raw_payload["source_node"] == "edge-worker-01"
        assert decoded.raw_payload["target_node"] == dispatch_result["route"]["target_node"]["node_id"]


def test_unknown_node_type_rejection():
    """Ensure load_tailnet_topology rejects unknown node types and unmapped tags."""
    net = EdgeNetwork()

    # Explicit invalid node_type string must raise ValueError
    with pytest.raises(ValueError, match="Unknown node type"):
        net.load_tailnet_topology({
            "machines": [{"name": "quantum-core-01", "node_type": "quantum_simulator", "ip": "100.1.1.1"}]
        })

    # Unrecognized tags with no role or type must raise ValueError
    with pytest.raises(ValueError, match="Unable to infer valid NodeType"):
        net.load_tailnet_topology({
            "machines": [{"name": "mystery-box-01", "tags": ["unrecognized_tag_xyz"], "ip": "100.1.1.2"}]
        })


def test_mesh_status_shape_and_estate_nodes():
    """Verify get_mesh_status() shape and compatibility with expanded estate nodes."""
    net = _estate_network()
    status = net.get_mesh_status()

    # Stable schema assertions (additive keys only)
    assert "network_name" in status
    assert "total_nodes" in status
    assert "active_nodes" in status
    assert "nodes" in status
    assert "topology_edges" in status
    assert "mesh_healthy" in status
    assert "estate_nodes" in status

    # Verify compatibility with all expanded estate nodes
    estate_expected = ["maurotufgamingp", "maurotufgamingp-wsl", "mariphone", "muse-1", "antigravity-agent"]
    for expected in estate_expected:
        assert expected in status["nodes"] or f"{expected}-27-2-4" in status["nodes"], f"Missing estate node: {expected}"
        node_entry = status["nodes"].get(expected) or status["nodes"].get(f"{expected}-27-2-4")
        assert "node_id" in node_entry
        assert "node_type" in node_entry
        assert "endpoint" in node_entry
        assert "capacity" in node_entry
        assert "telemetry" in node_entry
        assert node_entry["active"] is True


def test_peer_registration_and_routing_roundtrip():
    """Test full peer lifecycle: dynamic registration, routing priority, and removal fallback."""
    net = _estate_network()

    # Initial route for solana_tx goes to maurotufgamingp-wsl (1.5ms)
    initial_route = net.route_task("solana_tx", source_node="edge-worker-01")
    assert initial_route is not None
    assert initial_route["target_node"]["node_id"] == "maurotufgamingp-wsl"

    # Register dynamic low-latency peer
    turbo_peer = MeshNode(
        node_id="turbo-solana-peer",
        node_type=NodeType.SOLANA_VALIDATOR,
        endpoint="tailscale://100.99.1.1",
        capacity=NodeCapacity(specialties=["solana_tx", "rpc"]),
        telemetry=NodeTelemetry(latency_ms=0.2, current_load=0.01)
    )
    net.register_peer(turbo_peer, connect_to=["edge-worker-01"])

    # Task route must now prioritize turbo-solana-peer
    turbo_route = net.route_task("solana_tx", source_node="edge-worker-01")
    assert turbo_route is not None
    assert turbo_route["target_node"]["node_id"] == "turbo-solana-peer"
    assert turbo_route["route_path"] == ["edge-worker-01", "turbo-solana-peer"]

    # Unregister turbo peer
    net.unregister_peer("turbo-solana-peer")

    # Routing must fall back to maurotufgamingp-wsl
    fallback_route = net.route_task("solana_tx", source_node="edge-worker-01")
    assert fallback_route is not None
    assert fallback_route["target_node"]["node_id"] == "maurotufgamingp-wsl"


def test_gateway_coordination_routing():
    """Verify coordination task routing reaches antigravity-agent gateway."""
    net = _estate_network()
    route = net.route_task("coordination", source_node="edge-worker-01")
    assert route is not None
    assert route["target_node"]["node_id"] == "antigravity-agent"
    assert route["target_node"]["node_type"] == NodeType.GATEWAY.value

