"""Mapbox service for geographic operations and road detection."""

from typing import List, Dict, Optional, Tuple, Any
import aiohttp
import asyncio
import json
import logging
from urllib.parse import quote

from ...core.config import settings

logger = logging.getLogger(__name__)

class MapboxService:
    """Service for Mapbox API interactions."""
    
    def __init__(self, access_token: str):
        """Initialize the Mapbox service.
        
        Args:
            access_token: Mapbox API access token
        """
        self.access_token = access_token
        self.base_url = "https://api.mapbox.com"
        self.session: Optional[aiohttp.ClientSession] = None
        
    async def __aenter__(self):
        """Async context manager entry."""
        self.session = aiohttp.ClientSession()
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        if self.session:
            await self.session.close()
            
    async def _ensure_session(self):
        """Ensure aiohttp session exists."""
        if not self.session:
            self.session = aiohttp.ClientSession()
            
    async def validate_address(
        self,
        street: str,
        city: str,
        state: str,
        zip_code: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """Validate and geocode an address.
        
        Args:
            street: Street address
            city: City name
            state: State code
            zip_code: ZIP code (optional)
            
        Returns:
            Validated address with coordinates or None if invalid
        """
        await self._ensure_session()
        
        # Build search query
        query_parts = [street, city, state]
        if zip_code:
            query_parts.append(zip_code)
        query = ", ".join(query_parts)
        
        # Geocoding API endpoint
        url = f"{self.base_url}/geocoding/v5/mapbox.places/{quote(query)}.json"
        params = {
            "access_token": self.access_token,
            "country": "US",
            "types": "address",
            "limit": 1
        }
        
        try:
            async with self.session.get(url, params=params) as response:
                if response.status != 200:
                    logger.error(f"Mapbox geocoding failed: {response.status}")
                    return None
                    
                data = await response.json()
                
                if data.get("features"):
                    feature = data["features"][0]
                    
                    # Extract coordinates
                    coordinates = feature.get("geometry", {}).get("coordinates", [])
                    if len(coordinates) >= 2:
                        return {
                            "address": feature.get("place_name", ""),
                            "latitude": coordinates[1],
                            "longitude": coordinates[0],
                            "confidence": feature.get("relevance", 0),
                            "place_type": feature.get("place_type", [])
                        }
                        
        except Exception as e:
            logger.error(f"Address validation failed: {str(e)}")
            
        return None
        
    async def check_road_between_points(
        self,
        lat1: float,
        lon1: float,
        lat2: float,
        lon2: float
    ) -> bool:
        """Check if a road exists between two points.
        
        Args:
            lat1, lon1: First point coordinates
            lat2, lon2: Second point coordinates
            
        Returns:
            True if road exists between points, False otherwise
        """
        await self._ensure_session()
        
        # Use Mapbox Directions API to find route
        coordinates = f"{lon1},{lat1};{lon2},{lat2}"
        url = f"{self.base_url}/directions/v5/mapbox/driving/{coordinates}"
        params = {
            "access_token": self.access_token,
            "geometries": "geojson",
            "overview": "full",
            "steps": "true"
        }
        
        try:
            async with self.session.get(url, params=params) as response:
                if response.status != 200:
                    logger.error(f"Mapbox directions failed: {response.status}")
                    return False
                    
                data = await response.json()
                
                if data.get("routes"):
                    route = data["routes"][0]
                    distance = route.get("distance", 0)  # meters
                    
                    # Check if route follows roads vs direct path
                    direct_distance = self._haversine_distance(lat1, lon1, lat2, lon2)
                    
                    # If route distance is significantly longer than direct distance,
                    # it means the route follows roads
                    ratio = distance / direct_distance if direct_distance > 0 else 1
                    
                    # If ratio > 1.2, there's likely a road/obstacle
                    # For very short distances, check if route exists at all
                    if distance < 200:  # Less than 200m
                        # For short distances, check number of steps
                        steps = route.get("legs", [{}])[0].get("steps", [])
                        # More than 2 steps indicates road following
                        return len(steps) > 2
                    else:
                        return ratio > 1.2
                        
        except Exception as e:
            logger.error(f"Road detection failed: {str(e)}")
            
        return False
        
    async def get_isochrone(
        self,
        latitude: float,
        longitude: float,
        minutes: int = 5,
        profile: str = "driving"
    ) -> Optional[Dict[str, Any]]:
        """Get isochrone (reachable area) from a point.
        
        Args:
            latitude: Center point latitude
            longitude: Center point longitude
            minutes: Time in minutes
            profile: Travel profile (driving, walking, cycling)
            
        Returns:
            GeoJSON polygon of reachable area
        """
        await self._ensure_session()
        
        url = f"{self.base_url}/isochrone/v1/mapbox/{profile}/{longitude},{latitude}"
        params = {
            "access_token": self.access_token,
            "contours_minutes": minutes,
            "polygons": "true",
            "denoise": 1,
            "generalize": 500
        }
        
        try:
            async with self.session.get(url, params=params) as response:
                if response.status != 200:
                    logger.error(f"Mapbox isochrone failed: {response.status}")
                    return None
                    
                data = await response.json()
                return data
                
        except Exception as e:
            logger.error(f"Isochrone request failed: {str(e)}")
            
        return None
        
    async def reverse_geocode(
        self,
        latitude: float,
        longitude: float
    ) -> Optional[Dict[str, Any]]:
        """Reverse geocode coordinates to address.
        
        Args:
            latitude: Latitude
            longitude: Longitude
            
        Returns:
            Address information or None
        """
        await self._ensure_session()
        
        url = f"{self.base_url}/geocoding/v5/mapbox.places/{longitude},{latitude}.json"
        params = {
            "access_token": self.access_token,
            "types": "address"
        }
        
        try:
            async with self.session.get(url, params=params) as response:
                if response.status != 200:
                    logger.error(f"Mapbox reverse geocoding failed: {response.status}")
                    return None
                    
                data = await response.json()
                
                if data.get("features"):
                    feature = data["features"][0]
                    
                    # Parse address components
                    context = {item["id"].split(".")[0]: item["text"] 
                              for item in feature.get("context", [])}
                    
                    return {
                        "address": feature.get("place_name", ""),
                        "street": feature.get("text", ""),
                        "city": context.get("place", ""),
                        "state": context.get("region", ""),
                        "zip_code": context.get("postcode", ""),
                        "country": context.get("country", "")
                    }
                    
        except Exception as e:
            logger.error(f"Reverse geocoding failed: {str(e)}")
            
        return None
        
    async def get_static_map_url(
        self,
        center_lat: float,
        center_lon: float,
        zoom: int = 15,
        width: int = 600,
        height: int = 400,
        markers: Optional[List[Tuple[float, float]]] = None
    ) -> str:
        """Generate URL for static map image.
        
        Args:
            center_lat: Map center latitude
            center_lon: Map center longitude
            zoom: Zoom level (0-22)
            width: Image width in pixels
            height: Image height in pixels
            markers: List of (lat, lon) tuples for markers
            
        Returns:
            URL for static map image
        """
        # Base URL
        url = f"{self.base_url}/styles/v1/mapbox/streets-v11/static/"
        
        # Add markers
        if markers:
            for lat, lon in markers:
                url += f"pin-s+ff0000({lon},{lat}),"
            # Remove trailing comma
            url = url.rstrip(",") + "/"
        
        # Add center, zoom, and size
        url += f"{center_lon},{center_lat},{zoom}/{width}x{height}"
        
        # Add access token
        url += f"?access_token={self.access_token}"
        
        return url
        
    async def batch_geocode(
        self,
        addresses: List[Dict[str, str]]
    ) -> List[Optional[Dict[str, Any]]]:
        """Batch geocode multiple addresses.
        
        Args:
            addresses: List of address dicts with street, city, state, zip_code
            
        Returns:
            List of geocoded results (None for failed addresses)
        """
        tasks = []
        for addr in addresses:
            task = self.validate_address(
                addr.get("street", ""),
                addr.get("city", ""),
                addr.get("state", ""),
                addr.get("zip_code")
            )
            tasks.append(task)
            
        return await asyncio.gather(*tasks)
        
    # Private helper methods
    
    def _haversine_distance(self, lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        """Calculate haversine distance between two points in meters."""
        import math
        
        R = 6371000  # Earth radius in meters
        
        lat1_rad = math.radians(lat1)
        lat2_rad = math.radians(lat2)
        dlat = math.radians(lat2 - lat1)
        dlon = math.radians(lon2 - lon1)
        
        a = (math.sin(dlat/2)**2 + 
             math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(dlon/2)**2)
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
        
        return R * c
        
    async def close(self):
        """Close the aiohttp session."""
        if self.session:
            await self.session.close()
            self.session = None