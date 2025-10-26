# Contributing to Sentries

## Development Setup

### Prerequisites
- Python 3.10+ (3.11+ recommended)
- Ollama (for local LLM testing)
- Git with GitHub access

### Initial Setup
```bash
# Clone and install
git clone <your-repo>
cd sentries
make setup

# Install pre-commit hooks
pre-commit install
```

### Development Workflow

1. **Create feature branch**
   ```bash
   git checkout -b feature/your-feature-name
   ```

2. **Make changes and test**
   ```bash
   # Run linting
   make lint

   # Run tests
   make test

   # Test with local LLMs
   export SENTRIES_FORCE_LOCAL=true
   pytest tests/
   ```

3. **Submit PR**
   - Ensure all tests pass
   - Add documentation for new features
   - Follow conventional commit messages

### Code Standards

- **Formatting**: Black (line length 100)
- **Import sorting**: isort (black-compatible profile)
- **Linting**: Flake8 + MyPy
- **Testing**: pytest with coverage reporting

### Project Structure

```
sentries/
├── docs/                    # Documentation
│   ├── architecture/        # Framework and design docs
│   ├── dev/                 # Development guides
│   └── notes/               # Historical notes
├── sentries/                # Main package
│   ├── camel/               # CAMEL-based agents
│   └── framework/           # Reusable framework
├── tests/                   # Test suite
├── scripts/                 # Utility scripts
└── examples/                # Usage examples
```

### Testing Guidelines

- **Unit tests**: Test individual components
- **Integration tests**: Test agent workflows
- **Mock LLMs**: Use `MockLLMWrapper` for deterministic testing
- **Coverage**: Maintain >80% test coverage

### Debugging Tips

1. **Use simulation mode** for fast iteration:
   ```bash
   export SENTRIES_SIMULATION_MODE=true
   ```

2. **Force local LLMs** to avoid API costs:
   ```bash
   export SENTRIES_FORCE_LOCAL=true
   ```

3. **Enable debug logging**:
   ```bash
   export DEBUG=true
   export LOG_LEVEL=DEBUG
   ```

### Common Tasks

- **Add new agent**: Inherit from `BaseAgent`, implement `process()`
- **Add new tool**: Inherit from `BaseTool`, implement `execute()` and metadata
- **Create workflow**: Use `WorkflowBuilder` for multi-agent orchestration
- **Fix failing tests**: Use TestSentry CLI for automated fixes

### Getting Help

- Check existing issues and discussions
- Review documentation in `docs/`
- Ask questions in pull request comments
- For bugs, include reproduction steps and environment details

### Incident Response

If something breaks in production:

```bash
# Quick diagnostic
make incident

# Check system status
./scripts/check-runner-status.sh

# Review logs and metrics
streamlit run apps/camel_dashboard/app.py
```
