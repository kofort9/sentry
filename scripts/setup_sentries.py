#!/usr/bin/env python3
"""
Sentries Setup Script

Automated setup and configuration for Sentries with LLM management.
"""
import argparse
import os
import sys
import json
import subprocess
import requests
from pathlib import Path
from typing import Dict, List, Optional

# Add the parent directory to Python path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sentries.runner_common import setup_logging, get_logger

logger = get_logger(__name__)

class SentriesSetup:
    def __init__(self):
        self.ollama_base = "http://127.0.0.1:11434"
        self.required_models = {
            "planner": {
                "name": "llama3.1:8b-instruct-q4_K_M",
                "size_gb": 4.7,
                "description": "Planning model for analyzing issues and creating plans",
                "recommended": True
            },
            "patcher": {
                "name": "deepseek-coder:6.7b-instruct-q5_K_M",
                "size_gb": 4.2,
                "description": "Code generation model for creating patches",
                "recommended": True
            }
        }
        
        self.alternative_models = {
            "planner": [
                {
                    "name": "llama3.1:8b-instruct-q4_K_M",
                    "size_gb": 4.7,
                    "description": "Recommended planning model (balanced performance/size)"
                },
                {
                    "name": "llama3.1:8b-instruct-q8_0",
                    "size_gb": 8.5,
                    "description": "Higher quality planning (larger size)"
                },
                {
                    "name": "llama3.1:8b-instruct-q2_K",
                    "size_gb": 2.9,
                    "description": "Faster planning (smaller size, lower quality)"
                },
                {
                    "name": "mistral:7b-instruct-v0.2-q4_K_M",
                    "size_gb": 4.1,
                    "description": "Alternative planning model"
                }
            ],
            "patcher": [
                {
                    "name": "deepseek-coder:6.7b-instruct-q5_K_M",
                    "size_gb": 4.2,
                    "description": "Recommended code generation model"
                },
                {
                    "name": "deepseek-coder:6.7b-instruct-q8_0",
                    "size_gb": 6.7,
                    "description": "Higher quality code generation"
                },
                {
                    "name": "deepseek-coder:6.7b-instruct-q2_K",
                    "size_gb": 2.7,
                    "description": "Faster code generation (lower quality)"
                },
                {
                    "name": "codellama:7b-instruct-q4_K_M",
                    "size_gb": 4.1,
                    "description": "Alternative code generation model"
                }
            ]
        }
    
    def run_setup(self):
        """Run the complete setup process."""
        self.show_sentries_banner()
        print("=" * 50)
    
    def show_sentries_banner(self):
        """Display the Sentry ASCII art banner."""
        from sentries.banner import show_sentry_banner
        show_sentry_banner()
        print("🚀 Starting Sentry Setup Process...")
        print()
        
        # Check system requirements
        if not self.check_system_requirements():
            print("❌ System requirements not met. Please check the README for requirements.")
            sys.exit(1)
        
        # Check Ollama installation
        if not self.check_ollama():
            print("❌ Ollama not found. Please install Ollama first.")
            print("   Visit: https://ollama.ai/download")
            sys.exit(1)
        
        # Start Ollama if not running
        if not self.start_ollama():
            print("❌ Could not start Ollama. Please start it manually.")
            sys.exit(1)
        
        # Install required models
        self.install_models()
        
        # Configure environment
        self.configure_environment()
        
        # Test installation
        self.test_installation()
        
        # Show next steps
        self.show_next_steps()
    
    def check_system_requirements(self) -> bool:
        """Check if system meets requirements."""
        print("🔍 Checking system requirements...")
        
        # Check Python version
        python_version = sys.version_info
        if python_version < (3, 10):
            print(f"   ❌ Python {python_version.major}.{python_version.minor} found")
            print("      Python 3.10+ is required")
            return False
        else:
            print(f"   ✅ Python {python_version.major}.{python_version.minor} ✓")
        
        # Check available disk space
        try:
            import shutil
            total, used, free = shutil.disk_usage(".")
            free_gb = free // (1024**3)
            
            # Calculate required space (models + safety margin)
            required_gb = sum(model["size_gb"] for model in self.required_models.values()) + 2
            required_gb = max(required_gb, 10)  # Minimum 10GB
            
            if free_gb < required_gb:
                print(f"   ❌ Insufficient disk space")
                print(f"      Available: {free_gb}GB, Required: {required_gb}GB")
                return False
            else:
                print(f"   ✅ Disk space: {free_gb}GB available ✓")
        
        except Exception as e:
            print(f"   ⚠️  Could not check disk space: {e}")
        
        # Check memory
        try:
            import psutil
            memory_gb = psutil.virtual_memory().total // (1024**3)
            if memory_gb < 8:
                print(f"   ⚠️  Low memory: {memory_gb}GB (8GB+ recommended)")
            else:
                print(f"   ✅ Memory: {memory_gb}GB ✓")
        except ImportError:
            print("   ⚠️  Could not check memory (psutil not installed)")
        
        print("   ✅ System requirements check completed")
        return True
    
    def check_ollama(self) -> bool:
        """Check if Ollama is installed."""
        print("\n🔍 Checking Ollama installation...")
        
        # Check if ollama command exists
        try:
            result = subprocess.run(['ollama', '--version'], 
                                  capture_output=True, text=True, timeout=10)
            if result.returncode == 0:
                version = result.stdout.strip()
                print(f"   ✅ Ollama found: {version}")
                return True
            else:
                print("   ❌ Ollama command failed")
                return False
        except FileNotFoundError:
            print("   ❌ Ollama not found in PATH")
            return False
        except Exception as e:
            print(f"   ❌ Error checking Ollama: {e}")
            return False
    
    def start_ollama(self) -> bool:
        """Start Ollama if not running."""
        print("\n🚀 Starting Ollama...")
        
        # Check if Ollama is already running
        try:
            response = requests.get(f"{self.ollama_base}/api/tags", timeout=5)
            if response.status_code == 200:
                print("   ✅ Ollama is already running")
                return True
        except requests.RequestException:
            pass
        
        # Try to start Ollama
        try:
            print("   🔄 Starting Ollama service...")
            # Start in background
            subprocess.Popen(['ollama', 'serve'], 
                           stdout=subprocess.DEVNULL, 
                           stderr=subprocess.DEVNULL)
            
            # Wait for it to start
            import time
            for i in range(30):  # Wait up to 30 seconds
                time.sleep(1)
                try:
                    response = requests.get(f"{self.ollama_base}/api/tags", timeout=5)
                    if response.status_code == 200:
                        print("   ✅ Ollama started successfully")
                        return True
                except requests.RequestException:
                    pass
                
                if i % 5 == 0:
                    print(f"      Waiting... ({i+1}/30s)")
            
            print("   ❌ Ollama failed to start within 30 seconds")
            return False
            
        except Exception as e:
            print(f"   ❌ Failed to start Ollama: {e}")
            return False
    
    def install_models(self):
        """Install required models."""
        print("\n📦 Installing LLM models...")
        
        total_size = sum(model["size_gb"] for model in self.required_models.values())
        print(f"   Total size required: {total_size:.1f}GB")
        print()
        
        for model_type, model_info in self.required_models.items():
            print(f"   📥 Installing {model_type} model: {model_info['name']}")
            print(f"      Size: {model_info['size_gb']:.1f}GB")
            print(f"      Description: {model_info['description']}")
            
            if self.install_model(model_info['name']):
                print(f"      ✅ {model_info['name']} installed successfully")
            else:
                print(f"      ❌ Failed to install {model_info['name']}")
                print(f"      Please install manually: ollama pull {model_info['name']}")
            
            print()
    
    def install_model(self, model_name: str) -> bool:
        """Install a specific model."""
        try:
            print(f"      🔄 Downloading {model_name}...")
            
            # Start the pull process
            process = subprocess.Popen(
                ['ollama', 'pull', model_name],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            
            # Monitor progress
            while True:
                output = process.stdout.readline()
                if output == '' and process.poll() is not None:
                    break
                if output:
                    # Extract progress information
                    if 'pulling' in output.lower() or 'downloading' in output.lower():
                        print(f"         {output.strip()}")
            
            # Check result
            if process.returncode == 0:
                return True
            else:
                stderr = process.stderr.read()
                if stderr:
                    print(f"         Error: {stderr}")
                return False
                
        except Exception as e:
            print(f"         Error: {e}")
            return False
    
    def configure_environment(self):
        """Configure environment variables."""
        print("\n⚙️  Configuring environment...")
        
        # Create .env file if it doesn't exist
        env_file = Path(".env")
        if not env_file.exists():
            env_content = f"""# Sentries Configuration
# LLM Configuration
LLM_BASE=http://127.0.0.1:11434
MODEL_PLAN={self.required_models['planner']['name']}
MODEL_PATCH={self.required_models['patcher']['name']}

# GitHub Configuration (set these manually)
# GITHUB_TOKEN=your_github_token_here
# GITHUB_REPOSITORY=your-org/your-repo

# Optional Configuration
# LOG_LEVEL=INFO
# MAX_TEST_FILES=5
# MAX_TEST_LINES=200
# MAX_DOC_FILES=5
# MAX_DOC_LINES=300
"""
            
            with open(env_file, 'w') as f:
                f.write(env_content)
            
            print("   ✅ Created .env file with default configuration")
        else:
            print("   ℹ️  .env file already exists")
        
        # Create .env.example
        example_file = Path(".env.example")
        if not example_file.exists():
            with open(example_file, 'w') as f:
                f.write(env_content)
            print("   ✅ Created .env.example file")
        
        # Show configuration instructions
        print("\n   📝 Environment Configuration:")
        print("      - Edit .env file with your GitHub credentials")
        print("      - Set GITHUB_TOKEN and GITHUB_REPOSITORY")
        print("      - Adjust model names if using alternatives")
    
    def test_installation(self):
        """Test the Sentries installation."""
        print("\n🧪 Testing installation...")
        
        # Test Ollama connectivity
        try:
            response = requests.get(f"{self.ollama_base}/api/tags", timeout=10)
            if response.status_code == 200:
                print("   ✅ Ollama connectivity ✓")
            else:
                print("   ❌ Ollama API error")
                return
        except Exception as e:
            print(f"   ❌ Ollama connectivity failed: {e}")
            return
        
        # Test model availability
        models_available = True
        for model_type, model_info in self.required_models.items():
            if self.test_model(model_info['name']):
                print(f"   ✅ {model_type} model ({model_info['name']}) ✓")
            else:
                print(f"   ❌ {model_type} model ({model_info['name']}) failed")
                models_available = False
        
        if not models_available:
            print("\n   ⚠️  Some models failed testing")
            print("      Please check model installation")
            return
        
        # Test Sentries installation
        try:
            result = subprocess.run(['python', '-c', 'from sentries import testsentry, docsentry; print("OK")'],
                                  capture_output=True, text=True, timeout=10)
            if result.returncode == 0:
                print("   ✅ Sentries package ✓")
            else:
                print("   ❌ Sentries package failed")
                return
        except Exception as e:
            print(f"   ❌ Sentries package test failed: {e}")
            return
        
        # Test smoke script
        try:
            result = subprocess.run(['python', 'scripts/smoke.py'],
                                  capture_output=True, text=True, timeout=60)
            if result.returncode == 0:
                print("   ✅ Smoke test ✓")
            else:
                print("   ⚠️  Smoke test had issues (check output)")
        except Exception as e:
            print(f"   ⚠️  Smoke test failed: {e}")
        
        print("   ✅ Installation testing completed")
    
    def test_model(self, model_name: str) -> bool:
        """Test if a model is available and responding."""
        try:
            payload = {
                "model": model_name,
                "prompt": "Reply with 'OK'",
                "stream": False,
                "options": {
                    "temperature": 0.0,
                    "num_predict": 10
                }
            }
            
            response = requests.post(f"{self.ollama_base}/api/chat", 
                                  json=payload, timeout=30)
            
            if response.status_code == 200:
                result = response.json()
                model_response = result.get("message", {}).get("content", "").strip()
                return "OK" in model_response
            else:
                return False
                
        except Exception:
            return False
    
    def show_next_steps(self):
        """Show next steps for the user."""
        print("\n" + "=" * 50)
        print("🎉 Setup Complete!")
        print("=" * 50)
        
        print("\n📋 Next Steps:")
        print("1. Configure GitHub credentials in .env file")
        print("2. Test Sentries in a repository:")
        print("   cd /path/to/your/repo")
        print("   testsentry")
        print("   docsentry")
        print("3. Set up GitHub Actions workflows")
        print("4. Monitor with sentries-status")
        print("5. Clean up with sentries-cleanup")
        
        print("\n📚 Documentation:")
        print("   - README.md: Complete usage guide")
        print("   - examples/workflows/: GitHub Actions examples")
        
        print("\n🔧 Management Commands:")
        print("   sentries-status          # Check status")
        print("   sentries-cleanup --dry-run  # Preview cleanup")
        print("   ollama list              # List installed models")
        print("   ollama pull <model>      # Install additional models")
        
        print("\n💡 Tips:")
        print("   - Use --dry-run flag before cleanup operations")
        print("   - Monitor disk space for model storage")
        print("   - Keep models updated for best performance")
        
        print("\n🚀 Happy coding with Sentries!")

def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Setup Sentries with LLM management")
    parser.add_argument(
        '--skip-models', 
        action='store_true', 
        help='Skip model installation (models already installed)'
    )
    parser.add_argument(
        '--skip-tests', 
        action='store_true', 
        help='Skip installation testing'
    )
    
    args = parser.parse_args()
    
    # Setup logging
    setup_logging()
    
    # Initialize setup
    setup = SentriesSetup()
    
    # Run setup
    setup.run_setup()

if __name__ == "__main__":
    main()
