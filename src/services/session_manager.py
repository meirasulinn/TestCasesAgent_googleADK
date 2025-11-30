"""
Redis-based session manager for multi-user orchestration.
Each user gets a unique session with isolated data.
"""
import json
import logging
from typing import Dict, Any, Optional
import redis.asyncio as aioredis
from src.config.settings import settings

logger = logging.getLogger(__name__)


class SessionManager:
    def create_session_aa(self, session_id: str, user_id: str, title: str = None):
        """
        יצירת סשן חדש במונגו בלבד.
        """
        print(f"####################################SessionManager.create_session: session_id={session_id}, user_id={user_id}, title={title}")
        from src.services.mongo_session_manager import MongoSessionManager
        mongo_mgr = MongoSessionManager()
        mongo_mgr.create_session(session_id, user_id, title)
        print(f"#################################### ", mongo_mgr)


    async def create_redis_session(self, user_id: str) -> Dict[str, Any]:
        """
        יצירת סשן חדש ברדיס בלבד.
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
            json.dumps(session_data),
            ex=settings.SESSION_TTL
        )
        logger.info(f"Created session for user {user_id}")
        return session_data

    def get_sessions_for_user(self, user_id: str) -> list:
        """
        שליפת כל הסשנים למשתמש מתוך session_history בלבד.
        """
        print(f"SessionManager.get_sessions_for_user: user_id={user_id}")
        from src.services.mongo_session_history import MongoSessionHistory
        mongo_history = MongoSessionHistory()
        return mongo_history.get_sessions_for_user(user_id)

    def create_session_for_user(self, user_id: str, title: str = None) -> str:
        """
        יוצר מזהה סשן חדש (UUID4) ושומר אותו במונגו.
        """
        
        
        import uuid
        session_id = str(uuid.uuid4())
        print(f"@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@SessionManager.create_session_for_user: user_id={user_id}, title={title}, session_id={session_id}")
        self.create_session_aa(session_id, user_id, title)
        return session_id
    """
    Manages user sessions in Redis.
    
    Features:
    - Unique session ID per user
    - Session data storage (files, state, history)
    - Global cache for shared data
    - TTL-based session expiration
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
            json.dumps(session_data),
            ex=settings.SESSION_TTL
        )
        
        logger.info(f"Created session for user {user_id}")
        return session_data
    
    async def get_session(self, user_id: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve session data for a user.
        
        Args:
            user_id: Unique user identifier
        
        Returns:
            Session data or None if not found
        """
        await self.connect()
        
        key = self._session_key(user_id)
        data = await self.redis_client.get(key)
        
        if data:
            # Refresh TTL on access
            await self.redis_client.expire(key, settings.SESSION_TTL)
            return json.loads(data)
        
        return None
    
    async def update_session(self, user_id: str, updates: Dict[str, Any]):
        """
        Update session data for a user.
        
        Args:
            user_id: Unique user identifier
            updates: Dictionary of fields to update
        """
        await self.connect()
        
        session = await self.get_session(user_id)
        if not session:
            session = await self.create_session(user_id)
        
        session.update(updates)
        
        key = self._session_key(user_id)
        await self.redis_client.set(
            key,
            json.dumps(session),
            ex=settings.SESSION_TTL
        )
        
        logger.info(f"Updated session for user {user_id}")
    
    async def add_file_to_session(self, user_id: str, file_info: Dict[str, Any]):
        """
        Add uploaded file info to user session.
        
        Args:
            user_id: Unique user identifier
            file_info: File metadata (name, path, type, content)
        """
        session = await self.get_session(user_id)
        if not session:
            session = await self.create_session(user_id)
        
        session["files"].append(file_info)
        await self.update_session(user_id, session)
        logger.info(f"Added file {file_info.get('name')} to session for user {user_id}")
    
    async def get_cache(self, key: str) -> Optional[Any]:
        """
        Retrieve data from global cache.
        
        Args:
            key: Cache key
        
        Returns:
            Cached value or None
        """
        await self.connect()
        
        cache_key = self._cache_key(key)
        data = await self.redis_client.get(cache_key)
        
        if data:
            return json.loads(data)
        return None
    
    async def set_cache(self, key: str, value: Any, ttl: Optional[int] = None):
        """
        Store data in global cache.
        
        Args:
            key: Cache key
            value: Value to cache
            ttl: Time to live in seconds (optional)
        """
        await self.connect()
        
        cache_key = self._cache_key(key)
        await self.redis_client.set(
            cache_key,
            json.dumps(value),
            ex=ttl
        )
        logger.info(f"Cached data with key {key}")
    
    async def delete_session(self, user_id: str):
        """Delete a user session."""
        await self.connect()
        
        key = self._session_key(user_id)
        await self.redis_client.delete(key)
        logger.info(f"Deleted session for user {user_id}")


# Global session manager instance
session_manager = SessionManager()
