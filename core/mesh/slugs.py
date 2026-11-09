"""
UVIX Slug Topology & URI Resolution
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Implements the canonical UVIX naming canon, entity hierarchy slugs,
manifest resolver, and message class ladder per the UVIX White Paper
(9 November 2026) and UVIX Protocol Specification v0.1.

Expansion: UVIX = Universal-Inter-Cross-Compatability (spelling canonical).
"""

from enum import Enum
from typing import Dict, Any, Optional, Tuple, List
import re
from dataclasses import dataclass


class MessageClass(str, Enum):
    """
    Message class ladder.
    Receiving information MUST NOT implicitly grant permission to act.
    """
    OBSERVE = "OBSERVE"      # A fact was seen. Grants nothing.
    QUERY = "QUERY"          # A question was asked. Grants nothing.
    PROPOSE = "PROPOSE"      # An action was suggested. Grants nothing.
    AUTHORIZE = "AUTHORIZE"  # A principal approved the action.
    EXECUTE = "EXECUTE"      # The action was carried out.
    ATTEST = "ATTEST"        # The result was recorded as evidence.


# Allowed state transitions in the ladder
ALLOWED_TRANSITIONS: Dict[MessageClass, List[MessageClass]] = {
    MessageClass.OBSERVE: [MessageClass.QUERY, MessageClass.PROPOSE],
    MessageClass.QUERY: [MessageClass.PROPOSE, MessageClass.OBSERVE],
    MessageClass.PROPOSE: [MessageClass.AUTHORIZE],
    MessageClass.AUTHORIZE: [MessageClass.EXECUTE],
    MessageClass.EXECUTE: [MessageClass.ATTEST],
    MessageClass.ATTEST: [],
}


class ProtocolStackLayer(str, Enum):
    """The 7-layer UVIX protocol stack. Semantics survive transport swaps."""
    UVIX_0_PHYSICAL = "PHYSICAL"      # Loopback, LAN, Internet, fiber
    UVIX_1_TRANSPORT = "TRANSPORT"    # SHM, QUIC, TCP, HTTP, MCP, private IP
    UVIX_2_ENVELOPE = "ENVELOPE"      # UVIX-RI-1.0: identity, trace, type, payload
    UVIX_3_CAPABILITY = "CAPABILITY"  # Discover, query, invoke, subscribe
    UVIX_4_STATE = "STATE"            # Version, freshness, ownership, replication
    UVIX_5_TRUST = "TRUST"            # Identity, signatures, provenance, evidence
    UVIX_6_POLICY = "POLICY"          # Authorization, deadlines, constraints


class ContractType(str, Enum):
    """The Six Contracts of UVIX Interoperation Without Assimilation."""
    IDENTITY = "Identity"
    CAPABILITY = "Capability"
    ENVELOPE = "Envelope"
    TRANSPORT = "Transport"
    STATE = "State"
    TRUST = "Trust"


# Canonical entity hierarchy slugs
SLUG_SOLANA_MEMO = "UVIX.PERSISTENCE.SOLANA_MEMO"
SLUG_GATEWAY_APEX = "UVIX.GATEWAY"

CANONICAL_D1_ALIASES = {
    "GOOGLE": "UVIX.DATA.D1.GOOGLE",
    "SCALPER": "UVIX.DATA.D1.SCALPER",
    "OPPONENTS": "UVIX.DATA.D1.OPPONENTS",
    "LEAKSNIPE": "UVIX.DATA.D1.LEAKSNIPE",
    "MEM": "UVIX.DATA.D1.MEM",
    "WECRYPTO": "UVIX.DATA.D1.WECRYPTO",
    "GTO": "UVIX.DATA.D1.GTO",
    "TRUFFLES": "UVIX.DATA.D1.TRUFFLES",
}

CANONICAL_ORACLE_SOURCES = {
    "PYTH": "UVIX.DATA.ORACLE.PYTH",
    "DIA": "UVIX.DATA.ORACLE.DIA",
    "BRTI": "UVIX.DATA.ORACLE.BRTI",
}

CANONICAL_MESH_NODES = {
    "MUSE": "UVIX.MESH.MUSE",
    "TUF": "UVIX.MESH.TUF",
    "GLAP": "UVIX.MESH.GLAP",
    "TRUFFLE": "UVIX.MESH.TRUFFLE",
}


@dataclass(frozen=True)
class UvixURI:
    """
    Parsed canonical UVIX URI: uvix:<domain>:<system>[:<resource>]
    Identity is strictly independent of instance location and transport.
    """
    domain: str
    system: str
    resource: Optional[str] = None

    def __str__(self) -> str:
        if self.resource:
            return f"uvix:{self.domain}:{self.system}:{self.resource}"
        return f"uvix:{self.domain}:{self.system}"

    @classmethod
    def parse(cls, uri_str: str) -> "UvixURI":
        if not uri_str.startswith("uvix:"):
            raise ValueError(f"Invalid UVIX URI scheme (must start with 'uvix:'): {uri_str}")
        parts = uri_str.split(":")
        if len(parts) == 3:
            return cls(domain=parts[1], system=parts[2], resource=None)
        elif len(parts) == 4:
            return cls(domain=parts[1], system=parts[2], resource=parts[3])
        else:
            raise ValueError(f"Malformed UVIX URI (expected 3 or 4 parts): {uri_str}")


class SlugRegistry:
    """
    Authoritative slug and URI registry resolving against the live manifest.
    Default manifest resolver is uvix:router:universal_mesh_v1.
    """

    def __init__(self, manifest_uri: str = "uvix:router:universal_mesh_v1"):
        self.manifest_uri = manifest_uri
        self._live_uris: Dict[str, Dict[str, Any]] = {}
        self._hierarchy_slugs: Dict[str, str] = {}
        self._init_defaults()

    def _init_defaults(self):
        # Register core hierarchy slugs
        self.register_slug(SLUG_SOLANA_MEMO, "uvix:persistence:solana_memo:anchor")
        self.register_slug(SLUG_GATEWAY_APEX, "uvix:apex")
        for alias, slug in CANONICAL_D1_ALIASES.items():
            self.register_slug(slug, f"uvix:data:d1:{alias.lower()}")
        for src, slug in CANONICAL_ORACLE_SOURCES.items():
            self.register_slug(slug, f"uvix:oracle:{src.lower()}")
        for node, slug in CANONICAL_MESH_NODES.items():
            self.register_slug(slug, f"uvix:mesh:{node.lower()}")

    def register_slug(self, hierarchy_slug: str, canonical_uri: str, metadata: Optional[Dict[str, Any]] = None):
        self._hierarchy_slugs[hierarchy_slug] = canonical_uri
        self._live_uris[canonical_uri] = {
            "slug": hierarchy_slug,
            "metadata": metadata or {},
            "active": True
        }

    def resolve_slug(self, hierarchy_slug: str) -> Optional[str]:
        """Resolves a hierarchy slug (e.g. UVIX.DATA.D1.GOOGLE) to its canonical URI."""
        return self._hierarchy_slugs.get(hierarchy_slug)

    def is_live_in_manifest(self, uri_str: str) -> bool:
        """
        Identities resolve through the live manifest;
        one absent from the manifest does not resolve and must not be treated as live.
        """
        entry = self._live_uris.get(uri_str)
        return bool(entry and entry.get("active", False))

    def validate_transition(self, current: MessageClass, next_class: MessageClass) -> bool:
        """Enforces that message classes follow the explicit ladder."""
        allowed = ALLOWED_TRANSITIONS.get(current, [])
        return next_class in allowed
