# 🚀 **Sentries Usage Examples**

This document provides comprehensive examples for using Sentries in all three modes.

## 📋 **Quick Mode Detection**

```bash
# Check which mode will be used
python -c "
from sentries.chat import is_simulation_mode, has_api_key
import os

print('🔍 Mode Detection Results:')
print(f'  Simulation mode: {is_simulation_mode()}')
print(f'  API key available: {has_api_key()}')

if is_simulation_mode():
    print('  ✅ Will use: SIMULATION MODE (free, deterministic)')
elif has_api_key():
    print('  ✅ Will use: API MODE (real LLM responses)')
else:
    print('  ✅ Will use: LOCAL LLM MODE (requires Ollama)')

print('\\n📋 Priority: Simulation > API > Local LLM')
"
```

## 🎭 **Simulation Mode Examples**

### **Basic Usage**
```bash
# Enable simulation mode
export SENTRIES_SIMULATION_MODE=true

# Run TestSentry
python -m sentries.testsentry

# Or test directly
python -c "
from sentries.chat import chat
messages = [{'role': 'user', 'content': 'Fix this test: assert 1 == 2'}]
response = chat('test-model', messages)
print('Response:', response)
"
```

### **GitHub Actions Integration**
```yaml
# .github/workflows/test-sentries.yml
name: Test Sentries
on: [push, pull_request]

jobs:
  test-simulation:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'
      
      - name: Install Sentries
        run: pip install -e .
      
      - name: Test with Simulation Mode
        env:
          SENTRIES_SIMULATION_MODE: true
        run: |
          echo "🎭 Testing in simulation mode"
          python -m sentries.testsentry
```

### **Different Response Types**
```python
from sentries.chat import chat
import os

# Enable simulation mode
os.environ['SENTRIES_SIMULATION_MODE'] = 'true'

# Test fixing response
fix_messages = [{"role": "user", "content": "Fix this test: assert 1 == 2"}]
fix_response = chat("test-model", fix_messages)
print("Fix response:", fix_response[:100] + "...")

# Planning response
plan_messages = [{"role": "user", "content": "Create a plan for fixing this issue"}]
plan_response = chat("test-model", plan_messages)
print("Plan response:", plan_response[:100] + "...")

# JSON response
json_messages = [{"role": "user", "content": "Return JSON operations for this fix"}]
json_response = chat("test-model", json_messages)
print("JSON response:", json_response[:100] + "...")
```

## ☁️ **API Mode Examples**

### **Groq (Free Tier)**
```bash
# Get free API key from https://console.groq.com
export GROQ_API_KEY="gsk_..."

# Test the connection
python -c "
from sentries.chat import chat, has_api_key
print(f'API key detected: {has_api_key()}')

messages = [{'role': 'user', 'content': 'Hello, can you help fix a test?'}]
response = chat('llama3-8b-8192', messages)
print('Groq response:', response[:100] + '...')
"

# Run TestSentry with Groq
python -m sentries.testsentry
```

### **OpenAI**
```bash
# Set OpenAI API key (requires paid account)
export OPENAI_API_KEY="sk-..."

# Test with different models
python -c "
from sentries.chat import chat

# Test with GPT-4
messages = [{'role': 'user', 'content': 'Fix this failing test: assert 1 == 2'}]
response = chat('gpt-4', messages)
print('GPT-4 response:', response[:100] + '...')

# Test with GPT-3.5-turbo (cheaper)
response = chat('gpt-3.5-turbo', messages)
print('GPT-3.5 response:', response[:100] + '...')
"
```

### **Anthropic**
```bash
# Set Anthropic API key (requires paid account)
export ANTHROPIC_API_KEY="sk-ant-..."

# Test with Claude
python -c "
from sentries.chat import chat

messages = [{'role': 'user', 'content': 'Help me fix this test failure'}]
response = chat('claude-3-sonnet', messages)
print('Claude response:', response[:100] + '...')
"
```

### **API Fallback Chain**
```bash
# Set multiple API keys for fallback
export GROQ_API_KEY="gsk_..."
export OPENAI_API_KEY="sk-..."
export ANTHROPIC_API_KEY="sk-ant-..."

# Will try Groq first, then OpenAI, then Anthropic
python -c "
from sentries.chat import chat

messages = [{'role': 'user', 'content': 'Fix this test'}]
response = chat('llama3-8b-8192', messages)  # Groq model
print('Response (Groq priority):', response[:50] + '...')
"
```

## 🤖 **Local LLM Mode Examples**

### **Basic Ollama Setup**
```bash
# Install Ollama (macOS)
brew install ollama

# Or download from https://ollama.ai

# Start Ollama service
ollama serve

# Pull required models
ollama pull llama3.1
ollama pull deepseek-coder

# Verify models are available
ollama list
```

### **Test Local LLM**
```bash
# Clear API keys to force local mode
unset GROQ_API_KEY
unset OPENAI_API_KEY
unset ANTHROPIC_API_KEY
unset SENTRIES_SIMULATION_MODE

# Test connection
python -c "
from sentries.chat import chat, is_simulation_mode, has_api_key

print(f'Simulation mode: {is_simulation_mode()}')
print(f'API key available: {has_api_key()}')
print('Should use local LLM mode')

messages = [{'role': 'user', 'content': 'Fix this test: assert 1 == 2'}]
response = chat('llama3.1', messages)
print('Local LLM response:', response[:100] + '...')
"
```

### **Custom Ollama Configuration**
```bash
# Use custom Ollama server
export LLM_BASE="http://192.168.1.100:11434"

# Test custom server
python -c "
from sentries.chat import chat
messages = [{'role': 'user', 'content': 'Hello'}]
response = chat('llama3.1', messages)
print('Custom server response:', response[:50] + '...')
"
```

## 🔄 **Mode Switching Examples**

### **Dynamic Mode Switching**
```python
import os
from sentries.chat import chat

# Start with simulation
os.environ['SENTRIES_SIMULATION_MODE'] = 'true'
messages = [{"role": "user", "content": "Hello"}]

print("1. Simulation Mode:")
response1 = chat("test-model", messages)
print(f"   Response: {response1[:50]}...")

# Switch to API mode
os.environ.pop('SENTRIES_SIMULATION_MODE', None)
os.environ['GROQ_API_KEY'] = 'your-key-here'

print("2. API Mode:")
response2 = chat("llama3-8b-8192", messages)
print(f"   Response: {response2[:50]}...")

# Switch to local LLM mode
os.environ.pop('GROQ_API_KEY', None)

print("3. Local LLM Mode:")
response3 = chat("llama3.1", messages)
print(f"   Response: {response3[:50]}...")
```

### **Environment-Based Configuration**
```bash
# Create different environment files

# .env.simulation
echo "SENTRIES_SIMULATION_MODE=true" > .env.simulation

# .env.groq
echo "GROQ_API_KEY=your-groq-key" > .env.groq

# .env.openai
echo "OPENAI_API_KEY=your-openai-key" > .env.openai

# Use with different environments
source .env.simulation && python -m sentries.testsentry
source .env.groq && python -m sentries.testsentry
source .env.openai && python -m sentries.testsentry
```

## 🧪 **Testing Examples**

### **Test All Modes**
```bash
# Run comprehensive tests
pytest tests/test_chat_modes.py -v
pytest tests/test_pipeline_integration.py -v
pytest tests/test_ci_integration.py -v

# Test specific functionality
pytest tests/test_chat_modes.py::TestSimulationMode -v
pytest tests/test_pipeline_integration.py::TestModePriority -v
```

### **Performance Testing**
```python
import time
from sentries.chat import chat
import os

# Test simulation mode performance
os.environ['SENTRIES_SIMULATION_MODE'] = 'true'
messages = [{"role": "user", "content": "Fix this test: assert 1 == 2"}]

start_time = time.time()
for i in range(10):
    response = chat("test-model", messages)
end_time = time.time()

avg_time = (end_time - start_time) / 10
print(f"Simulation mode average response time: {avg_time:.4f}s")
```

### **Determinism Testing**
```python
import os
from sentries.chat import chat

# Test determinism in simulation mode
os.environ['SENTRIES_SIMULATION_MODE'] = 'true'
messages = [{"role": "user", "content": "Fix this test: assert 1 == 2"}]

responses = []
for i in range(5):
    response = chat("test-model", messages)
    responses.append(response)

# Check if all responses are identical
all_same = all(r == responses[0] for r in responses)
print(f"All responses identical: {all_same}")
if all_same:
    print("✅ Simulation mode is deterministic")
else:
    print("❌ Simulation mode is not deterministic")
```

## 🛠️ **Troubleshooting Examples**

### **Debug Mode Detection**
```python
import os
from sentries.chat import is_simulation_mode, has_api_key

def debug_mode_detection():
    print("🔍 Debug Mode Detection:")
    print(f"  SENTRIES_SIMULATION_MODE: {os.getenv('SENTRIES_SIMULATION_MODE', 'not set')}")
    print(f"  CI: {os.getenv('CI', 'not set')}")
    print(f"  GROQ_API_KEY: {'set' if os.getenv('GROQ_API_KEY') else 'not set'}")
    print(f"  OPENAI_API_KEY: {'set' if os.getenv('OPENAI_API_KEY') else 'not set'}")
    print(f"  ANTHROPIC_API_KEY: {'set' if os.getenv('ANTHROPIC_API_KEY') else 'not set'}")
    print(f"  LLM_BASE: {os.getenv('LLM_BASE', 'http://localhost:11434')}")
    print()
    print(f"  is_simulation_mode(): {is_simulation_mode()}")
    print(f"  has_api_key(): {has_api_key()}")
    print()
    
    if is_simulation_mode():
        print("  ✅ Will use: SIMULATION MODE")
    elif has_api_key():
        print("  ✅ Will use: API MODE")
    else:
        print("  ✅ Will use: LOCAL LLM MODE")

debug_mode_detection()
```

### **Test API Key Validity**
```python
import os
from sentries.chat import chat

def test_api_key(provider, api_key, model):
    """Test if an API key works."""
    print(f"Testing {provider} API key...")
    
    # Set the API key
    if provider == "groq":
        os.environ['GROQ_API_KEY'] = api_key
    elif provider == "openai":
        os.environ['OPENAI_API_KEY'] = api_key
    elif provider == "anthropic":
        os.environ['ANTHROPIC_API_KEY'] = api_key
    
    # Clear simulation mode
    os.environ.pop('SENTRIES_SIMULATION_MODE', None)
    
    try:
        messages = [{"role": "user", "content": "Hello, this is a test"}]
        response = chat(model, messages)
        print(f"  ✅ {provider} API key works!")
        print(f"  Response: {response[:50]}...")
        return True
    except Exception as e:
        print(f"  ❌ {provider} API key failed: {e}")
        return False
    finally:
        # Clean up
        os.environ.pop(f'{provider.upper()}_API_KEY', None)

# Example usage:
# test_api_key("groq", "gsk_...", "llama3-8b-8192")
# test_api_key("openai", "sk-...", "gpt-3.5-turbo")
```

### **Test Ollama Connection**
```python
import requests
import os

def test_ollama_connection():
    """Test Ollama connection and available models."""
    base_url = os.getenv('LLM_BASE', 'http://localhost:11434')
    
    try:
        # Test connection
        response = requests.get(f"{base_url}/api/tags", timeout=5)
        response.raise_for_status()
        
        models = response.json().get('models', [])
        print(f"✅ Ollama connection successful!")
        print(f"  Base URL: {base_url}")
        print(f"  Available models: {len(models)}")
        
        for model in models:
            print(f"    - {model.get('name', 'unknown')}")
        
        return True
        
    except requests.exceptions.ConnectionError:
        print(f"❌ Cannot connect to Ollama at {base_url}")
        print("  Make sure Ollama is running: ollama serve")
        return False
    except Exception as e:
        print(f"❌ Ollama connection failed: {e}")
        return False

test_ollama_connection()
```

## 📊 **Performance Comparison**

```python
import time
import os
from sentries.chat import chat
from unittest.mock import patch

def performance_comparison():
    """Compare performance across all modes."""
    messages = [{"role": "user", "content": "Fix this test: assert 1 == 2"}]
    results = {}
    
    # Test Simulation Mode
    print("Testing Simulation Mode...")
    os.environ['SENTRIES_SIMULATION_MODE'] = 'true'
    start_time = time.time()
    for _ in range(10):
        response = chat("test-model", messages)
    simulation_time = (time.time() - start_time) / 10
    results['Simulation'] = simulation_time
    
    # Test API Mode (mocked for speed)
    print("Testing API Mode (mocked)...")
    os.environ.pop('SENTRIES_SIMULATION_MODE', None)
    os.environ['OPENAI_API_KEY'] = 'test-key'
    
    with patch('sentries.chat.chat_with_openai') as mock_api:
        mock_api.return_value = "Mocked API response"
        start_time = time.time()
        for _ in range(10):
            response = chat("gpt-4", messages)
        api_time = (time.time() - start_time) / 10
        results['API (mocked)'] = api_time
    
    # Test Local LLM Mode (mocked for speed)
    print("Testing Local LLM Mode (mocked)...")
    os.environ.pop('OPENAI_API_KEY', None)
    
    with patch('sentries.chat.chat_with_ollama') as mock_ollama:
        mock_ollama.return_value = "Mocked Ollama response"
        start_time = time.time()
        for _ in range(10):
            response = chat("llama3.1", messages)
        local_time = (time.time() - start_time) / 10
        results['Local LLM (mocked)'] = local_time
    
    # Print results
    print("\\n📊 Performance Results:")
    for mode, avg_time in results.items():
        print(f"  {mode}: {avg_time:.4f}s average")
    
    return results

# performance_comparison()
```

## 🎯 **Best Practices**

### **1. Mode Selection**
```python
# Choose the right mode for your use case:

# For CI/CD and public repos
os.environ['SENTRIES_SIMULATION_MODE'] = 'true'

# For development with free API
os.environ['GROQ_API_KEY'] = 'your-groq-key'

# For production with best quality
os.environ['OPENAI_API_KEY'] = 'your-openai-key'

# For private development (free)
# Just ensure Ollama is running
```

### **2. Error Handling**
```python
from sentries.chat import chat
import os

def robust_chat(model, messages, fallback_to_simulation=True):
    """Chat with automatic fallback to simulation mode."""
    try:
        return chat(model, messages)
    except Exception as e:
        if fallback_to_simulation:
            print(f"Chat failed ({e}), falling back to simulation mode")
            os.environ['SENTRIES_SIMULATION_MODE'] = 'true'
            return chat(model, messages)
        else:
            raise

# Usage
messages = [{"role": "user", "content": "Hello"}]
response = robust_chat("gpt-4", messages)
```

### **3. Configuration Management**
```python
import os
from dataclasses import dataclass
from typing import Optional

@dataclass
class SentriesConfig:
    """Configuration for Sentries modes."""
    simulation_mode: bool = False
    groq_api_key: Optional[str] = None
    openai_api_key: Optional[str] = None
    anthropic_api_key: Optional[str] = None
    ollama_base_url: str = "http://localhost:11434"
    
    def apply(self):
        """Apply configuration to environment."""
        if self.simulation_mode:
            os.environ['SENTRIES_SIMULATION_MODE'] = 'true'
        
        if self.groq_api_key:
            os.environ['GROQ_API_KEY'] = self.groq_api_key
        
        if self.openai_api_key:
            os.environ['OPENAI_API_KEY'] = self.openai_api_key
        
        if self.anthropic_api_key:
            os.environ['ANTHROPIC_API_KEY'] = self.anthropic_api_key
        
        os.environ['LLM_BASE'] = self.ollama_base_url

# Usage
config = SentriesConfig(simulation_mode=True)
config.apply()
```

This comprehensive guide should help you use Sentries effectively in any environment!
