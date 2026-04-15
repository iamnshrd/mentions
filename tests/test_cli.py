from mentions_core.cli import main
from library.__main__ import main as legacy_main


def test_cli_lists_packs(capsys):
    code = main(['packs'])
    captured = capsys.readouterr()
    assert code == 0
    assert 'mentions' in captured.out


def test_cli_wording_rewrite(capsys):
    code = main(['capability', 'mentions', 'wording', 'rewrite', 'Event read'])
    captured = capsys.readouterr()
    assert code == 0
    assert 'Разбор события' in captured.out


def test_legacy_cli_run_uses_pack_shim(capsys):
    code = legacy_main(['run', 'fed rate decision market'])
    captured = capsys.readouterr()
    assert code == 0
    assert '"response"' in captured.out


def test_legacy_cli_frame_still_works(capsys):
    code = legacy_main(['frame', 'fed rate decision market'])
    captured = capsys.readouterr()
    assert code == 0
    assert '"route"' in captured.out


def test_cli_loads_dotenv_from_cwd(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv('OPENCLAW_PROGRESS_REPEAT_STUCK_THRESHOLD', raising=False)
    (tmp_path / '.env').write_text(
        'OPENCLAW_PROGRESS_REPEAT_STUCK_THRESHOLD=9\n',
        encoding='utf-8',
    )
    code = main(['packs'])
    captured = capsys.readouterr()
    assert code == 0
    assert 'mentions' in captured.out
