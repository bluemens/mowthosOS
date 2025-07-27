# MowthosOS Development Guidelines

**Critical guidelines for working with the MowthosOS codebase and external dependencies**

## 🚨 CRITICAL: Do NOT Modify External Submodules

### External Dependencies Are Read-Only

**Both PyMammotion and Mowthos-Cluster-Logic are git submodules pointing to external repositories and MUST NOT be modified directly.**

```
⚠️  WARNING: NEVER EDIT FILES IN THESE DIRECTORIES:
   - PyMammotion/
   - Mowthos-Cluster-Logic/
```

**Why external submodules should not be altered:**

1. **Git Submodules**: Both are git submodules from external repositories:
   - PyMammotion: `https://github.com/mikey0000/PyMammotion.git`
   - Mowthos-Cluster-Logic: `https://github.com/jackhobday/Mowthos-Cluster-Logic.git`
2. **External Ownership**: We do not own or control these repositories
3. **Update Conflicts**: Direct modifications will cause conflicts when updating
4. **Lost Changes**: Your changes will be overwritten during submodule updates
5. **Breaking Compatibility**: Modifications may break compatibility with upstream updates
6. **Open Source Contribution**: Changes should be contributed back to the original projects

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
    """Configuration adapter for PyMammotion"""
    
    @staticmethod
    def get_connection_preference(device_type: str) -> ConnectionPreference:
        """Custom logic for connection preferences"""
        preferences = {
            "luba": ConnectionPreference.WIFI,
            "luba2": ConnectionPreference.EITHER,
            "yuka": ConnectionPreference.BLUETOOTH
        }
        return preferences.get(device_type.lower(), ConnectionPreference.EITHER)
```

#### ❌ NEVER Do This:

```python
# ❌ DON'T: Modify PyMammotion files directly
# File: PyMammotion/pymammotion/mammotion/devices/mammotion.py

class Mammotion:  # ❌ DON'T EDIT THIS CLASS
    def __init__(self):
        # ❌ DON'T ADD CUSTOM CODE HERE
        pass
        
    def login_and_initiate_cloud(self, account, password):
        # ❌ DON'T MODIFY EXISTING METHODS
        pass
```

### Updating PyMammotion

**When PyMammotion needs to be updated:**

```bash
# 1. Check for updates
cd PyMammotion
git fetch origin
git log --oneline HEAD..origin/main  # See what's new

# 2. Update to latest version
git checkout main
git pull origin main

# 3. Update the parent repository
cd ..
git add PyMammotion
git commit -m "Update PyMammotion to latest version"

# 4. Test compatibility
python -m pytest tests/test_mammotion_integration.py
```

### Contributing to PyMammotion

**If you need features in PyMammotion:**

1. **Fork the original repository**: `https://github.com/mikey0000/PyMammotion`
2. **Create a feature branch**: `git checkout -b feature/my-improvement`
3. **Make your changes**: Follow their contributing guidelines
4. **Submit a pull request**: To the original PyMammotion repository
5. **Wait for acceptance**: Don't modify the submodule until merged
6. **Update submodule**: Once your PR is merged upstream

```bash
# Contributing workflow
git clone https://github.com/mikey0000/PyMammotion.git
cd PyMammotion
git checkout -b feature/my-improvement

# Make your changes
# Test your changes
# Submit PR to original repository

# After PR is merged, update our submodule
cd ../mowthosos
git submodule update --remote PyMammotion
```

## Development Workflow

### 1. Repository Structure

```
mowthosos/
├── PyMammotion/           # 🚨 DO NOT MODIFY - External submodule
├── Mowthos-Cluster-Logic/ # 🚨 DO NOT MODIFY - External submodule  
├── src/                   # ✅ Our code - modify freely
│   ├── services/
│   │   ├── mower/        # ✅ Wrappers around PyMammotion
│   │   ├── cluster/      # ✅ Wrappers around cluster logic
│   │   └── payment/      # ✅ Our payment system
│   └── api/              # ✅ Our API layer
├── tests/                # ✅ Our tests
├── docs/                 # ✅ Our documentation
└── main.py              # ✅ Our main application
```

### 2. Integration Patterns

**Use these patterns to integrate with PyMammotion safely:**

```python
# Pattern 1: Facade Pattern
class MowerFacade:
    """Simplified interface to PyMammotion"""
    
    def __init__(self):
        self._mammotion = Mammotion()  # Use, don't modify
    
    async def simple_start_mowing(self, device_name: str) -> bool:
        """Simplified mowing start"""
        try:
            await self._mammotion.send_command(device_name, "start_job")
            return True
        except Exception:
            return False

# Pattern 2: Adapter Pattern  
class MowerAdapter:
    """Adapt PyMammotion to our data models"""
    
    def __init__(self, mammotion: Mammotion):
        self._mammotion = mammotion
    
    def to_our_status_format(self, device_name: str) -> Dict:
        """Convert PyMammotion status to our format"""
        device = self._mammotion.get_device_by_name(device_name)
        
        return {
            "id": device_name,
            "status": "online" if device.mower_state.online else "offline",
            "battery": device.mower_state.report_data.dev.battery_val,
            # Our custom fields
            "mowthosos_cluster_id": self._get_cluster_id(device_name)
        }

# Pattern 3: Decorator Pattern
class MowerServiceDecorator:
    """Add MowthosOS features to PyMammotion"""
    
    def __init__(self, mammotion: Mammotion):
        self._mammotion = mammotion
        self._usage_tracker = UsageTracker()
    
    async def send_command_with_tracking(self, device_name: str, command: str):
        """Send command and track usage for billing"""
        # Track the command for billing
        self._usage_tracker.log_command(device_name, command)
        
        # Use PyMammotion unchanged
        return await self._mammotion.send_command(device_name, command)
```

### 3. Testing Integration

**Test your wrappers, not PyMammotion itself:**

```python
# tests/test_mower_service.py
import pytest
from unittest.mock import Mock, AsyncMock
from src.services.mower.service import MowerService

class TestMowerService:
    def test_mower_service_initialization(self):
        """Test our service initializes correctly"""
        service = MowerService()
        assert service._mammotion is not None
        assert hasattr(service, '_cache')
    
    @pytest.mark.asyncio
    async def test_enhanced_status(self):
        """Test our enhanced status method"""
        service = MowerService()
        
        # Mock PyMammotion response
        mock_device = Mock()
        mock_device.mower_state.online = True
        mock_device.mower_state.report_data.dev.battery_val = 85
        
        service._mammotion.get_device_by_name = Mock(return_value=mock_device)
        
        # Test our wrapper
        status = await service.get_enhanced_status("test_device")
        
        assert status.online is True
        assert status.battery_level == 85
```

### 4. Error Handling

**Handle PyMammotion errors gracefully:**

```python
class MowerErrorHandler:
    """Handle PyMammotion errors in MowthosOS context"""
    
    async def safe_execute_command(self, mammotion: Mammotion, device_name: str, command: str):
        """Execute command with proper error handling"""
        try:
            await mammotion.send_command(device_name, command)
            return {"success": True, "message": "Command executed"}
            
        except ConnectionError:
            return {"success": False, "error": "Device offline"}
            
        except Exception as e:
            # Log the error for debugging
            logger.error(f"PyMammotion error: {e}")
            return {"success": False, "error": "Internal error"}
```

## Code Review Checklist

**Before submitting any code, ensure:**

- [ ] ✅ No files in `PyMammotion/` directory are modified
- [ ] ✅ No files in `Mowthos-Cluster-Logic/` directory are modified  
- [ ] ✅ All PyMammotion integration uses wrapper/adapter patterns
- [ ] ✅ Tests mock PyMammotion instead of testing it directly
- [ ] ✅ Error handling wraps PyMammotion exceptions
- [ ] ✅ Documentation explains integration patterns used

## Emergency Procedures

### If PyMammotion Was Accidentally Modified

```bash
# 1. Check what was changed
cd PyMammotion
git status
git diff

# 2. Revert all changes
git checkout .
git clean -fd

# 3. Verify clean state
git status  # Should show "working tree clean"

# 4. Go back to parent directory
cd ..

# 5. Check submodule status
git submodule status
```

### If Submodule is Broken

```bash
# 1. Remove broken submodule
git submodule deinit PyMammotion
rm -rf .git/modules/PyMammotion
git rm PyMammotion

# 2. Re-add clean submodule
git submodule add https://github.com/mikey0000/PyMammotion.git PyMammotion
git submodule update --init PyMammotion

# 3. Commit the fix
git add .gitmodules PyMammotion
git commit -m "Fix PyMammotion submodule"
```

## Summary

**Remember: PyMammotion is an external dependency, treat it as read-only!**

- ✅ **DO**: Use composition, wrappers, and adapters
- ✅ **DO**: Contribute improvements back to the original project
- ✅ **DO**: Update the submodule when new versions are available
- ✅ **DO**: Test your integration code thoroughly

- ❌ **DON'T**: Modify any files in the PyMammotion directory
- ❌ **DON'T**: Add custom code to PyMammotion classes
- ❌ **DON'T**: Fork PyMammotion for private modifications
- ❌ **DON'T**: Ignore upstream updates

Following these guidelines ensures a maintainable, updatable, and professional codebase.