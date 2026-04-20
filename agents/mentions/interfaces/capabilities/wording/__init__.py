"""Wording capability interface."""

from agents.mentions.interfaces.capabilities.wording.api import check_text, enforce_text
from agents.mentions.interfaces.capabilities.wording.service import WordingCapabilityService

__all__ = ['WordingCapabilityService', 'check_text', 'enforce_text']
