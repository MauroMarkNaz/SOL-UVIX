"""
Heterogeneous Hardware Workload Orchestrator
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Routes tasks across the AMD XDNA 2 NPU (text/tokens) and NVIDIA RTX 4070 (video/raster).
"""

from .orchestrator import HardwareWorkloadOrchestrator
from .npu_engine import NPUTextEngine
from .gpu_pipeline import GPUVideoRasterPipeline

__all__ = [
    "HardwareWorkloadOrchestrator",
    "NPUTextEngine",
    "GPUVideoRasterPipeline",
]
