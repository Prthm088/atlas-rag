from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from atlas import __version__
from atlas.config import Settings, get_settings
from atlas.database import get_db
from atlas.errors import AppError
from atlas.schemas import HealthResponse

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
async def health(settings: Settings = Depends(get_settings)) -> HealthResponse:
    missing = settings.missing_runtime_configuration()
    return HealthResponse(
        status="degraded" if missing else "ok",
        service=settings.app_name,
        version=__version__,
        missing_configuration=missing,
    )


@router.get("/ready", response_model=HealthResponse)
async def readiness(
    session: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> HealthResponse:
    await session.execute(text("select 1"))
    missing = settings.missing_runtime_configuration()
    if missing:
        raise AppError(
            "service_not_ready",
            "The service is missing required runtime configuration.",
            status_code=503,
            details={"missing_configuration": missing},
        )
    return HealthResponse(
        status="ok",
        service=settings.app_name,
        version=__version__,
        missing_configuration=[],
    )
