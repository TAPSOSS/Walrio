#!/usr/bin/env python3
"""
Playlist sidebar view for Walrio GUI
Copyright (c) 2025 TAPS OSS
Project: https://github.com/TAPSOSS/Walrio
Licensed under the BSD-3-Clause License (see LICENSE file for details)

Contains the playlist sidebar with playlist management functionality.
"""

import sys
import subprocess

try:
    from PySide6.QtWidgets import (
        QWidget, QVBoxLayout, QHBoxLayout, QLabel, QListWidget, QListWidgetItem,
        QPushButton, QGroupBox, QMenu, QFileDialog, QProgressBar
    )
    from PySide6.QtCore import Qt, Signal
    from PySide6.QtGui import QFont, QAction
except ImportError:
    print("PySide6 not found. Installing...")
    subprocess.run([sys.executable, "-m", "pip", "install", "PySide6"])
    from PySide6.QtWidgets import (
        QWidget, QVBoxLayout, QHBoxLayout, QLabel, QListWidget, QListWidgetItem,
        QPushButton, QGroupBox, QMenu, QFileDialog, QProgressBar
    )
    from PySide6.QtCore import Qt, Signal
    from PySide6.QtGui import QFont, QAction

from .base_view import BaseView


class PlaylistSidebarView(BaseView):
    """Playlist sidebar widget for managing playlists."""
    
    # Define signals
    playlist_selected = Signal(str, str)  # playlist_name, playlist_path
    playlist_add_requested = Signal(str)  # playlist_path
    playlist_remove_requested = Signal(str)  # playlist_name
    playlist_refresh_requested = Signal()
    
    def __init__(self, parent=None):
        """Initialize the playlist sidebar."""
        super().__init__(parent)
    
    def setup_ui(self):
        """Setup the playlist sidebar UI."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        
        # Playlist header
        playlist_header = QLabel("Playlists")
        playlist_header.setAlignment(Qt.AlignCenter)
        header_font = QFont()
        header_font.setPointSize(12)
        header_font.setBold(True)
        playlist_header.setFont(header_font)
        layout.addWidget(playlist_header)
        
        # Create a container for the playlist list and buttons
        playlist_container = QGroupBox("Playlists")
        container_layout = QVBoxLayout(playlist_container)
        
        # Playlist list widget
        self.playlist_list = QListWidget()
        self.playlist_list.setMaximumWidth(250)
        self.playlist_list.setMinimumWidth(200)
        
        # Enable context menu for playlist operations
        self.playlist_list.setContextMenuPolicy(Qt.CustomContextMenu)
        
        container_layout.addWidget(self.playlist_list)
        
        # Progress bar and label (initially hidden)
        progress_layout = QVBoxLayout()
        
        self.progress_label = QLabel("")
        self.progress_label.setAlignment(Qt.AlignCenter)
        self.progress_label.hide()
        
        self.progress_bar = QProgressBar()
        self.progress_bar.setMinimum(0)
        self.progress_bar.setMaximum(100)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(True)
        self.progress_bar.hide()
        
        progress_layout.addWidget(self.progress_label)
        progress_layout.addWidget(self.progress_bar)
        container_layout.addLayout(progress_layout)
        
        # Playlist management buttons
        playlist_buttons_layout = QVBoxLayout()
        
        self.btn_load_playlist = QPushButton("Add Playlist")
        self.btn_delete_playlist = QPushButton("Remove Playlist")
        self.btn_refresh_playlists = QPushButton("Refresh")
        
        # Set button widths to match playlist list width
        button_width = 230
        self.btn_load_playlist.setFixedWidth(button_width)
        self.btn_delete_playlist.setFixedWidth(button_width)
        self.btn_refresh_playlists.setFixedWidth(button_width)
        
        # Initially disable delete button until a playlist is selected
        self.btn_delete_playlist.setEnabled(False)
        
        playlist_buttons_layout.addWidget(self.btn_load_playlist)
        playlist_buttons_layout.addWidget(self.btn_delete_playlist)
        playlist_buttons_layout.addWidget(self.btn_refresh_playlists)
        
        container_layout.addLayout(playlist_buttons_layout)
        layout.addWidget(playlist_container)
    
    def connect_signals(self):
        """Connect the UI signals."""
        self.playlist_list.itemClicked.connect(self._on_playlist_clicked)
        self.playlist_list.itemSelectionChanged.connect(self._on_selection_changed)
        self.playlist_list.customContextMenuRequested.connect(self._show_context_menu)
        
        self.btn_load_playlist.clicked.connect(self._on_add_playlist)
        self.btn_delete_playlist.clicked.connect(self._on_remove_playlist)
        self.btn_refresh_playlists.clicked.connect(self._on_refresh_playlists)
    
    def _on_playlist_clicked(self, item):
        """Handle playlist item click."""
        playlist_path = item.data(Qt.UserRole)
        display_text = item.text().split(' (')[0]  # Remove track count from display
        
        # Extract the base name without extension to match how playlists are stored
        from pathlib import Path
        playlist_name = Path(display_text).stem  # Remove extension from display name
        
        self.playlist_selected.emit(playlist_name, playlist_path)
    
    def _on_selection_changed(self):
        """Handle playlist selection changes."""
        selected_items = self.playlist_list.selectedItems()
        self.btn_delete_playlist.setEnabled(len(selected_items) > 0)
    
    def _show_context_menu(self, position):
        """Show context menu for playlist operations."""
        item = self.playlist_list.itemAt(position)
        if not item:
            return
            
        menu = QMenu(self)
        
        # Show playlist content action
        show_action = QAction("Show Playlist", self)
        show_action.triggered.connect(lambda: self._on_playlist_clicked(item))
        menu.addAction(show_action)
        
        menu.addSeparator()
        
        # Remove from list action
        remove_action = QAction("Remove from List", self)
        remove_action.triggered.connect(lambda: self._remove_playlist_by_item(item))
        menu.addAction(remove_action)
        
        # Show menu
        menu.exec(self.playlist_list.mapToGlobal(position))
    
    def _remove_playlist_by_item(self, item):
        """Remove playlist by item (used by context menu)."""
        self.playlist_list.setCurrentItem(item)
        self._on_remove_playlist()
    
    def _on_add_playlist(self):
        """Handle add playlist button click."""
        playlist_path, _ = QFileDialog.getOpenFileName(
            self, "Add Playlist", "",
            "Playlist Files (*.m3u *.m3u8 *.pls *.xspf);;M3U Files (*.m3u *.m3u8);;All Files (*)"
        )
        
        if playlist_path:
            self.playlist_add_requested.emit(playlist_path)
    
    def _on_remove_playlist(self):
        """Handle remove playlist button click."""
        current_item = self.playlist_list.currentItem()
        if not current_item:
            self.show_message("No Selection", "Please select a playlist to remove.")
            return
        
        display_text = current_item.text().split(' (')[0]  # Remove track count
        
        # Extract the base name without extension to match how playlists are stored
        from pathlib import Path
        playlist_name = Path(display_text).stem  # Remove extension from display name
        
        if self.show_question("Remove Playlist", 
                            f"Are you sure you want to remove '{playlist_name}' from the loaded playlists?\n\n"
                            f"This will only remove it from the list, not delete the actual file."):
            self.playlist_remove_requested.emit(playlist_name)
    
    def _on_refresh_playlists(self):
        """Handle refresh button click."""
        self.playlist_refresh_requested.emit()
    
    def add_playlist_to_list(self, name, filepath, track_count):
        """
        Add a playlist to the sidebar list.
        
        Args:
            name (str): Playlist name
            filepath (str): Path to the playlist file
            track_count (int): Number of tracks in playlist
        """
        from pathlib import Path
        
        # Check if playlist already exists
        for i in range(self.playlist_list.count()):
            item = self.playlist_list.item(i)
            if item.data(Qt.UserRole) == filepath:
                self.show_message("Playlist Already Loaded", 
                                f"Playlist '{Path(filepath).name}' is already in the list.")
                return False
        
        # Create display text with extension and track count
        extension = Path(filepath).suffix.upper()
        display_text = f"{name}{extension} ({track_count} tracks)"
        
        # Create list item
        item = QListWidgetItem(display_text)
        item.setData(Qt.UserRole, filepath)
        item.setToolTip(f"Path: {filepath}\nType: {extension}\nTracks: {track_count}")
        self.playlist_list.addItem(item)
        
        return True
    
    def remove_playlist_from_list(self, name):
        """
        Remove a playlist from the sidebar list.
        
        Args:
            name (str): Playlist name to remove
        """
        for i in range(self.playlist_list.count()):
            item = self.playlist_list.item(i)
            display_text = item.text().split(' (')[0]  # Remove track count
            
            # Extract the base name without extension to match how playlists are stored
            from pathlib import Path
            item_name = Path(display_text).stem  # Remove extension from display name
            
            if item_name == name:  # Use exact match instead of startswith
                self.playlist_list.takeItem(i)
                break
        
        # Disable remove button if no playlists remain
        if self.playlist_list.count() == 0:
            self.btn_delete_playlist.setEnabled(False)
    
    def clear_playlist_list(self):
        """Clear all playlists from the list."""
        self.playlist_list.clear()
        self.btn_delete_playlist.setEnabled(False)
    
    def get_selected_playlist_path(self):
        """Get the filepath of the currently selected playlist."""
        current_item = self.playlist_list.currentItem()
        if current_item:
            return current_item.data(Qt.UserRole)
        return None
    
    def show_progress(self, visible=True):
        """Show or hide the progress bar and label.
        
        Args:
            visible (bool): Whether to show the progress elements
        """
        if visible:
            self.progress_label.show()
            self.progress_bar.show()
        else:
            self.progress_label.hide()
            self.progress_bar.hide()
    
    def update_progress(self, current, total, current_file=None):
        """Update the progress bar and label.
        
        Args:
            current (int): Current file number
            total (int): Total number of files
            current_file (str): Name of current file being processed (optional)
        """
        if total > 0:
            progress_percent = int((current / total) * 100)
            self.progress_bar.setValue(progress_percent)
            
            # Update label with X/Y format
            progress_text = f"{current}/{total} imported"
            if current_file:
                progress_text += f"\n{current_file}"
            
            self.progress_label.setText(progress_text)
        
        # Show progress elements if not already visible
        if not self.progress_bar.isVisible():
            self.show_progress(True)