#!/usr/bin/env python3
"""
Walrio GUI - Standalone launcher
Copyright (c) 2025 TAPS OSS  
Project: https://github.com/TAPSOSS/Walrio
Licensed under the BSD-3-Clause License (see LICENSE file for details)

The main Walrio GUI.
It will contain as much functionality as possible while maintaining a nice GUI to use.
"""

import sys
import subprocess

from PySide6.QtWidgets import QApplication
from WalrioMainGUI.controllers.main_controller import MainController

def main():
    """Main entry point for Walrio GUI."""
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