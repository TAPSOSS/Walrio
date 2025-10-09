#!/usr/bin/env python3
"""
Worker classes for background tasks in Walrio GUI
Copyright (c) 2025 TAPS OSS
Project: https://github.com/TAPSOSS/Walrio
Licensed under the BSD-3-Clause License (see LICENSE file for details)

Contains QueueWorker and PlayerWorker classes for handling
audio metadata extraction and playback operations.
"""

import sys
import os
import subprocess
import threading
import time
import tempfile
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
    playlist_loaded = Signal(str, list)  # playlist_name, songs
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
            
            # Process files in batches with metadata extraction
            for i, (file_path, extinf_info) in enumerate(file_paths):
                if self.should_stop:
                    break
                
                # Emit progress
                self.progress_updated.emit(i + 1, total_files, Path(file_path).name)
                
                # Extract metadata for this file
                song_data = self._get_song_metadata(file_path, extinf_info)
                if song_data:
                    songs.append(song_data)
                
                # Small delay to keep UI responsive
                self.msleep(1)  # 1ms delay between files
            
            if not self.should_stop:
                self.playlist_loaded.emit(self.playlist_name, songs)
                
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
        try:
            # Try to extract full metadata from file
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
                    'genre': 'Unknown'
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
                'genre': 'Unknown'
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
        self.should_stop = False  # Controls position updates only
        self.thread_should_exit = False  # Controls main thread loop exit
        self.start_time = None
        self.paused_duration = 0
        self.pause_start = None
        self.last_known_position = 0
        self.process = None
    
    def run(self):
        """Run the audio player with direct communication."""
        try:
            # Start the audio process
            self._start_audio_process()
            
            # Main monitoring loop (position updates only, no event checking)
            # Keep loop running as long as process is alive and thread shouldn't exit
            while not self.thread_should_exit and self.process is not None and self.process.poll() is None:
                
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
            # Cleanup audio player if needed
            if hasattr(self, 'audio_player') and self.audio_player:
                try:
                    self.audio_player.should_quit = True
                except Exception:
                    pass
    
    def _send_player_command(self, command):
        """Send a command directly to the in-process audio player.
        
        Args:
            command (str): Command to send to the player
            
        Returns:
            tuple: (success: bool, response: str)
        """
        if not (self.process and self.process.poll() is None):
            return False, "No active player process"
            
        if not hasattr(self, 'audio_player') or not self.audio_player:
            return False, "Audio player not initialized"
            
        try:
            # Parse and execute the command directly
            cmd_parts = command.split(' ', 1)
            cmd = cmd_parts[0].lower()
            args = cmd_parts[1] if len(cmd_parts) > 1 else None
            
            if cmd == 'play':
                success = self.audio_player.play()
                return success, "OK: Play command executed" if success else "ERROR: Play failed"
            
            elif cmd == 'pause':
                success = self.audio_player.pause()
                return success, "OK: Pause command executed" if success else "ERROR: Pause failed"
            
            elif cmd == 'resume':
                success = self.audio_player.resume()
                return success, "OK: Resume command executed" if success else "ERROR: Resume failed"
            
            elif cmd == 'stop':
                success = self.audio_player.stop()
                return success, "OK: Stop command executed" if success else "ERROR: Stop failed"
            
            elif cmd == 'load' and args:
                success = self.audio_player.load_file(args)
                return success, f"OK: Loaded {args}" if success else f"ERROR: Failed to load {args}"
            
            elif cmd == 'volume' and args:
                try:
                    volume = float(args)
                    self.audio_player.set_volume(volume)
                    return True, f"OK: Volume set to {volume}"
                except ValueError:
                    return False, f"ERROR: Invalid volume value: {args}"
            
            elif cmd == 'seek' and args:
                try:
                    position = float(args)
                    success = self.audio_player.seek(position)
                    return success, f"OK: Seeked to {position}" if success else f"ERROR: Seek to {position} failed"
                except ValueError:
                    return False, f"ERROR: Invalid seek position: {args}"
            
            else:
                return False, f"ERROR: Unknown command: {command}"
                
        except Exception as e:
            return False, f"Command error: {e}"
    
    def pause(self):
        """
        Pause the playback using direct audio player.
        
        Returns:
            bool: True if pause command was successful, False otherwise.
        """
        if not hasattr(self, 'audio_player') or not self.audio_player:
            print("Error pausing: Audio player not initialized")
            return False
            
        try:
            success = self.audio_player.pause()
            if success:
                self.pause_start = time.time()
                print("Pause command successful")
            else:
                print("Error pausing: Pause failed")
            return success
        except Exception as e:
            print(f"Error pausing: {e}")
            return False
    
    def resume(self):
        """
        Resume the playback using direct audio player.
        
        Returns:
            bool: True if resume command was successful, False otherwise.
        """
        if not hasattr(self, 'audio_player') or not self.audio_player:
            print("Error resuming: Audio player not initialized")
            return False
            
        try:
            success = self.audio_player.resume()
            if success:
                if self.pause_start:
                    # Add the paused duration to our total paused time
                    self.paused_duration += time.time() - self.pause_start
                    self.pause_start = None
                print("Resume command successful")
            else:
                print("Error resuming: Resume failed")
            return success
        except Exception as e:
            print(f"Error resuming: {e}")
            return False
    
    def stop(self):
        """Stop the playback using direct audio player."""
        # Set should_stop immediately to stop position updates
        self.should_stop = True
        
        # Set thread_should_exit to stop the main thread loop
        self.thread_should_exit = True
        
        # Stop audio player thread handling
        
        # Stop the audio player directly
        if hasattr(self, 'audio_player') and self.audio_player:
            try:
                success = self.audio_player.stop()
                if success:
                    print("Stop command successful")
                else:
                    print("Error stopping: Stop failed")
            except Exception as e:
                print(f"Error stopping audio player: {e}")
        
        # Terminate the mock process if needed
        if self.process:
            try:
                self.process.terminate()
            except Exception as e:
                print(f"Error terminating process: {e}")
        
        # Give the run loop a moment to notice should_stop and exit
        time.sleep(0.05)
    
    def seek(self, position):
        """
        Seek to a specific position using direct audio player.
        
        Args:
            position (float): Position in seconds to seek to
            
        Returns:
            bool: True if seek command was successful, False otherwise.
        """
        if not hasattr(self, 'audio_player') or not self.audio_player:
            print("Error seeking: Audio player not initialized")
            return False
            
        try:
            success = self.audio_player.seek(position)
            
            if success:
                print(f"Seek to {position:.2f}s successful")
                # If seek was successful, update our timing
                current_time = time.time()
                self.start_time = current_time - position
                self.paused_duration = 0
                self.pause_start = None
                self.last_known_position = position
            else:
                print(f"Error seeking: Seek to {position:.2f}s failed")
                
            return success
        except Exception as e:
            print(f"Error seeking: {e}")
            return False
    
    def set_volume(self, volume):
        """
        Set the playback volume using direct audio player.
        
        Args:
            volume (float): Volume level between 0.0 and 1.0
            
        Returns:
            bool: True if volume command was successful, False otherwise.
        """
        if not hasattr(self, 'audio_player') or not self.audio_player:
            print("Error setting volume: Audio player not initialized")
            return False
            
        try:
            self.audio_player.set_volume(volume)
            print(f"Volume set to {volume:.2f}")
            return True
        except Exception as e:
            print(f"Error setting volume: {e}")
            return False
    
    def get_position(self):
        """
        Get the current playback position from the direct audio player.
        
        Returns:
            float: Current position in seconds, or 0 if query fails
        """
        if not hasattr(self, 'audio_player') or not self.audio_player:
            return 0.0
            
        try:
            return self.audio_player.get_position()
        except Exception as e:
            print(f"Error getting position: {e}")
            return 0.0
    
    def send_command(self, command):
        """
        Send a command to the direct audio player.
        
        Args:
            command (str): Command to send to the player
            
        Returns:
            bool: True if command was sent successfully, False otherwise
        """
        success, response = self._send_player_command(command)
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
        
        # If we have an audio player, use it directly to switch songs
        if hasattr(self, 'audio_player') and self.audio_player:
            try:
                # Load the new file
                print(f"PlayerWorker: Loading new song: {filepath}")
                success = self.audio_player.load_file(filepath)
                if success:
                    print(f"PlayerWorker: Loaded new song: {filepath}")
                    # Start playback of the loaded song
                    play_success = self.audio_player.play()
                    if play_success:
                        print("PlayerWorker: Started playback successfully")
                        # Record the start time for this new song
                        self.start_time = time.time()
                    else:
                        print("PlayerWorker: Failed to start playback")
                else:
                    print(f"PlayerWorker: Failed to load new song: {filepath}")
            except Exception as e:
                print(f"PlayerWorker: Error loading new song: {e}")
        else:
            # Start audio player if not initialized
            if not self.isRunning():
                self.start()
            else:
                self._start_audio_process()
    
    def _start_audio_process(self):
        """Initialize the in-process audio player (standard approach)."""
        try:
            # Import and initialize the AudioPlayer directly (works everywhere)
            from modules.core.player import AudioPlayer
            self.audio_player = AudioPlayer()
            
            # Create a simple mock process object for compatibility
            self.process = type('MockProcess', (), {
                'poll': lambda: None,  # Always return None (running)
                'terminate': self._terminate_audio_player
            })()
            
            print("In-process audio player initialized successfully")
            
        except ImportError as e:
            print(f"Failed to import AudioPlayer: {e}")
            self.process = None
            return
        except Exception as e:
            print(f"Failed to initialize audio player: {e}")
            self.process = None
            return
    
    def _terminate_audio_player(self):
        """Terminate the in-process audio player."""
        if hasattr(self, 'audio_player') and self.audio_player:
            try:
                self.audio_player.stop()
                self.audio_player.should_quit = True
                if hasattr(self.audio_player, 'loop') and self.audio_player.loop.is_running():
                    self.audio_player.loop.quit()
                print("Audio player terminated successfully")
            except Exception as e:
                print(f"Error terminating audio player: {e}")
        
        # If we have a file to play, load it now
        if hasattr(self, 'filepath') and self.filepath and hasattr(self, 'audio_player') and self.audio_player:
            try:
                success = self.audio_player.load_file(self.filepath)
                if success:
                    print(f"PlayerWorker: Loaded initial song: {self.filepath}")
                    # Start playback of the loaded song  
                    play_success = self.audio_player.play()
                    if play_success:
                        print("PlayerWorker: Started playback successfully")
                        # Record the start time
                        self.start_time = time.time()
                    else:
                        print("PlayerWorker: Failed to start playback")
                else:
                    print(f"PlayerWorker: Failed to load initial song: {self.filepath}")
            except Exception as e:
                print(f"Error loading initial song: {e}")