from __future__ import annotations

from mentions_domain.normalize import ensure_dict


def build_analysis_profiles(query: str, frame: dict, bundle: dict, analysis: dict) -> dict:
    frame = ensure_dict(frame)
    bundle = ensure_dict(bundle)
    analysis = ensure_dict(analysis)

    market_prior = ensure_dict(bundle.get('market_prior', {}))
    posterior_update = ensure_dict(bundle.get('posterior_update', {}))
    selected_pmt_evidence = ensure_dict(bundle.get('selected_pmt_evidence', {}))
    challenge_block = ensure_dict(bundle.get('challenge_block', {}))
    workflow_policy = ensure_dict(bundle.get('workflow_policy', {}))
    text_evidence_assessment = ensure_dict(bundle.get('text_evidence_assessment', {}))
    fused_evidence = ensure_dict(bundle.get('fused_evidence', {}))

    prior_probability = market_prior.get('prior_probability')
    suggested_posterior = posterior_update.get('suggested_posterior')
    thesis = _build_thesis(analysis, market_prior, posterior_update, workflow_policy, fused_evidence)
    fair_value_view = _build_fair_value_view(prior_probability, suggested_posterior, workflow_policy, market_prior, posterior_update, fused_evidence)
    why_now = _build_why_now(text_evidence_assessment, selected_pmt_evidence, fused_evidence)
    key_risk = challenge_block.get('disconfirming_indicator', '')
    invalidation = challenge_block.get('what_changes_view', '')
    recommended_action = _build_action(workflow_policy, posterior_update, market_prior, fused_evidence)
    structured_view = _build_structured_view(
        thesis=thesis,
        fair_value_view=fair_value_view,
        why_now=why_now,
        key_risk=key_risk,
        invalidation=invalidation,
        recommended_action=recommended_action,
        workflow_policy=workflow_policy,
        posterior_update=posterior_update,
        text_evidence_assessment=text_evidence_assessment,
        fused_evidence=fused_evidence,
    )

    return {
        'thesis': thesis,
        'fair_value_view': fair_value_view,
        'why_now': why_now,
        'key_risk': key_risk,
        'invalidation': invalidation,
        'recommended_action': recommended_action,
        'uncertainty': structured_view.get('uncertainty', ''),
        'next_check': structured_view.get('next_check', ''),
        'evidence_points': structured_view.get('evidence', []),
        'analysis_card': structured_view,
        'supporting_blocks': {
            'market_prior': market_prior,
            'posterior_update': posterior_update,
            'selected_pmt_evidence': selected_pmt_evidence,
            'challenge_block': challenge_block,
        },
        'route': frame.get('route', ''),
        'query': query,
    }


def build_analysis_v2(query: str, frame: dict, bundle: dict, legacy_analysis: dict) -> dict:
    profiles = build_analysis_profiles(query, frame, bundle, legacy_analysis)
    return {
        **profiles,
        'recommended_action_v2': profiles.get('recommended_action', ''),
    }


def _build_thesis(analysis: dict, market_prior: dict, posterior_update: dict, workflow_policy: dict, fused_evidence: dict) -> str:
    if workflow_policy.get('decision') == 'clarify':
        return 'Привязка рынка пока недостаточно чистая, чтобы формулировать устойчивый тезис.'
    prior = market_prior.get('prior_probability')
    posterior = posterior_update.get('suggested_posterior')
    prior_quality = market_prior.get('prior_quality', '')
    conflict_count = len(fused_evidence.get('conflicts', []))
    abstain = posterior_update.get('abstain_flag', False)
    abstain_reasons = posterior_update.get('abstain_reasons', []) or []
    if prior is None:
        return analysis.get('conclusion', 'Недостаточно market prior для устойчивого тезиса.')
    if abstain:
        reason_text = _render_abstain_reasons(abstain_reasons)
        return f'Базовый рынок стоит около {prior:.3f}, но текущий набор подтверждений не даёт права на апдейт ({reason_text}).'
    if posterior is None:
        return f'Рынок стоит около {prior:.3f}, но текущего текстового подтверждения недостаточно для осмысленного апдейта.'
    delta = posterior - prior
    if prior_quality in ('fragile', 'quoted_only'):
        return f'Базовый рынок стоит около {prior:.3f}, но сам baseline хрупкий, поэтому даже ограниченный сдвиг к {posterior:.3f} нельзя читать как надёжный эдж.'
    if conflict_count >= 2:
        return f'Базовый рынок стоит около {prior:.3f}; evidence тянет к {posterior:.3f}, но conflict load слишком высокий для уверенного тезиса.'
    if abs(delta) < 0.02:
        return f'Базовый рынок стоит около {prior:.3f}; текущие подтверждения дают лишь слабый сдвиг к {posterior:.3f}, без заметного эджа.'
    return f'Базовый рынок стоит около {prior:.3f}; текущие подтверждения допускают ограниченный сдвиг к {posterior:.3f}, но не полноценный rerate.'


def _build_fair_value_view(prior_probability, suggested_posterior, workflow_policy: dict, market_prior: dict, posterior_update: dict, fused_evidence: dict) -> str:
    if workflow_policy.get('decision') == 'partial_only':
        return 'Fair value view пока только ориентировочный, потому что policy не разрешает полный разбор.'
    if prior_probability is None:
        return 'Нельзя дать устойчивый fair value view, потому что market prior не извлечён.'
    if posterior_update.get('abstain_flag'):
        return f'Fair value пока остаётся около рынка, то есть примерно {prior_probability:.3f}, потому что подтверждений недостаточно для сдвига.'
    if market_prior.get('prior_quality') in ('fragile', 'quoted_only'):
        return f'Fair value пока нельзя уверенно сдвигать от {prior_probability:.3f}, потому что сам market prior хрупкий.'
    if len(fused_evidence.get('conflicts', [])) >= 2:
        return f'Fair value около {prior_probability:.3f}, но конфликтность подтверждений слишком высокая для уверенного пересмотра.'
    if suggested_posterior is None:
        return f'Fair value пока остаётся привязан к рынку около {prior_probability:.3f}.'
    if abs((suggested_posterior or prior_probability) - prior_probability) < 0.02:
        return f'Fair value остаётся близко к рынку: примерно {prior_probability:.3f}, с очень слабым дрейфом к {suggested_posterior:.3f}.'
    return f'Ориентир по fair value: ограниченный сдвиг от {prior_probability:.3f} к {suggested_posterior:.3f}.'


def _build_why_now(text_evidence_assessment: dict, selected_pmt_evidence: dict, fused_evidence: dict) -> str:
    strength = text_evidence_assessment.get('text_signal_strength', 'none')
    direction = text_evidence_assessment.get('direction', 'unclear')
    pricing_signal = ensure_dict(selected_pmt_evidence.get('selected_pricing_signal', {})).get('signal_name', '')
    coverage = ensure_dict(fused_evidence.get('coverage', {}))
    parts = [f'сила текстового подтверждения: {strength}', f'направление: {direction}']
    if not coverage.get('has_news'):
        parts.append('свежих новостей по событию нет')
    if not coverage.get('has_transcripts'):
        parts.append('подтверждающего transcript evidence нет')
    if pricing_signal:
        parts.append(f'PMT сигнал: {pricing_signal}')
    return '; '.join(parts)


def _render_abstain_reasons(reasons: list[str]) -> str:
    mapping = {
        'policy_clarify': 'сначала нужно уточнить привязку рынка',
        'no_text_support': 'нет текстового подтверждения',
        'quoted_only_prior_without_fresh_support': 'рынок опирается только на котировку без свежего подтверждения',
        'bounded_move_too_small': 'предполагаемый сдвиг слишком маленький',
        'high_contradiction_load': 'слишком много противоречий в подтверждениях',
        'low_reliability_without_fresh_support': 'слабые источники без свежего подтверждения',
    }
    rendered = [mapping.get(reason, reason) for reason in reasons[:2]]
    return ', '.join(rendered) if rendered else 'подтверждение слишком слабое'


def _build_action(workflow_policy: dict, posterior_update: dict, market_prior: dict, fused_evidence: dict) -> str:
    if workflow_policy.get('decision') == 'clarify':
        return 'Сначала уточнить привязку рынка и события.'
    if posterior_update.get('abstain_flag'):
        reasons = posterior_update.get('abstain_reasons', []) or []
        reason_text = _render_abstain_reasons(reasons)
        return f'Пока no-trade / monitor: апдейт не оправдан ({reason_text}).'
    if workflow_policy.get('decision') == 'partial_only':
        return 'Пока только monitor: policy не разрешает full-conviction trade view.'
    posterior = posterior_update.get('suggested_posterior')
    prior = market_prior.get('prior_probability')
    if market_prior.get('prior_quality') in ('fragile', 'quoted_only'):
        return 'Пока monitor: market prior слишком хрупкий для агрессивного trade view.'
    if len(fused_evidence.get('conflicts', [])) >= 2:
        return 'Пока monitor: conflict load слишком высокий.'
    if posterior is None or prior is None:
        return 'Пока monitor: posterior structure ещё слабая.'
    if abs(posterior - prior) < 0.02:
        return 'Пока monitor: предполагаемый edge над рынком слишком маленький.'
    return 'Можно смотреть как ограниченный trade setup поверх market prior.'


def _build_structured_view(*, thesis: str, fair_value_view: str, why_now: str,
                           key_risk: str, invalidation: str,
                           recommended_action: str, workflow_policy: dict,
                           posterior_update: dict, text_evidence_assessment: dict,
                           fused_evidence: dict) -> dict:
    return {
        'thesis': thesis,
        'evidence': _build_evidence_points(why_now, text_evidence_assessment, fused_evidence),
        'uncertainty': _build_uncertainty(workflow_policy, posterior_update, fused_evidence),
        'risk': key_risk,
        'next_check': _build_next_check(invalidation, posterior_update, text_evidence_assessment, fused_evidence),
        'action': recommended_action,
        'fair_value_view': fair_value_view,
    }


def _build_evidence_points(why_now: str, text_evidence_assessment: dict, fused_evidence: dict) -> list[str]:
    evidence = []
    if why_now:
        evidence.append(why_now)
    direction = text_evidence_assessment.get('direction', '')
    strength = text_evidence_assessment.get('text_signal_strength', '')
    if direction or strength:
        evidence.append(f'Текстовый сигнал: {direction or "unclear"} / {strength or "unknown"}')
    coverage = ensure_dict(fused_evidence.get('coverage', {}))
    if coverage:
        evidence.append(
            'Покрытие: '
            + ', '.join(
                part for part in [
                    'news' if coverage.get('has_news') else '',
                    'transcripts' if coverage.get('has_transcripts') else '',
                    'market' if coverage.get('has_market') else '',
                ] if part
            )
        )
    return [item for item in evidence if item][:3]


def _build_uncertainty(workflow_policy: dict, posterior_update: dict, fused_evidence: dict) -> str:
    if workflow_policy.get('decision') == 'clarify':
        return 'Привязка рынка к событию ещё требует уточнения.'
    if posterior_update.get('abstain_flag'):
        reasons = posterior_update.get('abstain_reasons', []) or []
        return 'Апдейт остановлен: ' + _render_abstain_reasons(reasons)
    conflict_count = len(ensure_dict(fused_evidence).get('conflicts', []))
    if conflict_count >= 2:
        return 'В подтверждениях слишком много конфликтов для уверенного апдейта.'
    return ''


def _build_next_check(invalidation: str, posterior_update: dict,
                      text_evidence_assessment: dict, fused_evidence: dict) -> str:
    if invalidation:
        return invalidation
    if posterior_update.get('abstain_flag'):
        reasons = posterior_update.get('abstain_reasons', []) or []
        if 'no_text_support' in reasons:
            return 'Нужен прямой текстовый триггер по событию: transcript clip, quote или подтверждающий news hit.'
        if 'high_contradiction_load' in reasons:
            return 'Нужен более чистый набор подтверждений без противоречий между news и transcript evidence.'
    coverage = ensure_dict(fused_evidence.get('coverage', {}))
    if not coverage.get('has_transcripts'):
        return 'Проверить, появилось ли transcript-backed подтверждение по событию.'
    if not coverage.get('has_news'):
        return 'Проверить, появилось ли прямое news-подтверждение по событию.'
    strength = text_evidence_assessment.get('text_signal_strength', '')
    if strength in {'weak', 'none', ''}:
        return 'Подождать более сильного текстового подтверждения, прежде чем двигать fair value.'
    return 'Следить за новым подтверждением, которое укрепляет или ломает текущий тезис.'
