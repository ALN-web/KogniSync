import asyncio
from datetime import UTC, datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Response, status
from pydantic import BaseModel

from app.core.config import Settings, get_settings
from app.core.health import DependencyStatus, check_secret_present, check_tcp

router = APIRouter(tags=["health"])

SettingsDep = Annotated[Settings, Depends(get_settings)]


class LivenessResponse(BaseModel):
    status: Literal["ok"]
    service: str
    version: str
    environment: str
    time: datetime


class ReadinessResponse(BaseModel):
    status: Literal["ready", "degraded"]
    dependencies: list[DependencyStatus]


@router.get("/health", response_model=LivenessResponse)
async def liveness(settings: SettingsDep) -> LivenessResponse:
    """Liveness: the process is up. Never touches dependencies."""
    return LivenessResponse(
        status="ok",
        service=settings.app_name,
        version=settings.version,
        environment=settings.app_env,
        time=datetime.now(UTC),
    )


@router.get("/health/ready", response_model=ReadinessResponse)
async def readiness(response: Response, settings: SettingsDep) -> ReadinessResponse:
    """Readiness: configured dependencies are reachable.

    A dependency that is not configured does not fail readiness (local dev runs without
    Postgres and Redis in M1); one that is configured but unreachable returns 503.
    """
    postgres, redis = await asyncio.gather(
        check_tcp("postgres", settings.database_url),
        check_tcp("redis", settings.redis_url),
    )
    deps = [postgres, redis, check_secret_present("gemini", settings.gemini_api_key)]
    if any(d.status == "error" for d in deps):
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return ReadinessResponse(status="degraded", dependencies=deps)
    return ReadinessResponse(status="ready", dependencies=deps)
