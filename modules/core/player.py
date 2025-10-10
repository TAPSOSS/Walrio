#!/usr/bin/env python3
"""
Audio Player using GStreamer Python Bindings
Copyright (c) 2025 TAPS OSS
Project: https://github.com/TAPSOSS/Walrio
Licensed under the BSD-3-Clause License (see LICENSE file for details)

A simple audio player that uses GStreamer Python bindings for real-time control
including volume, seeking, and playback management.
"""

import sys
import os
import signal
import json
import argparse
import threading
import time
import socket
import tempfile
from pathlib import Path

import gi
gi.require_version('Gst', '1.0')
from gi.repository import Gst, GLib

class AudioPlayer:
    """
    GStreamer-based audio player with real-time control.
    """
    def __init__(self):
        from gi.repository import Gst
        if not Gst.is_initialized():
            Gst.init(None)
        self.pipeline = None
        self.bus = None
        self.current_file = None
        self.is_playing = False
        self.is_paused = False
        self.duration = 0
        self.volume_value = 1.0
        self.loop_mode = 'off'
        self.repeat_count = 0
        self.position_callback = None
        self.position_update_interval = 500
        self.position_timeout_id = None
        self.should_quit = False
        self.interactive_mode = False
    
    def _start_position_updates(self):
        """Start sending position updates via callback."""
        if self.position_callback and not self.position_timeout_id:
            from gi.repository import GLib
            # Use GLib timeout for thread-safe position updates
            self.position_timeout_id = GLib.timeout_add(
                self.position_update_interval, 
                self._emit_position_update
            )
            print("DEBUG: Started GStreamer position updates")
    
    def _stop_position_updates(self):
        """Stop sending position updates."""
        if self.position_timeout_id:
            from gi.repository import GLib
            GLib.source_remove(self.position_timeout_id)
            self.position_timeout_id = None
            print("DEBUG: Stopped GStreamer position updates")
    
    def _emit_position_update(self):
        """Emit position update via callback. Returns True to keep timeout active."""
        if self.position_callback and self.pipeline and self.is_playing:
            try:
                position = self.get_position()
                if position >= 0:
                    self.position_callback(position)
                return True  # Keep timeout active
            except Exception as e:
                print(f"DEBUG: Position update error: {e}")
                return True  # Keep trying
        return False  # Stop timeout
    
    # Not needed for VLC
    
    # Not needed for VLC
    
    def _handle_eos(self):
        """Handle end of stream for looping."""
        print("DEBUG: _handle_eos() called")
        if self.should_quit:
            print("DEBUG: should_quit is True, returning early")
            return
        
        # Check if we've had any meaningful playback to avoid premature EOS
        current_position = self.get_position()
        print(f"DEBUG: EOS received at position {current_position:.2f}s")
        
        # Only process EOS if we've actually played for at least 1 second
        # This prevents premature EOS messages from being processed
        if current_position < 1.0:
            print("DEBUG: Ignoring premature EOS - insufficient playback time")
            return
        
        # Send song finished event to listeners
        print("DEBUG: Sending song_finished event to listeners")
        self._send_event("song_finished", {
            "file": self.current_file,
            "repeat_count": self.repeat_count,
            "loop_mode": self.loop_mode
        })
            
        should_loop = False
        if self.loop_mode == 'infinite':
            should_loop = True
        elif self.loop_mode.isdigit():
            if self.repeat_count < int(self.loop_mode):
                should_loop = True
        
        if should_loop:
            self.repeat_count += 1
            print(f"Looping song (repeat #{self.repeat_count})")
            # Send song starting event for repeat
            self._send_event("song_starting", {
                "file": self.current_file,
                "repeat_count": self.repeat_count,
                "is_repeat": True
            })
            # Seek back to beginning with explicit 0.0 to ensure it's a proper float
            self.seek(0.0)
        else:
            print(f"Finished looping after {self.repeat_count} repeats")
            # Send playback complete event
            self._send_event("playback_complete", {
                "file": self.current_file,
                "total_repeats": self.repeat_count
            })
            self.stop()
            if self.interactive_mode:
                print("player> ", end="", flush=True)
    
    def load_file(self, filepath):
        """
        Load an audio file for playback.
        """
        absolute_path = os.path.abspath(filepath)
        if not os.path.exists(absolute_path):
            print(f"Error: File '{filepath}' not found.")
            return False
        if not os.path.isfile(absolute_path):
            print(f"Error: '{filepath}' is not a file.")
            return False
        if self.pipeline:
            self.stop()
        self.current_file = absolute_path
        self.pipeline = Gst.ElementFactory.make("playbin", None)
        self.pipeline.set_property("uri", f"file://{absolute_path}")
        self.pipeline.set_property("volume", self.volume_value)
        self.bus = self.pipeline.get_bus()
        self.duration = self._get_file_duration(absolute_path)
        print(f"Loaded: {filepath}")
        if self.duration > 0:
            print(f"Duration: {self.duration:.1f} seconds")
        return True
    
    def play(self, seek_position=None):
        """
        Start or resume playback.
        """
        if not self.current_file:
            print("Error: No file loaded")
            return False
        if not self.pipeline:
            if not self.load_file(self.current_file):
                return False
        self.pipeline.set_state(Gst.State.PLAYING)
        self.is_playing = True
        self.is_paused = False
        if seek_position is not None:
            self.seek(seek_position)
        if seek_position is None or seek_position == 0:
            self.repeat_count = 0
        self._send_event("song_starting", {
            "file": self.current_file,
            "duration": self.duration,
            "seek_position": seek_position or 0,
            "is_repeat": False
        })
        self._start_position_updates()
        print("Playback started")
        return True
    
    def _run_loop(self):
        """Run the GLib main loop."""
        self.loop.run()
    
    def pause(self):
        """
        Pause playback.
        """
        if not self.is_playing or not self.pipeline:
            print("Player is not currently playing")
            return False
        self.pipeline.set_state(Gst.State.PAUSED)
        self.is_playing = False
        self.is_paused = True
        print("Playback paused")
        return True
    
    def resume(self):
        """
        Resume paused playback.
        """
        if not self.is_paused or not self.pipeline:
            print("Player is not currently paused")
            return False
        self.pipeline.set_state(Gst.State.PLAYING)
        self.is_playing = True
        self.is_paused = False
        print("Playback resumed")
        return True
    
    def stop(self):
        """
        Stop playback.
        """
        if self.pipeline:
            self.pipeline.set_state(Gst.State.NULL)
            self.pipeline = None
        self.is_playing = False
        self.is_paused = False
        self._stop_position_updates()
        print("Playback stopped")
        return True
    
    def set_volume(self, volume):
        """
        Set playback volume in real-time.
        """
        if volume < 0.0 or volume > 1.0:
            print("Error: Volume must be between 0.0 and 1.0")
            return False
        self.volume_value = volume
        if self.pipeline:
            self.pipeline.set_property("volume", volume)
            print(f"Volume set to {volume:.2f}")
        else:
            print(f"Volume will be set to {volume:.2f} when playback starts")
        return True
    
    def get_volume(self):
        """
        Get current volume level.
        
        Returns:
            float: Current volume between 0.0 and 1.0.
        """
        return self.volume_value
    
    def seek(self, position_seconds):
        """
        Seek to a specific position in the audio using VLC.
        """
        if not self.current_file:
            print("Error: No file loaded")
            return False
        try:
            position_seconds = float(position_seconds)
        except (ValueError, TypeError) as e:
            print(f"Error: Invalid seek position: {position_seconds}, error: {e}")
            return False
        if position_seconds < 0:
            print("Error: Seek position cannot be negative")
            return False
        if self.duration > 0 and position_seconds > self.duration:
            print(f"Error: Seek position {position_seconds:.1f}s exceeds duration {self.duration:.1f}s")
            return False
        if not self.pipeline:
            print("Error: No player available for seeking")
            return False
        seek_event = Gst.Event.new_seek(
            1.0, Gst.Format.TIME,
            Gst.SeekFlags.FLUSH | Gst.SeekFlags.KEY_UNIT,
            Gst.SeekType.SET, int(position_seconds * Gst.SECOND),
            Gst.SeekType.NONE, -1
        )
        res = self.pipeline.send_event(seek_event)
        if res:
            print(f"Seeked to {position_seconds:.1f} seconds")
            return True
        else:
            print(f"Error seeking to {position_seconds} seconds")
            return False
    
    def get_position(self):
        """
        Get current playback position from VLC player.
        """
        if self.pipeline:
            success, position = self.pipeline.query_position(Gst.Format.TIME)
            if success:
                self.position = position / Gst.SECOND
                return self.position
        return self.position
    
    def get_duration(self):
        """
        Get total duration of the current audio file.
        """
        if self.pipeline:
            success, duration = self.pipeline.query_duration(Gst.Format.TIME)
            if success and duration > 0:
                self.duration = duration / Gst.SECOND
        return self.duration
    
    def set_loop_mode(self, mode):
        """
        Set loop mode for playback.
        
        Args:
            mode (str): Loop mode - 'none', number (e.g. '3'), or 'infinite'.
            
        Returns:
            bool: True if loop mode set successfully, False otherwise.
        """
        # Validate input
        if mode != 'none' and mode != 'infinite' and not mode.isdigit():
            print("Error: Loop mode must be 'none', a number (e.g. '3'), or 'infinite'")
            return False
        
        if mode.isdigit() and int(mode) <= 0:
            print("Error: Loop count must be a positive number")
            return False
        
        self.loop_mode = mode
        # Don't reset repeat_count here - let it reset on new playback
        
        if mode == 'none':
            print("Loop mode: Off")
        elif mode == 'infinite':
            print("Loop mode: Infinite repeats")
        elif mode.isdigit():
            print(f"Loop mode: Repeat {mode} times")
        
        return True
    
    def get_loop_mode(self):
        """
        Get current loop mode.
        
        Returns:
            str: Current loop mode setting.
        """
        return self.loop_mode
    
    def get_repeat_count(self):
        """
        Get number of times the current song has repeated.
        
        Returns:
            int: Number of repeats completed.
        """
        return self.repeat_count
    
    def get_state(self):
        """
        Get current player state information.
        
        Returns:
            dict: Dictionary containing player state including:
                - is_playing (bool): Whether audio is currently playing
                - is_paused (bool): Whether audio is paused
                - current_file (str): Path to current file
                - position (float): Current position in seconds
                - duration (float): Total duration in seconds
                - volume (float): Current volume level
                - loop_mode (str): Current loop mode
                - repeat_count (int): Number of repeats completed
        """
        return {
            "is_playing": self.is_playing,
            "is_paused": self.is_paused,
            "current_file": self.current_file,
            "position": self.get_position(),
            "duration": self.get_duration(),
            "volume": self.get_volume(),
            "loop_mode": self.loop_mode,
            "repeat_count": self.repeat_count
        }
    
    def run_interactive(self):
        """
        Run the player in interactive mode with command input.
        
        Starts a command-line interface allowing real-time control
        of playback through user commands.
        """
        self.interactive_mode = True
        print("\nInteractive Audio Player")
        print("Commands:")
        print("  play/p    - Start/resume playback")
        print("  pause/ps  - Pause playback")
        print("  stop/s    - Stop playback")
        print("  volume/v <0.0-1.0> - Set volume")
        print("  seek/sk <seconds>   - Seek to position")
        print("  loop/l <none|number|infinite> - Set loop mode (e.g. 'loop 3' or 'loop infinite')")
        print("  status/st - Show current status")
        print("  quit/q    - Quit player")
        print()
        
        # Handle input directly in main thread
        self.handle_input()
    
    def handle_input(self):
        """
        Handle user input in interactive mode.
        
        Processes user commands while audio playback continues.
        """
        while not self.should_quit:
            try:
                cmd = input("player> ").strip().lower()
                if not cmd:
                    continue
                
                parts = cmd.split()
                command = parts[0]
                
                if command in ['quit', 'q']:
                    self.should_quit = True
                    self.stop()
                    break
                elif command in ['play', 'p']:
                    if self.is_paused:
                        self.resume()
                    else:
                        self.play()
                elif command in ['pause', 'ps']:
                    self.pause()
                elif command in ['stop', 's']:
                    self.stop()
                elif command in ['volume', 'v'] and len(parts) > 1:
                    try:
                        vol = float(parts[1])
                        self.set_volume(vol)
                    except ValueError:
                        print("Error: Invalid volume value")
                elif command in ['seek', 'sk'] and len(parts) > 1:
                    try:
                        pos = float(parts[1])
                        self.seek(pos)
                    except ValueError:
                        print("Error: Invalid seek position")
                elif command in ['loop', 'l'] and len(parts) > 1:
                    self.set_loop_mode(parts[1])
                elif command in ['status', 'st']:
                    state = self.get_state()
                    print(f"File: {state['current_file'] or 'None'}")
                    print(f"Status: {'Playing' if state['is_playing'] else 'Paused' if state['is_paused'] else 'Stopped'}")
                    print(f"Position: {state['position']:.1f}s / {state['duration']:.1f}s")
                    print(f"Volume: {state['volume']:.2f}")
                    print(f"Loop mode: {state['loop_mode']}")
                    if state['repeat_count'] > 0:
                        if state['loop_mode'] == 'infinite':
                            print(f"Repeat count: {state['repeat_count']} (infinite)")
                        elif state['loop_mode'].isdigit():
                            print(f"Repeat count: {state['repeat_count']}/{state['loop_mode']}")
                        else:
                            print(f"Repeat count: {state['repeat_count']}")
                elif command.startswith('loop') and len(parts) > 1:
                    mode = parts[1]
                    self.set_loop_mode(mode)
                else:
                    print("Unknown command. Type 'quit' to exit.")
            except EOFError:
                break
            except KeyboardInterrupt:
                print("\nExiting...")
                self.stop()
                break
            except Exception as e:
                print(f"Error handling input: {e}")
    
    def run_daemon(self):
        """
        Run the player in daemon mode with socket-based command interface.
        
        Creates a Unix socket server that listens for external commands.
        """
        # Create socket file in temp directory
        self.socket_path = os.path.join(tempfile.gettempdir(), f"walrio_player_{os.getpid()}.sock")
        
        # Remove existing socket file if it exists
        if os.path.exists(self.socket_path):
            os.unlink(self.socket_path)
        
        # Create Unix socket
        self.daemon_socket = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.daemon_socket.bind(self.socket_path)
        self.daemon_socket.listen(1)
        
        print(f"Daemon mode started. Socket: {self.socket_path}")
        
        # Start command server in a separate thread
        command_thread = threading.Thread(target=self._command_server, daemon=True)
        command_thread.start()
        
        # Main daemon loop
        try:
            while not self.should_quit:
                time.sleep(0.1)
        except KeyboardInterrupt:
            print("\nStopping daemon...")
        finally:
            self._cleanup_daemon()
    
    def _command_server(self):
        """Handle incoming commands in daemon mode."""
        while not self.should_quit:
            try:
                # Accept connection with timeout
                self.daemon_socket.settimeout(0.5)
                try:
                    conn, addr = self.daemon_socket.accept()
                except socket.timeout:
                    continue
                
                # Handle connection in a separate thread to support persistent event listeners
                threading.Thread(target=self._handle_connection, args=(conn,), daemon=True).start()
                    
            except Exception as e:
                if not self.should_quit:
                    print(f"Error in command server: {e}")
                break
    
    def _handle_connection(self, conn):
        """Handle a single client connection.
        
        Args:
            conn: Socket connection object for communicating with the client
        """
        is_event_subscription = False
        try:
            while not self.should_quit:
                # Receive command
                data = conn.recv(1024).decode('utf-8').strip()
                if not data:
                    break

                # Check for event subscription
                if data.lower() == 'subscribe':
                    # Add to event listeners
                    is_event_subscription = True
                    self.event_listeners.append(conn)
                    conn.send(b"OK: Subscribed to events\n")
                    # Keep connection alive for events
                    while not self.should_quit:
                        try:
                            # Keep connection alive for events
                            time.sleep(0.1)
                        except Exception:
                            break
                    break  # Exit loop, but connection cleanup depends on subscription status
                
                # Process regular command
                response = self._process_daemon_command(data)
                
                # Send response
                conn.send(response.encode('utf-8'))
                
                # Close connection for regular commands
                break
                
        except Exception as e:
            if not self.should_quit:
                print(f"Error handling connection: {e}")
        finally:
            # Only clean up if NOT an event subscription
            if not is_event_subscription:
                # Remove from event listeners if it was subscribed
                if conn in self.event_listeners:
                    self.event_listeners.remove(conn)
                try:
                    conn.close()
                except:
                    pass

    def _process_daemon_command(self, command):
        """
        Process a daemon command and return response.
        
        Args:
            command (str): The command string to process.
            
        Returns:
            str: Response message indicating success or failure.
        """
        try:
            parts = command.strip().split()
            if not parts:
                return "ERROR: Empty command"
            
            cmd = parts[0].lower()  # Only lowercase the command, not the arguments
            
            if cmd in ['play', 'p']:
                if self.is_paused:
                    result = self.resume()
                else:
                    result = self.play()
                return "OK: Playing" if result else "ERROR: Failed to play"
                
            elif cmd in ['pause', 'ps']:
                result = self.pause()
                return "OK: Paused" if result else "ERROR: Failed to pause"
                
            elif cmd in ['stop', 's']:
                result = self.stop()
                return "OK: Stopped" if result else "ERROR: Failed to stop"
                
            elif cmd in ['resume', 'r']:
                result = self.resume()
                return "OK: Resumed" if result else "ERROR: Failed to resume"
                
            elif cmd == 'status':
                status = "Playing" if self.is_playing else ("Paused" if self.is_paused else "Stopped")
                return f"OK: {status}"
                
            elif cmd == 'quit':
                self.should_quit = True
                self.stop()
                return "OK: Quitting"
                
            elif cmd == 'volume' and len(parts) > 1:
                try:
                    volume = float(parts[1])
                    result = self.set_volume(volume)
                    return f"OK: Volume set to {volume}" if result else "ERROR: Failed to set volume"
                except ValueError:
                    return "ERROR: Invalid volume value"
                    
            elif cmd == 'seek' and len(parts) > 1:
                try:
                    position = float(parts[1])
                    result = self.seek(position)
                    return f"OK: Seeked to {position}s" if result else "ERROR: Failed to seek"
                except ValueError:
                    return "ERROR: Invalid seek position"
                    
            elif cmd in ['position', 'pos']:
                position = self.get_position()
                return f"OK: {position:.3f}"
                
            elif cmd == 'loop' and len(parts) > 1:
                result = self.set_loop_mode(parts[1])
                return f"OK: Loop mode set to {parts[1]}" if result else "ERROR: Failed to set loop mode"
                
            elif cmd == 'load' and len(parts) > 1:
                # Load a new file for playback
                filepath = ' '.join(parts[1:])  # Handle paths with spaces
                try:
                    # Stop current playback first
                    self.stop()
                    # Load the new file
                    result = self.load_file(filepath)
                    if result:
                        self._send_event("song_loaded", {"file": filepath})
                        return f"OK: Loaded {filepath}"
                    else:
                        return f"ERROR: Failed to load {filepath}"
                except Exception as e:
                    return f"ERROR: Failed to load file: {str(e)}"
                    
            elif cmd == 'subscribe':
                # This command is handled in _handle_connection, but we need to handle it here too
                return "OK: Subscribed to events"
                    
            else:
                return f"ERROR: Unknown command '{cmd}'"
                
        except Exception as e:
            return f"ERROR: {str(e)}"
    
    def _cleanup_daemon(self):
        """Clean up daemon resources."""
        try:
            if hasattr(self, 'daemon_socket'):
                self.daemon_socket.close()
            if hasattr(self, 'socket_path') and os.path.exists(self.socket_path):
                os.unlink(self.socket_path)
        except Exception as e:
            print(f"Error cleaning up daemon: {e}")
    
    def _update_position(self):
        """Update position tracking using VLC player queries."""
        while self.is_playing and not self.should_quit:
            if self.player and not self.is_paused:
                self.get_position()
            time.sleep(0.1)
    
    def _start_position_tracking(self):
        """Start position tracking in a separate thread."""
        if self.position_thread and self.position_thread.is_alive():
            return
        
        self.position_thread = threading.Thread(target=self._update_position, daemon=True)
        self.position_thread.start()
    
    def _stop_position_tracking(self):
        """Stop position tracking."""
        if self.position_thread:
            self.position_thread = None
    
    def _send_event(self, event_type, data):
        """
        Send an event to all registered listeners.
        
        Args:
            event_type (str): Type of event (e.g., 'song_finished', 'song_starting')
            data (dict): Event data
        """
        if not hasattr(self, 'event_listeners'):
            return
            
        event_message = json.dumps({
            "type": "event",
            "event": event_type,
            "data": data,
            "timestamp": time.time()
        }) + "\n"
        
        # Send to all connected listeners
        print(f"DEBUG: Sending event '{event_type}' to {len(self.event_listeners)} listeners")
        dead_listeners = []
        for listener in self.event_listeners:
            try:
                listener.send(event_message.encode('utf-8'))
                print(f"DEBUG: Successfully sent event '{event_type}' to listener")
            except Exception as e:
                print(f"DEBUG: Failed to send event '{event_type}' to listener: {e}")
                # Mark dead connections for removal
                dead_listeners.append(listener)
        
        # Remove dead connections
        for dead in dead_listeners:
            if dead in self.event_listeners:
                self.event_listeners.remove(dead)
                try:
                    dead.close()
                except:
                    pass

    def _get_file_duration(self, filepath):
        """
        Get the duration of an audio file using the centralized metadata module.
        """
        try:
            import sys
            import os
            sys.path.append(os.path.dirname(os.path.dirname(__file__)))
            from . import metadata
            metadata_info = metadata.extract_metadata(filepath)
            if metadata_info and metadata_info.get('length', 0) > 0:
                duration = float(metadata_info['length'])
                print(f"DEBUG: Metadata module detected duration: {duration:.1f}s for {os.path.basename(filepath)}")
                return duration
        except Exception as e:
            print(f"DEBUG: Metadata module duration detection failed: {e}")
        return 0.0

def play_audio(filepath):
    """
    Simple playback function for command-line compatibility.
    
    Args:
        filepath (str): Path to the audio file to play.
        
    Returns:
        bool: True if playback completed successfully, False otherwise.
    """
    try:
        player = AudioPlayer()
        
        if not player.load_file(filepath):
            return False
        
        if not player.play():
            return False
        
        # Wait for playback to complete or user interruption
        try:
            while player.is_playing and not player.should_quit:
                time.sleep(0.1)
        except KeyboardInterrupt:
            print("\nPlayback interrupted by user.")
        finally:
            player.stop()
        
        return True
    except Exception as e:
        print(f"Error: {e}")
        return False


def send_daemon_command(command):
    """
    Send a command to a running daemon instance.
    
    Args:
        command (str): Command to send to daemon
        
    Returns:
        bool: True if command was sent successfully, False otherwise
    """
    # Find the most recent socket file
    temp_dir = tempfile.gettempdir()
    socket_files = []
    
    for filename in os.listdir(temp_dir):
        if filename.startswith("walrio_player_") and filename.endswith(".sock"):
            socket_path = os.path.join(temp_dir, filename)
            if os.path.exists(socket_path):
                socket_files.append((socket_path, os.path.getmtime(socket_path)))
    
    if not socket_files:
        print("Error: No running daemon instance found")
        return False
    
    # Use the most recently created socket
    socket_path = max(socket_files, key=lambda x: x[1])[0]
    
    try:
        # Connect to daemon socket
        client_socket = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        client_socket.connect(socket_path)
        
        # Send command
        client_socket.send(command.encode('utf-8'))
        
        # Receive response
        response = client_socket.recv(1024).decode('utf-8')
        print(response)
        
        client_socket.close()
        
        return response.startswith("OK:")
        
    except Exception as e:
        print(f"Error sending command to daemon: {e}")
        return False


def main():
    """
    Main function to handle command line arguments and play audio.
    
    Parses command-line arguments and initiates appropriate playback mode
    (simple, interactive, or daemon).
    
    Examples:
        Simple playback:
            python player.py /path/to/song.mp3
            
        Interactive mode with controls:
            python player.py --interactive /path/to/song.mp3
            
        Daemon mode for external control:
            python player.py --daemon /path/to/song.mp3
            
        Using test file:
            python player.py ../../testing_files/test.mp3
    """
    parser = argparse.ArgumentParser(
        description="Audio Player using GStreamer with full playback control",
        epilog="Examples:\n"
               "  python player.py /path/to/song.mp3              # Simple playback\n"
               "  python player.py --interactive /path/to/song.mp3 # Interactive mode\n"
               "  python player.py --daemon /path/to/song.mp3      # Daemon mode (for Electron)",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "filepath",
        nargs='?',
        help="Path to the audio file to play"
    )
    parser.add_argument(
        "--interactive", "-i",
        action="store_true",
        help="Run in interactive mode with playback controls"
    )
    parser.add_argument(
        "--daemon", "-d",
        action="store_true",
        help="Run in daemon mode (for external control)"
    )
    parser.add_argument(
        "--command", "-c",
        choices=['play', 'pause', 'stop', 'resume', 'status'],
        help="Send command to running player instance"
    )
    parser.add_argument(
        "--volume", "-v",
        type=float,
        help="Set volume (0.0 to 1.0)"
    )
    parser.add_argument(
        "--seek", "-s",
        type=float,
        help="Seek to position in seconds"
    )
    parser.add_argument(
        "--loop", "-l",
        default='none',
        help="Set loop mode: 'none', number (e.g. '3'), or 'infinite'"
    )

    args = parser.parse_args()
    
    try:
        player = AudioPlayer()
        
                # Handle different modes
        if args.command:
            # Send command to running daemon
            success = send_daemon_command(args.command)
            sys.exit(0 if success else 1)
            
        elif args.interactive:
            if args.filepath:
                if not player.load_file(args.filepath):
                    sys.exit(1)
            # Set loop mode if specified
            if args.loop:
                player.set_loop_mode(args.loop)
            player.run_interactive()
            
        elif args.daemon:
            # Daemon mode - load file and start daemon server
            if args.filepath:
                if not player.load_file(args.filepath):
                    sys.exit(1)
                # Set loop mode if specified
                if args.loop:
                    player.set_loop_mode(args.loop)
                # Auto-start playback in daemon mode
                player.play()
            
            # Run daemon server
            player.run_daemon()
            
        else:
            # Simple playback mode (backward compatibility)
            if not args.filepath:
                print("Error: filepath required for simple playback mode")
                parser.print_help()
                sys.exit(1)
            
            # Apply volume if specified
            if args.volume is not None:
                player.set_volume(args.volume)
            
            # Set loop mode if specified
            if args.loop:
                player.set_loop_mode(args.loop)
            
            success = play_audio(args.filepath)
            sys.exit(0 if success else 1)
        
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)

# run file
if __name__ == "__main__":
    main()