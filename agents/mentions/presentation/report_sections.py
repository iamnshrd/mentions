from __future__ import annotations


def baseline_line(topics: list[str]) -> str:
    baseline = ' / '.join(topics) if topics else 'контекст ещё тонкий'
    return f"**Базовая линия:** {baseline}."


def direct_topics_line(direct_topics: list[str]) -> str:
    return f"**Где тема выглядит наиболее естественной:** {', '.join(direct_topics)}." if direct_topics else ''


def weak_paths_line(weak_paths: list[str]) -> str:
    return f"**Где exact keyword hit выглядит слабее:** {', '.join(weak_paths)}." if weak_paths else ''


def late_paths_line(late_paths: list[str]) -> str:
    return f"**Где тема скорее уходит в поздние / боковые ветки:** {', '.join(late_paths)}." if late_paths else ''


def should_render_basket_explain(*, score_rows: list[dict], weak_media_case: bool) -> bool:
    return bool(score_rows) and not weak_media_case


def basket_explain_lines(score_rows: list[dict]) -> str:
    explain = []
    for row in score_rows[:4]:
        reasons = '; '.join((row.get('reasons') or [])[:2])
        explain.append(f"- `{row.get('strike')}`: {reasons}")
    if explain:
        return "**Почему корзины выглядят именно так:**\n" + '\n'.join(explain)
    return ''


def transcript_boundary_line(*, family_evidence: list[dict], transition_hints: list[dict]) -> str:
    if family_evidence and not transition_hints:
        return "**Граница того, что реально подтверждено:** транскрипты поддерживают core family, но не подтверждают сильный переход в более широкие боковые ветки."
    if not family_evidence:
        return "**Граница того, что реально подтверждено:** transcript-backed family support пока слабый, поэтому расширять read опасно."
    return ''
