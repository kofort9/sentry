#!/usr/bin/env python3
"""
Smart script to fix flake8 issues without breaking functionality.
Analyzes actual usage before making changes.
"""
import os
import re
from datetime import datetime

import ast


from pathlib import Path


def analyze_file_usage(file_path):
    """Analyze what names are actually used in a Python file."""
    try:
        with open(file_path, 'r') as f:
            content = f.read()

        # Parse the AST to find actual usage
        tree = ast.parse(content)

        # Collect all names that are used
        used_names = set()

        for node in ast.walk(tree):
            if isinstance(node, ast.Name):
                used_names.add(node.id)
            elif isinstance(node, ast.Attribute):
                # Handle attribute access like 'os.path'
                if isinstance(node.value, ast.Name):
                    used_names.add(node.value.id)

        return used_names
    except:
        # If parsing fails, return empty set to be safe
        return set()


def fix_unused_imports_smart(file_path):
    """Remove unused imports by analyzing actual usage."""
    with open(file_path, 'r') as f:
        content = f.read()

    original_content = content
    used_names = analyze_file_usage(file_path)

    # Common imports to check
    import_patterns = [
        (r'^import json\s*$', 'json', 'json'),
        (r'^import os\s*$', 'os', 'os'),
        (r'^import sys\s*$', 'sys', 'sys'),
        (r'^import time\s*$', 'time', 'time'),
        (r'^import re\s*$', 're', 're'),
        (r'^import logging\s*$', 'logging', 'logging'),
        (r'^from typing import Dict\s*$', 'Dict', 'typing.Dict'),
        (r'^from typing import List\s*$', 'List', 'typing.List'),
        (r'^from typing import Optional\s*$', 'Optional', 'typing.Optional'),
        (r'^from typing import Set\s*$', 'Set', 'typing.Set'),
        (r'^from typing import Tuple\s*$', 'Tuple', 'typing.Tuple'),
        (r'^from datetime import datetime\s*$', 'datetime', 'datetime.datetime'),
    ]

    modified = False

    for pattern, name, full_name in import_patterns:
        if name not in used_names and full_name not in used_names:
            # Only remove if not used
            content = re.sub(pattern, '', content, flags=re.MULTILINE)
            modified = True

    # Handle multi-line imports more carefully
    if 'typing' in content:
        # Look for "from typing import X, Y, Z" patterns
        typing_imports = re.findall(r'from typing import ([^,\n]+)', content)
        for import_line in typing_imports:
            imports = [imp.strip() for imp in import_line.split(',')]
            unused_imports = [imp for imp in imports if imp not in used_names]

            if unused_imports and len(unused_imports) == len(imports):
                # All imports are unused, remove the whole line
                pattern = rf'^.*{re.escape(import_line)}.*\n'
                content = re.sub(pattern, '', content, flags=re.MULTILINE)
                modified = True
            elif unused_imports:
                # Some imports are unused, remove just those
                for unused in unused_imports:
                    # This is complex, so we'll skip for now to be safe
                    pass

    if modified:
        with open(file_path, 'w') as f:
            f.write(content)
        return True
    return False


def fix_missing_blank_lines_smart(file_path):
    """Add missing blank lines between functions and classes."""
    with open(file_path, 'r') as f:
        lines = f.readlines()

    original_lines = lines.copy()
    modified = False

    i = 0
    while i < len(lines) - 1:
        line = lines[i].strip()

        # Check if we need a blank line after function/class definition
        if (line.startswith('def ') or line.startswith('class ')) and line.endswith(':'):
            # Look for the next non-empty line
            j = i + 1
            while j < len(lines) and not lines[j].strip():
                j += 1

            if j < len(lines):
                next_non_empty = lines[j].strip()
                # If next non-empty line is not a docstring and not a function/class
                if (not next_non_empty.startswith('"""') and
                    not next_non_empty.startswith("'''")
                    and not next_non_empty.startswith('def ')
                    and not next_non_empty.startswith('class ')
                    and not next_non_empty.startswith('@')
                        and not next_non_empty.startswith('if __name__')):

                    # Insert blank line
                    lines.insert(j, '\n')
                    modified = True
                    i = j  # Skip the line we just inserted

        i += 1

    if modified:
        with open(file_path, 'w') as f:
            f.writelines(lines)
        return True
    return False


def fix_f_string_issues_smart(file_path):
    """Fix f-strings that don't have placeholders."""
    with open(file_path, 'r') as f:
        content = f.read()

    original_content = content

    # Find f-strings without placeholders and convert them to regular strings
    # Pattern: "..." or '...' without { or } inside
    pattern = r'f(["\'])((?:(?!\1|{).)*)\1'

    def replace_f_string(match):

        quote = match.group(1)
        string_content = match.group(2)
        # Only replace if no braces in the string
        if '{' not in string_content and '}' not in string_content:
            return f'{quote}{string_content}{quote}'
        return match.group(0)

    content = re.sub(pattern, replace_f_string, content)

    if content != original_content:
        with open(file_path, 'w') as f:
            f.write(content)
        return True
    return False


def process_file_smart(file_path):
    """Process a single file to fix flake8 issues intelligently."""
    print(f"Processing: {file_path}")

    changes_made = False

    # Fix unused imports (smart version)
    if fix_unused_imports_smart(file_path):
        changes_made = True
        print("  ✓ Fixed unused imports (smart)")

    # Fix missing blank lines
    if fix_missing_blank_lines_smart(file_path):
        changes_made = True
        print("  ✓ Fixed missing blank lines")

    # Fix f-string issues
    if fix_f_string_issues_smart(file_path):
        changes_made = True
        print("  ✓ Fixed f-string issues")

    if not changes_made:
        print("  ✓ No changes needed")

    return changes_made


def main():
    """Main function to process all Python files."""
    print("🧠 Running smart flake8 fixes...")
    print()

    # Directories to process
    directories = ['sentries/', 'scripts/']

    total_files = 0
    changed_files = 0

    for directory in directories:
        if os.path.exists(directory):
            print(f"📁 Processing {directory}:")
            for file_path in Path(directory).rglob('*.py'):
                total_files += 1
                if process_file_smart(str(file_path)):
                    changed_files += 1
                print()

    print("🎯 Summary:")
    print(f"  Total files processed: {total_files}")
    print(f"  Files changed: {changed_files}")
    print(f"  Files unchanged: {total_files - changed_files}")

    if changed_files > 0:
        print()
        print("✨ Smart fixes applied! Run flake8 again to see remaining issues.")
    else:
        print()
        print("💡 No more smart fixes found. Manual review needed for remaining issues.")


if __name__ == "__main__":
    main()
