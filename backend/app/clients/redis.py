import logging

from redis.asyncio import Redis
from redis.exceptions import RedisError

from app.core.config import settings

logger = logging.getLogger(__name__)

redis_client: Redis = Redis.from_url(
    settings.redis_url,
    encoding="utf-8",
    decode_responses=True,
)


async def redis_ping() -> bool:
    try:
        return bool(await redis_client.ping())
    except RedisError as exc:
        logger.warning("Redis health check failed: %s", exc)
        return False
