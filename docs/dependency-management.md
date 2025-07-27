# Dependency Management Guide

## Overview

This project uses **Poetry** for dependency management. Poetry is a modern dependency management tool that handles dependency resolution, virtual environments, and package building.

## Migration from pip to Poetry

The project has been migrated from `pip` and `requirements.txt` to Poetry. The main changes include:

1. **Removed Files:**
   - `requirements.txt` - No longer needed, dependencies are now in `pyproject.toml`

2. **Added Files:**
   - `pyproject.toml` - Contains project metadata and dependencies
   - `poetry.lock` - Lockfile ensuring reproducible builds

## Installation

### Installing Poetry

Poetry can be installed using the official installer:

```bash
curl -sSL https://install.python-poetry.org | python3 -
```

After installation, add Poetry to your PATH:

```bash
export PATH="$HOME/.local/bin:$PATH"
```

### Installing Project Dependencies

To install all project dependencies:

```bash
poetry install
```

This will:
- Create a virtual environment automatically
- Install all dependencies from `poetry.lock`
- Install the project in development mode

To install only production dependencies (without dev dependencies):

```bash
poetry install --without dev
```

## Managing Dependencies

### Adding Dependencies

To add a new dependency:

```bash
# Add a production dependency
poetry add package-name

# Add a development dependency
poetry add --group dev package-name

# Add with version constraints
poetry add "package-name^2.0.0"
```

### Removing Dependencies

To remove a dependency:

```bash
poetry remove package-name
```

### Updating Dependencies

To update dependencies:

```bash
# Update all dependencies
poetry update

# Update specific package
poetry update package-name

# Show outdated packages
poetry show --outdated
```

### Viewing Dependencies

To view installed packages:

```bash
# Show all installed packages
poetry show

# Show dependency tree
poetry show --tree

# Show details of a specific package
poetry show package-name
```

## Virtual Environment Management

Poetry automatically manages virtual environments:

```bash
# Activate the virtual environment
poetry shell

# Run commands in the virtual environment
poetry run python script.py
poetry run pytest

# Show virtual environment info
poetry env info

# List all environments
poetry env list
```

## Configuration

### pyproject.toml Structure

The `pyproject.toml` file contains:

```toml
[tool.poetry]
name = "mowthos-os"
version = "0.1.0"
description = "FastAPI microservice for Mammotion robotic mower control"
authors = ["Your Name <you@example.com>"]
readme = "README.md"
packages = [{include = "src"}]

[tool.poetry.dependencies]
python = "^3.10"
fastapi = "^0.104.0"
uvicorn = {extras = ["standard"], version = "^0.24.0"}
pydantic = "^2.0.0"
pymammotion = "^0.4.0"

[tool.poetry.group.dev.dependencies]
pytest = "^7.4.0"
pytest-asyncio = "^0.21.0"
black = "^23.0.0"
flake8 = "^6.0.0"
mypy = "^1.5.0"
isort = "^5.12.0"
```

### Python Version Requirements

The project requires Python 3.10 or higher. The `pymammotion` dependency has specific version requirements that may limit the maximum Python version.

## Development Workflow

### Running the Application

```bash
# Using poetry run
poetry run python main.py

# Or activate shell first
poetry shell
python main.py
```

### Running Tests

```bash
poetry run pytest
```

### Code Formatting and Linting

```bash
# Format code with black
poetry run black .

# Sort imports with isort
poetry run isort .

# Run linting with flake8
poetry run flake8 .

# Type checking with mypy
poetry run mypy .
```

## Building and Publishing

### Building the Package

```bash
poetry build
```

This creates distribution packages in the `dist/` directory.

### Publishing to PyPI

```bash
# Configure PyPI credentials
poetry config pypi-token.pypi your-api-token

# Publish to PyPI
poetry publish
```

## Common Issues and Solutions

### Issue: Python Version Mismatch

If you encounter Python version issues:

1. Check your current Python version: `python --version`
2. Install a compatible Python version (3.10-3.12)
3. Tell Poetry to use the correct Python: `poetry env use python3.10`

### Issue: Dependency Conflicts

If dependency resolution fails:

1. Clear the cache: `poetry cache clear pypi --all`
2. Update the lock file: `poetry lock --no-update`
3. Remove and reinstall: `poetry env remove python && poetry install`

### Issue: Virtual Environment Not Activated

If commands fail to find packages:

1. Ensure you're using `poetry run` prefix
2. Or activate the shell: `poetry shell`
3. Check environment: `poetry env info`

## Docker Integration

When using Poetry in Docker:

```dockerfile
FROM python:3.10-slim

# Install Poetry
RUN pip install poetry

# Copy dependency files
COPY pyproject.toml poetry.lock /app/

WORKDIR /app

# Install dependencies
RUN poetry config virtualenvs.create false && \
    poetry install --no-interaction --no-ansi

# Copy application code
COPY . /app

CMD ["poetry", "run", "python", "main.py"]
```

## CI/CD Integration

For GitHub Actions:

```yaml
- name: Install Poetry
  uses: snok/install-poetry@v1
  with:
    version: latest
    virtualenvs-create: true
    virtualenvs-in-project: true

- name: Install dependencies
  run: poetry install

- name: Run tests
  run: poetry run pytest
```

## Migration Notes

When migrating from pip to Poetry:

1. **Import statements remain the same** - No code changes needed
2. **Virtual environment location changes** - Poetry manages its own environments
3. **Installation commands change** - Use `poetry add` instead of `pip install`
4. **Lock file format differs** - `poetry.lock` replaces `requirements.txt`

## Additional Resources

- [Poetry Documentation](https://python-poetry.org/docs/)
- [Poetry CLI Reference](https://python-poetry.org/docs/cli/)
- [Dependency Specification](https://python-poetry.org/docs/dependency-specification/)
- [pyproject.toml Specification](https://python-poetry.org/docs/pyproject/)