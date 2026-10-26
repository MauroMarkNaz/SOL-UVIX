"""
Neural Mesh Topology & Edge Network
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Modular package providing decentralized neural routing, node telemetry,
and edge network overlay for UVIX-SOL.
"""

from .node import MeshNode, NodeType, NodeCapacity, NodeTelemetry
from .topology import NeuralMeshTopology
from .edge_network import EdgeNetwork
from .router import NeuralMeshRouter

__all__ = [
    "MeshNode",
    "NodeType",
    "NodeCapacity",
    "NodeTelemetry",
    "NeuralMeshTopology",
    "EdgeNetwork",
    "NeuralMeshRouter",
]
