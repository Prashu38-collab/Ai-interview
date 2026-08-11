"""FastAPI application factory and root router mounting."""

import logging

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.core.config import get_settings
from app.routers import answers, auth, interviews, questions, reports
from app.services.ai.llm_service import AIProviderError, AIResponseError

settings = get_settings()
logger = logging.getLogger(__name__)


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.app_name,
        version="1.0.0",
        description="AI-powered technical interview platform.",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.exception_handler(AIProviderError)
    async def ai_provider_handler(request: Request, exc: AIProviderError) -> JSONResponse:
        """LLM provider is down / misconfigured -> friendly 503, full detail in logs."""
        logger.error("AI provider error on %s %s: %s", request.method, request.url.path, exc)
        return JSONResponse(
            status_code=503,
            content={"detail": "The AI service is temporarily unavailable. Please try again."},
        )

    @app.exception_handler(AIResponseError)
    async def ai_response_handler(request: Request, exc: AIResponseError) -> JSONResponse:
        """LLM returned unusable output -> 502 with a safe message."""
        logger.error("AI response error on %s %s: %s", request.method, request.url.path, exc)
        return JSONResponse(
            status_code=502,
            content={"detail": "The AI returned an invalid response. Please try again."},
        )

    app.include_router(auth.router)
    app.include_router(interviews.router)
    app.include_router(questions.router)
    app.include_router(answers.router)
    app.include_router(reports.router)

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()
