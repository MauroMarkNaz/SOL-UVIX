"""
Unit tests for UVIX Slug Topology & URI Resolution
"""

import pytest
from core.mesh.slugs import (
    UvixURI,
    SlugRegistry,
    MessageClass,
    ProtocolStackLayer,
    ContractType,
    SLUG_SOLANA_MEMO,
    SLUG_GATEWAY_APEX,
    CANONICAL_D1_ALIASES,
    CANONICAL_ORACLE_SOURCES,
    CANONICAL_MESH_NODES,
)


def test_uvix_uri_parsing():
    uri = UvixURI.parse("uvix:agent:truffle")
    assert uri.domain == "agent"
    assert uri.system == "truffle"
    assert uri.resource is None
    assert str(uri) == "uvix:agent:truffle"

    uri_res = UvixURI.parse("uvix:oracle:pyth:btc_usd")
    assert uri_res.domain == "oracle"
    assert uri_res.system == "pyth"
    assert uri_res.resource == "btc_usd"
    assert str(uri_res) == "uvix:oracle:pyth:btc_usd"


def test_invalid_uvix_uri():
    with pytest.raises(ValueError, match="Invalid UVIX URI scheme"):
        UvixURI.parse("http://example.com")

    with pytest.raises(ValueError, match="Malformed UVIX URI"):
        UvixURI.parse("uvix:single")


def test_slug_registry_defaults():
    registry = SlugRegistry()

    # Hierarchy slugs resolve to canonical URIs
    assert registry.resolve_slug(SLUG_SOLANA_MEMO) == "uvix:persistence:solana_memo:anchor"
    assert registry.resolve_slug(SLUG_GATEWAY_APEX) == "uvix:apex"
    assert registry.resolve_slug(CANONICAL_D1_ALIASES["GOOGLE"]) == "uvix:data:d1:google"
    assert registry.resolve_slug(CANONICAL_ORACLE_SOURCES["PYTH"]) == "uvix:oracle:pyth"
    assert registry.resolve_slug(CANONICAL_MESH_NODES["MUSE"]) == "uvix:mesh:muse"

    # Manifest live checks
    assert registry.is_live_in_manifest("uvix:apex") is True
    assert registry.is_live_in_manifest("uvix:data:d1:google") is True
    assert registry.is_live_in_manifest("uvix:ghost:entity") is False


def test_message_class_ladder_transitions():
    registry = SlugRegistry()

    # Valid transitions
    assert registry.validate_transition(MessageClass.OBSERVE, MessageClass.PROPOSE) is True
    assert registry.validate_transition(MessageClass.PROPOSE, MessageClass.AUTHORIZE) is True
    assert registry.validate_transition(MessageClass.AUTHORIZE, MessageClass.EXECUTE) is True
    assert registry.validate_transition(MessageClass.EXECUTE, MessageClass.ATTEST) is True

    # Invalid transitions (Observation is not authority)
    assert registry.validate_transition(MessageClass.OBSERVE, MessageClass.EXECUTE) is False
    assert registry.validate_transition(MessageClass.PROPOSE, MessageClass.EXECUTE) is False
    assert registry.validate_transition(MessageClass.QUERY, MessageClass.EXECUTE) is False
