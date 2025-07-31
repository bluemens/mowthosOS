# MowthosOS Development Guidelines

**Critical guidelines for working with the MowthosOS codebase and external dependencies**

## 🚨 CRITICAL: Do NOT Modify External Submodules

### External Dependencies Are Read-Only

**PyMammotion is a git submodule pointing to an external repository and MUST NOT be modified directly.**

```
⚠️  WARNING: NEVER EDIT FILES IN THIS DIRECTORY:
   - PyMammotion/
```

**✅ CLUSTER LOGIC IS NOW INTEGRATED:**
```
✅  MIGRATED: Clustering logic is now integrated in src/services/cluster/
✅  STATUS: No longer dependent on external Mowthos-Cluster-Logic submodule
✅  BENEFITS: Direct control, easier maintenance, better performance
```

**Why external submodules should not be altered:**

1. **Git Submodules**: PyMammotion is a git submodule from external repository:
   - PyMammotion: `https://github.com/mikey0000/PyMammotion.git`
2. **External Ownership**: We do not own or control this repository
3. **Update Conflicts**: Direct modifications will cause conflicts when updating
4. **Lost Changes**: Your changes will be overwritten during submodule updates
5. **Breaking Compatibility**: Modifications may break compatibility with upstream updates
6. **Open Source Contribution**: Changes should be contributed back to the original project

### What to Do Instead

#### ✅ Correct Approaches:

**1. Create Wrapper Services**
```python
# src/services/mower/wrapper.py
from pymammotion.mammotion.devices.mammotion import Mammotion
from typing import Dict, Any

class MowthosMAmmotionWrapper:
    """Wrapper around PyMammotion for MowthosOS-specific functionality"""
    
    def __init__(self):
        self.mammotion = Mammotion()
        self.custom_settings = {}
    
    async def enhanced_login(self, account: str, password: str) -> Dict[str, Any]:
        """Enhanced login with MowthosOS-specific features"""
        # Use PyMammotion as-is, add our custom logic
        await self.mammotion.login_and_initiate_cloud(account, password)
        
        # Add our custom functionality
        return {
            "success": True,
            "devices": list(self.mammotion.device_manager.devices.keys()),
            "session_id": self._generate_session_id()
        }
    
    def _generate_session_id(self) -> str:
        """Custom session management for MowthosOS"""
        # Our custom implementation
        pass
```

**2. Use Composition Pattern**
```python
# src/services/mower/service.py
from pymammotion.mammotion.devices.mammotion import Mammotion
from src.models.schemas import MowerStatus, MowerCommand

class MowerService:
    """MowthosOS mower service using PyMammotion"""
    
    def __init__(self):
        # Use PyMammotion as a dependency, don't modify it
        self._mammotion = Mammotion()
        self._cache = {}
        self._sessions = {}
    
    async def get_enhanced_status(self, device_name: str) -> MowerStatus:
        """Get device status with MowthosOS enhancements"""
        # Get data from PyMammotion unchanged
        device = self._mammotion.get_device_by_name(device_name)
        raw_state = device.mower_state
        
        # Transform to our format without changing PyMammotion
        return MowerStatus(
            device_name=device_name,
            online=raw_state.online,
            battery_level=raw_state.report_data.dev.battery_val,
            # Add our custom fields
            last_maintenance=self._get_maintenance_date(device_name),
            cluster_assignment=self._get_cluster_assignment(device_name)
        )
```

**3. Extend Through Configuration**
```python
# src/core/mammotion_config.py
from pymammotion.data.model.enums import ConnectionPreference

class MowthosMAmmotionConfig:
    """Configuration wrapper for PyMammotion settings"""
    
    def __init__(self):
        self.connection_preference = ConnectionPreference.WIFI
        self.timeout_seconds = 30
        self.retry_attempts = 3
    
    def get_mammotion_config(self) -> Dict[str, Any]:
        """Get configuration for PyMammotion without modifying it"""
        return {
            "connection_preference": self.connection_preference,
            "timeout": self.timeout_seconds,
            "retries": self.retry_attempts
        }
```

#### ❌ Incorrect Approaches:

**1. Direct Modification**
```python
# ❌ NEVER DO THIS
# Don't modify PyMammotion files directly
from pymammotion.mammotion.devices.mammotion import Mammotion

# ❌ Don't edit PyMammotion source code
class ModifiedMammotion(Mammotion):
    def __init__(self):
        super().__init__()
        # Don't override PyMammotion internals
```

**2. Forking External Repositories**
```python
# ❌ Don't fork and modify external repos
# Instead, use the original and create wrappers
from pymammotion.mammotion.devices.mammotion import Mammotion  # ✅ Use original
```

**3. Copying External Code**
```python
# ❌ Don't copy PyMammotion code into our codebase
# Instead, use it as a dependency
```

### Cluster Logic Migration

#### ✅ Current Status: Integrated Clustering

**The clustering logic has been successfully migrated from Mowthos-Cluster-Logic and is now fully integrated into our codebase.**

**Location**: `src/services/cluster/`

**Components**:
- `service.py` - Main cluster service interface
- `engine.py` - Core clustering algorithms and functions
- `mapbox.py` - Address validation and geocoding
- `__init__.py` - Module initialization

**Benefits of Migration**:
- ✅ Direct control over clustering algorithms
- ✅ Simplified architecture and imports
- ✅ Easy customization and maintenance
- ✅ No external dependencies for core logic
- ✅ Better performance and reliability

**Key Functions Now Available**:
```python
from src.services.cluster.engine import (
    register_host_home, register_neighbor_home,
    discover_neighbors_for_host, find_qualified_host_for_neighbor,
    ensure_host_homes_csv, ensure_neighbor_homes_csv
)

# Use these functions directly in your code
result = register_host_home("123 Main St", "Rochester", "MN", 44.0123, -92.1234)
neighbors = discover_neighbors_for_host("123 Main St, Rochester, MN")
```

### Project Structure

```
mowthosOS/
├── src/
│   ├── api/                    # FastAPI routes and endpoints
│   ├── core/                   # Core configuration and utilities
│   ├── models/                 # Data models and schemas
│   └── services/               # Business logic services
│       ├── mower/              # Mower control (PyMammotion wrapper)
│       └── cluster/            # ✅ INTEGRATED: Clustering logic
│           ├── service.py      # Main cluster service
│           ├── engine.py       # Core clustering algorithms
│           └── mapbox.py       # Address validation
├── PyMammotion/                # 🚨 DO NOT MODIFY - External submodule
├── tests/                      # Test suite
├── docs/                       # Documentation
└── requirements.txt            # Dependencies
```

### Development Workflow

#### 1. Setting Up Development Environment

```bash
# Clone repository with submodules
git clone --recursive https://github.com/your-org/mowthosOS.git
cd mowthosOS

# Install dependencies
poetry install

# Initialize submodules (PyMammotion only)
git submodule update --init --recursive

# Set up environment
cp .env.local.example .env.local
# Edit .env.local with your configuration
```

#### 2. Working with PyMammotion

**✅ Correct Pattern:**
```python
# src/services/mower/service.py
from pymammotion.mammotion.devices.mammotion import Mammotion

class MowerService:
    def __init__(self):
        # Use PyMammotion as-is
        self._mammotion = Mammotion()
    
    async def start_mowing(self, device_name: str):
        # Use PyMammotion methods directly
        await self._mammotion.send_command(device_name, "start_job")
        
        # Add our custom logic
        await self._log_mowing_start(device_name)
        await self._notify_cluster_members(device_name)
```

**❌ Incorrect Pattern:**
```python
# Don't modify PyMammotion files
# Don't copy PyMammotion code into our codebase
# Don't override PyMammotion internals
```

#### 3. Working with Cluster Logic

**✅ Correct Pattern:**
```python
# src/services/cluster/service.py
from .engine import register_host_home, discover_neighbors_for_host

class ClusterService:
    async def register_host(self, address: Address, user_id: int):
        # Use our integrated functions
        result = register_host_home(
            address.street, address.city, address.state,
            address.latitude, address.longitude
        )
        
        # Add our custom logic
        await self._create_cluster_record(result, user_id)
```

#### 4. Testing

**Test PyMammotion Integration:**
```python
# tests/test_mower/test_pymammotion_integration.py
import pytest
from pymammotion.mammotion.devices.mammotion import Mammotion

def test_pymammotion_connection():
    """Test PyMammotion integration without modifying it"""
    mammotion = Mammotion()
    # Test PyMammotion functionality as-is
    assert mammotion is not None
```

**Test Cluster Logic:**
```python
# tests/test_cluster/test_integrated_functions.py
from src.services.cluster.engine import register_host_home

def test_host_registration():
    """Test our integrated clustering functions"""
    result = register_host_home("123 Main St", "Rochester", "MN", 44.0123, -92.1234)
    assert result["success"] is True
```

### Code Review Checklist

#### ✅ Pre-Submission Checklist

**External Dependencies:**
- [ ] ✅ No files in `PyMammotion/` directory are modified
- [ ] ✅ No PyMammotion code copied into our codebase
- [ ] ✅ All PyMammotion usage is through proper imports
- [ ] ✅ Wrapper services created for custom functionality

**Cluster Logic:**
- [ ] ✅ All clustering functions use our integrated logic
- [ ] ✅ No references to external Mowthos-Cluster-Logic
- [ ] ✅ Tests pass for integrated clustering functions
- [ ] ✅ Documentation updated to reflect migration

**General Code Quality:**
- [ ] ✅ All tests pass
- [ ] ✅ Code follows PEP 8 style guidelines
- [ ] ✅ Type hints added where appropriate
- [ ] ✅ Documentation updated for any API changes
- [ ] ✅ No hardcoded secrets or credentials
- [ ] ✅ Error handling implemented
- [ ] ✅ Logging added for debugging

#### 🚨 Critical Review Points

**1. External Submodule Protection:**
```bash
# Check for any modifications to PyMammotion
git status PyMammotion/
# Should show "working tree clean" or only submodule updates
```

**2. Import Patterns:**
```python
# ✅ Correct: Import from PyMammotion
from pymammotion.mammotion.devices.mammotion import Mammotion

# ✅ Correct: Use our integrated functions
from src.services.cluster.engine import register_host_home

# ❌ Incorrect: Import from external Mowthos-Cluster-Logic
# from Mowthos-Cluster-Logic.app.services.cluster_engine import ...
```

**3. Function Usage:**
```python
# ✅ Correct: Use our integrated functions
result = register_host_home("123 Main St", "Rochester", "MN")

# ❌ Incorrect: Call external Mowthos functions
# result = external_mowthos_function("123 Main St", "Rochester", "MN")
```

### Troubleshooting

#### Common Issues

**1. PyMammotion Import Errors:**
```bash
# Solution: Update submodule
git submodule update --init --recursive
pip install -r PyMammotion/requirements.txt
```

**2. Cluster Function Errors:**
```bash
# Solution: Use our integrated functions
from src.services.cluster.engine import register_host_home
# Not from external Mowthos-Cluster-Logic
```

**3. Submodule Conflicts:**
```bash
# Solution: Reset submodule to clean state
git submodule update --init --recursive --force
```

#### Getting Help

**For PyMammotion Issues:**
- Check PyMammotion documentation: https://github.com/mikey0000/PyMammotion
- Create issues in PyMammotion repository
- Use PyMammotion as-is, create wrappers for custom needs

**For Cluster Logic Issues:**
- Check our integrated cluster service: `src/services/cluster/`
- Review migration documentation
- Use our integrated functions, not external ones

### Best Practices Summary

#### ✅ Do's

1. **Use PyMammotion as a dependency**
   - Import and use PyMammotion classes and functions
   - Create wrapper services for custom functionality
   - Extend through composition, not inheritance

2. **Use integrated cluster logic**
   - Import from `src.services.cluster.engine`
   - Use our integrated functions for all clustering
   - Customize algorithms in our codebase

3. **Follow proper testing patterns**
   - Test PyMammotion integration without modifying it
   - Test our integrated cluster functions
   - Mock external dependencies appropriately

4. **Maintain clean architecture**
   - Keep external dependencies separate
   - Use dependency injection for external services
   - Create clear interfaces between components

#### ❌ Don'ts

1. **Don't modify external submodules**
   - Never edit files in `PyMammotion/`
   - Don't copy external code into our codebase
   - Don't override external library internals

2. **Don't use external Mowthos functions**
   - Don't import from `Mowthos-Cluster-Logic/`
   - Don't call external clustering functions
   - Use our integrated cluster logic instead

3. **Don't bypass proper patterns**
   - Don't hardcode external library internals
   - Don't create tight coupling to external APIs
   - Don't ignore error handling and logging

### Migration Notes

**What Was Migrated:**
- ✅ All clustering algorithms from Mowthos-Cluster-Logic
- ✅ Address validation and geocoding functions
- ✅ CSV file management and data loading
- ✅ Road-aware neighbor detection
- ✅ BallTree optimization algorithms

**What Remains External:**
- PyMammotion (mower control library)
- Rochester address CSV data (read-only reference)

**Benefits Achieved:**
- ✅ Simplified architecture
- ✅ Direct control over clustering logic
- ✅ Better performance and reliability
- ✅ Easier maintenance and customization
- ✅ No external dependencies for core functionality

This migration represents a significant improvement in the system's maintainability and performance while preserving all the advanced geographic intelligence capabilities.