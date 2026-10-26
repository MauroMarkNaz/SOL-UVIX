import struct
from sol_uvix.pumpfun import PumpFunDecoder, BONDING_CURVE_LAYOUT
from sol_uvix.codec import decode_uvix_slug


def test_pumpfun_decode_and_slug():
    discriminator = b"\x17\xb7\xf8\x37\x60\xd8\xac\x60"
    v_tokens = 1_073_000_000_000_000  # 1.073B tokens
    v_sol = 30_000_000_000            # 30 SOL
    r_tokens = 793_100_000_000_000
    r_sol = 21_250_000_000            # 21.25 SOL (25% progress)
    total_supply = 1_000_000_000_000_000
    is_complete = False

    raw_bytes = struct.pack(
        BONDING_CURVE_LAYOUT,
        discriminator,
        v_tokens,
        v_sol,
        r_tokens,
        r_sol,
        total_supply,
        is_complete,
    )

    state = PumpFunDecoder.decode_account_data(
        raw_bytes,
        mint="DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263",
        bonding_curve_pubkey="TestBondingCurve11111111111111111111111111",
    )

    assert state.complete is False
    assert state.progress_percent == 25.0
    assert state.price_in_sol > 0.0

    slug_envelope = PumpFunDecoder.to_uvix_slug(state)
    assert slug_envelope.startswith("UVIX::")
    assert slug_envelope.endswith("::END")

    decoded_slug = decode_uvix_slug(slug_envelope)
    assert decoded_slug.source_platform == "PumpFun-Telemetry"
    assert decoded_slug.raw_payload["data"]["mint"] == "DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263"
