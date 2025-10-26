#!/bin/bash
# Diagnostic script to check self-hosted runner status

echo "🔍 Checking self-hosted runner status for TestSentry"
echo ""

# Check GitHub CLI authentication
echo "1️⃣  GitHub CLI Authentication:"
if gh auth status &> /dev/null; then
    echo "   ✅ Authenticated with GitHub CLI"
    USER=$(gh api user --jq '.login')
    echo "   👤 User: $USER"
else
    echo "   ❌ Not authenticated with GitHub CLI"
    echo "   🔧 Run: gh auth login"
    exit 1
fi

echo ""

# Check repository access
echo "2️⃣  Repository Access:"
if gh repo view kofort9/sentry &> /dev/null; then
    echo "   ✅ Can access kofort9/sentry repository"
else
    echo "   ❌ Cannot access kofort9/sentry repository"
    echo "   🔧 Check repository permissions"
    exit 1
fi

echo ""

# Check for self-hosted runners
echo "3️⃣  Self-Hosted Runners:"
RUNNERS=$(gh api repos/kofort9/sentry/actions/runners --jq '.total_count')
if [ "$RUNNERS" -gt 0 ]; then
    echo "   ✅ Found $RUNNERS self-hosted runner(s)"
    gh api repos/kofort9/sentry/actions/runners --jq '.runners[] | "   📋 \(.name) - \(.status) (\(.os))"'
else
    echo "   ❌ No self-hosted runners found"
    echo "   🔧 Run: ./scripts/setup-self-hosted-runner.sh"
fi

echo ""

# Check if Ollama is installed
echo "4️⃣  Ollama Installation:"
if command -v ollama &> /dev/null; then
    echo "   ✅ Ollama is installed"

    # Check if Ollama service is running
    if curl -sSf http://127.0.0.1:11434/api/tags >/dev/null 2>&1; then
        echo "   ✅ Ollama service is running"

        # Check available models
        MODELS=$(ollama list 2>/dev/null | wc -l)
        echo "   📋 Available models: $((MODELS - 1))"

        if [ "$MODELS" -gt 1 ]; then
            echo "   📝 Installed models:"
            ollama list | tail -n +2 | sed 's/^/      - /'
        else
            echo "   ⚠️  No models installed"
            echo "   🔧 Run: ollama pull llama3.1:8b-instruct-q4_K_M"
        fi
    else
        echo "   ❌ Ollama service is not running"
        echo "   🔧 Run: ollama serve"
    fi
else
    echo "   ❌ Ollama is not installed"
    echo "   🔧 Run: brew install ollama"
fi

echo ""

# Check system resources
echo "5️⃣  System Resources:"
echo "   💾 Memory: $(free -h | grep Mem | awk '{print $3 "/" $2}' 2>/dev/null || echo "N/A")"
echo "   💽 Disk: $(df -h / | tail -1 | awk '{print $3 "/" $2 " (" $5 " used)"}')"
echo "   🖥️  OS: $(uname -s) $(uname -m)"

echo ""

# Summary
echo "📊 Summary:"
if [ "$RUNNERS" -gt 0 ] && command -v ollama &> /dev/null && curl -sSf http://127.0.0.1:11434/api/tags >/dev/null 2>&1; then
    echo "   ✅ Ready for LLM tests!"
    echo "   🚀 You can now enable LLM tests in your PRs"
else
    echo "   ⚠️  Setup required:"
    if [ "$RUNNERS" -eq 0 ]; then
        echo "      - Set up self-hosted runner"
    fi
    if ! command -v ollama &> /dev/null; then
        echo "      - Install Ollama"
    fi
    if ! curl -sSf http://127.0.0.1:11434/api/tags >/dev/null 2>&1; then
        echo "      - Start Ollama service"
    fi
fi

echo ""
echo "🔧 Quick setup commands:"
echo "   ./scripts/setup-self-hosted-runner.sh  # Set up runner"
echo "   brew install ollama                    # Install Ollama"
echo "   ollama serve                           # Start Ollama"
echo "   ollama pull llama3.1:8b-instruct-q4_K_M  # Install models"
