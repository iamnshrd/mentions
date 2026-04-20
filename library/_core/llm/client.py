"""LLM client protocol with Null and Anthropic implementations.

Design goals:

* **Pluggable**: every consumer (intent classifier, extraction
  pipeline) takes an :class:`LLMClient` instance; tests supply a fake
  and production code supplies :class:`AnthropicClient` when an API
  key is present.
* **Optional dependency**: the ``anthropic`` SDK is imported lazily
  inside :class:`AnthropicClient._client` — callers that don't opt in
  never touch it.
* **Prompt caching**: :meth:`AnthropicClient.complete` accepts a
  ``cache_system`` flag. When set, the system prompt is sent with
  ``cache_control={"type": "ephemeral"}`` so repeated calls (e.g.
  extracting from each chunk of a document) hit the Anthropic prompt
  cache.
* **Structured JSON**: :meth:`LLMClient.complete_json` returns a dict
  parsed from the model's response, with a best-effort fallback to
  extract a JSON block out of surrounding prose.

Environment:

* ``ANTHROPIC_API_KEY`` — required for :class:`AnthropicClient`. If
  missing, :func:`default_client` returns :class:`NullClient` so
  callers degrade gracefully to rule-based paths.

Model selection:

* Default model for intent + extraction is ``claude-haiku-4-5`` (fast
  and cheap). Override per-call via the ``model`` arg.
"""
from __future__ import annotations

import json
import logging
import os
import re
from dataclasses import dataclass
from typing import Protocol

log = logging.getLogger('mentions')


DEFAULT_MODEL = 'claude-haiku-4-5'


# ── Data classes ───────────────────────────────────────────────────────────

@dataclass
class LLMResponse:
    """Lightweight completion result; ``text`` is always a string."""
    text:        str
    model:       str = ''
    stop_reason: str = ''
    input_tokens:  int = 0
    output_tokens: int = 0
    cache_read_tokens:    int = 0
    cache_create_tokens:  int = 0


# ── Protocol ───────────────────────────────────────────────────────────────

class LLMClient(Protocol):
    """Minimal interface every LLM client must satisfy."""

    def complete(
        self,
        *,
        system: str,
        user: str,
        model: str = DEFAULT_MODEL,
        max_tokens: int = 1024,
        temperature: float = 0.0,
        cache_system: bool = False,
    ) -> LLMResponse:
        ...

    def complete_json(
        self,
        *,
        system: str,
        user: str,
        model: str = DEFAULT_MODEL,
        max_tokens: int = 1024,
        temperature: float = 0.0,
        cache_system: bool = False,
    ) -> dict | None:
        ...


# ── Null client (default) ──────────────────────────────────────────────────

class NullClient:
    """No-op client. Every call returns an empty response.

    Callers that need LLM output should interpret an empty text (or a
    ``None`` from :meth:`complete_json`) as a signal to fall back to
    their rule-based path.
    """

    def complete(self, **_kw) -> LLMResponse:
        return LLMResponse(text='')

    def complete_json(self, **_kw) -> dict | None:
        return None


# ── Anthropic client (optional) ────────────────────────────────────────────

class AnthropicClient:
    """Claude-backed client with prompt caching.

    Requires ``pip install anthropic`` and ``ANTHROPIC_API_KEY`` set.
    Created lazily on first call; safe to instantiate even when the
    SDK is missing (the failure surfaces only on :meth:`complete`).
    """

    _sdk_client = None

    def __init__(self, *, api_key: str | None = None,
                 default_model: str = DEFAULT_MODEL,
                 max_attempts: int = 3,
                 base_delay: float = 1.0,
                 breaker_threshold: int = 5,
                 breaker_cooldown: float = 30.0):
        from library._core.llm.retry import CircuitBreaker
        self._api_key = api_key or os.getenv('ANTHROPIC_API_KEY', '')
        self._default_model = default_model
        self._max_attempts = max_attempts
        self._base_delay   = base_delay
        self._breaker = CircuitBreaker(threshold=breaker_threshold,
                                       cooldown_seconds=breaker_cooldown)

    def _client(self):
        if AnthropicClient._sdk_client is not None:
            return AnthropicClient._sdk_client
        try:
            import anthropic
        except ImportError as exc:
            raise RuntimeError(
                'anthropic package not installed. '
                'Run `pip install anthropic` to enable AnthropicClient.'
            ) from exc
        if not self._api_key:
            raise RuntimeError(
                'ANTHROPIC_API_KEY not set. '
                'Set it in the environment before using AnthropicClient.'
            )
        AnthropicClient._sdk_client = anthropic.Anthropic(api_key=self._api_key)
        return AnthropicClient._sdk_client

    # ── Core completion ────────────────────────────────────────────────────

    def complete(
        self,
        *,
        system: str,
        user: str,
        model: str | None = None,
        max_tokens: int = 1024,
        temperature: float = 0.0,
        cache_system: bool = False,
    ) -> LLMResponse:
        from library._core.obs import get_collector, trace_event
        metrics = get_collector()

        client = self._client()
        model = model or self._default_model

        # System prompt as a list so we can attach cache_control to
        # individual blocks — the Anthropic SDK accepts either a plain
        # string or a list of text blocks.
        if cache_system and system:
            system_arg = [{
                'type': 'text',
                'text': system,
                'cache_control': {'type': 'ephemeral'},
            }]
        else:
            system_arg = system

        metrics.incr('llm.call_attempt', tags={'model': model})

        from library._core.llm.retry import (
            with_retry, CircuitOpenError,
        )

        def _on_retry(attempt, exc, delay):
            metrics.incr('llm.retry', tags={'model': model})
            trace_event('llm.retry', model=model, attempt=attempt,
                        error=str(exc), delay=delay)

        def _do_call():
            return self._breaker.call(lambda: client.messages.create(
                model=model,
                system=system_arg,
                messages=[{'role': 'user', 'content': user}],
                max_tokens=max_tokens,
                temperature=temperature,
            ))

        try:
            with metrics.timed('llm.latency_ms', tags={'model': model}):
                resp = with_retry(
                    _do_call,
                    max_attempts=self._max_attempts,
                    base_delay=self._base_delay,
                    on_retry=_on_retry,
                )
        except CircuitOpenError as exc:
            log.warning('AnthropicClient.complete short-circuited: %s', exc)
            metrics.incr('llm.circuit_open', tags={'model': model})
            trace_event('llm.call', model=model, ok=False,
                        circuit_open=True, error=str(exc))
            return LLMResponse(text='', model=model)
        except Exception as exc:
            log.warning('AnthropicClient.complete failed: %s', exc)
            metrics.incr('llm.call_err', tags={'model': model})
            trace_event('llm.call', model=model, ok=False, error=str(exc))
            return LLMResponse(text='', model=model)

        metrics.incr('llm.call_ok', tags={'model': model})

        text = ''
        for block in getattr(resp, 'content', []) or []:
            # Text-only blocks; ignore tool_use etc.
            if getattr(block, 'type', '') == 'text':
                text += getattr(block, 'text', '') or ''

        usage = getattr(resp, 'usage', None)
        in_tok  = getattr(usage, 'input_tokens', 0) or 0
        out_tok = getattr(usage, 'output_tokens', 0) or 0
        cr_tok  = getattr(usage, 'cache_read_input_tokens', 0) or 0
        cc_tok  = getattr(usage, 'cache_creation_input_tokens', 0) or 0
        metrics.incr('llm.input_tokens',        n=in_tok,  tags={'model': model})
        metrics.incr('llm.output_tokens',       n=out_tok, tags={'model': model})
        metrics.incr('llm.cache_read_tokens',   n=cr_tok,  tags={'model': model})
        metrics.incr('llm.cache_create_tokens', n=cc_tok,  tags={'model': model})

        from library._core.llm.pricing import cost_usd
        call_cost = cost_usd(model=model, input_tokens=in_tok,
                             output_tokens=out_tok,
                             cache_read_tokens=cr_tok,
                             cache_create_tokens=cc_tok)
        # Per-call observation for p95 latency-of-cost.
        metrics.observe('llm.cost_usd', call_cost, tags={'model': model})
        # Counter in integer micro-USD for exact cumulative totals.
        metrics.incr('llm.cost_micro_usd',
                     n=int(round(call_cost * 1_000_000)),
                     tags={'model': model})

        trace_event('llm.call',
                    model=model, ok=True,
                    input_tokens=in_tok, output_tokens=out_tok,
                    cache_read_tokens=cr_tok, cache_create_tokens=cc_tok,
                    cost_usd=round(call_cost, 6),
                    stop_reason=getattr(resp, 'stop_reason', '') or '')
        return LLMResponse(
            text=text,
            model=model,
            stop_reason=getattr(resp, 'stop_reason', '') or '',
            input_tokens=in_tok,
            output_tokens=out_tok,
            cache_read_tokens=cr_tok,
            cache_create_tokens=cc_tok,
        )

    def complete_json(self, **kwargs) -> dict | None:
        """Request a JSON completion and parse it.

        On parse failure, returns ``None`` rather than raising — the
        caller is expected to either retry or fall back.
        """
        resp = self.complete(**kwargs)
        return _parse_json_text(resp.text)


# ── JSON extraction ────────────────────────────────────────────────────────

_JSON_BLOCK_RE = re.compile(
    r'```(?:json)?\s*(\{.*?\}|\[.*?\])\s*```',
    re.DOTALL,
)


def _parse_json_text(text: str) -> dict | None:
    r"""Best-effort JSON extraction from model output.

    Strategy:
      1. Direct ``json.loads``.
      2. Fenced ``\`\`\`json ... \`\`\``` block.
      3. First ``{...}`` substring.
    Returns ``None`` if nothing parses.
    """
    if not text:
        return None
    text = text.strip()

    # Direct parse
    try:
        obj = json.loads(text)
        return obj if isinstance(obj, dict) else None
    except json.JSONDecodeError:
        pass

    # Fenced code block
    m = _JSON_BLOCK_RE.search(text)
    if m:
        try:
            obj = json.loads(m.group(1))
            return obj if isinstance(obj, dict) else None
        except json.JSONDecodeError:
            pass

    # First {...} span — greedy, with balanced-brace scan
    start = text.find('{')
    if start >= 0:
        depth = 0
        for i in range(start, len(text)):
            if text[i] == '{':
                depth += 1
            elif text[i] == '}':
                depth -= 1
                if depth == 0:
                    try:
                        obj = json.loads(text[start:i + 1])
                        return obj if isinstance(obj, dict) else None
                    except json.JSONDecodeError:
                        break
    return None


# ── Factory ────────────────────────────────────────────────────────────────

def default_client() -> LLMClient:
    """Return :class:`AnthropicClient` if the SDK + API key are both
    present, else :class:`NullClient`.

    Safe to call at import time — neither path raises.
    """
    if not os.getenv('ANTHROPIC_API_KEY'):
        return NullClient()
    try:
        import anthropic  # noqa: F401
    except ImportError:
        return NullClient()
    return AnthropicClient()
