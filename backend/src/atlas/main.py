import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware

from atlas import __version__
from atlas.api.router import api_router
from atlas.config import get_settings
from atlas.database import close_database
from atlas.errors import AppError, app_error_handler
from atlas.logging import configure_logging
from atlas.middleware import RequestContextMiddleware

settings = get_settings()
configure_logging(settings.log_level)
logger = structlog.get_logger("atlas")


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    worker_task: asyncio.Task[None] | None = None
    if settings.database_url:
        from atlas.services.jobs import JobRunner

        worker_task = asyncio.create_task(JobRunner(settings).run_forever(), name="ingestion-worker")
        logger.info("ingestion_worker_started")
    yield
    if worker_task is not None:
        worker_task.cancel()
        await asyncio.gather(worker_task, return_exceptions=True)
    await close_database()


app = FastAPI(
    title="Atlas RAG API",
    description="Authenticated, user-isolated retrieval augmented generation API.",
    version=__version__,
    docs_url="/docs" if settings.app_env != "production" else None,
    redoc_url=None,
    lifespan=lifespan,
)
app.add_middleware(RequestContextMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Request-ID"],
    expose_headers=["X-Request-ID"],
)
if settings.trusted_host_list:
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=settings.trusted_host_list)
app.add_exception_handler(AppError, app_error_handler)
app.include_router(api_router, prefix=settings.api_v1_prefix)


@app.get("/", include_in_schema=False)
async def root() -> dict[str, str]:
    return {"service": "Atlas RAG API", "version": __version__}
