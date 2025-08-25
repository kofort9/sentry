#!/usr/bin/env python3
"""
DocSentry: Keeps documentation in sync with code changes.

This version uses a robust patch engine that eliminates reliance on model-generated line numbers.
Instead, it uses JSON find/replace operations that are converted to unified diffs locally.
"""

import os
from typing import Optional, Tuple

from .chat import chat, get_default_params
from .diff_utils import apply_unified_diff, extract_diff_summary
from .git_utils import (
    commit_all,
    create_branch,
    get_base_branch,
    open_pull_request,
)
from .patch_engine import (
    NoEffectiveChangeError,
    ValidationError,
    create_patch_engine,
)
from .prompts import PATCHER_DOCS, PLANNER_DOCS
from .runner_common import (
    MODEL_PATCH,
    MODEL_PLAN,
    exit_failure,
    exit_noop,
    exit_success,
    get_logger,
    get_short_sha,
    setup_logging,
    validate_environment,
)

logger = get_logger(__name__)


def get_pr_context() -> Optional[str]:
    """
    Get context about the current PR for documentation planning.

    Returns:
        PR context string or None if not available
    """
    # This would typically come from GitHub Actions context
    # For now, we'll use a placeholder
    return "Documentation updates needed for recent code changes"


def get_docs_context_with_excerpts() -> Tuple[str, str]:
    """
    Get documentation context and create minimal excerpts for the patcher.

    Returns:
        Tuple of (full_context, minimal_excerpts)
    """
    # Create minimal excerpts for documentation files
    minimal_excerpts = ""

    # Check for common documentation files
    doc_files = ["README.md", "docs/", "CHANGELOG.md"]

    for doc_path in doc_files:
        if os.path.exists(doc_path):
            try:
                if os.path.isfile(doc_path):
                    with open(doc_path, "r") as f:
                        content = f.read()
                    # Include first 30 lines for context
                    lines = content.split("\n")[:30]
                    minimal_excerpts += f"=== {doc_path} ===\n"
                    minimal_excerpts += "\n".join(lines)
                    minimal_excerpts += "\n\n"
                elif os.path.isdir(doc_path):
                    # For directories, list files
                    files = os.listdir(doc_path)
                    minimal_excerpts += f"=== {doc_path}/ ===\n"
                    minimal_excerpts += f"Files: {', '.join(files[:10])}\n\n"
            except Exception as e:
                minimal_excerpts += f"=== {doc_path} ===\n[Error reading: {e}]\n\n"

    full_context = "Documentation updates needed for recent code changes"

    return full_context, minimal_excerpts


def plan_docs_updates(context: str) -> Optional[str]:
    """
    Use the planner model to create a plan for documentation updates.

    Args:
        context: Documentation context

    Returns:
        Planning response from the LLM
    """
    try:
        params = get_default_params("planner")

        messages = [
            {"role": "system", "content": PLANNER_DOCS},
            {"role": "user", "content": context},
        ]

        logger.info("Planning documentation updates with LLM...")

        response = chat(
            model=MODEL_PLAN,
            messages=messages,
            temperature=params["temperature"],
            max_tokens=int(params["max_tokens"]),
        )

        if not response or len(response.strip()) == 0:
            logger.error("LLM planner returned empty response")
            return None

        logger.info("Documentation planning completed successfully")
        return response

    except Exception as e:
        logger.error(f"Error during documentation planning: {e}")
        return None


def generate_docs_patch_json(plan: str, excerpts: str) -> Optional[str]:
    """
    Use the patcher model to generate JSON operations for documentation updates.

    Args:
        plan: The planning response
        excerpts: Minimal file excerpts for the patcher

    Returns:
        JSON string with operations or None if ABORT
    """
    try:
        # Create focused context for the patcher
        patcher_context = f"""Plan: {plan}

{excerpts}

Generate JSON operations to update documentation. Copy exact text from the excerpts above."""

        messages = [
            {"role": "system", "content": PATCHER_DOCS},
            {"role": "user", "content": patcher_context},
        ]

        logger.info("Generating documentation patch JSON with LLM...")

        # Use tighter generation limits for JSON output
        response = chat(
            model=MODEL_PATCH,
            messages=messages,
            temperature=0.1,  # Lower temperature for more precise output
            max_tokens=600,  # Keep JSON output compact
        )

        # Log the response for debugging
        logger.info(f"LLM Patcher Response (length: {len(response)}):")
        logger.info("=" * 50)
        logger.info(response)
        logger.info("=" * 50)

        if "ABORT" in response.upper():
            logger.info("LLM patcher returned ABORT")
            return None

        # Clean up the response - remove any markdown or prose
        cleaned_response = response.strip()

        # Try to extract JSON if it's wrapped in markdown
        if cleaned_response.startswith("```json"):
            cleaned_response = cleaned_response[7:]  # Remove ```json
        elif cleaned_response.startswith("```"):
            cleaned_response = cleaned_response[3:]  # Remove ```
        if cleaned_response.endswith("```"):
            cleaned_response = cleaned_response[:-3]  # Remove ending ```

        cleaned_response = cleaned_response.strip()

        logger.info("JSON patch generation completed")
        return cleaned_response

    except Exception as e:
        logger.error(f"Error during JSON patch generation: {e}")
        return None


def apply_and_test_docs_patch_with_engine(
    json_operations: str, original_context: str, plan: str, max_attempts: int = 3
) -> Tuple[bool, str]:
    """
    Apply documentation patch using the patch engine with feedback loop.

    Args:
        json_operations: JSON string with find/replace operations
        original_context: Original documentation context
        plan: The documentation update plan
        max_attempts: Maximum number of correction attempts (default: 3)

    Returns:
        (success, final_diff) tuple
    """
    current_json = json_operations
    patch_engine = create_patch_engine()

    for attempt in range(max_attempts):
        logger.info(f"🔄 Documentation patch attempt {attempt + 1}/{max_attempts}")

        try:
            # Use the patch engine to convert JSON to unified diff
            logger.info("🔧 Converting JSON operations to unified diff...")
            unified_diff = patch_engine.process_operations(current_json)

            logger.info("✅ Patch engine generated valid unified diff")
            logger.info(f"📝 Diff length: {len(unified_diff)} characters")

            # Try to apply the diff
            if apply_unified_diff(".", unified_diff):
                logger.info("✅ Documentation patch applied successfully")
                return True, unified_diff
            else:
                feedback = "Patch failed to apply due to git apply error"

        except (ValidationError, NoEffectiveChangeError) as e:
            logger.warning(f"⚠️ Patch engine validation failed: {e}")
            feedback = f"Patch engine validation failed: {e}"
        except Exception as e:
            logger.error(f"❌ Unexpected error in patch engine: {e}")
            feedback = f"Patch engine error: {e}"

        # If we're not on the last attempt, try to get the LLM to fix it
        if attempt < max_attempts - 1:
            logger.info("🔄 Asking LLM to correct the JSON operations...")

            # Create feedback context
            feedback_context = f"""
{original_context}

PATCH ENGINE FEEDBACK (Attempt {attempt + 1}):
Your previous JSON operations failed: {feedback}

Please generate corrected JSON operations that address these issues.
Make sure to:
1. Only reference allowed file paths
2. Use exact text from the provided excerpts
3. Generate valid JSON format
4. Stay within size limits (max 5 ops, max 200 lines)

PREVIOUS FAILED JSON:
{current_json}
"""

            # Get corrected JSON from LLM
            corrected_json = generate_docs_patch_json(
                f"CORRECTION NEEDED: {feedback}", feedback_context
            )

            if corrected_json:
                current_json = corrected_json
                logger.info("🔄 LLM generated corrected JSON, retrying...")
                continue
            else:
                logger.error("❌ LLM failed to generate corrected JSON")
                break
        else:
            logger.error(f"❌ Max attempts ({max_attempts}) reached, giving up")
            logger.error(f"Final failure reason: {feedback}")
            break

    return False, ""


def create_docs_update_pr(plan: str, diff_summary: str) -> Optional[int]:
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
        branch_name = create_branch("ai-docs-updates", sentry_type="docsentry")

        # Commit changes
        commit_message = f"DocSentry: update documentation for {short_sha}\n\n{plan}"
        if not commit_all(commit_message):
            raise RuntimeError("Failed to commit changes")

        # Create PR
        title = f"DocSentry: update documentation for {short_sha}"
        body = f"""## Documentation Updates

**Plan:**
{plan}

**Changes:**
{diff_summary}

**Generated by:** DocSentry AI (Patch Engine v2)
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


def show_sentries_banner() -> None:
    """Display the Sentry ASCII art banner."""
    from sentries.banner import show_sentry_banner

    show_sentry_banner()
    print("📚 DocSentry v2 - AI-Powered Documentation Updates (Patch Engine)")
    print("=" * 65)
    print()


def main() -> None:
    """Main entry point for DocSentry."""
    show_sentries_banner()
    setup_logging()
    logger.info("DocSentry v2 starting with Patch Engine...")

    # Validate environment
    if not validate_environment():
        exit_failure("Environment validation failed")

    # Check if we're in a git repository
    if not os.path.exists(".git"):
        exit_failure("Not in a git repository")

    # Get documentation context with minimal excerpts for the patcher
    context, excerpts = get_docs_context_with_excerpts()

    # Plan documentation updates
    plan = plan_docs_updates(context)
    if not plan:
        exit_noop("No documentation updates needed")

    # Generate documentation patch JSON with feedback loop
    diff_str = generate_docs_patch_json(plan, excerpts)
    if not diff_str:
        exit_noop("Could not generate documentation patch JSON")

    # Apply and test with patch engine (max 3 attempts)
    logger.info("🔄 Starting documentation patch application with Patch Engine...")
    success, final_diff = apply_and_test_docs_patch_with_engine(
        diff_str, context, plan, max_attempts=3
    )

    if not success:
        exit_noop("Documentation patch application failed after 3 attempts")

    # Create PR only if we have a working patch
    diff_summary = extract_diff_summary(final_diff)
    pr_number = create_docs_update_pr(plan, diff_summary)

    if pr_number:
        logger.info("Documentation updates completed successfully")
        exit_success(f"Created PR #{pr_number} for documentation updates")
    else:
        exit_failure("Failed to create PR for documentation updates")


if __name__ == "__main__":
    main()
