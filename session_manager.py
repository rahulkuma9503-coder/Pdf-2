"""
Session Management with MongoDB
"""

from datetime import datetime, timedelta
import logging
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)


class SessionManager:
    """Manage user sessions with MongoDB"""
    
    def __init__(self, mongo_uri: str):
        """
        Initialize MongoDB connection
        
        Args:
            mongo_uri: MongoDB connection string
        """
        try:
            from pymongo import MongoClient
            from pymongo.errors import ConnectionError, ConfigurationError
            
            self.client = MongoClient(mongo_uri, serverSelectionTimeoutMS=5000)
            self.db = self.client.pdf_bot_db
            self.sessions = self.db.user_sessions
            
            # Test connection
            self.client.server_info()
            logger.info("MongoDB connection established")
            
            # Create TTL index for auto-expiry (1 hour)
            self.sessions.create_index(
                "expires_at",
                expireAfterSeconds=3600  # 1 hour
            )
            
            # Create index on chat_id for faster lookups
            self.sessions.create_index("chat_id", unique=True)
            
        except Exception as e:
            logger.error(f"MongoDB connection failed: {e}")
            self.client = None
            self.db = None
            self.sessions = None
    
    def create_session(self, chat_id: int, state: str = "waiting", data: Optional[Dict] = None):
        """
        Create a new user session
        
        Args:
            chat_id: Telegram chat ID
            state: Current bot state
            data: Optional session data
        """
        if not self.sessions:
            return
        
        session_data = {
            "chat_id": chat_id,
            "state": state,
            "data": data or {},
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow(),
            "expires_at": datetime.utcnow() + timedelta(hours=1)
        }
        
        try:
            # Upsert: update if exists, insert if not
            self.sessions.update_one(
                {"chat_id": chat_id},
                {"$set": session_data},
                upsert=True
            )
            logger.debug(f"Session created/updated for chat_id: {chat_id}")
        except Exception as e:
            logger.error(f"Failed to create session: {e}")
    
    def get_session(self, chat_id: int) -> Optional[Dict[str, Any]]:
        """
        Retrieve user session
        
        Args:
            chat_id: Telegram chat ID
            
        Returns:
            Session dict or None
        """
        if not self.sessions:
            return None
        
        try:
            session = self.sessions.find_one({"chat_id": chat_id})
            
            if session:
                # Remove MongoDB _id field
                session.pop('_id', None)
                return session
            
            return None
            
        except Exception as e:
            logger.error(f"Failed to get session: {e}")
            return None
    
    def update_session(self, chat_id: int, state: Optional[str] = None, data: Optional[Dict] = None):
        """
        Update existing session
        
        Args:
            chat_id: Telegram chat ID
            state: New state (optional)
            data: New data (optional)
        """
        if not self.sessions:
            return
        
        try:
            update_fields = {
                "updated_at": datetime.utcnow(),
                "expires_at": datetime.utcnow() + timedelta(hours=1)
            }
            
            if state is not None:
                update_fields["state"] = state
            
            if data is not None:
                # Merge with existing data
                existing = self.get_session(chat_id)
                if existing and 'data' in existing:
                    merged_data = {**existing.get('data', {}), **data}
                else:
                    merged_data = data
                
                update_fields["data"] = merged_data
            
            self.sessions.update_one(
                {"chat_id": chat_id},
                {"$set": update_fields}
            )
            
            logger.debug(f"Session updated for chat_id: {chat_id}")
            
        except Exception as e:
            logger.error(f"Failed to update session: {e}")
    
    def clear_session(self, chat_id: int):
        """
        Clear user session
        
        Args:
            chat_id: Telegram chat ID
        """
        if not self.sessions:
            return
        
        try:
            self.sessions.delete_one({"chat_id": chat_id})
            logger.debug(f"Session cleared for chat_id: {chat_id}")
        except Exception as e:
            logger.error(f"Failed to clear session: {e}")
    
    def update_session_data(self, chat_id: int, key: str, value: Any):
        """
        Update specific field in session data
        
        Args:
            chat_id: Telegram chat ID
            key: Data key
            value: Data value
        """
        if not self.sessions:
            return
        
        try:
            self.sessions.update_one(
                {"chat_id": chat_id},
                {
                    "$set": {
                        f"data.{key}": value,
                        "updated_at": datetime.utcnow(),
                        "expires_at": datetime.utcnow() + timedelta(hours=1)
                    }
                }
            )
        except Exception as e:
            logger.error(f"Failed to update session data: {e}")
    
    def get_session_data(self, chat_id: int, key: str, default: Any = None) -> Any:
        """
        Get specific field from session data
        
        Args:
            chat_id: Telegram chat ID
            key: Data key
            default: Default value if key not found
            
        Returns:
            Value or default
        """
        session = self.get_session(chat_id)
        if session and 'data' in session:
            return session['data'].get(key, default)
        return default
    
    def cleanup_expired_sessions(self):
        """Manually clean up expired sessions (TTL index should handle this)"""
        if not self.sessions:
            return
        
        try:
            result = self.sessions.delete_many({
                "expires_at": {"$lt": datetime.utcnow()}
            })
            logger.info(f"Cleaned up {result.deleted_count} expired sessions")
        except Exception as e:
            logger.error(f"Failed to cleanup sessions: {e}")
    
    def get_all_sessions(self) -> list:
        """
        Get all active sessions (for admin purposes)
        
        Returns:
            List of sessions
        """
        if not self.sessions:
            return []
        
        try:
            sessions = list(self.sessions.find(
                {"expires_at": {"$gt": datetime.utcnow()}},
                {"_id": 0}
            ).limit(100))
            return sessions
        except Exception as e:
            logger.error(f"Failed to get all sessions: {e}")
            return []
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Get session statistics
        
        Returns:
            Dictionary with stats
        """
        if not self.sessions:
            return {"total": 0, "active": 0}
        
        try:
            total = self.sessions.count_documents({})
            active = self.sessions.count_documents({
                "expires_at": {"$gt": datetime.utcnow()}
            })
            
            return {
                "total": total,
                "active": active,
                "expired": total - active
            }
        except Exception as e:
            logger.error(f"Failed to get stats: {e}")
            return {"total": 0, "active": 0, "error": str(e)}


class MemorySessionManager:
    """
    Fallback session manager using memory
    Used when MongoDB is not available
    """
    
    def __init__(self):
        self.sessions = {}
        self.logger = logging.getLogger(__name__)
    
    def create_session(self, chat_id: int, state: str = "waiting", data: Optional[Dict] = None):
        self.sessions[chat_id] = {
            "chat_id": chat_id,
            "state": state,
            "data": data or {},
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow()
        }
    
    def get_session(self, chat_id: int) -> Optional[Dict]:
        return self.sessions.get(chat_id)
    
    def update_session(self, chat_id: int, state: Optional[str] = None, data: Optional[Dict] = None):
        if chat_id in self.sessions:
            if state is not None:
                self.sessions[chat_id]["state"] = state
            if data is not None:
                # Merge data
                current_data = self.sessions[chat_id].get("data", {})
                self.sessions[chat_id]["data"] = {**current_data, **data}
            self.sessions[chat_id]["updated_at"] = datetime.utcnow()
    
    def clear_session(self, chat_id: int):
        self.sessions.pop(chat_id, None)
    
    def cleanup_expired_sessions(self, max_age_hours: int = 1):
        """Clean up sessions older than max_age_hours"""
        cutoff = datetime.utcnow() - timedelta(hours=max_age_hours)
        to_delete = []
        
        for chat_id, session in self.sessions.items():
            if session["updated_at"] < cutoff:
                to_delete.append(chat_id)
        
        for chat_id in to_delete:
            del self.sessions[chat_id]
        
        if to_delete:
            self.logger.info(f"Cleaned up {len(to_delete)} expired memory sessions")
