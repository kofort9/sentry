#!/usr/bin/env python3
"""
Sentries Setup CLI Wrapper
"""
import os
import sys

# Add scripts directory to path
scripts_dir = os.path.join(os.path.dirname(__file__), '..', 'scripts')
sys.path.insert(0, scripts_dir)

from setup_sentries import main

if __name__ == "__main__":
    main()
