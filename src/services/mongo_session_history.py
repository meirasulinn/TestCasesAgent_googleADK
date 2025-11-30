import os
from pymongo import MongoClient
from typing import List, Dict, Any

class MongoSessionHistory:
    def __init__(self):
        self.uri = os.getenv("MONGODB_URI", "mongodb://localhost:27017")
        self.db_name = os.getenv("MONGODB_DB", "adk_agent_db")
        self.collection_name = os.getenv("MONGODB_COLLECTION", "session_history")
        self.client = MongoClient(self.uri)
        self.db = self.client[self.db_name]
        self.collection = self.db[self.collection_name]

    def get_sessions_for_user(self, user_id: str) -> list:
        """
        מחזיר רשימת session_id ייחודיים לכל המשתמש.
        """
        pipeline = [
            {"$match": {"user_id": user_id}},
            {"$group": {"_id": "$session_id", "created": {"$min": "$message.timestamp"}}},
            {"$sort": {"created": -1}}
        ]
        return [doc["_id"] for doc in self.collection.aggregate(pipeline)]

    def get_history_by_session(self, session_id: str) -> list:
        """
        מחזיר את כל ההודעות עבור session_id מסוים.
        """
        cursor = self.collection.find({"session_id": session_id}).sort("message.timestamp", 1)
        history = []
        for doc in cursor:
            doc = dict(doc)
            if "_id" in doc:
                doc["_id"] = str(doc["_id"])
            history.append(doc)
        return history

    def save_message(self, session_id: str, user_id: str, agent_type: str, message: Dict[str, Any]):
        self.collection.insert_one({
            "session_id": session_id,
            "user_id": user_id,
            "agent_type": agent_type,
            "message": message
        })

    def get_history(self, session_id: str, user_id: str, agent_type: str) -> List[Dict[str, Any]]:
        cursor = self.collection.find({
            "session_id": session_id,
            "user_id": user_id,
            "agent_type": agent_type
        })
        return list(cursor)

    def clear_history(self, session_id: str, user_id: str, agent_type: str):
        self.collection.delete_many({
            "session_id": session_id,
            "user_id": user_id,
            "agent_type": agent_type
        })
