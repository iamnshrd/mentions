"""News-context capability interface."""

from agents.mentions.interfaces.capabilities.news_context.api import (
    build_context,
    fetch_news,
)
from agents.mentions.interfaces.capabilities.news_context.service import NewsContextCapabilityService

__all__ = ['NewsContextCapabilityService', 'build_context', 'fetch_news']
