#!/usr/bin/env python3
"""
Script to fix common flake8 issues automatically.
This helps clean up code before manual review.
"""
import os
import re



from pathlib import Path

def fix_trailing_whitespace(file_path):
    """Remove trailing whitespace from lines."""
    with open(file_path, 'r') as f:
        content = f.read()

    # Remove trailing whitespace from each line
    lines = content.split('\n')
    fixed_lines = [line.rstrip() for line in lines]

    # Only write if content changed
    new_content = '\n'.join(fixed_lines)
    if new_content != content:
        with open(file_path, 'w') as f:
            f.write(new_content)
        return True
    return False

def fix_blank_line_whitespace(file_path):
    """Remove whitespace from blank lines."""
    with open(file_path, 'r') as f:
        content = f.read()

    # Replace blank lines that contain only whitespace with empty lines
    fixed_content = re.sub(r'^\s+$', '', content, flags=re.MULTILINE)

    # Only write if content changed
    if fixed_content != content:
        with open(file_path, 'w') as f:
            f.write(fixed_content)
        return True
    return False

def fix_unused_imports(file_path):
    """Remove obviously unused imports."""
    with open(file_path, 'r') as f:
        content = f.read()

    # Common unused imports to remove
    unused_imports = [
        'import json',
        'import time',
        'import os',
        'import sys',
        'import re',
        'import logging',
        'from typing import Dict',
        'from typing import List',
        'from typing import Optional',
        'from typing import Tuple',
        'from typing import Set',
        'from datetime import datetime',
    ]

    original_content = content
    for imp in unused_imports:
        # Remove the import line if it's on its own line
        pattern = rf'^{re.escape(imp)}\s*$'
        content = re.sub(pattern, '', content, flags=re.MULTILINE)

    # Only write if content changed
    if content != original_content:
        with open(file_path, 'w') as f:
            f.write(content)
        return True
    return False

def process_file(file_path):
    """Process a single file to fix flake8 issues."""
    print(f"Processing: {file_path}")

    changes_made = False

    # Fix trailing whitespace
    if fix_trailing_whitespace(file_path):
        changes_made = True
        print("  ✓ Fixed trailing whitespace")

    # Fix blank line whitespace
    if fix_blank_line_whitespace(file_path):
        changes_made = True
        print("  ✓ Fixed blank line whitespace")

    # Fix unused imports (be careful with this)
    # if fix_unused_imports(file_path):
    #     changes_made = True
    #     print("  ✓ Fixed unused imports")

    if not changes_made:
        print("  ✓ No changes needed")

    return changes_made

def main():
    """Main function to process all Python files."""
    print("🔧 Fixing common flake8 issues...")
    print()

    # Directories to process
    directories = ['sentries/', 'scripts/']

    total_files = 0
    changed_files = 0

    for directory in directories:
        if os.path.exists(directory):
            for file_path in Path(directory).rglob('*.py'):
                if file_path.is_file():
                    total_files += 1
                    if process_file(file_path):
                        changed_files += 1
                    print()

    print("🎯 Summary:")
    print(f"  Total files processed: {total_files}")
    print(f"  Files changed: {changed_files}")
    print(f"  Files unchanged: {total_files - changed_files}")

    if changed_files > 0:
        print()
        print("⚠️  Note: Some issues may require manual review:")
        print("  - E302: Missing blank lines between functions")
        print("  - E402: Module level imports not at top")
        print("  - E501: Lines too long")
        print("  - F541: F-string missing placeholders")
        print()
        print("Run flake8 again to see remaining issues.")

if __name__ == "__main__":
    main()
