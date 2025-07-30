"""Base service class providing common functionality for all services."""

import logging
from typing import Any, Dict, Optional
from datetime import datetime, timedelta
import asyncio

class BaseService:
    """Base class for all services in the MowthosOS system."""
    
    def __init__(self, name: str):
        """Initialize the base service.
        
        Args:
            name: The name of the service for logging purposes
        """
        self.name = name
        self.logger = logging.getLogger(f"mowthosos.{name}")
        self._initialized = False
        self._initialization_time = None
        
    async def initialize(self) -> None:
        """Initialize the service. Override in subclasses for custom initialization."""
        self.logger.info(f"Initializing {self.name} service...")
        self._initialized = True
        self._initialization_time = datetime.now()
        self.logger.info(f"{self.name} service initialized successfully")
        
    async def cleanup(self) -> None:
        """Cleanup resources. Override in subclasses for custom cleanup."""
        self.logger.info(f"Cleaning up {self.name} service...")
        self._initialized = False
        
    @property
    def is_initialized(self) -> bool:
        """Check if the service is initialized."""
        return self._initialized
        
    @property
    def uptime(self) -> Optional[timedelta]:
        """Get the service uptime if initialized."""
        if self._initialization_time:
            return datetime.now() - self._initialization_time
        return None
        
    async def health_check(self) -> Dict[str, Any]:
        """Perform a health check on the service.
        
        Returns:
            Dictionary containing health status information
        """
        return {
            "service": self.name,
            "status": "healthy" if self._initialized else "unhealthy",
            "initialized": self._initialized,
            "uptime": str(self.uptime) if self.uptime else None,
            "timestamp": datetime.now().isoformat()
        }
        
    async def exponential_backoff(
        self,
        func,
        max_retries: int = 3,
        initial_delay: float = 1.0,
        max_delay: float = 10.0,
        jitter: bool = True
    ) -> Optional[Any]:
        """Execute function with exponential backoff retry logic.
        
        Args:
            func: The async function to execute
            max_retries: Maximum number of retry attempts
            initial_delay: Initial delay in seconds
            max_delay: Maximum delay in seconds
            jitter: Whether to add random jitter to delays
            
        Returns:
            The result of the function or None if all retries failed
        """
        import random
        
        delay = initial_delay
        for attempt in range(max_retries):
            try:
                return await func()
            except Exception as e:
                if attempt == max_retries - 1:
                    self.logger.error(f"Failed after {max_retries} attempts: {str(e)}")
                    raise
                    
                sleep_time = min(delay * (2 ** attempt), max_delay)
                if jitter:
                    sleep_time = random.uniform(0.5 * sleep_time, sleep_time)
                    
                self.logger.warning(
                    f"Attempt {attempt + 1}/{max_retries} failed, retrying in {sleep_time:.1f}s: {str(e)}"
                )
                await asyncio.sleep(sleep_time)