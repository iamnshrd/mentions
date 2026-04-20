from __future__ import annotations

from agents.mentions.module_contracts import ensure_dict, normalize_confidence


def compute_posterior_update(market_prior: dict, text_evidence_assessment: dict, workflow_policy: dict) -> dict:
    market_prior = ensure_dict(market_prior)
    text_evidence_assessment = ensure_dict(text_evidence_assessment)
    workflow_policy = ensure_dict(workflow_policy)

    prior = market_prior.get('prior_probability', None)
    if prior is None:
        return {
            'posterior_adjustment': 0.0,
            'suggested_posterior': None,
            'update_confidence': 'low',
            'damping_applied': True,
            'abstain_flag': True,
            'rationale': ['missing_prior_probability'],
        }

    strength = text_evidence_assessment.get('text_signal_strength', 'none')
    direction = text_evidence_assessment.get('direction', 'unclear')
    contradiction_penalty = int(text_evidence_assessment.get('contradiction_penalty', 0) or 0)
    source_reliability = text_evidence_assessment.get('source_reliability', 'low')
    fresh_support_score = int(text_evidence_assessment.get('fresh_support_score', 0) or 0)
    regime = market_prior.get('market_regime', '')
    prior_quality = market_prior.get('prior_quality', '')

    base_move = _base_move(strength, fresh_support_score)
    signed_move = _apply_direction(base_move, direction)
    damped_move = _apply_damping(signed_move, regime, prior_quality, source_reliability, contradiction_penalty, workflow_policy, fresh_support_score)
    suggested = _clamp(prior + damped_move) if damped_move is not None else prior

    abstain_reasons = _abstain_reasons(workflow_policy, strength, fresh_support_score, prior_quality, abs(damped_move or 0.0), contradiction_penalty, source_reliability)
    abstain = bool(abstain_reasons)
    if abstain:
        damped_move = 0.0
        suggested = prior

    return {
        'posterior_adjustment': round(damped_move, 4),
        'suggested_posterior': round(suggested, 4) if suggested is not None else None,
        'update_confidence': _update_confidence(strength, source_reliability, contradiction_penalty, abstain, prior_quality, fresh_support_score),
        'damping_applied': abs(damped_move) < abs(signed_move),
        'abstain_flag': abstain,
        'abstain_reasons': abstain_reasons,
        'rationale': _build_rationale(regime, prior_quality, strength, direction, source_reliability, contradiction_penalty, workflow_policy, fresh_support_score),
    }


def _base_move(strength: str, fresh_support_score: int) -> float:
    base = {
        'strong': 0.12,
        'moderate': 0.07,
        'weak': 0.03,
        'none': 0.0,
    }.get(strength, 0.0)
    if fresh_support_score == 0:
        base *= 0.5
    return base


def _apply_direction(move: float, direction: str) -> float:
    if direction == 'supports_yes':
        return move
    if direction == 'supports_no':
        return -move
    return 0.0


def _apply_damping(move: float, regime: str, prior_quality: str, source_reliability: str, contradiction_penalty: int, workflow_policy: dict, fresh_support_score: int) -> float:
    damp = 1.0
    if regime in ('high_confidence_market',):
        damp *= 0.4
    elif regime in ('thin_noisy_market',):
        damp *= 0.55
    if prior_quality == 'fragile':
        damp *= 0.6
    elif prior_quality == 'quoted_only':
        damp *= 0.35
    if source_reliability == 'low':
        damp *= 0.6
    elif source_reliability == 'medium':
        damp *= 0.85
    if fresh_support_score == 0:
        damp *= 0.4
    damp *= max(0.15, 1 - 0.18 * contradiction_penalty)
    if workflow_policy.get('decision') == 'partial_only':
        damp *= 0.6
    if workflow_policy.get('decision') == 'clarify':
        damp *= 0.1
    return move * damp


def _clamp(value: float) -> float:
    return max(0.0, min(1.0, value))


def _update_confidence(strength: str, source_reliability: str, contradiction_penalty: int, abstain: bool, prior_quality: str, fresh_support_score: int) -> str:
    if abstain:
        return 'low'
    score = 0
    if strength in ('moderate', 'strong'):
        score += 1
    if source_reliability in ('medium', 'high'):
        score += 1
    if contradiction_penalty == 0:
        score += 1
    if prior_quality == 'credible':
        score += 1
    if fresh_support_score >= 2:
        score += 1
    if score >= 4:
        return normalize_confidence('medium')
    return normalize_confidence('low')


def _build_rationale(regime: str, prior_quality: str, strength: str, direction: str, source_reliability: str, contradiction_penalty: int, workflow_policy: dict, fresh_support_score: int) -> list[str]:
    rationale = []
    if regime:
        rationale.append(f'market_regime={regime}')
    if prior_quality:
        rationale.append(f'prior_quality={prior_quality}')
    rationale.append(f'text_signal_strength={strength}')
    rationale.append(f'direction={direction}')
    rationale.append(f'source_reliability={source_reliability}')
    rationale.append(f'fresh_support_score={fresh_support_score}')
    if contradiction_penalty:
        rationale.append(f'contradiction_penalty={contradiction_penalty}')
    if workflow_policy.get('decision'):
        rationale.append(f"policy_decision={workflow_policy.get('decision')}")
    return rationale[:10]


def _abstain_reasons(workflow_policy: dict, strength: str, fresh_support_score: int, prior_quality: str, move_size: float, contradiction_penalty: int, source_reliability: str) -> list[str]:
    reasons = []
    if workflow_policy.get('decision') == 'clarify':
        reasons.append('policy_clarify')
    if strength == 'none' and fresh_support_score == 0:
        reasons.append('no_text_support')
    if prior_quality == 'quoted_only' and fresh_support_score == 0:
        reasons.append('quoted_only_prior_without_fresh_support')
    if move_size < 0.01 and strength in ('none', 'weak'):
        reasons.append('bounded_move_too_small')
    if contradiction_penalty >= 2:
        reasons.append('high_contradiction_load')
    if source_reliability == 'low' and fresh_support_score == 0 and strength != 'strong':
        reasons.append('low_reliability_without_fresh_support')
    return reasons
