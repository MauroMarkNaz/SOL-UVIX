"""
UVIX Edge Bridge & Multi-Agent Dispatcher
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Dispatches UVIX slugs across Cloudflare Edge routers (uvix.leaksnipe.win),
Tailscale zero-trust mesh nodes, and cross-agent event loops.
"""

import requests
from typing import Dict, Any, Optional
from .codec import encode_uvix_slug, decode_uvix_slug, UVIXSlug
from .models import AgentHandoffPayload

DEFAULT_GATEWAY_URL = "https://uvix.leaksnipe.win/uvix"


class UVIXEdgeBridge:
    """Bridge for broadcasting and receiving UVIX envelopes across mesh endpoints."""

    def __init__(self, gateway_url: Optional[str] = None, timeout: float = 8.0):
        self.gateway_url = gateway_url or DEFAULT_GATEWAY_URL
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update({
            "Content-Type": "application/json",
            "User-Agent": "SOL-UVIX-Bridge/1.0",
        })

    def dispatch_slug(self, envelope: str, destination_url: Optional[str] = None) -> Dict[str, Any]:
        """
        Dispatches a raw UVIX envelope string to the edge gateway.
        """
        target = destination_url or self.gateway_url
        payload = {"envelope": envelope}
        resp = self.session.post(target, json=payload, timeout=self.timeout)
        resp.raise_for_status()
        return resp.json()

    def dispatch_handoff(self,
                         source_agent: str,
                         target_agent: str,
                         intent: str,
                         action_type: str,
                         context: Dict[str, Any],
                         solana_data: Optional[Dict[str, Any]] = None,
                         destination_url: Optional[str] = None) -> Dict[str, Any]:
        """
        Encapsulates an agent handoff payload into a UVIX envelope and dispatches it.
        """
        handoff = AgentHandoffPayload(
            source_agent=source_agent,
            target_agent=target_agent,
            intent=intent,
            action_type=action_type,
            context=context,
            solana_data=solana_data,
        )
        envelope = encode_uvix_slug(
            handoff.to_dict(),
            source_platform=f"agent-{source_agent}",
            target_platform=f"agent-{target_agent}",
            compatibility_layer="solana-agent-handoff-v1",
        )
        return self.dispatch_slug(envelope, destination_url=destination_url)
