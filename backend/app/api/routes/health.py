import asyncio

from fastapi import APIRouter, Response, status

from app.clients.redis import redis_ping
from app.core.config import settings
from app.db.session import database_ping
from app.schemas.health import HealthResponse, LivenessResponse

router = APIRouter(tags=["health"])


@router.get("/health/live", response_model=LivenessResponse)
async def liveness() -> LivenessResponse:
    return LivenessResponse(
        status="ok",
        service=settings.app_name,
        version=settings.app_version,
    )


@router.get("/health", response_model=HealthResponse)
async def health(response: Response) -> HealthResponse:
    database_ok, redis_ok = await asyncio.gather(database_ping(), redis_ping())

    overall_status = "ok" if database_ok and redis_ok else "degraded"
    if overall_status != "ok":
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE

    return HealthResponse(
        status=overall_status,
        service=settings.app_name,
        version=settings.app_version,
        database="ok" if database_ok else "unavailable",
        redis="ok" if redis_ok else "unavailable",
    )
