#!/usr/bin/env python3
"""
Queue controller for Walrio GUI
Copyright (c) 2025 TAPS OSS
Project: https://github.com/TAPSOSS/Walrio
Licensed under the BSD-3-Clause License (see LICENSE file for details)

Controller for managing the playback queue.
"""

import sys
import os
from pathlib import Path

# Add the parent directory to the Python path so we can import modules
sys.path.append(os.path.join(os.path.dirname(__file__), '../../..'))

try:
    from PySide6.QtCore import QObject, Signal
    from PySide6.QtWidgets import QMessageBox, QFileDialog
except ImportError:
    import subprocess
    print("PySide6 not found. Installing...")
    subprocess.run([sys.executable, "-m", "pip", "install", "PySide6"])
    from PySide6.QtCore import QObject, Signal
    from PySide6.QtWidgets import QMessageBox, QFileDialog

from modules.core.playlist import create_m3u_playlist
from ..models.workers import QueueWorker
from ..models.data_models import Song


class QueueController(QObject):
    """Controller for queue management."""
    
    # Define signals
    song_selected = Signal(int)  # row index
    queue_updated = Signal()
    navigation_state_changed = Signal(bool)  # enabled state
    shuffle_state_changed = Signal(bool)  # shuffle enabled state
    
    def __init__(self, app_state, queue_view):
        """
        Initialize the queue controller.
        
        Args:
            app_state: Application state model
            queue_view: Queue view
        """
        super().__init__()
        self.app_state = app_state
        self.queue_view = queue_view
        self.queue_worker = None
        
        self._setup_connections()
    
    def _setup_connections(self):
        """Setup signal connections."""
        # Queue view connections
        self.queue_view.files_add_requested.connect(self._on_add_files)
        self.queue_view.queue_clear_requested.connect(self._on_clear_queue)
        self.queue_view.song_remove_requested.connect(self._on_remove_song)
        self.queue_view.song_selected.connect(self._on_song_selected)
        self.queue_view.queue_reordered.connect(self._on_queue_reordered)
        self.queue_view.queue_save_requested.connect(self._on_save_queue)
    
    def _on_add_files(self, filepaths):
        """Handle adding files to queue.
        
        Args:
            filepaths (list): List of file paths to add to the queue
        """
        if not filepaths:
            return
        
        # Disable the add button while processing
        self.queue_view.set_add_button_enabled(False)
        self.queue_view.set_add_button_text(f"Processing {len(filepaths)} files...")
        
        # Create and start the queue worker
        self.queue_worker = QueueWorker(filepaths)
        self.queue_worker.file_processed.connect(self._on_file_processed)
        self.queue_worker.all_files_processed.connect(self._on_all_files_processed)
        self.queue_worker.error.connect(self._on_queue_error)
        self.queue_worker.start()
    
    def _on_file_processed(self, song_dict):
        """Handle when a file has been processed by the queue worker.
        
        Args:
            song_dict (dict): Dictionary containing processed song metadata
        """
        # Add song to queue
        self.app_state.queue_songs.append(song_dict)
        
        # Update queue display
        self._update_queue_display()
        
        # Update queue manager
        self.app_state.update_queue_manager()
        
        # Log song addition
        song_title = song_dict.get('title', 'Unknown')
        print(f"Added to queue: {song_title} (Queue size: {len(self.app_state.queue_songs)})")
        
        # Enable navigation buttons if we have multiple songs
        if len(self.app_state.queue_songs) > 1:
            self.navigation_state_changed.emit(True)
        
        # If no current file, load the first song from queue
        if not self.app_state.current_file and len(self.app_state.queue_songs) == 1:
            self._load_song_from_queue(0)
    
    def _on_all_files_processed(self):
        """Handle when all files have been processed."""
        # Re-enable the add button
        self.queue_view.set_add_button_enabled(True)
        self.queue_view.set_add_button_text("Add To Queue")
        
        # Clean up the worker
        if self.queue_worker:
            self.queue_worker.deleteLater()
            self.queue_worker = None
    
    def _on_queue_error(self, error_message):
        """Handle queue processing errors.
        
        Args:
            error_message (str): Description of the error that occurred during processing
        """
        self.queue_view.show_message("Queue Error", f"Error processing files: {error_message}", "error")
        
        # Re-enable the add button
        self.queue_view.set_add_button_enabled(True)  
        self.queue_view.set_add_button_text("Add To Queue")
        
        # Clean up the worker
        if self.queue_worker:
            self.queue_worker.deleteLater()
            self.queue_worker = None
    
    def _on_clear_queue(self):
        """Handle clearing the queue."""
        self.app_state.queue_songs.clear()
        self.app_state.current_queue_index = 0
        self._update_queue_display()
        
        # Clear current file if it was from queue
        if self.app_state.current_file:
            self.app_state.current_file = None
            self.navigation_state_changed.emit(False)
    
    def _on_remove_song(self, row):
        """Handle removing a song from the queue.
        
        Args:
            row (int): Index of the song to remove from the queue
        """
        if 0 <= row < len(self.app_state.queue_songs):
            # Remove the song
            self.app_state.queue_songs.pop(row)
            
            # Update current index if needed
            if row < self.app_state.current_queue_index:
                self.app_state.current_queue_index -= 1
            elif row == self.app_state.current_queue_index and row >= len(self.app_state.queue_songs):
                self.app_state.current_queue_index = 0
            
            self._update_queue_display()
            
            # If queue is empty, clear current file
            if not self.app_state.queue_songs:
                self.app_state.current_file = None
                self.navigation_state_changed.emit(False)
            else:
                # Update navigation buttons
                self.navigation_state_changed.emit(len(self.app_state.queue_songs) > 1)
    
    def _on_song_selected(self, row):
        """Handle song selection for playback.
        
        Args:
            row (int): Index of the selected song in the queue
        """
        if 0 <= row < len(self.app_state.queue_songs):
            self._load_song_from_queue(row)
            self.song_selected.emit(row)
    
    def _on_queue_reordered(self, start, end, destination):
        """Handle queue reordering via drag and drop.
        
        Args:
            start (int): Starting row index of the moved item
            end (int): Ending row index of the moved item
            destination (int): Destination row index where the item was dropped
        """
        dest_row = int(destination) 
        start_row = int(start)
        
        print(f"Drag-drop: Moving row {start_row} to {dest_row}")
        
        if start_row != dest_row and 0 <= start_row < len(self.app_state.queue_songs):
            # Perform the move operation
            moved_song = self.app_state.queue_songs.pop(start_row)
            insert_pos = dest_row if dest_row < start_row else dest_row - 1
            insert_pos = max(0, min(insert_pos, len(self.app_state.queue_songs)))
            self.app_state.queue_songs.insert(insert_pos, moved_song)
            
            print(f"Moved '{moved_song.get('title', 'Unknown')}' from {start_row} to {insert_pos}")
            
            # Update current queue index efficiently
            if self.app_state.current_file and self.app_state.current_file:
                for i, song in enumerate(self.app_state.queue_songs):
                    if song['url'] == self.app_state.current_file:
                        self.app_state.current_queue_index = i
                        break
            
            # Update queue manager efficiently  
            if self.app_state.queue_manager:
                self.app_state.queue_manager.songs = self.app_state.queue_songs
                self.app_state.queue_manager.current_index = self.app_state.current_queue_index
            
            # Rebuild table content to sync with reordered queue_songs
            print("Rebuilding table content after drag-drop...")
            self._update_queue_display()
    
    def _on_save_queue(self):
        """Handle saving queue as playlist."""
        if not self.app_state.queue_songs:
            self.queue_view.show_message("Empty Queue", "The queue is empty. Add some songs first.")
            return
        
        # Get save file path from user
        file_path, _ = QFileDialog.getSaveFileName(
            self.queue_view,
            "Save Queue as Playlist",
            "queue_playlist.m3u",
            "M3U Playlist Files (*.m3u);;All Files (*)"
        )
        
        if file_path:
            try:
                # Generate playlist name from filename
                playlist_name = Path(file_path).stem
                
                # Save the playlist
                success = create_m3u_playlist(
                    self.app_state.queue_songs, 
                    file_path, 
                    use_absolute_paths=True, 
                    playlist_name=playlist_name
                )
                
                if success:
                    self.queue_view.show_message(
                        "Playlist Saved", 
                        f"Queue saved as playlist:\n{file_path}\n\n{len(self.app_state.queue_songs)} songs saved."
                    )
                else:
                    self.queue_view.show_message(
                        "Save Failed", 
                        f"Failed to save playlist to:\n{file_path}",
                        "error"
                    )
                    
            except Exception as e:
                self.queue_view.show_message(
                    "Save Error", 
                    f"Error saving playlist:\n{str(e)}",
                    "error"
                )
    
    def _load_song_from_queue(self, index):
        """Load a song from the queue by index.
        Handles missing files on manual selection by attempting to play and checking result.
        
        Args:
            index (int): Index of the song in the queue to load
        """
        if 0 <= index < len(self.app_state.queue_songs):
            song = self.app_state.queue_songs[index]
            file_path = song['url']
            
            # Check if file was previously marked as missing
            was_missing = song.get('file_missing', False)
            
            # Always attempt to load, even if marked as missing (manual selection override)
            self.app_state.current_queue_index = index
            self.app_state.current_file = file_path
            
            # Reset position
            self.app_state.reset_playback_state()
            
            # If this was a manual attempt on a missing file, check if it's now available
            if was_missing:
                import os
                if os.path.exists(file_path):
                    print(f"[INFO] Previously missing file now found: {file_path}")
                    # Update the song data to reflect it's no longer missing
                    song['file_missing'] = False
                    # Update queue manager if it exists
                    if (hasattr(self.app_state, 'queue_manager') and 
                        self.app_state.queue_manager and 
                        index < len(self.app_state.queue_manager.songs)):
                        self.app_state.queue_manager.songs[index]['file_missing'] = False
                else:
                    print(f"[WARNING] Manual attempt on missing file: {file_path}")
                    # File is still missing - playback will likely fail and show error
            
            # Update queue display to highlight current song
            self._update_queue_display()
    
    def _update_queue_display(self):
        """Update the queue display."""
        self.queue_view.update_queue_display(
            self.app_state.queue_songs,
            self.app_state.current_queue_index if self.app_state.current_file else -1
        )
    
    def update_current_position(self, queue_index):
        """Update the queue display highlighting for the current position.
        
        Args:
            queue_index (int): Index of the currently playing song in the queue
        """
        self.app_state.current_queue_index = queue_index
        self._update_queue_display()
    
    def update_current_position_and_scroll(self, queue_index):
        """Update the queue display highlighting and scroll to center on the current song.
        This method is called when the position changes due to next/previous button clicks.
        
        Args:
            queue_index (int): Index of the currently playing song in the queue
        """
        self.app_state.current_queue_index = queue_index
        self._update_queue_display()
        # Scroll the queue view to center on the newly playing song
        self.queue_view.scroll_to_current_song(queue_index)
    
    def toggle_shuffle_mode(self):
        """Toggle shuffle mode on/off."""
        if not self.app_state.queue_manager:
            self.queue_view.show_message("Queue Error", "Queue manager not available.", "error")
            return
            
        # Toggle the shuffle mode
        current_shuffle = self.app_state.queue_manager.shuffle_mode
        new_shuffle = not current_shuffle
        self.app_state.queue_manager.set_shuffle_mode(new_shuffle)
        
        # Update the app state shuffle flag if it exists
        if hasattr(self.app_state, 'shuffle_mode'):
            self.app_state.shuffle_mode = new_shuffle
        
        # Emit signal to update UI
        self.shuffle_state_changed.emit(new_shuffle)
    
    def handle_playlist_to_queue(self, songs, action):
        """Handle adding or replacing queue with playlist songs.
        
        Args:
            songs (list): List of song dictionaries to add to the queue
            action (str): Action to perform - "add" to append or "replace" to clear and set
        """
        if action == "replace":
            # Clear current queue
            self.app_state.queue_songs.clear()
            self.app_state.current_queue_index = 0
        
        # Add playlist songs to queue
        self.app_state.queue_songs.extend(songs)
        
        # Update queue display
        self._update_queue_display()
        
        # Update queue manager
        self.app_state.update_queue_manager()
        
        # Enable navigation buttons if we have songs
        if self.app_state.queue_songs:
            self.navigation_state_changed.emit(True)
        
        # Emit queue updated signal
        self.queue_updated.emit()
        
        print(f"Playlist {action}d in queue: {len(songs)} songs")