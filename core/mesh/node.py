"""
Neural Mesh Node Specification
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Defines interconnected node primitives for the distributed edge network topology.
"""

from enum import Enum
from dataclasses import dataclass, field
from typing import Dict, Any, Optional
import time


class NodeType(str, Enum):
    EDGE_ROUTER = "edge_router"
    NPU_ACCELERATOR = "npu_accelerator"
    GPU_COMPUTE = "gpu_compute"
    SOLANA_VALIDATOR = "solana_validator"
    NEURAL_SOLVER = "neural_solver"
    PQC_SIGNER = "pqc_signer"
    GATEWAY = "gateway"


@dataclass
class NodeCapacity:
    tops: float = 0.0
    vram_mb: int = 0
    bandwidth_mbps: float = 1000.0
    compute_type: str = "cpu"
    specialties: list[str] = field(default_factory=list)


@dataclass
class NodeTelemetry:
    current_load: float = 0.0  # 0.0 - 1.0
    latency_ms: float = 1.0
    uptime_seconds: float = 0.0
    error_rate: float = 0.0
    last_heartbeat: float = field(default_factory=time.time)


@dataclass
class MeshNode:
    node_id: str
    node_type: NodeType
    endpoint: str
    capacity: NodeCapacity
    telemetry: NodeTelemetry = field(default_factory=NodeTelemetry)
    metadata: Dict[str, Any] = field(default_factory=dict)
    active: bool = True

    def update_telemetry(self, latency_ms: Optional[float] = None, load: Optional[float] = None, error: bool = False):
        now = time.time()
        self.telemetry.last_heartbeat = now
        if latency_ms is not None:
            # Exponential moving average
            self.telemetry.latency_ms = 0.8 * self.telemetry.latency_ms + 0.2 * latency_ms
        if load is not None:
            self.telemetry.current_load = max(0.0, min(1.0, load))
        if error:
            self.telemetry.error_rate = min(1.0, self.telemetry.error_rate + 0.05)
        else:
            self.telemetry.error_rate = max(0.0, self.telemetry.error_rate * 0.95)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "node_id": self.node_id,
            "node_type": self.node_type.value,
            "endpoint": self.endpoint,
            "capacity": {
                "tops": self.capacity.tops,
                "vram_mb": self.capacity.vram_mb,
                "bandwidth_mbps": self.capacity.bandwidth_mbps,
                "compute_type": self.capacity.compute_type,
                "specialties": self.capacity.specialties,
            },
            "telemetry": {
                "current_load": round(self.telemetry.current_load, 4),
                "latency_ms": round(self.telemetry.latency_ms, 2),
                "error_rate": round(self.telemetry.error_rate, 4),
                "last_heartbeat": self.telemetry.last_heartbeat,
            },
            "active": self.active,
            "metadata": self.metadata,
        }
