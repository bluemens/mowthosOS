# MowthosOS Quick Reference Guide

**Essential functions and usage patterns for developers**

## 🚨 CRITICAL WARNING

### DO NOT MODIFY External Submodules

**NEVER edit files in this directory:**
- ❌ `PyMammotion/` - External submodule (read-only)

**✅ CLUSTER LOGIC IS NOW INTEGRATED:**
- ✅ `src/services/cluster/` - Integrated clustering logic (modify freely)

**Why?** PyMammotion is a git submodule pointing to an external repository. Any modifications will be:
- Lost during updates
- Cause merge conflicts
- Break compatibility

**See [Development Guidelines](development-guidelines.md) for safe integration patterns.**

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

# Connection preferences
ConnectionPreference.WIFI      # Cloud/WiFi connection
ConnectionPreference.BLUETOOTH # Direct BLE connection
ConnectionPreference.EITHER    # Automatic selection
```

## Cluster Service - Core Functions

### ✅ INTEGRATED CLUSTERING LOGIC

**The clustering logic has been migrated and is now fully integrated into our codebase.**

### Basic Cluster Operations

```python
from src.services.cluster.engine import (
    register_host_home, register_neighbor_home,
    discover_neighbors_for_host, find_qualified_host_for_neighbor
)

# Register a host home
result = register_host_home("123 Main St", "Rochester", "MN", 44.0123, -92.1234)
print(f"Host registration: {result['success']}")

# Register a neighbor home
result = register_neighbor_home("456 Elm St", "Rochester", "MN", 44.0124, -92.1235)
print(f"Neighbor registration: {result['success']}")

# Discover neighbors for a host
neighbors = discover_neighbors_for_host("123 Main St, Rochester, MN")
print(f"Found {len(neighbors)} qualified neighbors")

# Find qualified hosts for a neighbor
hosts = find_qualified_host_for_neighbor("456 Elm St, Rochester, MN")
print(f"Found {len(hosts)} qualified hosts")
```

### Cluster Service Interface

```python
from src.services.cluster.service import ClusterService
from src.models.schemas import Address

# Initialize service
cluster_service = ClusterService()
await cluster_service.initialize()

# Register a host
address = Address(
    street="503 GERANIUM ST SE",
    city="ROCHESTER",
    state="MN",
    zip_code="55904",
    latitude=43.9607404,
    longitude=-92.4557066
)

cluster = await cluster_service.register_host(address, user_id=123)
print(f"Created cluster: {cluster.cluster_id}")

# Find neighbors
neighbors = await cluster_service.find_neighbors(cluster.cluster_id)
print(f"Found {len(neighbors)} neighbors")

# Join a cluster
assignment = await cluster_service.join_cluster(cluster.cluster_id, address, user_id=456)
print(f"User joined cluster: {assignment.status}")
```

### Address Validation

```python
from src.services.cluster.mapbox import MapboxService

mapbox = MapboxService(settings.mapbox_access_token)

# Validate address
validated = await mapbox.validate_address(
    street="123 Main St",
    city="Rochester",
    state="MN",
    zip_code="55901"
)

if validated:
    print(f"Valid address: {validated['latitude']}, {validated['longitude']}")
else:
    print("Invalid address")
```

### CSV File Management

```python
from src.services.cluster.engine import (
    ensure_host_homes_csv, ensure_neighbor_homes_csv,
    load_addresses_from_csv
)

# Ensure CSV files exist
ensure_host_homes_csv()
ensure_neighbor_homes_csv()

# Load addresses from CSV
addresses = load_addresses_from_csv("path/to/addresses.csv")
print(f"Loaded {len(addresses)} addresses")
```

### Advanced Clustering

```python
# Suggest clusters for an address
suggestions = await cluster_service.suggest_clusters(address)
print(f"Found {len(suggestions)} cluster suggestions")

# Get cluster statistics
stats = await cluster_service.get_cluster_stats(cluster_id)
print(f"Cluster stats: {stats.member_count} members, {stats.coverage_area_sqm} sqm")

# Optimize routes
optimization = await cluster_service.optimize_routes(cluster_id)
print(f"Optimized route: {optimization.total_distance_meters}m")

# Calculate coverage
coverage = await cluster_service.calculate_coverage(addresses)
print(f"Coverage: {coverage['total_area']} sqm, {coverage['average_distance']} km")
```

### Geographic Constants

```python
from src.services.cluster.engine import (
    EARTH_RADIUS_M, RADIUS_METERS, RADIUS_RADIANS
)

# Geographic constants
print(f"Earth radius: {EARTH_RADIUS_M} meters")
print(f"Cluster radius: {RADIUS_METERS} meters")
print(f"Radius in radians: {RADIUS_RADIANS}")
```

## Service Integration Patterns

### Mower Service Wrapper

```python
from src.services.mower.service import MowerService

# Initialize mower service
mower_service = MowerService()

# Get device status
status = await mower_service.get_device_status("Luba_001")
print(f"Device {status.device_name}: {status.battery_level}% battery")

# Start mowing
await mower_service.start_mowing("Luba_001")

# Get all devices
devices = await mower_service.get_all_devices()
for device in devices:
    print(f"Device: {device.name}, Status: {device.status}")
```

### Cluster Service Integration

```python
from src.services.cluster.service import ClusterService

# Initialize cluster service
cluster_service = ClusterService()
await cluster_service.initialize()

# Register host and find neighbors
cluster = await cluster_service.register_host(address, user_id)
neighbors = await cluster_service.find_neighbors(cluster.cluster_id)

# Join cluster
assignment = await cluster_service.join_cluster(cluster.cluster_id, neighbor_address, user_id)

# Get cluster analytics
stats = await cluster_service.get_cluster_stats(cluster.cluster_id)
optimization = await cluster_service.optimize_routes(cluster.cluster_id)
```

## Error Handling Patterns

### PyMammotion Error Handling

```python
from pymammotion.mammotion.devices.mammotion import Mammotion

async def safe_mower_operation():
    try:
        mammotion = Mammotion()
        await mammotion.login_and_initiate_cloud("user@email.com", "password")
        
        # Safe command execution
        await mammotion.send_command("Luba_001", "start_job")
        return {"success": True, "message": "Mowing started"}
        
    except ConnectionError:
        return {"success": False, "error": "Device offline"}
    except Exception as e:
        return {"success": False, "error": f"Operation failed: {str(e)}"}
```

### Cluster Service Error Handling

```python
from src.services.cluster.engine import register_host_home

async def safe_host_registration(address, city, state, lat, lon):
    try:
        result = register_host_home(address, city, state, lat, lon)
        
        if result["success"]:
            return {"success": True, "cluster_id": result["full_address"]}
        else:
            return {"success": False, "error": result["message"]}
            
    except FileNotFoundError:
        return {"success": False, "error": "CSV file not found"}
    except Exception as e:
        return {"success": False, "error": f"Registration failed: {str(e)}"}
```

## Testing Patterns

### PyMammotion Testing

```python
import pytest
from unittest.mock import Mock, AsyncMock
from pymammotion.mammotion.devices.mammotion import Mammotion

def test_mammotion_integration():
    """Test PyMammotion integration without modifying it"""
    mammotion = Mammotion()
    assert mammotion is not None
    
    # Mock device for testing
    mock_device = Mock()
    mock_device.mower_state.online = True
    mock_device.mower_state.report_data.dev.battery_val = 85
    
    mammotion.get_device_by_name = Mock(return_value=mock_device)
    
    device = mammotion.get_device_by_name("test_device")
    assert device.mower_state.online is True
    assert device.mower_state.report_data.dev.battery_val == 85
```

### Cluster Logic Testing

```python
import pytest
from src.services.cluster.engine import register_host_home

def test_host_registration():
    """Test our integrated clustering functions"""
    result = register_host_home("123 Main St", "Rochester", "MN", 44.0123, -92.1234)
    assert result["success"] is True
    assert "full_address" in result
    assert "latitude" in result
    assert "longitude" in result

def test_neighbor_discovery():
    """Test neighbor discovery functionality"""
    # First register a host
    register_host_home("123 Main St", "Rochester", "MN", 44.0123, -92.1234)
    
    # Then discover neighbors
    from src.services.cluster.engine import discover_neighbors_for_host
    neighbors = discover_neighbors_for_host("123 Main St, Rochester, MN")
    
    # Should return a list (may be empty depending on data)
    assert isinstance(neighbors, list)
```

## Configuration

### Environment Variables

```bash
# Required for clustering
MAPBOX_ACCESS_TOKEN=your_mapbox_token_here

# Database (for production)
DATABASE_URL=postgresql://user:pass@localhost/mowthos

# Redis (for sessions)
REDIS_URL=redis://localhost:6379

# Security
SECRET_KEY=your-secret-key-here
```

### Poetry Dependencies

```bash
# Install dependencies
poetry install

# Add new dependency
poetry add package-name

# Update dependencies
poetry update

# Show dependency tree
poetry show --tree
```

## Common Commands

### Development

```bash
# Start development server
poetry run uvicorn main:app --reload --host 0.0.0.0 --port 8000

# Run tests
poetry run pytest

# Run specific test file
poetry run pytest tests/test_cluster/test_engine.py

# Run with coverage
poetry run pytest --cov=src --cov-report=html
```

### Code Quality

```bash
# Format code
poetry run black src/ tests/

# Sort imports
poetry run isort src/ tests/

# Type checking
poetry run mypy src/

# Linting
poetry run flake8 src/ tests/
```

### Submodule Management

```bash
# Update PyMammotion submodule
git submodule update --init --recursive

# Check submodule status
git submodule status

# Update to latest version
git submodule update --remote PyMammotion
```

## Migration Notes

### What Was Migrated

**From Mowthos-Cluster-Logic to Integrated Logic:**
- ✅ `register_host_home()` - Host registration
- ✅ `register_neighbor_home()` - Neighbor registration
- ✅ `discover_neighbors_for_host()` - Neighbor discovery
- ✅ `find_qualified_host_for_neighbor()` - Host finding
- ✅ `load_addresses_from_csv()` - CSV processing
- ✅ `ensure_host_homes_csv()` - CSV management
- ✅ Road-aware detection algorithms
- ✅ BallTree optimization
- ✅ Geographic distance calculations

### Benefits Achieved

- ✅ **Simplified Architecture**: No more complex import paths
- ✅ **Direct Control**: Full control over clustering algorithms
- ✅ **Better Performance**: No external module loading overhead
- ✅ **Easier Maintenance**: All logic in our codebase
- ✅ **No External Dependencies**: Core clustering is self-contained

### What Remains External

- PyMammotion (mower control library)
- Rochester address CSV data (read-only reference)

This quick reference provides the essential functions and patterns needed to work effectively with both PyMammotion and our integrated clustering system.