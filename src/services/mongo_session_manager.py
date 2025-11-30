import os
from pymongo import MongoClient
from typing import Dict, Any
from datetime import datetime

class MongoSessionManager:
    def __init__(self):
        self.uri = os.getenv("MONGODB_URI", "mongodb://localhost:27017")
        self.db_name = os.getenv("MONGODB_DB", "adk_agent_db")
        # מאפשר הגדרה דינמית של שם הקולקשן דרך ENV
        self.sessions_collection = os.getenv("MONGODB_SESSIONS_COLLECTION", "sessions")
        self.client = MongoClient(self.uri)
        self.db = self.client[self.db_name]
        self.sessions = self.db[self.sessions_collection]

    def create_session(self, session_id: str, user_id: str, title: str = None):
        now = datetime.utcnow().isoformat()
        session_doc = {
            "session_id": session_id,
            "user_id": user_id,
            "title": title or "שיחה חדשה",
            "created": now
        }
        self.sessions.insert_one(session_doc)

    def get_sessions_for_user(self, user_id: str) -> list:
        import logging
        logger = logging.getLogger(__name__)
        logger.info(f"MongoSessionManager: Searching for sessions with user_id='{user_id}'")
        cursor = self.sessions.find({"user_id": user_id}).sort("created", -1)
        sessions = []
        for doc in cursor:
            doc = dict(doc)
            if "_id" in doc:
                doc["_id"] = str(doc["_id"])
            sessions.append(doc)
        logger.info(f"MongoSessionManager: Found {len(sessions)} sessions for user_id='{user_id}'")
        return sessions

    def update_session_title(self, session_id: str, user_id: str, title: str):
        self.sessions.update_one({"session_id": session_id, "user_id": user_id}, {"$set": {"title": title}})

    def delete_session(self, session_id: str, user_id: str):
        self.sessions.delete_one({"session_id": session_id, "user_id": user_id})
