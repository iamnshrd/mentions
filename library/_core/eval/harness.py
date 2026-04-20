"""Eval harness — regression metrics for intent classification + retrieval.

Runs a gold-standard query set (``library/eval_queries.json``) through
the live pipeline and reports:

* ``intent_accuracy``  — fraction of queries whose classified intent
  matches the gold label.
* ``route_accuracy``   — same, for the downstream route.
* ``ticker_prf``       — precision / recall / F1 for ticker extraction.
* ``speaker_prf``      — same for speaker extraction.
* ``recall_at_k`` and ``mrr_at_k`` — only computed for queries that
  specify ``expected_doc_ids``. Skipped otherwise.

The harness takes an optional ``LLMClient`` injection so tests can
pass a :class:`FakeClient`; when omitted, :func:`default_client` is
used (which degrades to :class:`NullClient` without an API key, and
the intent classifier falls back to its rule path).

The shape is stable so the CLI can pickle the output verbatim into
``EVAL_REPORT`` and diff across runs.
"""
from __future__ import annotations

import json
import logging
import math
from typing import Iterable

from library.config import ROOT
from library._core.intent import classify_intent
from library._core.llm import LLMClient, NullClient
from library.utils import now_iso, load_json

log = logging.getLogger('mentions')


GOLD_QUERIES_PATH = ROOT / 'eval_queries.json'


# ── Gold loading ───────────────────────────────────────────────────────────

def load_gold_queries(path=None) -> list[dict]:
    """Load and validate the gold-standard query set.

    Each entry must have ``id`` and ``query``; other keys are optional
    and default to empty.
    """
    path = path or GOLD_QUERIES_PATH
    data = load_json(path, default=[])
    if not isinstance(data, list):
        raise ValueError(f'eval_queries.json must be a list, got {type(data).__name__}')
    for i, q in enumerate(data):
        if not isinstance(q, dict) or 'query' not in q:
            raise ValueError(f'eval_queries[{i}] missing required "query" field')
    return data


# ── Metric helpers ─────────────────────────────────────────────────────────

def _prf(tp: int, fp: int, fn: int) -> dict:
    p = tp / (tp + fp) if (tp + fp) else 0.0
    r = tp / (tp + fn) if (tp + fn) else 0.0
    f = 2 * p * r / (p + r) if (p + r) else 0.0
    return {'precision': round(p, 4), 'recall': round(r, 4),
            'f1': round(f, 4), 'tp': tp, 'fp': fp, 'fn': fn}


def _eq_ci(a: str, b: str) -> bool:
    return (a or '').strip().lower() == (b or '').strip().lower()


def _recall_at_k(ranked_ids: list[int], gold_ids: set[int], k: int) -> float:
    if not gold_ids:
        return 0.0
    top = ranked_ids[:k]
    hits = sum(1 for x in top if x in gold_ids)
    return hits / len(gold_ids)


def _mrr_at_k(ranked_ids: list[int], gold_ids: set[int], k: int) -> float:
    if not gold_ids:
        return 0.0
    for rank, did in enumerate(ranked_ids[:k], start=1):
        if did in gold_ids:
            return 1.0 / rank
    return 0.0


# ── Calibration ────────────────────────────────────────────────────────────

def _brier_score(preds: list[tuple[float, int]]) -> float:
    """Brier score: mean squared error between probability and outcome.

    *preds* is a list of ``(confidence, correct_0_or_1)`` pairs.
    0 = perfect; 0.25 = uninformative (always 0.5); higher is worse.
    """
    if not preds:
        return 0.0
    return sum((p - y) ** 2 for p, y in preds) / len(preds)


def _log_loss(preds: list[tuple[float, int]]) -> float:
    """Binary log loss with clamp to avoid log(0).

    0 = perfect; higher is worse. Uninformative p=0.5 → ln 2 ≈ 0.693.
    """
    if not preds:
        return 0.0
    eps = 1e-15
    total = 0.0
    for p, y in preds:
        p = min(1 - eps, max(eps, p))
        total += -(y * math.log(p) + (1 - y) * math.log(1 - p))
    return total / len(preds)


def _reliability_bins(preds: list[tuple[float, int]],
                      n_bins: int = 10) -> list[dict]:
    """Bucket predictions by confidence; return per-bin stats.

    Each bin carries ``[lo, hi)`` edges plus the mean confidence inside
    the bin, the empirical accuracy, and the count. A well-calibrated
    classifier has ``mean_confidence ≈ accuracy`` in every bin.
    """
    if not preds or n_bins <= 0:
        return []
    bins: list[list[tuple[float, int]]] = [[] for _ in range(n_bins)]
    for p, y in preds:
        # p=1.0 falls into the top bin.
        idx = min(n_bins - 1, int(p * n_bins))
        bins[idx].append((p, y))

    rows: list[dict] = []
    for i, bucket in enumerate(bins):
        lo = i / n_bins
        hi = (i + 1) / n_bins
        if not bucket:
            rows.append({'lo': round(lo, 4), 'hi': round(hi, 4),
                         'count': 0, 'mean_confidence': None,
                         'accuracy': None})
            continue
        mean_c = sum(p for p, _ in bucket) / len(bucket)
        acc    = sum(y for _, y in bucket) / len(bucket)
        rows.append({
            'lo':    round(lo, 4),
            'hi':    round(hi, 4),
            'count': len(bucket),
            'mean_confidence': round(mean_c, 4),
            'accuracy':        round(acc, 4),
        })
    return rows


def _ece(bins: list[dict]) -> float:
    """Expected Calibration Error — weighted gap between accuracy and confidence."""
    total = sum(b['count'] for b in bins)
    if total == 0:
        return 0.0
    gap_sum = 0.0
    for b in bins:
        if b['count'] == 0 or b['accuracy'] is None:
            continue
        gap = abs(b['accuracy'] - b['mean_confidence'])
        gap_sum += b['count'] * gap
    return gap_sum / total


# ── Extended calibration metrics (v0.13) ──────────────────────────────────

def _resolution(bins: list[dict], base_rate: float) -> float:
    """Resolution — how well bins separate from the unconditional base rate.

    From the Brier-score decomposition: Brier = Reliability − Resolution
    + Uncertainty. Higher resolution is better; it's the weighted
    variance of bin accuracy around the base rate. Zero = bins are
    all at the base rate (no discriminating power).
    """
    total = sum(b['count'] for b in bins)
    if total == 0:
        return 0.0
    acc = 0.0
    for b in bins:
        if b['count'] == 0 or b['accuracy'] is None:
            continue
        acc += b['count'] * (b['accuracy'] - base_rate) ** 2
    return acc / total


def _sharpness(preds: list[tuple[float, int]]) -> float:
    """Sharpness — mean distance of predictions from 0.5.

    High sharpness means the model is willing to commit to confident
    predictions; low sharpness means it hedges near 0.5. Orthogonal
    to calibration: a perfectly-calibrated-but-hedging model has low
    sharpness and low Brier; a sharp well-calibrated model is the
    goal.
    """
    if not preds:
        return 0.0
    return sum(abs(p - 0.5) for p, _ in preds) / len(preds)


def _auc_roc(preds: list[tuple[float, int]]) -> float:
    """AUC-ROC via the Mann-Whitney U formulation.

    Equivalent to ``P(score_positive > score_negative)`` with ties
    counted as 0.5. Returns 0.5 if either class is missing.

    Implementation is O(n log n) — sort, then walk and tally how
    many negatives each positive outranks, adjusting for ties.
    """
    if not preds:
        return 0.5
    pos = [p for p, y in preds if y == 1]
    neg = [p for p, y in preds if y == 0]
    if not pos or not neg:
        return 0.5
    # Assign ranks, averaging for ties.
    all_scores = sorted([p for p, _ in preds])
    # Rank lookup: for each distinct score s, the average rank of
    # positions it occupies in the sorted list.
    rank_of: dict[float, float] = {}
    i = 0
    n = len(all_scores)
    while i < n:
        j = i
        while j + 1 < n and all_scores[j + 1] == all_scores[i]:
            j += 1
        # positions i..j (0-based) → ranks i+1..j+1 (1-based)
        avg_rank = (i + 1 + j + 1) / 2.0
        rank_of[all_scores[i]] = avg_rank
        i = j + 1
    rank_sum_pos = sum(rank_of[p] for p in pos)
    n_pos = len(pos)
    n_neg = len(neg)
    u = rank_sum_pos - n_pos * (n_pos + 1) / 2.0
    return u / (n_pos * n_neg)


def _profit_sim(rows: list[dict], *, fractional: float = 0.25,
                cap: float = 0.25, bankroll: float = 1.0) -> dict:
    """Simulate fractional-Kelly P&L on a list of market-priced predictions.

    Each row must be a dict with ``p`` (subjective), ``q`` (market
    price as fraction), ``y`` (0/1 outcome). Bets are sized via
    :func:`library._core.analysis.probability.kelly_fraction`; payoff
    is ``(1-q)/q`` on win, ``-1`` (lose stake) on loss.

    Returns aggregate P&L plus counts. This is the bottom-line
    metric for a trading agent: calibration in service of dollars.
    """
    from library._core.analysis.probability import kelly_fraction

    if not rows:
        return {'n': 0, 'n_bet': 0, 'pnl': 0.0, 'roi': 0.0,
                'wins': 0, 'losses': 0}
    bank = float(bankroll)
    initial = bank
    bets = wins = losses = 0
    for r in rows:
        p = float(r.get('p', 0.5))
        q = float(r.get('q', 0.5))
        y = int(r.get('y', 0))
        f = kelly_fraction(p=p, q=q, fractional=fractional, cap=cap)
        if f <= 0:
            continue
        stake = bank * f
        bets += 1
        if y == 1:
            # Bet pays out stake * (1-q) / q in addition to returning stake.
            bank += stake * (1.0 - q) / q
            wins += 1
        else:
            bank -= stake
            losses += 1
    pnl = bank - initial
    return {
        'n':      len(rows),
        'n_bet':  bets,
        'wins':   wins,
        'losses': losses,
        'pnl':    round(pnl, 6),
        'roi':    round(pnl / initial, 6) if initial else 0.0,
    }


# ── Harness ────────────────────────────────────────────────────────────────

def _calibration_summary(preds: list[tuple[float, int]]) -> dict:
    """Collapse a list of (confidence, correct) pairs to a flat metrics dict.

    Used twice by :func:`run_eval` — once for the primary pass and
    once for the shadow rules-only pass when ``compare_paths=True``.
    """
    bins = _reliability_bins(preds, n_bins=10)
    base_rate = (sum(y for _, y in preds) / len(preds)) if preds else 0.0
    return {
        'n':          len(preds),
        'base_rate':  round(base_rate, 4),
        'brier':      round(_brier_score(preds), 4),
        'log_loss':   round(_log_loss(preds), 4),
        'ece':        round(_ece(bins), 4),
        'resolution': round(_resolution(bins, base_rate), 4),
        'sharpness':  round(_sharpness(preds), 4),
        'auc_roc':    round(_auc_roc(preds), 4),
        'bins':       bins,
    }


def _shadow_rules_pass(queries: list[dict]) -> dict:
    """Re-run intent classification with :class:`NullClient` (rules only).

    Returns a compact report — intent accuracy + calibration summary.
    Only metrics that depend on the intent classifier are recomputed;
    retrieval / entity PRF are path-agnostic so we don't duplicate.
    """
    null = NullClient()
    preds: list[tuple[float, int]] = []
    hits = 0
    with_gold = 0
    for gold in queries:
        ir = classify_intent(gold['query'], client=null)
        exp = gold.get('expected_intent', '')
        if not exp:
            continue
        with_gold += 1
        correct = _eq_ci(ir.intent, exp)
        if correct:
            hits += 1
        preds.append((float(ir.confidence or 0.0), 1 if correct else 0))
    summary = _calibration_summary(preds)
    summary['intent_accuracy'] = round(hits / with_gold, 4) if with_gold else 0.0
    return summary


def _path_comparison_delta(llm: dict, rules: dict) -> dict:
    """Per-key arithmetic delta (llm − rules) over overlapping scalar fields.

    Positive ``intent_accuracy`` / ``auc_roc`` / ``resolution`` /
    ``sharpness`` means LLM is better; positive ``brier`` / ``log_loss``
    / ``ece`` means LLM is worse. Dict is flat so the CLI can diff it
    trivially across runs.
    """
    keys = ('intent_accuracy', 'brier', 'log_loss', 'ece',
            'resolution', 'sharpness', 'auc_roc')
    return {k: round(float(llm.get(k, 0.0)) - float(rules.get(k, 0.0)), 4)
            for k in keys}


def run_eval(
    *,
    queries: list[dict] | None = None,
    client: LLMClient | None = None,
    retrieve: bool = False,
    k_values: Iterable[int] = (1, 3, 5),
    limit: int | None = None,
    compare_paths: bool = False,
) -> dict:
    """Run the gold set and return an aggregated metrics report.

    Parameters:
      queries:  list of gold dicts. Defaults to :func:`load_gold_queries`.
      client:   LLMClient for the intent classifier. ``None`` → default.
      retrieve: if True, also run :func:`hybrid_retrieve` per query and
                compute recall@k / MRR@k for queries with
                ``expected_doc_ids`` (requires a populated DB).
      k_values: which k's to compute retrieval metrics at.
      limit:    only run the first N queries (debug / cost control).
      compare_paths: if True, run a second pass with :class:`NullClient`
                to force the deterministic rules path, and emit a
                ``path_comparison`` block so callers can see whether
                the LLM-augmented classifier actually improves on the
                rules baseline (and by how much, per metric).
    """
    k_values = tuple(sorted({int(k) for k in k_values}))
    queries = list(queries) if queries is not None else load_gold_queries()
    if limit is not None:
        queries = queries[:max(0, int(limit))]

    per_query: list[dict] = []
    intent_hits = 0
    route_hits = 0
    ticker_tp = ticker_fp = ticker_fn = 0
    speaker_tp = speaker_fp = speaker_fn = 0
    recall_sums: dict[int, float] = {k: 0.0 for k in k_values}
    mrr_sums:    dict[int, float] = {k: 0.0 for k in k_values}
    retrieval_n = 0
    # Calibration: one (confidence, correct) pair per query with a gold intent.
    calibration_preds: list[tuple[float, int]] = []

    for gold in queries:
        out: dict = {'id': gold.get('id', ''), 'query': gold['query']}

        # Intent classification
        ir = classify_intent(gold['query'], client=client)
        out['actual'] = {
            'intent':     ir.intent,
            'route':      ir.route,
            'source':     ir.source,
            'entities':   ir.entities,
            'confidence': float(ir.confidence or 0.0),
        }
        exp_intent = gold.get('expected_intent', '')
        exp_route  = gold.get('expected_route', '')
        out['intent_ok'] = _eq_ci(ir.intent, exp_intent) if exp_intent else None
        out['route_ok']  = _eq_ci(ir.route, exp_route)   if exp_route  else None
        if out['intent_ok']:
            intent_hits += 1
        if out['route_ok']:
            route_hits += 1

        # Calibration: score this query if it has a gold intent label.
        if exp_intent:
            calibration_preds.append(
                (float(ir.confidence or 0.0), 1 if out['intent_ok'] else 0)
            )

        # Entity PRF — ticker and speaker only (most-used).
        exp_ent = gold.get('expected_entities') or {}
        for field, tp_add, fp_add, fn_add in _entity_counts(
            exp_ent, ir.entities, 'ticker',
        ):
            ticker_tp += tp_add; ticker_fp += fp_add; ticker_fn += fn_add
        for field, tp_add, fp_add, fn_add in _entity_counts(
            exp_ent, ir.entities, 'speaker',
        ):
            speaker_tp += tp_add; speaker_fp += fp_add; speaker_fn += fn_add

        # Retrieval (optional)
        if retrieve and gold.get('expected_doc_ids'):
            try:
                from library._core.retrieve import hybrid_retrieve
                hits = hybrid_retrieve(
                    gold['query'], limit=max(k_values),
                )
                ranked = [h.document_id for h in hits]
                gold_set = set(int(x) for x in gold['expected_doc_ids'])
                per_k = {}
                for k in k_values:
                    rk = _recall_at_k(ranked, gold_set, k)
                    mk = _mrr_at_k(ranked, gold_set, k)
                    per_k[str(k)] = {'recall': rk, 'mrr': mk}
                    recall_sums[k] += rk
                    mrr_sums[k]    += mk
                out['retrieval'] = {'ranked_doc_ids': ranked[:max(k_values)],
                                    'per_k': per_k}
                retrieval_n += 1
            except Exception as exc:
                out['retrieval'] = {'error': str(exc)}

        per_query.append(out)

    total = len(queries) or 1
    primary_cal = _calibration_summary(calibration_preds)
    # Profit sim rows — only queries that carry p/q/y in gold.
    pnl_rows: list[dict] = []
    for gold, qout in zip(queries, per_query):
        if 'expected_outcome' in gold and 'market_price' in gold:
            try:
                pnl_rows.append({
                    'p': float(qout['actual'].get('confidence') or 0.0),
                    'q': float(gold['market_price']),
                    'y': int(gold['expected_outcome']),
                })
            except (TypeError, ValueError):
                pass

    report = {
        'timestamp': now_iso(),
        'n_queries': len(queries),
        'intent_accuracy': round(intent_hits / total, 4),
        'route_accuracy':  round(route_hits / total, 4),
        'ticker_prf':  _prf(ticker_tp, ticker_fp, ticker_fn),
        'speaker_prf': _prf(speaker_tp, speaker_fp, speaker_fn),
        'calibration': primary_cal,
        'profit_sim': _profit_sim(pnl_rows) if pnl_rows else None,
        'retrieval': (
            {
                'n_queries_with_gold': retrieval_n,
                'recall_at_k': {str(k): round(recall_sums[k] / retrieval_n, 4)
                                for k in k_values} if retrieval_n else {},
                'mrr_at_k':    {str(k): round(mrr_sums[k] / retrieval_n, 4)
                                for k in k_values} if retrieval_n else {},
            } if retrieve else None
        ),
        'queries': per_query,
    }
    if compare_paths:
        primary_summary = {
            'intent_accuracy': report['intent_accuracy'],
            **{k: primary_cal[k] for k in (
                'n', 'base_rate', 'brier', 'log_loss', 'ece',
                'resolution', 'sharpness', 'auc_roc',
            )},
        }
        rules_summary = _shadow_rules_pass(queries)
        report['path_comparison'] = {
            'llm':   primary_summary,
            'rules': {k: rules_summary[k] for k in (
                'intent_accuracy', 'n', 'base_rate', 'brier', 'log_loss',
                'ece', 'resolution', 'sharpness', 'auc_roc',
            )},
            'delta': _path_comparison_delta(primary_summary, rules_summary),
        }
    return report


def _entity_counts(expected: dict, actual: dict, field: str):
    """Yield (field, tp, fp, fn) tuples for a single-valued entity field.

    We only count presence/absence — a field in ``expected`` means
    "should be extracted"; matching is case-insensitive substring.
    """
    exp = (expected.get(field) or '').strip()
    act = (actual.get(field) or '').strip()
    if exp and act:
        if exp.lower() in act.lower() or act.lower() in exp.lower():
            yield (field, 1, 0, 0)
        else:
            yield (field, 0, 1, 1)
    elif exp and not act:
        yield (field, 0, 0, 1)
    elif act and not exp:
        yield (field, 0, 1, 0)
    else:
        # Nothing expected, nothing produced — no-op.
        yield (field, 0, 0, 0)


# ── CLI entrypoint ─────────────────────────────────────────────────────────

def run_and_persist(*, retrieve: bool = False,
                    limit: int | None = None,
                    compare_paths: bool = False) -> dict:
    """Run the harness and persist the report to EVAL_REPORT."""
    from library.config import EVAL_REPORT
    report = run_eval(retrieve=retrieve, limit=limit,
                      compare_paths=compare_paths)
    try:
        EVAL_REPORT.parent.mkdir(parents=True, exist_ok=True)
        EVAL_REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2),
                               encoding='utf-8')
    except OSError as exc:
        log.warning('Failed to persist eval report: %s', exc)
    return report
