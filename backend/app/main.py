import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.router import api_router
from app.clients.redis import redis_client
from app.core.config import settings
from app.db.session import async_session_maker, engine
from app.services.runtime import recover_incomplete_runs

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    async with async_session_maker() as session:
        recovered = await recover_incomplete_runs(session)
        if recovered:
            logger.warning(
                "Recovered %s interrupted Run(s) into PAUSED state",
                recovered,
            )

    yield
    await redis_client.aclose()
    await engine.dispose()


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="Control plane and runtime API for Enterprise Agent Runtime Platform.",
    lifespan=lifespan,
)

app.include_router(api_router)


@app.get("/", tags=["meta"])
async def root() -> dict[str, str]:
    return {
        "service": settings.app_name,
        "version": settings.app_version,
        "status": "running",
    }
