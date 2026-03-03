import redis, hashlib, json
from typing import Any
from src.core.config import get_settings
from src.core.logging import get_logger

logger = get_logger(__name__)
settings = get_settings()


class CacheService:
    def __init__(self):
        self.client = redis.Redis(
            host=settings.REDIS_HOST,
            port=settings.REDIS_PORT,
            decode_responses=True
        )
        self.ttl = settings.CACHE_TTL

    def _make_keys(self, question: str) -> str:
        normalized = question.strip().lower()
        return "query:" + hashlib.md5(normalized.encode()).hexdigest()

    def get_cached(self, question: str) -> list[dict[str, Any]]:
        key = self._make_keys(question)
        try:
            value = self.client.get(key)
            if value:
                logger.info(f"Cache HIT for key {key}")
                return json.loads(value)
            logger.info(f"Cache MISS for key {key}")
            return None
        except Exception as e:
            logger.warning(f"Cache GET Failed: {e}")
            return None
        
    def set_cached(self, question: str, data: list[dict[str, Any]]) -> None:
        key = self._make_keys(question)
        try:
            self.client.setex(key, self.ttl, json.dumps(data, default=str))
            logger.info(f"Cache SET for key {key}, TTL={self.ttl}s")
        except Exception as e:
            logger.warning(f"Cache SET Failed: {e}")