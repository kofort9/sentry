#!/bin/bash
# Setup script for self-hosted GitHub Actions runner

set -e

echo "🚀 Setting up self-hosted GitHub Actions runner for TestSentry"
echo ""

# Check if we're on macOS
if [[ "$OSTYPE" != "darwin"* ]]; then
    echo "❌ This script is designed for macOS. Please adapt for your OS."
    exit 1
fi

# Check if required tools are installed
if ! command -v curl &> /dev/null; then
    echo "❌ curl is required but not installed"
    exit 1
fi

if ! command -v gh &> /dev/null; then
    echo "❌ GitHub CLI (gh) is required but not installed"
    echo "   Install with: brew install gh"
    exit 1
fi

# Check if user is authenticated with GitHub
if ! gh auth status &> /dev/null; then
    echo "❌ Not authenticated with GitHub CLI"
    echo "   Run: gh auth login"
    exit 1
fi

echo "✅ Prerequisites check passed"
echo ""

# Create runner directory
RUNNER_DIR="$HOME/actions-runner"
echo "📁 Creating runner directory: $RUNNER_DIR"
mkdir -p "$RUNNER_DIR"
cd "$RUNNER_DIR"

# Download the latest runner
echo "📥 Downloading GitHub Actions runner..."
LATEST_VERSION=$(gh api repos/actions/runner/releases/latest --jq '.tag_name' | sed 's/v//')
echo "   Latest version: $LATEST_VERSION"

curl -o "actions-runner-osx-x64-${LATEST_VERSION}.tar.gz" \
     -L "https://github.com/actions/runner/releases/download/v${LATEST_VERSION}/actions-runner-osx-x64-${LATEST_VERSION}.tar.gz"

echo "📦 Extracting runner package..."
tar xzf "actions-runner-osx-x64-${LATEST_VERSION}.tar.gz"

echo "🔧 Configuring runner..."
echo ""
echo "⚠️  You need to get a registration token from GitHub:"
echo "   1. Go to: https://github.com/kofort9/sentry/settings/actions/runners"
echo "   2. Click 'New runner'"
echo "   3. Select 'macOS' and 'x64'"
echo "   4. Copy the registration token"
echo ""
read -p "Enter the registration token: " REGISTRATION_TOKEN

# Configure the runner
./config.sh \
    --url https://github.com/kofort9/sentry \
    --token "$REGISTRATION_TOKEN" \
    --name "macos-runner-$(hostname)" \
    --work "_work" \
    --replace

echo ""
echo "✅ Runner configured successfully!"
echo ""

# Ask if user wants to install as a service
read -p "Install as a service for auto-start? (y/n): " INSTALL_SERVICE
if [[ $INSTALL_SERVICE =~ ^[Yy]$ ]]; then
    echo "🔧 Installing as a service..."
    ./svc.sh install
    echo "🚀 Starting service..."
    ./svc.sh start
    echo "✅ Service installed and started!"
else
    echo "ℹ️  To start the runner manually, run:"
    echo "   cd $RUNNER_DIR && ./run.sh"
fi

echo ""
echo "🎉 Self-hosted runner setup complete!"
echo ""
echo "📋 Next steps:"
echo "   1. Verify the runner appears in GitHub:"
echo "      https://github.com/kofort9/sentry/settings/actions/runners"
echo "   2. Install Ollama for LLM operations:"
echo "      brew install ollama"
echo "   3. Start Ollama service:"
echo "      ollama serve"
echo "   4. Download required models:"
echo "      ollama pull llama3.1:8b-instruct-q4_K_M"
echo "      ollama pull deepseek-coder:6.7b-instruct-q5_K_M"
echo ""
echo "🔍 To check runner status:"
echo "   gh api repos/kofort9/sentry/actions/runners"
