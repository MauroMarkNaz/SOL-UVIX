"""
Neural Mesh Topology & Edge Network
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Modular package providing decentralized neural routing, node telemetry,
edge network overlay, and canonical slug topology for UVIX.
"""

from .node import MeshNode, NodeType, NodeCapacity, NodeTelemetry
from .topology import NeuralMeshTopology
from .edge_network import EdgeNetwork
from .router import NeuralMeshRouter
from .slugs import (
    MessageClass,
    ProtocolStackLayer,
    ContractType,
    UvixURI,
    SlugRegistry,
    SLUG_SOLANA_MEMO,
    SLUG_GATEWAY_APEX,
    CANONICAL_D1_ALIASES,
    CANONICAL_ORACLE_SOURCES,
    CANONICAL_MESH_NODES,
)

__all__ = [
    "MeshNode",
    "NodeType",
    "NodeCapacity",
    "NodeTelemetry",
    "NeuralMeshTopology",
    "EdgeNetwork",
    "NeuralMeshRouter",
    "MessageClass",
    "ProtocolStackLayer",
    "ContractType",
    "UvixURI",
    "SlugRegistry",
    "SLUG_SOLANA_MEMO",
    "SLUG_GATEWAY_APEX",
    "CANONICAL_D1_ALIASES",
    "CANONICAL_ORACLE_SOURCES",
    "CANONICAL_MESH_NODES",
]
