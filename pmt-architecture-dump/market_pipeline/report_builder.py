#!/usr/bin/env python3
import argparse, json, os, sys, requests

if __package__ is None or __package__ == '':
    sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from market_pipeline.classify_strikes import classify_event
from market_pipeline.analyze import analyze_event

API='https://api.elections.kalshi.com/trade-api/v2/events/{ticker}'

def fetch_event(ticker): return requests.get(API.format(ticker=ticker), timeout=20).json()

def price_for_market(m):
    yb, ya, last = m.get('yes_bid_dollars'), m.get('yes_ask_dollars'), m.get('last_price_dollars')
    if isinstance(yb,(int,float)) and isinstance(ya,(int,float)):
        return round((yb+ya)/2, 3)
    return last

def market_map(markets):
    mp={}
    for m in markets:
        label = m.get('yes_sub_title') or m.get('title')
        if label: mp[label]=m
    return mp

def strike_line(mp,label,fv,note):
    m=mp.get(label)
    if not m: return {'label': label, 'current_price': 'N/A', 'fv_price': fv, 'note': note}
    return {'label': label, 'ticker': m.get('ticker'), 'current_price': price_for_market(m), 'fv_price': fv, 'note': note}


def grouped_classified_strikes(ticker, preset):
    rows = classify_event(ticker, preset)
    groups = {'core yes': [], 'selective': [], 'passive no': [], 'no-touch': []}
    for row in rows:
        note = row.get('action')
        if row.get('confidence') or row.get('reason'):
            note = f"{note} | {row.get('confidence','?')} confidence | {row.get('reason','')}"
        groups.setdefault(row['bucket'], []).append({
            'label': row['label'],
            'ticker': row.get('ticker'),
            'current_price': row.get('current_price'),
            'fv_price': row.get('fv'),
            'note': note,
        })
    return groups


PRICING_SIGNAL_REWRITES = {
    'maker-quality-beats-theoretical-ev': 'Качество исполнения и лимитные входы здесь важнее, чем абстрактный theoretical EV на бумаге.',
    'fresh-context-over-pooled-history': 'Свежий контекст события важнее, чем усреднённая историческая база по похожим рынкам.',
    'phase-aware-pricing': 'Нельзя одинаково оценивать prepared remarks и Q&A — это разные режимы ценообразования.',
}
CROWD_MISTAKE_REWRITES = {
    'trusting-pooled-historicals': 'Рынок слишком доверяет усреднённой истории похожих рынков и недооценивает текущий setup.',
    'pricing-all-drift-as-equal': 'Рынок слишком равномерно оценивает все off-script ветки, хотя их ширина и качество сильно отличаются.',
    'overpaying-narrow-subpaths': 'Рынок переплачивает за узкие и detail-heavy подветки, как будто это прямое ядро события.',
}
PHASE_LOGIC_REWRITES = {
    'prepared-remarks': 'Prepared remarks и Q&A надо оценивать отдельно: прямое ядро может жить уже в opening remarks, а поздние темы требуют живого расширения.',
    'late-qa-expansion': 'Поздние темы часто живут только через Q&A и reporter-driven expansion, а не через стартовый скрипт.',
}


def humanize_slug(text):
    if not text:
        return ''
    return str(text).replace('_', ' ').replace('-', ' ').strip()


def clean_compact_text(text, max_len=220):
    if not text:
        return ''
    s = ' '.join(str(text).split()).strip()
    if len(s) > max_len:
        return ''
    bad_markers = ['>>', 'guys,', 'let\'s see', 'having a pretty damn good week', 'audio', 'tonka']
    lowered = s.lower()
    if any(marker in lowered for marker in bad_markers):
        return ''
    return s


def first_clean(*values, max_len=220):
    for v in values:
        cleaned = clean_compact_text(v, max_len=max_len)
        if cleaned:
            return cleaned
    return ''


def kb_item_to_prose(item, kind):
    if not item:
        return 'TBD after live event-specific read'
    name = item.get('name') or ''
    slug = name.strip()
    if kind == 'pricing_signal':
        return PRICING_SIGNAL_REWRITES.get(slug) or first_clean(item.get('interpretation'), item.get('description'), item.get('typical_action')) or humanize_slug(name)
    if kind == 'crowd_mistake':
        return CROWD_MISTAKE_REWRITES.get(slug) or first_clean(item.get('description'), item.get('why_it_happens'), item.get('how_to_exploit')) or humanize_slug(name)
    if kind == 'phase_logic':
        rewritten = PHASE_LOGIC_REWRITES.get(slug)
        if rewritten:
            return rewritten
        parts = []
        desc = clean_compact_text(item.get('description'))
        err = clean_compact_text(item.get('common_pricing_errors'), max_len=140)
        if desc: parts.append(desc)
        if err: parts.append(f"pricing error: {err}")
        return ' | '.join(parts) if parts else humanize_slug(name)
    return first_clean(item.get('description')) or humanize_slug(name)


def case_to_prose(item):
    if not item:
        return 'TBD after retrieval and strike classification'
    mc = clean_compact_text(item.get('market_context'), max_len=90)
    setup = clean_compact_text(item.get('setup'), max_len=160)
    lesson = clean_compact_text(item.get('lesson'), max_len=160)

    setup_l = (setup or '').lower()
    lesson_l = (lesson or '').lower()
    if 'prepared remarks' in setup_l and 'q&a' in setup_l:
        return 'Хороший аналог по структуре: prepared remarks и Q&A создают разные ветки, но рынок часто переоценивает все страйки слишком равномерно.'
    if 'fresh' in lesson_l and 'history' in lesson_l:
        return 'Хороший аналог: свежий контекст события важнее, чем старая историческая база по похожим рынкам.'
    if 'phase' in mc.lower() or 'phase' in setup_l:
        return 'Ближайший аналог — фазовый рынок, где разные слова живут в разных частях события и нельзя оценивать все ветки одинаково.'

    parts = []
    if mc:
        parts.append(mc)
    if setup:
        parts.append(setup)
    if lesson:
        parts.append(f"lesson: {lesson}")
    text = ' | '.join(parts)
    if len(text) > 240:
        text = text[:237].rstrip() + '...'
    return text or 'TBD after retrieval and strike classification'


def kb_fields_for_preset(ticker, preset):
    preset_map = {
        'iran-press': 'trump-live-qa',
        'trump-live-qa': 'trump-live-qa',
        'briefing-style': 'briefing-style',
    }
    analysis = analyze_event(ticker, preset=preset_map.get(preset, ''))
    bundle = analysis.get('kb_bundle', {}) or {}
    return {
        'main_pricing_signal': kb_item_to_prose(bundle.get('main_pricing_signal') or {}, 'pricing_signal'),
        'main_crowd_mistake': kb_item_to_prose(bundle.get('main_crowd_mistake') or {}, 'crowd_mistake'),
        'relevant_phase_logic': kb_item_to_prose(bundle.get('relevant_phase_logic') or {}, 'phase_logic'),
        'closest_case': case_to_prose(bundle.get('closest_case') or {}),
    }

def build_iran_report(ticker):
    data=fetch_event(ticker); event=data.get('event',{}); groups = grouped_classified_strikes(ticker, 'iran-press'); kb = kb_fields_for_preset(ticker, 'iran-press')
    return {
        'title': event.get('title') or ticker,
        'topic_line': 'Иран, Brady Briefing Room / White House, реальная пресс-конференция, средняя или длинная длительность',
        'guests_qa': 'Гости могут появиться, но ключевое — высокая вероятность живых вопросов от репортеров / Q&A',
        'difficulty': 'средний', 'regime': 'mixed',
        'core_read': 'Это реальная пресс-конференция с естественным ядром, связанным с Ираном. Базовая идея здесь — лонговать основную YES корзину, избирательно брать более широкую geopolitical / Q&A корзину и шортить узко-нарративную корзину.',
        'baskets': [
            {'name':'Основная YES корзина','thesis':'Прямые Iran / nuclear / Israel / negotiation темы — естественное ядро события.','why':['Эти темы живут уже в prepared remarks и не требуют слишком длинный офф-топик мостик.','Они также сохраняют шанс дожить до Q&A и расширения дерева тем благодаря репортерам.','Это естественное ядро, связанное с Ираном.'],'win_condition':'Трамп держится прямого Iran / nuclear / regional-security framing хотя бы в части выступления.','invalidation':'Если событие резко уходит в domestic comedy / media spectacle и прямое Iran core оказывается коротким или формальным.','strikes':groups.get('core yes', [])},
            {'name':'Средняя / Избирательно','thesis':'Более широкая geopolitical и поздняя Q&A корзина может зайти, но это уже не такой чистый YES.','why':['Эти страйки больше зависят от широкой политической тирады и reporter-driven expansion.','Они живут во второй волне события, а не обязательно в opening remarks.','Цена здесь важнее, чем по direct Iran core.'],'win_condition':'Трамп расширяет тему за пределы прямого Iran core в сторону broader geopolitical / negotiation brag.','invalidation':'Если пресс-конференция остаётся узкой и не даёт реального расширения дерева тем.','strikes':groups.get('selective', [])},
            {'name':'Пассивные NO','thesis':'Рынок часто слишком сильно платит не за прямое Iran core, а за слабые направления, куда Трамп может уйти.','why':['Эти страйки требуют более специфичного нарратива, чем просто live Iran event.','Они выглядят хуже, чем broad geopolitics, если priced как direct core.','Узко-нарративные страйки — лучшие кандидаты на пассивные NO.'],'win_condition':'Трамп говорит широко об Иране, но не заходит в very specific branded / detail-heavy subpaths.','invalidation':'Если он неожиданно уходит в очень конкретные personal или operation-specific references.','strikes':groups.get('passive no', [])}
        ],
        'best_basket':'Основная YES корзина',
        'best_yes':'`Uranium`',
        'best_no':'`Epic Fury`',
        'no_touch':'`Biden`, `Barack Hussein Obama`, `Crypto / Bitcoin`, `Venezuela`',
        'main_pricing_signal': kb['main_pricing_signal'],
        'main_crowd_mistake': kb['main_crowd_mistake'],
        'relevant_phase_logic': kb['relevant_phase_logic'],
        'closest_case': kb['closest_case'],
        'execution':'лонговать основную YES корзину, избирательно брать более широкую geopolitical / Q&A корзину, шортить узко-нарративную корзину',
        'sizing':'normal on core, selective on broader basket, passive sizing on NO basket',
        'wording_checked': True
    }

def build_trump_live_qa_report(ticker):
    data=fetch_event(ticker); event=data.get('event',{}); groups = grouped_classified_strikes(ticker, 'trump-live-qa'); kb = kb_fields_for_preset(ticker, 'trump-live-qa')
    subtitle = event.get('sub_title') or event.get('subtitle') or 'live Trump event'
    return {
        'title': event.get('title') or ticker,
        'topic_line': f"Trump event, {subtitle}, live remarks / likely Q&A, expected medium event duration",
        'guests_qa': 'Guests may appear, but key question is whether Trump gets meaningful reporter interaction / Q&A.',
        'difficulty': 'средний',
        'regime': 'mixed',
        'core_read': 'Use this preset when the event is a real Trump live remarks / Q&A market but there is no hand-built event-specific basket map yet. The main job is to separate direct topic core from weaker drift paths and Q&A-only expansion.',
        'baskets': [
            {
                'name': 'Основная YES корзина',
                'thesis': 'Only direct topic-core names belong here.',
                'why': [
                    'These strikes should be naturally live in prepared remarks or the first layer of Q&A.',
                    'They should not need a long off-topic bridge.'
                ],
                'win_condition': 'Trump stays close enough to the stated topic or natural first-order expansion of that topic.',
                'invalidation': 'The event turns out much shorter, more ceremonial, or more constrained than expected.',
                'strikes': groups.get('core yes', [])
            },
            {
                'name': 'Поздние темы / Q&A корзина',
                'thesis': 'These are topic-adjacent names that mostly need live reporter-driven expansion.',
                'why': [
                    'They are less natural in opening remarks than the direct topic core.',
                    'They depend more on how wide the Q&A tree becomes.'
                ],
                'win_condition': 'Trump gets a real Q&A and expands into adjacent themes.',
                'invalidation': 'Q&A is cut short or remains narrowly on-script.',
                'strikes': groups.get('selective', [])
            },
            {
                'name': 'Пассивные NO',
                'thesis': 'Use this bucket for narrow, detail-heavy, or phrase-specific names that the market is treating like broad drift.',
                'why': [
                    'These strikes usually require a more specific narrative branch than the market initially assumes.',
                    'This is often where crowd overpay is largest.'
                ],
                'win_condition': 'Trump stays broad and does not go into very specific or branded subpaths.',
                'invalidation': 'He unexpectedly fixates on a narrow subtopic or repeated named phrase.',
                'strikes': groups.get('passive no', [])
            }
        ],
        'best_basket': 'TBD after strike classification',
        'best_yes':'TBD',
        'best_no':'TBD',
        'no_touch':'TBD',
        'main_pricing_signal': kb['main_pricing_signal'],
        'main_crowd_mistake': kb['main_crowd_mistake'],
        'relevant_phase_logic': kb['relevant_phase_logic'],
        'closest_case': kb['closest_case'],
        'execution': 'build basket map first; then long direct core, selectively buy Q&A expansion, and use passive NO on narrow detail-heavy names',
        'sizing': 'small until strike buckets are explicitly classified',
        'wording_checked': True
    }


def build_briefing_style_report(ticker):
    data=fetch_event(ticker); event=data.get('event',{}); groups = grouped_classified_strikes(ticker, 'briefing-style'); kb = kb_fields_for_preset(ticker, 'briefing-style')
    subtitle = event.get('sub_title') or event.get('subtitle') or 'briefing-style event'
    return {
        'title': event.get('title') or ticker,
        'topic_line': f"Briefing-style event, {subtitle}, live press format, medium event duration",
        'guests_qa': 'Guests may appear, but the central question is whether the format stays open enough for real reporter-driven expansion.',
        'difficulty': 'средний',
        'regime': 'mixed',
        'core_read': 'In briefing-style markets the key split is direct topic core versus Q&A-only expansion versus narrow over-specific names. Direct topic core usually deserves the strongest weight; adjacent names depend on how open the room really is.',
        'baskets': [
            {
                'name': 'Основная YES корзина',
                'thesis': 'Use this for direct topic-core names that should be naturally live even without a very wide Q&A.',
                'why': [
                    'These names fit the stated subject of the briefing.',
                    'They should not require a large drift away from the announced format.'
                ],
                'win_condition': 'The event remains true to its announced topic and gives enough live time for direct-core names to appear.',
                'invalidation': 'The event is much shorter, more constrained, or more ceremonial than the market assumes.',
                'strikes': groups.get('core yes', [])
            },
            {
                'name': 'Поздние темы / Q&A корзина',
                'thesis': 'Use this for topic-adjacent names that mostly need reporter expansion or a late drift in the topic tree.',
                'why': [
                    'These names are less likely to appear in the scripted opening than in open questioning.',
                    'Their value rises sharply if the format is truly live and unscripted.'
                ],
                'win_condition': 'The room opens up and reporters materially widen the topic tree.',
                'invalidation': 'Questions are limited, controlled, or stay narrowly inside the prepared frame.',
                'strikes': groups.get('selective', [])
            },
            {
                'name': 'Пассивные NO',
                'thesis': 'Use this for narrow, detail-heavy, or branded names that the market is incorrectly pricing like broad topic drift.',
                'why': [
                    'These names usually require a more specific path than the crowd initially thinks.',
                    'This is often where briefing-style markets overpay the most.'
                ],
                'win_condition': 'The event stays broad enough to hit core names but not specific enough to reach narrow subpaths.',
                'invalidation': 'The speaker or reporters unexpectedly fixate on a narrow branded thread.',
                'strikes': groups.get('passive no', [])
            }
        ],
        'best_basket': 'TBD after strike classification',
        'best_yes':'TBD',
        'best_no':'TBD',
        'no_touch':'TBD',
        'main_pricing_signal': kb['main_pricing_signal'],
        'main_crowd_mistake': kb['main_crowd_mistake'],
        'relevant_phase_logic': kb['relevant_phase_logic'],
        'closest_case': kb['closest_case'],
        'execution': 'buy direct topic core first, add selective Q&A names only if the format is truly open, and use passive NO on narrow detail-heavy overpays',
        'sizing': 'small until strike buckets are explicitly classified',
        'wording_checked': True
    }


def build_report_json(ticker,preset='iran-press'):
    if preset=='iran-press': return build_iran_report(ticker)
    if preset=='trump-live-qa': return build_trump_live_qa_report(ticker)
    if preset=='briefing-style': return build_briefing_style_report(ticker)
    raise SystemExit('Unknown preset')

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('ticker'); ap.add_argument('--preset', default='iran-press'); args=ap.parse_args()
    print(json.dumps(build_report_json(args.ticker,args.preset), indent=2, ensure_ascii=False))

if __name__ == '__main__':
    main()
