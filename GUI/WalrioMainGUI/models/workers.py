#!/usr/bin/env python3
"""
Worker classes for background tasks in Walrio GUI
Copyright (c) 2025 TAPS OSS
Project: https://github.com/TAPSOSS/Walrio
Licensed under the BSD-3-Clause License (see LICENSE file for details)

Contains QueueWorker and Playe                song = {
                    'url': self.file_url,
                    'title': metadata['title'],
                    'artist': metadata['artist'],
                    'album': metadata['album'],
                    'albumartist': metadata['albumartist'],
                    'year': metadata['year'],
                    'length': metadata['length']
                }lasses for handling
audio metadata extraction and playback operations.
"""

import sys
import os
import subprocess
import threading
import time
import tempfile
import socket
import json
from pathlib import Path

# Add the parent directory to the Python path so we can import modules
sys.path.append(os.path.join(os.path.dirname(__file__), '../../..'))

from modules.core import metadata

try:
    from PySide6.QtCore import QThread, Signal, Qt
except ImportError:
    print("PySide6 not found. Installing...")
    subprocess.run([sys.executable, "-m", "pip", "install", "PySide6"])
    from PySide6.QtCore import QThread, Signal, Qt


class PlaylistWorker(QThread):
    """Worker thread for loading playlists without blocking the main thread."""
    
    # Signals
    progress_updated = Signal(int, int, str)  # current, total, current_file
    playlist_loaded = Signal(str, list, list)  # playlist_name, songs, missing_files
    error = Signal(str)
    
    def __init__(self, playlist_path, playlist_name):
        """
        Initialize the playlist worker.
        
        Args:
            playlist_path (str): Path to the playlist file
            playlist_name (str): Name for the playlist
        """
        super().__init__()
        self.playlist_path = playlist_path
        self.playlist_name = playlist_name
        self.should_stop = False
    
    def stop(self):
        """Stop the playlist loading process."""
        self.should_stop = True
    
    def run(self):
        """Load the playlist in the background."""
        try:
            # First, quickly parse the playlist file to get file paths
            file_paths = self._parse_playlist_structure()
            if not file_paths:
                self.error.emit(f"No valid files found in playlist: {self.playlist_path}")
                return
            
            total_files = len(file_paths)
            songs = []
            missing_files = []
            
            # Process files in batches with metadata extraction
            for i, (file_path, extinf_info) in enumerate(file_paths):
                if self.should_stop:
                    break
                
                # Emit progress
                self.progress_updated.emit(i + 1, total_files, Path(file_path).name)
                
                # Extract metadata for this file (handles missing files with placeholders)
                song_data = self._get_song_metadata(file_path, extinf_info)
                if song_data:
                    songs.append(song_data)
                    # Track missing files for error reporting
                    if song_data.get('file_missing', False):
                        missing_files.append(file_path)
                
                # Small delay to keep UI responsive
                self.msleep(1)  # 1ms delay between files
            
            if not self.should_stop:
                self.playlist_loaded.emit(self.playlist_name, songs, missing_files)
                
        except Exception as e:
            self.error.emit(f"Error loading playlist: {str(e)}")
    
    def _parse_playlist_structure(self):
        """
        Quickly parse playlist file to extract file paths without metadata.
        
        Returns:
            list: List of (file_path, extinf_info) tuples
        """
        file_paths = []
        
        try:
            with open(self.playlist_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()
            
            current_extinf = {}
            for line in lines:
                line = line.strip()
                
                # Skip empty lines and comments (except EXTINF)
                if not line or (line.startswith('#') and not line.startswith('#EXTINF')):
                    continue
                
                # Parse EXTINF line
                if line.startswith('#EXTINF:'):
                    try:
                        parts = line[8:].split(',', 1)  # Remove #EXTINF: and split on first comma
                        duration = int(parts[0]) if parts[0].isdigit() else 0
                        if len(parts) > 1 and ' - ' in parts[1]:
                            artist, title = parts[1].split(' - ', 1)
                            current_extinf = {
                                'artist': artist.strip(),
                                'title': title.strip(),
                                'duration': duration
                            }
                    except (ValueError, IndexError):
                        current_extinf = {}
                else:
                    # This should be a file path
                    file_path = line
                    
                    # Convert relative path to absolute if needed
                    if not os.path.isabs(file_path):
                        playlist_dir = Path(self.playlist_path).parent
                        file_path = os.path.abspath(os.path.join(playlist_dir, file_path))
                    
                    # Add to list with current EXTINF info
                    file_paths.append((file_path, current_extinf.copy()))
                    current_extinf = {}  # Reset for next file
                    
        except Exception as e:
            raise Exception(f"Failed to parse playlist structure: {str(e)}")
        
        return file_paths
    
    def _get_song_metadata(self, file_path, extinf_info):
        """
        Get metadata for a single song file.
        
        Args:
            file_path (str): Path to the audio file
            extinf_info (dict): Information from EXTINF line
            
        Returns:
            dict: Song metadata dictionary or None if failed
        """
        # Check if file exists
        file_exists = os.path.exists(file_path)
        
        try:
            # Try to extract full metadata from file (only if it exists)
            metadata_info = None
            if file_exists:
                metadata_info = metadata.extract_metadata_for_playlist(file_path)
            
            if metadata_info:
                # Use extracted metadata but prefer EXTINF info if available
                song = metadata_info.copy()
                
                # Override with EXTINF info if available (might have corrected info)
                if extinf_info.get('artist'):
                    song['artist'] = extinf_info['artist']
                if extinf_info.get('title'):
                    song['title'] = extinf_info['title']
                if extinf_info.get('duration'):
                    song['length'] = extinf_info['duration']
                
                # Add file existence flag
                song['file_missing'] = not file_exists
                    
                return song
            else:
                # Fallback to basic EXTINF info if metadata extraction fails
                return {
                    'url': file_path,
                    'artist': extinf_info.get('artist', 'Unknown Artist'),
                    'title': extinf_info.get('title', Path(file_path).stem),
                    'album': 'Unknown Album',
                    'albumartist': extinf_info.get('artist', 'Unknown Artist'),
                    'length': extinf_info.get('duration', 0),
                    'track': 0,
                    'disc': 0,
                    'year': 0,
                    'genre': 'Unknown',
                    'file_missing': not file_exists
                }
                
        except Exception as e:
            print(f"Warning: Could not extract metadata from {file_path}: {e}")
            return {
                'url': file_path,
                'title': Path(file_path).stem,
                'artist': 'Unknown Artist',
                'album': 'Unknown Album',
                'albumartist': 'Unknown Artist',
                'length': 0,
                'track': 0,
                'disc': 0,
                'year': 0,
                'genre': 'Unknown',
                'file_missing': not file_exists
            }


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
                    'length': self._parse_duration(metadata.get('duration', '0:00'))
                }
            else:
                # Fallback if metadata extraction fails (error reading metadata)
                return {
                    'title': Path(filepath).stem,
                    'artist': 'Unknown',
                    'album': 'Unknown',
                    'albumartist': 'Unknown',
                    'year': 'Unknown',
                    'length': 0
                }
                
        except Exception as e:
            print(f"Error getting metadata for {filepath}: {e}")
            return {
                'title': Path(filepath).stem,
                'artist': 'Unknown', 
                'album': 'Unknown',
                'albumartist': 'Unknown',
                'year': 'Unknown',
                'length': 0
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
        self.should_stop = False  # Controls position updates only
        self.thread_should_exit = False  # Controls main thread loop exit
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
            # Keep loop running as long as process is alive and thread shouldn't exit
            while not self.thread_should_exit and self.process.poll() is None:
                
                if not self.pause_start and not self.should_stop:
                    # Query actual position from the audio daemon every 0.1 seconds for smooth seekbar
                    actual_position = self.get_position()
                    
                    if actual_position >= 0:  # Emit position updates for all valid positions including 0
                        # Use the actual audio position
                        self.last_known_position = actual_position
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
        # Set should_stop immediately to stop position updates
        self.should_stop = True
        
        # Set thread_should_exit to stop the main thread loop
        self.thread_should_exit = True
        
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
                        time.sleep(1.0)
                        continue
                
                # Check for events (this blocks for up to 1 second)
                self._check_daemon_events()
                
            except Exception as e:
                print(f"EventListener: Error in event loop: {e}")
                self.event_socket = None
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
        print(f"PlayerWorker: Reset should_stop=False for new song, duration={duration}")
        print(f"PlayerWorker: Position update loop active: {not self.should_stop and self.isRunning()}")
        
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
            modules_dir = Path(__file__).parent.parent.parent.parent / "modules"
            
            # Build command - start daemon without specific file (persistent mode)
            cmd = ["python", "walrio.py", "player", "--daemon"]
            
            # Run walrio player in daemon mode for external control
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