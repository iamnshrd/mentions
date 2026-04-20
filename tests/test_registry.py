from mentions_core.base.registry import get_pack, list_packs


def test_mentions_pack_registered():
    assert 'mentions' in list_packs()
    pack = get_pack('mentions')
    manifest = pack.manifest()
    assert manifest.id == 'mentions'
    assert 'analysis' in manifest.capabilities


def test_legacy_library_shim_points_to_new_runtime():
    from library._core.runtime.orchestrator import orchestrate as legacy_orchestrate
    from agents.mentions.runtime.orchestrator import orchestrate as new_orchestrate

    assert legacy_orchestrate is new_orchestrate
