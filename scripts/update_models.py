#!/usr/bin/env python3
"""
Sentries Model Update Utility

Check for and install better versions of LLM models.
"""
import os
import sys
import json
import subprocess
import requests
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from datetime import datetime

# Add the parent directory to Python path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sentries.runner_common import setup_logging, get_logger

logger = get_logger(__name__)

class ModelUpdater:
    def __init__(self):
        self.ollama_base = "http://127.0.0.1:11434"
        
        # Model recommendations with quality tiers
        self.model_recommendations = {
            "planner": {
                "tier_1": [
                    {
                        "name": "llama3.1:8b-instruct-q8_0",
                        "size_gb": 8.5,
                        "description": "Highest quality planning (best reasoning)",
                        "recommended": True
                    },
                    {
                        "name": "llama3.1:8b-instruct-q4_K_M",
                        "size_gb": 4.7,
                        "description": "Balanced quality/size (current default)",
                        "recommended": True
                    }
                ],
                "tier_2": [
                    {
                        "name": "llama3.1:8b-instruct-q2_K",
                        "size_gb": 2.9,
                        "description": "Fast planning (lower quality)",
                        "recommended": False
                    },
                    {
                        "name": "mistral:7b-instruct-v0.2-q4_K_M",
                        "size_gb": 4.1,
                        "description": "Alternative planning model",
                        "recommended": False
                    }
                ]
            },
            "patcher": {
                "tier_1": [
                    {
                        "name": "deepseek-coder:6.7b-instruct-q8_0",
                        "size_gb": 6.7,
                        "description": "Highest quality code generation",
                        "recommended": True
                    },
                    {
                        "name": "deepseek-coder:6.7b-instruct-q5_K_M",
                        "size_gb": 4.2,
                        "description": "Balanced quality/size (current default)",
                        "recommended": True
                    }
                ],
                "tier_2": [
                    {
                        "name": "deepseek-coder:6.7b-instruct-q2_K",
                        "size_gb": 2.7,
                        "description": "Fast code generation (lower quality)",
                        "recommended": False
                    },
                    {
                        "name": "codellama:7b-instruct-q4_K_M",
                        "size_gb": 4.1,
                        "description": "Alternative code generation model",
                        "recommended": False
                    }
                ]
            }
        }
    
    def run_update_check(self):
        """Run the complete model update check."""
        self.show_sentries_banner()
        print("=" * 50)
    
    def show_sentries_banner(self):
        """Display the Sentry ASCII art banner."""
        from sentries.banner import show_sentry_banner
        show_sentry_banner()
        print("🔄 Starting Model Update Check...")
        print()
        
        # Check Ollama connectivity
        if not self.check_ollama():
            print("❌ Ollama not accessible. Please start Ollama first.")
            sys.exit(1)
        
        # Get current models
        current_models = self.get_current_models()
        
        # Check for updates
        self.check_for_updates(current_models)
        
        # Show recommendations
        self.show_recommendations()
        
        # Offer to install better models
        self.offer_updates()
    
    def check_ollama(self) -> bool:
        """Check if Ollama is accessible."""
        try:
            response = requests.get(f"{self.ollama_base}/api/tags", timeout=10)
            return response.status_code == 200
        except Exception:
            return False
    
    def get_current_models(self) -> Dict[str, List[str]]:
        """Get currently installed models."""
        print("🔍 Checking currently installed models...")
        
        try:
            response = requests.get(f"{self.ollama_base}/api/tags", timeout=10)
            if response.status_code != 200:
                return {"planner": [], "patcher": []}
            
            models_data = response.json()
            installed_models = [model["name"] for model in models_data.get("models", [])]
            
            # Categorize models
            current_models = {
                "planner": [],
                "patcher": []
            }
            
            for model_name in installed_models:
                if "llama" in model_name.lower() or "mistral" in model_name.lower():
                    current_models["planner"].append(model_name)
                elif "deepseek" in model_name.lower() or "codellama" in model_name.lower():
                    current_models["patcher"].append(model_name)
            
            # Show current models
            for model_type, models in current_models.items():
                if models:
                    print(f"   📦 {model_type.title()} models:")
                    for model in models:
                        print(f"      - {model}")
                else:
                    print(f"   ❌ No {model_type} models found")
            
            return current_models
            
        except Exception as e:
            logger.error(f"Error getting current models: {e}")
            return {"planner": [], "patcher": []}
    
    def check_for_updates(self, current_models: Dict[str, List[str]]):
        """Check for available model updates."""
        print("\n🔄 Checking for model updates...")
        
        self.update_opportunities = []
        
        for model_type, recommendations in self.model_recommendations.items():
            current_best = self.get_best_current_model(current_models.get(model_type, []), model_type)
            
            # Check if we can upgrade to tier 1
            tier_1_models = recommendations["tier_1"]
            for tier_1_model in tier_1_models:
                if tier_1_model["name"] not in current_models.get(model_type, []):
                    # Check if this is better than current
                    if not current_best or self.is_model_better(tier_1_model, current_best, model_type):
                        self.update_opportunities.append({
                            "type": model_type,
                            "current": current_best,
                            "upgrade": tier_1_model,
                            "priority": "high" if tier_1_model["recommended"] else "medium"
                        })
        
        if self.update_opportunities:
            print(f"   ✅ Found {len(self.update_opportunities)} upgrade opportunities")
        else:
            print("   ℹ️  No upgrade opportunities found")
    
    def get_best_current_model(self, models: List[str], model_type: str) -> Optional[Dict]:
        """Get the best currently installed model of a given type."""
        if not models:
            return None
        
        # Find the best model based on quality tier
        best_model = None
        best_tier = 3  # Lower is better
        
        for model_name in models:
            for tier_name, tier_models in self.model_recommendations[model_type].items():
                tier_num = 1 if tier_name == "tier_1" else 2
                
                for tier_model in tier_models:
                    if tier_model["name"] == model_name and tier_num < best_tier:
                        best_model = tier_model
                        best_tier = tier_num
                        break
        
        return best_model
    
    def is_model_better(self, new_model: Dict, current_model: Optional[Dict], model_type: str) -> bool:
        """Check if a new model is better than the current one."""
        if not current_model:
            return True
        
        # Simple heuristic: higher quality quantization is better
        new_quality = self.get_quantization_quality(new_model["name"])
        current_quality = self.get_quantization_quality(current_model["name"])
        
        return new_quality > current_quality
    
    def get_quantization_quality(self, model_name: str) -> int:
        """Get quantization quality score (higher is better)."""
        if "q8_0" in model_name:
            return 8
        elif "q5_K_M" in model_name:
            return 5
        elif "q4_K_M" in model_name:
            return 4
        elif "q2_K" in model_name:
            return 2
        else:
            return 1
    
    def show_recommendations(self):
        """Show model recommendations."""
        print("\n📋 Model Recommendations:")
        print("-" * 30)
        
        for model_type, recommendations in self.model_recommendations.items():
            print(f"\n   🎯 {model_type.title()} Models:")
            
            # Show tier 1 (recommended)
            print("      🥇 Tier 1 (Recommended):")
            for model in recommendations["tier_1"]:
                status = "✅" if model["recommended"] else "⚪"
                print(f"         {status} {model['name']}")
                print(f"            Size: {model['size_gb']:.1f}GB")
                print(f"            Description: {model['description']}")
            
            # Show tier 2 (alternatives)
            print("      🥈 Tier 2 (Alternatives):")
            for model in recommendations["tier_2"]:
                print(f"         ⚪ {model['name']}")
                print(f"            Size: {model['size_gb']:.1f}GB")
                print(f"            Description: {model['description']}")
    
    def offer_updates(self):
        """Offer to install model updates."""
        if not self.update_opportunities:
            print("\n🎉 Your models are up to date!")
            return
        
        print(f"\n🚀 Found {len(self.update_opportunities)} upgrade opportunities:")
        
        for i, opportunity in enumerate(self.update_opportunities, 1):
            current_name = opportunity["current"]["name"] if opportunity["current"] else "None"
            upgrade_name = opportunity["upgrade"]["name"]
            priority = opportunity["priority"]
            
            print(f"\n   {i}. {opportunity['type'].title()} Model Upgrade")
            print(f"      Current: {current_name}")
            print(f"      Upgrade to: {upgrade_name}")
            print(f"      Priority: {priority.upper()}")
            print(f"      Size: {opportunity['upgrade']['size_gb']:.1f}GB")
            print(f"      Description: {opportunity['upgrade']['description']}")
        
        # Ask user what they want to do
        print("\n" + "=" * 50)
        response = input("Would you like to install any of these upgrades? (y/n): ")
        
        if response.lower() in ['y', 'yes']:
            self.install_updates()
        else:
            print("No updates installed. You can run this script again later.")
    
    def install_updates(self):
        """Install selected model updates."""
        print("\n📦 Installing model updates...")
        
        for opportunity in self.update_opportunities:
            upgrade_name = opportunity["upgrade"]["name"]
            print(f"\n   📥 Installing {upgrade_name}...")
            
            if self.install_model(upgrade_name):
                print(f"      ✅ {upgrade_name} installed successfully")
                
                # Update .env file if this is a recommended model
                if opportunity["upgrade"]["recommended"]:
                    self.update_env_file(opportunity["type"], upgrade_name)
            else:
                print(f"      ❌ Failed to install {upgrade_name}")
                print(f"      You can install manually: ollama pull {upgrade_name}")
        
        print("\n🎉 Model update installation completed!")
    
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
    
    def update_env_file(self, model_type: str, model_name: str):
        """Update .env file with new model."""
        env_file = Path(".env")
        if not env_file.exists():
            print(f"      ℹ️  .env file not found, skipping update")
            return
        
        try:
            # Read current .env file
            with open(env_file, 'r') as f:
                content = f.read()
            
            # Update the appropriate model variable
            if model_type == "planner":
                content = self.update_env_variable(content, "MODEL_PLAN", model_name)
            elif model_type == "patcher":
                content = self.update_env_variable(content, "MODEL_PATCH", model_name)
            
            # Write updated content
            with open(env_file, 'w') as f:
                f.write(content)
            
            print(f"      ✅ Updated .env file with new {model_type} model")
            
        except Exception as e:
            print(f"      ⚠️  Could not update .env file: {e}")
    
    def update_env_variable(self, content: str, var_name: str, new_value: str) -> str:
        """Update an environment variable in .env content."""
        lines = content.split('\n')
        updated_lines = []
        
        for line in lines:
            if line.startswith(f"{var_name}="):
                updated_lines.append(f"{var_name}={new_value}")
            else:
                updated_lines.append(line)
        
        return '\n'.join(updated_lines)
    
    def show_model_info(self):
        """Show detailed information about models."""
        self.show_sentries_banner()
        print("📊 Model Information:")
        print("-" * 30)
        
        # Get disk usage
        try:
            result = subprocess.run(['ollama', 'list'], capture_output=True, text=True, timeout=10)
            if result.returncode == 0:
                lines = result.stdout.strip().split('\n')[1:]  # Skip header
                
                total_size = 0
                for line in lines:
                    if line.strip():
                        parts = line.split()
                        if len(parts) >= 3:
                            size_str = parts[2]
                            if 'GB' in size_str:
                                size_gb = float(size_str.replace('GB', ''))
                                total_size += size_gb
                
                print(f"   💾 Total model storage: {total_size:.1f}GB")
                
        except Exception as e:
            print(f"   ⚠️  Could not get model storage info: {e}")
        
        # Show model recommendations summary
        print("\n   🎯 Recommended Models:")
        for model_type, recommendations in self.model_recommendations.items():
            tier_1_models = [m for m in recommendations["tier_1"] if m["recommended"]]
            for model in tier_1_models:
                print(f"      {model_type.title()}: {model['name']} ({model['size_gb']:.1f}GB)")

def main():
    """Main entry point."""
    import argparse
    parser = argparse.ArgumentParser(description="Update Sentries LLM models")
    parser.add_argument(
        '--info-only', 
        action='store_true', 
        help='Show model information without offering updates'
    )
    
    args = parser.parse_args()
    
    # Setup logging
    setup_logging()
    
    # Initialize updater
    updater = ModelUpdater()
    
    if args.info_only:
        updater.show_model_info()
    else:
        # Run update check
        updater.run_update_check()

if __name__ == "__main__":
    main()
