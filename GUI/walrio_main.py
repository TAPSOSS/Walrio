#!/usr/bin/env python3
"""
Walrio Music Player GUI
Copyright (c) 2025 TAPS OSS
Project: https://github.com/TAPSOSS/Walrio
Licensed under the BSD-3-Clause License (see LICENSE file for details)

A music player GUI built with PySide that uses as many Walrio music library modules as possible to
play, modify, display, and do other things relating to audio files.
"""

import sys
import os
import subprocess
import threading
import time
from pathlib import Path

# Add the parent directory to the Python path so we can import modules
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from modules.core.queue import QueueManager, RepeatMode  # Import queue system
from modules.core import playlist  # Import playlist module

try:
    from PySide6.QtWidgets import (
        QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
        QPushButton, QSlider, QLabel, QFileDialog, QMessageBox, QListWidget, QListWidgetItem,
        QTableWidget, QTableWidgetItem, QHeaderView, QMenu, QSplitter, QTabWidget
    )
    from PySide6.QtCore import QTimer, QThread, Signal, Qt
    from PySide6.QtGui import QFont, QColor, QAction
except ImportError:
    print("PySide6 not found. Installing...")
    subprocess.run([sys.executable, "-m", "pip", "install", "PySide6"])
    from PySide6.QtWidgets import (
        QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
        QPushButton, QSlider, QLabel, QFileDialog, QMessageBox, QListWidget, QListWidgetItem,
        QTableWidget, QTableWidgetItem, QHeaderView, QMenu, QSplitter, QTabWidget
    )
    from PySide6.QtCore import QTimer, QThread, Signal, Qt
    from PySide6.QtGui import QFont, QColor, QAction


class QueueWorker(QThread):
    """Worker thread for queue operations like metadata extraction."""
    
    # Signals
    file_processed = Signal(dict)  # Emitted when a file's metadata is extracted
    all_files_processed = Signal()  # Emitted when all files are done
    error = Signal(str)  # Emitted on error
    
    def __init__(self, filepaths):
        """
        Initialize the QueueWorker thread.
        
        Args:
            filepaths (list): List of file paths to process for metadata extraction.
        """
        super().__init__()
        self.filepaths = filepaths
        self.should_stop = False
    
    def run(self):
        """Process files in background thread."""
        try:
            for filepath in self.filepaths:
                if self.should_stop:
                    break
                
                # Debug: Print the actual filepath being processed
                print(f"QueueWorker processing: {repr(filepath)}")
                    
                # Get metadata for the file
                metadata = self._get_file_metadata(filepath)
                song = {
                    'url': filepath,
                    'title': metadata['title'],
                    'artist': metadata['artist'],
                    'album': metadata['album'],
                    'albumartist': metadata['albumartist'],
                    'year': metadata['year'],
                    'duration': metadata['duration']
                }
                
                # Debug: Print the song data
                print(f"QueueWorker emitting song: {song['title']} -> {repr(song['url'])}")
                
                # Emit the processed file
                self.file_processed.emit(song)
                
            # Signal that all files are processed
            if not self.should_stop:
                self.all_files_processed.emit()
                
        except Exception as e:
            self.error.emit(f"Error processing files: {str(e)}")
    
    def _get_file_metadata(self, filepath):
        """
        Get metadata for an audio file including artist, title, album, and duration.
        
        Args:
            filepath (str): Path to the audio file to extract metadata from.
            
        Returns:
            dict: Dictionary containing song metadata with keys like 'title', 'artist', 'album', 'albumartist', 'year', 'duration'.
        """
        try:
            modules_dir = Path(__file__).parent.parent / "modules"
            
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
                        key = key.strip().lower().replace(' ', '_').replace('/', '_')
                        value = value.strip()
                        metadata[key] = value
                
                # Debug: Show what we extracted for year and album artist
                print(f"DEBUG {Path(filepath).name}: date_year='{metadata.get('date_year')}', album_artist='{metadata.get('album_artist')}'")
                
                # Return structured metadata with fallbacks
                return {
                    'title': metadata.get('title', Path(filepath).stem),
                    'artist': metadata.get('artist', ''),
                    'album': metadata.get('album', ''),
                    'albumartist': metadata.get('album_artist', metadata.get('artist', '')),
                    'year': metadata.get('date_year', metadata.get('year', metadata.get('date', ''))),
                    'duration': self._parse_duration(metadata.get('duration', '0:00'))
                }
            else:
                # Fallback if metadata extraction fails (error reading metadata)
                return {
                    'title': Path(filepath).stem,
                    'artist': 'Unknown',
                    'album': 'Unknown',
                    'albumartist': 'Unknown',
                    'year': 'Unknown',
                    'duration': 0
                }
                
        except Exception as e:
            print(f"Error getting metadata for {filepath}: {e}")
            return {
                'title': Path(filepath).stem,
                'artist': 'Unknown', 
                'album': 'Unknown',
                'albumartist': 'Unknown',
                'year': 'Unknown',
                'duration': 0
            }
    
    def _parse_duration(self, duration_str):
        """
        Parse duration string like '3:45 (225.6 seconds)' and return seconds.
        
        Args:
            duration_str (str): Duration string in format like '3:45 (225.6 seconds)'.
            
        Returns:
            float: Duration in seconds, or 0 if parsing fails.
        """
        try:
            if '(' in duration_str and 'seconds)' in duration_str:
                # Extract seconds from parentheses
                seconds_part = duration_str.split('(')[1].split(' seconds)')[0]
                return int(float(seconds_part))
            elif ':' in duration_str:
                # Parse MM:SS format
                parts = duration_str.split(':')
                if len(parts) == 2:
                    minutes, seconds = parts
                    return int(minutes) * 60 + int(seconds)
            return 0
        except:
            return 0
    
    def stop(self):
        """Stop the worker thread."""
        self.should_stop = True


class PlayerWorker(QThread):
    """Worker thread for handling audio playback operations with event-based communication."""
    
    position_updated = Signal(float)
    playback_finished = Signal()
    song_starting = Signal(dict)  # New signal for when songs start
    error = Signal(str)
    
    def __init__(self, filepath, duration=0):
        """
        Initialize the PlayerWorker thread.
        
        Args:
            filepath (str): Path to the audio file to play.
            duration (float): Expected duration of the audio file in seconds.
        """
        super().__init__()
        self.filepath = filepath
        self.duration = duration
        self.should_stop = False
        self.stop_event_listener = False  # Separate flag for event listener thread
        self.start_time = None
        self.paused_duration = 0
        self.pause_start = None
        self.last_known_position = 0
        self.process = None
        self.event_socket = None  # Socket for receiving daemon events
    
    def run(self):
        """Run the audio player with event-based communication."""
        try:
            # Start the audio process
            self._start_audio_process()
            
            # Start dedicated event listener thread instead of inline event checking
            self._start_event_listener_thread()
            
            # Main monitoring loop (position updates only, no event checking)
            while not self.should_stop and self.process.poll() is None:
                
                if not self.pause_start and not self.should_stop:
                    # Query actual position from the audio daemon every 0.1 seconds for smooth seekbar
                    actual_position = self.get_position()
                    
                    if actual_position >= 0:  # Emit position updates for all valid positions including 0
                        # Use the actual audio position
                        self.last_known_position = actual_position
                        if not self.should_stop:
                            # Emit position update every 0.1 seconds for smooth seekbar
                            self.position_updated.emit(actual_position)
                
                # Short sleep to avoid busy waiting
                time.sleep(0.1)
            
            # Process ended - this should be rare now with event-based system
            if not self.should_stop:
                print("PlayerWorker: Process ended unexpectedly")
                self.playback_finished.emit()
                
        except Exception as e:
            error_msg = f"Error in player worker: {e}"
            print(error_msg)
            self.error.emit(error_msg)
        finally:
            self._cleanup_event_socket()
    
    def _send_socket_command(self, command):
        """Send a command to the player daemon via socket.
        
        Args:
            command (str): Command to send to the daemon
            
        Returns:
            tuple: (success: bool, response: str)
        """
        if not (self.process and self.process.poll() is None):
            return False, "No active player process"
            
        try:
            import socket
            import tempfile
            import os
            
            # Find the socket file for this daemon
            temp_dir = tempfile.gettempdir()
            socket_files = []
            
            for filename in os.listdir(temp_dir):
                if filename.startswith("walrio_player_") and filename.endswith(".sock"):
                    socket_path = os.path.join(temp_dir, filename)
                    if os.path.exists(socket_path):
                        socket_files.append((socket_path, os.path.getmtime(socket_path)))
            
            if not socket_files:
                return False, "No socket file found"
                
            # Use the most recent socket file
            socket_path = max(socket_files, key=lambda x: x[1])[0]
            
            # Connect to socket and send command
            sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            try:
                sock.connect(socket_path)
                sock.send(command.encode('utf-8'))
                response = sock.recv(1024).decode('utf-8')
                return response.startswith("OK:"), response
            finally:
                sock.close()
                
        except Exception as e:
            return False, f"Socket error: {e}"
    
    def pause(self):
        """
        Pause the playback using daemon socket command.
        
        Returns:
            bool: True if pause command was successful, False otherwise.
        """
        success, response = self._send_socket_command("pause")
        if success:
            self.pause_start = time.time()
            print(f"Pause command response: {response}")
        else:
            print(f"Error pausing: {response}")
        return success
    
    def resume(self):
        """
        Resume the playback using daemon socket command.
        
        Returns:
            bool: True if resume command was successful, False otherwise.
        """
        success, response = self._send_socket_command("resume")
        if success:
            if self.pause_start:
                # Add the paused duration to our total paused time
                self.paused_duration += time.time() - self.pause_start
                self.pause_start = None
            print(f"Resume command response: {response}")
        else:
            print(f"Error resuming: {response}")
        return success
    
    def stop(self):
        """Stop the playback using daemon socket command."""
        # Set should_stop immediately to break the position update loop
        self.should_stop = True
        
        # Stop the event listener thread
        self.stop_event_listener = True
        
        if self.process and self.process.poll() is None:
            # Try to stop via socket first
            success, response = self._send_socket_command("stop")
            if success:
                print(f"Stop command response: {response}")
            else:
                print(f"Error stopping via socket: {response}")
            
            # Wait a moment for graceful shutdown
            try:
                self.process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                # Fallback to process termination if socket stop didn't work
                try:
                    self.process.terminate()
                    self.process.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    self.process.kill()
        
        # Give the run loop a moment to notice should_stop and exit
        time.sleep(0.05)
                    
    def _send_socket_command(self, command):
        """Send a command to the player daemon via socket.
        
        Args:
            command (str): Command to send to the daemon
            
        Returns:
            tuple: (success: bool, response: str)
        """
        if not (self.process and self.process.poll() is None):
            return False, "No active player process"
            
        try:
            import socket
            import tempfile
            import os
            
            # Find the socket file for this daemon
            temp_dir = tempfile.gettempdir()
            socket_files = []
            
            for filename in os.listdir(temp_dir):
                if filename.startswith("walrio_player_") and filename.endswith(".sock"):
                    socket_path = os.path.join(temp_dir, filename)
                    if os.path.exists(socket_path):
                        socket_files.append((socket_path, os.path.getmtime(socket_path)))
            
            if not socket_files:
                return False, "No socket file found"
                
            # Use the most recent socket file
            socket_path = max(socket_files, key=lambda x: x[1])[0]
            
            # Connect to socket and send command
            sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            try:
                sock.connect(socket_path)
                sock.send(command.encode('utf-8'))
                response = sock.recv(1024).decode('utf-8')
                return response.startswith("OK:"), response
            finally:
                sock.close()
                
        except Exception as e:
            return False, f"Socket error: {e}"
    
    def seek(self, position):
        """
        Seek to a specific position using daemon socket command.
        
        Args:
            position (float): Position in seconds to seek to
            
        Returns:
            bool: True if seek command was successful, False otherwise.
        """
        command = f"seek {position:.2f}"
        success, response = self._send_socket_command(command)
        
        if success:
            print(f"Seek command response: {response}")
            # If seek was successful, update our timing
            current_time = time.time()
            self.start_time = current_time - position
            self.paused_duration = 0
            self.pause_start = None
            self.last_known_position = position
        else:
            print(f"Error seeking: {response}")
            
        return success
    
    def set_volume(self, volume):
        """
        Set the playback volume using daemon socket command.
        
        Args:
            volume (float): Volume level between 0.0 and 1.0
            
        Returns:
            bool: True if volume command was successful, False otherwise.
        """
        command = f"volume {volume:.2f}"
        success, response = self._send_socket_command(command)
        
        if success:
            print(f"Volume command response: {response}")
        else:
            print(f"Error setting volume: {response}")
            
        return success
    
    def get_position(self):
        """
        Get the current playback position from the daemon.
        
        Returns:
            float: Current position in seconds, or 0 if query fails
        """
        success, response = self._send_socket_command("position")
        if success and response.startswith("OK:"):
            try:
                return float(response.split(":")[1].strip())
            except (ValueError, IndexError):
                pass
        return 0.0
    
    def send_command(self, command):
        """
        Send a command to the daemon.
        
        Args:
            command (str): Command to send to the daemon
            
        Returns:
            bool: True if command was sent successfully, False otherwise
        """
        success, response = self._send_socket_command(command)
        return success
    
    def _connect_to_daemon_events_with_retry(self):
        """Connect to daemon events with retry logic for timing issues."""
        import time
        max_retries = 10
        for attempt in range(max_retries):
            if self._connect_to_daemon_events():
                return
            if attempt < max_retries - 1:
                print(f"PlayerWorker: Daemon socket not ready, retrying in 0.2s (attempt {attempt + 1})")
                time.sleep(0.2)
        print("PlayerWorker: Failed to connect to daemon events after all retries")

    def _connect_to_daemon_events(self):
        """
        Connect to the daemon for event notifications.
        
        Returns:
            bool: True if connection successful, False otherwise.
        """
        try:
            import tempfile
            import socket
            import os
            
            # Find the daemon socket
            temp_dir = tempfile.gettempdir()
            socket_files = []
            
            for filename in os.listdir(temp_dir):
                if filename.startswith("walrio_player_") and filename.endswith(".sock"):
                    socket_path = os.path.join(temp_dir, filename)
                    if os.path.exists(socket_path):
                        # Test if socket is alive by trying to connect
                        try:
                            test_socket = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
                            test_socket.settimeout(0.1)
                            test_socket.connect(socket_path)
                            test_socket.close()
                            # Socket is alive, add it to the list
                            socket_files.append((socket_path, os.path.getmtime(socket_path)))
                        except:
                            # Socket is dead, clean it up
                            print(f"PlayerWorker: Removing stale socket file: {socket_path}")
                            try:
                                os.unlink(socket_path)
                            except:
                                pass
            
            if socket_files:
                # Use the most recent live socket
                socket_path = max(socket_files, key=lambda x: x[1])[0]
                print(f"PlayerWorker: Connecting to daemon socket: {socket_path}")
                
                # Create event socket
                self.event_socket = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
                self.event_socket.connect(socket_path)
                self.event_socket.settimeout(1.0)  # Short timeout just for initial connection
                
                # Subscribe to events
                self.event_socket.send(b"subscribe")
                response = self.event_socket.recv(1024).decode('utf-8')
                if "OK: Subscribed" in response:
                    print("PlayerWorker: Successfully subscribed to daemon events")
                    # Set socket for non-blocking reads so position updates aren't blocked
                    self.event_socket.settimeout(1.0)  # 1 second timeout to catch events reliably while staying responsive
                    return True
                else:
                    print(f"PlayerWorker: Event subscription failed: {response}")
                    self.event_socket = None
                    return False
            else:
                return False  # No live socket found, will retry
                    
        except Exception as e:
            print(f"PlayerWorker: Failed to connect to daemon events: {e}")
            self.event_socket = None
            return False
    
    def _check_daemon_events(self):
        """Check for events from the daemon."""
        if not self.event_socket:
            return
        
        try:
            data = self.event_socket.recv(1024).decode('utf-8')
            if data:
                print(f"PlayerWorker: Received daemon data: {repr(data)}")
                for line in data.strip().split('\n'):
                    if line.strip():
                        self._process_daemon_event(line.strip())
        except Exception as e:
            # Handle different types of exceptions
            error_str = str(e).lower()
            if "timeout" in error_str or "would block" in error_str:
                # Normal timeout - no events available right now, this is expected with short timeout
                pass  # Continue checking events
            elif "connection" in error_str or "broken pipe" in error_str:
                # Connection lost
                print(f"PlayerWorker: Lost connection to daemon: {e}")
                self.event_socket = None
            else:
                # Log unexpected errors
                print(f"PlayerWorker: Unexpected error checking daemon events: {e}")
                self.event_socket = None
    
    def _process_daemon_event(self, event_data):
        """
        Process a daemon event.
        
        Args:
            event_data (str): JSON string containing event data from the daemon.
        """
        try:
            import json
            event = json.loads(event_data)
            
            if event.get("type") == "event":
                event_name = event.get("event")
                data = event.get("data", {})
                
                print(f"PlayerWorker: Received event {event_name}: {data}")
                
                if event_name == "song_finished":
                    print("PlayerWorker: Song finished event - stopping position updates and emitting playback_finished")
                    print(f"PlayerWorker: Emitting playback_finished signal now...")
                    # Stop position updates to prevent repeating final position
                    self.should_stop = True
                    self.playback_finished.emit()
                    print(f"PlayerWorker: playback_finished signal emitted successfully")
                elif event_name == "song_starting":
                    print(f"PlayerWorker: Song starting event - resuming position updates - {data.get('file')}")
                    # Resume position updates for new song
                    self.should_stop = False
                    self.song_starting.emit(data)
                elif event_name == "playback_complete":
                    print("PlayerWorker: Playback complete event - ignoring (already handled by song_finished)")
                    # Don't emit playback_finished again - song_finished already did it
                    
        except Exception as e:
            print(f"PlayerWorker: Error processing daemon event: {e}")
    
    def _cleanup_event_socket(self):
        """Clean up the event socket connection."""
        if self.event_socket:
            try:
                self.event_socket.close()
            except:
                pass
            self.event_socket = None

    def _start_event_listener_thread(self):
        """Start a dedicated thread for listening to daemon events."""
        import threading
        self.event_thread = threading.Thread(target=self._event_listener_loop, daemon=True)
        self.event_thread.start()
    
    def _event_listener_loop(self):
        """Dedicated event listener loop running in separate thread."""
        while not getattr(self, 'stop_event_listener', False):
            try:
                # Connect to daemon if not connected
                if not self.event_socket:
                    self._connect_to_daemon_events_with_retry()
                    if not self.event_socket:
                        # Connection failed, wait before retrying
                        import time
                        time.sleep(1.0)
                        continue
                
                # Check for events (this blocks for up to 1 second)
                self._check_daemon_events()
                
            except Exception as e:
                print(f"EventListener: Error in event loop: {e}")
                self.event_socket = None
                import time
                time.sleep(0.5)  # Brief pause before retry
    
    def play_new_song(self, filepath, duration=0):
        """
        Switch to a new song using the persistent daemon.
        
        Args:
            filepath (str): Path to the new audio file
            duration (float): Duration of the new file in seconds
        """
        # Update file info
        self.filepath = filepath
        self.duration = duration
        
        # Reset timing state
        self.should_stop = False  # Allow position updates for new song
        self.start_time = None
        self.paused_duration = 0
        self.pause_start = None
        self.last_known_position = 0
        print(f"PlayerWorker: Reset should_stop=False for new song")
        
        # Debug: Print the filepath being used
        print(f"PlayerWorker play_new_song called with: {repr(filepath)}")
        
        # If we have a running process, use load command to switch songs
        if self.process and self.process.poll() is None:
            # Use daemon's load command to switch to new file
            print(f"PlayerWorker: Sending load command: load {filepath}")
            success, response = self._send_socket_command(f"load {filepath}")
            if success and "OK:" in response:
                print(f"PlayerWorker: Loaded new song: {filepath}")
                # Start playback of the loaded song
                play_success, play_response = self._send_socket_command("play")
                print(f"PlayerWorker: Play command result: {play_response}")
                # Record the start time for this new song
                self.start_time = time.time()
            else:
                print(f"PlayerWorker: Failed to load new song: {response}")
                # Don't restart daemon - just report failure and keep using current daemon
                # TODO: Consider implementing daemon restart strategy
        else:
            # Start new daemon if no process is running
            if not self.isRunning():
                self.start()
            else:
                self._start_audio_process()
    
    def _start_audio_process(self):
        """Start the persistent daemon process."""
        try:
            # Change to modules directory for walrio.py execution
            modules_dir = Path(__file__).parent.parent / "modules"
            
            # Build command - start daemon without specific file (persistent mode)
            cmd = ["python", "walrio.py", "player", "--daemon"]
            # Don't append self.filepath - we'll load files via commands
            
            # Run walrio player in daemon mode for external control
            # Don't capture stdout/stderr so we can see debug output
            self.process = subprocess.Popen(
                cmd,
                cwd=str(modules_dir),
                text=True
            )
            
            # Allow a brief moment for the daemon to initialize
            time.sleep(0.2)
            
            # If we have a file to play, load it now
            if hasattr(self, 'filepath') and self.filepath:
                success, response = self._send_socket_command(f"load {self.filepath}")
                if success and "OK:" in response:
                    print(f"PlayerWorker: Loaded initial song: {self.filepath}")
                    # Start playback of the loaded song
                    play_success, play_response = self._send_socket_command("play")
                    print(f"PlayerWorker: Play command result: {play_response}")
                    # Record the start time
                    self.start_time = time.time()
                else:
                    print(f"PlayerWorker: Failed to load initial song: {response}")
            
        except Exception as e:
            print(f"Error starting audio process: {e}")


class WalrioMusicPlayer(QMainWindow):
    """Walrio music player with full playback controls."""
    
    def __init__(self):
        """
        Initialize the WalrioMusicPlayer main window.
        
        Sets up the UI, initializes state variables, and configures timers.
        """
        super().__init__()
        self.current_file = None
        self.is_playing = False
        self.player_worker = None
        self.position = 0
        self.duration = 0
        self.is_seeking = False
        self.loop_mode = "off"  # Can be "off" or "track"
        self.queue_manager = None  # Queue manager for loop handling
        self.pending_position = 0  # Position to apply when user stops seeking
        self.queue_songs = []  # List of songs in the queue
        self.current_queue_index = 0  # Current song index in queue
        self.loaded_playlists = {}  # Dictionary to store loaded playlists {name: [songs]}
        self.selected_playlist_name = None  # Currently selected playlist name
        self.selected_playlist_songs = []  # Currently selected playlist songs
        
        self.setup_ui()
        self.setup_timer()
    
    def _update_queue_manager(self):
        """
        Create or update the queue manager with current queue state.
        Creates QueueManager only once, then updates it.
        """
        current_songs = self.queue_songs if self.queue_songs else []
        
        # If no queue songs, create single-song queue for current file
        if not current_songs and self.current_file:
            current_songs = [{
                'url': self.current_file,
                'title': Path(self.current_file).stem,
                'artist': 'Unknown Artist',
                'album': 'Unknown Album'
            }]
        
        # Create QueueManager only if it doesn't exist
        if not self.queue_manager:
            print(f"Creating initial QueueManager with {len(current_songs)} songs")
            self.queue_manager = QueueManager(current_songs)
            self.queue_manager.set_current_index(self.current_queue_index)
        else:
            # Update the current index
            self.queue_manager.set_current_index(self.current_queue_index)
    
    def setup_playlist_sidebar(self, splitter):
        """Setup the playlist sidebar on the left side of the UI.
        
        Args:
            splitter: QSplitter widget to add the playlist sidebar to
        """
        # Create playlist sidebar widget
        playlist_widget = QWidget()
        playlist_layout = QVBoxLayout(playlist_widget)
        playlist_layout.setContentsMargins(5, 5, 5, 5)
        
        # Playlist header
        playlist_header = QLabel("Playlists")
        playlist_header.setAlignment(Qt.AlignCenter)
        header_font = QFont()
        header_font.setPointSize(12)
        header_font.setBold(True)
        playlist_header.setFont(header_font)
        playlist_layout.addWidget(playlist_header)
        
        # Playlist list widget
        self.playlist_list = QListWidget()
        self.playlist_list.setMaximumWidth(250)
        self.playlist_list.setMinimumWidth(200)
        
        # Enable context menu for playlist operations
        self.playlist_list.setContextMenuPolicy(Qt.CustomContextMenu)
        self.playlist_list.customContextMenuRequested.connect(self.show_playlist_context_menu)
        
        # Connect click events
        self.playlist_list.itemClicked.connect(self.on_playlist_clicked)
        self.playlist_list.itemSelectionChanged.connect(self.on_playlist_selection_changed)
        
        playlist_layout.addWidget(self.playlist_list)
        
        # Playlist management buttons
        playlist_buttons_layout = QVBoxLayout()
        
        self.btn_load_playlist = QPushButton("Load Playlist")
        self.btn_delete_playlist = QPushButton("Delete Selected")
        self.btn_refresh_playlists = QPushButton("Refresh")
        
        self.btn_load_playlist.clicked.connect(self.load_playlist_file)
        self.btn_delete_playlist.clicked.connect(self.delete_selected_playlist)
        self.btn_refresh_playlists.clicked.connect(self.refresh_playlist_display)
        
        # Initially disable delete button until a playlist is selected
        self.btn_delete_playlist.setEnabled(False)
        
        playlist_buttons_layout.addWidget(self.btn_load_playlist)
        playlist_buttons_layout.addWidget(self.btn_delete_playlist)
        playlist_buttons_layout.addWidget(self.btn_refresh_playlists)
        
        playlist_layout.addLayout(playlist_buttons_layout)
        
        # Add to splitter
        splitter.addWidget(playlist_widget)
    
    def setup_ui(self):
        """Setup the user interface."""
        self.setWindowTitle("Walrio")
        self.setGeometry(300, 300, 1200, 600)  # Made wider and taller for sidebar + tabs
        
        # Central widget with horizontal splitter
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QHBoxLayout(central_widget)
        main_layout.setContentsMargins(5, 5, 5, 5)
        
        # Create splitter to separate playlist sidebar from main content
        splitter = QSplitter(Qt.Horizontal)
        main_layout.addWidget(splitter)
        
        # Left side - Playlist sidebar
        self.setup_playlist_sidebar(splitter)
        
        # Right side - Tabbed content area
        tabs_widget = QWidget()
        tabs_layout = QVBoxLayout(tabs_widget)
        tabs_layout.setContentsMargins(0, 0, 0, 0)
        
        # Create tab widget for main content
        self.tab_widget = QTabWidget()
        tabs_layout.addWidget(self.tab_widget)
        
        # Setup tabs
        self.setup_queue_tab()
        self.setup_playlist_content_tab()
        
        # Add shared controls at the bottom of the tabbed area
        self.setup_shared_controls(tabs_layout)
        
        splitter.addWidget(tabs_widget)
        
        # Set splitter proportions (playlist sidebar takes 1/4, main content takes 3/4)
        splitter.setSizes([300, 900])
    
    def setup_queue_tab(self):
        """Setup the Queue tab with queue management components."""
        queue_widget = QWidget()
        layout = QVBoxLayout(queue_widget)
        
        # Create table widget for queue display with metadata columns
        self.queue_table = QTableWidget()
        self.queue_table.setAlternatingRowColors(True)
        
        # Set up columns: Title, Album, Album Artist, Artist, Year
        self.queue_table.setColumnCount(5)
        self.queue_table.setHorizontalHeaderLabels(['Title', 'Album', 'Album Artist', 'Artist', 'Year'])
        
        # Enable resizable columns (optimized for better performance)
        header = self.queue_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.Stretch)  # Title column stretches
        header.setSectionResizeMode(1, QHeaderView.Interactive)  # Album - manual resize
        header.setSectionResizeMode(2, QHeaderView.Interactive)  # Album Artist - manual resize
        header.setSectionResizeMode(3, QHeaderView.Interactive)  # Artist - manual resize
        header.setSectionResizeMode(4, QHeaderView.Fixed)  # Year - fixed width
        
        # Enable right-click context menu on header for column visibility
        header.setContextMenuPolicy(Qt.CustomContextMenu)
        header.customContextMenuRequested.connect(self.show_column_context_menu)
        
        # Set reasonable default column widths
        self.queue_table.setColumnWidth(1, 120)  # Album
        self.queue_table.setColumnWidth(2, 120)  # Album Artist  
        self.queue_table.setColumnWidth(3, 100)  # Artist
        self.queue_table.setColumnWidth(4, 50)   # Year
        
        # Allow manual column resizing
        header.setSectionsMovable(False)  # Don't allow column reordering
        header.setStretchLastSection(False)
        
        # Enable drag and drop for reordering rows (manual control for better sync)
        self.queue_table.setDragDropMode(QTableWidget.InternalMove)
        self.queue_table.setDefaultDropAction(Qt.MoveAction)
        self.queue_table.setDragDropOverwriteMode(False)  # Prevent automatic overwrites
        self.queue_table.setSelectionBehavior(QTableWidget.SelectRows)
        
        # Optimize drag-drop performance (Strawberry-style)
        self.queue_table.setAutoScroll(True)  # Allow scrolling but don't force it
        self.queue_table.setVerticalScrollMode(QTableWidget.ScrollPerPixel)  # Smoother scrolling
        
        # Additional performance optimizations
        self.queue_table.setAlternatingRowColors(True)  # Better visual feedback
        self.queue_table.setShowGrid(False)  # Reduce visual clutter and improve performance
        self.queue_table.setWordWrap(False)  # Prevent text wrapping delays
        self.queue_table.viewport().setAcceptDrops(True)  # Ensure proper drag-drop handling
        
        # Connect events
        self.queue_table.itemClicked.connect(self.on_queue_item_clicked)
        self.queue_table.itemDoubleClicked.connect(self.on_queue_item_double_clicked)
        
        # Connect drag-drop event to update queue order (with debouncing for performance)
        self.queue_table.model().rowsMoved.connect(self.on_queue_reordered)
        
        # Additional performance: reduce update frequency during drag operations
        self.queue_table.setDragEnabled(True)
        self.queue_table.setDropIndicatorShown(True)
        layout.addWidget(self.queue_table)
        
        # Add/Remove queue buttons
        queue_buttons_layout = QHBoxLayout()
        self.btn_add_files = QPushButton("Add Files to Queue")
        self.btn_clear_queue = QPushButton("Clear Queue")
        self.btn_remove_selected = QPushButton("Remove Selected")
        
        self.btn_add_files.clicked.connect(self.add_files_to_queue)
        self.btn_clear_queue.clicked.connect(self.clear_queue)
        self.btn_remove_selected.clicked.connect(self.remove_selected_from_queue)
        
        queue_buttons_layout.addWidget(self.btn_add_files)
        queue_buttons_layout.addWidget(self.btn_remove_selected)
        queue_buttons_layout.addWidget(self.btn_clear_queue)
        layout.addLayout(queue_buttons_layout)
        
        # Add to tab widget
        self.tab_widget.addTab(queue_widget, "Queue")
    
    def setup_playlist_content_tab(self):
        """Setup the Playlist content tab for viewing selected playlist contents."""
        playlist_content_widget = QWidget()
        layout = QVBoxLayout(playlist_content_widget)
        
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
        
        self.btn_add_to_queue = QPushButton("Add to Queue")
        self.btn_replace_queue = QPushButton("Replace Queue")
        
        self.btn_add_to_queue.clicked.connect(self.add_selected_playlist_to_queue)
        self.btn_replace_queue.clicked.connect(self.replace_queue_with_selected_playlist)
        
        # Initially disable these buttons until a playlist is selected
        self.btn_add_to_queue.setEnabled(False)
        self.btn_replace_queue.setEnabled(False)
        
        playlist_to_queue_layout.addWidget(self.btn_add_to_queue)
        playlist_to_queue_layout.addWidget(self.btn_replace_queue)
        
        layout.addLayout(playlist_to_queue_layout)
        
        # Add to tab widget
        self.tab_widget.addTab(playlist_content_widget, "Playlist")
    
    def setup_shared_controls(self, main_layout):
        """Setup shared controls that appear below the tabs.
        
        Args:
            main_layout (QVBoxLayout): The main layout to add controls to
        """
        # Track info
        self.track_label = QLabel("No file selected")
        self.track_label.setAlignment(Qt.AlignCenter)
        font = QFont()
        font.setPointSize(12)
        font.setBold(True)
        self.track_label.setFont(font)
        main_layout.addWidget(self.track_label)
        
        # Time and progress
        time_layout = QHBoxLayout()
        self.time_current = QLabel("00:00")
        self.progress_slider = QSlider(Qt.Horizontal)
        self.progress_slider.setMinimum(0)
        self.progress_slider.setMaximum(100)
        self.progress_slider.setValue(0)
        
        # Enable click-to-position behavior
        self.progress_slider.mousePressEvent = self.slider_mouse_press_event
        
        self.progress_slider.sliderPressed.connect(self.on_seek_start)
        self.progress_slider.sliderReleased.connect(self.on_seek_end)
        self.progress_slider.valueChanged.connect(self.on_slider_value_changed)
        self.time_total = QLabel("00:00")
        
        time_layout.addWidget(self.time_current)
        time_layout.addWidget(self.progress_slider)
        time_layout.addWidget(self.time_total)
        main_layout.addLayout(time_layout)
        
        # Control buttons
        controls_layout = QHBoxLayout()
        
        self.btn_previous = QPushButton("⏮ Previous")
        self.btn_play_pause = QPushButton("▶ Play")
        self.btn_stop = QPushButton("⏹ Stop")
        self.btn_next = QPushButton("⏭ Next")
        self.btn_loop = QPushButton("🔁 Repeat: Off")
        
        # Style buttons (smaller for better layout with volume slider)
        button_style = """
            QPushButton {
                font-size: 12px;
                padding: 6px 8px;
                min-width: 70px;
            }
        """
        self.btn_previous.setStyleSheet(button_style)
        self.btn_play_pause.setStyleSheet(button_style)
        self.btn_stop.setStyleSheet(button_style)
        self.btn_next.setStyleSheet(button_style)
        self.btn_loop.setStyleSheet(button_style)
        
        # Connect buttons
        self.btn_previous.clicked.connect(self.previous_track)
        self.btn_play_pause.clicked.connect(self.toggle_play_pause)
        self.btn_stop.clicked.connect(self.stop_playback)
        self.btn_next.clicked.connect(self.next_track)
        self.btn_loop.clicked.connect(self.toggle_loop)
        
        # Volume control (add to controls layout)
        self.volume_slider = QSlider(Qt.Horizontal)
        self.volume_slider.setMinimum(0)
        self.volume_slider.setMaximum(100)
        self.volume_slider.setValue(70)
        self.volume_slider.setMinimumWidth(200)  # Make it bigger for easier dragging
        self.volume_slider.setMaximumWidth(300)
        self.volume_slider.valueChanged.connect(self.on_volume_change)
        self.volume_label = QLabel("70%")
        self.volume_label.setMinimumWidth(40)

        controls_layout.addStretch()
        controls_layout.addWidget(QLabel("Volume:"))
        controls_layout.addWidget(self.volume_slider)
        controls_layout.addWidget(self.volume_label)
        controls_layout.addSpacing(15)  # Add some spacing between volume and previous button
        controls_layout.addWidget(self.btn_previous)
        controls_layout.addWidget(self.btn_play_pause)
        controls_layout.addWidget(self.btn_stop)
        controls_layout.addWidget(self.btn_next)
        controls_layout.addWidget(self.btn_loop)
        controls_layout.addStretch()
        main_layout.addLayout(controls_layout)
        
        # Initially disable play/stop buttons
        self.btn_play_pause.setEnabled(False)
        self.btn_stop.setEnabled(False)
        self.btn_previous.setEnabled(False)
        self.btn_next.setEnabled(False)
    
    def setup_timer(self):
        """Setup timer for updating UI (reduced frequency since position comes from worker)."""
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_ui)
        self.timer.start(100)  # Update UI every 100ms for smooth updates
    
    def load_playlist_file(self):
        """Load playlist file using file dialog."""
        playlist_path, _ = QFileDialog.getOpenFileName(
            self, "Load Playlist", "",
            "Playlist Files (*.m3u *.m3u8 *.pls *.xspf);;M3U Files (*.m3u *.m3u8);;All Files (*)"
        )
        
        if playlist_path:
            self.add_playlist_to_sidebar(playlist_path)
    
    def add_playlist_to_sidebar(self, playlist_path):
        """
        Add a playlist to the sidebar list.
        
        Args:
            playlist_path (str): Path to the M3U playlist file to add
        """
        playlist_path_obj = Path(playlist_path)
        playlist_name = playlist_path_obj.stem
        playlist_extension = playlist_path_obj.suffix.upper()  # Get extension in uppercase
        playlist_filename = playlist_path_obj.name  # Full filename with extension
        
        # Check if playlist already exists
        for i in range(self.playlist_list.count()):
            item = self.playlist_list.item(i)
            if item.data(Qt.UserRole) == playlist_path:
                QMessageBox.information(self, "Playlist Already Loaded", 
                                      f"Playlist '{playlist_filename}' is already in the list.")
                return
        
        # Load playlist using playlist module
        try:
            songs = playlist.load_m3u_playlist(playlist_path)
            if songs:
                # Store songs in loaded_playlists (use stem for internal reference)
                self.loaded_playlists[playlist_name] = songs
                
                # Add to playlist list widget with extension
                display_text = f"{playlist_name}{playlist_extension} ({len(songs)} tracks)"
                item = QListWidgetItem(display_text)
                item.setData(Qt.UserRole, playlist_path)
                item.setToolTip(f"Path: {playlist_path}\nType: {playlist_extension}\nTracks: {len(songs)}")
                self.playlist_list.addItem(item)
                
                print(f"Loaded playlist '{playlist_name}' with {len(songs)} tracks")
            else:
                QMessageBox.warning(self, "Load Error", 
                                  f"Could not load playlist from '{playlist_path}'.")
        except Exception as e:
            QMessageBox.critical(self, "Load Error", 
                               f"Error loading playlist: {str(e)}")
    
    def on_playlist_clicked(self, item):
        """
        Handle playlist item click - show playlist content in the Playlist tab.
        
        Args:
            item (QListWidgetItem): The clicked playlist item
        """
        playlist_path = item.data(Qt.UserRole)
        playlist_name = Path(playlist_path).stem
        
        if playlist_name in self.loaded_playlists:
            songs = self.loaded_playlists[playlist_name]
            
            # Update the selected playlist for queue operations
            self.selected_playlist_name = playlist_name
            self.selected_playlist_songs = songs
            
            # Update playlist content table
            self.update_playlist_content_display(playlist_name, songs)
            
            # Enable the playlist-to-queue buttons
            self.btn_add_to_queue.setEnabled(True)
            self.btn_replace_queue.setEnabled(True)
            
            # Switch to playlist tab to show content
            self.tab_widget.setCurrentIndex(1)  # Playlist tab is index 1
            
            print(f"Selected playlist '{playlist_name}' ({len(songs)} tracks)")
            
    def show_playlist_context_menu(self, position):
        """
        Show context menu for playlist operations.
        
        Args:
            position (QPoint): Position where the context menu was requested
        """
        item = self.playlist_list.itemAt(position)
        if not item:
            return
            
        menu = QMenu(self)
        
        # Load into queue action
        load_action = QAction("Load into Queue", self)
        load_action.triggered.connect(lambda: self.on_playlist_clicked(item))
        menu.addAction(load_action)
        
        menu.addSeparator()
        
        # Delete from list action
        delete_action = QAction("Delete from List", self)
        delete_action.triggered.connect(lambda: self.delete_playlist_by_item(item))
        menu.addAction(delete_action)
        
        # Show menu
        menu.exec(self.playlist_list.mapToGlobal(position))
    
    def remove_playlist_from_sidebar(self, item):
        """
        Remove playlist from sidebar list.
        
        Args:
            item (QListWidgetItem): The playlist item to remove
        """
        playlist_path = item.data(Qt.UserRole)
        playlist_name = Path(playlist_path).stem
        
        # Remove from loaded playlists
        if playlist_name in self.loaded_playlists:
            del self.loaded_playlists[playlist_name]
        
        # Remove from list widget
        row = self.playlist_list.row(item)
        self.playlist_list.takeItem(row)
        
        print(f"Removed playlist '{playlist_name}' from sidebar")
    
    def delete_playlist_by_item(self, item):
        """
        Delete playlist by item (used by context menu).
        
        Args:
            item (QListWidgetItem): The playlist item to delete
        """
        # Select the item first to match the button behavior
        self.playlist_list.setCurrentItem(item)
        # Then call the delete method
        self.delete_selected_playlist()
    
    def refresh_playlist_display(self):
        """Refresh the playlist display (placeholder for future functionality)."""
        # For now, this just clears and reloads if needed
        # Could be extended to scan a default playlists directory
        print("Playlist display refreshed")
    
    def on_playlist_selection_changed(self):
        """Handle playlist selection changes to enable/disable delete button."""
        selected_items = self.playlist_list.selectedItems()
        self.btn_delete_playlist.setEnabled(len(selected_items) > 0)
    
    def delete_selected_playlist(self):
        """Delete the selected playlist from the loaded list."""
        current_item = self.playlist_list.currentItem()
        if not current_item:
            QMessageBox.information(self, "No Selection", "Please select a playlist to delete.")
            return
        
        playlist_path = current_item.data(Qt.UserRole)
        playlist_path_obj = Path(playlist_path)
        playlist_name = playlist_path_obj.stem
        playlist_filename = playlist_path_obj.name  # Full filename with extension
        
        # Confirm deletion
        reply = QMessageBox.question(
            self, "Delete Playlist", 
            f"Are you sure you want to remove '{playlist_filename}' from the loaded playlists?\n\n"
            f"This will only remove it from the list, not delete the actual file.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            # Remove from loaded playlists dictionary
            if playlist_name in self.loaded_playlists:
                del self.loaded_playlists[playlist_name]
            
            # Remove from list widget
            row = self.playlist_list.row(current_item)
            self.playlist_list.takeItem(row)
            
            # Clear playlist content if this was the selected playlist
            if self.selected_playlist_name == playlist_name:
                self.selected_playlist_name = None
                self.selected_playlist_songs = []
                self.current_playlist_label.setText("No playlist selected")
                self.playlist_content_table.setRowCount(0)
                
                # Disable playlist-to-queue buttons
                self.btn_add_to_queue.setEnabled(False)
                self.btn_replace_queue.setEnabled(False)
            
            # Disable delete button if no playlists remain
            if self.playlist_list.count() == 0:
                self.btn_delete_playlist.setEnabled(False)
            
            print(f"Removed playlist '{playlist_filename}' from loaded list")
            QMessageBox.information(self, "Playlist Removed", 
                                  f"'{playlist_filename}' has been removed from the loaded playlists.")
    
    def update_playlist_content_display(self, playlist_name, songs):
        """
        Update the playlist content table with songs from the selected playlist.
        
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
    
    def add_selected_playlist_to_queue(self):
        """Add the selected playlist songs to the current queue."""
        if not self.selected_playlist_songs:
            QMessageBox.information(self, "No Playlist Selected", 
                                  "Please select a playlist first.")
            return
        
        # Add playlist songs to existing queue
        self.queue_songs.extend(self.selected_playlist_songs)
        
        # Update queue display
        self.update_queue_display()
        
        # Update queue manager
        self._update_queue_manager()
        
        # Enable navigation buttons
        if self.queue_songs:
            self.btn_previous.setEnabled(True)
            self.btn_next.setEnabled(True)
        
        # Switch to queue tab to show results
        self.tab_widget.setCurrentIndex(0)  # Queue tab is index 0
        
        print(f"Added {len(self.selected_playlist_songs)} tracks from '{self.selected_playlist_name}' to queue")
        QMessageBox.information(self, "Added to Queue", 
                              f"Added {len(self.selected_playlist_songs)} tracks to queue.")
    
    def replace_queue_with_selected_playlist(self):
        """Replace the current queue with the selected playlist songs."""
        if not self.selected_playlist_songs:
            QMessageBox.information(self, "No Playlist Selected", 
                                  "Please select a playlist first.")
            return
        
        # Clear current queue and replace with playlist
        self.clear_queue()
        self.queue_songs = self.selected_playlist_songs.copy()
        self.current_queue_index = 0
        
        # Update queue display
        self.update_queue_display()
        
        # Update queue manager
        self._update_queue_manager()
        
        # Enable navigation buttons
        if self.queue_songs:
            self.btn_previous.setEnabled(True)
            self.btn_next.setEnabled(True)
        
        # Switch to queue tab to show results
        self.tab_widget.setCurrentIndex(0)  # Queue tab is index 0
        
        print(f"Replaced queue with {len(self.selected_playlist_songs)} tracks from '{self.selected_playlist_name}'")
        QMessageBox.information(self, "Queue Replaced", 
                              f"Queue replaced with {len(self.selected_playlist_songs)} tracks from '{self.selected_playlist_name}'.")
    
    def add_files_to_queue(self):
        """Add files to the queue using background thread."""
        filepaths, _ = QFileDialog.getOpenFileNames(
            self, "Add Audio Files to Queue", "",
            "Audio Files (*.mp3 *.flac *.ogg *.wav *.m4a *.aac *.opus)"
        )
        
        if filepaths:
            # Disable the add button while processing
            self.btn_add_files.setEnabled(False)
            self.btn_add_files.setText(f"Processing {len(filepaths)} files...")
            
            # Create and start the queue worker
            self.queue_worker = QueueWorker(filepaths)
            self.queue_worker.file_processed.connect(self.on_file_processed)
            self.queue_worker.all_files_processed.connect(self.on_all_files_processed)
            self.queue_worker.error.connect(self.on_queue_error)
            self.queue_worker.start()
    
    def on_file_processed(self, song):
        """
        Handle when a file has been processed by the queue worker.
        
        Args:
            song (dict): Dictionary containing song metadata including title, artist, album, etc.
        """
        self.queue_songs.append(song)
        self.update_queue_display()
        
        # Add song to queue manager
        if not self.queue_manager:
            # Create QueueManager with empty list, then add this song
            self.queue_manager = QueueManager([])
            self.queue_manager.set_current_index(self.current_queue_index)
            
        # Always add the new song to the queue manager
        self.queue_manager.add_song(song)
        
        # Log song addition
        song_title = song.get('title', 'Unknown')
        print(f"Added to queue: {song_title} (Queue size: {len(self.queue_songs)})")
        
        # Enable navigation buttons if we have multiple songs
        if len(self.queue_songs) > 1:
            self.btn_previous.setEnabled(True)
            self.btn_next.setEnabled(True)
        
        # If no current file, load the first song from queue
        if not self.current_file and len(self.queue_songs) == 1:
            self.load_song_from_queue(0)
    
    def on_all_files_processed(self):
        """Handle when all files have been processed."""
        # Re-enable the add button
        self.btn_add_files.setEnabled(True)
        self.btn_add_files.setText("Add Files to Queue")
        
        # Clean up the worker
        if hasattr(self, 'queue_worker'):
            self.queue_worker.deleteLater()
            del self.queue_worker
    
    def on_queue_error(self, error_message):
        """
        Handle queue processing errors.
        
        Args:
            error_message (str): Error message describing what went wrong during queue processing.
        """
        QMessageBox.warning(self, "Queue Error", f"Error processing files: {error_message}")
        
        # Re-enable the add button
        self.btn_add_files.setEnabled(True)  
        self.btn_add_files.setText("Add Files to Queue")
        
        # Clean up the worker
        if hasattr(self, 'queue_worker'):
            self.queue_worker.deleteLater()
            del self.queue_worker
    
    def clear_queue(self):
        """Clear all songs from the queue."""
        self.queue_songs.clear()
        self.current_queue_index = 0
        self.update_queue_display()
        
        # Clear current file if it was from queue
        if self.current_file:
            self.current_file = None
            self.track_label.setText("No file selected")
            self.btn_play_pause.setEnabled(False)
            self.btn_stop.setEnabled(False)
            self.btn_previous.setEnabled(False)
            self.btn_next.setEnabled(False)
            self.stop_playback()
    
    def remove_selected_from_queue(self):
        """Remove selected song from the queue."""
        current_row = self.queue_table.currentRow()
        if current_row >= 0 and current_row < len(self.queue_songs):
            # Check if we're removing the currently playing song
            if current_row == self.current_queue_index and self.is_playing:
                self.stop_playback()
            
            # Remove the song
            self.queue_songs.pop(current_row)
            
            # Update current index if needed
            if current_row < self.current_queue_index:
                self.current_queue_index -= 1
            elif current_row == self.current_queue_index and current_row >= len(self.queue_songs):
                self.current_queue_index = 0
            
            self.update_queue_display()
            
            # If queue is empty, clear current file
            if not self.queue_songs:
                self.current_file = None
                self.track_label.setText("No file selected")
                self.btn_play_pause.setEnabled(False)
                self.btn_stop.setEnabled(False)
                self.btn_previous.setEnabled(False)
                self.btn_next.setEnabled(False)
            else:
                # Update navigation buttons
                self.btn_previous.setEnabled(len(self.queue_songs) > 1)
                self.btn_next.setEnabled(len(self.queue_songs) > 1)
    
    def on_queue_reordered(self, parent, start, end, destination, row):
        """
        Handle when queue items are reordered via drag and drop (sync fix for content).
        
        Args:
            parent: Parent model index (unused).
            start (int): Starting row index of moved items.
            end (int): Ending row index of moved items.
            destination: Destination parent model index (unused).
            row (int): Destination row index.
        """
        dest_row = int(row) 
        start_row = int(start)
        
        print(f"Drag-drop: Moving row {start_row} to {dest_row}")
        
        if start_row != dest_row and 0 <= start_row < len(self.queue_songs):
            # Emit layoutAboutToBeChanged for proper model-view updates (Strawberry pattern)
            self.queue_table.model().layoutAboutToBeChanged.emit()
            
            # Perform the move operation on our data
            moved_song = self.queue_songs.pop(start_row)
            insert_pos = dest_row if dest_row < start_row else dest_row - 1
            insert_pos = max(0, min(insert_pos, len(self.queue_songs)))
            self.queue_songs.insert(insert_pos, moved_song)
            
            print(f"Moved '{moved_song.get('title', 'Unknown')}' from {start_row} to {insert_pos}")
            
            # Update current queue index efficiently
            if self.current_file and self.is_playing:
                for i, song in enumerate(self.queue_songs):
                    if song['url'] == self.current_file:
                        self.current_queue_index = i
                        break
            
            # Update queue manager efficiently  
            if self.queue_manager:
                self.queue_manager.songs = self.queue_songs
                self.queue_manager.current_index = self.current_queue_index
            
            # Emit layoutChanged to notify views (Strawberry pattern)
            self.queue_table.model().layoutChanged.emit()
            
            # CRITICAL: Rebuild table content to sync with reordered queue_songs
            # The table widget moved rows visually but content is now out of sync
            print("Rebuilding table content after drag-drop...")
            self.update_queue_display()
    
    def on_queue_item_clicked(self, item):
        """Handle clicking on a queue item to select it (single-click only selects, does not play).
        
        Args:
            item: The QTableWidgetItem that was clicked.
        """
        row = item.row()
        if 0 <= row < len(self.queue_songs):
            # Single-click only selects the item for potential removal or other operations
            # To play a song, user must double-click
            print(f"Selected queue item #{row + 1}: {self.queue_songs[row]['title']}")
            # Update selection visual feedback is handled automatically by QTableWidget
    
    def on_queue_item_double_clicked(self, item):
        """Handle double-clicking on a queue item to immediately play it.
        
        Args:
            item: The QTableWidgetItem that was double-clicked.
        """
        row = item.row()
        if 0 <= row < len(self.queue_songs):
            was_playing = self.is_playing
            
            # If something is already playing, stop it first
            if was_playing and self.player_worker:
                # Stop the current player worker
                self.player_worker.stop()
                if not self.player_worker.wait(1000):  # Wait up to 1 second
                    self.player_worker.terminate()
                    self.player_worker.wait()
                self.player_worker = None
            
            # Load the selected song
            self.load_song_from_queue(row)
            
            # Start playing the new song
            self.start_playback()
    
    def load_song_from_queue(self, index):
        """Load a song from the queue by index.
        
        Args:
            index (int): The index of the song in the queue to load.
        """
        if 0 <= index < len(self.queue_songs):
            song = self.queue_songs[index]
            self.current_queue_index = index
            self.current_file = song['url']
            
            filename = Path(song['url']).name
            self.track_label.setText(f"{song['artist']} - {song['title']}")
            
            # Reset position
            self.position = 0
            self.progress_slider.setValue(0)
            self.time_current.setText("00:00")
            
            # Use cached duration or get it
            if song.get('duration', 0) > 0:
                self.duration = song['duration']
            else:
                # If no duration cached, get fresh metadata
                metadata = self.get_file_metadata(song['url'])
                self.duration = metadata['duration']
                # Update the song with fresh metadata
                song.update(metadata)
            
            if self.duration > 0:
                self.time_total.setText(self.format_time(self.duration))
                self.progress_slider.setMaximum(int(self.duration))
            else:
                self.time_total.setText("--:--")
                self.progress_slider.setMaximum(100)
            
            # Enable controls
            self.btn_play_pause.setEnabled(True)
            self.btn_stop.setEnabled(True)
            self.btn_previous.setEnabled(len(self.queue_songs) > 1)
            self.btn_next.setEnabled(len(self.queue_songs) > 1)
            
            # Update queue display to highlight current song
            self.update_queue_display()
    
    def get_file_duration(self, filepath):
        """Get the duration of an audio file.
        
        Args:
            filepath (str): Path to the audio file.
            
        Returns:
            float: Duration in seconds, or 0.0 if unable to determine.
        """
        try:
            modules_dir = Path(__file__).parent.parent / "modules"
            result = subprocess.run(
                ["python", "walrio.py", "metadata", "--duration", filepath],
                cwd=str(modules_dir),
                capture_output=True,
                text=True,
                timeout=10
            )
            if result.returncode == 0 and result.stdout.strip():
                return float(result.stdout.strip())
        except Exception as e:
            print(f"Error getting duration for {filepath}: {e}")
        return 0
    
    def get_file_metadata(self, filepath):
        """Get metadata for an audio file including artist, title, album, and duration.
        
        Args:
            filepath (str): Path to the audio file.
            
        Returns:
            dict: Dictionary containing file metadata with keys 'title', 'artist', 'album', 
                 'albumartist', 'year', 'url', and 'duration'.
        """
        try:
            modules_dir = Path(__file__).parent.parent / "modules"
            
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
                
                # Extract the information we need with proper fallbacks
                artist = metadata.get('artist') or metadata.get('album_artist') or 'Unknown Artist'
                title = metadata.get('title') or Path(filepath).stem
                album = metadata.get('album') or 'Unknown Album'
                
                # Get duration separately since --show might not include it
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
                    'artist': artist,
                    'title': title,
                    'album': album,
                    'duration': duration
                }
        except Exception as e:
            print(f"Error getting metadata for {filepath}: {e}")
        
        # Fallback to basic info
        return {
            'artist': 'Unknown Artist',
            'title': Path(filepath).stem,
            'album': 'Unknown Album',
            'duration': self.get_file_duration(filepath)
        }
    
    def update_queue_display(self):
        """Update the queue table widget display (Strawberry-style optimized)."""
        # Use blockSignals for better performance during bulk updates
        self.queue_table.blockSignals(True)
        self.queue_table.setUpdatesEnabled(False)
        
        try:
            # Only resize if the row count actually changed
            if self.queue_table.rowCount() != len(self.queue_songs):
                self.queue_table.setRowCount(len(self.queue_songs))
            
            # Batch update items to reduce redraws  
            for i, song in enumerate(self.queue_songs):
                texts = [
                    song.get('title', 'Unknown Title'),
                    song.get('album', 'Unknown Album'),
                    song.get('albumartist', song.get('artist', 'Unknown Artist')),
                    song.get('artist', 'Unknown Artist'), 
                    str(song.get('year', ''))
                ]
                
                # Update all columns for this row in one batch
                for col, text in enumerate(texts):
                    item = self.queue_table.item(i, col)
                    if item is None:
                        item = QTableWidgetItem(text)
                        # Set item properties once during creation
                        item.setFlags(item.flags() & ~Qt.ItemIsEditable)  # Make non-editable
                        self.queue_table.setItem(i, col, item)
                    elif item.text() != text:  # Only update if text actually changed
                        item.setText(text)
            
            # Update highlighting with a single call
            self.update_queue_highlighting()
            
        finally:
            # Re-enable signals and updates
            self.queue_table.setUpdatesEnabled(True) 
            self.queue_table.blockSignals(False)
            self.queue_table.setSortingEnabled(False)  # Keep sorting disabled for drag-drop
    
    def update_queue_highlighting(self):
        """Update only the highlighting of the currently playing song (lightweight update)."""
        for row in range(self.queue_table.rowCount()):
            is_current = (row == self.current_queue_index and self.current_file)
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
    
    def show_column_context_menu(self, position):
        """Show context menu for column visibility on header right-click.
        
        Args:
            position: The position where the context menu was requested.
        """
        header = self.queue_table.horizontalHeader()
        column_names = ["Title", "Album", "Album Artist", "Artist", "Year"]
        
        # Create the context menu
        menu = QMenu(self)
        
        # Add actions for each column
        for col, name in enumerate(column_names):
            action = menu.addAction(name)
            action.setCheckable(True)
            action.setChecked(not header.isSectionHidden(col))
            action.triggered.connect(lambda checked, column=col: self.toggle_column_visibility(column, checked))
        
        # Show the menu at the cursor position
        menu.exec_(header.mapToGlobal(position))
    
    def toggle_column_visibility(self, column, visible):
        """Toggle the visibility of a table column.
        
        Args:
            column (int): The column index to toggle.
            visible (bool): Whether to show (True) or hide (False) the column.
        """
        header = self.queue_table.horizontalHeader()
        if visible:
            header.showSection(column)
        else:
            header.hideSection(column)
    
    def toggle_play_pause(self):
        """Toggle between play, pause, and resume."""
        if not self.current_file:
            return
        
        if self.is_playing:
            self.pause_playback()
        else:
            # Check if we have a paused player worker to resume
            if self.player_worker and not self.is_playing:
                self.resume_playback()
            else:
                # Start fresh playback
                self.start_playback()
    
    def toggle_loop(self):
        """Toggle repeat mode between 'off' and 'track' (queue-based approach)."""
        if self.loop_mode == "off":
            self.loop_mode = "track"  # Use queue-based track repeat
            self.btn_loop.setText("🔁 Repeat: Track")
            self.btn_loop.setStyleSheet("""
                QPushButton {
                    font-size: 14px;
                    padding: 10px;
                    min-width: 100px;
                    background-color: #4CAF50;
                    color: white;
                }
            """)
        else:
            self.loop_mode = "off"
            self.btn_loop.setText("🔁 Repeat: Off")
            self.btn_loop.setStyleSheet("""
                QPushButton {
                    font-size: 14px;
                    padding: 10px;
                    min-width: 100px;
                }
            """)
        
        print(f"Repeat mode changed to: {self.loop_mode}")
        
        # Update queue manager if one exists
        if hasattr(self, 'queue_manager') and self.queue_manager:
            self.queue_manager.set_repeat_mode(self.loop_mode)
        
        # If currently playing, the loop mode will take effect on the next track end
        # No need to restart playback immediately
    
    def restart_with_loop(self, position):
        """
        Restart playback with current loop setting at specified position.
        
        Args:
            position (float): Position in seconds to resume from.
        """
        if self.current_file:
            self.start_playback()
    
    def start_playback(self):
        """Start audio playback with queue-based loop support."""
        if not self.current_file:
            return
        
        # Log song starting
        current_title = Path(self.current_file).stem if self.current_file else "Unknown"
        if self.queue_songs and hasattr(self, 'current_queue_index'):
            queue_position = f"#{self.current_queue_index + 1}/{len(self.queue_songs)}"
        else:
            queue_position = "Single song"
        print(f"Starting song: {current_title} ({queue_position})")
        
        # Create or update player worker
        if not self.player_worker:
            # Create new PlayerWorker only if it doesn't exist
            self.player_worker = PlayerWorker(self.current_file, self.duration)
            self.player_worker.playback_finished.connect(self.on_playback_finished)
            self.player_worker.error.connect(self.on_playback_error)
            self.player_worker.position_updated.connect(self.on_position_updated)
            self.player_worker.start()
        else:
            # Update existing PlayerWorker with new song
            self.player_worker.play_new_song(self.current_file, self.duration)
        
        # Update queue manager with current queue (create if needed)
        self._update_queue_manager()
        
        # Ensure queue manager has correct repeat mode
        if self.queue_manager:
            self.queue_manager.set_repeat_mode(self.loop_mode)
        
        # Ensure daemon loop mode is set to 'none' for queue-controlled progression
        if self.player_worker:
            # Give daemon a moment to initialize before sending command
            QTimer.singleShot(200, lambda: self.player_worker.send_command("loop none"))
        
        self.is_playing = True
        self.btn_play_pause.setText("⏸ Pause")
        self.btn_stop.setEnabled(True)
    
    def _set_daemon_loop_mode(self):
        """Set the daemon's loop mode to 'none' for queue-controlled progression."""
        if self.player_worker:
            success = self.player_worker.send_command("loop none")
            if success:
                print("Set daemon loop mode to 'none'")
            else:
                print("Failed to set daemon loop mode - daemon may not be ready yet")
    
    def pause_playback(self):
        """Pause audio playback using CLI command."""
        if not self.is_playing or not self.player_worker:
            return
            
        self.is_playing = False
        self.btn_play_pause.setText("▶ Resume")
        
        # Send pause command to the player
        if self.player_worker:
            self.player_worker.pause()
    
    def resume_playback(self):
        """Resume audio playback using CLI command."""
        if self.is_playing or not self.player_worker:
            return
        
        self.is_playing = True
        self.btn_play_pause.setText("⏸ Pause")
        
        # Send resume command to the player
        if self.player_worker:
            self.player_worker.resume()
    
    def stop_playback(self):
        """Stop audio playback."""
        # Set state first
        self.is_playing = False
        self.btn_play_pause.setText("▶ Play")
        
        # Immediately disable the stop button to prevent multiple clicks
        self.btn_stop.setEnabled(False)
        
        # Reset position and UI immediately to prevent further updates
        self.position = 0
        self.progress_slider.setValue(0)
        self.time_current.setText("00:00")
        
        # Force GUI to update immediately
        QApplication.processEvents()
        
        if self.player_worker:
            # Disconnect all signals first to prevent further updates
            try:
                self.player_worker.position_updated.disconnect()
                self.player_worker.playback_finished.disconnect()
                self.player_worker.error.disconnect()
            except:
                pass  # Signals might already be disconnected
            
            # Stop the worker thread
            self.player_worker.stop()
            
            # Wait for the thread to finish, but with a timeout
            if not self.player_worker.wait(3000):  # Wait up to 3 seconds
                # If thread doesn't finish, terminate it forcefully
                self.player_worker.terminate()
                self.player_worker.wait()
            
            self.player_worker = None
        
        # Re-enable play button (stop button already disabled above)
        self.btn_play_pause.setEnabled(True)
    
    def on_volume_change(self, value):
        """
        Handle volume slider changes.
        
        Args:
            value (int): The new volume slider value (0-100).
        """
        self.volume_label.setText(f"{value}%")
        
        # Convert slider value (0-100) to volume range (0.0-1.0)
        volume = value / 100.0
        
        # Set volume if player worker exists (playing or paused)
        if self.player_worker:
            self.player_worker.set_volume(volume)
    
    def slider_mouse_press_event(self, event):
        """
        Handle mouse press events on the slider to enable click-to-position.
        
        Args:
            event: The mouse press event from Qt containing position and button information.
        """
        if event.button() == Qt.LeftButton:
            # Calculate the position where the user clicked
            slider_min = self.progress_slider.minimum()
            slider_max = self.progress_slider.maximum()
            slider_range = slider_max - slider_min
            
            # Get the click position relative to the slider
            click_pos = event.position().x()
            slider_width = self.progress_slider.width()
            
            # Calculate the value based on click position
            if slider_width > 0:
                ratio = click_pos / slider_width
                new_value = slider_min + (ratio * slider_range)
                new_value = max(slider_min, min(slider_max, int(new_value)))
                
                # Set the slider to this position
                self.progress_slider.setValue(new_value)
        
        # Call the original mouse press event to maintain normal slider behavior
        QSlider.mousePressEvent(self.progress_slider, event)
    
    def on_slider_value_changed(self, value):
        """
        Debug method to track slider value changes.
        
        Args:
            value (int): The new slider value from the progress slider.
        """
        pass  # Remove debug output for production use
    
    def on_seek_start(self):
        """Handle when user starts seeking."""
        self.is_seeking = True
    
    def on_seek_end(self):
        """Handle when user finishes seeking."""
        self.is_seeking = False
        
        # Always use the slider position where user released it
        seek_position = self.progress_slider.value()
        self.position = seek_position
        self.time_current.setText(self.format_time(seek_position))
        
        # Try to seek the actual player to this position using socket
        if self.player_worker:
            success = self.player_worker.seek(seek_position)
            if not success:
                print(f"Seek to {seek_position}s failed")
        
        # Clear pending position
        self.pending_position = 0
    
    def on_position_updated(self, position):
        """
        Handle position updates from the player worker (ignore position while seeking).
        
        Args:
            position (float): Current playback position in seconds.
        """
        # Ignore position updates if we're not playing
        if not self.is_playing or not self.player_worker:
            return
            
        if self.progress_slider.isSliderDown():
            # Store the real position for reference but don't update UI
            self.pending_position = position
            return
            
        # Cap position at duration to prevent going beyond song length
        if self.duration > 0 and position >= self.duration:
            position = self.duration
            
        # Update position and UI (only when user is not interacting with slider)
        self.position = position
        self.progress_slider.setValue(int(position))
        self.time_current.setText(self.format_time(position))
    
    def update_ui(self):
        """Update UI elements (called by timer)."""
        # Most updates now come from position_updated signal
        # This is just for any additional UI updates needed
        pass
    
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
    
    def on_playback_finished(self):
        """Handle when playback finishes - use queue system for completion logic."""
        print("on_playback_finished called - song has ended")
        print(f"DEBUG: Queue manager exists: {self.queue_manager is not None}")
        print(f"DEBUG: Processing finish flag: {getattr(self, '_processing_finish', 'not set')}")
        
        # Prevent multiple calls for the same song completion
        if hasattr(self, '_processing_finish') and self._processing_finish:
            print("Already processing playback finish - ignoring duplicate event")
            return
        self._processing_finish = True
        
        if not self.queue_manager:
            print("No queue manager - stopping playback")
            self.stop_playback()
            self._processing_finish = False
            return
        
        # Use the new handle_song_finished method from QueueManager
        should_continue, next_song = self.queue_manager.handle_song_finished()
        
        if should_continue and next_song:
            # Update the current file reference - use 'url' key which contains the filepath
            self.current_file = next_song.get('url') or next_song.get('filepath')
            
            # Sync GUI current_queue_index with queue manager's current_index
            self.current_queue_index = self.queue_manager.current_index
            
            # Update the track label to show the new song
            self.track_label.setText(f"{next_song.get('artist', 'Unknown Artist')} - {next_song.get('title', 'Unknown Title')}")
            
            # Reset position display for new song
            self.position = 0
            self.progress_slider.setValue(0)
            self.time_current.setText("00:00")
            
            # Update the queue display to reflect current position
            self.update_queue_display()
            
            # Start playing the next/repeated song
            self.start_playback()
        else:
            # Queue is finished or no next song
            print("Playback completed - no more songs")
            self.stop_playback()
        
        # Reset the flag after processing
        self._processing_finish = False
    def next_track(self):
        """Skip to the next track in the queue."""
        if not self.queue_manager or not self.queue_manager.has_songs():
            return
        
        was_playing = self.is_playing
        
        # Stop current playback
        if self.is_playing:
            self.stop_playback()
        
        # Use queue manager to move to next track
        if self.queue_manager.next_track():
            next_song = self.queue_manager.current_song()
            if next_song:
                self.current_file = next_song['filepath']
                self.update_queue_display()
                
                # Resume playback if we were playing
                if was_playing:
                    self.start_playback()
    
    def previous_track(self):
        """Skip to the previous track in the queue."""
        if not self.queue_manager or not self.queue_manager.has_songs():
            return
        
        was_playing = self.is_playing
        
        # Stop current playback
        if self.is_playing:
            self.stop_playback()
        
        # Use queue manager to move to previous track
        if self.queue_manager.previous_track():
            prev_song = self.queue_manager.current_song()
            if prev_song:
                self.current_file = prev_song['filepath']
                self.update_queue_display()
                
                # Resume playback if we were playing
                if was_playing:
                    self.start_playback()
    
    def on_playback_error(self, error):
        """
        Handle playback errors.
        
        Args:
            error (str): Error message to display.
        """
        self.show_message("Playback Error", error)
        self.stop_playback()
    
    def show_message(self, title, message):
        """
        Show a message dialog.
        
        Args:
            title (str): Dialog window title.
            message (str): Message content to display.
        """
        QMessageBox.information(self, title, message)
    
    def closeEvent(self, event):
        """
        Handle application close.
        
        Args:
            event: The close event from Qt.
        """
        if self.player_worker:
            self.player_worker.stop()
            self.player_worker.wait()
        event.accept()


def main():
    """Main entry point for Walrio."""
    app = QApplication(sys.argv)
    app.setApplicationName("Walrio")
    
    player = WalrioMusicPlayer()
    player.show()
    
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
