#!/usr/bin/env python3
"""
Playback controller for Walrio GUI
Copyright (c) 2025 TAPS OSS
Project: https://github.com/TAPSOSS/Walrio
Licensed under the BSD-3-Clause License (see LICENSE file for details)

Controller for managing audio playback operations.
"""

import sys
import os
import subprocess
from pathlib import Path

# Add the parent directory to the Python path so we can import modules
sys.path.append(os.path.join(os.path.dirname(__file__), '../../..'))

try:
    from PySide6.QtCore import QObject, Signal, QTimer
    from PySide6.QtWidgets import QApplication
except ImportError:
    print("PySide6 not found. Installing...")
    subprocess.run([sys.executable, "-m", "pip", "install", "PySide6"])
    from PySide6.QtCore import QObject, Signal, QTimer
    from PySide6.QtWidgets import QApplication

from ..models.workers import PlayerWorker


class PlaybackController(QObject):
    """Controller for playback management."""
    
    # Define signals
    track_changed = Signal(dict)  # song info
    playback_finished = Signal()
    queue_position_changed = Signal(int)  # current queue index
    
    def __init__(self, app_state, controls_view):
        """
        Initialize the playback controller.
        
        Args:
            app_state: Application state model
            controls_view: Controls view
        """
        super().__init__()
        self.app_state = app_state
        self.controls_view = controls_view
        self.player_worker = None
        
        self._setup_connections()
    
    def _setup_connections(self):
        """Setup signal connections."""
        # Controls view connections
        self.controls_view.play_pause_requested.connect(self._on_play_pause)
        self.controls_view.stop_requested.connect(self._on_stop)
        self.controls_view.previous_requested.connect(self._on_previous)
        self.controls_view.next_requested.connect(self._on_next)
        self.controls_view.loop_toggle_requested.connect(self._on_loop_toggle)
        self.controls_view.seek_started.connect(self._on_seek_start)
        self.controls_view.seek_ended.connect(self._on_seek_end)
        self.controls_view.volume_changed.connect(self._on_volume_changed)
    
    def _on_play_pause(self):
        """Handle play/pause button."""
        if not self.app_state.current_file:
            return
        
        if self.app_state.is_playing:
            self._pause_playback()
        else:
            # Check if we have a paused player worker to resume
            if self.player_worker and not self.app_state.is_playing:
                self._resume_playback()
            else:
                # Start fresh playback
                self._start_playback()
    
    def _on_stop(self):
        """Handle stop button."""
        self.stop_playback()
    
    def _on_previous(self):
        """Handle previous button."""
        if not self.app_state.queue_manager or not self.app_state.queue_manager.has_songs():
            return
        
        was_playing = self.app_state.is_playing
        
        # Use queue manager to move to previous track
        if self.app_state.queue_manager.previous_track():
            prev_song = self.app_state.queue_manager.current_song()
            if prev_song:
                self.app_state.current_file = prev_song.get('url') or prev_song.get('filepath')
                self.app_state.current_queue_index = self.app_state.queue_manager.current_index
                
                # Emit track changed signal
                self.track_changed.emit(prev_song)
                
                # Emit queue position changed signal
                self.queue_position_changed.emit(self.app_state.current_queue_index)
                
                # Fast track switching using existing PlayerWorker
                if was_playing and self.player_worker:
                    self.player_worker.play_new_song(self.app_state.current_file, self.app_state.duration)
                elif was_playing:
                    self._start_playback()
    
    def _on_next(self):
        """Handle next button."""
        if not self.app_state.queue_manager or not self.app_state.queue_manager.has_songs():
            return
        
        was_playing = self.app_state.is_playing
        
        # Use queue manager to move to next track
        if self.app_state.queue_manager.next_track():
            next_song = self.app_state.queue_manager.current_song()
            if next_song:
                self.app_state.current_file = next_song.get('url') or next_song.get('filepath')
                self.app_state.current_queue_index = self.app_state.queue_manager.current_index
                
                # Emit track changed signal
                self.track_changed.emit(next_song)
                
                # Emit queue position changed signal
                self.queue_position_changed.emit(self.app_state.current_queue_index)
                
                # Fast track switching using existing PlayerWorker
                if was_playing and self.player_worker:
                    self.player_worker.play_new_song(self.app_state.current_file, self.app_state.duration)
                elif was_playing:
                    self._start_playback()
    
    def _on_loop_toggle(self):
        """Handle loop toggle button."""
        if self.app_state.loop_mode == "off":
            self.app_state.loop_mode = "track"
            self.controls_view.set_loop_text("🔁 Repeat: Track")
            self.controls_view.set_loop_style(True)
        else:
            self.app_state.loop_mode = "off"
            self.controls_view.set_loop_text("🔁 Repeat: Off")
            self.controls_view.set_loop_style(False)
        
        print(f"Repeat mode changed to: {self.app_state.loop_mode}")
        
        # Update queue manager if one exists
        if self.app_state.queue_manager:
            self.app_state.queue_manager.set_repeat_mode(self.app_state.loop_mode)
    
    def _on_seek_start(self):
        """Handle when user starts seeking."""
        self.app_state.is_seeking = True
    
    def _on_seek_end(self, position):
        """Handle when user finishes seeking."""
        self.app_state.is_seeking = False
        self.app_state.position = position
        self.controls_view.set_time_current(self._format_time(position))
        
        # Try to seek the actual player to this position
        if self.player_worker:
            success = self.player_worker.seek(position)
            if not success:
                print(f"Seek to {position}s failed")
        
        # Clear pending position
        self.app_state.pending_position = 0
    
    def _on_volume_changed(self, volume):
        """Handle volume changes."""
        self.app_state.volume = volume
        
        # Set volume if player worker exists
        if self.player_worker:
            self.player_worker.set_volume(volume / 100.0)
    
    def load_and_play_song(self, index):
        """Load and play a song from the queue by index."""
        if 0 <= index < len(self.app_state.queue_songs):
            song = self.app_state.queue_songs[index]
            self.app_state.current_queue_index = index
            self.app_state.current_file = song['url']
            
            # Get metadata and update duration
            metadata = self._get_file_metadata(song['url'])
            self.app_state.duration = metadata.get('duration', 0)
            
            # Update controls
            self.controls_view.set_duration(self.app_state.duration)
            if self.app_state.duration > 0:
                self.controls_view.set_time_total(self._format_time(self.app_state.duration))
            else:
                self.controls_view.set_time_total("--:--")
            
            # Reset position
            self.app_state.reset_playback_state()
            self.controls_view.set_position(0)
            self.controls_view.set_time_current("00:00")
            
            # Enable controls
            self.controls_view.set_play_pause_enabled(True)
            self.controls_view.set_stop_enabled(True)
            
            # Emit track changed signal
            self.track_changed.emit(song)
            
            # Start playback
            self._start_playback()
    
    def _start_playback(self):
        """Start audio playback."""
        if not self.app_state.current_file:
            return
        
        # Log song starting
        current_title = Path(self.app_state.current_file).stem
        if self.app_state.queue_songs and hasattr(self.app_state, 'current_queue_index'):
            queue_position = f"#{self.app_state.current_queue_index + 1}/{len(self.app_state.queue_songs)}"
        else:
            queue_position = "Single song"
        print(f"Starting song: {current_title} ({queue_position})")
        
        # Create or update player worker
        if not self.player_worker:
            self.player_worker = PlayerWorker(self.app_state.current_file, self.app_state.duration)
            self.player_worker.playback_finished.connect(self._on_playback_finished)
            self.player_worker.error.connect(self._on_playback_error)
            self.player_worker.position_updated.connect(self._on_position_updated)
            self.player_worker.start()
        else:
            self.player_worker.play_new_song(self.app_state.current_file, self.app_state.duration)
        
        # Update queue manager
        self.app_state.update_queue_manager()
        
        # Ensure queue manager has correct repeat mode
        if self.app_state.queue_manager:
            self.app_state.queue_manager.set_repeat_mode(self.app_state.loop_mode)
        
        # Set daemon loop mode to 'none' for queue-controlled progression
        if self.player_worker:
            QTimer.singleShot(200, lambda: self.player_worker.send_command("loop none"))
        
        self.app_state.is_playing = True
        self.controls_view.set_play_pause_text("⏸ Pause")
        self.controls_view.set_stop_enabled(True)
    
    def _pause_playback(self):
        """Pause audio playback."""
        if not self.app_state.is_playing or not self.player_worker:
            return
            
        self.app_state.is_playing = False
        self.controls_view.set_play_pause_text("▶ Resume")
        
        if self.player_worker:
            self.player_worker.pause()
    
    def _resume_playback(self):
        """Resume audio playback."""
        if self.app_state.is_playing or not self.player_worker:
            return
        
        self.app_state.is_playing = True
        self.controls_view.set_play_pause_text("⏸ Pause")
        
        if self.player_worker:
            self.player_worker.resume()
    
    def stop_playback(self):
        """Stop audio playback."""
        # Set state first
        self.app_state.is_playing = False
        self.controls_view.set_play_pause_text("▶ Play")
        
        # Immediately disable the stop button to prevent multiple clicks
        self.controls_view.set_stop_enabled(False)
        
        # Reset position and UI immediately
        self.app_state.reset_playback_state()
        self.controls_view.set_position(0)
        self.controls_view.set_time_current("00:00")
        
        # Force GUI to update immediately
        QApplication.processEvents()
        
        if self.player_worker:
            # Disconnect signals first
            try:
                self.player_worker.position_updated.disconnect()
                self.player_worker.playback_finished.disconnect()
                self.player_worker.error.disconnect()
            except:
                pass  # Signals might already be disconnected
            
            # Stop the worker thread
            self.player_worker.stop()
            
            # Wait for thread to finish
            if not self.player_worker.wait(3000):
                self.player_worker.terminate()
                self.player_worker.wait()
            
            self.player_worker = None
        
        # Re-enable play button
        self.controls_view.set_play_pause_enabled(True)
    
    def _on_position_updated(self, position):
        """Handle position updates from player worker."""
        if not self.app_state.is_playing or not self.player_worker:
            return
            
        if self.controls_view.is_slider_pressed():
            # Store the real position for reference but don't update UI
            self.app_state.pending_position = position
            return
            
        # Cap position at duration to prevent going beyond song length
        if self.app_state.duration > 0 and position >= self.app_state.duration:
            position = self.app_state.duration
            
        # Update position and UI
        self.app_state.position = position
        self.controls_view.set_position(position)
        self.controls_view.set_time_current(self._format_time(position))
    
    def _on_playback_finished(self):
        """Handle when playback finishes."""
        print("Playback finished - song has ended")
        
        # Prevent multiple calls
        if self.app_state.is_processing_finish:
            print("Already processing playback finish - ignoring duplicate event")
            return
        self.app_state.is_processing_finish = True
        
        # Emit signal to main controller
        self.playback_finished.emit()
        
        # Reset the flag
        self.app_state.is_processing_finish = False
    
    def _on_playback_error(self, error):
        """Handle playback errors."""
        self.controls_view.show_message("Playback Error", error, "error")
        self.stop_playback()
    
    def update_queue_state(self):
        """Update internal state when queue changes."""
        # Update queue manager
        self.app_state.update_queue_manager()
    
    def _get_file_metadata(self, filepath):
        """Get metadata for an audio file."""
        try:
            modules_dir = Path(__file__).parent.parent.parent.parent / "modules"
            
            # Get full metadata using --show
            result = subprocess.run(
                ["python", "walrio.py", "metadata", "--show", filepath],
                cwd=str(modules_dir),
                capture_output=True,
                text=True,
                timeout=10
            )
            
            if result.returncode == 0 and result.stdout.strip():
                # Parse the metadata output
                metadata = {}
                for line in result.stdout.strip().split('\n'):
                    if ':' in line and not line.startswith('='):
                        key, value = line.split(':', 1)
                        key = key.strip().lower().replace(' ', '_')
                        value = value.strip()
                        if value and value != 'None' and value != 'Unknown':
                            metadata[key] = value
                
                # Get duration separately
                duration = 0
                try:
                    duration_result = subprocess.run(
                        ["python", "walrio.py", "metadata", "--duration", filepath],
                        cwd=str(modules_dir),
                        capture_output=True,
                        text=True,
                        timeout=10
                    )
                    if duration_result.returncode == 0 and duration_result.stdout.strip():
                        duration = float(duration_result.stdout.strip())
                except:
                    pass
                
                return {
                    'artist': metadata.get('artist') or metadata.get('album_artist') or 'Unknown Artist',
                    'title': metadata.get('title') or Path(filepath).stem,
                    'album': metadata.get('album') or 'Unknown Album',
                    'duration': duration
                }
        except Exception as e:
            print(f"Error getting metadata for {filepath}: {e}")
        
        return {
            'artist': 'Unknown Artist',
            'title': Path(filepath).stem,
            'album': 'Unknown Album',
            'duration': 0
        }
    
    def _format_time(self, seconds):
        """Format time in MM:SS format."""
        minutes = int(seconds // 60)
        seconds = int(seconds % 60)
        return f"{minutes:02d}:{seconds:02d}"