#!/usr/bin/env python3
"""
Base view class for Walrio GUI components
Copyright (c) 2025 TAPS OSS
Project: https://github.com/TAPSOSS/Walrio
Licensed under the BSD-3-Clause License (see LICENSE file for details)

Contains base view class that other views can inherit from.
"""

import sys
import subprocess

try:
    from PySide6.QtWidgets import QWidget
    from PySide6.QtCore import Signal
except ImportError:
    print("PySide6 not found. Installing...")
    subprocess.run([sys.executable, "-m", "pip", "install", "PySide6"])
    from PySide6.QtWidgets import QWidget
    from PySide6.QtCore import Signal


class BaseView(QWidget):
    """Base class for all view components."""
    
    def __init__(self, parent=None):
        """Initialize the base view."""
        super().__init__(parent)
        self.setup_ui()
        self.connect_signals()
    
    def setup_ui(self):
        """Setup the user interface - to be implemented by subclasses."""
        pass
    
    def connect_signals(self):
        """Connect signals - to be implemented by subclasses."""
        pass
    
    def show_message(self, title, message, message_type="info"):
        """
        Show a message to the user.
        
        Args:
            title (str): Dialog title
            message (str): Message content
            message_type (str): Type of message ("info", "warning", "error")
        """
        from PySide6.QtWidgets import QMessageBox
        
        if message_type == "warning":
            QMessageBox.warning(self, title, message)
        elif message_type == "error":
            QMessageBox.critical(self, title, message)
        else:
            QMessageBox.information(self, title, message)
    
    def show_question(self, title, question, default_yes=False):
        """
        Show a yes/no question dialog.
        
        Args:
            title (str): Dialog title
            question (str): Question text
            default_yes (bool): Whether Yes should be the default
            
        Returns:
            bool: True if user clicked Yes, False if No
        """
        from PySide6.QtWidgets import QMessageBox
        
        default = QMessageBox.Yes if default_yes else QMessageBox.No
        reply = QMessageBox.question(
            self, title, question,
            QMessageBox.Yes | QMessageBox.No,
            default
        )
        return reply == QMessageBox.Yes