"""Pack registration for Mentions."""
from __future__ import annotations

import json
import logging

from agents.mentions.interfaces.capabilities.analysis.service import AnalysisCapabilityService
from agents.mentions.interfaces.capabilities.news_context.service import NewsContextCapabilityService
from agents.mentions.interfaces.capabilities.transcripts.service import TranscriptsCapabilityService
from agents.mentions.interfaces.capabilities.wording.service import WordingCapabilityService
from agents.mentions.config import MANIFEST
from mentions_core.base.config import WORKSPACE, get_default_store
from mentions_core.base.pack_types import CapabilityDescriptor, PackContext, PackManifest


class MentionsPack:
    """Mentions pack implementation for OpenClaw."""

    def __init__(self):
        self._manifest = self._load_manifest()
        self._logger = logging.getLogger('mentions')

    def manifest(self) -> PackManifest:
        return self._manifest

    def build_context(self) -> PackContext:
        return PackContext(
            pack_id=self._manifest.id,
            workspace_root=WORKSPACE,
            logger=self._logger,
            state_store=get_default_store(),
            settings={'required_env': list(self._manifest.required_env)},
            scheduler_hooks={hook: hook for hook in self._manifest.schedule_hooks},
            transport_hooks={},
        )

    def capability_descriptors(self) -> dict[str, CapabilityDescriptor]:
        return {
            'analysis': CapabilityDescriptor(
                name='analysis',
                command_namespace='analysis',
                service_factory=lambda ctx: AnalysisCapabilityService(ctx),
                config_schema={'actions': ['query', 'url', 'prompt', 'autonomous']},
            ),
            'transcripts': CapabilityDescriptor(
                name='transcripts',
                command_namespace='transcripts',
                service_factory=lambda ctx: TranscriptsCapabilityService(ctx),
                config_schema={'actions': ['ingest', 'search', 'build']},
            ),
            'news_context': CapabilityDescriptor(
                name='news_context',
                command_namespace='news_context',
                service_factory=lambda ctx: NewsContextCapabilityService(ctx),
                config_schema={'actions': ['build']},
            ),
            'wording': CapabilityDescriptor(
                name='wording',
                command_namespace='wording',
                service_factory=lambda ctx: WordingCapabilityService(ctx),
                config_schema={'actions': ['check', 'rewrite']},
            ),
        }

    def run(self, query: str, user_id: str = 'default') -> dict:
        from agents.mentions.interfaces.capabilities.analysis.api import run_query

        return run_query(query, user_id=user_id)

    def prompt(self, query: str, user_id: str = 'default',
               system_only: bool = False) -> dict | str:
        from agents.mentions.interfaces.capabilities.analysis.api import build_prompt

        return build_prompt(query, user_id=user_id, system_only=system_only)

    def schedule(self, action: str, **kwargs) -> dict:
        from agents.mentions.interfaces.capabilities.analysis.api import run_autonomous_scan

        if action != 'run':
            raise SystemExit(f'Unknown schedule action for mentions: {action}')
        return run_autonomous_scan(dry_run=bool(kwargs.get('dry_run', False)))

    def _load_manifest(self) -> PackManifest:
        raw = json.loads(MANIFEST.read_text(encoding='utf-8'))
        return PackManifest(
            id=raw['id'],
            version=raw['version'],
            identity=raw['identity'],
            capabilities=tuple(raw.get('capabilities', [])),
            commands=tuple(raw.get('commands', [])),
            required_env=tuple(raw.get('required_env', [])),
            schedule_hooks=tuple(raw.get('schedule_hooks', [])),
        )
