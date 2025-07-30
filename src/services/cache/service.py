"""Cache service for efficient data caching across the system."""

from typing import Any, Dict, Optional, List, Set
from datetime import datetime, timedelta
import json
import asyncio
import logging
from enum import Enum

try:
    import redis.asyncio as redis
except ImportError:
    import aioredis as redis

from ..base import BaseService
from ...core.config import settings

logger = logging.getLogger(__name__)

class CacheNamespace(Enum):
    """Cache namespaces for different data types."""
    MOWER_STATUS = "mower:status"
    MOWER_DIAGNOSTICS = "mower:diagnostics"
    CLUSTER_DATA = "cluster:data"
    CLUSTER_STATS = "cluster:stats"
    USER_SESSION = "user:session"
    ADDRESS_VALIDATION = "address:validation"
    ROUTE_OPTIMIZATION = "route:optimization"
    NOTIFICATION_QUEUE = "notification:queue"
    SCHEDULE_DATA = "schedule:data"

class CacheService(BaseService):
    """Service for managing application-wide caching."""
    
    def __init__(self):
        """Initialize the cache service."""
        super().__init__("cache")
        self.redis_client: Optional[redis.Redis] = None
        self.local_cache: Dict[str, Dict[str, Any]] = {}
        self.cache_stats = {
            "hits": 0,
            "misses": 0,
            "sets": 0,
            "deletes": 0
        }
        
        # Default TTLs for different cache types (in seconds)
        self.default_ttls = {
            CacheNamespace.MOWER_STATUS: 30,
            CacheNamespace.MOWER_DIAGNOSTICS: 300,
            CacheNamespace.CLUSTER_DATA: 3600,
            CacheNamespace.CLUSTER_STATS: 600,
            CacheNamespace.USER_SESSION: 86400,
            CacheNamespace.ADDRESS_VALIDATION: 86400 * 7,
            CacheNamespace.ROUTE_OPTIMIZATION: 1800,
            CacheNamespace.NOTIFICATION_QUEUE: 3600,
            CacheNamespace.SCHEDULE_DATA: 3600
        }
        
    async def initialize(self) -> None:
        """Initialize the cache service and connect to Redis."""
        await super().initialize()
        
        try:
            # Connect to Redis
            self.redis_client = await redis.from_url(
                settings.redis_url,
                encoding="utf-8",
                decode_responses=True
            )
            
            # Test connection
            await self.redis_client.ping()
            self.logger.info("Successfully connected to Redis")
            
        except Exception as e:
            self.logger.warning(f"Failed to connect to Redis: {str(e)}. Using local cache only.")
            self.redis_client = None
            
    async def cleanup(self) -> None:
        """Cleanup resources."""
        await super().cleanup()
        
        if self.redis_client:
            await self.redis_client.close()
            self.redis_client = None
            
        self.local_cache.clear()
        
    async def get(
        self,
        key: str,
        namespace: CacheNamespace = None,
        default: Any = None
    ) -> Any:
        """Get value from cache.
        
        Args:
            key: Cache key
            namespace: Cache namespace
            default: Default value if not found
            
        Returns:
            Cached value or default
        """
        full_key = self._make_key(key, namespace)
        
        try:
            # Try Redis first
            if self.redis_client:
                value = await self.redis_client.get(full_key)
                if value is not None:
                    self.cache_stats["hits"] += 1
                    # Try to decode JSON
                    try:
                        return json.loads(value)
                    except json.JSONDecodeError:
                        return value
            
            # Fall back to local cache
            if full_key in self.local_cache:
                entry = self.local_cache[full_key]
                if entry["expires_at"] is None or entry["expires_at"] > datetime.now():
                    self.cache_stats["hits"] += 1
                    return entry["value"]
                else:
                    # Expired
                    del self.local_cache[full_key]
                    
        except Exception as e:
            self.logger.error(f"Cache get error for key {full_key}: {str(e)}")
            
        self.cache_stats["misses"] += 1
        return default
        
    async def set(
        self,
        key: str,
        value: Any,
        namespace: CacheNamespace = None,
        ttl: Optional[int] = None
    ) -> bool:
        """Set value in cache.
        
        Args:
            key: Cache key
            value: Value to cache
            namespace: Cache namespace
            ttl: Time to live in seconds (None for default)
            
        Returns:
            True if successful
        """
        full_key = self._make_key(key, namespace)
        
        # Determine TTL
        if ttl is None and namespace:
            ttl = self.default_ttls.get(namespace, 3600)
            
        try:
            # Serialize value
            serialized = json.dumps(value) if not isinstance(value, str) else value
            
            # Try Redis first
            if self.redis_client:
                if ttl:
                    await self.redis_client.setex(full_key, ttl, serialized)
                else:
                    await self.redis_client.set(full_key, serialized)
                self.cache_stats["sets"] += 1
                return True
                
            # Fall back to local cache
            expires_at = datetime.now() + timedelta(seconds=ttl) if ttl else None
            self.local_cache[full_key] = {
                "value": value,
                "expires_at": expires_at
            }
            self.cache_stats["sets"] += 1
            
            # Clean up expired entries periodically
            if len(self.local_cache) > 1000:
                await self._cleanup_local_cache()
                
            return True
            
        except Exception as e:
            self.logger.error(f"Cache set error for key {full_key}: {str(e)}")
            return False
            
    async def delete(
        self,
        key: str,
        namespace: CacheNamespace = None
    ) -> bool:
        """Delete value from cache.
        
        Args:
            key: Cache key
            namespace: Cache namespace
            
        Returns:
            True if deleted
        """
        full_key = self._make_key(key, namespace)
        
        try:
            deleted = False
            
            # Try Redis first
            if self.redis_client:
                result = await self.redis_client.delete(full_key)
                deleted = result > 0
                
            # Also delete from local cache
            if full_key in self.local_cache:
                del self.local_cache[full_key]
                deleted = True
                
            if deleted:
                self.cache_stats["deletes"] += 1
                
            return deleted
            
        except Exception as e:
            self.logger.error(f"Cache delete error for key {full_key}: {str(e)}")
            return False
            
    async def delete_pattern(
        self,
        pattern: str,
        namespace: CacheNamespace = None
    ) -> int:
        """Delete all keys matching pattern.
        
        Args:
            pattern: Key pattern (supports * wildcard)
            namespace: Cache namespace
            
        Returns:
            Number of keys deleted
        """
        full_pattern = self._make_key(pattern, namespace)
        deleted_count = 0
        
        try:
            # Redis deletion
            if self.redis_client:
                cursor = 0
                while True:
                    cursor, keys = await self.redis_client.scan(
                        cursor, match=full_pattern
                    )
                    if keys:
                        deleted_count += await self.redis_client.delete(*keys)
                    if cursor == 0:
                        break
                        
            # Local cache deletion
            keys_to_delete = [
                k for k in self.local_cache.keys()
                if self._match_pattern(k, full_pattern)
            ]
            for key in keys_to_delete:
                del self.local_cache[key]
                deleted_count += 1
                
            self.cache_stats["deletes"] += deleted_count
            return deleted_count
            
        except Exception as e:
            self.logger.error(f"Cache delete pattern error for {full_pattern}: {str(e)}")
            return 0
            
    async def exists(
        self,
        key: str,
        namespace: CacheNamespace = None
    ) -> bool:
        """Check if key exists in cache.
        
        Args:
            key: Cache key
            namespace: Cache namespace
            
        Returns:
            True if exists
        """
        full_key = self._make_key(key, namespace)
        
        try:
            # Check Redis first
            if self.redis_client:
                return await self.redis_client.exists(full_key) > 0
                
            # Check local cache
            if full_key in self.local_cache:
                entry = self.local_cache[full_key]
                if entry["expires_at"] is None or entry["expires_at"] > datetime.now():
                    return True
                else:
                    del self.local_cache[full_key]
                    
            return False
            
        except Exception as e:
            self.logger.error(f"Cache exists error for key {full_key}: {str(e)}")
            return False
            
    async def get_ttl(
        self,
        key: str,
        namespace: CacheNamespace = None
    ) -> Optional[int]:
        """Get remaining TTL for a key.
        
        Args:
            key: Cache key
            namespace: Cache namespace
            
        Returns:
            TTL in seconds or None if not found
        """
        full_key = self._make_key(key, namespace)
        
        try:
            # Check Redis first
            if self.redis_client:
                ttl = await self.redis_client.ttl(full_key)
                return ttl if ttl > 0 else None
                
            # Check local cache
            if full_key in self.local_cache:
                entry = self.local_cache[full_key]
                if entry["expires_at"]:
                    remaining = (entry["expires_at"] - datetime.now()).total_seconds()
                    return int(remaining) if remaining > 0 else None
                return None
                
        except Exception as e:
            self.logger.error(f"Cache get TTL error for key {full_key}: {str(e)}")
            
        return None
        
    async def increment(
        self,
        key: str,
        namespace: CacheNamespace = None,
        amount: int = 1
    ) -> Optional[int]:
        """Increment a counter in cache.
        
        Args:
            key: Cache key
            namespace: Cache namespace
            amount: Amount to increment by
            
        Returns:
            New value or None if error
        """
        full_key = self._make_key(key, namespace)
        
        try:
            if self.redis_client:
                return await self.redis_client.incrby(full_key, amount)
            else:
                # Local cache increment
                current = await self.get(key, namespace, 0)
                new_value = int(current) + amount
                await self.set(key, new_value, namespace)
                return new_value
                
        except Exception as e:
            self.logger.error(f"Cache increment error for key {full_key}: {str(e)}")
            return None
            
    async def add_to_set(
        self,
        key: str,
        values: List[str],
        namespace: CacheNamespace = None,
        ttl: Optional[int] = None
    ) -> int:
        """Add values to a set in cache.
        
        Args:
            key: Cache key
            values: Values to add
            namespace: Cache namespace
            ttl: Time to live in seconds
            
        Returns:
            Number of values added
        """
        full_key = self._make_key(key, namespace)
        
        try:
            if self.redis_client:
                added = await self.redis_client.sadd(full_key, *values)
                if ttl:
                    await self.redis_client.expire(full_key, ttl)
                return added
            else:
                # Local cache set simulation
                current_set = await self.get(key, namespace, set())
                if not isinstance(current_set, set):
                    current_set = set()
                before_size = len(current_set)
                current_set.update(values)
                await self.set(key, list(current_set), namespace, ttl)
                return len(current_set) - before_size
                
        except Exception as e:
            self.logger.error(f"Cache add to set error for key {full_key}: {str(e)}")
            return 0
            
    async def get_set_members(
        self,
        key: str,
        namespace: CacheNamespace = None
    ) -> Set[str]:
        """Get all members of a set.
        
        Args:
            key: Cache key
            namespace: Cache namespace
            
        Returns:
            Set of members
        """
        full_key = self._make_key(key, namespace)
        
        try:
            if self.redis_client:
                members = await self.redis_client.smembers(full_key)
                return set(members)
            else:
                # Local cache
                current = await self.get(key, namespace, [])
                return set(current) if isinstance(current, list) else set()
                
        except Exception as e:
            self.logger.error(f"Cache get set members error for key {full_key}: {str(e)}")
            return set()
            
    async def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics.
        
        Returns:
            Dictionary of cache statistics
        """
        stats = self.cache_stats.copy()
        
        # Calculate hit rate
        total_requests = stats["hits"] + stats["misses"]
        stats["hit_rate"] = (
            stats["hits"] / total_requests if total_requests > 0 else 0
        )
        
        # Add cache sizes
        stats["local_cache_size"] = len(self.local_cache)
        
        if self.redis_client:
            try:
                info = await self.redis_client.info()
                stats["redis_used_memory"] = info.get("used_memory_human", "N/A")
                stats["redis_connected_clients"] = info.get("connected_clients", 0)
                stats["redis_uptime_days"] = info.get("uptime_in_days", 0)
            except:
                stats["redis_status"] = "disconnected"
        else:
            stats["redis_status"] = "not configured"
            
        return stats
        
    async def clear_namespace(self, namespace: CacheNamespace) -> int:
        """Clear all keys in a namespace.
        
        Args:
            namespace: Cache namespace to clear
            
        Returns:
            Number of keys cleared
        """
        pattern = f"{namespace.value}:*"
        return await self.delete_pattern(pattern)
        
    # Private helper methods
    
    def _make_key(self, key: str, namespace: Optional[CacheNamespace]) -> str:
        """Make full cache key with namespace."""
        if namespace:
            return f"{namespace.value}:{key}"
        return key
        
    def _match_pattern(self, key: str, pattern: str) -> bool:
        """Check if key matches pattern (simple * wildcard support)."""
        import fnmatch
        return fnmatch.fnmatch(key, pattern)
        
    async def _cleanup_local_cache(self) -> None:
        """Clean up expired entries from local cache."""
        now = datetime.now()
        expired_keys = [
            k for k, v in self.local_cache.items()
            if v["expires_at"] and v["expires_at"] <= now
        ]
        for key in expired_keys:
            del self.local_cache[key]
            
        self.logger.debug(f"Cleaned up {len(expired_keys)} expired cache entries")