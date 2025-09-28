# Sentries

```
╔────────────────────────────────────────────╗
│  _________              __                 │
│ /   _____/ ____   _____/  |________ ___.__.│
│ \_____  \_/ __ \ /    \   __\_  __ <   |  |│
│ /        \  ___/|   |  \  |  |  | \/\___  |│
│/_______  /\___  >___|  /__|  |__|   / ____││
│        \/     \/     \/             \/     │
╚────────────────────────────────────────────╝
```

**⚠️ PROJECT STATUS: POC COMPLETE - TABLED ⚠️**

This project has been **tabled** due to resource limitations. It serves as a **proof-of-concept** demonstrating the technical feasibility of using local LLMs for automated test maintenance.

**Current Status**: 
- ✅ **TestSentry**: Basic functionality works for simple test failures
- ❌ **DocSentry**: Never fully implemented
- 🟡 **Overall**: POC complete, not suitable for production use

**Why Tabled**: Resource limitations and complexity constraints make further development not worth pursuing at this time.

---

## 🎯 What This POC Demonstrated

**Automated test maintenance via local LLMs** - Successfully proved that:

1. **Local LLMs can fix simple test failures** (assertion mismatches, basic imports)
2. **Patch engine approach works** (JSON find/replace → unified diffs)
3. **Git integration is solid** (automated PR creation and branch management)
4. **Safety guardrails are effective** (path restrictions, size limits, validation)

## 🚀 Quick Start (For POC Evaluation)

### Prerequisites

- **Python**: 3.10+ (3.11+ recommended)
- **Ollama**: Latest version with required models
- **System**: macOS/Linux with 8GB+ RAM, 10GB+ free disk space
- **Git**: Repository with GitHub integration

### Installation

```bash
# Clone and install
git clone <your-repo>
cd sentries
pip install -e .

# Set environment variables
export LLM_BASE=http://127.0.0.1:11434
export MODEL_PLAN=llama3.1:8b-instruct-q4_K_M
export MODEL_PATCH=deepseek-coder:6.7b-instruct-q5_K_M

# Test basic functionality
testsentry --help
```

### What Works (Simple Cases)

```bash
# Fix basic failing tests (simple assertions, basic imports)
testsentry

# Check status
sentries-status

# Clean up artifacts
sentries-cleanup --dry-run
```

### What Doesn't Work

- ❌ **DocSentry**: Never implemented
- ❌ **Complex test failures**: Fixtures, complex dependencies, type issues
- ❌ **Advanced scenarios**: Multi-file dependencies, integration problems

## 🏗️ Architecture (POC Implementation)

### Core Components

- **`sentries/patch_engine.py`**: ✅ **Working** - Converts JSON operations to unified diffs
- **`sentries/intelligent_analysis.py`**: ✅ **Working** - Test failure classification
- **`sentries/git_utils.py`**: ✅ **Working** - Git operations and PR management
- **`sentries/testsentry.py`**: 🟡 **Partially Working** - Basic test fixes only
- **`sentries/docsentry.py`**: ❌ **Not Working** - Never implemented
- **`sentries/chat.py`**: ✅ **Working** - LLM communication layer

### Two-Model Approach

1. **Planner Model** (`MODEL_PLAN`): Analyzes context and creates numbered plans
2. **Patcher Model** (`MODEL_PATCH`): Generates unified diffs based on plans

### Safety Features

- **Path Allowlists**: Only modify files under allowed paths (`tests/`)
- **Size Limits**: Enforce caps on files changed (≤5) and lines modified (≤200)
- **Diff Validation**: Verify unified diff format and content
- **Re-testing**: Verify fixes work before creating PRs

## 🔧 Configuration

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `LLM_BASE` | `http://127.0.0.1:11434` | Ollama API endpoint |
| `MODEL_PLAN` | `llama3.1:8b-instruct-q4_K_M` | Planning model name |
| `MODEL_PATCH` | `deepseek-coder:6.7b-instruct-q5_K_M` | Patching model name |
| `GITHUB_TOKEN` | Required | GitHub API token |
| `GITHUB_REPOSITORY` | Required | Repository name (org/repo) |

## 🤖 LLM Models & Requirements

### **Model Recommendations**

#### **Planner Models (Analysis & Planning)**
| Model | Size | Quality | Speed | Use Case |
|-------|------|---------|-------|----------|
| `llama3.1:8b-instruct-q4_K_M` | 4.7GB | 🥈 High | 🚀 Fast | **Recommended** - balanced performance |
| `llama3.1:8b-instruct-q8_0` | 8.5GB | 🥇 Highest | 🐌 Slow | Best reasoning, complex analysis |
| `llama3.1:8b-instruct-q2_K` | 2.9GB | 🥉 Medium | ⚡ Fastest | Quick planning, limited reasoning |

#### **Patcher Models (Code Generation)**
| Model | Size | Quality | Speed | Use Case |
|-------|------|---------|-------|----------|
| `deepseek-coder:6.7b-instruct-q5_K_M` | 4.2GB | 🥈 High | 🚀 Fast | **Recommended** - balanced performance |
| `deepseek-coder:6.7b-instruct-q8_0` | 6.7GB | 🥇 Highest | 🐌 Slow | Best code quality, complex patches |
| `deepseek-coder:6.7b-instruct-q2_K` | 2.7GB | 🥉 Medium | ⚡ Fastest | Quick patches, limited quality |

### **Storage Requirements**

- **Minimum Setup**: ~9GB (planner + patcher)
- **Recommended Free Space**: 15GB+ (models + safety margin)
- **Model Storage**: `~/.ollama/models/` directory

## 📋 TestSentry (POC Status: Partially Working)

**Capabilities**: Automatically fixes **simple** failing tests by:
1. Running `pytest` to discover failures
2. Planning minimal test-only changes
3. Generating and applying patches
4. Re-testing to verify fixes
5. Creating PRs with test fixes

**What Works**:
- ✅ Simple assertion failures (`assert 1 == 2` → `assert 1 == 1`)
- ✅ Basic import issues
- ✅ Test file modifications in `tests/` directory

**What Doesn't Work**:
- ❌ Complex test failures (fixtures, dependencies)
- ❌ Integration problems
- ❌ Advanced pytest scenarios

**Allowlist**: `tests/`  
**Limits**: ≤5 files, ≤200 lines changed

## 📚 DocSentry (POC Status: Not Implemented)

**Status**: ❌ **Never implemented or tested**

**Intended Purpose**: Keep documentation synchronized by:
1. Analyzing PR changes and metadata
2. Planning minimal documentation updates
3. Generating documentation patches
4. Creating PRs with doc updates

**Reality**: Basic structure exists but no working functionality.

## 🔒 Security & Guardrails

### Path Restrictions
- TestSentry: Only modifies files under `tests/`
- Hard-coded allowlists prevent unauthorized changes

### Size Limits
- Enforced at diff validation time
- Rejects patches that exceed configured caps
- Prevents large, unmanageable changes

### Validation
- Unified diff format validation
- Path allowlist enforcement
- Size limit checking
- Re-testing after patch application

## 🚀 GitHub Actions Integration

### Self-Hosted Runner Setup

**Required**: Self-hosted runners for LLM operations (models cannot run on GitHub-hosted runners)

1. **Install Ollama on Runner**
   ```bash
   # On macOS
   brew install ollama
   
   # On Linux
   curl -fsSL https://ollama.ai/install.sh | sh
   ```

2. **Install Required Models**
   ```bash
   ollama pull llama3.1:8b-instruct-q4_K_M
   ollama pull deepseek-coder:6.7b-instruct-q5_K_M
   ```

3. **Configure Repository Secrets**
   - `GITHUB_TOKEN`: Personal access token
   - `MODEL_PLAN`: Planner model name (optional)
   - `MODEL_PATCH`: Patcher model name (optional)

### Workflow Files

- `.github/workflows/test-sentries.yml`: Comprehensive CI/CD workflow
- Includes linting, testing, and LLM operations

## 🧪 Testing

### Current Test Status
- **Total Tests**: 28
- **Passing**: 26
- **Failing**: 2 (intentional failures for testing)
- **Coverage**: 18% (low due to untested modules)

### Smoke Test

```bash
python scripts/smoke.py
```

Verifies:
- Ollama connectivity
- Model availability
- Basic model response capability

## 📊 Output & Labeling

### Exit Codes
- `0`: Success (PR created or no-op)
- `1`: Failure (error occurred)

### PR Labels
- `tests-sentry:done`: Test fixes completed successfully
- `tests-sentry:noop`: No test fixes needed

## 🛠️ Development

### Project Structure

```
sentries/
├── pyproject.toml              # Dependencies and console scripts
├── README.md                   # This documentation
├── PROJECT_STATUS_AUDIT.md     # Detailed project status
├── .gitignore                  # Python and project-specific ignores
├── sentries/                   # Core package
│   ├── __init__.py            # Package initialization
│   ├── banner.py              # Centralized ASCII art banner
│   ├── chat.py                # LLM communication (Ollama + OpenAI-style)
│   ├── prompts.py             # System prompts for planner/patcher models
│   ├── diff_utils.py          # Diff validation and application
│   ├── git_utils.py           # Git operations and PR management
│   ├── runner_common.py       # Shared utilities and constants
│   ├── testsentry.py          # TestSentry CLI (test fixes)
│   ├── docsentry.py           # DocSentry CLI (doc updates) - NOT WORKING
│   ├── intelligent_analysis.py # Smart test failure analysis
│   ├── patch_engine.py        # Patch generation engine
│   └── smart_prompts.py       # Experimental prompts - NOT INTEGRATED
├── scripts/                    # Standalone utilities
│   ├── setup_sentries.py      # Automated setup and configuration
│   ├── update_models.py       # LLM model management
│   └── smoke.py               # Health check and connectivity test
└── .github/workflows/          # GitHub Actions integration
    └── test-sentries.yml      # Comprehensive CI/CD workflow
```

## 🏷️ Artifact Tagging & Cleanup

### **Automatic Tagging**
The sentries automatically tag all created artifacts for easy identification:

#### **Branch Tagging**
- **Naming Convention**: `ai-test-fixes/<sha>-<timestamp>`
- **Metadata Files**: Each branch contains `.sentries-metadata.json` with creation details

#### **PR Tagging**
- **Labels**: Automatic labels like `ai-generated`, `sentries`, `sentry-testsentry`
- **Metadata**: PR descriptions include sentries metadata section

### **Cleanup Utilities**

```bash
# Show all sentries artifacts
sentries-status

# See what would be cleaned up (dry run)
sentries-cleanup --dry-run

# Clean up everything
sentries-cleanup --force

# Clean up artifacts older than 7 days
sentries-cleanup --max-age-days 7
```

## 🆘 Troubleshooting

### Common Issues

**Ollama Connection Failed**
```bash
# Check if Ollama is running
curl http://127.0.0.1:11434/api/tags

# Start Ollama if needed
ollama serve
```

**Model Not Found**
```bash
# List available models
ollama list

# Pull required models
ollama pull llama3.1:8b-instruct-q4_K_M
ollama pull deepseek-coder:6.7b-instruct-q5_K_M
```

**GitHub Token Issues**
- Ensure `GITHUB_TOKEN` has appropriate permissions
- Check repository access and secrets configuration

## 📝 Project Status & Future

### **Current State**
This project is a **successful POC** that demonstrates:
- Local LLMs can fix simple test failures
- Patch engine architecture is sound
- Git integration is production-ready
- Safety mechanisms work effectively

### **Why Tabled**
- Resource limitations (computational, maintenance overhead)
- Complex test scenarios require human intervention
- Limited ROI for the complexity involved
- Better alternatives exist for production use

### **Future Possibilities**
- Revisit when local LLM technology improves significantly
- Apply learned patterns to other AI-assisted development tools
- Use as reference for similar projects
- Extract working components for other use cases

### **Recommendation**
**Archive this POC** and revisit when:
1. Local LLM technology improves significantly
2. Resource constraints are reduced
3. Specific use cases emerge that match current capabilities
4. Better models become available for complex scenarios

---

## 📄 License

MIT License

## 🤝 Contributing

**Note**: This project is currently tabled and not accepting contributions. The codebase is preserved for future reference and potential revival.

---

**⚠️ IMPORTANT**: This is a **proof-of-concept** that has been **tabled**. It demonstrates technical feasibility but is **not suitable for production use**. Use at your own risk and only for evaluation purposes.

## 🔄 **Three-Mode LLM System**

Sentries now supports **three different LLM modes** to accommodate different use cases and constraints:

### **Mode 1: 🎭 Simulation Mode (Free, Public Repo Compatible)**
- **Cost**: $0 (completely free)
- **Requirements**: Public repository + GitHub Actions
- **Use Case**: Demonstration, CI/CD, public repositories
- **Setup**: Automatic (no additional setup needed)
- **Results**: Deterministic mock responses that simulate real LLM behavior

```bash
# Enable simulation mode
export SENTRIES_SIMULATION_MODE=true
python -m sentries.testsentry
```

### **Mode 2: 🤖 Local LLM Mode (Free, Private Repo Required)**
- **Cost**: $0 (uses local Ollama)
- **Requirements**: Private repository + self-hosted runner + Ollama
- **Use Case**: Real LLM testing, private development
- **Setup**: Install Ollama + set up self-hosted runner
- **Results**: Real LLM responses using local models

```bash
# Install Ollama and models
ollama pull llama3.1
ollama pull deepseek-coder

# Run with local LLM
python -m sentries.testsentry
```

### **Mode 3: ☁️ API Mode (Paid, Public Repo Compatible)**
- **Cost**: Pay per API call (OpenAI/Anthropic/Groq pricing)
- **Requirements**: API key + public/private repository
- **Use Case**: Production use, advanced LLM capabilities
- **Setup**: Get API key + set environment variable
- **Results**: Real LLM responses using cloud APIs

```bash
# Set up API key (choose one)
export GROQ_API_KEY="your-groq-key"        # Free tier available
export OPENAI_API_KEY="your-openai-key"    # Paid
export ANTHROPIC_API_KEY="your-anthropic-key"  # Paid

# Run with API
python -m sentries.testsentry
```

## 🔧 **Configuration**

### **Environment Variables**

| Variable | Description | Default | Mode |
|----------|-------------|---------|------|
| `SENTRIES_SIMULATION_MODE` | Force simulation mode | `false` | Simulation |
| `CI` | Auto-enable simulation in CI | `false` | Simulation |
| `GROQ_API_KEY` | Groq API key (free tier) | `None` | API |
| `OPENAI_API_KEY` | OpenAI API key | `None` | API |
| `ANTHROPIC_API_KEY` | Anthropic API key | `None` | API |
| `LLM_BASE` | Ollama server URL | `http://localhost:11434` | Local LLM |

### **Model Configuration**

```python
# For API mode
MODEL_PLAN = "gpt-4"                    # OpenAI
MODEL_PLAN = "claude-3-sonnet"          # Anthropic  
MODEL_PLAN = "llama3-8b-8192"           # Groq (free tier)

# For local mode
MODEL_PLAN = "llama3.1"                 # Ollama
MODEL_PATCH = "deepseek-coder"          # Ollama
```

## 🚀 **Quick Start Examples**

### **For Public Repository (Simulation)**
```bash
git clone https://github.com/kofort9/sentry.git
cd sentries
pip install -e .
export SENTRIES_SIMULATION_MODE=true
python -m sentries.testsentry
```

### **For Private Repository (Local LLM)**
```bash
git clone <your-private-repo>
cd sentries
pip install -e .
ollama pull llama3.1
ollama pull deepseek-coder
python -m sentries.testsentry
```

### **For API Usage (Any Repository)**
```bash
git clone https://github.com/kofort9/sentry.git
cd sentries
pip install -e .
export GROQ_API_KEY="your-free-key"  # Get from https://console.groq.com
python -m sentries.testsentry
```

## 💡 **Why Three Modes?**

- **Simulation Mode**: Perfect for public repositories, CI/CD, and demonstrations
- **Local LLM Mode**: Free real testing, but requires private repository due to GitHub's security policy
- **API Mode**: Most flexible, works anywhere, supports free (Groq) and paid options

**Mode Priority**: Simulation > API > Local LLM (automatic detection)

## 🧪 **Testing**

Run the comprehensive test suite:

```bash
# Test all three modes
pytest tests/test_chat_modes.py -v

# Test pipeline integration
pytest tests/test_pipeline_integration.py -v

# Test CI integration
pytest tests/test_ci_integration.py -v

# Test specific mode
pytest tests/test_chat_modes.py::TestSimulationMode -v
```

## 🔄 **Mode Detection Logic**

The system automatically detects which mode to use:

1. **Simulation Mode** (highest priority)
   - `SENTRIES_SIMULATION_MODE=true` OR
   - `CI=true` (GitHub Actions, etc.)

2. **API Mode** (second priority)
   - Any of: `GROQ_API_KEY`, `OPENAI_API_KEY`, `ANTHROPIC_API_KEY` set

3. **Local LLM Mode** (fallback)
   - No simulation mode, no API keys
   - Requires Ollama running locally

## 🛠️ **Troubleshooting**

### **Common Issues**

#### **"Stuck waiting for self-hosted runner"**
- **Problem**: GitHub Actions waiting for self-hosted runner
- **Solution**: Remove `test-llm` label/tag from PR, or use simulation mode
- **Why**: Public repos can't use self-hosted runners for security reasons

#### **"API key not working"**
- **Problem**: API calls failing
- **Solution**: Check API key format and permissions
- **Groq**: Get free key at https://console.groq.com
- **OpenAI**: Requires paid account
- **Anthropic**: Requires paid account

#### **"Ollama connection failed"**
- **Problem**: Can't connect to local Ollama
- **Solution**: 
  ```bash
  # Start Ollama
  ollama serve
  
  # Pull required models
  ollama pull llama3.1
  ollama pull deepseek-coder
  ```

#### **"Simulation responses not realistic"**
- **Problem**: Mock responses too simple
- **Solution**: This is expected - simulation mode provides basic responses for testing
- **Alternative**: Use API mode for better responses

### **Environment Debugging**

```bash
# Check which mode will be used
python -c "
from sentries.chat import is_simulation_mode, has_api_key
print(f'Simulation mode: {is_simulation_mode()}')
print(f'API key available: {has_api_key()}')
print('Mode priority: Simulation > API > Local LLM')
"
```

### **Performance Expectations**

| Mode | Response Time | Cost | Quality |
|------|---------------|------|---------|
| Simulation | <0.1s | Free | Basic |
| API (Groq) | 1-3s | Free tier | Good |
| API (OpenAI/Anthropic) | 1-5s | Paid | Excellent |
| Local LLM | 5-30s | Free | Good |

## 📋 **GitHub Actions Integration**

### **Automatic Simulation Mode**
- Public repositories automatically use simulation mode in CI
- No setup required - works out of the box
- Deterministic results for consistent testing

### **Optional LLM Testing**
Add to PR title, body, or labels to enable LLM tests:
- `[test-llm]` in title or body
- `test-llm` label on PR
- Manual workflow trigger with `run_llm_tests=true`

**Note**: LLM tests require self-hosted runner (private repos only)

### **Workflow Configuration**
```yaml
# .github/workflows/test-sentries.yml
- name: Test with Simulation Mode
  env:
    SENTRIES_SIMULATION_MODE: true
  run: |
    python -m sentries.testsentry
```

## 🔐 **Security Considerations**

### **API Keys**
- Store as GitHub Secrets, never in code
- Use environment variables only
- Groq offers free tier for testing

### **Self-Hosted Runners**
- Only work with private repositories
- Public repos use GitHub-hosted runners + simulation mode
- This is a GitHub security policy, not a limitation of Sentries

### **Data Privacy**
- Simulation mode: No data sent anywhere
- API mode: Data sent to API provider
- Local LLM mode: All processing local

## 📊 **Observability Features**

The system includes comprehensive observability:
- **Real-time metrics** collection during LLM operations
- **PII detection** and masking for privacy
- **Tokenization analysis** and drift detection
- **Deterministic reports** generated in CI
- **Interactive dashboard** (optional Streamlit app)

See the observability documentation for details on metrics and monitoring.
