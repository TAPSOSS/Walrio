#!/usr/bin/env python3
"""
Main window view for Walrio GUI
Copyright (c) 2025 TAPS OSS
Project: https://github.com/TAPSOSS/Walrio
Licensed under the BSD-3-Clause License (see LICENSE file for details)

Contains the main window layout and tab management.
"""

import sys
import subprocess

try:
    from PySide6.QtWidgets import (
        QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
        QSplitter, QTabWidget, QLabel
    )
    from PySide6.QtCore import Qt, Signal
    from PySide6.QtGui import QFont
except ImportError:
    print("PySide6 not found. Installing...")
    subprocess.run([sys.executable, "-m", "pip", "install", "PySide6"])
    from PySide6.QtWidgets import (
        QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
        QSplitter, QTabWidget, QLabel
    )
    from PySide6.QtCore import Qt, Signal
    from PySide6.QtGui import QFont

from .base_view import BaseView


class MainWindow(QMainWindow):
    """Main window for the Walrio music player."""
    
    # Define signals for inter-component communication
    window_closing = Signal()
    
    def __init__(self):
        """Initialize the main window."""
        super().__init__()
        self.setup_ui()
    
    def setup_ui(self):
        """Setup the main window UI."""
        self.setWindowTitle("Walrio")
        self.setGeometry(300, 300, 1200, 600)  # Made wider and taller for sidebar + tabs
        
        # Central widget with horizontal splitter
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QHBoxLayout(central_widget)
        main_layout.setContentsMargins(5, 5, 5, 5)
        
        # Create splitter to separate playlist sidebar from main content
        self.splitter = QSplitter(Qt.Horizontal)
        main_layout.addWidget(self.splitter)
        
        # Right side - Tabbed content area
        self.tabs_widget = QWidget()
        self.tabs_layout = QVBoxLayout(self.tabs_widget)
        self.tabs_layout.setContentsMargins(0, 0, 0, 0)
        
        # Create tab widget for main content
        self.tab_widget = QTabWidget()
        self.tabs_layout.addWidget(self.tab_widget)
        
        # Track info at the bottom
        self.track_label = QLabel("No file selected")
        self.track_label.setAlignment(Qt.AlignCenter)
        font = QFont()
        font.setPointSize(12)
        font.setBold(True)
        self.track_label.setFont(font)
        self.tabs_layout.addWidget(self.track_label)
        
        self.splitter.addWidget(self.tabs_widget)
        
        # Set splitter proportions (playlist sidebar takes 1/4, main content takes 3/4)
        self.splitter.setSizes([300, 900])
    
    def add_playlist_sidebar(self, sidebar_widget):
        """Add the playlist sidebar widget to the splitter."""
        # Insert at the beginning (left side)
        self.splitter.insertWidget(0, sidebar_widget)
    
    def add_tab(self, widget, title):
        """Add a tab to the tab widget."""
        self.tab_widget.addTab(widget, title)
    
    def set_current_tab(self, index):
        """Set the current tab by index."""
        self.tab_widget.setCurrentIndex(index)
    
    def add_controls(self, controls_widget):
        """Add the controls widget to the bottom of the layout."""
        self.tabs_layout.addWidget(controls_widget)
    
    def set_track_info(self, text):
        """Set the track information text."""
        self.track_label.setText(text)
    
    def closeEvent(self, event):
        """Handle window close event."""
        self.window_closing.emit()
        event.accept()