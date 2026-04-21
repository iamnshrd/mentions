"""FastAPI app for serving Mentions workspace payloads."""
from __future__ import annotations

import os

try:
    from fastapi import FastAPI, HTTPException, Request
    from fastapi.exceptions import RequestValidationError
    from fastapi.middleware.cors import CORSMiddleware
    from fastapi.responses import JSONResponse
except ImportError:  # pragma: no cover - optional web extra
    FastAPI = None
    HTTPException = None
    Request = None
    RequestValidationError = None
    CORSMiddleware = None
    JSONResponse = None


def _cors_origins() -> list[str]:
    raw = os.getenv('MENTIONS_WEB_CORS_ORIGINS', '').strip()
    if raw:
        return [item.strip() for item in raw.split(',') if item.strip()]
    return [
        'http://localhost:3000',
        'http://127.0.0.1:3000',
        'http://localhost:5173',
        'http://127.0.0.1:5173',
        'https://iamnshrd.github.io',
    ]


def create_app():
    if FastAPI is None:  # pragma: no cover - depends on optional install
        raise RuntimeError(
            'FastAPI is not installed. Install the web extra: pip install -e \'.[web]\''
        )

    from mentions_core.server.routes.workspace import router as workspace_router

    app = FastAPI(
        title='Mentions Workspace API',
        version='0.1.0',
        docs_url='/api/docs',
        openapi_url='/api/openapi.json',
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=_cors_origins(),
        allow_credentials=False,
        allow_methods=['GET', 'POST', 'OPTIONS'],
        allow_headers=['*'],
    )
    app.include_router(workspace_router)

    @app.exception_handler(HTTPException)
    async def handle_http_exception(_request: Request, exc: HTTPException):
        detail = exc.detail
        if not isinstance(detail, dict):
            detail = {'code': 'http_error', 'message': str(detail)}
        return JSONResponse(
            status_code=exc.status_code,
            content={'ok': False, 'error': detail},
        )

    @app.exception_handler(RequestValidationError)
    async def handle_validation_exception(_request: Request, exc: RequestValidationError):
        return JSONResponse(
            status_code=400,
            content={
                'ok': False,
                'error': {
                    'code': 'bad_request',
                    'message': str(exc),
                },
            },
        )

    @app.exception_handler(Exception)
    async def handle_unexpected_exception(_request: Request, exc: Exception):
        return JSONResponse(
            status_code=500,
            content={
                'ok': False,
                'error': {'code': 'internal_error', 'message': str(exc)},
            },
        )

    return app


app = create_app() if FastAPI is not None else None
