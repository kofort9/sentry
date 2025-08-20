#!/usr/bin/env python3
"""
Smoke test script for Sentries.
Tests connectivity to Ollama and model availability.
"""
import os
import sys
import requests
import json

def test_ollama_connectivity():
    """Test basic connectivity to Ollama."""
    try:
        llm_base = os.getenv("LLM_BASE", "http://127.0.0.1:11434")

        # Test basic connectivity
        response = requests.get(f"{llm_base}/api/tags", timeout=10)
        if response.status_code != 200:
            print(f"❌ Ollama API returned status {response.status_code}")
            return False

        print("✅ Ollama connectivity: OK")
        return True

    except requests.exceptions.ConnectionError:
        print("❌ Cannot connect to Ollama. Is it running?")
        return False
    except Exception as e:
        print(f"❌ Ollama connectivity error: {e}")
        return False

def test_model_availability():
    """Test if required models are available."""
    try:
        llm_base = os.getenv("LLM_BASE", "http://127.0.0.1:11434")
        model_plan = os.getenv("MODEL_PLAN", "llama3.1:8b-instruct-q4_K_M")
        model_patch = os.getenv("MODEL_PATCH", "deepseek-coder:6.7b-instruct-q5_K_M")

        # Get available models
        response = requests.get(f"{llm_base}/api/tags", timeout=10)
        if response.status_code != 200:
            print("❌ Failed to get model list")
            return False

        models_data = response.json()
        available_models = [model["name"] for model in models_data.get("models", [])]

        # Check planner model
        if model_plan in available_models:
            print(f"✅ Planner model available: {model_plan}")
        else:
            print(f"❌ Planner model not found: {model_plan}")
            print(f"Available models: {', '.join(available_models[:5])}...")
            return False

        # Check patcher model
        if model_patch in available_models:
            print(f"✅ Patcher model available: {model_patch}")
        else:
            print(f"❌ Patcher model not found: {model_patch}")
            print(f"Available models: {', '.join(available_models[:5])}...")
            return False

        return True

    except Exception as e:
        print(f"❌ Model availability check error: {e}")
        return False

def test_model_response():
    """Test if models can respond to simple prompts."""
    try:
        llm_base = os.getenv("LLM_BASE", "http://127.0.0.1:11434")
        model_plan = os.getenv("MODEL_PLAN", "llama3.1:8b-instruct-q4_K_M")

        # Test with a simple prompt using the newer Ollama API format
        payload = {
            "model": model_plan,
            "messages": [
                {
                    "role": "user",
                    "content": "Reply exactly: OK"
                }
            ],
            "stream": False,
            "options": {
                "temperature": 0.0,
                "num_predict": 10
            }
        }

        response = requests.post(f"{llm_base}/api/chat", json=payload, timeout=30)
        if response.status_code != 200:
            print(f"❌ Model response test failed: {response.status_code}")
            return False

        result = response.json()
        model_response = result.get("message", {}).get("content", "").strip()

        if "OK" in model_response:
            print("✅ Model response test: OK")
            return True
        else:
            print(f"❌ Unexpected model response: {model_response}")
            return False

    except Exception as e:
        print(f"❌ Model response test error: {e}")
        return False

def show_sentries_banner():
    """Display the Sentry ASCII art banner."""
    from sentries.banner import show_sentry_banner
    show_sentry_banner()
    print("🚬 Sentry Smoke Test - System Health Check")
    print("=" * 50)
    print()

def main():
    """Run all smoke tests."""
    show_sentries_banner()

    # Test 1: Ollama connectivity
    if not test_ollama_connectivity():
        sys.exit(1)

    # Test 2: Model availability
    if not test_model_availability():
        sys.exit(1)

    # Test 3: Model response
    if not test_model_response():
        sys.exit(1)

    print("=" * 40)
    print("✅ All smoke tests passed!")
    print("\nYou can now run:")
    print("  testsentry")
    print("  docsentry")

if __name__ == "__main__":
    main()
