#!/usr/bin/env python3
"""
TestSentry CAMEL Edition: Multi-agent test fixing with CAMEL framework.

This module implements the CAMEL-based multi-agent architecture while
preserving all safety guardrails and core functionality from the original TestSentry.
"""

import json
import subprocess
import time
from typing import Any, Dict, Optional

from .banner import show_sentry_banner
from .camel_agents import CAMELCoordinator
from .diff_utils import apply_unified_diff
from .git_utils import get_base_branch
from .runner_common import (
    MODEL_PATCH,
    MODEL_PLAN,
    exit_noop,
    exit_success,
    get_logger,
    validate_environment,
)

# Import observability hooks
try:
    from packages.metrics_core.observability import (
        get_observability,
        save_observability_metrics,
    )

    OBSERVABILITY_AVAILABLE = True
except ImportError:
    OBSERVABILITY_AVAILABLE = False

    def save_observability_metrics() -> None:
        pass

    def get_observability() -> None:
        return None


logger = get_logger(__name__)


def discover_test_failures() -> Optional[str]:
    """
    Discover failing tests by running pytest or using pre-captured output.

    Returns:
        pytest output if there are failures, None if all tests pass
    """
    # Check if we have pre-captured test failure output from CI
    try:
        with open("pytest-output.txt", "r") as f:
            output = f.read()

        if "FAILED" in output or "ERROR" in output or "AssertionError" in output:
            logger.info("Found test failures in pre-captured output")
            return output
        else:
            logger.info("No test failures found in pre-captured output")
            return None
    except FileNotFoundError:
        logger.info("No pre-captured output found, running pytest...")
    except Exception as e:
        logger.warning(f"Error reading pre-captured output: {e}")

    # Fall back to running pytest directly
    try:
        logger.info("Running pytest to discover test failures...")
        result = subprocess.run(
            ["python", "-m", "pytest", "tests/", "sentries/", "--tb=short", "-q"],
            capture_output=True,
            text=True,
            timeout=300,  # 5 minutes timeout
        )

        if result.returncode == 0:
            logger.info("All tests are passing")
            return None

        # Check if there are actual test failures (not just collection errors)
        output = result.stdout + result.stderr
        if "FAILED" in output or "ERROR" in output or "AssertionError" in output:
            logger.info(f"Found test failures: {result.returncode} tests failed")
            return output
        else:
            logger.info("No test failures found, only collection issues")
            return None

    except subprocess.TimeoutExpired:
        logger.error("pytest timed out")
        return None
    except Exception as e:
        logger.error(f"Error running pytest: {e}")
        return None


def apply_and_verify_patch(unified_diff: str, test_file_path: str) -> tuple[bool, str]:
    """
    Apply patch and verify with pytest.

    Args:
        unified_diff: The unified diff string to apply
        test_file_path: Path to test file being modified

    Returns:
        (success, feedback) - whether patch succeeded and any feedback
    """
    logger.info("🔧 Applying CAMEL-generated unified diff...")

    try:
        # Apply the diff using our existing diff utilities
        success = apply_unified_diff(".", unified_diff)

        if not success:
            logger.error("❌ Failed to apply unified diff")
            return False, "Failed to apply unified diff"

        logger.info("✅ Unified diff applied successfully")

        # Verify the changes work by running pytest
        logger.info("🧪 Running pytest to verify CAMEL fixes...")

        # Run pytest on the specific test file
        result = subprocess.run(
            ["python", "-m", "pytest", test_file_path, "-v"],
            capture_output=True,
            text=True,
            cwd=".",
        )

        if result.returncode == 0:
            logger.info("✅ Pytest passed - CAMEL patch fixes working correctly")
            return True, "CAMEL patch applied and tests passing"
        else:
            logger.warning("⚠️ Pytest failed after CAMEL patch application")
            logger.info(f"Pytest output:\n{result.stdout}\n{result.stderr}")

            # Rollback the changes
            logger.info("🔄 Rolling back failed CAMEL patch...")
            subprocess.run(["git", "checkout", "--", test_file_path], cwd=".")

            return False, f"Tests still failing after CAMEL patch: {result.stderr}"

    except Exception as e:
        logger.error(f"❌ Error during CAMEL patch application: {e}")
        return False, f"CAMEL patch application error: {e}"


def create_structured_log_entry(workflow_history: Dict[str, Any]) -> Dict[str, Any]:
    """
    Create structured log entry for CAMEL agent interactions.

    Args:
        workflow_history: Workflow history from CAMELCoordinator

    Returns:
        Structured log data for observability
    """
    return {
        "framework": workflow_history.get("framework", "CAMEL"),
        "version": workflow_history.get("version", "Phase1"),
        "workflow_duration": workflow_history.get("duration_seconds", 0),
        "agents_used": [agent["name"] for agent in workflow_history.get("agents", [])],
        "total_interactions": workflow_history.get("total_interactions", 0),
        "start_time": workflow_history.get("start_time"),
        "end_time": workflow_history.get("end_time"),
        "success_metrics": {
            "planner_interactions": next(
                (
                    agent["interactions"]
                    for agent in workflow_history.get("agents", [])
                    if agent["name"] == "planner"
                ),
                0,
            ),
            "patcher_interactions": next(
                (
                    agent["interactions"]
                    for agent in workflow_history.get("agents", [])
                    if agent["name"] == "patcher"
                ),
                0,
            ),
        },
    }


def create_camel_pr(
    plan: Dict[str, Any], test_file_path: str, workflow_summary: Dict[str, Any]
) -> None:
    """
    Create a pull request with CAMEL-generated fix and detailed metadata.

    Args:
        plan: Plan generated by PlannerAgent
        test_file_path: Path to the test file that was modified
        workflow_summary: Structured summary of the CAMEL workflow
    """
    logger.info("🚀 Creating PR with CAMEL-generated fix...")

    try:
        # Create a new branch for the fix
        fix_branch = f"camel-test-fix-{int(time.time())}"
        subprocess.run(["git", "checkout", "-b", fix_branch], cwd=".")

        # Extract plan summary
        plan_summary = plan.get("plan", "Fix failing tests")
        if isinstance(plan_summary, dict):
            plan_summary = plan_summary.get("raw", "Fix failing tests")

        # Commit the fix
        subprocess.run(["git", "add", test_file_path], cwd=".")
        commit_message = (
            f"fix: {plan_summary}\n\nApplied by TestSentry CAMEL using multi-agent workflow"
        )
        subprocess.run(["git", "commit", "-m", commit_message], cwd=".")

        # Push the fix branch
        subprocess.run(["git", "push", "origin", fix_branch], cwd=".")

        # Create PR using GitHub CLI
        pr_title = f"🐫 CAMEL Test Fix: {plan_summary}"
        pr_body = f"""## CAMEL Multi-Agent Test Fix

**Plan:** {plan_summary}

**Files Modified:** {test_file_path}

**Agent Workflow:**
- **Framework**: CAMEL (Phase 1)
- **Planner Agent**: Analyzed test failures and created structured plan
- **Patcher Agent**: Generated JSON operations and unified diff
- **Validation**: Automated validation and iterative refinement

**Workflow Summary:**
```json
{json.dumps(workflow_summary, indent=2)}
```

**Verification:** ✅ Tests now pass after CAMEL fix

**Generated by:** TestSentry CAMEL Edition with resource-conscious
multi-agent coordination

---
*This PR was automatically created by TestSentry CAMEL after intelligent
multi-agent analysis and fix generation.*"""

        # Try to create PR using GitHub CLI
        try:
            base_branch = get_base_branch()
            result = subprocess.run(
                [
                    "gh",
                    "pr",
                    "create",
                    "--title",
                    pr_title,
                    "--body",
                    pr_body,
                    "--base",
                    base_branch,
                    "--head",
                    fix_branch,
                ],
                capture_output=True,
                text=True,
                cwd=".",
            )

            if result.returncode == 0:
                logger.info("🎉 CAMEL PR created successfully!")
                logger.info(f"PR URL: {result.stdout.strip()}")
            else:
                logger.warning("⚠️ GitHub CLI failed, branch pushed for manual PR creation")
                logger.info(f"Branch pushed: {fix_branch}")
                logger.info(f"PR body:\n{pr_body}")

        except FileNotFoundError:
            logger.warning("⚠️ GitHub CLI not available, branch pushed for manual PR creation")
            logger.info(f"Branch pushed: {fix_branch}")
            logger.info(f"PR body:\n{pr_body}")

    except Exception as e:
        logger.error(f"Error creating CAMEL PR: {e}")
        logger.info("Manual PR creation may be needed")


def main() -> None:
    """Main TestSentry CAMEL function."""
    show_sentry_banner()
    print("🐫 TestSentry CAMEL Edition - Multi-Agent Test Fixing")
    print("=" * 60)
    print("Phase 1: Resource-Conscious 2-Agent Workflow")
    print()

    logger.info("🚀 TestSentry CAMEL starting with multi-agent coordination...")

    # Validate environment
    if not validate_environment():
        exit_noop("Environment validation failed")

    # Discover test failures
    failing_tests = discover_test_failures()
    if not failing_tests:
        exit_success("No test failures detected")

    logger.info("❌ Test failures detected, starting CAMEL multi-agent workflow...")

    # Initialize CAMEL coordinator with our models
    coordinator = CAMELCoordinator(planner_model=str(MODEL_PLAN), patcher_model=str(MODEL_PATCH))

    # Process test failures using CAMEL agents
    logger.info("🤖 Starting CAMEL 2-agent coordination...")
    result = coordinator.process_test_failures(failing_tests)

    # Create structured log entry for observability
    workflow_history = result.get("workflow_history", {})
    structured_log = create_structured_log_entry(workflow_history)
    logger.info(f"📊 CAMEL Workflow Summary: {json.dumps(structured_log, indent=2)}")

    if not result.get("success"):
        error_msg = result.get("error", "Unknown error in CAMEL workflow")
        logger.error(f"❌ CAMEL workflow failed: {error_msg}")
        exit_noop(f"CAMEL agent workflow failed: {error_msg}")

    # Extract results
    unified_diff = result.get("unified_diff")
    if not unified_diff:
        exit_noop("No unified diff generated by CAMEL agents")

    logger.info("✅ CAMEL agents successfully generated patch")

    # Determine the test file to apply patch to
    try:
        json_operations = result.get("json_operations", "{}")
        operations_data = json.loads(json_operations)
        ops = operations_data.get("ops", [])

        if ops and len(ops) > 0:
            test_file_path = ops[0].get("file", "tests/")
        else:
            test_file_path = "tests/"
    except (json.JSONDecodeError, Exception):
        test_file_path = "tests/"

    # Apply and verify the CAMEL-generated patch
    logger.info("🔨 Applying CAMEL-generated patch...")
    success, feedback = apply_and_verify_patch(unified_diff, test_file_path)

    if not success:
        logger.error(f"❌ CAMEL patch application failed: {feedback}")
        exit_noop(f"CAMEL patch application failed: {feedback}")

    logger.info("🎉 CAMEL patch applied and verified successfully!")

    # Create PR with comprehensive CAMEL metadata
    plan = result.get("plan", {})
    create_camel_pr(plan, test_file_path, structured_log)

    # Save observability metrics before exiting
    if OBSERVABILITY_AVAILABLE:
        logger.info("💾 Saving observability metrics...")
        save_observability_metrics()

        # Get and log summary metrics
        obs = get_observability()
        if obs:
            summary = obs.get_summary_metrics()
            logger.info(f"📊 Observability Summary: {summary}")

    exit_success("CAMEL multi-agent test fix applied and PR created successfully")


if __name__ == "__main__":
    main()
