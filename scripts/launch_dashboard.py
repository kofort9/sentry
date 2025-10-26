#!/usr/bin/env python3
"""
CAMEL Dashboard Launcher

Simple launcher script for the CAMEL monitoring dashboard.
Handles environment setup and graceful error handling.
"""

import subprocess
import sys
import os
from pathlib import Path

def check_dependencies():
    """Check if required dependencies are installed."""
    try:
        import streamlit
        import plotly
        import pandas
        print("✅ All dashboard dependencies are available")
        return True
    except ImportError as e:
        print(f"❌ Missing dependency: {e}")
        print("💡 Install missing dependencies with:")
        print("   pip install streamlit plotly pandas")
        return False

def launch_dashboard():
    """Launch the Streamlit dashboard."""
    dashboard_path = Path(__file__).parent / "apps" / "camel_dashboard" / "app.py"
    
    if not dashboard_path.exists():
        print(f"❌ Dashboard not found at: {dashboard_path}")
        return False
    
    print(f"🚀 Launching CAMEL Dashboard from: {dashboard_path}")
    print("📍 Dashboard will be available at: http://localhost:8501")
    print("🛑 Press Ctrl+C to stop the dashboard")
    
    try:
        # Launch Streamlit
        subprocess.run([
            sys.executable, "-m", "streamlit", "run", 
            str(dashboard_path),
            "--server.port", "8501",
            "--server.headless", "false",
            "--browser.gatherUsageStats", "false"
        ], check=True)
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ Failed to launch dashboard: {e}")
        return False
    except KeyboardInterrupt:
        print("\n🛑 Dashboard stopped by user")
        return True

def main():
    """Main launcher function."""
    print("🐫 CAMEL Dashboard Launcher")
    print("=" * 40)
    
    # Check dependencies
    if not check_dependencies():
        sys.exit(1)
    
    # Set up environment
    os.environ['STREAMLIT_THEME_BASE'] = 'light'
    
    # Launch dashboard
    success = launch_dashboard()
    
    if not success:
        print("\n❌ Dashboard launch failed")
        sys.exit(1)
    else:
        print("\n✅ Dashboard session ended")

if __name__ == "__main__":
    main()
