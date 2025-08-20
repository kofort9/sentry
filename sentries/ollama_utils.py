"""
Ollama management utilities for Sentries workflows.

Provides automatic startup, health checking, and cleanup of Ollama service.
"""

import os
import time
import subprocess
import requests
from typing import Optional, Tuple


def check_ollama_running() -> bool:
    """Check if Ollama is running and accessible."""
    try:
        # Try to connect to Ollama API
        response = requests.get("http://127.0.0.1:11434/api/version", timeout=3)
        return response.status_code == 200
    except (requests.exceptions.ConnectionError, requests.exceptions.Timeout):
        return False


def start_ollama() -> Tuple[bool, Optional[subprocess.Popen]]:
    """
    Start Ollama service if not running.

    Returns:
        (success, process): Tuple of success status and process object (if started)
    """
    if check_ollama_running():
        print("ℹ️  Ollama is already running")
        return True, None

    print("🚀 Starting Ollama...")

    try:
        # Start Ollama in the background
        process = subprocess.Popen(
            ["ollama", "serve"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            preexec_fn=os.setsid if hasattr(os, 'setsid') else None
        )

        # Wait for Ollama to start up (max 30 seconds)
        for i in range(30):
            time.sleep(1)
            if check_ollama_running():
                print("✅ Ollama started successfully")
                return True, process
            print(f"   Waiting for Ollama to start... ({i+1}/30)")

        print("❌ Timeout waiting for Ollama to start")
        process.terminate()
        return False, None

    except FileNotFoundError:
        print("❌ Ollama not found. Please install Ollama first:")
        print("   Visit: https://ollama.com/download")
        return False, None
    except Exception as e:
        print(f"❌ Failed to start Ollama: {e}")
        return False, None


def stop_ollama(process: Optional[subprocess.Popen]) -> None:
    """
    Stop Ollama service if we started it.

    Args:
        process: The process object returned by start_ollama()
    """
    if process is None:
        print("ℹ️  Ollama was already running, leaving it running")
        return

    print("🛑 Stopping Ollama...")
    try:
        process.terminate()

        # Wait for graceful shutdown
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            print("   Force killing Ollama process...")
            process.kill()
            process.wait()

        print("✅ Ollama stopped")

    except Exception as e:
        print(f"⚠️  Error stopping Ollama: {e}")


def ensure_model_available(model_name: str = "llama3.1:8b-instruct-q4_K_M") -> bool:
    """
    Ensure the specified model is available in Ollama.

    Args:
        model_name: Name of the model to check/pull

    Returns:
        True if model is available, False otherwise
    """
    if not check_ollama_running():
        print("❌ Ollama is not running")
        return False

    try:
        # Check if model exists
        result = subprocess.run(
            ["ollama", "list"],
            capture_output=True,
            text=True,
            timeout=10
        )

        if model_name in result.stdout:
            print(f"✅ Model {model_name} is available")
            return True

        print(f"📥 Pulling model {model_name}...")
        print("   This may take a few minutes...")

        # Pull the model
        result = subprocess.run(
            ["ollama", "pull", model_name],
            timeout=600  # 10 minutes timeout for model download
        )

        if result.returncode == 0:
            print(f"✅ Model {model_name} downloaded successfully")
            return True
        else:
            print(f"❌ Failed to download model {model_name}")
            return False

    except subprocess.TimeoutExpired:
        print(f"❌ Timeout downloading model {model_name}")
        return False
    except Exception as e:
        print(f"❌ Error checking/downloading model: {e}")
        return False


class OllamaManager:
    """Context manager for automatic Ollama lifecycle management."""

    def __init__(self, model_name: Optional[str] = None):
        self.model_name = model_name or "llama3.1:8b-instruct-q4_K_M"
        self.process = None
        self.started_ollama = False

    def __enter__(self):
        """Start Ollama and ensure model is available."""
        print("🔧 Setting up Ollama for Sentries...")

        # Start Ollama if needed
        success, process = start_ollama()
        if not success:
            raise RuntimeError("Failed to start Ollama")

        self.process = process
        self.started_ollama = process is not None

        # Ensure model is available
        if not ensure_model_available(self.model_name):
            if self.started_ollama:
                stop_ollama(self.process)
            raise RuntimeError(f"Model {self.model_name} is not available")

        print("✅ Ollama is ready for Sentries")
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Clean up Ollama if we started it."""
        if self.started_ollama:
            stop_ollama(self.process)
        else:
            print("ℹ️  Leaving Ollama running (was already running)")


def get_ollama_status() -> dict:
    """Get comprehensive Ollama status information."""
    status = {
        "running": check_ollama_running(),
        "models": [],
        "version": None
    }

    if status["running"]:
        try:
            # Get version
            response = requests.get("http://127.0.0.1:11434/api/version", timeout=3)
            if response.status_code == 200:
                status["version"] = response.json().get("version", "unknown")

            # Get models
            result = subprocess.run(
                ["ollama", "list"],
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode == 0:
                # Parse model list (skip header line)
                lines = result.stdout.strip().split('\n')[1:]
                status["models"] = [line.split()[0] for line in lines if line.strip()]

        except Exception:
            pass  # Status will show as running but without details

    return status
