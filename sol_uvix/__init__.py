"""Compatibility imports for the UVIX protocol package."""

from importlib import import_module
import sys

from core.protocol import *
from core.protocol import __all__


_protocol_modules = (
    "bridge",
    "cli_wrapper",
    "client",
    "codec",
    "models",
    "pumpfun",
    "raydium",
    "tokens",
    "transactions",
    "ws_client",
)

for _module_name in _protocol_modules:
    sys.modules[f"{__name__}.{_module_name}"] = import_module(
        f"core.protocol.{_module_name}"
    )

sys.modules[f"{__name__}.hardware_orchestrator"] = import_module(
    "core.hardware.orchestrator"
)
