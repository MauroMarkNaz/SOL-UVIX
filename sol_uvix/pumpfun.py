"""
Pump.fun Bonding Curve Protocol Decoder
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Parses on-chain binary account state for Pump.fun bonding curves,
calculates constant-product pricing (k = x * y), and formats state for UVIX slugs.
"""

import struct
import base64
from typing import Dict, Any, Optional
from .models import PumpFunBondingCurveState
from .codec import encode_uvix_slug

PUMPFUN_PROGRAM_ID = "6EF8rrecthR5Dkzon8Nwu78hRvfCKubJ14M5uBEwF6P"
PUMPFUN_FEE_RECIPIENT = "CebN5WGQ4jvEPvsVU4EoHEpgzq1VV7AbicfhtW4xC9iM"

# Expected layout: 8B discriminator + 8B vTokens + 8B vSol + 8B rTokens + 8B rSol + 8B supply + 1B complete
BONDING_CURVE_LAYOUT = "<8sQQQQQ?"
TARGET_REAL_SOL_RESERVES = 85_000_000_000  # ~85 SOL for Raydium graduation


class PumpFunDecoder:
    """Decoder and analytical engine for Pump.fun bonding curves."""

    @staticmethod
    def decode_account_data(raw_bytes: bytes,
                            mint: str = "",
                            bonding_curve_pubkey: str = "",
                            associated_bonding_curve: str = "") -> PumpFunBondingCurveState:
        """
        Parses binary buffer of Pump.fun bonding curve account into PumpFunBondingCurveState.
        """
        if len(raw_bytes) < struct.calcsize(BONDING_CURVE_LAYOUT):
            raise ValueError(f"Data length {len(raw_bytes)} is shorter than layout requirement")

        (
            discriminator,
            v_token_reserves,
            v_sol_reserves,
            r_token_reserves,
            r_sol_reserves,
            total_supply,
            is_complete,
        ) = struct.unpack_from(BONDING_CURVE_LAYOUT, raw_bytes)

        # Price in SOL per token: (v_sol_reserves / 1e9) / (v_token_reserves / 1e6)
        if v_token_reserves > 0:
            sol_amount = v_sol_reserves / 1_000_000_000.0
            token_amount = v_token_reserves / 1_000_000.0
            price_in_sol = sol_amount / token_amount
        else:
            price_in_sol = 0.0

        market_cap_sol = (total_supply / 1_000_000.0) * price_in_sol
        progress_pct = min(100.0, (r_sol_reserves / TARGET_REAL_SOL_RESERVES) * 100.0)

        return PumpFunBondingCurveState(
            mint=mint,
            bonding_curve=bonding_curve_pubkey,
            associated_bonding_curve=associated_bonding_curve,
            virtual_token_reserves=v_token_reserves,
            virtual_sol_reserves=v_sol_reserves,
            real_token_reserves=r_token_reserves,
            real_sol_reserves=r_sol_reserves,
            token_total_supply=total_supply,
            complete=bool(is_complete),
            price_in_sol=price_in_sol,
            market_cap_sol=market_cap_sol,
            progress_percent=round(progress_pct, 2),
        )

    @classmethod
    def decode_base64_account(cls,
                              b64_data: str,
                              mint: str = "",
                              bonding_curve_pubkey: str = "",
                              associated_bonding_curve: str = "") -> PumpFunBondingCurveState:
        """Helper to decode base64 string directly from RPC getAccountInfo response."""
        data_bytes = base64.b64decode(b64_data)
        return cls.decode_account_data(
            data_bytes,
            mint=mint,
            bonding_curve_pubkey=bonding_curve_pubkey,
            associated_bonding_curve=associated_bonding_curve,
        )

    @classmethod
    def to_uvix_slug(cls, state: PumpFunBondingCurveState) -> str:
        """Wraps Pump.fun bonding curve telemetry into a standard UVIX envelope."""
        payload = {
            "protocol": "pumpfun-v1",
            "type": "bonding_curve_telemetry",
            "data": state.to_dict(),
        }
        return encode_uvix_slug(
            payload,
            source_platform="PumpFun-Telemetry",
            target_platform="UVIX-Mesh-MultiAgent",
            compatibility_layer="solana-pumpfun-uvix",
        )
