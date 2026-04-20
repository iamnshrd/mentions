from mentions_core.cli import main


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


def test_cli_run_uses_pack(capsys):
    code = main(['run', 'mentions', 'fed rate decision market'])
    captured = capsys.readouterr()
    assert code == 0
    assert '"response"' in captured.out


def test_cli_prompt_still_works(capsys):
    code = main(['prompt', 'mentions', 'fed rate decision market'])
    captured = capsys.readouterr()
    assert code == 0
    assert '"action"' in captured.out


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
