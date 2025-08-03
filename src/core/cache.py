"""
Cache management for MowthosOS.
"""

from typing import Any, Dict, Optional
from datetime import datetime, timedelta
import asyncio


class CacheManager:
    """Simple in-memory cache manager."""
    
    def __init__(self):
        self._cache: Dict[str, Dict[str, Any]] = {}
    
    def get(self, key: str) -> Optional[Any]:
        """Get value from cache."""
        if key in self._cache:
            item = self._cache[key]
            if datetime.now() < item['expires']:
                return item['value']
            else:
                del self._cache[key]
        return None
    
    def set(self, key: str, value: Any, ttl_seconds: int = 300) -> None:
        """Set value in cache with TTL."""
        self._cache[key] = {
            'value': value,
            'expires': datetime.now() + timedelta(seconds=ttl_seconds)
        }
    
    def delete(self, key: str) -> None:
        """Delete value from cache."""
        if key in self._cache:
            del self._cache[key]
    
    def clear(self) -> None:
        """Clear all cache."""
        self._cache.clear()


# Global cache manager instance
cache_manager = CacheManager() 