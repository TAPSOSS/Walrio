#!/usr/bin/env python3
"""
Walrio Lite GUI - Standalone launcher
Copyright (c) 2025 TAPS OSS  
Project: https://github.com/TAPSOSS/Walrio
Licensed under the BSD-3-Clause License (see LICENSE file for details)

A lightweight, simple music player GUI built with PySide and music libraries from Walrio that focuses entirely on 
playing music files without any file modification or other extra unneeded capabilities.
"""

import sys
import subprocess

from PySide6.QtWidgets import QApplication
from WalrioLiteGUI.controllers.main_controller import MainController

def main():
    """Main entry point for Walrio Lite GUI."""
    app = QApplication(sys.argv)
    app.setApplicationName("Walrio Lite")
    
    try:
        # Create and show the main controller
        controller = MainController()
        controller.show()
        
        # Start the event loop
        sys.exit(app.exec())
    except Exception as e:
        print(f"Error starting Walrio Lite GUI: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()