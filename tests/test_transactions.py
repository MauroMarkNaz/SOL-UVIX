"""
Unit tests for Solana VersionedTransaction, Address Lookup Tables,
instruction decoding, and ComputeBudget priority fees.
"""

import pytest
import struct
import base64
from sol_uvix.transactions import (
    VersionedTransaction,
    MessageHeader,
    CompiledInstruction,
    AddressTableLookup,
    AddressLookupTableAccount,
    ComputeBudgetInfo,
    b58encode,
    b58decode,
    encode_compact_u16,
    decode_compact_u16,
    COMPUTE_BUDGET_PROGRAM_ID,
    ADDRESS_LOOKUP_TABLE_PROGRAM_ID,
    SYSTEM_PROGRAM_ID,
)
from sol_uvix.codec import decode_uvix_slug, compute_canonical_payload_hash


def test_base58_encoding_and_decoding():
    # Test zero padding
    zeros = b"\x00" * 32
    enc_zeros = b58encode(zeros)
    assert enc_zeros == "11111111111111111111111111111111"
    assert b58decode(enc_zeros) == zeros

    # Test random binary
    data = b"TestingBase58Encoding_Solana_UVIX_Bridge_2026!"
    encoded = b58encode(data)
    assert b58decode(encoded) == data

    # Test known Solana system program
    assert b58encode(b"\x00" * 32) == SYSTEM_PROGRAM_ID


def test_compact_u16_roundtrip():
    test_values = [0, 1, 63, 127, 128, 255, 300, 16383, 16384, 65535]
    for val in test_values:
        encoded = encode_compact_u16(val)
        decoded, offset = decode_compact_u16(encoded, 0)
        assert decoded == val
        assert offset == len(encoded)


def test_legacy_transaction_serialization_roundtrip():
    key1 = b58encode(b"\x01" * 32)
    key2 = b58encode(b"\x02" * 32)
    prog_id = b58encode(b"\x03" * 32)
    sig = b58encode(b"\x05" * 64)
    blockhash = b58encode(b"\x09" * 32)

    header = MessageHeader(
        num_required_signatures=1,
        num_readonly_signed_accounts=0,
        num_readonly_unsigned_accounts=1,
    )
    ix = CompiledInstruction(
        program_id_index=2,
        accounts=[0, 1],
        data=b"hello-legacy-tx",
    )

    tx = VersionedTransaction(
        version="legacy",
        signatures=[sig],
        header=header,
        account_keys=[key1, key2, prog_id],
        recent_blockhash=blockhash,
        instructions=[ix],
    )

    # Wire serialization & deserialization
    raw_wire = tx.serialize()
    deserialized = VersionedTransaction.from_bytes(raw_wire)

    assert deserialized.version == "legacy"
    assert deserialized.signatures == [sig]
    assert deserialized.header.num_required_signatures == 1
    assert deserialized.account_keys == [key1, key2, prog_id]
    assert deserialized.recent_blockhash == blockhash
    assert len(deserialized.instructions) == 1
    assert deserialized.instructions[0].data == b"hello-legacy-tx"

    # Decode instructions
    decoded_ixs = deserialized.decode_instructions()
    assert len(decoded_ixs) == 1
    d_ix = decoded_ixs[0]
    assert d_ix.program_id == prog_id
    assert len(d_ix.accounts) == 2
    assert d_ix.accounts[0].pubkey == key1
    assert d_ix.accounts[0].is_signer is True
    assert d_ix.accounts[0].is_writable is True
    assert d_ix.accounts[1].pubkey == key2
    assert d_ix.accounts[1].is_signer is False


def test_versioned_transaction_v0_with_alts():
    signer_key = b58encode(b"\x10" * 32)
    static_account = b58encode(b"\x11" * 32)
    lut_key = b58encode(b"\x12" * 32)
    sig = b58encode(b"\x15" * 64)
    blockhash = b58encode(b"\x19" * 32)

    # Create ALT table accounts
    alt_addr0 = b58encode(b"\x20" * 32)
    alt_addr1 = b58encode(b"\x21" * 32)
    alt_addr2 = b58encode(b"\x22" * 32)
    alt_addr3 = b58encode(b"\x23" * 32)

    header = MessageHeader(
        num_required_signatures=1,
        num_readonly_signed_accounts=0,
        num_readonly_unsigned_accounts=0,
    )
    ix = CompiledInstruction(
        program_id_index=1,
        accounts=[0, 2, 3],  # 0: signer_key, 2: first dynamic writable, 3: first dynamic readonly
        data=b"v0-swap-instruction",
    )
    lut_lookup = AddressTableLookup(
        account_key=lut_key,
        writable_indexes=[1],   # maps to alt_addr1
        readonly_indexes=[3],   # maps to alt_addr3
    )

    tx = VersionedTransaction(
        version=0,
        signatures=[sig],
        header=header,
        account_keys=[signer_key, static_account],
        recent_blockhash=blockhash,
        instructions=[ix],
        address_table_lookups=[lut_lookup],
    )

    raw_wire = tx.serialize()
    b64_wire = base64.b64encode(raw_wire).decode()
    deserialized = VersionedTransaction.from_base64(b64_wire)

    assert deserialized.version == 0
    assert deserialized.is_versioned is True
    assert len(deserialized.address_table_lookups) == 1
    assert deserialized.address_table_lookups[0].account_key == lut_key

    # Resolve addresses
    lookup_tables = {
        lut_key: [alt_addr0, alt_addr1, alt_addr2, alt_addr3]
    }
    resolved = deserialized.resolve_addresses(lookup_tables)

    # Expected order: static accounts, dynamic writable, dynamic readonly
    expected_resolved = [signer_key, static_account, alt_addr1, alt_addr3]
    assert resolved == expected_resolved

    decoded_ixs = deserialized.decode_instructions(lookup_tables)
    assert len(decoded_ixs) == 1
    d_ix = decoded_ixs[0]
    assert d_ix.program_id == static_account
    assert d_ix.accounts[0].pubkey == signer_key
    assert d_ix.accounts[0].is_signer is True
    assert d_ix.accounts[1].pubkey == alt_addr1
    assert d_ix.accounts[1].is_signer is False
    assert d_ix.accounts[1].is_writable is True
    assert d_ix.accounts[2].pubkey == alt_addr3
    assert d_ix.accounts[2].is_signer is False
    assert d_ix.accounts[2].is_writable is False


def test_address_lookup_table_account_decoding():
    auth_bytes = b"\x33" * 32
    auth_str = b58encode(auth_bytes)

    addr1_bytes = b"\x41" * 32
    addr2_bytes = b"\x42" * 32
    addr3_bytes = b"\x43" * 32

    # Pack 4B discriminator + 56B LookupTableMeta + 3*32B pubkeys
    buf = bytearray()
    buf.extend(struct.pack("<I", 1))  # ProgramState::LookupTable enum variant
    buf.extend(struct.pack("<QQB", 18446744073709551615, 290123456, 0))  # deactivation_slot (u64::MAX), last_extended_slot, start_idx
    buf.append(1)  # authority option: Some
    buf.extend(auth_bytes)  # 32B authority
    buf.extend(struct.pack("<H", 0))  # 2B padding
    # Align to 56B meta (4 + 8 + 8 + 1 + 1 + 32 + 2 = 56)
    assert len(buf) == 56

    buf.extend(addr1_bytes)
    buf.extend(addr2_bytes)
    buf.extend(addr3_bytes)

    alt_account = AddressLookupTableAccount.decode(bytes(buf), key="TestALTAccount1111111111111111111111111111")
    assert alt_account.key == "TestALTAccount1111111111111111111111111111"
    assert alt_account.last_extended_slot == 290123456
    assert alt_account.authority == auth_str
    assert len(alt_account.addresses) == 3
    assert alt_account.addresses[0] == b58encode(addr1_bytes)
    assert alt_account.addresses[1] == b58encode(addr2_bytes)
    assert alt_account.addresses[2] == b58encode(addr3_bytes)

    # Wrap to UVIX slug
    slug_env = alt_account.to_uvix_slug()
    assert slug_env.startswith("UVIX::") and slug_env.endswith("::END")
    decoded_slug = decode_uvix_slug(slug_env, verify_integrity=True)
    assert decoded_slug.raw_payload["data"]["authority"] == auth_str


def test_compute_budget_and_priority_fee_extraction():
    cu_limit_data = struct.pack("<BI", 2, 450_000)  # discriminator 2 = SetComputeUnitLimit
    cu_price_data = struct.pack("<BQ", 3, 50_000)   # discriminator 3 = SetComputeUnitPrice (50,000 micro-lamports / CU)

    payer = b58encode(b"\x51" * 32)
    compute_prog = COMPUTE_BUDGET_PROGRAM_ID

    header = MessageHeader(num_required_signatures=1, num_readonly_signed_accounts=0, num_readonly_unsigned_accounts=1)
    ix1 = CompiledInstruction(program_id_index=1, accounts=[], data=cu_limit_data)
    ix2 = CompiledInstruction(program_id_index=1, accounts=[], data=cu_price_data)

    tx = VersionedTransaction(
        version=0,
        signatures=[b58encode(b"\x55" * 64)],
        header=header,
        account_keys=[payer, compute_prog],
        recent_blockhash=b58encode(b"\x59" * 32),
        instructions=[ix1, ix2],
    )

    cb_info = tx.extract_compute_budget()
    assert cb_info.unit_limit == 450_000
    assert cb_info.unit_price_micro_lamports == 50_000

    # 450,000 * 50,000 / 1,000,000 = 22,500 lamports
    assert cb_info.priority_fee_lamports == 22_500
    assert cb_info.priority_fee_sol == 0.0000225

    # Check decoded instruction labels
    decoded_ixs = tx.decode_instructions()
    assert decoded_ixs[0].parsed_type == "ComputeBudget::SetComputeUnitLimit"
    assert decoded_ixs[0].parsed_info == {"units": 450_000}
    assert decoded_ixs[1].parsed_type == "ComputeBudget::SetComputeUnitPrice"
    assert decoded_ixs[1].parsed_info == {"micro_lamports": 50_000}


def test_versioned_transaction_uvix_slug_roundtrip():
    tx = VersionedTransaction(
        version=0,
        signatures=[b58encode(b"\x77" * 64)],
        header=MessageHeader(num_required_signatures=1, num_readonly_signed_accounts=0, num_readonly_unsigned_accounts=0),
        account_keys=[b58encode(b"\x71" * 32)],
        recent_blockhash=b58encode(b"\x72" * 32),
        instructions=[],
    )

    envelope = tx.to_uvix_slug()
    assert envelope.startswith("UVIX::")
    assert envelope.endswith("::END")

    decoded = decode_uvix_slug(envelope, verify_integrity=True)
    assert decoded.source_platform == "Solana-Tx-Engine"
    assert decoded.raw_payload["protocol"] == "solana-transaction-v0"
    assert decoded.payload_hash == compute_canonical_payload_hash(decoded.raw_payload)
