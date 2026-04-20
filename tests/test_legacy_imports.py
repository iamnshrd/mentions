from library._adapters import FileSystemStore, get_store
from library._core.analysis import analyze_market, assess_signal
from library._core.eval import audit
from library._core.fetch import fetch_all, get_market, parse_kalshi_url
from library._core.ingest import ingest, register
from library._core.kb import build, migrate_up, query
from library._core.runtime import build_prompt, orchestrate, select_frame
from library._core.scheduler import run_autonomous
from library._core.session import assemble, estimate, load, update_session


def test_legacy_package_level_imports_resolve_to_new_modules():
    assert get_store.__module__ == 'library._adapters.default_components'
    assert FileSystemStore.__module__ == 'mentions_core.base.adapters.fs_store'
    assert orchestrate.__module__ == 'agents.mentions.runtime.orchestrator'
    assert select_frame.__module__ == 'agents.mentions.runtime.frame'
    assert build_prompt.__module__ == 'agents.mentions.runtime.llm_prompt'
    assert analyze_market.__module__ == 'agents.mentions.analysis.market'
    assert assess_signal.__module__ == 'agents.mentions.analysis.signal'
    assert fetch_all.__module__ == 'agents.mentions.fetch.auto'
    assert get_market.__module__ == 'agents.mentions.fetch.kalshi'
    assert parse_kalshi_url.__module__ == 'agents.mentions.fetch.url_parser'
    assert ingest.__module__ == 'agents.mentions.ingest.auto'
    assert register.__module__ == 'agents.mentions.ingest.transcript'
    assert build.__module__ == 'agents.mentions.kb.build'
    assert query.__module__ == 'agents.mentions.kb.query'
    assert migrate_up.__module__ == 'agents.mentions.kb.migrate'
    assert assemble.__module__ == 'mentions_core.base.session.context'
    assert estimate.__module__ == 'mentions_core.base.session.progress'
    assert load.__module__ == 'mentions_core.base.session.continuity'
    assert update_session.__module__ == 'mentions_core.base.session.state'
    assert run_autonomous.__module__ == 'agents.mentions.scheduler.runner'
    assert audit.__module__ == 'agents.mentions.eval.audit'
