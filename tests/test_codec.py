try:
    import pytest
except ImportError:
    class _MockPytest:
        @staticmethod
        def raises(expected_exception):
            import contextlib
            @contextlib.contextmanager
            def _cm():
                try:
                    yield
                except expected_exception:
                    pass
                else:
                    raise AssertionError(f"Expected exception {expected_exception.__name__} was not raised")
            return _cm()
    pytest = _MockPytest()

import json
import base64
from sol_uvix.codec import (
    encode_uvix_slug,
    decode_uvix_slug,
    compute_canonical_payload_hash,
    UVIXIntegrityError,
    UVIXFormatError,
    UVIXSlug,
)
from core.protocol.codec import (
    encode_uvix_slug as core_encode_uvix_slug,
    decode_uvix_slug as core_decode_uvix_slug,
    compute_canonical_payload_hash as core_compute_hash,
    UVIXSlug as CoreUVIXSlug,
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


def test_core_protocol_codec_parity():
    """Verify core.protocol.codec behaves identically to sol_uvix.codec."""
    payload = {"network": "solana", "slot": 284910283, "active": True}
    env_core = core_encode_uvix_slug(payload, source_platform="NodeA", target_platform="NodeB")
    env_sol = encode_uvix_slug(payload, source_platform="NodeA", target_platform="NodeB")
    assert env_core == env_sol

    dec_core = core_decode_uvix_slug(env_sol, verify_integrity=True)
    dec_sol = decode_uvix_slug(env_core, verify_integrity=True)
    assert isinstance(dec_core, CoreUVIXSlug)
    assert dec_core.raw_payload == dec_sol.raw_payload
    assert dec_core.payload_hash == dec_sol.payload_hash


def test_normative_vectors_annex_a():
    """
    Verify test vectors from UVIX-RI-1.0 Annex A:
    V1: Empty payload
    V2: Solana slot snapshot
    V3: Token record
    """
    # Vector V1
    v1_payload = {}
    v1_hash = "44136fa355b3678a1146ad16f7e8649e94fb4fc21fe77e8310c060f61caaff8a"
    v1_envelope = (
        "UVIX::eyJjb21wYXRpYmlsaXR5X2xheWVyIjoidXZpeC12ZWN0b3JzLXYxIiwicGF5bG9hZF9oYXNoIjoi"
        "NDQxMzZmYTM1NWIzNjc4YTExNDZhZDE2ZjdlODY0OWU5NGZiNGZjMjFmZTc3ZTgzMTBjMDYwZjYxY2FhZm"
        "Y4YSIsInByb3RvY29sX3ZlcnNpb24iOiIxLjAiLCJyYXdfcGF5bG9hZCI6e30sInNvdXJjZV9wbGF0Zm9y"
        "bSI6IlZlY3RvckdlbiIsInRhcmdldF9wbGF0Zm9ybSI6IlZlY3RvckdlbiJ9::END"
    )
    assert compute_canonical_payload_hash(v1_payload) == v1_hash
    dec_v1 = decode_uvix_slug(v1_envelope, verify_integrity=True)
    assert dec_v1.raw_payload == v1_payload
    assert dec_v1.payload_hash == v1_hash

    # Vector V2
    v2_payload = {
        "network": "solana",
        "slot": 284910283,
        "accounts": ["TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA"],
        "active": True,
    }
    v2_hash = "27aa6168b06a9a889f21c2d66515dbba7d9ffe023677dc5841dd21f4495cb86a"
    v2_envelope = (
        "UVIX::eyJjb21wYXRpYmlsaXR5X2xheWVyIjoidXZpeC12ZWN0b3JzLXYxIiwicGF5bG9hZF9oYXNoIjoi"
        "MjdhYTYxNjhiMDZhOWE4ODlmMjFjMmQ2NjUxNWRiYmE3ZDlmZmUwMjM2NzdkYzU4NDFkZDIxZjQ0OTVjYj"
        "g2YSIsInByb3RvY29sX3ZlcnNpb24iOiIxLjAiLCJyYXdfcGF5bG9hZCI6eyJhY2NvdW50cyI6WyJUb2tl"
        "bmtlZ1FmZVp5aU53QUpiTmJHS1BGWENXdUJ2ZjlTczYyM1ZRNURBIl0sImFjdGl2ZSI6dHJ1ZSwibmV0d2"
        "9yayI6InNvbGFuYSIsInNsb3QiOjI4NDkxMDI4M30sInNvdXJjZV9wbGF0Zm9ybSI6IlZlY3RvckdlbiIs"
        "InRhcmdldF9wbGF0Zm9ybSI6IlZlY3RvckdlbiJ9::END"
    )
    assert compute_canonical_payload_hash(v2_payload) == v2_hash
    dec_v2 = decode_uvix_slug(v2_envelope, verify_integrity=True)
    assert dec_v2.raw_payload == v2_payload
    assert dec_v2.payload_hash == v2_hash

    # Vector V3
    v3_payload = {
        "mint": "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v",
        "symbol": "USDC",
        "decimals": 6,
        "features": ["spl-token", "verified"],
    }
    v3_hash = "6225c0870e098c9e5606d1c7c2e8a100e820cf0cb51a6c4e9f7628526fd2a0df"
    v3_envelope = (
        "UVIX::eyJjb21wYXRpYmlsaXR5X2xheWVyIjoidXZpeC12ZWN0b3JzLXYxIiwicGF5bG9hZF9oYXNoIjoi"
        "NjIyNWMwODcwZTA5OGM5ZTU2MDZkMWM3YzJlOGExMDBlODIwY2YwY2I1MWE2YzRlOWY3NjI4NTI2ZmQyYT"
        "BkZiIsInByb3RvY29sX3ZlcnNpb24iOiIxLjAiLCJyYXdfcGF5bG9hZCI6eyJkZWNpbWFscyI6NiwiZmVh"
        "dHVyZXMiOlsic3BsLXRva2VuIiwidmVyaWZpZWQiXSwibWludCI6IkVQakZXZGQ1QXVmcVNTcWVNMnFOMX"
        "h6eWJhcEM4RzR3RUdHa1p3eVREdDF2Iiwic3ltYm9sIjoiVVNEQyJ9LCJzb3VyY2VfcGxhdGZvcm0iOiJW"
        "ZWN0b3JHZW4iLCJ0YXJnZXRfcGxhdGZvcm0iOiJWZWN0b3JHZW4ifQ==::END"
    )
    assert compute_canonical_payload_hash(v3_payload) == v3_hash
    dec_v3 = decode_uvix_slug(v3_envelope, verify_integrity=True)
    assert dec_v3.raw_payload == v3_payload
    assert dec_v3.payload_hash == v3_hash


def test_slug_specification_poh_compatibility():
    """
    Verify compatibility with the slug specification for Proof-of-History state:
    seq, ts, poh_slot, prev_state_hash.
    """
    payload = {
        "seq": 42,
        "ts": 1731162440.123,
        "poh_slot": 284910283,
        "prev_state_hash": "44136fa355b3678a1146ad16f7e8649e94fb4fc21fe77e8310c060f61caaff8a",
    }
    envelope = encode_uvix_slug(
        payload,
        source_platform="solana-feeder",
        target_platform="uvix-mesh",
        compatibility_layer="solana-poh-v1",
    )
    assert envelope.startswith("UVIX::")
    assert envelope.endswith("::END")

    decoded = decode_uvix_slug(envelope, verify_integrity=True)
    assert decoded.raw_payload == payload
    assert decoded.raw_payload["seq"] == 42
    assert decoded.raw_payload["ts"] == 1731162440.123
    assert decoded.raw_payload["poh_slot"] == 284910283
    assert decoded.raw_payload["prev_state_hash"] == payload["prev_state_hash"]
    assert decoded.payload_hash == compute_canonical_payload_hash(payload)

    # Test genesis state
    genesis_payload = {
        "seq": 0,
        "ts": 1731160000,
        "poh_slot": 284900000,
        "prev_state_hash": "GENESIS",
    }
    gen_envelope = encode_uvix_slug(genesis_payload)
    gen_decoded = decode_uvix_slug(gen_envelope, verify_integrity=True)
    assert gen_decoded.raw_payload == genesis_payload
    assert gen_decoded.raw_payload["seq"] == 0
    assert gen_decoded.raw_payload["prev_state_hash"] == "GENESIS"


def test_tampered_payload_raises_integrity_error():
    payload = {"account": "Alice", "balance_sol": 100.0}
    envelope = encode_uvix_slug(payload)

    # Tamper with the internal payload in base64
    b64_str = envelope[6:-5]
    slug_dict = json.loads(base64.b64decode(b64_str.encode()).decode())
    slug_dict["raw_payload"]["balance_sol"] = 999999.0  # Tampered!

    tampered_b64 = base64.b64encode(json.dumps(slug_dict).encode()).decode()
    tampered_envelope = f"UVIX::{tampered_b64}::END"

    with pytest.raises(UVIXIntegrityError):
        decode_uvix_slug(tampered_envelope, verify_integrity=True)


def test_tampered_hash_raises_integrity_error():
    payload = {"account": "Alice", "balance_sol": 100.0}
    envelope = encode_uvix_slug(payload)

    b64_str = envelope[6:-5]
    slug_dict = json.loads(base64.b64decode(b64_str.encode()).decode())
    slug_dict["payload_hash"] = "0" * 64  # Invalid hash

    tampered_b64 = base64.b64encode(json.dumps(slug_dict).encode()).decode()
    tampered_envelope = f"UVIX::{tampered_b64}::END"

    with pytest.raises(UVIXIntegrityError):
        decode_uvix_slug(tampered_envelope, verify_integrity=True)


def test_malformed_envelope_framing():
    with pytest.raises(UVIXFormatError):
        decode_uvix_slug("INVALID_PREFIX_data_INVALID_SUFFIX")

    with pytest.raises(UVIXFormatError):
        decode_uvix_slug("UVIX::bad_suffix")

    with pytest.raises(UVIXFormatError):
        decode_uvix_slug("bad_prefix::END")

    with pytest.raises(UVIXFormatError):
        decode_uvix_slug(12345)


def test_missing_required_fields_raises_format_error():
    payload = {"item": "val"}
    envelope = encode_uvix_slug(payload)
    b64_str = envelope[6:-5]
    slug_dict = json.loads(base64.b64decode(b64_str.encode()).decode())

    for req_field in ["protocol_version", "source_platform", "target_platform", "payload_hash", "compatibility_layer", "raw_payload"]:
        tampered_dict = dict(slug_dict)
        del tampered_dict[req_field]
        bad_b64 = base64.b64encode(json.dumps(tampered_dict).encode()).decode()
        bad_envelope = f"UVIX::{bad_b64}::END"
        with pytest.raises(UVIXFormatError):
            decode_uvix_slug(bad_envelope)


if __name__ == "__main__":
    print("Running tests directly under Python...")
    test_slug_encoding_and_decoding_roundtrip()
    print("✓ test_slug_encoding_and_decoding_roundtrip passed")
    test_core_protocol_codec_parity()
    print("✓ test_core_protocol_codec_parity passed")
    test_normative_vectors_annex_a()
    print("✓ test_normative_vectors_annex_a passed")
    test_slug_specification_poh_compatibility()
    print("✓ test_slug_specification_poh_compatibility passed")
    test_tampered_payload_raises_integrity_error()
    print("✓ test_tampered_payload_raises_integrity_error passed")
    test_tampered_hash_raises_integrity_error()
    print("✓ test_tampered_hash_raises_integrity_error passed")
    test_malformed_envelope_framing()
    print("✓ test_malformed_envelope_framing passed")
    test_missing_required_fields_raises_format_error()
    print("✓ test_missing_required_fields_raises_format_error passed")
    print("\nALL 8 TESTS PASSED DIRECTLY UNDER PYTHON!")
