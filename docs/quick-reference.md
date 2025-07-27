# MowthosOS Quick Reference Guide

**Essential functions and usage patterns for developers**

## PyMammotion - Core Functions

### Device Management

```python
from pymammotion.mammotion.devices.mammotion import Mammotion

# Initialize and authenticate
mammotion = Mammotion()
await mammotion.login_and_initiate_cloud("user@email.com", "password")

# Get available devices
devices = mammotion.device_manager.devices
device_name = list(devices.keys())[0]

# Get specific device
device = mammotion.get_device_by_name(device_name)
```

### Mower Control Commands

```python
# Start mowing
await mammotion.send_command(device_name, "start_job")

# Stop mowing
await mammotion.send_command(device_name, "cancel_job")

# Pause operation
await mammotion.send_command(device_name, "pause_execute_task")

# Resume operation
await mammotion.send_command(device_name, "resume_execute_task")

# Return to charging dock
await mammotion.send_command(device_name, "return_to_dock")
```

### Device Status Monitoring

```python
# Get complete device state
device = mammotion.get_device_by_name(device_name)
state = device.mower_state

# Key status properties
battery_level = state.report_data.dev.battery_val
charging_state = state.report_data.dev.charge_state
work_mode = state.report_data.dev.sys_status
online_status = state.online

# Location information
if state.location.device:
    latitude = state.location.device.latitude
    longitude = state.location.device.longitude
    orientation = state.location.orientation

# Work progress
work_progress = state.report_data.work.progress
work_area = state.report_data.work.area
```

### Movement Control

```python
from pymammotion.mammotion.commands.mammotion_command import MammotionCommand

command = MammotionCommand(device_name, user_account_id)

# Movement commands (0.0-1.0 speed)
command.move_forward(0.5)
command.move_back(0.3)
command.move_left(0.4)
command.move_right(0.6)
```

### Connection Types

```python
from pymammotion.data.model.enums import ConnectionPreference

# Set connection preference
device.preference = ConnectionPreference.WIFI       # Cloud/WiFi
device.preference = ConnectionPreference.BLUETOOTH  # Direct BLE
device.preference = ConnectionPreference.EITHER     # Auto-select
```

## Mowthos-Cluster-Logic - Core Functions

### Home Registration

```python
from app.services.cluster_engine import register_host_home, register_neighbor_home

# Register host home with mower
host_result = register_host_home(
    address="123 Main St",
    city="Rochester", 
    state="MN",
    latitude=44.0123,  # optional - will geocode if not provided
    longitude=-92.1234  # optional
)

# Register neighbor home
neighbor_result = register_neighbor_home(
    address="456 Elm St",
    city="Rochester",
    state="MN"
)
```

### Neighbor Discovery

```python
from app.services.cluster_engine import discover_neighbors_for_host, find_qualified_host_for_neighbor

# Find neighbors for a host
host_address = "123 Main St, Rochester, MN"
qualified_neighbors = discover_neighbors_for_host(host_address)

# Find qualifying hosts for a neighbor
neighbor_address = "456 Elm St, Rochester, MN" 
qualified_hosts = find_qualified_host_for_neighbor(neighbor_address)
```

### Geographic Services

```python
from app.services.mapbox_service import MapboxService

mapbox = MapboxService(access_token)

# Geocode address
coords = mapbox.geocode_address("123 Main St, Rochester, MN")
if coords:
    latitude, longitude = coords

# Check road crossing (road-aware detection)
host_coords = (44.0123, -92.1234)
neighbor_coords = (44.0124, -92.1235)
is_accessible = mapbox.is_accessible_without_crossing_road(host_coords, neighbor_coords)
```

## Current API Endpoints

### Authentication

```bash
# Login to get session
curl -X POST "http://localhost:8000/login" \
  -H "Content-Type: application/json" \
  -d '{
    "account": "user@email.com",
    "password": "password123",
    "device_name": "Luba-XXXXX"
  }'
```

### Mower Control

```bash
# Get device status
curl "http://localhost:8000/status?device_name=Luba-XXXXX"

# Start mowing
curl -X POST "http://localhost:8000/start-mow" \
  -H "Content-Type: application/json" \
  -d '{"device_name": "Luba-XXXXX"}'

# Stop mowing
curl -X POST "http://localhost:8000/stop-mow" \
  -H "Content-Type: application/json" \
  -d '{"device_name": "Luba-XXXXX"}'

# Return to dock
curl -X POST "http://localhost:8000/return-to-dock" \
  -H "Content-Type: application/json" \
  -d '{"device_name": "Luba-XXXXX"}'
```

### Cluster Management

```bash
# Register host home
curl -X POST "http://localhost:8000/clusters/register_host_home_csv" \
  -H "Content-Type: application/json" \
  -d '{
    "address": "123 Main St",
    "city": "Rochester",
    "state": "MN"
  }'

# Find neighbors for host
curl -X POST "http://localhost:8000/clusters/discover_neighbors_for_host_csv" \
  -H "Content-Type: application/json" \
  -d '{
    "address": "123 Main St",
    "city": "Rochester", 
    "state": "MN"
  }'

# Geocode address
curl -X POST "http://localhost:8000/clusters/geocode" \
  -H "Content-Type: application/json" \
  -d '{"address": "123 Main St, Rochester, MN"}'
```

## Work Mode Constants

```python
# PyMammotion work modes
MODE_NOT_ACTIVE = 0
MODE_ONLINE = 1
MODE_OFFLINE = 2
MODE_DISABLE = 8
MODE_INITIALIZATION = 10
MODE_READY = 11
MODE_WORKING = 13
MODE_RETURNING = 14
MODE_CHARGING = 15
MODE_UPDATING = 16
MODE_LOCK = 17
MODE_PAUSE = 19
MODE_MANUAL_MOWING = 20
```

## Common Usage Patterns

### Full Mower Control Workflow

```python
async def complete_mowing_session():
    # 1. Initialize and authenticate
    mammotion = Mammotion()
    await mammotion.login_and_initiate_cloud("user@email.com", "password")
    
    # 2. Get device
    devices = mammotion.device_manager.devices
    device_name = list(devices.keys())[0]
    
    # 3. Check status before starting
    device = mammotion.get_device_by_name(device_name)
    battery = device.mower_state.report_data.dev.battery_val
    
    if battery < 20:
        print("Battery too low, sending to dock")
        await mammotion.send_command(device_name, "return_to_dock")
        return
    
    # 4. Start mowing
    await mammotion.send_command(device_name, "start_job")
    
    # 5. Monitor progress
    while True:
        device = mammotion.get_device_by_name(device_name)
        mode = device.mower_state.report_data.dev.sys_status
        progress = device.mower_state.report_data.work.progress
        
        print(f"Mode: {mode}, Progress: {progress}%")
        
        if mode == 14:  # MODE_RETURNING
            print("Mowing complete, returning to dock")
            break
            
        await asyncio.sleep(30)  # Check every 30 seconds
```

### Cluster Setup Workflow

```python
async def setup_mowing_cluster():
    # 1. Register host home
    host_result = register_host_home(
        "123 Main St", "Rochester", "MN"
    )
    
    if not host_result["success"]:
        print("Failed to register host")
        return
    
    # 2. Find qualified neighbors
    neighbors = discover_neighbors_for_host(host_result["full_address"])
    print(f"Found {len(neighbors)} qualified neighbors")
    
    # 3. Register neighbors that want to join
    for neighbor_address in neighbors[:3]:  # Limit to 3 neighbors
        # In real implementation, this would be user-driven
        address_parts = neighbor_address.split(", ")
        register_neighbor_home(
            address_parts[0],
            address_parts[1], 
            address_parts[2]
        )
    
    print("Cluster setup complete")
```

### Error Handling Patterns

```python
async def robust_mower_command(device_name: str, command: str):
    """Execute mower command with error handling"""
    max_retries = 3
    
    for attempt in range(max_retries):
        try:
            await mammotion.send_command(device_name, command)
            print(f"Command '{command}' executed successfully")
            return True
            
        except Exception as e:
            print(f"Attempt {attempt + 1} failed: {e}")
            if attempt < max_retries - 1:
                await asyncio.sleep(2 ** attempt)  # Exponential backoff
            else:
                print(f"Command '{command}' failed after {max_retries} attempts")
                return False
```

### Status Monitoring with Caching

```python
import time
from typing import Dict, Optional

class MowerStatusCache:
    def __init__(self, cache_duration: int = 30):
        self.cache: Dict[str, tuple] = {}
        self.cache_duration = cache_duration
    
    async def get_status(self, device_name: str) -> Optional[Dict]:
        """Get device status with caching"""
        now = time.time()
        
        # Check cache
        if device_name in self.cache:
            cached_data, timestamp = self.cache[device_name]
            if now - timestamp < self.cache_duration:
                return cached_data
        
        # Fetch fresh data
        try:
            device = mammotion.get_device_by_name(device_name)
            status = {
                "online": device.mower_state.online,
                "battery": device.mower_state.report_data.dev.battery_val,
                "mode": device.mower_state.report_data.dev.sys_status,
                "timestamp": now
            }
            
            # Cache the result
            self.cache[device_name] = (status, now)
            return status
            
        except Exception as e:
            print(f"Failed to get status for {device_name}: {e}")
            return None

# Usage
cache = MowerStatusCache()
status = await cache.get_status("Luba-XXXXX")
```

## Development Setup

```bash
# 1. Clone with submodules
git clone --recursive https://github.com/your-org/mowthosos
cd mowthosos

# 2. Install dependencies
pip install -r requirements.txt
pip install -r PyMammotion/requirements.txt
pip install -r Mowthos-Cluster-Logic/requirements.txt

# 3. Set up environment
cp .env.example .env
# Edit .env with your API keys

# 4. Run the application
python main.py

# 5. Test the API
curl http://localhost:8000/health
```

## Configuration

```python
# Essential environment variables
MAPBOX_ACCESS_TOKEN=pk.xxx              # For geocoding and mapping
STRIPE_SECRET_KEY=sk_xxx                # For payment processing (future)
DATABASE_URL=postgresql://...           # Database connection
REDIS_URL=redis://localhost:6379/0     # Cache and sessions
SECRET_KEY=your_secret_key              # JWT signing
LOG_LEVEL=INFO                          # Logging level
```

## Troubleshooting

### Common PyMammotion Issues

```python
# Issue: Login fails
# Solution: Check credentials and network connectivity
try:
    await mammotion.login_and_initiate_cloud(account, password)
except Exception as e:
    print(f"Login failed: {e}")
    # Check account credentials, network connection

# Issue: Device not found  
# Solution: Verify device name and ensure it's online
devices = mammotion.device_manager.devices
if device_name not in devices:
    print(f"Available devices: {list(devices.keys())}")

# Issue: Command not responding
# Solution: Check device connection preference
device = mammotion.get_device_by_name(device_name)
if not device.has_cloud() and device.preference == ConnectionPreference.WIFI:
    print("Device has no cloud connection but WiFi preference set")
```

### Common Cluster Logic Issues

```python
# Issue: Geocoding fails
# Solution: Check Mapbox token and address format
coords = mapbox.geocode_address(address)
if not coords:
    print(f"Failed to geocode: {address}")
    print("Check address format and Mapbox token")

# Issue: No neighbors found
# Solution: Check radius and road detection
neighbors = discover_neighbors_for_host(host_address)
if not neighbors:
    print("No neighbors found - check 80m radius and road accessibility")

# Issue: Road detection errors
# Solution: Ensure OSMnx is installed and network is available
try:
    import osmnx as ox
except ImportError:
    print("OSMnx not available - road detection disabled")
```

This quick reference provides the essential functions and patterns needed to work effectively with both PyMammotion and Mowthos-Cluster-Logic components.