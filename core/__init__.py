"""
UVIX-SOL: Unified Core Package
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Modular architecture encapsulating:
- mesh: Neural mesh topology & edge network routing
- crypto: Post-quantum cryptography & hybrid state sealing
- intelligence: Neural inference, game-theoretic solvers & profiling
- hardware: Heterogeneous accelerator split (AMD NPU + NVIDIA GPU)
- protocol: Canonical UVIX-RI-1.0 framing & Solana on-chain decoders
"""

from . import mesh
from . import crypto
from . import intelligence
from . import hardware
from . import protocol

__all__ = [
    "mesh",
    "crypto",
    "intelligence",
    "hardware",
    "protocol",
]
