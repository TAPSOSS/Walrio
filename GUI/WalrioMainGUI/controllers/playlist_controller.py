#!/usr/bin/env python3
"""
Playlist controller for Walrio GUI
Copyright (c) 2025 TAPS OSS
Project: https://github.com/TAPSOSS/Walrio
Licensed under the BSD-3-Clause License (see LICENSE file for details)

Controller for managing playlists and playlist interactions.
"""

import sys
import os
from pathlib import Path

# Add the parent directory to the Python path so we can import modules
sys.path.append(os.path.join(os.path.dirname(__file__), '../../..'))

try:
    from PySide6.QtCore import QObject, Signal
    from PySide6.QtWidgets import QMessageBox
except ImportError:
    import subprocess
    print("PySide6 not found. Installing...")
    subprocess.run([sys.executable, "-m", "pip", "install", "PySide6"])
    from PySide6.QtCore import QObject, Signal
    from PySide6.QtWidgets import QMessageBox

from modules.core import playlist
from ..models.data_models import Playlist
from ..models.workers import PlaylistWorker
from ..views.error_dialog import show_missing_files_dialog


class PlaylistController(QObject):
    """Controller for playlist management."""
    
    # Define signals
    playlist_songs_ready = Signal(list, str)  # songs, action ("add" or "replace")
    
    def __init__(self, app_state, playlist_sidebar, playlist_content_view):
        """
        Initialize the playlist controller.
        
        Args:
            app_state: Application state model
            playlist_sidebar: Playlist sidebar view
            playlist_content_view: Playlist content view
        """
        super().__init__()
        self.app_state = app_state
        self.playlist_sidebar = playlist_sidebar
        self.playlist_content_view = playlist_content_view
        self.playlist_worker = None  # Background worker for loading playlists
        
        self._setup_connections()
    
    def _setup_connections(self):
        """Setup signal connections."""
        # Playlist sidebar connections
        self.playlist_sidebar.playlist_selected.connect(self._on_playlist_selected)
        self.playlist_sidebar.playlist_add_requested.connect(self._on_add_playlist)
        self.playlist_sidebar.playlist_remove_requested.connect(self._on_remove_playlist)
        self.playlist_sidebar.playlist_refresh_requested.connect(self._on_refresh_playlists)
        
        # Playlist content view connections
        self.playlist_content_view.add_to_queue_requested.connect(self._on_add_to_queue)
        self.playlist_content_view.replace_queue_requested.connect(self._on_replace_queue)
    
    def _on_playlist_selected(self, playlist_name, playlist_path):
        """Handle playlist selection from sidebar.
        
        Args:
            playlist_name (str): Name of the selected playlist
            playlist_path (str): File path to the selected playlist
        """
        print(f"DEBUG: Playlist selection - name: '{playlist_name}', path: '{playlist_path}'")
        print(f"DEBUG: Available playlists: {list(self.app_state.loaded_playlists.keys())}")
        
        playlist_obj = self.app_state.get_playlist(playlist_name)
        if playlist_obj:
            songs = [song.to_dict() for song in playlist_obj.songs]
            
            # Update the selected playlist for queue operations
            self.app_state.selected_playlist_name = playlist_name
            self.app_state.selected_playlist_songs = songs
            
            # Update playlist content display
            self.playlist_content_view.update_playlist_content(playlist_name, songs)
            
            print(f"Selected playlist '{playlist_name}' ({len(songs)} tracks)")
        else:
            print(f"DEBUG: Playlist '{playlist_name}' not found in loaded playlists!")
            # Try to load it directly from the path
            try:
                songs = playlist.load_m3u_playlist(playlist_path)
                if songs:
                    # Store in application state
                    self.app_state.add_playlist(playlist_name, songs)
                    
                    # Convert to dict format for display
                    songs_dict = [song if isinstance(song, dict) else song.to_dict() for song in songs]
                    
                    # Update the selected playlist for queue operations
                    self.app_state.selected_playlist_name = playlist_name
                    self.app_state.selected_playlist_songs = songs_dict
                    
                    # Update playlist content display
                    self.playlist_content_view.update_playlist_content(playlist_name, songs_dict)
                    
                    print(f"Loaded and selected playlist '{playlist_name}' ({len(songs_dict)} tracks)")
            except Exception as e:
                print(f"DEBUG: Error loading playlist directly: {e}")
                self.playlist_content_view.show_message(
                    "Load Error", 
                    f"Could not load playlist '{playlist_name}': {str(e)}",
                    "error"
                )
    
    def _on_add_playlist(self, playlist_path):
        """Handle adding a new playlist.
        
        Args:
            playlist_path (str): File path to the playlist to add
        """
        playlist_path_obj = Path(playlist_path)
        playlist_name = playlist_path_obj.stem
        
        # Stop any existing playlist worker
        if self.playlist_worker and self.playlist_worker.isRunning():
            self.playlist_worker.stop()
            self.playlist_worker.wait()
        
        # Show progress bar
        self.playlist_sidebar.show_progress(True)
        
        # Create and start the playlist worker
        self.playlist_worker = PlaylistWorker(playlist_path, playlist_name)
        
        # Connect worker signals
        self.playlist_worker.progress_updated.connect(self._on_playlist_progress)
        self.playlist_worker.playlist_loaded.connect(self._on_playlist_loaded)
        self.playlist_worker.error.connect(self._on_playlist_error)
        
        # Start loading in background
        self.playlist_worker.start()
        print(f"Started background loading for playlist: {playlist_name}")
    
    def _on_playlist_progress(self, current, total, current_file):
        """Handle playlist loading progress updates.
        
        Args:
            current (int): Current file number
            total (int): Total number of files
            current_file (str): Name of file currently being processed
        """
        progress_percent = int((current / total) * 100) if total > 0 else 0
        print(f"Loading playlist: {current}/{total} ({progress_percent}%) - {current_file}")
        
        # Update progress bar in sidebar
        self.playlist_sidebar.update_progress(current, total, current_file)
    
    def _on_playlist_loaded(self, playlist_name, songs, missing_files):
        """Handle successful playlist loading.
        
        Args:
            playlist_name (str): Name of the loaded playlist
            songs (list): List of song dictionaries
            missing_files (list): List of file paths that could not be found
        """
        try:
            if songs:
                # Store in application state
                self.app_state.add_playlist(playlist_name, songs)
                
                # Add to sidebar
                success = self.playlist_sidebar.add_playlist_to_list(
                    playlist_name, self.playlist_worker.playlist_path, len(songs)
                )
                
                if success:
                    print(f"Successfully loaded playlist '{playlist_name}' with {len(songs)} tracks")
                    
                    # Show success message
                    success_msg = f"Successfully loaded '{playlist_name}' with {len(songs)} tracks."
                    if missing_files:
                        success_msg += f" ({len(missing_files)} files not found)"
                    
                    self.playlist_sidebar.show_message("Playlist Loaded", success_msg)
                    
                    # Show detailed error log if there are missing files
                    if missing_files:
                        show_missing_files_dialog(
                            f"Missing Files - {playlist_name}",
                            missing_files,
                            self.playlist_sidebar
                        )
            else:
                self.playlist_sidebar.show_message(
                    "Load Error", 
                    f"No valid tracks found in playlist '{playlist_name}'.",
                    "warning"
                )
        except Exception as e:
            self.playlist_sidebar.show_message(
                "Load Error", 
                f"Error storing playlist: {str(e)}",
                "error"
            )
        finally:
            # Hide progress bar and clean up worker
            self.playlist_sidebar.show_progress(False)
            self.playlist_worker = None
    
    def _on_playlist_error(self, error_message):
        """Handle playlist loading errors.
        
        Args:
            error_message (str): Error message from the worker
        """
        print(f"Playlist loading error: {error_message}")
        self.playlist_sidebar.show_message(
            "Load Error", 
            f"Error loading playlist: {error_message}",
            "error"
        )
        # Hide progress bar and clean up worker
        self.playlist_sidebar.show_progress(False)
        self.playlist_worker = None
    
    def _on_remove_playlist(self, playlist_name):
        """Handle removing a playlist.
        
        Args:
            playlist_name (str): Name of the playlist to remove
        """
        # Remove from application state
        success = self.app_state.remove_playlist(playlist_name)
        
        if success:
            # Remove from sidebar
            self.playlist_sidebar.remove_playlist_from_list(playlist_name)
            
            # Clear content view if this was the selected playlist
            if self.app_state.selected_playlist_name == playlist_name:
                self.app_state.selected_playlist_name = None
                self.app_state.selected_playlist_songs = []
                self.playlist_content_view.clear_playlist_content()
            
            print(f"Removed playlist '{playlist_name}' from loaded list")
            self.playlist_sidebar.show_message(
                "Playlist Removed", 
                f"'{playlist_name}' has been removed from the loaded playlists."
            )
    
    def _on_refresh_playlists(self):
        """Handle playlist refresh request."""
        # For now, this just clears and reloads if needed
        # Could be extended to scan a default playlists directory
        print("Playlist display refreshed")
    
    def _on_add_to_queue(self):
        """Handle adding selected playlist to queue."""
        if not self.app_state.selected_playlist_songs:
            self.playlist_content_view.show_message(
                "No Playlist Selected", 
                "Please select a playlist first."
            )
            return
        
        # Emit signal with songs and action
        self.playlist_songs_ready.emit(self.app_state.selected_playlist_songs.copy(), "add")
        
        print(f"Added {len(self.app_state.selected_playlist_songs)} tracks from '{self.app_state.selected_playlist_name}' to queue")
        self.playlist_content_view.show_message(
            "Added to Queue", 
            f"Added {len(self.app_state.selected_playlist_songs)} tracks to queue."
        )
    
    def _on_replace_queue(self):
        """Handle replacing queue with selected playlist."""
        if not self.app_state.selected_playlist_songs:
            self.playlist_content_view.show_message(
                "No Playlist Selected", 
                "Please select a playlist first."
            )
            return
        
        # Emit signal with songs and action
        self.playlist_songs_ready.emit(self.app_state.selected_playlist_songs.copy(), "replace")
        
        print(f"Replaced queue with {len(self.app_state.selected_playlist_songs)} tracks from '{self.app_state.selected_playlist_name}'")
        self.playlist_content_view.show_message(
            "Queue Replaced", 
            f"Queue replaced with {len(self.app_state.selected_playlist_songs)} tracks from '{self.app_state.selected_playlist_name}'."
        )