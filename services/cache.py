"""Redis cache service"""
import json
import pickle
from typing import Optional, Any
import redis
from config.settings import settings
from config.logging import logger


class CacheService:
    """Redis-based caching service"""

    def __init__(self):
        self.client = redis.from_url(settings.REDIS_URL, decode_responses=True)
        self.ttl_company = 86400  # 24 hours
        self.ttl_embedding = 604800  # 7 days
        self.ttl_llm = 3600  # 1 hour
        logger.info("CacheService initialized")

    def get(self, key: str) -> Optional[Any]:
        """Get value from cache"""
        try:
            value = self.client.get(key)
            if value:
                logger.debug(f"Cache HIT: {key}")
                return json.loads(value)
            logger.debug(f"Cache MISS: {key}")
            return None
        except Exception as e:
            logger.error(f"Cache get error: {e}")
            return None

    def set(self, key: str, value: Any, ttl: int = 3600) -> bool:
        """Set value in cache"""
        try:
            self.client.setex(key, ttl, json.dumps(value))
            logger.debug(f"Cache SET: {key}")
            return True
        except Exception as e:
            logger.error(f"Cache set error: {e}")
            return False

    def get_company(self, domain: str) -> Optional[dict]:
        """Get cached company research"""
        return self.get(f"company:{domain}")

    def set_company(self, domain: str, data: dict) -> bool:
        """Cache company research"""
        return self.set(f"company:{domain}", data, self.ttl_company)

    def get_llm_response(self, prompt_hash: str) -> Optional[str]:
        """Get cached LLM response"""
        return self.get(f"llm:{prompt_hash}")

    def set_llm_response(self, prompt_hash: str, response: str) -> bool:
        """Cache LLM response"""
        return self.set(f"llm:{prompt_hash}", response, self.ttl_llm)

    def delete(self, key: str) -> bool:
        """Delete key from cache"""
        try:
            self.client.delete(key)
            return True
        except Exception as e:
            logger.error(f"Cache delete error: {e}")
            return False

    def flush(self) -> bool:
        """Flush all cache"""
        try:
            self.client.flushdb()
            logger.info("Cache flushed")
            return True
        except Exception as e:
            logger.error(f"Cache flush error: {e}")
            return False
