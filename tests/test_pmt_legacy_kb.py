from agents.mentions.modules.pmt_legacy_kb.query import query_pmt_knowledge_bundle


def test_pmt_legacy_kb_returns_bundle_from_active_db():
    bundle = query_pmt_knowledge_bundle(event_title='Trump interview', speaker='Trump', fmt='interview', freeform='Iran mention market', top=2)
    assert 'query_terms' in bundle
    assert 'pricing_signals' in bundle
    assert 'execution_patterns' in bundle
    assert isinstance(bundle['pricing_signals'], list)
    assert isinstance(bundle['execution_patterns'], list)
