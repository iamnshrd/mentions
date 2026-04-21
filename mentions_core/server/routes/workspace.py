"""Workspace API routes."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException

from agents.mentions.application.workspace_service import build_workspace_payload_for_input
from mentions_core.server.schemas import (
    ErrorResponse,
    HealthResponse,
    WorkspaceRequest,
    WorkspaceSuccessResponse,
)

router = APIRouter(tags=['workspace'])


@router.get('/api/health', response_model=HealthResponse)
def get_health() -> HealthResponse:
    return HealthResponse()


@router.post(
    '/api/workspace',
    response_model=WorkspaceSuccessResponse,
    responses={
        400: {'model': ErrorResponse},
        500: {'model': ErrorResponse},
    },
)
def post_workspace(request: WorkspaceRequest) -> WorkspaceSuccessResponse:
    try:
        payload = build_workspace_payload_for_input(
            query=request.query,
            market_url=request.market_url,
            user_id=request.user_id,
            news_limit=request.news_limit,
            transcript_limit=request.transcript_limit,
        )
        return WorkspaceSuccessResponse(payload=payload)
    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail={'code': 'bad_request', 'message': str(exc)},
        ) from exc
    except Exception as exc:  # noqa: BLE001 - HTTP boundary
        raise HTTPException(
            status_code=500,
            detail={'code': 'internal_error', 'message': str(exc)},
        ) from exc
