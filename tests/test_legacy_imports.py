from mentions_core.base.adapters import FileSystemStore, get_store
from mentions_core.base.session.context import assemble
from mentions_core.base.session.continuity import load
from mentions_core.base.session.progress import estimate
from mentions_core.base.session.state import update_session
from agents.mentions.eval.audit import audit
from agents.mentions.providers.kalshi.client import get_market
from agents.mentions.services.intake.url_parser import parse_kalshi_url
from agents.mentions.ingest.auto import ingest
from agents.mentions.ingest.transcript import register
from agents.mentions.services.knowledge import build
from agents.mentions.services.knowledge import query
from agents.mentions.storage.knowledge.migrate import migrate_up
from agents.mentions.services.analysis.market import analyze_market
from agents.mentions.services.analysis.signal import assess_signal
from agents.mentions.workflows.frame_selection import select_frame
from agents.mentions.workflows.fetch_auto import fetch_all
from agents.mentions.workflows.llm_prompt import build_prompt
from agents.mentions.workflows.orchestrator import orchestrate
from agents.mentions.workflows.scheduling import run_autonomous


def test_canonical_package_imports_resolve_to_new_modules():
    assert get_store.__module__ == 'mentions_core.base.adapters'
    assert FileSystemStore.__module__ == 'mentions_core.base.adapters.fs_store'
    assert orchestrate.__module__ == 'agents.mentions.workflows.orchestrator'
    assert select_frame.__module__ == 'agents.mentions.workflows.frame_selection'
    assert build_prompt.__module__ == 'agents.mentions.workflows.llm_prompt'
    assert analyze_market.__module__ == 'agents.mentions.services.analysis.market'
    assert assess_signal.__module__ == 'agents.mentions.services.analysis.signal'
    assert fetch_all.__module__ == 'agents.mentions.workflows.fetch_auto'
    assert get_market.__module__ == 'agents.mentions.providers.kalshi.client'
    assert parse_kalshi_url.__module__ == 'agents.mentions.services.intake.url_parser'
    assert ingest.__module__ == 'agents.mentions.ingest.auto'
    assert register.__module__ == 'agents.mentions.ingest.transcript'
    assert build.__module__ == 'agents.mentions.services.knowledge.build'
    assert query.__module__ == 'agents.mentions.services.knowledge.query'
    assert migrate_up.__module__ == 'agents.mentions.storage.knowledge.migrate'
    assert assemble.__module__ == 'mentions_core.base.session.context'
    assert estimate.__module__ == 'mentions_core.base.session.progress'
    assert load.__module__ == 'mentions_core.base.session.continuity'
    assert update_session.__module__ == 'mentions_core.base.session.state'
    assert run_autonomous.__module__ == 'agents.mentions.workflows.scheduling.runner'
    assert audit.__module__ == 'agents.mentions.eval.audit'
