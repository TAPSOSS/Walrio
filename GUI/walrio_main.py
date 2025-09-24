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
import sys
import os
import subprocess
import threading
import time
from pathlib import Path

# Add the parent directory to the Python path so we can import modules
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from modules.core.queue import QueueManager, RepeatMode  # Import queue system

try:
    from PySide6.QtWidgets import (
        QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
        QPushButton, QSlider, QLabel, QFileDialog, QMessageBox, QListWidget, QListWidgetItem
    )
    from PySide6.QtCore import QTimer, QThread, Signal, Qt
    from PySide6.QtGui import QFont, QColor
except ImportError:
    print("PySide6 not found. Installing...")
    subprocess.run([sys.executable, "-m", "pip", "install", "PySide6"])
    from PySide6.QtWidgets import (
        QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
        QPushButton, QSlider, QLabel, QFileDialog, QMessageBox, QListWidget, QListWidgetItem
    )
    from PySide6.QtCore import QTimer, QThread, Signal, Qt
    from PySide6.QtGui import QFont, QColor


class QueueWorker(QThread):
    """Worker thread for queue operations like metadata extraction."""
    
    # Signals
    file_processed = Signal(dict)  # Emitted when a file's metadata is extracted
    all_files_processed = Signal()  # Emitted when all files are done
    error = Signal(str)  # Emitted on error
    
    def __init__(self, filepaths):
        super().__init__()
        self.filepaths = filepaths
        self.should_stop = False
    
    def run(self):
        """Process files in background thread."""
        try:
            for filepath in self.filepaths:
                if self.should_stop:
                    break
                    
                # Get metadata for the file
                metadata = self._get_file_metadata(filepath)
                song = {
                    'url': filepath,
                    'title': metadata['title'],
                    'artist': metadata['artist'],
                    'album': metadata['album'],
                    'duration': metadata['duration']
                }
                
                # Emit the processed file
                self.file_processed.emit(song)
                
            # Signal that all files are processed
            if not self.should_stop:
                self.all_files_processed.emit()
                
        except Exception as e:
            self.error.emit(f"Error processing files: {str(e)}")
    
    def _get_file_metadata(self, filepath):
        """Get metadata for an audio file including artist, title, album, and duration."""
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
                        metadata[key] = value
                
                # Return structured metadata with fallbacks
                return {
                    'title': metadata.get('title', Path(filepath).stem),
                    'artist': metadata.get('artist', 'Unknown Artist'),
                    'album': metadata.get('album', 'Unknown Album'),
                    'duration': self._parse_duration(metadata.get('duration', '0:00'))
                }
            else:
                # Fallback if metadata extraction fails
                return {
                    'title': Path(filepath).stem,
                    'artist': 'Unknown Artist',
                    'album': 'Unknown Album',
                    'duration': 0
                }
                
        except Exception as e:
            print(f"Error getting metadata for {filepath}: {e}")
            return {
                'title': Path(filepath).stem,
                'artist': 'Unknown Artist', 
                'album': 'Unknown Album',
                'duration': 0
            }
    
    def _parse_duration(self, duration_str):
        """Parse duration string like '3:45 (225.6 seconds)' and return seconds."""
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
            
            # Connect to daemon for events (with retry for timing)
            self._connect_to_daemon_events_with_retry()
            
            # Main monitoring loop
            event_check_counter = 0
            while not self.should_stop and self.process.poll() is None:
                # Check for daemon events less frequently to avoid timeout errors
                event_check_counter += 1
                if event_check_counter % 5 == 0:  # Check every 5 iterations (0.5 seconds)
                    self._check_daemon_events()
                
                if not self.pause_start and not self.should_stop:
                    # Query actual position from the audio daemon
                    actual_position = self.get_position()
                    
                    if actual_position > 0:
                        # Use the actual audio position
                        self.last_known_position = actual_position
                        if not self.should_stop:
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
        """Connect to the daemon for event notifications."""
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
                self.event_socket.settimeout(1.0)  # Longer timeout for more reliable connection
                
                # Subscribe to events
                self.event_socket.send(b"subscribe")
                response = self.event_socket.recv(1024).decode('utf-8')
                if "OK: Subscribed" in response:
                    print("PlayerWorker: Successfully subscribed to daemon events")
                    # Set socket to non-blocking mode for event checking
                    self.event_socket.settimeout(0.1)
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
                # Normal timeout - no events available
                pass
            elif "connection" in error_str or "broken pipe" in error_str:
                # Connection lost
                print(f"PlayerWorker: Lost connection to daemon: {e}")
                self.event_socket = None
            else:
                print(f"PlayerWorker: Error checking daemon events: {e}")
                self.event_socket = None
    
    def _process_daemon_event(self, event_data):
        """Process a daemon event."""
        try:
            import json
            event = json.loads(event_data)
            
            if event.get("type") == "event":
                event_name = event.get("event")
                data = event.get("data", {})
                
                print(f"PlayerWorker: Received event {event_name}: {data}")
                
                if event_name == "song_finished":
                    print("PlayerWorker: Song finished event - emitting playback_finished")
                    self.playback_finished.emit()
                elif event_name == "song_starting":
                    print(f"PlayerWorker: Song starting event - {data.get('file')}")
                    self.song_starting.emit(data)
                elif event_name == "playback_complete":
                    print("PlayerWorker: Playback complete event - emitting playback_finished")
                    self.playback_finished.emit()
                    
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
    
    def play_new_song(self, filepath, duration=0):
        """
        Switch to a new song without recreating the PlayerWorker thread.
        
        Args:
            filepath (str): Path to the new audio file
            duration (float): Duration of the new file in seconds
        """
        # Stop current playback
        if self.process and self.process.poll() is None:
            self.stop()
            
        # Update file info
        self.filepath = filepath
        self.duration = duration
        
        # Reset timing state
        self.should_stop = False
        self.start_time = None
        self.paused_duration = 0
        self.pause_start = None
        self.last_known_position = 0
        
        # Start new playback
        if not self.isRunning():
            self.start()
        else:
            # If thread is running, restart the audio process
            self._start_audio_process()
    
    def _start_audio_process(self):
        """Start the audio process for the current file."""
        try:
            # Change to modules directory for walrio.py execution
            modules_dir = Path(__file__).parent.parent / "modules"
            
            # Build command - no loop option needed (handled by queue)
            cmd = ["python", "walrio.py", "player", "--daemon"]
            cmd.append(self.filepath)
            
            # Run walrio player in daemon mode for external control
            self.process = subprocess.Popen(
                cmd,
                cwd=str(modules_dir),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            
            # Allow a brief moment for the audio player to initialize
            time.sleep(0.1)
            
            # Record the actual start time after initialization
            self.start_time = time.time()
            
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
    
    def setup_ui(self):
        """Setup the user interface."""
        self.setWindowTitle("Walrio")
        self.setGeometry(300, 300, 800, 500)
        
        # Central widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)
        
        # Queue List Widget
        queue_label = QLabel("Queue")
        queue_label.setAlignment(Qt.AlignCenter)
        queue_font = QFont()
        queue_font.setPointSize(10)
        queue_font.setBold(True)
        queue_label.setFont(queue_font)
        layout.addWidget(queue_label)
        
        self.queue_list = QListWidget()
        self.queue_list.setMaximumHeight(150)
        self.queue_list.setAlternatingRowColors(True)
        self.queue_list.itemClicked.connect(self.on_queue_item_clicked)
        self.queue_list.itemDoubleClicked.connect(self.on_queue_item_double_clicked)
        layout.addWidget(self.queue_list)
        
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
        
        # Track info
        self.track_label = QLabel("No file selected")
        self.track_label.setAlignment(Qt.AlignCenter)
        font = QFont()
        font.setPointSize(12)
        font.setBold(True)
        self.track_label.setFont(font)
        layout.addWidget(self.track_label)
        
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
        layout.addLayout(time_layout)
        
        # Control buttons
        controls_layout = QHBoxLayout()
        
        self.btn_open = QPushButton("Open File")
        self.btn_previous = QPushButton("⏮ Previous")
        self.btn_play_pause = QPushButton("▶ Play")
        self.btn_stop = QPushButton("⏹ Stop")
        self.btn_next = QPushButton("⏭ Next")
        self.btn_loop = QPushButton("🔁 Repeat: Off")
        
        # Style buttons
        button_style = """
            QPushButton {
                font-size: 14px;
                padding: 10px;
                min-width: 100px;
            }
        """
        self.btn_open.setStyleSheet(button_style)
        self.btn_previous.setStyleSheet(button_style)
        self.btn_play_pause.setStyleSheet(button_style)
        self.btn_stop.setStyleSheet(button_style)
        self.btn_next.setStyleSheet(button_style)
        self.btn_loop.setStyleSheet(button_style)
        
        # Connect buttons
        self.btn_open.clicked.connect(self.open_file)
        self.btn_previous.clicked.connect(self.previous_track)
        self.btn_play_pause.clicked.connect(self.toggle_play_pause)
        self.btn_stop.clicked.connect(self.stop_playback)
        self.btn_next.clicked.connect(self.next_track)
        self.btn_loop.clicked.connect(self.toggle_loop)
        
        controls_layout.addStretch()
        controls_layout.addWidget(self.btn_open)
        controls_layout.addWidget(self.btn_previous)
        controls_layout.addWidget(self.btn_play_pause)
        controls_layout.addWidget(self.btn_stop)
        controls_layout.addWidget(self.btn_next)
        controls_layout.addWidget(self.btn_loop)
        controls_layout.addStretch()
        layout.addLayout(controls_layout)
        
        # Volume control
        volume_layout = QHBoxLayout()
        volume_layout.addWidget(QLabel("Volume:"))
        self.volume_slider = QSlider(Qt.Horizontal)
        self.volume_slider.setMinimum(0)
        self.volume_slider.setMaximum(100)
        self.volume_slider.setValue(70)
        self.volume_slider.setMaximumWidth(200)
        self.volume_slider.valueChanged.connect(self.on_volume_change)
        self.volume_label = QLabel("70%")
        self.volume_label.setMinimumWidth(40)
        
        volume_layout.addWidget(self.volume_slider)
        volume_layout.addWidget(self.volume_label)
        volume_layout.addStretch()
        layout.addLayout(volume_layout)
        
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
        """Handle when a file has been processed by the queue worker."""
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
        """Handle queue processing errors."""
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
        current_row = self.queue_list.currentRow()
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
    
    def on_queue_item_clicked(self, item):
        """Handle clicking on a queue item to select it."""
        row = self.queue_list.row(item)
        if 0 <= row < len(self.queue_songs):
            # Just select the item, don't automatically play
            # Playing is now handled by double-click
            pass
    
    def on_queue_item_double_clicked(self, item):
        """Handle double-clicking on a queue item to immediately play it."""
        row = self.queue_list.row(item)
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
        """Load a song from the queue by index."""
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
        """Get the duration of an audio file."""
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
        """Get metadata for an audio file including artist, title, album, and duration."""
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
        """Update the queue list widget display."""
        self.queue_list.clear()
        
        for i, song in enumerate(self.queue_songs):
            # Format display text
            duration_text = self.format_time(song['duration']) if song['duration'] > 0 else "--:--"
            display_text = f"{song['artist']} - {song['title']} [{duration_text}]"
            
            item = QListWidgetItem(display_text)
            
            # Highlight currently playing song
            if i == self.current_queue_index and self.current_file:
                item.setBackground(QColor(200, 255, 200))  # Light green background
                font = item.font()
                font.setBold(True)
                item.setFont(font)
            
            self.queue_list.addItem(item)
    
    def open_file(self):
        """Open an audio file (legacy single file method)."""
        filepath, _ = QFileDialog.getOpenFileName(
            self, "Open Audio File", "",
            "Audio Files (*.mp3 *.flac *.ogg *.wav *.m4a *.aac *.opus)"
        )
        
        if filepath:
            # Get metadata for the file
            metadata = self.get_file_metadata(filepath)
            song = {
                'url': filepath,
                'title': metadata['title'],
                'artist': metadata['artist'],
                'album': metadata['album'],
                'duration': metadata['duration']
            }
            
            # Add to beginning of queue
            self.queue_songs.insert(0, song)
            self.current_queue_index = 0
            self.load_song_from_queue(0)
    
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
        
        if not self.queue_manager:
            print("No queue manager - stopping playback")
            self.stop_playback()
            return
        
        # Use the new handle_song_finished method from QueueManager
        should_continue, next_song = self.queue_manager.handle_song_finished()
        
        if should_continue and next_song:
            # Update the current file reference - use 'url' key which contains the filepath
            self.current_file = next_song.get('url') or next_song.get('filepath')
            
            # Update the queue display to reflect current position
            self.update_queue_display()
            
            # Start playing the next/repeated song
            self.start_playback()
        else:
            # Queue is finished or no next song
            print("Playback completed - no more songs")
            self.stop_playback()
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
