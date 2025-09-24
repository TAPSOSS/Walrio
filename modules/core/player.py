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

# GStreamer Python bindings
import gi
gi.require_version('Gst', '1.0')
from gi.repository import Gst, GLib

class AudioPlayer:
    """
    A GStreamer Python bindings based audio player with real-time control.
    
    This class provides audio playback functionality using GStreamer Python
    bindings for real-time volume control, seeking, and playback management.
    """
    
    def __init__(self):
        """
        Initialize the AudioPlayer with GStreamer Python bindings.
        
        Raises:
            RuntimeError: If GStreamer initialization fails.
        """
        # Initialize GStreamer
        Gst.init(None)
        
        # Create pipeline elements
        self.pipeline = None
        self.source = None
        self.decodebin = None
        self.volume = None
        self.audioconvert = None
        self.audioresample = None
        self.audiosink = None
        
        # Player state
        self.is_playing = False
        self.is_paused = False
        self.current_file = None
        self.duration = 0
        self.position = 0
        self.volume_value = 1.0
        self.should_quit = False
        self.loop_mode = 'none'  # 'none', number (e.g. '3'), or 'infinite'
        self.repeat_count = 0
        self.interactive_mode = False  # Track if we're in interactive mode
        
        # Event notification system for daemon mode
        self.event_listeners = []  # List of sockets to send events to
        
        # GLib main loop for handling messages
        self.loop = GLib.MainLoop()
        self.loop_thread = None
        
        # Position tracking
        self.position_thread = None
        
        # Setup signal handlers
        signal.signal(signal.SIGINT, self.signal_handler)
        signal.signal(signal.SIGTERM, self.signal_handler)
    
    def signal_handler(self, signum, frame):
        """
        Handle termination signals gracefully.
        
        Args:
            signum (int): Signal number received.
            frame: Current stack frame (unused).
        """
        print(f"\nReceived signal {signum}, stopping playback...")
        self.stop()
        self.should_quit = True
        if self.loop.is_running():
            self.loop.quit()
    
    def _create_pipeline(self):
        """Create and configure the GStreamer pipeline."""
        # Create pipeline
        self.pipeline = Gst.Pipeline.new("audio-player")
        
        # Create elements
        self.source = Gst.ElementFactory.make("filesrc", "source")
        self.decodebin = Gst.ElementFactory.make("decodebin", "decoder")
        self.volume = Gst.ElementFactory.make("volume", "volume")
        self.audioconvert = Gst.ElementFactory.make("audioconvert", "convert")
        self.audioresample = Gst.ElementFactory.make("audioresample", "resample")
        self.audiosink = Gst.ElementFactory.make("autoaudiosink", "sink")
        
        if not all([self.source, self.decodebin, self.volume, self.audioconvert, 
                   self.audioresample, self.audiosink]):
            raise RuntimeError("Failed to create GStreamer elements")
        
        # Add elements to pipeline
        self.pipeline.add(self.source)
        self.pipeline.add(self.decodebin)
        self.pipeline.add(self.volume)
        self.pipeline.add(self.audioconvert)
        self.pipeline.add(self.audioresample)
        self.pipeline.add(self.audiosink)
        
        # Link static elements
        self.source.link(self.decodebin)
        self.volume.link(self.audioconvert)
        self.audioconvert.link(self.audioresample)
        self.audioresample.link(self.audiosink)
        
        # Connect dynamic pad for decodebin
        self.decodebin.connect("pad-added", self._on_pad_added)
        
        # Set up message bus
        bus = self.pipeline.get_bus()
        bus.add_signal_watch()
        bus.connect("message", self._on_bus_message)
    
    def _on_pad_added(self, decodebin, pad):
        """
        Handle dynamic pad addition from decodebin.
        
        Args:
            decodebin: The GStreamer decodebin element that added the pad.
            pad: The newly added pad from decodebin.
        """
        caps = pad.query_caps(None)
        structure = caps.get_structure(0)
        
        if structure and structure.get_name().startswith("audio/"):
            sink_pad = self.volume.get_static_pad("sink")
            if not sink_pad.is_linked():
                pad.link(sink_pad)
    
    def _on_bus_message(self, bus, message):
        """
        Handle GStreamer bus messages.
        
        Args:
            bus: The GStreamer bus that sent the message.
            message: The GStreamer message to process.
        """
        if message.type == Gst.MessageType.EOS:
            # End of stream - handle looping
            self._handle_eos()
        elif message.type == Gst.MessageType.ERROR:
            error, debug = message.parse_error()
            print(f"GStreamer Error: {error}, Debug: {debug}")
            self.stop()
        elif message.type == Gst.MessageType.STATE_CHANGED:
            if message.src == self.pipeline:
                old_state, new_state, pending_state = message.parse_state_changed()
                if new_state == Gst.State.PLAYING:
                    self.is_playing = True
                    self.is_paused = False
                elif new_state == Gst.State.PAUSED:
                    self.is_paused = True
    
    def _handle_eos(self):
        """Handle end of stream for looping."""
        if self.should_quit:
            return
        
        # Send song finished event to listeners
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
    
    def _handle_looping(self):
        """Handle looping functionality - now handled by EOS message."""
        # This method is kept for compatibility but functionality moved to _handle_eos
        pass
    
    def load_file(self, filepath):
        """
        Load an audio file for playback.
        
        Args:
            filepath (str): Path to the audio file.
            
        Returns:
            bool: True if file loaded successfully, False otherwise.
        """
        absolute_path = os.path.abspath(filepath)
        
        # Check if file exists
        if not os.path.exists(absolute_path):
            print(f"Error: File '{filepath}' not found.")
            return False
        
        # Check that it's a file and not directory
        if not os.path.isfile(absolute_path):
            print(f"Error: '{filepath}' is not a file.")
            return False
        
        # Stop any existing playback
        if self.pipeline:
            self.stop()
        
        # Store the file path for playback
        self.current_file = absolute_path
        
        # Reset position for new file
        self.position = 0
        
        # Create new pipeline
        self._create_pipeline()
        
        # Set file source
        self.source.set_property("location", absolute_path)
        
        # Get the duration of the file
        self.duration = self._get_file_duration(absolute_path)
        
        print(f"Loaded: {filepath}")
        if self.duration > 0:
            print(f"Duration: {self.duration:.1f} seconds")
        return True
    
    def play(self, seek_position=None):
        """
        Start or resume playback.
        
        Args:
            seek_position (float, optional): Position in seconds to start playback from
        
        Returns:
            bool: True if playback started successfully, False otherwise.
        """
        if not self.current_file:
            print("Error: No file loaded")
            return False
        
        if not self.pipeline:
            if not self.load_file(self.current_file):
                return False
        
        # Start GLib main loop in separate thread if not running
        if not self.loop_thread or not self.loop_thread.is_alive():
            self.loop_thread = threading.Thread(target=self._run_loop, daemon=True)
            self.loop_thread.start()
        
        # Set volume
        self.volume.set_property("volume", self.volume_value)
        
        # Seek to position if specified
        if seek_position is not None:
            self.pipeline.set_state(Gst.State.PAUSED)
            self.pipeline.get_state(Gst.CLOCK_TIME_NONE)
            self.seek(seek_position)
        
        # Start playback
        ret = self.pipeline.set_state(Gst.State.PLAYING)
        if ret == Gst.StateChangeReturn.FAILURE:
            print("Error: Failed to start playback")
            return False
        
        # Reset repeat count for new playback
        if seek_position is None or seek_position == 0:
            self.repeat_count = 0
        
        # Send song starting event
        self._send_event("song_starting", {
            "file": self.current_file,
            "duration": self.duration,
            "seek_position": seek_position or 0,
            "is_repeat": False
        })
        
        # Start position tracking
        self._start_position_tracking()
        
        print("Playback started")
        return True
    
    def _run_loop(self):
        """Run the GLib main loop."""
        self.loop.run()
    
    def pause(self):
        """
        Pause playback using GStreamer's pipeline state control.
        
        Returns:
            bool: True if paused successfully, False otherwise.
        """
        if not self.is_playing or not self.pipeline:
            print("Player is not currently playing")
            return False
        
        ret = self.pipeline.set_state(Gst.State.PAUSED)
        if ret == Gst.StateChangeReturn.FAILURE:
            print("Error: Failed to pause playback")
            return False
        
        print("Playback paused")
        return True
    
    def resume(self):
        """
        Resume paused playback.
        
        Returns:
            bool: True if resumed successfully, False otherwise.
        """
        if not self.is_paused or not self.pipeline:
            print("Player is not currently paused")
            return False
        
        ret = self.pipeline.set_state(Gst.State.PLAYING)
        if ret == Gst.StateChangeReturn.FAILURE:
            print("Error: Failed to resume playback")
            return False
        
        print("Playback resumed")
        return True
    
    def stop(self):
        """
        Stop playback.
        
        Returns:
            bool: True if stopped successfully, False otherwise.
        """
        if self.pipeline:
            self.pipeline.set_state(Gst.State.NULL)
            self.pipeline = None
        
        self.is_playing = False
        self.is_paused = False
        self._stop_position_tracking()
        
        print("Playback stopped")
        return True
    
    def set_volume(self, volume):
        """
        Set playback volume in real-time.
        
        Args:
            volume (float): Volume level between 0.0 and 1.0.
            
        Returns:
            bool: True if volume set successfully, False otherwise.
        """
        if volume < 0.0 or volume > 1.0:
            print("Error: Volume must be between 0.0 and 1.0")
            return False
        
        self.volume_value = volume
        
        # Apply volume immediately to the GStreamer pipeline
        if self.volume and self.pipeline:
            self.volume.set_property("volume", volume)
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
        Seek to a specific position in the audio using GStreamer.
        
        Args:
            position_seconds (float): Position to seek to in seconds.
            
        Returns:
            bool: True if seek successful, False otherwise.
        """
        if not self.current_file:
            print("Error: No file loaded")
            return False

        # Convert to float and validate input
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
            print("Error: No pipeline available for seeking")
            return False
        
        try:
            # Ensure position_seconds is within safe bounds
            position_seconds = max(0.0, min(float(position_seconds), 86400.0))  # Cap at 24 hours
            
            # Convert position to nanoseconds for GStreamer
            GST_SECOND = 1000000000
            position_ns = int(position_seconds * GST_SECOND)
            
            # Ensure the nanosecond value is within acceptable range
            if position_ns < 0:
                position_ns = 0
            
            # Use simpler seek approach that avoids GStreamer constant issues
            result = self.pipeline.seek_simple(
                Gst.Format.TIME,
                Gst.SeekFlags.FLUSH | Gst.SeekFlags.ACCURATE,
                position_ns
            )
            
            if result:
                self.position = position_seconds
                print(f"Seeked to {position_seconds:.1f} seconds")
                return True
            else:
                print(f"Failed to seek to {position_seconds:.1f} seconds")
                return False
                
        except Exception as e:
            print(f"Error seeking to {position_seconds} seconds: {e}")
            return False
    
    def get_position(self):
        """
        Get current playback position from GStreamer pipeline.
        
        Returns:
            float: Current position in seconds.
        """
        if self.pipeline and self.is_playing:
            try:
                # Query current position from pipeline
                success, position = self.pipeline.query_position(Gst.Format.TIME)
                if success:
                    # Convert from nanoseconds to seconds
                    self.position = position / Gst.SECOND
                    return self.position
            except Exception:
                pass
        
        return self.position
    
    def get_duration(self):
        """
        Get total duration of the current audio file.
        
        Returns:
            float: Total duration in seconds.
        """
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
        """Handle a single client connection."""
        try:
            while not self.should_quit:
                # Receive command
                data = conn.recv(1024).decode('utf-8').strip()
                if not data:
                    break
                
                # Check for event subscription
                if data.lower() == 'subscribe':
                    # Add to event listeners
                    self.event_listeners.append(conn)
                    conn.send(b"OK: Subscribed to events\n")
                    # Keep connection open for events
                    continue
                
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
            parts = command.strip().lower().split()
            if not parts:
                return "ERROR: Empty command"
            
            cmd = parts[0]
            
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
        """Update position tracking using GStreamer pipeline queries."""
        while self.is_playing and not self.should_quit:
            if self.pipeline and not self.is_paused:
                # Query position from GStreamer pipeline
                self.get_position()
            time.sleep(0.1)  # Update every 100ms
    
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
        dead_listeners = []
        for listener in self.event_listeners:
            try:
                listener.send(event_message.encode('utf-8'))
            except Exception:
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
        Get the duration of an audio file using GStreamer discoverer.
        
        Args:
            filepath (str): Path to the audio file.
            
        Returns:
            float: Duration in seconds, or 0 if unable to determine.
        """
        try:
            # Create a temporary pipeline to discover duration
            uri = f"file://{os.path.abspath(filepath)}"
            discoverer = Gst.PbUtilsDiscoverer.new(10 * Gst.SECOND)
            
            try:
                info = discoverer.discover_uri(uri)
                duration = info.get_duration()
                if duration != Gst.CLOCK_TIME_NONE:
                    return duration / Gst.SECOND
            except Exception as e:
                print(f"Error discovering duration: {e}")
                
        except Exception:
            pass
        
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