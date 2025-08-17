# Testing Guide for Sentries

This document describes how to test the Sentries package to ensure it works correctly before deploying to other repositories.

## 🧪 Testing Overview

The Sentries package includes multiple layers of testing to ensure reliability:

1. **Unit Tests**: Test individual components and functions
2. **Integration Tests**: Test how components work together
3. **End-to-End Tests**: Test complete workflows in realistic scenarios
4. **GitHub Actions**: Automated testing on every PR and push
5. **Smoke Tests**: Quick health checks for basic functionality

## 🚀 Quick Start Testing

### Prerequisites

```bash
# Install the package in development mode
pip install -e .

# Install testing dependencies
pip install -e ".[test]"
```

### Run All Tests

```bash
# Run unit tests with coverage
pytest

# Run end-to-end tests
python scripts/e2e_test.py

# Run smoke test
python scripts/smoke.py
```

## 📋 Test Categories

### 1. Unit Tests (`pytest`)

Unit tests verify individual components work correctly:

```bash
# Run all unit tests
pytest

# Run tests with coverage report
pytest --cov=sentries --cov-report=html

# Run specific test file
pytest sentries/test_basic.py

# Run tests with verbose output
pytest -v
```

**Test Files:**
- `sentries/test_basic.py` - Basic functionality tests
- Additional test files can be added to `sentries/` and `scripts/` directories

### 2. End-to-End Tests (`scripts/e2e_test.py`)

End-to-end tests simulate real-world usage scenarios:

```bash
python scripts/e2e_test.py
```

**What E2E Tests Cover:**
- ✅ Import functionality for all modules
- ✅ Allowlist validation and configuration
- ✅ CLI command availability
- ✅ Repository structure validation
- ✅ Test failure simulation
- ✅ Git repository operations

**E2E Test Process:**
1. Creates a temporary test repository
2. Sets up realistic file structures
3. Initializes git repository with test data
4. Runs comprehensive validation tests
5. Cleans up test environment

### 3. Smoke Tests (`scripts/smoke.py`)

Smoke tests provide quick health checks:

```bash
python scripts/smoke.py
```

**Smoke Test Coverage:**
- Ollama connectivity
- Model availability
- Basic LLM response capability
- Environment configuration

### 4. Linting and Code Quality

```bash
# Run all linting tools
flake8 sentries/ scripts/
black --check --diff sentries/ scripts/
isort --check-only --diff sentries/ scripts/
mypy sentries/ --ignore-missing-imports
```

## 🔄 GitHub Actions Testing

The repository includes automated GitHub Actions workflows that run on every PR and push:

### Workflows

1. **`test-sentries.yml`** - Comprehensive testing matrix
   - Runs on Python 3.10, 3.11, 3.12
   - Includes unit tests, integration tests, and linting
   - Generates coverage reports

2. **`test-sentry.yml`** - TestSentry integration testing
   - Tests TestSentry functionality in real repository
   - Requires self-hosted runner with Ollama

3. **`doc-sentry.yml`** - DocSentry integration testing
   - Tests DocSentry functionality in real repository
   - Requires self-hosted runner with Ollama

### Self-Hosted Runner Setup

For integration testing, you need a self-hosted runner with Ollama:

```bash
# Install Ollama on runner
curl -fsSL https://ollama.ai/install.sh | sh

# Install required models
ollama pull llama3.1:8b-instruct-q4_K_M
ollama pull deepseek-coder:6.7b-instruct-q5_K_M

# Start Ollama service
ollama serve
```

## 🧪 Testing Scenarios

### TestSentry Testing

To test TestSentry functionality:

1. **Create a repository with failing tests:**
   ```python
   def test_failing_function():
       assert 1 == 2  # This will fail
   ```

2. **Run TestSentry:**
   ```bash
   testsentry
   ```

3. **Verify:**
   - TestSentry identifies failing tests
   - Generates appropriate fixes
   - Creates PR with test fixes
   - Labels PR correctly

### DocSentry Testing

To test DocSentry functionality:

1. **Create a PR with code changes**
2. **Run DocSentry:**
   ```bash
   docsentry
   ```

3. **Verify:**
   - DocSentry analyzes PR changes
   - Generates documentation updates
   - Creates PR with doc updates
   - Labels PR correctly

## 🔍 Debugging Tests

### Enable Debug Logging

```bash
export LOG_LEVEL=DEBUG
pytest -v
```

### Test Specific Components

```bash
# Test only import functionality
python -c "from sentries import banner, chat, prompts; print('Imports OK')"

# Test CLI commands
testsentry --help
docsentry --help

# Test allowlists
python -c "from sentries.runner_common import TESTS_ALLOWLIST, DOCS_ALLOWLIST; print(f'Test allowlist: {TESTS_ALLOWLIST}'); print(f'Doc allowlist: {DOCS_ALLOWLIST}')"
```

### Common Test Issues

1. **Import Errors:**
   - Ensure package is installed: `pip install -e .`
   - Check Python path: `python -c "import sys; print(sys.path)"`

2. **CLI Command Not Found:**
   - Verify installation: `pip list | grep sentries`
   - Check entry points: `pip show sentries`

3. **Git Operations Fail:**
   - Ensure git is configured: `git config --list`
   - Check repository status: `git status`

## 📊 Coverage Reports

Generate coverage reports to identify untested code:

```bash
# Generate HTML coverage report
pytest --cov=sentries --cov-report=html

# Open coverage report
open htmlcov/index.html

# Generate XML coverage for CI
pytest --cov=sentries --cov-report=xml
```

## 🚨 Pre-Deployment Checklist

Before deploying Sentries to other repositories, ensure:

- [ ] All unit tests pass: `pytest`
- [ ] All E2E tests pass: `python scripts/e2e_test.py`
- [ ] Smoke test passes: `python scripts/smoke.py`
- [ ] Linting passes: `flake8`, `black`, `isort`, `mypy`
- [ ] GitHub Actions pass on main branch
- [ ] Coverage is above 80%
- [ ] Documentation is up to date

## 🔧 Adding New Tests

### Unit Tests

Create test files in `sentries/` or `scripts/` directories:

```python
# sentries/test_new_feature.py
import pytest
from sentries.new_feature import new_function

def test_new_function():
    result = new_function()
    assert result == "expected_value"
```

### Integration Tests

Add new test methods to `E2ETestRunner` in `scripts/e2e_test.py`:

```python
def test_new_feature_integration(self):
    """Test new feature integration"""
    # Test implementation
    pass
```

### GitHub Actions

Update workflow files in `.github/workflows/` to include new test steps.

## 📚 Additional Resources

- [pytest Documentation](https://docs.pytest.org/)
- [Coverage.py Documentation](https://coverage.readthedocs.io/)
- [GitHub Actions Documentation](https://docs.github.com/en/actions)
- [Ollama Documentation](https://ollama.ai/docs)

## 🤝 Contributing Tests

When contributing to Sentries:

1. **Write tests for new features**
2. **Ensure existing tests pass**
3. **Add integration tests for complex workflows**
4. **Update this testing guide as needed**
5. **Verify GitHub Actions pass before merging**

---

**Remember**: Comprehensive testing ensures Sentries work reliably when deployed to other repositories. Always run the full test suite before releasing new versions.
