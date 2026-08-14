from __future__ import annotations

import os
import secrets

import uvicorn
from fastapi import Depends, FastAPI, Header, HTTPException, status

from tiktok_factory.api.service import FactoryOrchestrationService, RunRequest, RunResponse


def create_app(
    service: FactoryOrchestrationService | None = None,
    *,
    api_token: str | None = None,
) -> FastAPI:
    app = FastAPI(
        title="TikTok AI Factory API",
        version="4.0.0",
        docs_url=None,
        redoc_url=None,
    )
    orchestration = service or FactoryOrchestrationService()
    expected_token = api_token if api_token is not None else os.getenv("FACTORY_API_TOKEN")

    def authorize(authorization: str | None = Header(default=None)) -> None:
        if not expected_token:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="FACTORY_API_TOKEN is not configured",
            )
        prefix = "Bearer "
        if authorization is None or not authorization.startswith(prefix):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="invalid bearer token",
            )
        supplied = authorization[len(prefix):]
        if not secrets.compare_digest(supplied, expected_token):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="invalid bearer token",
            )

    @app.get("/healthz")
    def healthz() -> dict[str, str]:
        return {"status": "ok", "service": "tiktok-ai-factory"}

    @app.post("/v1/runs", response_model=RunResponse)
    def create_run(
        request: RunRequest,
        _authorization: None = Depends(authorize),
    ) -> RunResponse:
        try:
            return orchestration.run(request)
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(exc),
            ) from exc
        except RuntimeError as exc:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=str(exc),
            ) from exc

    return app


app = create_app()


def run() -> None:
    uvicorn.run(
        "tiktok_factory.api.app:app",
        host=os.getenv("FACTORY_API_HOST", "0.0.0.0"),
        port=int(os.getenv("PORT", "8000")),
        log_level=os.getenv("FACTORY_API_LOG_LEVEL", "info"),
    )
