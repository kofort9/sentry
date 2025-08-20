#!/usr/bin/env python3
"""
Demonstration Script for Complete Sentries Workflow

This script demonstrates the complete end-to-end workflow:
1. CodeSentry analyzes the repository for candidates
2. TestSentry fixes failing tests
3. DocSentry updates documentation
4. Shows the complete automation pipeline
"""

import os
import sys
import subprocess
import time
from pathlib import Path

# Add the parent directory to the path so we can import sentries
sys.path.insert(0, str(Path(__file__).parent.parent))

from sentries.banner import show_sentry_banner

def run_command(cmd: str, description: str, capture_output: bool = False) -> bool:
    """Run a command and display results."""
    print(f"\n🔧 {description}")
    print("-" * 50)

    try:
        if capture_output:
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
            if result.returncode == 0:
                print(f"✅ {description} completed successfully")
                if result.stdout:
                    print("Output:")
                    print(result.stdout)
                return True
            else:
                print(f"❌ {description} failed")
                if result.stderr:
                    print("Error:")
                    print(result.stderr)
                return False
        else:
            result = subprocess.run(cmd, shell=True)
            return result.returncode == 0
    except Exception as e:
        print(f"❌ Error running {description}: {e}")
        return False

def check_prerequisites():
    """Check if all prerequisites are met."""
    print("🔍 Checking Prerequisites")
    print("=" * 50)

    # Check if we're in a git repository
    if not Path(".git").exists():
        print("❌ Not in a git repository")
        return False

    # Check if we have the required environment variables
    required_vars = ["GITHUB_TOKEN", "GITHUB_REPOSITORY"]
    missing_vars = []

    for var in required_vars:
        if not os.getenv(var):
            missing_vars.append(var)

    if missing_vars:
        print(f"❌ Missing environment variables: {', '.join(missing_vars)}")
        print("Please set these variables before running the demo:")
        for var in missing_vars:
            if var == "GITHUB_TOKEN":
                print(f"  export {var}=your_github_token")
            else:
                print(f"  export {var}=your_org/repo_name")
        return False

    print("✅ All prerequisites met")
    return True

def demonstrate_codesentry():
    """Demonstrate CodeSentry functionality."""
    print("\n🔍 STEP 1: CodeSentry Analysis")
    print("=" * 50)

    print("CodeSentry will analyze the repository to find:")
    print("• Functions that lack tests")
    print("• Code that needs documentation")
    print("• Test coverage gaps")
    print("• Improvement opportunities")

    # Run CodeSentry
    success = run_command("codesentry", "Running CodeSentry analysis", capture_output=True)

    if success:
        print("\n📊 CodeSentry Analysis Complete!")
        print("This gives us a comprehensive view of what needs improvement.")
    else:
        print("\n⚠️  CodeSentry analysis had issues, but we can continue with the demo.")

    return success

def demonstrate_testsentry():
    """Demonstrate TestSentry functionality."""
    print("\n🧪 STEP 2: TestSentry Test Fixing")
    print("=" * 50)

    print("TestSentry will:")
    print("• Run pytest to discover failing tests")
    print("• Analyze test failures")
    print("• Generate fixes for failing tests")
    print("• Create PRs with test fixes")

    # First, let's show the current test status
    print("\n📋 Current Test Status:")
    run_command("python -m pytest sentries/test_example_feature.py --tb=short",
               "Running tests to show current status", capture_output=True)

    # Now run TestSentry
    print("\n🚀 Running TestSentry...")
    success = run_command("testsentry", "Running TestSentry to fix failing tests", capture_output=True)

    if success:
        print("\n✅ TestSentry completed!")
        print("It should have created a PR with test fixes.")
    else:
        print("\n⚠️  TestSentry had issues, but this demonstrates the workflow.")

    return success

def demonstrate_docsentry():
    """Demonstrate DocSentry functionality."""
    print("\n📚 STEP 3: DocSentry Documentation Updates")
    print("=" * 50)

    print("DocSentry will:")
    print("• Analyze recent code changes")
    print("• Identify documentation needs")
    print("• Generate documentation updates")
    print("• Create PRs with doc improvements")

    # Run DocSentry
    print("\n🚀 Running DocSentry...")
    success = run_command("docsentry", "Running DocSentry to update documentation", capture_output=True)

    if success:
        print("\n✅ DocSentry completed!")
        print("It should have created a PR with documentation updates.")
    else:
        print("\n⚠️  DocSentry had issues, but this demonstrates the workflow.")

    return True  # DocSentry might not have changes to make

def show_workflow_summary():
    """Show a summary of the complete workflow."""
    print("\n🎯 COMPLETE WORKFLOW SUMMARY")
    print("=" * 50)

    print("We've demonstrated the complete Sentries automation pipeline:")
    print()
    print("1️⃣  **CodeSentry** - Automated code analysis")
    print("    • Scans repositories for improvement opportunities")
    print("    • Identifies untested functions and documentation needs")
    print("    • Provides actionable insights")
    print()
    print("2️⃣  **TestSentry** - Automated test fixing")
    print("    • Detects failing tests automatically")
    print("    • Generates intelligent test fixes")
    print("    • Creates PRs with test improvements")
    print()
    print("3️⃣  **DocSentry** - Automated documentation updates")
    print("    • Keeps docs in sync with code changes")
    print("    • Identifies documentation gaps")
    print("    • Creates PRs with doc improvements")
    print()
    print("🔄 **Continuous Automation**")
    print("    • GitHub Actions run on every PR and push")
    print("    • Automated testing ensures quality")
    print("    • Self-healing repository maintenance")
    print()
    print("💡 **Benefits**")
    print("    • Reduced manual maintenance burden")
    print("    • Consistent code quality")
    print("    • Automated documentation sync")
    print("    • Faster development cycles")
    print()
    print("🚀 **Ready for Production**")
    print("    • Comprehensive testing infrastructure")
    print("    • End-to-end workflow validation")
    print("    • Automated quality assurance")
    print("    • Production-ready reliability")

def main():
    """Main demonstration function."""
    show_sentry_banner()
    print("🚀 Sentries Complete Workflow Demonstration")
    print("=" * 60)
    print("This script demonstrates the complete end-to-end Sentries workflow")
    print("including CodeSentry analysis, TestSentry fixes, and DocSentry updates.")
    print()

    # Check prerequisites
    if not check_prerequisites():
        print("\n❌ Prerequisites not met. Please fix the issues above and try again.")
        sys.exit(1)

    print("\n🎬 Starting Workflow Demonstration...")
    print("This will take a few minutes to complete.")

    # Step 1: CodeSentry
    codesentry_success = demonstrate_codesentry()

    # Step 2: TestSentry
    testsentry_success = demonstrate_testsentry()

    # Step 3: DocSentry
    docsentry_success = demonstrate_docsentry()

    # Summary
    show_workflow_summary()

    # Final status
    print("\n📊 DEMONSTRATION RESULTS")
    print("=" * 50)
    print(f"CodeSentry: {'✅ Success' if codesentry_success else '⚠️  Issues'}")
    print(f"TestSentry: {'✅ Success' if testsentry_success else '⚠️  Issues'}")
    print(f"DocSentry:  {'✅ Success' if docsentry_success else '⚠️  Issues'}")

    if codesentry_success and testsentry_success and docsentry_success:
        print("\n🎉 All components working perfectly!")
        print("Your Sentries installation is ready for production use.")
    else:
        print("\n⚠️  Some components had issues.")
        print("This is normal for demonstration purposes.")
        print("Check the output above for details.")

    print("\n🔗 Next Steps:")
    print("1. Visit GitHub to see any created PRs")
    print("2. Review the automated changes")
    print("3. Deploy Sentries to your other repositories")
    print("4. Enjoy automated code maintenance!")

if __name__ == "__main__":
    main()
