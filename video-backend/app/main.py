"""FastAPI application factory.

``create_app`` assembles the app from explicit components so production
(Modal-backed) and tests (in-memory) share one wiring path. A module-level
``app`` built from environment settings is exposed for ``uvicorn`` / Modal.
"""

from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from .api import router
from .auth import GoogleTokenVerifier, TokenVerifier
from .config import Settings, get_settings
from .errors import ApiError, ErrorCode
from .jobs import JobService
from .storage import (
    FileStore,
    InMemoryMetadataStore,
    LocalFileStore,
    MetadataStore,
)
from .worker import LocalPlaceholderProcessor, Processor


def create_app(
    *,
    settings: Settings | None = None,
    verifier: TokenVerifier | None = None,
    files: FileStore | None = None,
    meta: MetadataStore | None = None,
    processor: Processor | None = None,
) -> FastAPI:
    settings = settings or get_settings()
    files = files or LocalFileStore(settings.data_dir)
    meta = meta or InMemoryMetadataStore()
    verifier = verifier or GoogleTokenVerifier(settings.google_web_client_id)

    job_service = JobService(meta, files)
    processor = processor or LocalPlaceholderProcessor(job_service, files)

    app = FastAPI(title="AI Video Upscaler", version=settings.api_version)

    # Components shared with route handlers via request.app.state.
    app.state.settings = settings
    app.state.verifier = verifier
    app.state.files = files
    app.state.meta = meta
    app.state.job_service = job_service
    app.state.processor = processor

    app.include_router(router)
    _register_error_handlers(app)
    return app


def _register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(ApiError)
    async def _handle_api_error(_: Request, exc: ApiError) -> JSONResponse:
        return JSONResponse(status_code=exc.http_status, content=exc.to_dict())

    @app.exception_handler(RequestValidationError)
    async def _handle_validation(_: Request, exc: RequestValidationError) -> JSONResponse:
        err = ApiError(ErrorCode.VALIDATION_ERROR, "Request validation failed")
        return JSONResponse(status_code=err.http_status, content=err.to_dict())


# Default app for `uvicorn app.main:app` and Modal ASGI mounting.
app = create_app()
