#!/usr/bin/env python3
"""
Targeted script to fix specific flake8 issues that are easy to resolve.
Focuses on unused imports, missing blank lines, and f-string issues.
"""
import os
import re


from pathlib import Path


def fix_unused_imports(file_path):
    """Remove obviously unused imports."""
    with open(file_path, 'r') as f:
        content = f.read()
    
    original_content = content
    
    # Common unused imports to remove
    unused_imports = [
        'import json',
        'import os',
        'import sys',
        'import time',
        'import re',
        'import logging',
        'from typing import Dict',
        'from typing import List',
        'from typing import Optional',
        'from typing import Set',
        'from typing import Tuple',
        'from datetime import datetime',
    ]
    
    for imp in unused_imports:
        # Remove the import line if it's on its own line
        pattern = rf'^{re.escape(imp)}\s*$'
        content = re.sub(pattern, '', content, flags=re.MULTILINE)
        
        # Also handle multi-line imports
        if imp.startswith('from typing import'):
            # Handle "from typing import X, Y, Z" cases
            base = imp.replace('from typing import ', '')
            pattern = rf'from typing import [^,\n]*{re.escape(base)}[^,\n]*\s*$'
            content = re.sub(pattern, '', content, flags=re.MULTILINE)
    
    # Only write if content changed
    if content != original_content:
        with open(file_path, 'w') as f:
            f.write(content)
        return True
    return False


def fix_missing_blank_lines(file_path):
    """Add missing blank lines between functions and classes."""
    with open(file_path, 'r') as f:
        lines = f.readlines()
    
    original_lines = lines.copy()
    modified = False
    
    i = 0
    while i < len(lines) - 1:
        line = lines[i].strip()
        next_line = lines[i + 1].strip()
        
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
                    not next_non_empty.startswith("'''") and
                    not next_non_empty.startswith('def ') and
                    not next_non_empty.startswith('class ') and
                    not next_non_empty.startswith('@') and
                    not next_non_empty.startswith('if __name__')):
                    
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


def fix_f_string_issues(file_path):
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


def process_file(file_path):
    """Process a single file to fix targeted flake8 issues."""
    print(f"Processing: {file_path}")
    
    changes_made = False
    
    # Fix unused imports
    if fix_unused_imports(file_path):
        changes_made = True
        print("  ✓ Fixed unused imports")
    
    # Fix missing blank lines
    if fix_missing_blank_lines(file_path):
        changes_made = True
        print("  ✓ Fixed missing blank lines")
    
    # Fix f-string issues
    if fix_f_string_issues(file_path):
        changes_made = True
        print("  ✓ Fixed f-string issues")
    
    if not changes_made:
        print("  ✓ No changes needed")
    
    return changes_made


def main():
    """Main function to process all Python files."""
    print("🎯 Fixing targeted flake8 issues...")
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
                if process_file(str(file_path)):
                    changed_files += 1
                print()
    
    print("🎯 Summary:")
    print(f"  Total files processed: {total_files}")
    print(f"  Files changed: {changed_files}")
    print(f"  Files unchanged: {total_files - changed_files}")
    
    if changed_files > 0:
        print()
        print("✨ Changes made! Run flake8 again to see remaining issues.")
    else:
        print()
        print("💡 No more easy fixes found. Manual review needed for remaining issues.")


if __name__ == "__main__":
    main()
