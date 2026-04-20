"""Wording validation and rewrite rules for Mentions outputs."""
from __future__ import annotations

import json
import re

from agents.mentions.config import WORDING_DB

FALLBACK_PHRASE_REWRITES = {
    'selective yes': 'избирательная ставка на YES',
    'selective buy': 'избирательная покупка',
    'passive no': 'пассивный NO',
    'strong passive no': 'сильный кандидат на пассивный NO',
    'off-path drift': 'слишком широкое отклонение от основной темы',
    'clean core': 'прямое ядро события',
    'clean trade thesis': 'чистая торговая идея',
    'narrative branch': 'отдельная тематическая ветка',
    'branded subpaths': 'узкие именованные подветки',
    'broad yes fest': 'массовая покупка YES по всему рынку',
    'selective long': 'избирательный лонг',
    'fade': 'шорт / игра от переоценки',
    'off-script bridge': 'офф-топик мостик',
    'detail-heavy': 'узко-нарративный',
    'detail-heavy names': 'узко-нарративные страйки',
    'core bucket': 'основная корзина',
    'selective bucket': 'избирательная корзина',
    'best yes': 'лучшая ставка на YES',
    'best no bucket': 'лучшая NO корзина',
    'broad drift': 'широкое отклонение от темы',
    'pricing in': 'закладывает в цену',
    'auto-buy': 'автоматическая покупка',
}

BAD_PATTERNS = [
    ('SETT — Settle / Deal', 'Use only human-readable strike label in monospace'),
    ('Event read', 'Use "Разбор события"'),
    ('Bottom line by bucket', 'Use "Итого по корзинам"'),
]

SAFE_AUTO_FIX_KEYS = {
    'event read',
    'bottom line by bucket',
    'best basket',
    'core yes basket',
    'late-path / q&a basket',
    'long core basket',
    'short detail-heavy basket',
    'detail-heavy names are the best candidates for passive no',
    'cleanest structural read',
    'this is a market where the cleanest logic is to',
    'selective buy',
    'passive no',
}


def load_db():
    """Load the wording rule database."""
    if not WORDING_DB.exists():
        return {}
    return json.loads(WORDING_DB.read_text(encoding='utf-8'))


def build_rewrite_map(db: dict) -> dict[str, str]:
    """Build a lower-cased rewrite map from DB + fallback rules."""
    mapping = {}
    for item in db.get('preferred_replacements', []):
        src = (item.get('source') or '').strip()
        tgt = (item.get('target') or '').strip()
        if src and tgt:
            mapping[src.lower()] = tgt
    for src, tgt in FALLBACK_PHRASE_REWRITES.items():
        mapping.setdefault(src.lower(), tgt)
    return mapping


def apply_case_preserving_replace(text: str, src: str, tgt: str) -> str:
    """Replace *src* with *tgt* while preserving the source case shape."""
    pattern = re.compile(re.escape(src), flags=re.IGNORECASE)

    def repl(match):
        found = match.group(0)
        if found.isupper():
            return tgt.upper()
        if found[:1].isupper():
            return tgt[:1].upper() + tgt[1:]
        return tgt

    return pattern.sub(repl, text)


def contextual_rewrite(text: str) -> str:
    """Apply a small set of context-sensitive prose rewrites."""
    rules = [
        (r'looks more like (?:a )?fade / passive no', 'выглядит скорее как кандидат на шорт / пассивный NO'),
        (r'not (?:a )?clean core', 'не прямое ядро события'),
        (r'wide off-path drift', 'слишком широкое отклонение от основной темы'),
        (r'selective long \+ strong passive no', 'избирательный лонг + сильные кандидаты на пассивные NO'),
        (r'buy everything', 'покупать всё подряд'),
        (r'best selective yes', 'лучшая избирательная ставка на YES'),
        (r'cleanest logic is to', 'логичнее всего'),
        (r'cleanest structural read', 'короткий структурный разбор'),
    ]
    out = text
    for pattern, repl in rules:
        out = re.sub(pattern, repl, out, flags=re.IGNORECASE)
    return out


def suggest_rewrites(text: str, rewrite_map: dict[str, str]) -> list[dict]:
    """Return all rewrite suggestions that match *text*."""
    lowered = text.lower()
    hits = []
    for bad, good in rewrite_map.items():
        if bad in lowered:
            hits.append({'bad': bad, 'preferred': good})
    return hits


def auto_rewrite(text: str, rewrite_map: dict[str, str], mode: str = 'safe') -> str:
    """Rewrite *text* with safe or full rules."""
    out = text
    items = sorted(rewrite_map.items(), key=lambda kv: len(kv[0]), reverse=True)
    if mode == 'safe':
        items = [kv for kv in items if kv[0] in SAFE_AUTO_FIX_KEYS]
    for bad, good in items:
        out = apply_case_preserving_replace(out, bad, good)
    if mode == 'full':
        out = contextual_rewrite(out)
    return out


def check_text(text: str, apply_fixes: bool = False, mode: str = 'safe') -> dict:
    """Validate and optionally rewrite a prose block."""
    warnings = []
    db = load_db()
    rewrite_map = build_rewrite_map(db)
    lowered = text.lower()

    for bad, note in BAD_PATTERNS:
        if bad.lower() in lowered:
            warnings.append(f'bad pattern: {bad} -> {note}')

    rewrites = suggest_rewrites(text, rewrite_map)
    for item in rewrites:
        warnings.append(f"hybrid prose: {item['bad']} -> {item['preferred']}")

    fixed = auto_rewrite(text, rewrite_map, mode=mode) if apply_fixes else text
    return {
        'ok': len(warnings) == 0,
        'warnings': warnings,
        'db_loaded': bool(db),
        'rewrites': rewrites,
        'text': fixed,
        'rewrite_count': len(rewrites),
        'mode': mode,
    }
