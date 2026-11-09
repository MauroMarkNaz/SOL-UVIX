"""
Unit and Integration Tests for SolanaCLIWrapper
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Tests CLI interaction, parsing, and canonical UVIX-RI-1.0 slug framing.
"""

import json
import pytest
from unittest.mock import MagicMock, patch
from sol_uvix.cli_wrapper import SolanaCLIWrapper, SolanaCLIError
from sol_uvix.codec import decode_uvix_slug, UVIXIntegrityError


def test_cli_wrapper_version_parsing():
    wrapper = SolanaCLIWrapper(cli_path="solana")
    sample_output = "solana-cli 4.3.2 (src:4b44ad97; feat:c9ad34d2, client:Agave)"

    with patch.object(wrapper, "execute_raw", return_value=(0, sample_output, "")):
        info = wrapper.get_version()
        assert info["version"] == "4.3.2"
        assert info["client"] == "Agave"
        assert info["commit"] == "4b44ad97"
        assert info["feature_set"] == "c9ad34d2"


def test_cli_wrapper_address_parsing():
    wrapper = SolanaCLIWrapper(cli_path="solana")
    mock_address = "EkYRoqE35go8XdHCBrSmeguUkiKU1vXQgbusYd9PrBHr"

    with patch.object(wrapper, "execute_raw", return_value=(0, mock_address + "\n", "")):
        addr = wrapper.get_address()
        assert addr == mock_address

        slug = wrapper.get_address_slug()
        decoded = decode_uvix_slug(slug, verify_integrity=True)
        assert decoded.source_platform == "Solana-CLI"
        assert decoded.raw_payload["data"]["address"] == mock_address


def test_cli_wrapper_config_parsing():
    wrapper = SolanaCLIWrapper(cli_path="solana")
    mock_config_output = (
        "Config File: /home/user/.config/solana/cli/config.yml\n"
        "RPC URL: https://api.devnet.solana.com\n"
        "WebSocket URL: wss://api.devnet.solana.com/ (computed)\n"
        "Keypair Path: /home/user/.config/solana/id.json\n"
        "Commitment: confirmed\n"
    )

    with patch.object(wrapper, "execute_raw", return_value=(0, mock_config_output, "")):
        cfg = wrapper.get_config()
        assert cfg["rpc_url"] == "https://api.devnet.solana.com"
        assert cfg["keypair_path"] == "/home/user/.config/solana/id.json"
        assert cfg["commitment"] == "confirmed"

        slug = wrapper.get_config_slug()
        decoded = decode_uvix_slug(slug, verify_integrity=True)
        assert decoded.raw_payload["type"] == "config"
        assert decoded.raw_payload["data"]["rpc_url"] == "https://api.devnet.solana.com"


def test_cli_wrapper_balance_json():
    wrapper = SolanaCLIWrapper(cli_path="solana")
    mock_json = json.dumps({"lamports": 1500000000})

    with patch.object(wrapper, "execute_raw", return_value=(0, mock_json, "")), \
         patch.object(wrapper, "get_address", return_value="TestPubkey11111111111111111111111111111111"):
        res = wrapper.get_balance()
        assert res["lamports"] == 1500000000
        assert res["sol"] == 1.5

        slug = wrapper.get_balance_slug()
        decoded = decode_uvix_slug(slug, verify_integrity=True)
        assert decoded.raw_payload["type"] == "balance"
        assert decoded.raw_payload["data"]["sol"] == 1.5


def test_cli_wrapper_airdrop_slug():
    wrapper = SolanaCLIWrapper(cli_path="solana")
    with patch.object(wrapper, "execute_raw", return_value=(0, "Signature: 5VERv8NMvzbJMEkV8xnr5QMuMW2RKq69EPNA4XCH9qWamQYTqia3pHPHS6SvhCB84jFF5F5FBRe2UV69qz221Ufq", "")), \
         patch.object(wrapper, "get_address", return_value="RecipientAddress123"):
        result = wrapper.request_airdrop(1.0)
        assert result["success"] is True
        assert result["amount_sol"] == 1.0

        slug = wrapper.request_airdrop_slug(1.0)
        decoded = decode_uvix_slug(slug, verify_integrity=True)
        assert decoded.raw_payload["type"] == "airdrop"
        assert decoded.raw_payload["data"]["amount_sol"] == 1.0


def test_cli_wrapper_cluster_status():
    wrapper = SolanaCLIWrapper(cli_path="solana")
    with patch.object(wrapper, "get_config", return_value={"rpc_url": "https://api.devnet.solana.com", "commitment": "confirmed"}), \
         patch.object(wrapper, "get_cluster_version", return_value="4.4.0"), \
         patch.object(wrapper, "get_epoch_info", return_value={"epoch": 1192, "blockHeight": 502395619}):
        status = wrapper.get_cluster_status()
        assert status["cluster_version"] == "4.4.0"
        assert status["epoch_info"]["epoch"] == 1192

        slug = wrapper.get_cluster_status_slug()
        decoded = decode_uvix_slug(slug, verify_integrity=True)
        assert decoded.raw_payload["type"] == "cluster_status"
        assert decoded.raw_payload["data"]["cluster_version"] == "4.4.0"


def test_cli_wrapper_live_smoke():
    """Live smoke test using actual installed Solana CLI binary."""
    wrapper = SolanaCLIWrapper()
    version_info = wrapper.get_version()
    assert version_info["version"] is not None
    assert "Agave" in version_info["client"] or "Solana" in version_info["client"]

    config = wrapper.get_config()
    assert "devnet" in config["rpc_url"] or "solana.com" in config["rpc_url"]

    try:
        addr = wrapper.get_address()
        assert len(addr) > 30

        slug = wrapper.get_balance_slug()
        decoded = decode_uvix_slug(slug, verify_integrity=True)
        assert decoded.raw_payload["type"] == "balance"
    except SolanaCLIError as e:
        if "No default signer" in str(e) or "No such file" in str(e):
            pytest.skip("No default signer keypair configured on test host (Rule 0 key safety).")
        raise
