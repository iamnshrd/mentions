from __future__ import annotations

import os

from agents.mentions.config import MODULE_BINDINGS
from agents.mentions.module_registry import module_health_report


REQUIRED_ENV_KEYS = [
    'NEWSAPI_KEY',
]

OPTIONAL_ENV_KEYS = [
    'KALSHI_API_KEY',
    'KALSHI_API_URL',
    'KALSHI_ENV',
]


def runtime_validation_report() -> dict:
    module_report = module_health_report()
    required_env = {key: bool(os.environ.get(key, '').strip()) for key in REQUIRED_ENV_KEYS}
    optional_env = {key: bool(os.environ.get(key, '').strip()) for key in OPTIONAL_ENV_KEYS}

    problems = []
    for name, payload in module_report.items():
        if not payload.get('ok'):
            problems.append(f'module-binding-invalid:{name}')
    for key, ok in required_env.items():
        if not ok:
            problems.append(f'missing-required-env:{key}')

    return {
        'module_bindings_path': str(MODULE_BINDINGS),
        'modules': module_report,
        'required_env': required_env,
        'optional_env': optional_env,
        'ok': not problems,
        'problems': problems,
    }
