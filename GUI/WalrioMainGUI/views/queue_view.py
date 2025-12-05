#!/usr/bin/env python3
"""
Queue view for Walrio GUI
Copyright (c) 2025 TAPS OSS
Project: https://github.com/TAPSOSS/Walrio
Licensed under the BSD-3-Clause License (see LICENSE file for details)

Contains the queue table and management controls.
"""

import sys
import subprocess

try:
    from PySide6.QtWidgets import (
        QWidget, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem,
        QPushButton, QHeaderView, QMenu, QFileDialog, QAbstractItemView
    )
    from PySide6.QtCore import Qt, Signal
    from PySide6.QtGui import QColor, QAction
except ImportError:
    print("PySide6 not found. Installing...")
    subprocess.run([sys.executable, "-m", "pip", "install", "PySide6"])
    from PySide6.QtWidgets import (
        QWidget, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem,
        QPushButton, QHeaderView, QMenu, QFileDialog, QAbstractItemView
    )
    from PySide6.QtCore import Qt, Signal
    from PySide6.QtGui import QColor, QAction

from .base_view import BaseView


class QueueView(BaseView):
    """Queue tab widget for managing the playback queue."""
    
    # Define signals
    files_add_requested = Signal(list)  # list of filepaths
    queue_clear_requested = Signal()
    song_remove_requested = Signal(int)  # row index
    song_selected = Signal(int)  # row index for playing
    queue_reordered = Signal(int, int, int)  # start, end, destination
    queue_save_requested = Signal()
    
    def __init__(self, parent=None):
        """Initialize the queue view."""
        super().__init__(parent)
    
    def setup_ui(self):
        """Setup the queue view UI."""
        layout = QVBoxLayout(self)
        
        # Create table widget for queue display with metadata columns
        self.queue_table = QTableWidget()
        self.queue_table.setAlternatingRowColors(True)
        
        # Set up columns: Title, Album, Album Artist, Artist, Year
        self.queue_table.setColumnCount(7)
        self.queue_table.setHorizontalHeaderLabels(['Title', 'Album', 'Album Artist', 'Artist', 'Year', 'Length', 'Filepath'])
        
        # Enable resizable columns
        header = self.queue_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.Stretch)  # Title column stretches
        header.setSectionResizeMode(1, QHeaderView.Interactive)  # Album - manual resize
        header.setSectionResizeMode(2, QHeaderView.Interactive)  # Album Artist - manual resize
        header.setSectionResizeMode(3, QHeaderView.Interactive)  # Artist - manual resize
        header.setSectionResizeMode(4, QHeaderView.Fixed)  # Year - fixed width
        header.setSectionResizeMode(5, QHeaderView.Fixed)  # Length - fixed width
        header.setSectionResizeMode(6, QHeaderView.Interactive)  # Filepath - manual resize
        self.queue_table.setColumnWidth(4, 60)
        self.queue_table.setColumnWidth(5, 80)
        
        # Enable right-click context menu on header for column visibility
        header.setContextMenuPolicy(Qt.CustomContextMenu)
        
        # Set reasonable default column widths
        self.queue_table.setColumnWidth(1, 120)  # Album
        self.queue_table.setColumnWidth(2, 120)  # Album Artist  
        self.queue_table.setColumnWidth(3, 100)  # Artist
        self.queue_table.setColumnWidth(4, 50)   # Year
        
        # Allow manual column resizing
        header.setSectionsMovable(False)  # Don't allow column reordering
        header.setStretchLastSection(False)
        
        # Enable drag and drop for reordering rows
        self.queue_table.setDragDropMode(QTableWidget.InternalMove)
        self.queue_table.setDefaultDropAction(Qt.MoveAction)
        self.queue_table.setDragDropOverwriteMode(False)
        self.queue_table.setSelectionBehavior(QTableWidget.SelectRows)
        
        # Performance optimizations
        self.queue_table.setAutoScroll(True)
        self.queue_table.setVerticalScrollMode(QTableWidget.ScrollPerPixel)
        self.queue_table.setAlternatingRowColors(True)
        self.queue_table.setShowGrid(False)
        self.queue_table.setWordWrap(False)
        self.queue_table.viewport().setAcceptDrops(True)
        self.queue_table.setDragEnabled(True)
        self.queue_table.setDropIndicatorShown(True)
        
        layout.addWidget(self.queue_table)
        
        # Add/Remove queue buttons
        queue_buttons_layout = QHBoxLayout()
        self.btn_add_files = QPushButton("Add To Queue")
        self.btn_clear_queue = QPushButton("Clear Queue")
        self.btn_remove_selected = QPushButton("Remove From Queue")
        self.btn_save_queue = QPushButton("Save as Playlist")
        
        queue_buttons_layout.addWidget(self.btn_add_files)
        queue_buttons_layout.addWidget(self.btn_remove_selected)
        queue_buttons_layout.addWidget(self.btn_clear_queue)
        queue_buttons_layout.addWidget(self.btn_save_queue)
        layout.addLayout(queue_buttons_layout)
    
    def connect_signals(self):
        """Connect the UI signals."""
        self.queue_table.itemClicked.connect(self._on_item_clicked)
        self.queue_table.itemDoubleClicked.connect(self._on_item_double_clicked)
        self.queue_table.model().rowsMoved.connect(self._on_rows_moved)
        
        header = self.queue_table.horizontalHeader()
        header.customContextMenuRequested.connect(self._show_column_context_menu)
        
        self.btn_add_files.clicked.connect(self._on_add_files)
        self.btn_clear_queue.clicked.connect(self._on_clear_queue)
        self.btn_remove_selected.clicked.connect(self._on_remove_selected)
        self.btn_save_queue.clicked.connect(self._on_save_queue)
    
    def _on_item_clicked(self, item):
        """Handle single-click on queue item (selection only)."""
        row = item.row()
        print(f"Selected queue item #{row + 1}")
    
    def _on_item_double_clicked(self, item):
        """Handle double-click on queue item (play song)."""
        row = item.row()
        self.song_selected.emit(row)
    
    def _on_rows_moved(self, parent, start, end, destination, row):
        """Handle drag-and-drop reordering."""
        self.queue_reordered.emit(start, end, row)
    
    def _show_column_context_menu(self, position):
        """Show context menu for column visibility."""
        header = self.queue_table.horizontalHeader()
        column_names = ["Title", "Album", "Album Artist", "Artist", "Year", "Length", "Filepath"]
        
        menu = QMenu(self)
        
        for col, name in enumerate(column_names):
            action = menu.addAction(name)
            action.setCheckable(True)
            action.setChecked(not header.isSectionHidden(col))
            action.triggered.connect(lambda checked, column=col: self._toggle_column_visibility(column, checked))
        
        menu.exec_(header.mapToGlobal(position))
    
    def _toggle_column_visibility(self, column, visible):
        """Toggle the visibility of a table column."""
        header = self.queue_table.horizontalHeader()
        if visible:
            header.showSection(column)
        else:
            header.hideSection(column)
    
    def _on_add_files(self):
        """Handle add files button click."""
        filepaths, _ = QFileDialog.getOpenFileNames(
            self, "Add Audio Files to Queue", "",
            "Audio Files (*.mp3 *.flac *.ogg *.wav *.m4a *.aac *.opus)"
        )
        
        if filepaths:
            self.files_add_requested.emit(filepaths)
    
    def _on_clear_queue(self):
        """Handle clear queue button click."""
        self.queue_clear_requested.emit()
    
    def _on_remove_selected(self):
        """Handle remove selected button click."""
        current_row = self.queue_table.currentRow()
        if current_row >= 0:
            self.song_remove_requested.emit(current_row)
    
    def _on_save_queue(self):
        """Handle save queue button click."""
        self.queue_save_requested.emit()
    
    def update_queue_display(self, songs, current_index=-1):
        """
        Update the queue table with songs.
        
        Args:
            songs (list): List of song dictionaries
            current_index (int): Index of currently playing song (-1 for none)
        """
        # Store songs data for access during highlighting
        self.songs_data = songs
        # Block signals for better performance during bulk updates
        self.queue_table.blockSignals(True)
        self.queue_table.setUpdatesEnabled(False)
        
        try:
            # Only resize if the row count actually changed
            if self.queue_table.rowCount() != len(songs):
                self.queue_table.setRowCount(len(songs))
            
            # Batch update items to reduce redraws  
            for i, song in enumerate(songs):
                # Format duration from seconds to MM:SS
                duration_seconds = song.get('length', 0)
                print(f"DEBUG: Queue song {i}: title={song.get('title', 'Unknown')}, length={duration_seconds}")
                if duration_seconds and duration_seconds > 0:
                    minutes = int(duration_seconds // 60)
                    seconds = int(duration_seconds % 60)
                    duration_text = f"{minutes}:{seconds:02d}"
                else:
                    duration_text = ""
                
                # Get filepath - use url or filepath field
                filepath = song.get('url', song.get('filepath', ''))
                
                texts = [
                    song.get('title', 'Unknown Title'),
                    song.get('album', 'Unknown Album'),
                    song.get('albumartist', song.get('artist', 'Unknown Artist')),
                    song.get('artist', 'Unknown Artist'), 
                    str(song.get('year', '')),
                    duration_text,
                    filepath
                ]
                
                is_missing = song.get('file_missing', False)
                
                # Update all columns for this row
                for col, text in enumerate(texts):
                    item = self.queue_table.item(i, col)
                    if item is None:
                        item = QTableWidgetItem(text)
                        item.setFlags(item.flags() & ~Qt.ItemIsEditable)  # Make non-editable
                        self.queue_table.setItem(i, col, item)
                    elif item.text() != text:
                        item.setText(text)
                    
                    # Apply visual styling for missing files
                    if is_missing:
                        item.setForeground(QColor(128, 128, 128))  # Gray text
                        item.setBackground(QColor(255, 200, 200, 128))  # Light red background at 50% opacity
                        font = item.font()
                        font.setItalic(True)
                        item.setFont(font)
                    else:
                        item.setForeground(QColor(0, 0, 0))  # Normal black text
                        item.setData(Qt.BackgroundRole, None)  # Clear background
                        font = item.font()
                        font.setItalic(False)
                        item.setFont(font)
            
            # Update highlighting
            self._update_highlighting(current_index)
            
        finally:
            # Re-enable signals and updates
            self.queue_table.setUpdatesEnabled(True) 
            self.queue_table.blockSignals(False)
            self.queue_table.setSortingEnabled(False)
    
    def _update_highlighting(self, current_index):
        """Update highlighting of the currently playing song."""
        for row in range(self.queue_table.rowCount()):
            is_current = (row == current_index)
            is_missing = False
            
            # Check if this song is missing (if we have the data)
            if hasattr(self, 'songs_data') and row < len(self.songs_data):
                is_missing = self.songs_data[row].get('file_missing', False)
                
            for col in range(5):
                item = self.queue_table.item(row, col)
                if item:
                    if is_current:
                        item.setBackground(QColor(200, 255, 200))  # Light green background
                        font = item.font()
                        font.setBold(True)
                        item.setFont(font)
                    else:
                        # Clear the background to use default system colors
                        item.setData(Qt.BackgroundRole, None)
                        font = item.font()
                        font.setBold(False)
                        item.setFont(font)
                    
                    # Preserve missing file styling regardless of current status
                    if is_missing:
                        item.setForeground(QColor(128, 128, 128))  # Gray text
                        if not is_current:  # Don't override current song background
                            item.setBackground(QColor(255, 200, 200, 128))  # Light red background at 50% opacity
                        font = item.font()
                        font.setItalic(True)
                        item.setFont(font)
                    elif not is_current:  # Only reset if not current (current styling takes precedence)
                        item.setForeground(QColor(0, 0, 0))  # Normal black text
                        item.setData(Qt.BackgroundRole, None)  # Clear background
                        font = item.font()
                        font.setItalic(False)
                        item.setFont(font)
    
    def set_add_button_text(self, text):
        """Set the text of the add files button (for progress indication)."""
        self.btn_add_files.setText(text)
    
    def set_add_button_enabled(self, enabled):
        """Enable or disable the add files button."""
        self.btn_add_files.setEnabled(enabled)
    
    def clear_table(self):
        """Clear all items from the queue table."""
        self.queue_table.setRowCount(0)
    
    def get_current_row(self):
        """Get the currently selected row."""
        return self.queue_table.currentRow()
    
    def scroll_to_current_song(self, index):
        """Scroll the table to center on the currently playing song.
        
        Args:
            index (int): Index of the currently playing song to center on
        """
        if 0 <= index < self.queue_table.rowCount():
            # Create a QModelIndex for the row to scroll to (using the first column)
            item = self.queue_table.item(index, 0)
            if item:
                # Scroll to position the item in the center of the viewport
                self.queue_table.scrollToItem(item, QAbstractItemView.PositionAtCenter)