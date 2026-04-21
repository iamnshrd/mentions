"""Pydantic schemas for the Mentions HTTP API."""
from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, model_validator


class WorkspaceRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')

    query: str | None = None
    market_url: str | None = None
    user_id: str = 'default'
    news_limit: int = Field(default=5, ge=1, le=20)
    transcript_limit: int = Field(default=5, ge=1, le=20)

    @model_validator(mode='after')
    def validate_input_mode(self) -> 'WorkspaceRequest':
        query = (self.query or '').strip()
        market_url = (self.market_url or '').strip()
        if bool(query) == bool(market_url):
            raise ValueError('provide exactly one of query or market_url')
        self.query = query or None
        self.market_url = market_url or None
        return self


class HealthResponse(BaseModel):
    ok: bool = True
    status: str = 'ok'
    service: str = 'mentions-workspace-api'


class ErrorDetail(BaseModel):
    code: str
    message: str


class ErrorResponse(BaseModel):
    ok: bool = False
    error: ErrorDetail


class WorkspaceSuccessResponse(BaseModel):
    ok: bool = True
    payload: dict
