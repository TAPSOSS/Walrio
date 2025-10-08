#!/usr/bin/env python3
"""
Main controller for Walrio GUI
Copyright (c) 2025 TAPS OSS
Project: https://github.com/TAPSOSS/Walrio
Licensed under the BSD-3-Clause License (see LICENSE file for details)

Main controller that coordinates all other controllers and manages application state.
"""

import sys
import os
import subprocess
from pathlib import Path

# Add the parent directory to the Python path so we can import modules
sys.path.append(os.path.join(os.path.dirname(__file__), '../../..'))

try:
    from PySide6.QtWidgets import QApplication, QMessageBox
    from PySide6.QtCore import QTimer, QObject
except ImportError:
    print("PySide6 not found. Installing...")
    subprocess.run([sys.executable, "-m", "pip", "install", "PySide6"])
    from PySide6.QtWidgets import QApplication, QMessageBox
    from PySide6.QtCore import QTimer, QObject

from ..models.data_models import ApplicationState, Song, Playlist
from ..models.workers import QueueWorker, PlayerWorker
from ..views.main_window import MainWindow
from ..views.playlist_sidebar import PlaylistSidebarView
from ..views.queue_view import QueueView
from ..views.playlist_content_view import PlaylistContentView
from ..views.controls_view import ControlsView

from .playlist_controller import PlaylistController
from .queue_controller import QueueController
from .playback_controller import PlaybackController

from modules.core import playlist


class MainController(QObject):
    """Main controller that coordinates all components of the Walrio GUI."""
    
    def __init__(self):
        """Initialize the main controller."""
        super().__init__()
        
        # Initialize application state
        self.app_state = ApplicationState()
        
        # Initialize all views
        self._initialize_views()
        
        # Set up view layout
        self._setup_views()
        
        # Initialize sub-controllers
        self._setup_controllers()
        
        # Setup connections between controllers and views
        self._setup_connections()
        
        # Setup main window timer
        self._setup_timer()
    
    def _initialize_views(self):
        """Initialize all view components."""
        self.main_window = MainWindow()
        self.playlist_sidebar = PlaylistSidebarView()
        self.queue_view = QueueView()
        self.playlist_content_view = PlaylistContentView()
        self.controls_view = ControlsView()
    
    def _setup_views(self):
        """Set up and connect all views."""
        # Add the playlist sidebar to the left
        self.main_window.add_playlist_sidebar(self.playlist_sidebar)
        
        # Add tabs for main content (Queue first since it's the default)
        self.main_window.add_tab(self.queue_view, "Queue")
        self.main_window.add_tab(self.playlist_content_view, "Playlist")
        
        # Set default tab to Queue (now at index 0)
        self.main_window.set_current_tab(0)  # Start with Queue tab
        
        # Add controls to the bottom
        self.main_window.add_controls(self.controls_view)
        
        # Show the main window
        self.main_window.show()
    
    def _setup_controllers(self):
        """Initialize sub-controllers."""
        self.playlist_controller = PlaylistController(
            self.app_state,
            self.playlist_sidebar,
            self.playlist_content_view
        )
        
        self.queue_controller = QueueController(
            self.app_state,
            self.queue_view
        )
        
        self.playback_controller = PlaybackController(
            self.app_state,
            self.controls_view
        )
    
    def _setup_connections(self):
        """Setup connections between controllers and views."""
        # Main window connections
        self.main_window.window_closing.connect(self._on_window_closing)
        
        # Cross-controller connections
        self.playlist_controller.playlist_songs_ready.connect(
            self.queue_controller.handle_playlist_to_queue
        )
        
        # When a playlist is selected, switch to the playlist tab to show content
        self.playlist_sidebar.playlist_selected.connect(self._on_playlist_selected_switch_tab)
        
        self.queue_controller.song_selected.connect(
            self.playback_controller.load_and_play_song
        )
        
        self.queue_controller.queue_updated.connect(
            self.playback_controller.update_queue_state
        )
        
        self.playback_controller.track_changed.connect(
            self._on_track_changed
        )
        
        self.playback_controller.playback_finished.connect(
            self._on_playback_finished
        )
        
        # Update queue highlighting when position changes via next/previous
        self.playback_controller.queue_position_changed.connect(
            self.queue_controller.update_current_position
        )
        
        # Update navigation buttons based on queue state
        self.queue_controller.navigation_state_changed.connect(
            self.controls_view.set_navigation_enabled
        )
        
        # Connect shuffle button to toggle shuffle mode
        self.controls_view.shuffle_requested.connect(
            self.queue_controller.toggle_shuffle_mode
        )
        
        # Update shuffle button state based on queue availability
        self.queue_controller.navigation_state_changed.connect(
            self.controls_view.set_shuffle_enabled
        )
        
        # Update shuffle button appearance when mode changes
        self.queue_controller.shuffle_state_changed.connect(
            self._on_shuffle_state_changed
        )
    
    def _setup_timer(self):
        """Setup the main application timer."""
        self.timer = QTimer()
        self.timer.timeout.connect(self._update_ui)
        self.timer.start(100)  # Update UI every 100ms
    
    def _update_ui(self):
        """Update UI elements (called by timer)."""
        # Most updates now come from signals, this is just for any additional updates
        pass
    
    def _on_track_changed(self, song_info):
        """Handle track changes.
        
        Args:
            song_info (dict): Dictionary containing track metadata with 'artist' and 'title' keys
        """
        if song_info:
            track_text = f"{song_info.get('artist', 'Unknown Artist')} - {song_info.get('title', 'Unknown Title')}"
            self.main_window.set_track_info(track_text)
        else:
            self.main_window.set_track_info("No file selected")
    
    def _on_playback_finished(self):
        """Handle playback finished events."""
        # Check if we should continue with next track or stop
        if self.app_state.queue_manager:
            should_continue, next_song = self.app_state.queue_manager.handle_song_finished()
            
            if should_continue and next_song:
                # Update current file and queue index
                self.app_state.current_file = next_song.get('url') or next_song.get('filepath')
                self.app_state.current_queue_index = self.app_state.queue_manager.current_index
                
                # Emit queue position changed signal to update highlighting
                self.playback_controller.queue_position_changed.emit(self.app_state.current_queue_index)
                
                # Emit track changed signal for UI updates
                self.playback_controller.track_changed.emit(next_song)
                
                # Update displays
                self.queue_view.update_queue_display(
                    self.app_state.queue_songs,
                    self.app_state.current_queue_index
                )
                
                # Let playback controller handle the new song
                self.playback_controller.load_and_play_song(self.app_state.current_queue_index)
            else:
                # End of queue/playlist
                self.playback_controller.stop_playback()
    
    def _on_window_closing(self):
        """Handle application shutdown."""
        # Stop playbook
        if hasattr(self.playback_controller, 'player_worker') and self.playback_controller.player_worker:
            self.playback_controller.player_worker.stop()
            self.playback_controller.player_worker.wait()
    
    def _on_playlist_selected_switch_tab(self, playlist_path):
        """Switch to playlist tab when a playlist is selected.
        
        Args:
            playlist_path (str): Path to the selected playlist file
        """
        # Switch to the playlist content tab (index 1)
        self.main_window.set_current_tab(1)
    
    def _on_shuffle_state_changed(self, shuffle_enabled):
        """Handle shuffle state changes.
        
        Args:
            shuffle_enabled (bool): Whether shuffle mode is enabled
        """
        # Update shuffle button text and style
        if shuffle_enabled:
            self.controls_view.set_shuffle_text("🔀 Shuffle: On")
            self.controls_view.set_shuffle_style(True)
        else:
            self.controls_view.set_shuffle_text("🔀 Shuffle: Off")
            self.controls_view.set_shuffle_style(False)
    
    def show(self):
        """Show the main window."""
        self.main_window.show()
    
    def format_time(self, seconds):
        """
        Format time in MM:SS format.
        
        Args:
            seconds (float): Time in seconds to format.
            
        Returns:
            str: Formatted time string in MM:SS format.
        """
        minutes = int(seconds // 60)
        seconds = int(seconds % 60)
        return f"{minutes:02d}:{seconds:02d}"