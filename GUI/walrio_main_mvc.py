#!/usr/bin/env python3
"""
Walrio MVC GUI - Standalone launcher
Copyright (c) 2025 TAPS OSS  
Project: https://github.com/TAPSOSS/Walrio
Licensed under the BSD-3-Clause License (see LICENSE file for details)

Standalone launcher for the Walrio MVC GUI application.
Run this script to start the new MVC version of Walrio GUI.
"""

import sys
import subprocess

try:
    from PySide6.QtWidgets import QApplication
except ImportError:
    print("PySide6 not found. Installing...")
    subprocess.run([sys.executable, "-m", "pip", "install", "PySide6"])
    from PySide6.QtWidgets import QApplication

from WalrioMainGUI.controllers.main_controller import MainController


def main():
    """Main entry point for Walrio MVC GUI."""
    app = QApplication(sys.argv)
    app.setApplicationName("Walrio")
    
    try:
        # Create and show the main controller
        controller = MainController()
        controller.show()
        
        # Start the event loop
        sys.exit(app.exec())
    except Exception as e:
        print(f"Error starting Walrio GUI: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()