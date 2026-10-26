"""
SOL-UVIX Command Line Interface
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
CLI utility to inspect, encode, decode, and verify UVIX envelopes.
"""

import sys
import json
import argparse
from .codec import encode_uvix_slug, decode_uvix_slug, UVIXIntegrityError, UVIXFormatError
from .client import SolanaUVIXClient


def main():
    parser = argparse.ArgumentParser(
        prog="sol-uvix",
        description="Solana Stack and UVIX-RI-1.0 Interoperability Protocol CLI",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # Encode command
    encode_parser = subparsers.add_parser("encode", help="Encode JSON file or string into UVIX envelope")
    encode_parser.add_argument("input", help="JSON string or path to JSON file")
    encode_parser.add_argument("--source", default="Solana-CLI", help="Source platform identifier")
    encode_parser.add_argument("--target", default="UVIX-Mesh", help="Target platform identifier")

    # Decode command
    decode_parser = subparsers.add_parser("decode", help="Decode and verify UVIX envelope")
    decode_parser.add_argument("envelope", help="UVIX::<base64>::END envelope string")

    # Account command
    acc_parser = subparsers.add_parser("account", help="Query Solana account and output UVIX slug")
    acc_parser.add_argument("pubkey", help="Solana public key (base58)")
    acc_parser.add_argument("--rpc", default="https://api.mainnet-beta.solana.com", help="RPC URL")

    args = parser.parse_args()

    if args.command == "encode":
        try:
            try:
                with open(args.input, "r", encoding="utf-8") as f:
                    payload = json.load(f)
            except Exception:
                payload = json.loads(args.input)

            envelope = encode_uvix_slug(payload, source_platform=args.source, target_platform=args.target)
            print(envelope)
        except Exception as e:
            print(f"Error encoding UVIX slug: {e}", file=sys.stderr)
            sys.exit(1)

    elif args.command == "decode":
        try:
            slug = decode_uvix_slug(args.envelope)
            print(json.dumps(slug.to_dict(), indent=2))
        except UVIXIntegrityError as e:
            print(f"INTEGRITY ERROR: {e}", file=sys.stderr)
            sys.exit(2)
        except UVIXFormatError as e:
            print(f"FORMAT ERROR: {e}", file=sys.stderr)
            sys.exit(3)
        except Exception as e:
            print(f"Error decoding: {e}", file=sys.stderr)
            sys.exit(1)

    elif args.command == "account":
        try:
            client = SolanaUVIXClient(rpc_url=args.rpc)
            slug = client.get_account_uvix_slug(args.pubkey)
            if slug:
                print(slug)
            else:
                print(f"Account {args.pubkey} not found", file=sys.stderr)
                sys.exit(1)
        except Exception as e:
            print(f"RPC Error: {e}", file=sys.stderr)
            sys.exit(1)


if __name__ == "__main__":
    main()
