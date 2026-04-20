from __future__ import annotations

from agents.mentions.runtime.validation import runtime_validation_report


class RuntimeBootstrapError(RuntimeError):
    pass


def run_bootstrap_checks(strict: bool = False) -> dict:
    report = runtime_validation_report()
    if strict and not report.get('ok', False):
        raise RuntimeBootstrapError('; '.join(report.get('problems', [])))
    return report
