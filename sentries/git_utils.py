"""
Git utilities for branch management, commits, and PR operations.
"""
import os
import re
import json
import requests
import subprocess
from datetime import datetime
from typing import Optional, List, Dict
from .runner_common import GITHUB_TOKEN, GITHUB_REPOSITORY, get_logger

logger = get_logger(__name__)

def current_sha() -> str:
    """Get the current commit SHA."""
    try:
        result = subprocess.run(
            ['git', 'rev-parse', 'HEAD'],
            capture_output=True,
            text=True,
            timeout=10
        )
        if result.returncode == 0:
            return result.stdout.strip()
        else:
            raise RuntimeError(f"Failed to get current SHA: {result.stderr}")
    except Exception as e:
        logger.error(f"Error getting current SHA: {e}")
        raise

def get_short_sha(sha: str = None) -> str:
    """Get the short version of a SHA."""
    if sha is None:
        sha = current_sha()

    try:
        result = subprocess.run(
            ['git', 'rev-parse', '--short', sha],
            capture_output=True,
            text=True,
            timeout=10
        )
        if result.returncode == 0:
            return result.stdout.strip()
        else:
            return sha[:8]  # Fallback to first 8 characters
    except Exception as e:
        logger.error(f"Error getting short SHA: {e}")
        return sha[:8]

def create_branch(prefix: str, sha: str = None, sentry_type: str = "unknown") -> str:
    """
    Create a new branch from the given SHA with Sentries tagging.

    Args:
        prefix: Branch name prefix (e.g., 'ai-test-fixes' or 'ai-doc-updates')
        sha: Commit SHA to branch from (defaults to current HEAD)
        sentry_type: Type of sentry creating the branch ('testsentry' or 'docsentry')

    Returns:
        The created branch name
    """
    if sha is None:
        sha = current_sha()

    short_sha = get_short_sha(sha)
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    branch_name = f"{prefix}/{short_sha}-{timestamp}"

    try:
        # Check if branch already exists
        result = subprocess.run(
            ['git', 'show-ref', '--verify', '--quiet', f'refs/heads/{branch_name}'],
            capture_output=True,
            timeout=10
        )

        if result.returncode == 0:
            # Branch exists, delete it
            logger.info(f"Branch {branch_name} already exists, deleting...")
            subprocess.run(
                ['git', 'branch', '-D', branch_name],
                check=True,
                timeout=10
            )

        # Create new branch
        subprocess.run(
            ['git', 'checkout', '-b', branch_name, sha],
            check=True,
            timeout=10
        )

        # Tag the branch with Sentries metadata
        tag_branch_with_sentries_metadata(branch_name, sentry_type, sha)

        logger.info(f"Created Sentries branch: {branch_name}")
        return branch_name

    except subprocess.CalledProcessError as e:
        logger.error(f"Failed to create branch {branch_name}: {e}")
        raise
    except Exception as e:
        logger.error(f"Error creating branch: {e}")
        raise

def tag_branch_with_sentries_metadata(branch_name: str, sentry_type: str, source_sha: str):
    """
    Add Sentries metadata to a branch for easy identification.

    Args:
        branch_name: Name of the branch to tag
        sentry_type: Type of sentry ('testsentry' or 'docsentry')
        source_sha: Source commit SHA that triggered the sentry
    """
    try:
        # Create a metadata file in the branch
        metadata = {
            "created_by": "sentries",
            "sentry_type": sentry_type,
            "source_commit": source_sha,
            "created_at": datetime.now().isoformat(),
            "version": "0.1.0",
            "branch_name": branch_name
        }

        metadata_file = ".sentries-metadata.json"
        with open(metadata_file, 'w') as f:
            json.dump(metadata, f, indent=2)

        # Add and commit the metadata
        subprocess.run(['git', 'add', metadata_file], check=True, timeout=10)
        subprocess.run(
            ['git', 'commit', '-m', f"Add Sentries metadata for {sentry_type}"],
            check=True, timeout=10
        )

        logger.info(f"Tagged branch {branch_name} with Sentries metadata")

    except Exception as e:
        logger.warning(f"Could not add metadata to branch {branch_name}: {e}")

def is_sentries_branch(branch_name: str) -> bool:
    """
    Check if a branch was created by Sentries.

    Args:
        branch_name: Name of the branch to check

    Returns:
        True if it's a Sentries branch, False otherwise
    """
    try:
        # Check branch name pattern
        sentries_patterns = [
            r'^ai-test-fixes/',
            r'^ai-doc-updates/',
            r'^sentry-',
            r'^ai-sentry-'
        ]

        for pattern in sentries_patterns:
            if re.match(pattern, branch_name):
                return True

        # Check for metadata file
        result = subprocess.run(
            ['git', 'show', f'{branch_name}:.sentries-metadata.json'],
            capture_output=True,
            timeout=10
        )

        if result.returncode == 0:
            return True

        return False

    except Exception:
        return False

def get_sentries_branches() -> List[str]:
    """
    Get all branches created by Sentries.

    Returns:
        List of Sentries branch names
    """
    try:
        result = subprocess.run(
            ['git', 'branch', '--list'],
            capture_output=True,
            text=True,
            timeout=10
        )

        if result.returncode != 0:
            return []

        branches = []
        for line in result.stdout.strip().split('\n'):
            branch_name = line.strip().lstrip('* ').strip()
            if branch_name and is_sentries_branch(branch_name):
                branches.append(branch_name)

        return branches

    except Exception as e:
        logger.error(f"Error getting Sentries branches: {e}")
        return []

def commit_all(message: str) -> bool:
    """
    Commit all staged changes with the given message.

    Args:
        message: Commit message

    Returns:
        True if successful, False otherwise
    """
    try:
        # Check if there are changes to commit
        result = subprocess.run(
            ['git', 'status', '--porcelain'],
            capture_output=True,
            text=True,
            timeout=10
        )

        if not result.stdout.strip():
            logger.info("No changes to commit")
            return True

        # Add all changes
        subprocess.run(['git', 'add', '.'], check=True, timeout=10)

        # Commit
        subprocess.run(
            ['git', 'commit', '-m', message],
            check=True,
            timeout=10
        )

        logger.info(f"Committed changes: {message}")
        return True

    except subprocess.CalledProcessError as e:
        logger.error(f"Failed to commit changes: {e}")
        return False
    except Exception as e:
        logger.error(f"Error committing changes: {e}")
        return False

def open_pull_request(
    base_branch: str,
    head_branch: str,
    title: str,
    body: str,
    sentry_type: str = "unknown"
) -> Optional[int]:
    """
    Open a pull request using GitHub REST API with Sentries tagging.

    Args:
        base_branch: Base branch (usually main/master)
        head_branch: Head branch (our AI-generated branch)
        title: PR title
        body: PR body
        sentry_type: Type of sentry creating the PR

    Returns:
        PR number if successful, None otherwise
    """
    if not GITHUB_TOKEN or not GITHUB_REPOSITORY:
        logger.error("GitHub token or repository not configured")
        return None

    url = f"https://api.github.com/repos/{GITHUB_REPOSITORY}/pulls"

    headers = {
        "Authorization": f"token {GITHUB_TOKEN}",
        "Accept": "application/vnd.github.v3+json"
    }

    # Add Sentries metadata to PR body
    sentries_body = body + f"""

---
**🤖 Sentries Metadata**
- **Created by**: {sentry_type}
- **Source branch**: {head_branch}
- **Generated at**: {datetime.now().isoformat()}
- **Version**: 0.1.0
"""

    payload = {
        "title": title,
        "body": sentries_body,
        "head": head_branch,
        "base": base_branch
    }

    try:
        response = requests.post(url, json=payload, headers=headers, timeout=30)
        response.raise_for_status()

        pr_data = response.json()
        pr_number = pr_data.get("number")

        if pr_number:
            # Automatically add Sentries labels
            add_sentries_labels_to_pr(pr_number, sentry_type)

            # Add Sentries metadata to PR description
            add_sentries_metadata_to_pr(pr_number, sentry_type, head_branch)

        logger.info(f"Created Sentries PR #{pr_number}: {title}")
        return pr_number

    except requests.RequestException as e:
        logger.error(f"Failed to create PR: {e}")
        return None
    except Exception as e:
        logger.error(f"Error creating PR: {e}")
        return None

def add_sentries_labels_to_pr(pr_number: int, sentry_type: str):
    """
    Add Sentries-specific labels to a PR for easy identification.

    Args:
        pr_number: PR number to label
        sentry_type: Type of sentry that created the PR
    """
    try:
        # Core Sentries labels
        base_labels = ["ai-generated", "sentries", f"sentry-{sentry_type}"]

        # Add timestamp label
        timestamp = datetime.now().strftime("%Y%m%d")
        base_labels.append(f"generated-{timestamp}")

        # Add to PR
        if label_pull_request(pr_number, base_labels):
            logger.info(f"Added Sentries labels to PR #{pr_number}: {base_labels}")
        else:
            logger.warning(f"Failed to add Sentries labels to PR #{pr_number}")

    except Exception as e:
        logger.error(f"Error adding Sentries labels to PR #{pr_number}: {e}")

def add_sentries_metadata_to_pr(pr_number: int, sentry_type: str, source_branch: str):
    """
    Add Sentries metadata as a comment to the PR.

    Args:
        pr_number: PR number to add metadata to
        sentry_type: Type of sentry that created the PR
        source_branch: Source branch name
    """
    try:
        metadata_comment = f"""🤖 **Sentries Metadata**

- **Sentry Type**: {sentry_type}
- **Source Branch**: `{source_branch}`
- **Generated At**: {datetime.now().isoformat()}
- **Version**: 0.1.0
- **Repository**: {GITHUB_REPOSITORY}

---
*This PR was automatically generated by Sentries AI. Please review all changes carefully.*"""

        # Add as comment
        url = f"https://api.github.com/repos/{GITHUB_REPOSITORY}/issues/{pr_number}/comments"
        headers = {
            "Authorization": f"token {GITHUB_TOKEN}",
            "Accept": "application/vnd.github.v3+json"
        }

        response = requests.post(url, json={"body": metadata_comment}, headers=headers, timeout=30)
        if response.status_code == 201:
            logger.info(f"Added Sentries metadata comment to PR #{pr_number}")
        else:
            logger.warning(f"Failed to add metadata comment to PR #{pr_number}")

    except Exception as e:
        logger.error(f"Error adding metadata comment to PR #{pr_number}: {e}")

def get_sentries_prs() -> List[Dict]:
    """
    Get all PRs created by Sentries.

    Returns:
        List of PR data dictionaries
    """
    try:
        if not GITHUB_TOKEN or not GITHUB_REPOSITORY:
            return []

        url = f"https://api.github.com/repos/{GITHUB_REPOSITORY}/pulls"
        headers = {
            "Authorization": f"token {GITHUB_TOKEN}",
            "Accept": "application/vnd.github.v3+json"
        }

        response = requests.get(url, headers=headers, timeout=30)
        if response.status_code != 200:
            return []

        prs = response.json()
        sentries_prs = []

        for pr in prs:
            # Check for Sentries labels
            if any(label.get('name', '').startswith('sentry-') for label in pr.get('labels', [])):
                sentries_prs.append(pr)
            # Check for Sentries metadata in body
            elif '🤖 Sentries Metadata' in pr.get('body', ''):
                sentries_prs.append(pr)

        return sentries_prs

    except Exception as e:
        logger.error(f"Error getting Sentries PRs: {e}")
        return []

def label_pull_request(pr_number: int, labels: List[str]) -> bool:
    """
    Add labels to a pull request.

    Args:
        pr_number: PR number
        labels: List of labels to add

    Returns:
        True if successful, False otherwise
    """
    if not GITHUB_TOKEN or not GITHUB_REPOSITORY:
        logger.error("GitHub token or repository not configured")
        return False

    url = f"https://api.github.com/repos/{GITHUB_REPOSITORY}/issues/{pr_number}/labels"

    headers = {
        "Authorization": f"token {GITHUB_TOKEN}",
        "Accept": "application/vnd.github.v3+json"
    }

    payload = {"labels": labels}

    try:
        response = requests.post(url, json=payload, headers=headers, timeout=30)
        response.raise_for_status()

        logger.info(f"Added labels to PR #{pr_number}: {labels}")
        return True

    except requests.RequestException as e:
        logger.error(f"Failed to add labels to PR #{pr_number}: {e}")
        return False
    except Exception as e:
        logger.error(f"Error adding labels to PR #{pr_number}: {e}")
        return False

def get_base_branch() -> str:
    """Get the base branch name (main or master)."""
    try:
        # Try to get the default branch from GitHub API
        if GITHUB_TOKEN and GITHUB_REPOSITORY:
            url = f"https://api.github.com/repos/{GITHUB_REPOSITORY}"
            headers = {
                "Authorization": f"token {GITHUB_TOKEN}",
                "Accept": "application/vnd.github.v3+json"
            }

            response = requests.get(url, headers=headers, timeout=30)
            if response.status_code == 200:
                repo_data = response.json()
                return repo_data.get("default_branch", "main")

        # Fallback: check local branches
        result = subprocess.run(
            ['git', 'branch', '-r'],
            capture_output=True,
            text=True,
            timeout=10
        )

        if result.returncode == 0:
            branches = result.stdout.strip().split('\n')
            for branch in branches:
                if 'origin/main' in branch:
                    return 'main'
                elif 'origin/master' in branch:
                    return 'master'

        # Default fallback
        return 'main'

    except Exception as e:
        logger.warning(f"Could not determine base branch, using 'main': {e}")
        return 'main'
