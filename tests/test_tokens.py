"""
Unit tests for SPL Token & Token-2022 account decoders,
TransferFeeConfig calculations, InterestBearingConfig, TokenMetadata,
and swap simulation math.
"""

import pytest
import time
from sol_uvix.transactions import b58encode
from sol_uvix.tokens import (
    SPLTokenDecoder,
    SPLTokenMint,
    SPLTokenAccount,
    TransferFee,
    TransferFeeConfig,
    InterestBearingConfig,
    TokenMetadata,
    TOKEN_PROGRAM_ID,
    TOKEN_2022_PROGRAM_ID,
)
from sol_uvix.pumpfun import PumpFunDecoder, PumpFunBondingCurveState
from sol_uvix.raydium import RaydiumDecoder, RaydiumPoolState
from sol_uvix.bridge import UVIXEdgeBridge
from sol_uvix.codec import decode_uvix_slug, compute_canonical_payload_hash


def test_standard_spl_mint_encoding_and_decoding():
    auth_key = b58encode(b"\x11" * 32)
    freeze_key = b58encode(b"\x22" * 32)
    supply = 1_000_000_000_000  # 1,000,000 USDC (6 decimals)
    decimals = 6

    raw_bytes = SPLTokenDecoder.encode_mint_data(
        mint_authority=auth_key,
        supply=supply,
        decimals=decimals,
        is_initialized=True,
        freeze_authority=freeze_key,
    )

    assert len(raw_bytes) == 82

    mint_state = SPLTokenDecoder.decode_mint_data(raw_bytes, mint_pubkey="EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v")
    assert mint_state.mint == "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"
    assert mint_state.mint_authority == auth_key
    assert mint_state.freeze_authority == freeze_key
    assert mint_state.supply == supply
    assert mint_state.decimals == 6
    assert mint_state.ui_supply == 1_000_000.0
    assert mint_state.is_initialized is True
    assert mint_state.is_token_2022 is False
    assert mint_state.transfer_fee_config is None

    # UVIX slug roundtrip
    slug = mint_state.to_uvix_slug()
    assert slug.startswith("UVIX::")
    decoded = decode_uvix_slug(slug, verify_integrity=True)
    assert decoded.raw_payload["protocol"] == "spl-token"
    assert decoded.raw_payload["data"]["supply"] == supply


def test_standard_spl_token_account_decoding():
    mint_key = b58encode(b"\x33" * 32)
    owner_key = b58encode(b"\x44" * 32)
    delegate_key = b58encode(b"\x55" * 32)
    amount = 500_000_000

    raw_bytes = SPLTokenDecoder.encode_token_account_data(
        mint=mint_key,
        owner=owner_key,
        amount=amount,
        delegate=delegate_key,
        state=1,  # initialized
        is_native_lamports=None,
        delegated_amount=100_000,
        close_authority=owner_key,
    )

    assert len(raw_bytes) == 165

    acc_state = SPLTokenDecoder.decode_token_account_data(raw_bytes, account_pubkey="TestAccount111111111111111111111111111111")
    assert acc_state.mint == mint_key
    assert acc_state.owner == owner_key
    assert acc_state.delegate == delegate_key
    assert acc_state.amount == amount
    assert acc_state.state == "initialized"
    assert acc_state.is_native is False
    assert acc_state.delegated_amount == 100_000
    assert acc_state.close_authority == owner_key
    assert acc_state.is_token_2022 is False
    assert acc_state.transfer_fee_amount is None

    # UVIX slug
    slug = acc_state.to_uvix_slug()
    decoded = decode_uvix_slug(slug, verify_integrity=True)
    assert decoded.raw_payload["data"]["amount"] == amount


def test_token_2022_mint_with_transfer_fee_config():
    auth_key = b58encode(b"\x61" * 32)
    withheld_auth = b58encode(b"\x62" * 32)

    fee_config = TransferFeeConfig(
        transfer_fee_config_authority=auth_key,
        withdraw_withheld_authority=withheld_auth,
        withheld_amount=12_000,
        older_transfer_fee=TransferFee(epoch=100, transfer_fee_basis_points=150, maximum_fee=500_000),  # 1.5%
        newer_transfer_fee=TransferFee(epoch=200, transfer_fee_basis_points=250, maximum_fee=1_000_000),  # 2.5%
    )

    raw_bytes = SPLTokenDecoder.encode_mint_data(
        mint_authority=auth_key,
        supply=50_000_000_000,
        decimals=6,
        is_initialized=True,
        transfer_fee_config=fee_config,
    )

    assert len(raw_bytes) > 82

    mint_state = SPLTokenDecoder.decode_mint_data(raw_bytes, mint_pubkey="Token2022FeeMint11111111111111111111111111111")
    assert mint_state.is_token_2022 is True
    assert mint_state.transfer_fee_config is not None
    assert mint_state.transfer_fee_config.withheld_amount == 12_000

    # Fee calculation test under older rule (epoch 150 < 200)
    # 100,000 * 150 bps (1.5%) = 1,500
    fee_older = mint_state.calculate_transfer_fee(100_000, current_epoch=150)
    assert fee_older == 1500

    # Fee calculation test under newer rule (epoch 250 >= 200)
    # 100,000 * 250 bps (2.5%) = 2,500
    fee_newer = mint_state.calculate_transfer_fee(100_000, current_epoch=250)
    assert fee_newer == 2500

    # Fee capping test: 100,000,000 * 2.5% = 2,500,000, capped at maximum_fee 1,000,000
    fee_capped = mint_state.calculate_transfer_fee(100_000_000, current_epoch=250)
    assert fee_capped == 1_000_000

    # Div-ceil test: 1 unit transfer with 250 bps = ceil(250 / 10000) = 1
    assert mint_state.calculate_transfer_fee(1, current_epoch=250) == 1

    # Slug test
    slug = mint_state.to_uvix_slug()
    decoded = decode_uvix_slug(slug, verify_integrity=True)
    assert decoded.raw_payload["protocol"] == "spl-token-2022"
    assert decoded.raw_payload["data"]["transfer_fee_config"]["withheld_amount"] == 12_000


def test_token_2022_mint_with_interest_bearing_and_metadata():
    rate_auth = b58encode(b"\x71" * 32)
    update_auth = b58encode(b"\x72" * 32)
    mint_pk = b58encode(b"\x73" * 32)

    now = int(time.time())
    ib_config = InterestBearingConfig(
        rate_authority=rate_auth,
        initialization_timestamp=now - 86400 * 30,
        pre_update_average_rate=400,
        last_update_timestamp=now - 86400 * 10,
        current_rate=500,  # 5.0% APY
    )

    metadata = TokenMetadata(
        update_authority=update_auth,
        mint=mint_pk,
        name="UVIX Synthetics",
        symbol="uSYNTH",
        uri="https://uvix.leaksnipe.win/metadata/usynth.json",
        additional_metadata={"risk_tier": "A+", "issuer": "SOL-UVIX-DAO"},
    )

    raw_bytes = SPLTokenDecoder.encode_mint_data(
        mint_authority=update_auth,
        supply=10_000_000_000,
        decimals=6,
        is_initialized=True,
        interest_bearing_config=ib_config,
        metadata=metadata,
    )

    mint_state = SPLTokenDecoder.decode_mint_data(raw_bytes, mint_pubkey=mint_pk)
    assert mint_state.is_token_2022 is True
    assert mint_state.interest_bearing_config is not None
    assert mint_state.interest_bearing_config.current_rate == 500
    assert mint_state.metadata is not None
    assert mint_state.metadata.name == "UVIX Synthetics"
    assert mint_state.metadata.symbol == "uSYNTH"
    assert mint_state.metadata.additional_metadata["risk_tier"] == "A+"

    # Accrued interest math
    # 10 days elapsed: accrued amount > principal
    accrued = ib_config.calculate_accrued_amount(principal=1_000_000, current_timestamp=now)
    assert accrued > 1_000_000


def test_token_2022_account_with_withheld_transfer_fee():
    mint_key = b58encode(b"\x81" * 32)
    owner_key = b58encode(b"\x82" * 32)

    raw_bytes = SPLTokenDecoder.encode_token_account_data(
        mint=mint_key,
        owner=owner_key,
        amount=250_000_000,
        transfer_fee_amount=15_000,
    )

    acc = SPLTokenDecoder.decode_token_account_data(raw_bytes, account_pubkey="TestHoldingAccount11111111111111111111111")
    assert acc.is_token_2022 is True
    assert acc.transfer_fee_amount == 15_000
    assert acc.amount == 250_000_000


def test_pumpfun_swap_simulation_math():
    state = PumpFunBondingCurveState(
        mint="PumpToken1111111111111111111111111111111111",
        bonding_curve="BondingCurve111111111111111111111111111111",
        associated_bonding_curve="AssocCurve111111111111111111111111111111",
        virtual_token_reserves=1_073_000_000_000_000,
        virtual_sol_reserves=30_000_000_000,  # 30 SOL
        real_token_reserves=793_100_000_000_000,
        real_sol_reserves=20_000_000_000,     # 20 SOL
        token_total_supply=1_000_000_000_000_000,
        complete=False,
        price_in_sol=0.000000028,
        market_cap_sol=28.0,
        progress_percent=23.53,
    )

    # Buy 1 SOL (1,000,000,000 lamports)
    buy_sim = PumpFunDecoder.simulate_buy(state, sol_amount_lamports=1_000_000_000, fee_bps=100)
    assert buy_sim["sol_in_lamports"] == 1_000_000_000
    assert buy_sim["sol_fee_lamports"] == 10_000_000  # 1% fee
    assert buy_sim["net_sol_lamports"] == 990_000_000
    assert buy_sim["tokens_out"] > 0
    assert buy_sim["new_virtual_sol_reserves"] == 30_000_000_000 + 990_000_000
    assert buy_sim["effective_price_sol"] > 0.0

    # Sell 1,000,000,000 tokens (1,000 tokens with 6 decimals)
    sell_sim = PumpFunDecoder.simulate_sell(state, token_amount=1_000_000_000, fee_bps=100)
    assert sell_sim["token_amount_in"] == 1_000_000_000
    assert sell_sim["gross_sol_lamports"] > 0
    assert sell_sim["sol_fee_lamports"] == (sell_sim["gross_sol_lamports"] * 100) // 10000
    assert sell_sim["net_sol_lamports"] == sell_sim["gross_sol_lamports"] - sell_sim["sol_fee_lamports"]


def test_raydium_swap_simulation_math():
    pool = RaydiumPoolState(
        pool_id="RaydiumPool111111111111111111111111111111111",
        base_mint="BaseMint11111111111111111111111111111111111",
        quote_mint="QuoteMint1111111111111111111111111111111111",
        base_vault="BaseVault1111111111111111111111111111111111",
        quote_vault="QuoteVault111111111111111111111111111111111",
        base_reserve=1_000_000_000_000,   # 1,000 tokens (9 dec)
        quote_reserve=100_000_000_000,   # 100,000 USDC (6 dec) -> Price ~ 100 USDC per token
        price=100.0,
        lp_supply=10_000_000_000,
    )

    # Swap 10 tokens (10 * 10^9) base -> quote
    swap_sim = RaydiumDecoder.simulate_swap(
        state=pool,
        amount_in=10_000_000_000,
        is_base_to_quote=True,
        fee_bps=25,  # 0.25% fee
        base_decimals=9,
        quote_decimals=6,
    )

    assert swap_sim["amount_in"] == 10_000_000_000
    assert swap_sim["fee_amount"] == 25_000_000
    assert swap_sim["amount_out"] > 0
    assert swap_sim["new_base_reserve"] == pool.base_reserve + 10_000_000_000
    assert swap_sim["new_quote_reserve"] == pool.quote_reserve - swap_sim["amount_out"]
    assert swap_sim["execution_price"] > 0.0


def test_leaksnipe_discord_embed_formatting():
    payload = {
        "protocol": "pumpfun-v1",
        "mint": "DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263",
        "price_in_sol": 0.000000045,
    }
    from sol_uvix.codec import encode_uvix_slug
    envelope = encode_uvix_slug(payload, source_platform="PumpFun-Feeder", target_platform="LeakSnipe-Discord")

    embed = UVIXEdgeBridge.format_leaksnipe_discord_embed(envelope)
    assert "📡 SOL-UVIX Telemetry" in embed["title"]
    assert embed["color"] == 0x14F195
    assert any(f["name"] == "Source" and "PumpFun-Feeder" in f["value"] for f in embed["fields"])
    assert any(f["name"] == "Target" and "LeakSnipe-Discord" in f["value"] for f in embed["fields"])
