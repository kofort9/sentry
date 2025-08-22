#!/usr/bin/env python3
"""
DocSentry: Keeps docs in sync by proposing docs-only patches.
"""
import os
import json

import subprocess
from typing import Dict, Optional, Tuple
from .runner_common import (
    setup_logging, get_logger, validate_environment, get_short_sha,
    exit_success, exit_noop, exit_failure, DOCS_ALLOWLIST,
    MODEL_PLAN, MODEL_PATCH, GITHUB_EVENT_PATH
)
from .chat import chat, get_default_params
from .prompts import PLANNER_DOCS, PATCHER_DOCS
from .diff_utils import validate_unified_diff, apply_unified_diff, extract_diff_summary
from .git_utils import (
    create_branch, commit_all, open_pull_request, label_pull_request,
    get_base_branch
)

logger = get_logger(__name__)


def read_github_event() -> Optional[Dict]:
    """
    Read and parse the GitHub event payload.

    Returns:
        Parsed event data or None if not available
    """
    if not GITHUB_EVENT_PATH or not os.path.exists(GITHUB_EVENT_PATH):
        logger.warning("GitHub event file not found")
        return None

    try:
        with open(GITHUB_EVENT_PATH, 'r') as f:
            event_data = json.load(f)

        logger.info(f"Read GitHub event: {event_data.get('action', 'unknown')}")
        return event_data

    except Exception as e:
        logger.error(f"Error reading GitHub event: {e}")
        return None


def get_pr_context(event_data: Dict) -> Optional[Tuple[str, str, str]]:
    """
    Extract PR context from GitHub event data.

    Args:
        event_data: GitHub event payload

    Returns:
        Tuple of (title, body, diff_summary) or None
    """
    try:
        if event_data.get("action") != "opened":
            logger.info("PR not opened, skipping")
            return None

        pr = event_data.get("pull_request", {})
        title = pr.get("title", "")
        body = pr.get("body", "")

        # Get diff summary
        diff_summary = get_diff_summary()

        if not title or not diff_summary:
            logger.warning("Missing PR title or diff")
            return None

        logger.info(f"PR: {title}")
        return title, body, diff_summary

    except Exception as e:
        logger.error(f"Error extracting PR context: {e}")
        return None


def get_diff_summary() -> Optional[str]:
    """
    Get a summary of changes in the current PR.

    Returns:
        Diff summary string or None
    """
    try:
        # Get the base branch
        base_branch = get_base_branch()

        # Get list of changed files
        result = subprocess.run(
            ['git', 'di', '--name-status', f'origin/{base_branch}...HEAD'],
            capture_output=True,
            text=True,
            timeout=30
        )

        if result.returncode != 0:
            logger.error(f"Failed to get diff: {result.stderr}")
            return None

        changed_files = []
        for line in result.stdout.strip().split('\n'):
            if line.strip():
                status, file_path = line.split('\t', 1)
                changed_files.append(f"{status} {file_path}")

        if not changed_files:
            logger.info("No files changed")
            return None

        # Get actual diff content (limited to avoid context overflow)
        diff_result = subprocess.run(
            ['git', 'di', '--stat', f'origin/{base_branch}...HEAD'],
            capture_output=True,
            text=True,
            timeout=30
        )

        diff_summary = ""
        if diff_result.returncode == 0:
            diff_summary = diff_result.stdout

        return "Changed files:\n" + "\n".join(changed_files) + f"\n\nDiff summary:\n{diff_summary}"

    except Exception as e:
        logger.error(f"Error getting diff summary: {e}")
        return None


def plan_doc_updates(title: str, body: str, diff_summary: str) -> Optional[str]:
    """
    Use the planner model to plan documentation updates.

    Args:
        title: PR title
        body: PR body
        diff_summary: Summary of code changes

    Returns:
        Planning response from the LLM
    """
    try:
        params = get_default_params("planner")

        context = """PR Title: {title}

PR Description:
{body}

Code Changes:
{diff_summary}

Please analyze these changes and propose minimal documentation updates to keep docs in sync."""

        messages = [
            {"role": "system", "content": PLANNER_DOCS},
            {"role": "user", "content": context}
        ]

        logger.info("Planning documentation updates with LLM...")
        response = chat(
            model=MODEL_PLAN,
            messages=messages,
            **params
        )

        logger.info("Documentation planning completed")
        return response

    except Exception as e:
        logger.error(f"Error during documentation planning: {e}")
        return None


def generate_doc_patch(plan: str, context: str) -> Optional[str]:
    """
    Use the patcher model to generate a documentation patch.

    Args:
        plan: The planning response
        context: PR context and diff summary

    Returns:
        Unified diff string or None if ABORT
    """
    try:
        params = get_default_params("patcher")

        messages = [
            {"role": "system", "content": PATCHER_DOCS},
            {"role": "user", "content": f"Plan: {plan}\n\nContext: {context}"}
        ]

        logger.info("Generating documentation patch with LLM...")
        response = chat(
            model=MODEL_PATCH,
            messages=messages,
            **params
        )

        if "ABORT" in response.upper():
            logger.info("LLM patcher returned ABORT")
            return None

        logger.info("Documentation patch generation completed")
        return response

    except Exception as e:
        logger.error(f"Error during patch generation: {e}")
        return None


def apply_doc_patch(diff_str: str) -> bool:
    """
    Apply the documentation patch.

    Args:
        diff_str: The unified diff to apply

    Returns:
        True if successful, False otherwise
    """
    try:
        # Validate the diff
        is_valid, reason = validate_unified_diff(diff_str, DOCS_ALLOWLIST)
        if not is_valid:
            logger.error(f"Invalid diff: {reason}")
            return False

        # Apply the diff
        if not apply_unified_diff(".", diff_str):
            logger.error("Failed to apply diff")
            return False

        logger.info("Documentation patch applied successfully")
        return True

    except Exception as e:
        logger.error(f"Error applying documentation patch: {e}")
        return False


def create_doc_update_pr(plan: str, diff_summary: str) -> Optional[int]:
    """
    Create a pull request for the documentation updates.

    Args:
        plan: The planning response
        diff_summary: Summary of what the diff changes

    Returns:
        PR number if successful, None otherwise
    """
    try:
        short_sha = get_short_sha()
        base_branch = get_base_branch()

        # Create branch
        branch_name = create_branch("ai-doc-updates", sentry_type="docsentry")

        # Commit changes
        commit_message = f"DocSentry: docs for {short_sha}\n\n{plan}"
        if not commit_all(commit_message):
            raise RuntimeError("Failed to commit changes")

        # Create PR
        title = f"DocSentry: docs for {short_sha}"
        body = """## Documentation Updates

**Plan:**
{plan}

**Changes:**
{diff_summary}

**Generated by:** DocSentry AI
**Branch:** {branch_name}
"""

        pr_number = open_pull_request(base_branch, branch_name, title, body, "docsentry")
        if pr_number:
            logger.info(f"Created PR #{pr_number} for documentation updates")
            return pr_number
        else:
            raise RuntimeError("Failed to create PR")

    except Exception as e:
        logger.error(f"Error creating documentation update PR: {e}")
        return None


def label_feature_pr(pr_number: int, success: bool = True) -> None:
    """
    Label the feature PR that triggered this action.

    Args:
        pr_number: PR number to label
        success: Whether the documentation updates were successful
    """
    try:
        label = "docs-sentry:done" if success else "docs-sentry:noop"
        if label_pull_request(pr_number, [label]):
            logger.info(f"Labeled feature PR with: {label}")
        else:
            logger.warning(f"Failed to label feature PR with: {label}")
    except Exception as e:
        logger.error(f"Error labeling feature PR: {e}")


def show_sentries_banner():
    """Display the Sentry ASCII art banner."""
    from sentries.banner import show_sentry_banner
    show_sentry_banner()
    print("📚 DocSentry - AI-Powered Documentation Updates")
    print("=" * 50)
    print()


def main() -> None:
    """Main entry point for DocSentry."""
    show_sentries_banner()
    setup_logging()
    logger.info("DocSentry starting...")

    # Validate environment
    if not validate_environment():
        exit_failure("Environment validation failed")

    # Check if we're in a git repository
    if not os.path.exists(".git"):
        exit_failure("Not in a git repository")

    # Read GitHub event
    event_data = read_github_event()
    if not event_data:
        exit_noop("No GitHub event data available")

    # Get PR context
    pr_context = get_pr_context(event_data)
    if not pr_context:
        exit_noop("No PR context available")

    title, body, diff_summary = pr_context

    # Plan documentation updates
    plan = plan_doc_updates(title, body, diff_summary)
    if not plan:
        exit_noop("Could not plan documentation updates")

    # Generate documentation patch
    context = f"PR: {title}\n\n{body}\n\nChanges:\n{diff_summary}"
    diff_str = generate_doc_patch(plan, context)
    if not diff_str:
        exit_noop("Could not generate documentation patch")

    # Apply the patch
    if not apply_doc_patch(diff_str):
        exit_noop("Failed to apply documentation patch")

    # Create PR
    diff_summary = extract_diff_summary(diff_str)
    pr_number = create_doc_update_pr(plan, diff_summary)

    if pr_number:
        # Try to label the feature PR if we can determine its number
        try:
            # Extract PR number from event data
            feature_pr_number = event_data.get("pull_request", {}).get("number")
            if feature_pr_number:
                label_feature_pr(feature_pr_number, True)
        except Exception as e:
            logger.warning(f"Could not label feature PR: {e}")

        exit_success(f"Created PR #{pr_number} for documentation updates")
    else:
        exit_failure("Failed to create PR for documentation updates")


if __name__ == "__main__":
    main()
