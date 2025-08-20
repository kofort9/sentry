#!/usr/bin/env python3
"""
Script to restore essential imports that were incorrectly removed by automated scripts.
This fixes the F821 undefined name errors causing pipeline failures.
"""
import sys
import re
import json
import logging
from datetime import datetime
import os
from pathlib import Path


def restore_imports_in_file(file_path):
    """Restore missing imports in a file based on undefined name errors."""
    with open(file_path, 'r') as f:
        content = f.read()
    
    original_content = content
    
    # Check what imports are needed based on usage
    needs_os = 'os.' in content or 'os.environ' in content or 'os.getenv' in content or 'os.path' in content
    needs_sys = 'sys.' in content or 'sys.path' in content or 'sys.exit' in content
    needs_re = 're.' in content or 're.search' in content or 're.sub' in content or 're.match' in content
    needs_json = 'json.' in content or 'json.loads' in content or 'json.dumps' in content
    needs_logging = 'logging.' in content
    needs_datetime = 'datetime.' in content or 'datetime(' in content
    
    # Find where imports should be added (after docstring, before first function/class)
    lines = content.split('\n')
    import_insert_line = 0
    
    # Skip shebang and docstring
    for i, line in enumerate(lines):
        if line.strip().startswith('"""') and '"""' in line[line.find('"""')+3:]:
            # Single line docstring
            import_insert_line = i + 1
            break
        elif line.strip().startswith('"""'):
            # Multi-line docstring start
            for j in range(i+1, len(lines)):
                if '"""' in lines[j]:
                    import_insert_line = j + 1
                    break
            break
        elif line.strip() and not line.startswith('#'):
            import_insert_line = i
            break
    
    # Check if imports already exist
    import_section = '\n'.join(lines[:import_insert_line + 10])
    has_os = 'import os' in import_section
    has_sys = 'import sys' in import_section  
    has_re = 'import re' in import_section
    has_json = 'import json' in import_section
    has_logging = 'import logging' in import_section
    has_datetime = 'from datetime import datetime' in import_section or 'import datetime' in import_section
    
    # Add missing imports
    imports_to_add = []
    if needs_os and not has_os:
        imports_to_add.append('import os')
    if needs_sys and not has_sys:
        imports_to_add.append('import sys')
    if needs_re and not has_re:
        imports_to_add.append('import re')
    if needs_json and not has_json:
        imports_to_add.append('import json')
    if needs_logging and not has_logging:
        imports_to_add.append('import logging')
    if needs_datetime and not has_datetime:
        imports_to_add.append('from datetime import datetime')
    
    if imports_to_add:
        # Insert imports at the right location
        for import_line in reversed(imports_to_add):  # Reverse to maintain order
            lines.insert(import_insert_line, import_line)
        
        content = '\n'.join(lines)
        
        with open(file_path, 'w') as f:
            f.write(content)
        
        return True
    
    return False


def main():
    """Process all Python files to restore missing imports."""
    print("🔧 Restoring missing imports...")
    
    directories = ['sentries/', 'scripts/']
    total_files = 0
    fixed_files = 0
    
    for directory in directories:
        if os.path.exists(directory):
            for file_path in Path(directory).rglob('*.py'):
                total_files += 1
                if restore_imports_in_file(str(file_path)):
                    print(f"✅ Fixed imports in {file_path}")
                    fixed_files += 1
    
    print(f"\n📊 Summary:")
    print(f"  Total files processed: {total_files}")
    print(f"  Files with restored imports: {fixed_files}")
    print(f"  Files unchanged: {total_files - fixed_files}")


if __name__ == "__main__":
    main()
