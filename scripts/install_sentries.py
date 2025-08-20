#!/usr/bin/env python3
"""
Installation script for Sentries - Automated test and documentation maintenance.

This script helps users quickly set up Sentries in their repository.
"""

import os
import sys
import subprocess
import shutil
from pathlib import Path


def print_banner():
    """Print the Sentries installation banner."""
    print("🚀" * 50)
    print("🚀           SENTRIES INSTALLATION SCRIPT           🚀")
    print("🚀" * 50)
    print("🤖 Automated test and documentation maintenance via local LLMs")
    print()


def check_python_version():
    """Check if Python version meets requirements."""
    if sys.version_info < (3, 10):
        print("❌ Python 3.10+ is required")
        print(f"   Current version: {sys.version}")
        sys.exit(1)
    print(f"✅ Python version: {sys.version.split()[0]}")


def check_git_repo():
    """Check if we're in a git repository."""
    if not Path(".git").exists():
        print("❌ Not in a git repository")
        print("   Please run this script from your repository root")
        sys.exit(1)
    print("✅ Git repository detected")


def check_github_integration():
    """Check if GitHub integration is available."""
    try:
        result = subprocess.run(
            ["git", "remote", "get-url", "origin"],
            capture_output=True,
            text=True,
            check=True
        )
        remote_url = result.stdout.strip()
        if "github.com" in remote_url:
            print(f"✅ GitHub repository: {remote_url}")
        else:
            print(f"⚠️  Remote repository: {remote_url}")
            print("   GitHub integration recommended for best experience")
    except subprocess.CalledProcessError:
        print("⚠️  No remote origin configured")
        print("   GitHub integration recommended for best experience")


def install_sentries():
    """Install Sentries package."""
    print("\n📦 Installing Sentries...")
    
    try:
        # Try to install from GitHub
        subprocess.run([
            sys.executable, "-m", "pip", "install",
            "git+https://github.com/kofort9/sentries.git[all]"
        ], check=True)
        print("✅ Sentries installed successfully!")
        return True
    except subprocess.CalledProcessError:
        print("❌ Failed to install from GitHub")
        print("   Trying alternative installation method...")
        
        try:
            # Try basic installation
            subprocess.run([
                sys.executable, "-m", "pip", "install",
                "git+https://github.com/kofort9/sentries.git"
            ], check=True)
            print("✅ Sentries installed (basic version)")
            return True
        except subprocess.CalledProcessError:
            print("❌ Installation failed")
            return False


def verify_installation():
    """Verify that Sentries was installed correctly."""
    print("\n🔍 Verifying installation...")
    
    # Check if package can be imported
    try:
        import sentries
        print("✅ Sentries package imported successfully")
    except ImportError as e:
        print(f"❌ Failed to import sentries: {e}")
        return False
    
    # Check CLI tools
    cli_tools = ["testsentry", "docsentry", "codesentry"]
    available_tools = []
    
    for tool in cli_tools:
        if shutil.which(tool):
            available_tools.append(tool)
            print(f"✅ {tool} command available")
        else:
            print(f"⚠️  {tool} command not found")
    
    if len(available_tools) >= 2:
        print(f"✅ {len(available_tools)}/{len(cli_tools)} CLI tools available")
        return True
    else:
        print("⚠️  Some CLI tools may not be available")
        return False


def setup_github_actions():
    """Set up GitHub Actions workflows."""
    print("\n⚙️  Setting up GitHub Actions...")
    
    workflows_dir = Path(".github/workflows")
    workflows_dir.mkdir(parents=True, exist_ok=True)
    
    # Copy workflow files if they don't exist
    workflow_files = {
        "test-sentry.yml": "https://raw.githubusercontent.com/kofort9/sentries/main/.github/workflows/test-sentry.yml",
        "doc-sentry.yml": "https://raw.githubusercontent.com/kofort9/sentries/main/.github/workflows/doc-sentry.yml"
    }
    
    for filename, url in workflow_files.items():
        workflow_path = workflows_dir / filename
        if not workflow_path.exists():
            print(f"📥 Downloading {filename}...")
            try:
                import requests
                response = requests.get(url)
                response.raise_for_status()
                workflow_path.write_text(response.text)
                print(f"✅ {filename} downloaded")
            except Exception as e:
                print(f"⚠️  Failed to download {filename}: {e}")
                print(f"   You can manually copy it from: {url}")
        else:
            print(f"✅ {filename} already exists")
    
    print("✅ GitHub Actions setup complete")


def create_config_file():
    """Create a basic configuration file."""
    print("\n📝 Creating configuration file...")
    
    config_content = """# Sentries Configuration
# This file contains configuration for Sentries automation

# LLM Configuration
LLM_BASE=http://127.0.0.1:11434
MODEL_PLAN=llama3.1:8b-instruct-q4_K_M
MODEL_PATCH=deepseek-coder:6.7b-instruct-q5_K_M

# GitHub Configuration
# GITHUB_TOKEN=your_github_token_here
# GITHUB_REPOSITORY=owner/repo
# GITHUB_REF=refs/heads/main

# Sentries Configuration
TESTS_ALLOWLIST=[]  # Add test file patterns to ignore
DOCS_ALLOWLIST=[]   # Add documentation patterns to ignore
"""
    
    config_path = Path(".sentriesrc")
    if not config_path.exists():
        config_path.write_text(config_content)
        print("✅ Configuration file created: .sentriesrc")
        print("   Edit this file to customize Sentries behavior")
    else:
        print("✅ Configuration file already exists: .sentriesrc")


def print_next_steps():
    """Print next steps for the user."""
    print("\n" + "🎯" * 50)
    print("🎯                    NEXT STEPS                    🎯")
    print("🎯" * 50)
    
    print("\n1. 🔧 Configure Self-Hosted Runner")
    print("   - Set up a GitHub Actions self-hosted runner")
    print("   - Install Ollama and required models:")
    print("     ollama pull llama3.1:8b-instruct-q4_K_M")
    print("     ollama pull deepseek-coder:6.7b-instruct-q5_K_M")
    
    print("\n2. 🔑 Set GitHub Repository Variables")
    print("   - Go to Settings > Secrets and variables > Actions")
    print("   - Add GITHUB_TOKEN with repo access")
    print("   - Add MODEL_PLAN and MODEL_PATCH variables")
    
    print("\n3. 🧪 Test the Installation")
    print("   - Run: testsentry --help")
    print("   - Run: docsentry --help")
    print("   - Run: codesentry --help")
    
    print("\n4. 🚀 Create a Test PR")
    print("   - Make a code change in a new branch")
    print("   - Create a PR to trigger the workflows")
    print("   - Watch Sentries in action!")
    
    print("\n📚 For more information:")
    print("   - README.md: Complete project documentation")
    print("   - QUICKSTART.md: Quick setup guide")
    print("   - WORKFLOW_ENHANCEMENTS.md: Workflow details")
    
    print("\n🎉 Welcome to Sentries! Your repository now has AI-powered automation!")
    print("🎯" * 50)


def main():
    """Main installation function."""
    print_banner()
    
    # Pre-flight checks
    check_python_version()
    check_git_repo()
    check_github_integration()
    
    # Installation
    if not install_sentries():
        print("\n❌ Installation failed. Please check the errors above.")
        sys.exit(1)
    
    # Verification
    if not verify_installation():
        print("\n⚠️  Installation verification failed. Some features may not work.")
    
    # Setup
    setup_github_actions()
    create_config_file()
    
    # Next steps
    print_next_steps()


if __name__ == "__main__":
    main()
