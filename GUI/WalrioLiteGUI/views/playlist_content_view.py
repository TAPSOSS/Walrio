#!/usr/bin/env python3
"""
Playlist content view for Walrio GUI
Copyright (c) 2025 TAPS OSS
Project: https://github.com/TAPSOSS/Walrio
Licensed under the BSD-3-Clause License (see LICENSE file for details)

Contains the playlist content display and queue interaction buttons.
"""

import sys
import subprocess

try:
    from PySide6.QtWidgets import (
        QWidget, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem,
        QPushButton, QHeaderView, QLabel
    )
    from PySide6.QtCore import Qt, Signal
    from PySide6.QtGui import QFont
except ImportError:
    print("PySide6 not found. Installing...")
    subprocess.run([sys.executable, "-m", "pip", "install", "PySide6"])
    from PySide6.QtWidgets import (
        QWidget, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem,
        QPushButton, QHeaderView, QLabel
    )
    from PySide6.QtCore import Qt, Signal
    from PySide6.QtGui import QFont

from .base_view import BaseView


class PlaylistContentView(BaseView):
    """Playlist content tab widget for viewing selected playlist contents."""
    
    # Define signals
    add_to_queue_requested = Signal()
    replace_queue_requested = Signal()
    
    def __init__(self, parent=None):
        """Initialize the playlist content view."""
        super().__init__(parent)
    
    def setup_ui(self):
        """Setup the playlist content view UI."""
        layout = QVBoxLayout(self)
        
        # Current playlist info
        self.current_playlist_label = QLabel("No playlist selected")
        self.current_playlist_label.setAlignment(Qt.AlignCenter)
        font = QFont()
        font.setPointSize(11)
        font.setBold(True)
        self.current_playlist_label.setFont(font)
        layout.addWidget(self.current_playlist_label)
        
        # Playlist content table
        self.playlist_content_table = QTableWidget()
        self.playlist_content_table.setAlternatingRowColors(True)
        
        # Set up columns: same as queue for consistency
        self.playlist_content_table.setColumnCount(5)
        self.playlist_content_table.setHorizontalHeaderLabels(['Title', 'Album', 'Album Artist', 'Artist', 'Year'])
        
        # Configure column behavior
        header = self.playlist_content_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.Stretch)  # Title column stretches
        header.setSectionResizeMode(1, QHeaderView.Interactive)  # Album - manual resize
        header.setSectionResizeMode(2, QHeaderView.Interactive)  # Album Artist - manual resize
        header.setSectionResizeMode(3, QHeaderView.Interactive)  # Artist - manual resize
        header.setSectionResizeMode(4, QHeaderView.Fixed)  # Year - fixed width
        
        # Set reasonable default column widths
        self.playlist_content_table.setColumnWidth(1, 120)  # Album
        self.playlist_content_table.setColumnWidth(2, 120)  # Album Artist
        self.playlist_content_table.setColumnWidth(3, 100)  # Artist
        self.playlist_content_table.setColumnWidth(4, 50)   # Year
        
        # Performance optimizations
        self.playlist_content_table.setShowGrid(False)
        self.playlist_content_table.setWordWrap(False)
        self.playlist_content_table.setSelectionBehavior(QTableWidget.SelectRows)
        
        layout.addWidget(self.playlist_content_table)
        
        # Playlist to queue buttons
        playlist_to_queue_layout = QHBoxLayout()
        
        self.btn_add_to_queue = QPushButton("Add To Queue")
        self.btn_replace_queue = QPushButton("Override Queue")
        
        # Initially disable these buttons until a playlist is selected
        self.btn_add_to_queue.setEnabled(False)
        self.btn_replace_queue.setEnabled(False)
        
        playlist_to_queue_layout.addWidget(self.btn_add_to_queue)
        playlist_to_queue_layout.addWidget(self.btn_replace_queue)
        
        layout.addLayout(playlist_to_queue_layout)
    
    def connect_signals(self):
        """Connect the UI signals."""
        self.btn_add_to_queue.clicked.connect(self._on_add_to_queue)
        self.btn_replace_queue.clicked.connect(self._on_replace_queue)
    
    def _on_add_to_queue(self):
        """Handle add to queue button click."""
        self.add_to_queue_requested.emit()
    
    def _on_replace_queue(self):
        """Handle replace queue button click."""
        self.replace_queue_requested.emit()
    
    def update_playlist_content(self, playlist_name, songs):
        """
        Update the playlist content table with songs.
        
        Args:
            playlist_name (str): Name of the playlist being displayed
            songs (list): List of song dictionaries to display
        """
        # Update the playlist label
        self.current_playlist_label.setText(f"Playlist: {playlist_name} ({len(songs)} tracks)")
        
        # Clear and populate the table
        self.playlist_content_table.setRowCount(len(songs))
        
        for row, song in enumerate(songs):
            # Title
            title_item = QTableWidgetItem(song.get('title', 'Unknown Title'))
            self.playlist_content_table.setItem(row, 0, title_item)
            
            # Album
            album_item = QTableWidgetItem(song.get('album', 'Unknown Album'))
            self.playlist_content_table.setItem(row, 1, album_item)
            
            # Album Artist
            albumartist_item = QTableWidgetItem(song.get('albumartist', 'Unknown Album Artist'))
            self.playlist_content_table.setItem(row, 2, albumartist_item)
            
            # Artist
            artist_item = QTableWidgetItem(song.get('artist', 'Unknown Artist'))
            self.playlist_content_table.setItem(row, 3, artist_item)
            
            # Year
            year_item = QTableWidgetItem(str(song.get('year', '')))
            self.playlist_content_table.setItem(row, 4, year_item)
        
        # Enable playlist-to-queue buttons
        self.btn_add_to_queue.setEnabled(True)
        self.btn_replace_queue.setEnabled(True)
    
    def clear_playlist_content(self):
        """Clear the playlist content display."""
        self.current_playlist_label.setText("No playlist selected")
        self.playlist_content_table.setRowCount(0)
        
        # Disable playlist-to-queue buttons
        self.btn_add_to_queue.setEnabled(False)
        self.btn_replace_queue.setEnabled(False)
    
    def set_buttons_enabled(self, enabled):
        """Enable or disable the playlist-to-queue buttons."""
        self.btn_add_to_queue.setEnabled(enabled)
        self.btn_replace_queue.setEnabled(enabled)