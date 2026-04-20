from agents.mentions.module_registry import load_module_bindings, module_health_report
from agents.mentions.workflows.validation import runtime_validation_report


def test_module_bindings_load_defaults():
    bindings = load_module_bindings()
    assert bindings['frame_selector'] == 'default'
    assert bindings['response_renderer'] == 'default'


def test_module_health_report_has_expected_modules():
    report = module_health_report()
    assert report['frame_selector']['ok'] is True
    assert report['analysis_engine']['ok'] is True
    assert report['response_renderer']['ok'] is True


def test_runtime_validation_report_shape():
    report = runtime_validation_report()
    assert 'modules' in report
    assert 'required_env' in report
    assert 'optional_env' in report
    assert isinstance(report['problems'], list)
