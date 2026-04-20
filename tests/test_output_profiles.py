from agents.mentions.presentation.profile_renderers import build_output_profiles


def test_build_output_profiles_returns_three_render_modes():
    profiles = build_output_profiles(
        'Will Trump mention Iran?',
        {
            'thesis': 'Bounded move over market prior.',
            'fair_value_view': 'Provisional fair value shifts from 0.12 toward 0.18.',
            'why_now': 'text evidence strength is moderate',
            'key_risk': 'Fresh reporting contradicts setup',
            'invalidation': 'New transcript evidence',
            'recommended_action_v2': 'Review for possible trade setup',
        },
    )
    assert 'Тезис:' in profiles['telegram_brief']
    assert profiles['trade_memo']['thesis'] == 'Bounded move over рыночная базовая линия.'
    assert profiles['investor_note'].startswith('Инвесторская заметка:')


def test_build_output_profiles_humanizes_no_trade_reasoning():
    profiles = build_output_profiles(
        'Will Trump mention Iran?',
        {
            'thesis': 'Base market stays near 0.12.',
            'fair_value_view': 'Fair value view stays close to market.',
            'why_now': 'text evidence strength is weak; no supporting transcript evidence',
            'key_risk': '',
            'invalidation': '',
            'recommended_action_v2': 'Пока no-trade / monitor: апдейт не оправдан (no_text_support, high_contradiction_load).',
        },
    )
    assert 'Base market stays near 0.12.' in profiles['telegram_brief']
    assert profiles['trade_memo']['recommended_action'] == ''


def test_build_output_profiles_uses_analysis_card_when_present():
    profiles = build_output_profiles(
        'Will Trump mention Iran?',
        {
            'analysis_card': {
                'thesis': 'Core event read still looks bounded.',
                'fair_value_view': 'Fair value around 0.18.',
                'evidence': ['text support is moderate', 'coverage: news, market'],
                'uncertainty': 'Transcript support still thin.',
                'risk': 'Fresh reporting contradicts setup',
                'next_check': 'Need direct transcript confirmation',
                'action': 'Can watch as a limited setup.',
            },
        },
    )
    assert 'Core event read still looks bounded.' in profiles['telegram_brief']
    assert profiles['trade_memo']['thesis'] == 'Core event read still looks bounded.'
    assert profiles['trade_memo']['invalidation'] == 'Need direct transcript confirmation'
    assert profiles['investor_note'].startswith('Инвесторская заметка:')
