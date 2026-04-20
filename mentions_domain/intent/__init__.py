"""Canonical intent classification domain logic."""

from .classifier import INTENTS, IntentResult, classify_intent

__all__ = ['INTENTS', 'IntentResult', 'classify_intent']
