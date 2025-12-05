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
import socket
import json
from pathlib import Path

# Add the parent directory to the Python path so we can import modules
sys.path.append(os.path.join(os.path.dirname(__file__), '../../..'))

from modules.core import metadata
from modules.core.gstreamer_player import AudioPlayer

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
                    'length': metadata['length'],
                    'file_missing': metadata['file_missing']
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
            dict: Dictionary containing song metadata with keys like 'title', 'artist', 'album', 'albumartist', 'year', 'duration', 'file_missing'.
        """
        # Check if file exists first
        file_exists = os.path.exists(filepath)
        
        try:
            # Import metadata module directly instead of subprocess
            from modules.core.metadata import MetadataEditor
            
            # Get metadata using the module
            meta = MetadataEditor(filepath)
            tag_data = meta.get_all_tags()
            
            # Return structured metadata with fallbacks
            return {
                'title': tag_data.get('title') or Path(filepath).stem,
                'artist': tag_data.get('artist') or '',
                'album': tag_data.get('album') or '',
                'albumartist': tag_data.get('albumartist') or tag_data.get('artist') or '',
                'year': str(tag_data.get('year') or tag_data.get('originalyear') or ''),
                'length': tag_data.get('length', 0),
                'file_missing': not file_exists
            }
                
        except Exception as e:
            print(f"Error getting metadata for {filepath}: {e}")
            return {
                'title': Path(filepath).stem,
                'artist': 'Unknown', 
                'album': 'Unknown',
                'albumartist': 'Unknown',
                'year': 'Unknown',
                'length': 0,
                'file_missing': not file_exists
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
    """Worker thread for handling audio playback operations using centralized GStreamer AudioPlayer."""
    
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
        self.thread_should_exit = False
        
        # Initialize the GStreamer-based audio player
        self.audio_player = AudioPlayer()
        
        # Position tracking
        self.position_timer = None
    
    def run(self):
        """Run using the centralized AudioPlayer from modules."""
        try:
            # Load and start playback if filepath is provided
            if self.filepath:
                success = self.audio_player.load_file(self.filepath)
                if success:
                    # Get actual duration from the audio player
                    detected_duration = self.audio_player.get_duration()
                    print(f"DEBUG: AudioPlayer detected duration: {detected_duration}")
                    if detected_duration > 0:
                        self.duration = detected_duration
                        print(f"DEBUG: Updated PlayerWorker duration to: {self.duration}")
                    
                    # Emit song starting signal with detected duration
                    print(f"DEBUG: Emitting song_starting signal with duration: {self.duration}")
                    self.song_starting.emit({
                        'filepath': self.filepath,
                        'duration': self.duration,
                        'title': os.path.basename(self.filepath),
                        'position': 0.0
                    })
                    
                    # Start playback using modules/core/player.py
                    play_success = self.audio_player.play()
                    if not play_success:
                        self.error.emit(f"Failed to start playback: {self.filepath}")
                        return
                else:
                    self.error.emit(f"Failed to load file: {self.filepath}")
                    return
            
            # Position tracking now handled by main thread
            
            # Main loop - monitor playback state from modules/core/player.py
            while not self.should_stop and not self.thread_should_exit:
                # Process any pending GLib main context messages to ensure bus messages are handled
                try:
                    from gi.repository import GLib
                    main_context = GLib.MainContext.default()
                    while main_context.pending():
                        main_context.iteration(False)
                except Exception as e:
                    pass  # Ignore GLib processing errors
                
                # Check playback state from the core player module
                player_state = self.audio_player.get_state()
                
                if not player_state['is_playing'] and not player_state['is_paused']:
                    if hasattr(self, '_playback_was_active') and self._playback_was_active:
                        print("PlayerWorker: Playback finished (detected by core player state polling)")
                        print(f"PlayerWorker: Player state - is_playing: {player_state['is_playing']}, is_paused: {player_state['is_paused']}")
                        self.playback_finished.emit()
                        break
                
                # Track if we were playing for completion detection
                if player_state['is_playing']:
                    self._playback_was_active = True
                
                # Brief sleep to avoid busy waiting
                time.sleep(0.1)
                
        except Exception as e:
            error_msg = f"Error in player worker: {e}"
            print(error_msg)
            self.error.emit(error_msg)
        # No command handling here; all playback is managed by AudioPlayer (GStreamer).
    
    def pause(self):
        """
        Pause the playback using core AudioPlayer.
        
        Returns:
            bool: True if pause command was successful, False otherwise.
        """
        if self.audio_player:
            return self.audio_player.pause()
        return False
    
    def resume(self):
        """
        Resume the playback using core AudioPlayer.
        
        Returns:
            bool: True if resume command was successful, False otherwise.
        """
        if self.audio_player:
            return self.audio_player.resume()
        return False
    
    def stop(self):
        """Stop the playback using core AudioPlayer."""
        # Set flags to stop the worker thread
        self.should_stop = True
        self.thread_should_exit = True
        
        # Stop the core audio player
        if hasattr(self, 'audio_player') and self.audio_player:
            try:
                success = self.audio_player.stop()
                print("Stop command successful" if success else "Stop command failed")
                return success
            except Exception as e:
                print(f"Error stopping audio player: {e}")
                return False
        
        return True
    
    def seek(self, position):
        """
        Seek to a specific position using core AudioPlayer.
        
        Args:
            position (float): Position in seconds to seek to
            
        Returns:
            bool: True if seek command was successful, False otherwise.
        """
        if hasattr(self, 'audio_player') and self.audio_player:
            try:
                success = self.audio_player.seek(position)
                print(f"Seek to {position:.2f}s {'successful' if success else 'failed'}")
                return success
            except Exception as e:
                print(f"Error seeking: {e}")
                return False
        return False
    
    def set_volume(self, volume):
        """
        Set the playback volume using core AudioPlayer.
        
        Args:
            volume (float): Volume level between 0.0 and 1.0
            
        Returns:
            bool: True if volume command was successful, False otherwise.
        """
        if hasattr(self, 'audio_player') and self.audio_player:
            try:
                success = self.audio_player.set_volume(volume)
                print(f"Volume set to {volume:.2f} {'successfully' if success else 'failed'}")
                return success
            except Exception as e:
                print(f"Error setting volume: {e}")
                return False
        return False
    
    def get_position(self):
        """
        Get the current playback position from core AudioPlayer.
        
        Returns:
            float: Current position in seconds, or 0 if not playing
        """
        if hasattr(self, 'audio_player') and self.audio_player:
            try:
                return self.audio_player.get_position()
            except Exception as e:
                print(f"Error getting position: {e}")
                return 0.0
        return 0.0
    
    def send_command(self, command):
        """
        Send a command to the direct audio player.
        
        Args:
            command (str): Command to send to the player
            
        Returns:
            bool: True if command was sent successfully, False otherwise
        """
        # Directly handle supported commands
        cmd_parts = command.split(' ', 1)
        cmd = cmd_parts[0].lower()
        args = cmd_parts[1] if len(cmd_parts) > 1 else None
        if cmd == 'play':
            return self.audio_player.play()
        elif cmd == 'pause':
            return self.audio_player.pause()
        elif cmd == 'resume':
            return self.audio_player.resume()
        elif cmd == 'stop':
            return self.audio_player.stop()
        elif cmd == 'load' and args:
            return self.audio_player.load_file(args)
        elif cmd == 'volume' and args:
            try:
                volume = float(args)
                return self.audio_player.set_volume(volume)
            except ValueError:
                return False
        elif cmd == 'seek' and args:
            try:
                position = float(args)
                return self.audio_player.seek(position)
            except ValueError:
                return False
        elif cmd == 'loop' and args:
            self.audio_player.set_loop_mode(args)
            return True
        else:
            return False
    
    def _start_position_tracking(self):
        """Start position tracking timer."""
        if hasattr(self, 'position_timer') and self.position_timer:
            print("DEBUG: Position timer already running")
            return  # Already running
            
        from PySide6.QtCore import QTimer
        self.position_timer = QTimer()
        self.position_timer.timeout.connect(self._update_position)
        self.position_timer.start(100)  # Update every 100ms
        print("DEBUG: Position timer started - updating every 100ms")
    
    def _stop_position_tracking(self):
        """Stop position tracking timer."""
        if hasattr(self, 'position_timer') and self.position_timer:
            self.position_timer.stop()
            self.position_timer = None
    
    # Not needed for VLC
    
    def _update_position(self):
        """Update position and emit signal."""
        if not self.should_stop and hasattr(self, 'audio_player') and self.audio_player:
            try:
                # Get position directly from audio player
                position = self.audio_player.get_position()
                
                # Debug: Always print first few position updates and periodically after
                if not hasattr(self, '_pos_update_count'):
                    self._pos_update_count = 0
                self._pos_update_count += 1
                
                if self._pos_update_count <= 5 or self._pos_update_count % 50 == 0:  # First 5 then every 5 seconds
                    print(f"DEBUG: Position update #{self._pos_update_count}: position={position}")
                
                # Emit position updates if we have a valid position
                if position >= 0:
                    self.position_updated.emit(position)
                    # Debug: Print position occasionally  
                    if hasattr(self, '_last_pos_debug'):
                        if abs(position - self._last_pos_debug) > 1.0:  # Every second
                            print(f"DEBUG: Position update: {position:.1f}s")
                            self._last_pos_debug = position
                    else:
                        self._last_pos_debug = position
                        print(f"DEBUG: First position update: {position:.1f}s")
                        
            except Exception as e:
                print(f"DEBUG: Error updating position: {e}")
    
    def play_new_song(self, filepath, duration=0):
        """Load and play a new song using core AudioPlayer."""
        try:
            # Stop current playback
            if hasattr(self, 'audio_player') and self.audio_player:
                self.audio_player.stop()
            
            # Update file info
            self.filepath = filepath
            self.duration = duration
            self.should_stop = False
            
            # Load new file
            if self.audio_player.load_file(filepath):
                # Get actual duration
                detected_duration = self.audio_player.get_duration()
                print(f"DEBUG: play_new_song - AudioPlayer detected duration: {detected_duration}")
                if detected_duration > 0:
                    self.duration = detected_duration
                    print(f"DEBUG: play_new_song - Updated duration to: {self.duration}")
                
                # Emit song starting signal
                print(f"DEBUG: play_new_song - Emitting song_starting signal with duration: {self.duration}")
                self.song_starting.emit({
                    'filepath': filepath,
                    'duration': self.duration,
                    'title': os.path.basename(filepath),
                    'position': 0.0
                })
                
                # Start playback
                return self.audio_player.play()
            return False
        except Exception as e:
            print(f"Error playing new song: {e}")
            return False
    
    # Note: Daemon connection methods removed - now using direct AudioPlayer integration
    # from modules/core/player.py for better reliability and threading compatibility
    
    # PlayerWorker now uses direct integration with modules/core/player.py AudioPlayer
    # instead of subprocess or daemon approaches for better reliability and threading
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
                    print("PlayerWorker: Song finished event - emitting playback_finished")
                    print(f"PlayerWorker: Emitting playback_finished signal now...")
                    # Don't set should_stop=True here - PlayerWorker needs to stay alive for next song
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
    
    def _get_duration_with_ffprobe(self, filepath):
        """Get duration of audio file using ffprobe."""
        try:
            import subprocess
            cmd = [
                'ffprobe',
                '-v', 'quiet',
                '-show_entries', 'format=duration',
                '-of', 'csv=p=0',
                filepath
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
            if result.returncode == 0 and result.stdout.strip():
                duration = float(result.stdout.strip())
                print(f"Detected duration: {duration} seconds for {os.path.basename(filepath)}")
                return duration
        except Exception as e:
            print(f"Error getting duration with ffprobe: {e}")
        return 0.0

    def _start_audio_process(self):
        """Initialize audio process using mpv for better control, fallback to ffplay."""
        try:
            # First, terminate any existing process
            if hasattr(self, 'process') and self.process:
                try:
                    if hasattr(self.process, 'terminate'):
                        self.process.terminate()
                        print("Terminated previous audio process")
                except Exception as e:
                    print(f"Error terminating previous process: {e}")
                    
            # Try to use mpv first (better control), then ffplay as fallback
            if hasattr(self, 'filepath') and self.filepath and os.path.exists(self.filepath):
                import subprocess
                import tempfile
                
                # Get the actual duration using ffprobe
                detected_duration = self._get_duration_with_ffprobe(self.filepath)
                if detected_duration > 0:
                    self.duration = detected_duration
                    print(f"Updated duration to {self.duration} seconds")
                
                # Try mpv first (better for control)
                try:
                    # Create a temporary socket for mpv IPC
                    self.mpv_socket = tempfile.mktemp(suffix='.sock', prefix='walrio_mpv_')
                    
                    cmd = [
                        'mpv',
                        '--no-video',  # Audio only
                        '--no-terminal',  # No terminal output
                        f'--input-ipc-server={self.mpv_socket}',  # Enable IPC control
                        '--idle=yes',  # Stay open after file ends
                        self.filepath
                    ]
                    
                    self.process = subprocess.Popen(
                        cmd,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        stdin=subprocess.PIPE
                    )
                    self.audio_backend = 'mpv'
                    print(f"MPV audio player started for: {os.path.basename(self.filepath)}")
                    
                except FileNotFoundError:
                    print("mpv not found, trying ffplay...")
                    # Fallback to ffplay
                    cmd = [
                        'ffplay',
                        '-nodisp',  # No display window
                        '-autoexit',  # Exit when playback finishes
                        '-loglevel', 'quiet',  # Suppress verbose output
                        self.filepath
                    ]
                    
                    self.process = subprocess.Popen(
                        cmd,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        stdin=subprocess.PIPE
                    )
                    self.audio_backend = 'ffplay'
                    print(f"FFplay audio player started for: {os.path.basename(self.filepath)}")
                
                self.start_time = time.time()
                
                # Emit song_starting signal with duration info
                self.song_starting.emit({
                    'filepath': self.filepath,
                    'duration': self.duration,
                    'title': os.path.basename(self.filepath),
                    'position': 0.0
                })
                return
                    
            # Fallback to mock if ffplay not available or no file
            self.process = type('MockProcess', (), {
                'poll': lambda *args: None,  # Always return None (running)
                'terminate': lambda *args: None
            })()
            
            print("Mock audio player initialized (ffplay not available)")
            
            # Load file if specified
            if hasattr(self, 'filepath') and self.filepath:
                print(f"PlayerWorker: Would load {self.filepath} (mock mode)")
                self.start_time = time.time()
            
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