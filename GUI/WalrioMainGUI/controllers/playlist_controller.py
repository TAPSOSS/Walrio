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
        """Handle playlist selection from sidebar."""
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
        """Handle adding a new playlist."""
        playlist_path_obj = Path(playlist_path)
        playlist_name = playlist_path_obj.stem
        
        try:
            # Load playlist using playlist module
            songs = playlist.load_m3u_playlist(playlist_path)
            if songs:
                # Store in application state
                self.app_state.add_playlist(playlist_name, songs)
                
                # Add to sidebar
                success = self.playlist_sidebar.add_playlist_to_list(
                    playlist_name, playlist_path, len(songs)
                )
                
                if success:
                    print(f"Loaded playlist '{playlist_name}' with {len(songs)} tracks")
                
            else:
                self.playlist_sidebar.show_message(
                    "Load Error", 
                    f"Could not load playlist from '{playlist_path}'.",
                    "warning"
                )
        except Exception as e:
            self.playlist_sidebar.show_message(
                "Load Error", 
                f"Error loading playlist: {str(e)}",
                "error"
            )
    
    def _on_remove_playlist(self, playlist_name):
        """Handle removing a playlist."""
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