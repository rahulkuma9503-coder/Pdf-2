"""
Session Management
"""

from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class SessionManager:
    """Simple session manager using memory"""
    
    def __init__(self, mongo_uri=''):
        """
        Initialize session manager
        """
        self.sessions = {}
        logger.info("Using memory-based session manager")
    
    def get_session(self, chat_id):
        """
        Get session data
        """
        return self.sessions.get(str(chat_id), {})
    
    def update_session(self, chat_id, **kwargs):
        """
        Update session data
        """
        chat_id_str = str(chat_id)
        
        if chat_id_str not in self.sessions:
            self.sessions[chat_id_str] = {}
        
        # Update with new data
        for key, value in kwargs.items():
            if value is not None:
                self.sessions[chat_id_str][key] = value
        
        logger.debug(f"Session updated for {chat_id}")
    
    def clear_session(self, chat_id):
        """
        Clear session
        """
        chat_id_str = str(chat_id)
        if chat_id_str in self.sessions:
            del self.sessions[chat_id_str]
            logger.debug(f"Session cleared for {chat_id}")
