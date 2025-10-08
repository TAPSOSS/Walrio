#!/usr/bin/env python3
"""
Error dialog for displaying detailed error logs with copy functionality
Copyright (c) 2025 TAPS OSS
Project: https://github.com/TAPSOSS/Walrio
Licensed under the BSD-3-Clause License (see LICENSE file for details)

Shows detailed error information in a scrollable dialog with copy functionality.
"""

import sys
import subprocess

try:
    from PySide6.QtWidgets import (
        QDialog, QVBoxLayout, QHBoxLayout, QLabel, QTextEdit, 
        QPushButton, QScrollArea, QApplication
    )
    from PySide6.QtCore import Qt
    from PySide6.QtGui import QFont
except ImportError:
    print("PySide6 not found. Installing...")
    subprocess.run([sys.executable, "-m", "pip", "install", "PySide6"])
    from PySide6.QtWidgets import (
        QDialog, QVBoxLayout, QHBoxLayout, QLabel, QTextEdit, 
        QPushButton, QScrollArea, QApplication
    )
    from PySide6.QtCore import Qt
    from PySide6.QtGui import QFont


class ErrorLogDialog(QDialog):
    """Dialog for showing detailed error logs with copy functionality."""
    
    def __init__(self, title, missing_files, parent=None):
        """Initialize the error log dialog.
        
        Args:
            title (str): Dialog title
            missing_files (list): List of missing file paths
            parent (QWidget): Parent widget
        """
        super().__init__(parent)
        self.missing_files = missing_files
        self.setup_ui(title)
    
    def setup_ui(self, title):
        """Setup the dialog UI.
        
        Args:
            title (str): Dialog title
        """
        self.setWindowTitle(title)
        self.setModal(True)
        self.resize(600, 400)
        
        # Main layout
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)
        
        # Title and summary
        if self.missing_files:
            summary_text = f"Found {len(self.missing_files)} files that could not be loaded:"
        else:
            summary_text = "No missing files detected."
        
        summary_label = QLabel(summary_text)
        summary_font = QFont()
        summary_font.setPointSize(12)
        summary_font.setBold(True)
        summary_label.setFont(summary_font)
        layout.addWidget(summary_label)
        
        if self.missing_files:
            # Scrollable text area for the log
            self.log_text = QTextEdit()
            self.log_text.setReadOnly(True)
            self.log_text.setFont(QFont("Courier", 9))  # Monospace font
            
            # Format the missing files log
            log_content = self._format_error_log()
            self.log_text.setPlainText(log_content)
            
            layout.addWidget(self.log_text)
            
            # Button layout
            button_layout = QHBoxLayout()
            
            # Copy log button
            self.copy_button = QPushButton("Copy Log")
            self.copy_button.clicked.connect(self._copy_log_to_clipboard)
            button_layout.addWidget(self.copy_button)
            
            # Spacer
            button_layout.addStretch()
        else:
            # No errors case - just add some space
            layout.addStretch()
            button_layout = QHBoxLayout()
        
        # Close button
        close_button = QPushButton("Close")
        close_button.clicked.connect(self.accept)
        close_button.setDefault(True)
        button_layout.addWidget(close_button)
        
        layout.addLayout(button_layout)
    
    def _format_error_log(self):
        """Format the missing files into a detailed log.
        
        Returns:
            str: Formatted log content
        """
        if not self.missing_files:
            return "No missing files found."
        
        log_lines = [
            "MISSING FILES REPORT",
            "=" * 50,
            f"Generated: {self._get_timestamp()}",
            f"Total missing files: {len(self.missing_files)}",
            "",
            "FILES NOT FOUND:",
            "-" * 20
        ]
        
        for i, file_path in enumerate(self.missing_files, 1):
            log_lines.append(f"{i:3d}. {file_path}")
        
        log_lines.extend([
            "",
            "=" * 50,
            "These files were referenced in the playlist but could not be found on disk.",
            "Please verify the file paths and ensure the files exist at the specified locations."
        ])
        
        return "\n".join(log_lines)
    
    def _get_timestamp(self):
        """Get current timestamp for the log.
        
        Returns:
            str: Formatted timestamp
        """
        from datetime import datetime
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    def _copy_log_to_clipboard(self):
        """Copy the entire log to clipboard."""
        clipboard = QApplication.clipboard()
        clipboard.setText(self.log_text.toPlainText())
        
        # Temporarily change button text to show success
        original_text = self.copy_button.text()
        self.copy_button.setText("Copied!")
        
        # Reset button text after 2 seconds
        from PySide6.QtCore import QTimer
        QTimer.singleShot(2000, lambda: self.copy_button.setText(original_text))


def show_missing_files_dialog(title, missing_files, parent=None):
    """Convenience function to show the missing files dialog.
    
    Args:
        title (str): Dialog title
        missing_files (list): List of missing file paths
        parent (QWidget): Parent widget
        
    Returns:
        int: Dialog result (QDialog.Accepted or QDialog.Rejected)
    """
    dialog = ErrorLogDialog(title, missing_files, parent)
    return dialog.exec()