"""
Neural Mesh Topology
~~~~~~~~~~~~~~~~~~~~
Dynamic graph matrix modeling neural routing weights and optimal shortest-path
dispatch across heterogeneous edge network nodes.
"""

from typing import Dict, List, Optional, Tuple, Set
import heapq
import math
from .node import MeshNode, NodeType


class NeuralMeshTopology:
    """
    Dynamic graph modeling the neural mesh network.
    Calculates dynamic edge weights using a composite neural loss function
    incorporating latency, load, hardware specialization, and error history.
    """

    def __init__(self):
        self.nodes: Dict[str, MeshNode] = {}
        # Adjacency list: node_id -> set of neighbor node_ids
        self.adj: Dict[str, Set[str]] = {}

    def add_node(self, node: MeshNode):
        self.nodes[node.node_id] = node
        if node.node_id not in self.adj:
            self.adj[node.node_id] = set()

    def remove_node(self, node_id: str):
        if node_id in self.nodes:
            del self.nodes[node_id]
        if node_id in self.adj:
            del self.adj[node_id]
        for neighbors in self.adj.values():
            neighbors.discard(node_id)

    def add_edge(self, from_id: str, to_id: str, bidirectional: bool = True):
        if from_id not in self.adj:
            self.adj[from_id] = set()
        if to_id not in self.adj:
            self.adj[to_id] = set()
        self.adj[from_id].add(to_id)
        if bidirectional:
            self.adj[to_id].add(from_id)

    def has_task_affinity(self, target_node: MeshNode, task_type: str) -> bool:
        """Determines if target_node has hardware or specialty affinity for task_type."""
        task_lower = task_type.lower()
        specialties = [s.lower() for s in target_node.capacity.specialties]
        if task_lower in specialties:
            return True
        if target_node.node_type == NodeType.NPU_ACCELERATOR and task_lower in ("text", "nlp", "embedding", "llm"):
            return True
        if target_node.node_type == NodeType.GPU_COMPUTE and task_lower in ("video", "transcode", "raster", "render"):
            return True
        if target_node.node_type == NodeType.SOLANA_VALIDATOR and task_lower in ("solana_tx", "rpc", "token", "amm"):
            return True
        if target_node.node_type == NodeType.NEURAL_SOLVER and task_lower in ("cfr", "nash", "dossier", "simulation"):
            return True
        if target_node.node_type == NodeType.PQC_SIGNER and task_lower in ("pqc", "sign", "verify", "encapsulate"):
            return True
        if target_node.node_type == NodeType.GATEWAY and task_lower in ("gateway", "coordination", "orchestrator", "orchestration"):
            return True
        return False

    def compute_neural_weight(self, target_node: MeshNode, task_type: str) -> float:
        """
        Neural loss function calculating cost for routing a task to target_node:
        Cost = LatencyCost + LoadPenalty + AffinityPenalty + ErrorPenalty
        """
        if not target_node.active:
            return float("inf")

        # 1. Latency cost (normalized)
        latency_cost = math.log1p(max(0.1, target_node.telemetry.latency_ms))

        # 2. Compute load factor (exponential penalty as load approaches 1.0)
        load = target_node.telemetry.current_load
        load_penalty = 1.0 / (1.01 - min(0.99, load))

        # 3. Hardware task affinity
        # Ideal matches have 0.1 penalty; non-ideal matches have high penalty
        affinity_penalty = 0.0
        if self.has_task_affinity(target_node, task_type):
            affinity_penalty = 0.1
        elif target_node.node_type in (NodeType.EDGE_ROUTER, NodeType.GATEWAY):
            affinity_penalty = 1.0  # Pass-through router / gateway
        else:
            affinity_penalty = 8.0  # Mismatched hardware capability

        # 4. Error rate penalty
        error_penalty = target_node.telemetry.error_rate * 10.0

        total_weight = (0.35 * latency_cost) + (0.35 * load_penalty) + (0.20 * affinity_penalty) + (0.10 * error_penalty)
        return total_weight

    def find_optimal_route(self, source_id: str, task_type: str, max_hops: int = 5) -> Optional[List[str]]:
        """
        Dijkstra-based shortest neural weight path from source_id to the most suitable
        target node in the mesh executing task_type. Honors max_hops and never routes through
        or terminates at removed/disconnected nodes.
        """
        if source_id not in self.nodes:
            return None
        if not self.nodes[source_id].active:
            return None

        # Priority queue: (accumulated_weight, [path_nodes])
        pq: List[Tuple[float, List[str]]] = [(0.0, [source_id])]
        # Keyed by (node_id, hops) to ensure shorter-hop paths aren't pruned by longer lower-weight paths
        visited: Dict[Tuple[str, int], float] = {(source_id, 0): 0.0}

        while pq:
            curr_weight, path = heapq.heappop(pq)
            u = path[-1]
            hops = len(path) - 1

            if hops > max_hops:
                continue

            # Evaluate if current node is a viable terminal executor
            node_u = self.nodes.get(u)
            if node_u and node_u.active and u != source_id:
                is_router = node_u.node_type == NodeType.EDGE_ROUTER
                is_gateway = node_u.node_type == NodeType.GATEWAY
                allows_gateway = task_type.lower() in ("gateway", "coordination", "orchestrator", "orchestration")
                if not is_router and (not is_gateway or allows_gateway):
                    if self.has_task_affinity(node_u, task_type):
                        return path

            if hops < max_hops:
                for v in self.adj.get(u, set()):
                    node_v = self.nodes.get(v)
                    if not node_v or not node_v.active:
                        continue

                    edge_cost = self.compute_neural_weight(node_v, task_type)
                    next_weight = curr_weight + edge_cost
                    next_hops = hops + 1

                    if (v, next_hops) not in visited or next_weight < visited[(v, next_hops)]:
                        visited[(v, next_hops)] = next_weight
                        heapq.heappush(pq, (next_weight, path + [v]))

        return None
