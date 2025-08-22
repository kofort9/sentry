#!/usr/bin/env python3
"""
Test the full TestSentry workflow locally.
"""

import os
import sys
from pathlib import Path

# Add the current directory to sys.path
sys.path.insert(0, str(Path(__file__).parent))

from sentries.testsentry import plan_test_fixes, generate_test_patch

def test_full_workflow():
    """Test the full TestSentry workflow: planning + patch generation."""
    
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
    
    print("🧪 Testing full TestSentry workflow...")
    print(f"📝 Context length: {len(context)}")
    
    try:
        # Step 1: Planning
        print(f"\n🔍 Step 1: Planning with model: llama3.1:8b-instruct-q4_K_M")
        plan = plan_test_fixes(context)
        
        if not plan:
            print("❌ FAILED: No plan generated")
            return False
            
        print(f"✅ Planning successful (length: {len(plan)}):")
        print(f"📄 Plan: {plan}")
        
        # Step 2: Patch Generation
        print(f"\n🔍 Step 2: Generating patch with model: deepseek-coder:6.7b-instruct-q5_K_M")
        patch = generate_test_patch(plan, context)
        
        if not patch:
            print("❌ FAILED: No patch generated")
            return False
            
        print(f"✅ Patch generation successful (length: {len(patch)}):")
        print(f"📄 Patch: {patch}")
        
        print("🎉 SUCCESS: Full TestSentry workflow is working!")
        return True
            
    except Exception as e:
        print(f"❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_full_workflow()
    sys.exit(0 if success else 1)
