"""
Session management for MowthosOS.

This module handles user session management including creation, validation,
and cleanup of user sessions.
"""

import logging
from typing import Dict, Optional, Any, List
from datetime import datetime, timedelta

from src.core.config import settings

logger = logging.getLogger(__name__)

class SessionManager:
    """Manages user sessions for the application."""
    
    def __init__(self):
        self.sessions: Dict[str, Dict[str, Any]] = {}
    
    def create_session(self, account: str, device_name: Optional[str] = None) -> str:
        """
        Create a new session for a user.
        
        Args:
            account: User account identifier
            device_name: Optional device name for the session
            
        Returns:
            Session ID for the created session
        """
        session_id = f"{account}_{datetime.now().timestamp()}"
        
        self.sessions[session_id] = {
            "account": account,
            "device_name": device_name,
            "created_at": datetime.now(),
            "last_accessed": datetime.now(),
            "active": True
        }
        
        logger.info(f"Created session {session_id} for account {account}")
        return session_id
    
    def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """
        Get session by ID.
        
        Args:
            session_id: Session identifier
            
        Returns:
            Session data if valid, None otherwise
        """
        session = self.sessions.get(session_id)
        
        if session and self._is_session_valid(session):
            # Update last accessed time
            session["last_accessed"] = datetime.now()
            return session
        
        # Remove invalid session
        if session_id in self.sessions:
            self.remove_session(session_id)
        
        return None
    
    def remove_session(self, session_id: str) -> bool:
        """
        Remove a session.
        
        Args:
            session_id: Session identifier
            
        Returns:
            True if session was removed, False if not found
        """
        if session_id in self.sessions:
            del self.sessions[session_id]
            logger.info(f"Removed session {session_id}")
            return True
        return False
    
    def cleanup_expired_sessions(self) -> int:
        """
        Clean up expired sessions.
        
        Returns:
            Number of sessions removed
        """
        expired_sessions = []
        current_time = datetime.now()
        
        for session_id, session in self.sessions.items():
            if not self._is_session_valid(session):
                expired_sessions.append(session_id)
        
        for session_id in expired_sessions:
            self.remove_session(session_id)
        
        if expired_sessions:
            logger.info(f"Cleaned up {len(expired_sessions)} expired sessions")
        
        return len(expired_sessions)
    
    def get_active_sessions_for_account(self, account: str) -> List[str]:
        """
        Get all active session IDs for an account.
        
        Args:
            account: User account identifier
            
        Returns:
            List of active session IDs
        """
        active_sessions = []
        
        for session_id, session in self.sessions.items():
            if (session["account"] == account and 
                session["active"] and 
                self._is_session_valid(session)):
                active_sessions.append(session_id)
        
        return active_sessions
    
    def _is_session_valid(self, session: Dict[str, Any]) -> bool:
        """
        Check if a session is still valid.
        
        Args:
            session: Session data dictionary
            
        Returns:
            True if session is valid, False otherwise
        """
        if not session.get("active", False):
            return False
        
        # Check session timeout
        last_accessed = session.get("last_accessed")
        if not last_accessed:
            return False
        
        timeout_delta = timedelta(minutes=settings.session_timeout_minutes)
        if datetime.now() - last_accessed > timeout_delta:
            return False
        
        return True
    
    def get_session_count(self) -> int:
        """
        Get total number of active sessions.
        
        Returns:
            Number of active sessions
        """
        return len([s for s in self.sessions.values() if self._is_session_valid(s)]) 