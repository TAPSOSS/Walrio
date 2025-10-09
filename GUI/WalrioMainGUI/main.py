#!/usr/bin/env python3
"""
Main entry point for Walrio Lite GUI application
Copyright (c) 2025 TAPS OSS
Project: https://github.com/TAPSOSS/Walrio
Licensed under the BSD-3-Clause License (see LICENSE file for details)

Entry point for running the Walrio Lite GUI application.
"""

import sys
import subprocess

try:
    from PySide6.QtWidgets import QApplication
except ImportError:
    print("PySide6 not found. Installing...")
    subprocess.run([sys.executable, "-m", "pip", "install", "PySide6"])
    from PySide6.QtWidgets import QApplication

from .controllers.main_controller import MainController


def main():
    """Main entry point for Walrio Lite GUI."""
    app = QApplication(sys.argv)
    app.setApplicationName("Walrio Lite")
    
    # Create the main controller (it will show the window automatically)
    controller = MainController()
    
    sys.exit(app.exec())


if __name__ == "__main__":
    main()