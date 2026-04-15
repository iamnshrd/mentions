#!/usr/bin/env python3
import json, re, sys

REQUIRED_TOP = [
    'title',
    'topic_line',
    'guests_qa',
    'difficulty',
    'regime',
    'core_read',
    'baskets',
    'best_basket',
    'main_pricing_signal',
    'main_crowd_mistake',
    'relevant_phase_logic',
    'execution',
    'sizing',
]
REQUIRED_BASKET = ['name', 'thesis', 'why', 'win_condition', 'invalidation', 'strikes']
REQUIRED_STRIKE = ['label', 'current_price', 'fv_price', 'note']
VALID_DIFFICULTY = {'легкий', 'средний', 'тяжелый'}
VALID_REGIME = {'Y fest', 'N fest', 'mixed'}


def is_missing(v):
    return v is None or v == '' or v == []


def validate_report(data):
    errors = []
    warnings = []

    for key in REQUIRED_TOP:
        if key not in data or is_missing(data.get(key)):
            errors.append(f'missing top-level field: {key}')

    if data.get('difficulty') and data.get('difficulty') not in VALID_DIFFICULTY:
        warnings.append(f"difficulty not in canonical set: {data.get('difficulty')}")
    if data.get('regime') and data.get('regime') not in VALID_REGIME:
        warnings.append(f"regime not in canonical set: {data.get('regime')}")

    title = data.get('title', '') or ''
    if re.fullmatch(r'[A-Z0-9\-]+', title.strip()):
        warnings.append('title looks like raw ticker/shorthand, not human-readable title')

    baskets = data.get('baskets', []) or []
    if not baskets:
        errors.append('no baskets present')
    for i, basket in enumerate(baskets, start=1):
        for key in REQUIRED_BASKET:
            if key not in basket or is_missing(basket.get(key)):
                errors.append(f'basket {i} missing field: {key}')
        strikes = basket.get('strikes', []) or []
        for j, strike in enumerate(strikes, start=1):
            for key in REQUIRED_STRIKE:
                if key not in strike or is_missing(strike.get(key)):
                    errors.append(f'basket {i} strike {j} missing field: {key}')
            if strike.get('current_price') == 'N/A':
                warnings.append(f"basket {i} strike {j} has missing live current_price for {strike.get('label')}")

    if 'wording_checked' not in data:
        warnings.append('wording_checked flag missing; upstream wording-db compliance not explicitly marked')
    elif data.get('wording_checked') is not True:
        warnings.append('wording_checked is not true')

    ok = not errors
    return {'ok': ok, 'errors': errors, 'warnings': warnings}


def main():
    data = json.load(sys.stdin)
    print(json.dumps(validate_report(data), indent=2, ensure_ascii=False))

if __name__ == '__main__':
    main()
