# ⚠️ CRITICAL WARNING: External Submodules

## DO NOT MODIFY THESE DIRECTORIES

### 🚨 READ-ONLY DIRECTORIES
```
❌ PyMammotion/           - External submodule (mikey0000/PyMammotion)
❌ Mowthos-Cluster-Logic/ - External submodule (jackhobday/Mowthos-Cluster-Logic)
```

### WHY?
- **Git Submodules**: These point to external repositories
- **Not Our Code**: We don't own or control these projects
- **Lost Changes**: Updates will overwrite any modifications
- **Merge Conflicts**: Local changes cause update conflicts

### WHAT TO DO INSTEAD
✅ Create wrapper services in `src/services/`
✅ Use composition patterns
✅ Add our logic around their APIs
✅ Contribute changes back to original projects

### NEED HELP?
📖 Read the full guide: [Development Guidelines](development-guidelines.md)

---

**Remember: Treat external submodules as dependencies, not as part of our codebase!**