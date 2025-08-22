#!/usr/bin/env python3
"""
Test the fixed chat function locally.
"""

import os
import sys
from pathlib import Path

# Add the current directory to sys.path
sys.path.insert(0, str(Path(__file__).parent))

from sentries.chat import chat, get_default_params

def test_chat_function():
    """Test the chat function with a simple prompt."""
    
    # Set environment variables
    os.environ['LLM_BASE'] = 'http://127.0.0.1:11434'
    
    # Test parameters
    params = get_default_params("planner")
    
    # Simple test messages
    messages = [
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "Reply with just the word OK"}
    ]
    
    print("🧪 Testing chat function with Ollama...")
    print(f"📝 Messages: {messages}")
    print(f"⚙️  Params: {params}")
    
    try:
        # Test with primary model
        print(f"\n🔍 Testing with model: llama3.1:8b-instruct-q4_K_M")
        response = chat(
            model="llama3.1:8b-instruct-q4_K_M",
            messages=messages,
            **params
        )
        
        print(f"✅ Response received (length: {len(response)}):")
        print(f"📄 Content: '{response}'")
        
        if response and len(response.strip()) > 0:
            print("🎉 SUCCESS: Chat function is working!")
            return True
        else:
            print("❌ FAILED: Empty response received")
            return False
            
    except Exception as e:
        print(f"❌ ERROR: {e}")
        return False

if __name__ == "__main__":
    success = test_chat_function()
    sys.exit(0 if success else 1)
