# 🚨 CRITICAL: External Submodule Warning

## ⚠️ DO NOT MODIFY EXTERNAL SUBMODULES

**This repository contains external git submodules that MUST NOT be modified directly.**

### Current External Dependencies

**✅ CLUSTER LOGIC MIGRATED:**
- ✅ `src/services/cluster/` - Integrated clustering logic (modify freely)

**🚨 EXTERNAL SUBMODULE (READ-ONLY):**
- ❌ `PyMammotion/` - External submodule (mikey0000/PyMammotion)

### Why This Matters

**External submodules are git repositories within git repositories:**

1. **External Ownership**: We do not own or control these repositories
2. **Update Conflicts**: Direct modifications will cause conflicts when updating
3. **Lost Changes**: Your changes will be overwritten during submodule updates
4. **Breaking Compatibility**: Modifications may break compatibility with upstream updates

### What Happens If You Modify External Submodules

```bash
# ❌ DON'T DO THIS
cd PyMammotion/
# Edit files here - BAD!
git add .
git commit -m "My changes"  # This will cause problems!

# ✅ DO THIS INSTEAD
# Use PyMammotion as-is, create wrappers in our codebase
# See development-guidelines.md for proper integration patterns
```

### Proper Integration Patterns

**✅ Correct Approach - Use Wrappers:**
```python
# src/services/mower/service.py
from pymammotion.mammotion.devices.mammotion import Mammotion

class MowerService:
    def __init__(self):
        # Use PyMammotion as-is, don't modify it
        self._mammotion = Mammotion()
    
    async def enhanced_start_mowing(self, device_name: str):
        # Add our custom logic around PyMammotion
        await self._log_operation_start(device_name)
        
        # Use PyMammotion unchanged
        await self._mammotion.send_command(device_name, "start_job")
        
        # Add our custom logic
        await self._notify_cluster_members(device_name)
```

**❌ Incorrect Approach - Direct Modification:**
```python
# ❌ DON'T DO THIS
# Don't modify PyMammotion files directly
# Don't copy PyMammotion code into our codebase
# Don't override PyMammotion internals
```

### Cluster Logic Migration

**✅ GOOD NEWS: Clustering logic is now integrated!**

The clustering logic has been successfully migrated from the external `Mowthos-Cluster-Logic` submodule and is now fully integrated into our codebase at `src/services/cluster/`.

**Benefits of Migration:**
- ✅ Direct control over clustering algorithms
- ✅ Simplified architecture and imports
- ✅ Easy customization and maintenance
- ✅ No external dependencies for core logic
- ✅ Better performance and reliability

**Use Our Integrated Functions:**
```python
# ✅ CORRECT: Use our integrated functions
from src.services.cluster.engine import (
    register_host_home, discover_neighbors_for_host
)

result = register_host_home("123 Main St", "Rochester", "MN", 44.0123, -92.1234)
neighbors = discover_neighbors_for_host("123 Main St, Rochester, MN")
```

### Emergency Procedures

**If you accidentally modified PyMammotion:**

```bash
# 1. Check what was changed
cd PyMammotion/
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

**If submodule is broken:**

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

### Contributing to External Projects

**If you need features in PyMammotion:**

1. **Fork the original repository**: `https://github.com/mikey0000/PyMammotion`
2. **Create a feature branch**: `git checkout -b feature/my-improvement`
3. **Make your changes**: Follow their contributing guidelines
4. **Submit a pull request**: To the original PyMammotion repository
5. **Wait for acceptance**: Don't modify the submodule until merged
6. **Update submodule**: Once your PR is merged upstream

### Summary

**✅ DO:**
- Use external libraries as dependencies
- Create wrapper services for custom functionality
- Contribute improvements back to original projects
- Update submodules when new versions are available

**❌ DON'T:**
- Modify any files in `PyMammotion/` directory
- Add custom code to external library classes
- Fork external repositories for private modifications
- Ignore upstream updates

**Remember: External submodules are read-only dependencies!**

For detailed integration patterns, see [Development Guidelines](development-guidelines.md).