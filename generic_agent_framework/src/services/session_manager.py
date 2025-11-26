"""
Redis-based session manager for multi-user orchestration.
Each user gets a unique session with isolated data.
"""
import json
import logging
from typing import Dict, Any, Optional
import redis.asyncio as aioredis
from config.settings import settings

logger = logging.getLogger(__name__)


class SessionManager:
    """
    Manages user sessions in Redis.
    
    Features:
    - Unique session ID per user
    - Session data storage (files, state, history)
    - Global cache for shared data
    - TTL-based expiration
    """
    
    def __init__(self):
        self.redis_client: Optional[aioredis.Redis] = None
        logger.info("SessionManager initialized")
    
    async def connect(self):
        """Connect to Redis."""
        if self.redis_client is None:
            try:
                self.redis_client = await aioredis.from_url(
                    f"redis://{settings.REDIS_HOST}:{settings.REDIS_PORT}/{settings.REDIS_DB}",
                    password=settings.REDIS_PASSWORD if settings.REDIS_PASSWORD else None,
                    decode_responses=True
                )
                # Test connection
                await self.redis_client.ping()
                logger.info(f"Connected to Redis at {settings.REDIS_HOST}:{settings.REDIS_PORT}")
            except Exception as e:
                logger.error(f"Failed to connect to Redis: {e}")
                self.redis_client = None
                raise
    
    async def disconnect(self):
        """Disconnect from Redis."""
        if self.redis_client:
            await self.redis_client.close()
            logger.info("Disconnected from Redis")
    
    def _session_key(self, user_id: str) -> str:
        """Generate Redis key for user session."""
        return f"session:{user_id}"
    
    def _cache_key(self, key: str) -> str:
        """Generate Redis key for global cache."""
        return f"cache:{key}"
    
    async def create_session(self, user_id: str) -> Dict[str, Any]:
        """
        Create a new session for a user.
        
        Args:
            user_id: Unique user identifier
        
        Returns:
            Session data dict
        """
        await self.connect()
        
        session_data = {
            "user_id": user_id,
            "files": [],
            "history": [],
            "state": {}
        }
        
        key = self._session_key(user_id)
        await self.redis_client.set(
            key,
            json.dumps(session_data)
        )
        
        logger.info(f"Created session for user {user_id}")
        return session_data
    
    async def get_session(self, user_id: str) -> Optional[Dict[str, Any]]:
        """
        Get session data for a user.
        
        Args:
            user_id: User identifier
        
        Returns:
            Session data or None if not exists
        """
        await self.connect()
        
        key = self._session_key(user_id)
        data = await self.redis_client.get(key)
        
        if data:
            return json.loads(data)
        return None
    
    async def update_session(self, user_id: str, session_data: Dict[str, Any]):
        """
        Update session data for a user.
        
        Args:
            user_id: User identifier
            session_data: Updated session data
        """
        await self.connect()
        
        key = self._session_key(user_id)
        await self.redis_client.set(
            key,
            json.dumps(session_data)
        )
        
        logger.debug(f"Updated session for user {user_id}")
    
    async def get_cache(self, cache_key: str) -> Optional[Any]:
        """
        Get cached data.
        
        Args:
            cache_key: Cache key
        
        Returns:
            Cached data or None
        """
        await self.connect()
        
        key = self._cache_key(cache_key)
        data = await self.redis_client.get(key)
        
        if data:
            return json.loads(data)
        return None
    
    async def set_cache(self, cache_key: str, value: Any, ttl: int = None):
        """
        Set cached data with optional TTL.
        
        Args:
            cache_key: Cache key
            value: Data to cache
            ttl: Time to live in seconds (optional)
        """
        await self.connect()
        
        key = self._cache_key(cache_key)
        
        if ttl:
            await self.redis_client.setex(
                key,
                ttl,
                json.dumps(value)
            )
        else:
            await self.redis_client.set(
                key,
                json.dumps(value)
            )
        
        logger.debug(f"Set cache for key {cache_key} (TTL: {ttl})")


# Global session manager instance
session_manager = SessionManager()
