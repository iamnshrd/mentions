from __future__ import annotations


from agents.mentions.presentation.normalizer import normalize_path_label as humanize_path_label, normalize_show_family as humanize_show_family


def render_media_output_block(media_context: dict | None) -> list[str]:
    media_context = media_context or {}
    if not media_context:
        return []

    lines: list[str] = []
    show_family = media_context.get('show_family') or ''
    show_label = humanize_show_family(show_family)
    realistic_paths = [humanize_path_label(p) for p in (media_context.get('realistic_paths') or []) if humanize_path_label(p)]
    weak_paths = [humanize_path_label(p) for p in (media_context.get('weak_paths') or []) if humanize_path_label(p)]
    blocked_paths = [humanize_path_label(p) for p in (media_context.get('blocked_paths') or []) if humanize_path_label(p)]

    if show_label:
        lines.append(f"**Media-формат:** это больше похоже на {show_label}, чем на свободно расширяющееся event-пространство.")
    if realistic_paths:
        lines.append("**Реалистичный путь к mention:** " + '; '.join(realistic_paths[:3]) + '.')
    if weak_paths:
        lines.append("**Слабый путь к mention:** " + '; '.join(weak_paths[:3]) + '.')
    if blocked_paths:
        lines.append("**Что здесь выглядит структурно слабым:** " + '; '.join(blocked_paths[:3]) + '.')
    return lines
