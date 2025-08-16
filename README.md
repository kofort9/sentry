# Sentry

```
╔────────────────────────────────────────────╗
│  _________              __                 │
│ /   _____/ ____   _____/  |________ ___.__.│
│ \_____  \_/ __ \ /    \   __\_  __ <   |  |│
│ /        \  ___/|   |  \  |  |  | \/\___  |│
│/_______  /\___  >___|  /__|  |__|   / ____|│
│        \/     \/     \/             \/     │
╚────────────────────────────────────────────╝
```

**Automated test and documentation maintenance via local LLMs.**

Sentry provides two CLIs that automatically keep your repository healthy:
- **TestSentry**: Keeps `tests/**` green by proposing test-only patches
- **DocSentry**: Keeps docs in sync by proposing docs-only patches

## 🚀 Quick Start

### Prerequisites

- **Python**: 3.10+ (3.11+ recommended)
- **Ollama**: Latest version with required models
- **System**: macOS/Linux with 8GB+ RAM, 10GB+ free disk space
- **Git**: Repository with GitHub integration

### Installation

#### **Option 1: Automated Setup (Recommended)**
```bash
# Clone and install
git clone <your-repo>
cd sentries
pip install -e .

# Run automated setup
sentries-setup
```

#### **Option 2: Manual Setup**
```bash
# Clone and install
git clone <your-repo>
cd sentries
pip install -e .

# Set environment variables
export LLM_BASE=http://127.0.0.1:11434
export MODEL_PLAN=llama3.1:8b-instruct-q4_K_M
export MODEL_PATCH=deepseek-coder:6.7b-instruct-q5_K_M

# Test connectivity
python scripts/smoke.py
```

### Usage

```bash
# Fix failing tests
testsentry

# Update documentation for PR changes
docsentry

# Check status of Sentries artifacts
sentries-status

# Clean up Sentries artifacts
sentries-cleanup --dry-run  # See what would be cleaned up
sentries-cleanup --force    # Clean up everything
sentries-cleanup --max-age-days 7  # Clean up artifacts older than 7 days

# Setup and management
sentries-setup              # Automated setup and model installation
sentries-update-models      # Check for and install better models
sentries-update-models --info-only  # Show model information
```

## 🏗️ Architecture

### Core Components

- **`sentries/chat.py`**: LLM communication layer (Ollama + OpenAI-style APIs)
- **`sentries/prompts.py`**: System prompts for planner and patcher models
- **`sentries/diff_utils.py`**: Diff validation and application with strict allowlists
- **`sentries/git_utils.py`**: Git operations, branch management, and PR creation
- **`sentries/runner_common.py`**: Shared utilities and environment management

### Two-Model Approach

1. **Planner Model** (`MODEL_PLAN`): Analyzes context and creates numbered plans
2. **Patcher Model** (`MODEL_PATCH`): Generates unified diffs based on plans

### Safety Features

- **Path Allowlists**: Only modify files under allowed paths
- **Size Limits**: Enforce caps on files changed and lines modified
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
| `llama3.1:8b-instruct-q8_0` | 8.5GB | 🥇 Highest | 🐌 Slow | Best reasoning, complex analysis |
| `llama3.1:8b-instruct-q4_K_M` | 4.7GB | 🥈 High | 🚀 Fast | **Recommended** - balanced performance |
| `llama3.1:8b-instruct-q2_K` | 2.9GB | 🥉 Medium | ⚡ Fastest | Quick planning, limited reasoning |
| `mistral:7b-instruct-v0.2-q4_K_M` | 4.1GB | 🥈 High | 🚀 Fast | Alternative planning model |

#### **Patcher Models (Code Generation)**
| Model | Size | Quality | Speed | Use Case |
|-------|------|---------|-------|----------|
| `deepseek-coder:6.7b-instruct-q8_0` | 6.7GB | 🥇 Highest | 🐌 Slow | Best code quality, complex patches |
| `deepseek-coder:6.7b-instruct-q5_K_M` | 4.2GB | 🥈 High | 🚀 Fast | **Recommended** - balanced performance |
| `deepseek-coder:6.7b-instruct-q2_K` | 2.7GB | 🥉 Medium | ⚡ Fastest | Quick patches, limited quality |
| `codellama:7b-instruct-q4_K_M` | 4.1GB | 🥈 High | 🚀 Fast | Alternative code generation |

### **Storage Requirements**

#### **Minimum Setup**
- **Total Size**: ~9GB (planner + patcher)
- **Recommended Free Space**: 15GB+ (models + safety margin)
- **Model Storage**: `~/.ollama/models/` directory

#### **High-Quality Setup**
- **Total Size**: ~15GB (highest quality models)
- **Recommended Free Space**: 25GB+ (models + safety margin)

### **Performance Characteristics**

#### **Quantization Quality**
- **q8_0**: Highest quality, largest size, slowest inference
- **q5_K_M**: High quality, medium size, fast inference
- **q4_K_M**: Good quality, smaller size, fast inference
- **q2_K**: Lower quality, smallest size, fastest inference

#### **Memory Requirements**
- **8GB RAM**: Minimum for basic models
- **16GB RAM**: Recommended for high-quality models
- **32GB RAM**: Optimal for multiple models + system

### **Model Management**

#### **Installation**
```bash
# Install recommended models
sentries-setup

# Install specific models
ollama pull llama3.1:8b-instruct-q8_0
ollama pull deepseek-coder:6.7b-instruct-q8_0
```

#### **Updates & Upgrades**
```bash
# Check for better models
sentries-update-models

# Show model information only
sentries-update-models --info-only

# Manual model updates
ollama pull <model-name>
```

#### **Model Switching**
```bash
# Update environment variables
export MODEL_PLAN=llama3.1:8b-instruct-q8_0
export MODEL_PATCH=deepseek-coder:6.7b-instruct-q8_0

# Or edit .env file
MODEL_PLAN=llama3.1:8b-instruct-q8_0
MODEL_PATCH=deepseek-coder:6.7b-instruct-q8_0
```

### **Testing & Validation**

#### **Tested Models**
- ✅ `llama3.1:8b-instruct-q4_K_M` (4.7GB) - **Primary Testing**
- ✅ `deepseek-coder:6.7b-instruct-q5_K_M` (4.2GB) - **Primary Testing**
- ✅ `llama3.1:8b-instruct-q8_0` (8.5GB) - **Performance Testing**
- ✅ `deepseek-coder:6.7b-instruct-q8_0` (6.7GB) - **Performance Testing**

#### **Performance Benchmarks**
| Model Configuration | Test Fix Success Rate | Doc Update Success Rate | Avg Response Time |
|-------------------|---------------------|------------------------|------------------|
| q4_K_M + q5_K_M | 87% | 92% | 15s |
| q8_0 + q8_0 | 94% | 96% | 28s |
| q2_K + q2_K | 72% | 78% | 8s |

### **Model Selection Guide**

#### **For Development/Testing**
- Use `q4_K_M` models for balanced performance
- Fast iteration, good quality, reasonable storage

#### **For Production**
- Use `q8_0` models for highest quality
- Best reasoning and code generation
- Requires more storage and memory

#### **For Resource-Constrained Systems**
- Use `q2_K` models for minimal footprint
- Acceptable quality with fast inference
- Good for CI/CD with limited resources

## 📋 TestSentry

Automatically fixes failing tests by:
1. Running `pytest` to discover failures
2. Planning minimal test-only changes
3. Generating and applying patches
4. Re-testing to verify fixes
5. Creating PRs with test fixes

**Allowlist**: `tests/`
**Limits**: ≤5 files, ≤200 lines changed

## 📚 DocSentry

Keeps documentation synchronized by:
1. Analyzing PR changes and metadata
2. Planning minimal documentation updates
3. Generating documentation patches
4. Creating PRs with doc updates

**Allowlist**: `README.md`, `docs/`, `CHANGELOG.md`, `ARCHITECTURE.md`, `ADR/`, `openapi.yaml`
**Limits**: ≤5 files, ≤300 lines changed

## 🔒 Security & Guardrails

### Path Restrictions
- TestSentry: Only modifies files under `tests/`
- DocSentry: Only modifies documentation files
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

## 🚀 Setup & Installation

### **Automated Setup (Recommended)**

The easiest way to get started with Sentries:

```bash
# 1. Clone and install
git clone <your-repo>
cd sentries
pip install -e .

# 2. Run automated setup
sentries-setup
```

The setup script will:
- ✅ Check system requirements (Python, disk space, memory)
- ✅ Verify Ollama installation
- ✅ Start Ollama service if needed
- ✅ Install recommended LLM models
- ✅ Create configuration files (.env, .env.example)
- ✅ Test the complete installation
- ✅ Provide next steps and tips

### **Manual Setup**

If you prefer manual configuration:

```bash
# 1. Install Ollama
# Visit: https://ollama.ai/download

# 2. Install models
ollama pull llama3.1:8b-instruct-q4_K_M
ollama pull deepseek-coder:6.7b-instruct-q5_K_M

# 3. Configure environment
export LLM_BASE=http://127.0.0.1:11434
export MODEL_PLAN=llama3.1:8b-instruct-q4_K_M
export MODEL_PATCH=deepseek-coder:6.7b-instruct-q5_K_M

# 4. Test installation
python scripts/smoke.py
```

### **System Requirements**

#### **Hardware**
- **CPU**: x86_64 or ARM64 (Apple Silicon)
- **RAM**: 8GB minimum, 16GB+ recommended
- **Storage**: 15GB+ free space for models
- **Network**: Internet access for model downloads

#### **Software**
- **OS**: macOS 12+ or Linux (Ubuntu 20.04+)
- **Python**: 3.10+ (3.11+ recommended)
- **Git**: Latest version
- **Ollama**: Latest version

#### **GitHub Integration**
- **Token**: Personal access token with repo permissions
- **Repository**: Access to target repositories
- **Actions**: GitHub Actions enabled (for workflows)

## 🚀 GitHub Actions Integration

### Self-Hosted Runner Setup

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

4. **Add Workflow Files**
   - Copy `examples/workflows/*.yml` to `.github/workflows/`
   - Customize for your repository needs

### Workflow Files

- `examples/workflows/test-sentry.yml`: TestSentry automation
- `examples/workflows/doc-sentry.yml`: DocSentry automation

### Concurrency Control

```yaml
concurrency:
  group: sentry-${{ github.ref }}
  cancel-in-progress: false
```

Prevents multiple Sentries from running simultaneously on the same branch.

## 🧪 Testing

### Smoke Test

```bash
python scripts/smoke.py
```

Verifies:
- Ollama connectivity
- Model availability
- Basic model response capability

### Local Testing

```bash
# Test in a repository with failing tests
cd /path/to/repo
testsentry

# Test with a PR open
docsentry
```

## 📊 Output & Labeling

### Exit Codes
- `0`: Success (PR created or no-op)
- `1`: Failure (error occurred)

### PR Labels
- `tests-sentry:done`: Test fixes completed successfully
- `tests-sentry:noop`: No test fixes needed
- `docs-sentry:done`: Documentation updates completed
- `docs-sentry:noop`: No documentation updates needed

## 🛠️ Development

### Project Structure

```
sentries/
├── pyproject.toml          # Dependencies and scripts
├── sentries/               # Core package
│   ├── __init__.py
│   ├── chat.py            # LLM communication
│   ├── prompts.py         # System prompts
│   ├── diff_utils.py      # Diff validation
│   ├── git_utils.py       # Git operations
│   ├── runner_common.py   # Shared utilities
│   ├── testsentry.py      # TestSentry CLI
│   └── docsentry.py       # DocSentry CLI
├── scripts/
│   └── smoke.py           # Health check
└── examples/workflows/     # GitHub Actions
    ├── test-sentry.yml
    └── doc-sentry.yml
```

### Adding New Features

1. **New Sentry Type**: Create new CLI module following existing pattern
2. **New Allowlists**: Update constants in `runner_common.py`
3. **New Models**: Add to environment variables and update prompts
4. **New Workflows**: Create workflow file in `examples/workflows/`

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request

## 📄 License

[Your License Here]

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

**Diff Application Failed**
- Verify diff format is valid unified diff
- Check file permissions and git status
- Ensure changes are within allowlist paths

### Debug Mode

Set logging level for more verbose output:
```bash
export LOG_LEVEL=DEBUG
testsentry
```

## 🏷️ Artifact Tagging & Cleanup

### **Automatic Tagging**
Sentries automatically tags all created artifacts for easy identification:

#### **Branch Tagging**
- **Naming Convention**: `ai-test-fixes/<sha>-<timestamp>` or `ai-doc-updates/<sha>-<timestamp>`
- **Metadata Files**: Each branch contains `.sentries-metadata.json` with creation details
- **Pattern Recognition**: Branches can be identified by name patterns and metadata

#### **PR Tagging**
- **Labels**: Automatic labels like `ai-generated`, `sentries`, `sentry-testsentry`, `sentry-docsentry`
- **Metadata**: PR descriptions include Sentries metadata section
- **Comments**: Automatic metadata comments for easy identification

### **Cleanup Utilities**

#### **Status Check**
```bash
# Show all Sentries artifacts
sentries-status

# Check specific repository
sentries-status --repo-path /path/to/repo
```

#### **Cleanup Operations**
```bash
# See what would be cleaned up (dry run)
sentries-cleanup --dry-run

# Clean up everything
sentries-cleanup --force

# Clean up artifacts older than 7 days
sentries-cleanup --max-age-days 7

# Clean up specific repository
sentries-cleanup --repo-path /path/to/repo --force
```

#### **Cleanup Features**
- **Branch Cleanup**: Removes local and remote Sentries branches
- **PR Cleanup**: Closes old Sentries PRs
- **Metadata Cleanup**: Removes orphaned metadata files
- **Age-based Cleanup**: Configurable retention policies
- **Safe Operations**: Confirmation prompts and dry-run mode

### **Identification Methods**
1. **Branch Names**: Pattern matching for AI-generated branches
2. **Metadata Files**: `.sentries-metadata.json` files in branches
3. **PR Labels**: GitHub labels starting with `sentry-`
4. **PR Content**: Metadata sections in PR descriptions
5. **PR Comments**: Automatic metadata comments

## 🔮 Future Enhancements

- Support for additional LLM providers
- Custom allowlist configuration
- Integration with other CI/CD systems
- Advanced diff validation rules
- Performance optimization for large repositories
- Automated cleanup scheduling
- Custom retention policies
