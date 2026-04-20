from __future__ import annotations

from agents.mentions.services.media.pathing import evaluate_media_paths
from agents.mentions.services.media.prior_registry import detect_media_prior_mode, get_media_prior
from agents.mentions.services.media.show_registry import detect_media_show


def analyze_media_appearance(event_ctx: dict | None) -> dict:
    event_ctx = event_ctx or {}
    event_title = event_ctx.get('event_title') or event_ctx.get('title') or ''
    fmt = event_ctx.get('format') or ''
    show_key, show_cfg = detect_media_show(event_title)
    media_prior_mode = detect_media_prior_mode(event_title, fmt)
    if media_prior_mode == 'default' and not show_cfg:
        return {}
    prior = get_media_prior(media_prior_mode)
    host_control = show_cfg.get('host_control') or prior.get('host_control', 'unknown')
    segment_shape = show_cfg.get('segment_shape') or prior.get('segment_shape', 'unknown')
    media_context = {
        'media_event_type': media_prior_mode if media_prior_mode != 'default' else 'media_appearance',
        'show_family': show_key,
        'show_outlet': show_cfg.get('outlet', ''),
        'show_type': show_cfg.get('program_type', ''),
        'show_style': show_cfg.get('style', ''),
        'host_control': host_control,
        'segment_shape': segment_shape,
        'realistic_paths': list(prior.get('realistic_paths', [])),
        'weak_paths': list(prior.get('weak_paths', [])),
        'path_confidence': 'medium',
        'framework': 'media_appearance_v0',
        'gets_right': prior.get('gets_right', ''),
    }
    media_context.update(evaluate_media_paths(event_ctx, media_context))
    return media_context
