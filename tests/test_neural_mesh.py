"""
Neural Mesh Topology & Edge Network Tests
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Validates the dynamic routing matrix, node telemetry, hardware affinity weights,
and canonical UVIX-RI-1.0 slug dispatch through the edge network.
"""

import pytest
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
