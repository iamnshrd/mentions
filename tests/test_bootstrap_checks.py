from mentions_core.base.bootstrap_checks import run_bootstrap_checks


def test_bootstrap_checks_report_shape():
    report = run_bootstrap_checks(strict=False)
    assert 'modules' in report
    assert 'required_env' in report
    assert 'problems' in report
