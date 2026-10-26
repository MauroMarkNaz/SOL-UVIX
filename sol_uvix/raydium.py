"""
Raydium AMM Protocol Decoder
~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Parses on-chain binary account state for Raydium V4 Liquidity Pools,
calculates swap reserves, pricing, and generates UVIX slugs.
"""

from typing import Dict, Any, Optional
from .models import RaydiumPoolState
from .codec import encode_uvix_slug

RAYDIUM_V4_PROGRAM_ID = "675kPX9MHTjS2zt1qfr1NYHuzeLXfQM9H24wFSUt1Mp8"


class RaydiumDecoder:
    """Analytical engine and decoder for Raydium liquidity pools."""

    @staticmethod
    def calculate_pool_state(pool_id: str,
                             base_mint: str,
                             quote_mint: str,
                             base_vault: str,
                             quote_vault: str,
                             base_reserve: int,
                             quote_reserve: int,
                             base_decimals: int = 9,
                             quote_decimals: int = 6,
                             lp_supply: int = 0) -> RaydiumPoolState:
        """
        Calculates price and constructs RaydiumPoolState.
        Price = (quote_reserve / 10^quote_decimals) / (base_reserve / 10^base_decimals)
        """
        if base_reserve > 0:
            norm_base = base_reserve / (10 ** base_decimals)
            norm_quote = quote_reserve / (10 ** quote_decimals)
            price = norm_quote / norm_base if norm_base > 0 else 0.0
        else:
            price = 0.0

        return RaydiumPoolState(
            pool_id=pool_id,
            base_mint=base_mint,
            quote_mint=quote_mint,
            base_vault=base_vault,
            quote_vault=quote_vault,
            base_reserve=base_reserve,
            quote_reserve=quote_reserve,
            price=price,
            lp_supply=lp_supply,
        )

    @classmethod
    def to_uvix_slug(cls, state: RaydiumPoolState) -> str:
        """Wraps Raydium pool telemetry into a standard UVIX envelope."""
        payload = {
            "protocol": "raydium-amm-v4",
            "type": "pool_reserves_telemetry",
            "data": state.to_dict(),
        }
        return encode_uvix_slug(
            payload,
            source_platform="Raydium-Telemetry",
            target_platform="UVIX-Mesh-MultiAgent",
            compatibility_layer="solana-raydium-uvix",
        )
