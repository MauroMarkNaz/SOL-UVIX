import pytest
import json
from sol_uvix.codec import (
    encode_uvix_slug,
    decode_uvix_slug,
    compute_canonical_payload_hash,
    UVIXIntegrityError,
    UVIXFormatError,
    UVIXSlug,
)


def test_slug_encoding_and_decoding_roundtrip():
    payload = {
        "mint": "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v",
        "symbol": "USDC",
        "decimals": 6,
        "features": ["spl-token", "verified"],
    }
    envelope = encode_uvix_slug(
        payload,
        source_platform="Solana-Test",
        target_platform="UVIX-Agent",
        compatibility_layer="solana-test-v1",
    )

    assert envelope.startswith("UVIX::")
    assert envelope.endswith("::END")

    decoded = decode_uvix_slug(envelope)
    assert isinstance(decoded, UVIXSlug)
    assert decoded.source_platform == "Solana-Test"
    assert decoded.target_platform == "UVIX-Agent"
    assert decoded.raw_payload == payload

    # Verify deterministic hash
    expected_hash = compute_canonical_payload_hash(payload)
    assert decoded.payload_hash == expected_hash


def test_tampered_payload_raises_integrity_error():
    payload = {"account": "Alice", "balance_sol": 100.0}
    envelope = encode_uvix_slug(payload)

    # Tamper with the internal payload in base64
    import base64
    b64_str = envelope[6:-5]
    slug_dict = json.loads(base64.b64decode(b64_str.encode()).decode())
    slug_dict["raw_payload"]["balance_sol"] = 999999.0  # Tampered!

    tampered_b64 = base64.b64encode(json.dumps(slug_dict).encode()).decode()
    tampered_envelope = f"UVIX::{tampered_b64}::END"

    with pytest.raises(UVIXIntegrityError):
        decode_uvix_slug(tampered_envelope, verify_integrity=True)


def test_malformed_envelope_framing():
    with pytest.raises(UVIXFormatError):
        decode_uvix_slug("INVALID_PREFIX_data_INVALID_SUFFIX")
