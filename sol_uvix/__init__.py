"""
SOL-UVIX Protocol Suite
~~~~~~~~~~~~~~~~~~~~~~~
Solana Stack and UVIX-RI-1.0 Interoperability Protocol Bridge.
Enables cross-agent encapsulation of Solana RPC state, bonding curves,
SPL token balances, and transactions into canonical UVIX slug envelopes.
"""

__version__ = "1.0.0"
__protocol__ = "UVIX-RI-1.0"

from .codec import (
    UVIXSlug,
    encode_uvix_slug,
    decode_uvix_slug,
    compute_canonical_payload_hash,
    UVIXIntegrityError,
    UVIXFormatError,
)
from .models import (
    SolanaAccountState,
    SolanaTransactionState,
    PumpFunBondingCurveState,
    RaydiumPoolState,
    AgentHandoffPayload,
)
from .pumpfun import PumpFunDecoder
from .raydium import RaydiumDecoder
from .client import SolanaUVIXClient
from .bridge import UVIXEdgeBridge

__all__ = [
    "UVIXSlug",
    "encode_uvix_slug",
    "decode_uvix_slug",
    "compute_canonical_payload_hash",
    "UVIXIntegrityError",
    "UVIXFormatError",
    "SolanaAccountState",
    "SolanaTransactionState",
    "PumpFunBondingCurveState",
    "RaydiumPoolState",
    "AgentHandoffPayload",
    "PumpFunDecoder",
    "RaydiumDecoder",
    "SolanaUVIXClient",
    "UVIXEdgeBridge",
]
