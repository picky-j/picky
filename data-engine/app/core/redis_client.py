"""
Redis 캐싱 클라이언트
"""
import json
import logging
from typing import Optional, Any
import redis.asyncio as redis
from .config import settings

logger = logging.getLogger(__name__)

class RedisCache:
    """Redis 캐싱 클라이언트"""
    
    def __init__(self):
        self.client = None
        self._connect()
    
    def _connect(self):
        """Redis 연결 (URL 형식)"""
        try:
            redis_url = settings.REDIS_URL
            # URL 형식 검증
            if not redis_url or not redis_url.startswith(("redis://", "rediss://", "unix://")):
                logger.error(f"[Redis] 잘못된 URL 형식: {redis_url}")
                logger.info(f"[Redis] 기본값 사용: redis://redis:6379/1")
                redis_url = "redis://redis:6379/1"
            
            self.client = redis.from_url(
                redis_url,
                decode_responses=False,  # 바이너리 모드 (JSON 저장용)
                socket_connect_timeout=5,
                socket_timeout=5
            )
            logger.info(f"[Redis] 연결 성공: {redis_url}")
        except Exception as e:
            logger.error(f"[Redis] 연결 실패: {e}")
            logger.error(f"[Redis] 사용된 URL: {settings.REDIS_URL}")
            self.client = None
    
    async def get(self, key: str) -> Optional[Any]:
        """캐시에서 값 조회"""
        if not self.client:
            return None
        try:
            value = await self.client.get(key)
            if value:
                return json.loads(value.decode('utf-8'))
            return None
        except Exception as e:
            logger.error(f"[Redis] 조회 실패 (key: {key}): {e}")
            return None
    
    async def set(self, key: str, value: Any, ttl: int = 3600):
        """캐시에 값 저장"""
        if not self.client:
            return False
        try:
            serialized = json.dumps(value, ensure_ascii=False)
            await self.client.setex(key, ttl, serialized)
            return True
        except Exception as e:
            logger.error(f"[Redis] 저장 실패 (key: {key}): {e}")
            return False
    
    async def delete(self, key: str):
        """캐시 삭제"""
        if not self.client:
            return False
        try:
            await self.client.delete(key)
            return True
        except Exception as e:
            logger.error(f"[Redis] 삭제 실패 (key: {key}): {e}")
            return False
    
    async def exists(self, key: str) -> bool:
        """캐시 존재 여부 확인"""
        if not self.client:
            return False
        try:
            return await self.client.exists(key) > 0
        except Exception as e:
            logger.error(f"[Redis] 존재 확인 실패 (key: {key}): {e}")
            return False

# 전역 인스턴스
redis_cache = RedisCache()