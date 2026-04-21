"""Base pack contracts for pluggable runtime packs."""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Mapping, Protocol, runtime_checkable

from mentions_core.base.state_store import StateStore


@dataclass(frozen=True)
class CapabilityDescriptor:
    """Declarative capability registration for a pack."""

    name: str
    command_namespace: str
    service_factory: Callable[['PackContext'], Any]
    config_schema: Mapping[str, Any] | None = None


@dataclass(frozen=True)
class PackManifest:
    """Static metadata for an agent pack."""

    id: str
    version: str
    identity: str
    capabilities: tuple[str, ...]
    commands: tuple[str, ...]
    required_env: tuple[str, ...] = ()
    schedule_hooks: tuple[str, ...] = ()


@dataclass
class PackContext:
    """Runtime context passed to pack and capability services."""

    pack_id: str
    workspace_root: Path
    logger: logging.Logger
    state_store: StateStore
    settings: dict[str, Any] = field(default_factory=dict)
    scheduler_hooks: dict[str, Any] = field(default_factory=dict)
    transport_hooks: dict[str, Any] = field(default_factory=dict)


@runtime_checkable
class AgentPack(Protocol):
    """Protocol implemented by every pack exposed through the runtime."""

    def manifest(self) -> PackManifest:
        ...

    def build_context(self) -> PackContext:
        ...

    def capability_descriptors(self) -> dict[str, CapabilityDescriptor]:
        ...

    def run(self, query: str, user_id: str = 'default') -> dict:
        ...

    def prompt(self, query: str, user_id: str = 'default',
               system_only: bool = False) -> dict | str:
        ...

    def schedule(self, action: str, **kwargs) -> dict:
        ...
