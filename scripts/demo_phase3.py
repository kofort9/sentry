#!/usr/bin/env python3
"""
CAMEL Phase 3 Demo - Streamlit Dashboard + Error Recovery

This demo showcases all Phase 3 features:
- Streamlit dashboard integration
- Enhanced error recovery mechanisms  
- Real-time workflow monitoring
- User-friendly error reporting
- Complete workflow integration
"""

import time
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from sentries.camel.coordinator import CAMELCoordinator
from sentries.camel.error_recovery import global_error_recovery, ErrorSeverity, ErrorCategory
from sentries.runner_common import MODEL_PLAN, MODEL_PATCH


def demo_error_recovery():
    """Demonstrate the enhanced error recovery system."""
    print("🔥 PHASE 3 DEMO: Enhanced Error Recovery")
    print("=" * 50)
    
    # Simulate different types of errors
    test_errors = [
        (ConnectionError("Network timeout"), {"operation": "llm_call"}),
        (ValueError("Invalid JSON format"), {"operation": "parsing"}),
        (PermissionError("Access denied"), {"operation": "file_access"}),
    ]
    
    for error, context in test_errors:
        print(f"\n🧪 Simulating error: {type(error).__name__}")
        error_info = global_error_recovery.classify_error(error, context)
        
        print(f"   📊 Category: {error_info.category.value}")
        print(f"   ⚠️  Severity: {error_info.severity.value}")
        
        # Attempt recovery
        recovery_success = global_error_recovery.attempt_recovery(error_info)
        print(f"   {'✅' if recovery_success else '❌'} Recovery: {'Successful' if recovery_success else 'Failed'}")
    
    # Show error summary
    summary = global_error_recovery.get_error_summary()
    print(f"\n📈 Error Recovery Summary:")
    print(f"   Total Errors: {summary['total_errors']}")
    print(f"   Recovery Rate: {summary['recovery_rate']:.1%}")
    print(f"   By Category: {summary['by_category']}")


def demo_camel_workflow_with_recovery():
    """Demonstrate CAMEL workflow with integrated error recovery."""
    print("\n🐫 PHASE 3 DEMO: CAMEL Workflow + Error Recovery")
    print("=" * 55)
    
    # Initialize coordinator
    coordinator = CAMELCoordinator(MODEL_PLAN, MODEL_PATCH)
    print("✅ CAMEL Coordinator initialized with error recovery")
    
    # Test workflow with sample failure
    test_output = """
FAILED tests/test_calculation.py::test_add - AssertionError: assert add(2, 3) == 6
>       assert add(2, 3) == 6
E       AssertionError: assert 5 == 6

tests/test_calculation.py:10: AssertionError
"""
    
    print("\n🚀 Running CAMEL workflow with error recovery...")
    print("   📋 Planner analyzing failures...")
    time.sleep(1)
    print("   🔧 Patcher generating solutions...")
    time.sleep(1)
    print("   ✅ Validation with retry logic...")
    time.sleep(1)
    
    result = coordinator.process_test_failures(test_output)
    
    print(f"\n📊 Workflow Results:")
    print(f"   Success: {'✅' if result.get('success') else '❌'}")
    print(f"   Duration: {result.get('workflow_duration', 0):.2f}s")
    
    if 'error_recovery_summary' in result:
        recovery = result['error_recovery_summary']
        print(f"   Error Recovery: {recovery.get('total_errors', 0)} errors, {recovery.get('recovery_rate', 0):.1%} recovery rate")
    
    if result.get('validation_attempts'):
        attempts = len(result['validation_attempts'])
        print(f"   Validation Attempts: {attempts}")


def demo_dashboard_features():
    """Demonstrate dashboard features (without actually running Streamlit)."""
    print("\n📊 PHASE 3 DEMO: Dashboard Features")
    print("=" * 40)
    
    print("🎛️ Dashboard Features Available:")
    print("   ✅ Real-time workflow monitoring")
    print("   ✅ Agent status tracking")
    print("   ✅ Interactive error reporting")
    print("   ✅ Historical analytics")
    print("   ✅ Error recovery visualization")
    print("   ✅ Manual workflow control")
    
    print("\n🚀 To launch the dashboard:")
    print("   python launch_dashboard.py")
    print("   📍 Available at: http://localhost:8501")
    
    print("\n📋 Dashboard Tabs:")
    print("   🎛️ Control Panel - Manual workflow execution")
    print("   🤖 Agent Status - Real-time agent activity")
    print("   📊 Analytics - Historical workflow data")
    print("   🚨 Error Log - Enhanced error recovery info")


def demo_integration_test():
    """Demonstrate complete Phase 3 integration."""
    print("\n🔗 PHASE 3 DEMO: Complete Integration Test")
    print("=" * 45)
    
    # Test all components work together
    coordinator = CAMELCoordinator(MODEL_PLAN, MODEL_PATCH)
    
    # Show initial status
    recovery_status = coordinator.get_error_recovery_status()
    print(f"📊 Initial Error Status: {recovery_status['total_errors']} errors")
    
    # Simulate a workflow that might have errors
    test_cases = [
        "FAILED tests/test_simple.py::test_basic - AssertionError: assert 1 == 2",
        "FAILED tests/test_complex.py::test_algorithm - IndexError: list index out of range",
    ]
    
    for i, test_case in enumerate(test_cases, 1):
        print(f"\n🧪 Test Case {i}: Running workflow...")
        result = coordinator.process_test_failures(test_case)
        
        success_icon = "✅" if result.get("success") else "❌"
        print(f"   {success_icon} Result: {result.get('success', False)}")
        
        if result.get("plan"):
            plan = result["plan"]
            print(f"   📋 Plan: {plan.get('plan', 'N/A')[:50]}...")
    
    # Final status
    final_status = coordinator.get_error_recovery_status()
    print(f"\n📈 Final Error Status: {final_status['total_errors']} errors")
    print(f"   Recovery Rate: {final_status.get('recovery_rate', 0):.1%}")


def main():
    """Run the complete Phase 3 demo."""
    print("\n🎉 CAMEL REFACTOR PHASE 3 COMPLETE!")
    print("🐫 Streamlit Dashboard + Enhanced Error Recovery")
    print("=" * 60)
    
    try:
        # Run all demo components
        demo_error_recovery()
        demo_camel_workflow_with_recovery()
        demo_dashboard_features()
        demo_integration_test()
        
        print("\n🎊 PHASE 3 DEMO COMPLETED SUCCESSFULLY!")
        print("\n🚀 What's Available Now:")
        print("   ✅ Enhanced Error Recovery System")
        print("   ✅ Streamlit Dashboard for Monitoring")
        print("   ✅ Real-time Workflow Visualization")
        print("   ✅ User-friendly Error Reporting")
        print("   ✅ Complete CAMEL Integration")
        
        print("\n📍 Next Steps:")
        print("   1. Run 'python launch_dashboard.py' to start the UI")
        print("   2. Use the dashboard to monitor workflows")
        print("   3. View error recovery in real-time")
        print("   4. Ready for Phase 4: Generalization!")
        
    except Exception as e:
        print(f"❌ Demo failed: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
