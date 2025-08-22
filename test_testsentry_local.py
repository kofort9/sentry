#!/usr/bin/env python3
"""
Test TestSentry locally with the fixed chat function.
"""

import os
import sys
from pathlib import Path

# Add the current directory to sys.path
sys.path.insert(0, str(Path(__file__).parent))

from sentries.testsentry import plan_test_fixes

def test_testsentry_planning():
    """Test TestSentry's planning function with a simple test failure."""
    
    # Set environment variables
    os.environ['LLM_BASE'] = 'http://127.0.0.1:11434'
    
    # Create a simple test failure context
    context = """Test failures detected:

FAILED sentries/test_example_feature.py::test_guaranteed_failure - AssertionError: This will always fail: 1 + 1 = 2, not 999
assert 2 == 999

Relevant test files and content:

=== sentries/test_example_feature.py ===
def test_guaranteed_failure():
    # This test is intentionally failing to trigger TestSentry
    # TestSentry should fix this by changing the assertion
    result = 1 + 1
    assert result == 999, f"This will always fail: 1 + 1 = {result}, not 999"
"""
    
    print("🧪 Testing TestSentry planning function...")
    print(f"📝 Context length: {len(context)}")
    print(f"📄 Context preview: {context[:200]}...")
    
    try:
        # Test the planning function
        print(f"\n🔍 Testing with model: llama3.1:8b-instruct-q4_K_M")
        plan = plan_test_fixes(context)
        
        if plan:
            print(f"✅ Planning successful (length: {len(plan)}):")
            print(f"📄 Plan: {plan}")
            print("🎉 SUCCESS: TestSentry planning is working!")
            return True
        else:
            print("❌ FAILED: No plan generated")
            return False
            
    except Exception as e:
        print(f"❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_testsentry_planning()
    sys.exit(0 if success else 1)
