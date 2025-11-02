# 🚀 Quick Start Guide for Sentries

## Install Sentries in Your Repository

### **Option 1: Install from GitHub (Recommended for Testing)**

```bash
# Install directly from the repository
pip install git+https://github.com/kofort9/sentries.git

# Or install with test dependencies
pip install git+https://github.com/kofort9/sentries.git[test]

# Or install with all dependencies
pip install git+https://github.com/kofort9/sentries.git[all]
```

### **Option 2: Add to Your Project Dependencies**

Add to your `pyproject.toml`:

```toml
[project.dependencies]
sentries = {git = "https://github.com/kofort9/sentries.git"}

# Or with specific extras
sentries = {git = "https://github.com/kofort9/sentries.git", extras = ["test"]}
```

Or add to your `requirements.txt`:

```txt
git+https://github.com/kofort9/sentries.git
```

## 🎯 **Quick Setup**

### **1. Install Sentries**
```bash
pip install git+https://github.com/kofort9/sentries.git
```

### **2. Verify Installation**
```bash
# Check if CLI tools are available
testsentry --help
testsentry-camel --help
docsentry --help

# Check if package can be imported
python -c "import sentries; print('✅ Sentries installed successfully!')"
```

### **3. Set Up GitHub Actions**

Copy the workflow file to your `.github/workflows/` directory:

- **`.github/workflows/test-sentries.yml`** - Comprehensive CI/CD workflow with test maintenance

### **4. Configure Self-Hosted Runner**

You'll need a self-hosted GitHub Actions runner with:
- **Ollama** running locally
- **Required models** installed:
  - `llama3.1:8b-instruct-q4_K_M` (planner)
  - `deepseek-coder:6.7b-instruct-q5_K_M` (patcher)

### **5. Set Repository Variables**

In your repository settings, add these variables:
- `MODEL_PLAN`: `llama3.1:8b-instruct-q4_K_M`
- `MODEL_PATCH`: `deepseek-coder:6.7b-instruct-q5_K_M`

## 🔧 **Usage Examples**

### **Run TestSentry Manually**
```bash
# Analyze and fix failing tests
testsentry

# Or with custom environment
LLM_BASE=http://127.0.0.1:11434 \
MODEL_PLAN=llama3.1:8b-instruct-q4_K_M \
MODEL_PATCH=deepseek-coder:6.7b-instruct-q5_K_M \
GITHUB_TOKEN=your_token \
testsentry
```

### **Run DocSentry Manually**
```bash
# Update documentation
docsentry

# Or with custom environment
LLM_BASE=http://127.0.0.1:11434 \
MODEL_PLAN=llama3.1:8b-instruct-q4_K_M \
MODEL_PATCH=deepseek-coder:6.7b-instruct-q5_K_M \
GITHUB_TOKEN=your_token \
docsentry
```

## 📋 **What Sentries Do**

### **TestSentry**
- 🔍 **Analyzes** failing tests
- 🛠️ **Generates** fixes using LLM
- 📝 **Creates** patches and PRs
- 🏷️ **Labels** PRs appropriately
- 🎭 **Two implementations**: Original (`testsentry`) and CAMEL-based (`testsentry-camel`)

### **DocSentry**
- 📚 **Identifies** outdated documentation (planned but not yet implemented)
- ✍️ **Updates** docstrings and READMEs
- 🔄 **Creates** documentation PRs
- 🎯 **Focuses** on code-related docs

## 🚨 **Requirements**

- **Python 3.10+**
- **Git repository** with GitHub integration
- **Self-hosted GitHub Actions runner**
- **Ollama** with required models
- **GitHub token** with repo access

## 🔗 **More Information**

- **Full Documentation**: See `README.md`
- **Workflow Examples**: Check `.github/workflows/`
- **Configuration**: Review `WORKFLOW_ENHANCEMENTS.md`
- **Issues**: Report problems on GitHub

## 🎉 **That's It!**

Once set up, Sentries will automatically:
- **Monitor** your PRs for code changes
- **Run** when meaningful modifications are detected
- **Create** improvements for tests and documentation
- **Maintain** code quality automatically

Your repository will have AI-powered test and documentation maintenance! 🤖✨

## 🚀 **Advanced Configuration**

### **Custom Models**
You can use different LLM models by setting:
```bash
export MODEL_PLAN="your-planner-model"
export MODEL_PATCH="your-patch-model"
```

### **Custom LLM Endpoints**
Point to different Ollama instances:
```bash
export LLM_BASE="http://your-ollama-host:11434"
```

### **GitHub Enterprise**
For GitHub Enterprise, set:
```bash
export GITHUB_API_URL="https://your-github-enterprise.com/api/v3"
```

## 🔧 **Troubleshooting**

### **Common Issues**

1. **"Command not found"**: Make sure you installed with `[all]` extras
2. **"Ollama connection failed"**: Check if Ollama is running and accessible
3. **"GitHub token invalid"**: Verify your token has the right permissions
4. **"No models found"**: Install required models in Ollama

### **Getting Help**

- Check the [GitHub Issues](https://github.com/kofort9/sentries/issues)
- Review the [workflow logs](https://github.com/kofort9/sentries/actions)
- Ensure your [self-hosted runner](https://docs.github.com/en/actions/hosting-your-own-runners) is configured correctly
