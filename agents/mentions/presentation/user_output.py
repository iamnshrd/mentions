from __future__ import annotations

from agents.mentions.presentation.media_output import humanize_show_family, render_media_output_block
from agents.mentions.presentation.normalizer import normalize_family_label as humanize_family_label, normalize_market_phrase, normalize_path_label as humanize_path_label


def humanize_market_line(text: str) -> str:
    line = normalize_market_phrase(text or '')
    replacements = {
        '`generic_fox_news_hit`': humanize_show_family('generic_fox_news_hit'),
        '`fox_news_sunday`': humanize_show_family('fox_news_sunday'),
        'direct_prompt_path': humanize_path_label('direct_prompt_path'),
        'reactive_path': humanize_path_label('reactive_path'),
        'bridge_path': humanize_path_label('bridge_path'),
        'agenda_native_path': humanize_path_label('agenda_native_path'),
        'closing_riff_path': humanize_path_label('closing_riff_path'),
    }
    for raw, rendered in replacements.items():
        line = line.replace(raw, rendered)
    return line


def render_user_output_sections(*, interpretation_block: dict | None = None) -> dict:
    interpretation_block = interpretation_block or {}
    media_context = interpretation_block.get('media_context') or {}
    support_signals = interpretation_block.get('support_signals') or []
    caution_signals = interpretation_block.get('caution_signals') or []
    market_gets_right = [_render_support_signal(signal, media_context) for signal in support_signals]
    market_flattens = [_render_caution_signal(signal, media_context) for signal in caution_signals]
    return {
        'media_lines': render_media_output_block(media_context),
        'market_gets_right': [line for line in market_gets_right if line],
        'market_flattens': [line for line in market_flattens if line],
    }


def _render_support_signal(signal: str, media_context: dict) -> str:
    mapping = {
        'topic-core': 'целевая тема действительно встроена в базовую конструкцию события',
        'topic-adjacent-weak': 'общая тематическая релевантность видна, но текущая опора пока слишком тонкая для уверенного event-level read',
        'topic-adjacent': 'общая тематическая релевантность события действительно просматривается',
        'media-format-fit': humanize_market_line(str(media_context.get('gets_right') or '')),
        'show-format-bounded': f"формат `{media_context.get('show_family')}` лучше читать как {media_context.get('show_style')}, а не как свободно расширяющееся event-пространство" if media_context.get('show_family') and media_context.get('show_style') else '',
        'realistic-media-paths': f"реалистичные path'ы к mention здесь скорее всего идут через: {', '.join((media_context.get('realistic_paths') or [])[:3])}" if media_context.get('realistic_paths') else '',
        'historical-strong': 'исторические transcript-аналоги действительно дают сильную опору по speaker/path поведению',
        'historical-partial-weak': 'частичная историческая transcript-опора есть, но она пока не тянет на сильный структурный read',
        'historical-partial': 'есть частичная историческая transcript-опора, особенно по соседним веткам',
        'semi-open-qa-expansion': 'полуоткрытый формат и Q&A действительно допускают живые боковые расширения',
    }
    return humanize_market_line(mapping.get(signal, ''))


def _render_caution_signal(signal: str, media_context: dict) -> str:
    mapping = {
        'topic-not-exclusive': 'тему легко переоценить как единственный фокус события, хотя она не выглядит таким фокусом',
        'media-topical-vs-conversational': 'общая topical relevance не равна реальному conversational path to mention внутри host-driven media format',
        'show-format-constrained': 'конкретный show-format может жёстко ограничивать или направлять topic transitions',
        'blocked-media-paths': f"часть path'ов здесь выглядит структурно слабой или заблокированной: {', '.join((media_context.get('blocked_paths') or [])[:3])}" if media_context.get('blocked_paths') else '',
        'weak-media-paths': f"часть path'ов здесь скорее слабая, чем естественная: {', '.join((media_context.get('weak_paths') or [])[:3])}" if media_context.get('weak_paths') else '',
        'scripted-limits': 'простор для спонтанных уходов от основной темы здесь легко переоценить',
        'historical-regime-only': 'историческая опора здесь больше похожа на regime-level фон, чем на direct transcript core',
        'historical-thin': 'историческая опора по аналогам пока слишком тонкая, чтобы уверенно расширять read',
        'overextended-paths': 'core event path здесь легко слишком рано расширить в более широкие policy/Q&A ветки без transcript-backed переходов',
        'spillover-without-core': 'broad rhetorical regime легко принять за прямое подтверждение тех веток, которых в transcript core пока не видно',
        'generic-regime-without-core': 'часть adjacent policy/industry веток сейчас больше выглядит как regime-embedded expansion, чем как прямой transcript-backed core path',
        'dead-end-families': 'часть боковых веток в текущем transcript path больше похожа на dead ends, чем на естественное продолжение',
        'late-branch-expansion': 'event read здесь легко слишком рано расширить в соседние ветки без прямого core-подтверждения',
        'late-preview-expansion': 'часть веток сейчас больше похожа на late/Q&A expansion, чем на естественный основной path',
        'weak-family-baskets': 'часть тематических корзин пока выглядит скорее натянутой, чем подтвержденной event path',
    }
    return humanize_market_line(mapping.get(signal, ''))
