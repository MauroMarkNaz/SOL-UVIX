"""
Neural Mesh Router
~~~~~~~~~~~~~~~~~~
Executes task dispatch across the edge network, packing outputs into canonical
UVIX-RI-1.0 envelopes with deterministic SHA-256 payload integrity hashing.
"""

from typing import Dict, Any, Optional
import time
from .edge_network import EdgeNetwork
from core.protocol.codec import encode_uvix_slug, decode_uvix_slug


class NeuralMeshRouter:
    """
    High-level router integrating neural mesh topology with UVIX envelope transmission.
    """

    def __init__(self, network: Optional[EdgeNetwork] = None):
        self.network = network or EdgeNetwork()

    def dispatch_workload(
        self,
        task_type: str,
        payload_data: Dict[str, Any],
        source_node: str = "edge-worker-01"
    ) -> Dict[str, Any]:
        """
        Dispatches a task payload through the neural mesh to the optimal target node,
        returning a canonical UVIX-RI-1.0 slug.
        """
        route_info = self.network.route_task(task_type, source_node=source_node)
        if not route_info:
            raise RuntimeError(f"No viable route found in neural mesh for task '{task_type}'.")

        target_node = route_info["target_node"]
        target_id = target_node["node_id"]

        # Synthesize task execution metadata
        execution_payload = {
            "task_type": task_type,
            "source_node": source_node,
            "target_node": target_id,
            "route_hops": route_info["route_path"],
            "data": payload_data,
            "timestamp": time.time(),
        }

        # Encode with canonical UVIX-RI-1.0 framing
        slug = encode_uvix_slug(
            execution_payload,
            source_platform=f"NeuralMesh::{source_node}",
            target_platform=f"NeuralMesh::{target_id}",
            compatibility_layer="neural-mesh-v1"
        )

        return {
            "status": "DISPATCHED",
            "route": route_info,
            "slug": slug,
        }
