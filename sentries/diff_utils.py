"""
Diff utilities for validating and applying unified diffs.
"""
import re
import os
import subprocess
from typing import List, Tuple, Optional
from .runner_common import get_logger, TESTS_ALLOWLIST, DOCS_ALLOWLIST

logger = get_logger(__name__)

def is_allowed_path(path: str, allowlist: List[str]) -> bool:
    """
    Check if a path is allowed based on the allowlist.
    
    Args:
        path: File path to check
        allowlist: List of allowed path patterns
    
    Returns:
        True if path is allowed, False otherwise
    """
    for pattern in allowlist:
        if pattern.endswith("/"):
            # Directory pattern (e.g., "tests/")
            if path.startswith(pattern):
                return True
        elif pattern.endswith("**"):
            # Recursive pattern (e.g., "docs/**")
            base_pattern = pattern[:-2]
            if path.startswith(base_pattern):
                return True
        else:
            # Exact file pattern (e.g., "README.md")
            if path == pattern:
                return True
    
    return False

def validate_unified_diff(diff_str: str, allowlist: List[str]) -> Tuple[bool, str]:
    """
    Validate a unified diff against the allowlist and format.
    
    Args:
        diff_str: The unified diff string to validate
        allowlist: List of allowed path patterns
    
    Returns:
        Tuple of (is_valid, reason)
    """
    if not diff_str.strip():
        return False, "Empty diff"
    
    # Check for ABORT response
    if "ABORT" in diff_str.upper():
        return False, "LLM returned ABORT"
    
    # Parse diff to extract file paths
    file_paths = set()
    lines_changed = 0
    
    for line in diff_str.split('\n'):
        line = line.strip()
        
        # Extract file paths from diff headers
        if line.startswith('--- a/') or line.startswith('+++ b/'):
            path = line[6:]  # Remove '--- a/' or '+++ b/'
            if path and path != '/dev/null':
                file_paths.add(path)
        
        # Count changed lines
        if line.startswith('+') or line.startswith('-'):
            lines_changed += 1
    
    # Check if all files are allowed
    for path in file_paths:
        if not is_allowed_path(path, allowlist):
            return False, f"Path not allowed: {path}"
    
    # Check file count limits
    if len(file_paths) > 5:
        return False, f"Too many files changed: {len(file_paths)} > 5"
    
    # Check line count limits
    max_lines = 200 if "tests/" in str(allowlist) else 300
    if lines_changed > max_lines:
        return False, f"Too many lines changed: {lines_changed} > {max_lines}"
    
    # Basic diff format validation
    if not re.search(r'^@@ -\d+(?:,\d+)? \+\d+(?:,\d+)? @@', diff_str, re.MULTILINE):
        return False, "Invalid unified diff format"
    
    return True, "Valid diff"

def apply_unified_diff(repo_path: str, diff_str: str) -> bool:
    """
    Apply a unified diff to the repository.
    
    Args:
        repo_path: Path to the git repository
        diff_str: The unified diff string to apply
    
    Returns:
        True if successful, False otherwise
    """
    try:
        # Create a temporary diff file
        import tempfile
        with tempfile.NamedTemporaryFile(mode='w', suffix='.diff', delete=False) as f:
            f.write(diff_str)
            temp_diff_path = f.name
        
        try:
            # Apply the diff
            result = subprocess.run(
                ['git', 'apply', '-p0', temp_diff_path],
                cwd=repo_path,
                capture_output=True,
                text=True,
                timeout=30
            )
            
            if result.returncode != 0:
                logger.error(f"Failed to apply diff: {result.stderr}")
                return False
            
            logger.info("Diff applied successfully")
            return True
            
        finally:
            # Clean up temporary file
            os.unlink(temp_diff_path)
            
    except Exception as e:
        logger.error(f"Error applying diff: {e}")
        return False

def extract_diff_summary(diff_str: str) -> str:
    """
    Extract a summary of what the diff changes.
    
    Args:
        diff_str: The unified diff string
    
    Returns:
        Summary string
    """
    files_changed = set()
    lines_added = 0
    lines_removed = 0
    
    for line in diff_str.split('\n'):
        line = line.strip()
        
        if line.startswith('--- a/') or line.startswith('+++ b/'):
            path = line[6:]
            if path and path != '/dev/null':
                files_changed.add(path)
        
        if line.startswith('+') and not line.startswith('+++'):
            lines_added += 1
        elif line.startswith('-') and not line.startswith('---'):
            lines_removed += 1
    
    return f"Changed {len(files_changed)} files: +{lines_added} -{lines_removed} lines"
