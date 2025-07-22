#!/usr/bin/env python3
"""
Audio Player using GStreamer
Copyright (c) 2025 TAPS OSS
Project: https://github.com/TAPSOSS/Walrio
Licensed under the BSD-3-Clause License (see LICENSE file for details)

A simple audio player that uses GStreamer Python bindings for full playback control.
"""

import sys
import os
import signal
import json
import argparse
import threading
import time
from pathlib import Path

try:
    import gi
    gi.require_version('Gst', '1.0')
    gi.require_version('GLib', '2.0')
    from gi.repository import Gst, GLib
    GST_AVAILABLE = True
except ImportError:
    GST_AVAILABLE = False
    print("Warning: GStreamer Python bindings not available. Install with: pip install PyGObject")

class AudioPlayer:
    """
    A GStreamer-based audio player with full playback control.
    
    This class provides comprehensive audio playback functionality including
    play, pause, stop, seek, volume control, and looping capabilities.
    """
    
    def __init__(self):
        """
        Initialize the AudioPlayer with GStreamer components.
        
        Raises:
            RuntimeError: If GStreamer Python bindings are not available.
        """
        if not GST_AVAILABLE:
            raise RuntimeError("GStreamer Python bindings not available")
        
        # Initialize GStreamer
        Gst.init(None)
        
        # Create playbin element
        self.player = Gst.ElementFactory.make("playbin", "player")
        if not self.player:
            raise RuntimeError("Could not create playbin element")
        
        # Create bus to watch for messages
        self.bus = self.player.get_bus()
        self.bus.add_signal_watch()
        self.bus.connect("message", self.on_message)
        
        # Player state
        self.is_playing = False
        self.is_paused = False
        self.current_file = None
        self.duration = 0
        self.position = 0
        self.volume = 1.0
        self.loop = None
        self.should_quit = False
        self.loop_mode = 'none'  # 'none', number (e.g. '3'), or 'infinite'
        self.repeat_count = 0
        self.max_repeats = 0  # 0 means no limit (infinite)
        self.interactive_mode = False  # Track if we're in interactive mode
        
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
        if self.loop:
            self.loop.quit()
    
    def on_message(self, bus, message):
        """
        Handle GStreamer bus messages.
        
        Args:
            bus: GStreamer bus object.
            message: GStreamer message object.
        """
        t = message.type
        
        if t == Gst.MessageType.EOS:
            print("Playback finished")
            
            # Handle looping
            if self.loop_mode != 'none':
                # Check if we should continue looping
                should_loop = False
                if self.loop_mode == 'infinite':
                    should_loop = True
                elif self.loop_mode.isdigit():
                    if self.repeat_count < int(self.loop_mode):
                        should_loop = True
                
                if should_loop:
                    print(f"Looping song (repeat #{self.repeat_count + 1})")
                    self.repeat_count += 1
                    # Seek back to beginning and continue playing
                    if self.seek(0):
                        return  # Continue playing, don't stop
                else:
                    print(f"Finished looping after {self.repeat_count} repeats")
            
            # Reset position to beginning for next play
            self.seek(0)
            self.stop()
            # Only quit the loop if not in interactive mode
            if self.loop and not self.interactive_mode:
                self.loop.quit()
            elif self.interactive_mode:
                # Re-print prompt for user to know they can continue
                print("player> ", end="", flush=True)
        elif t == Gst.MessageType.ERROR:
            err, debug = message.parse_error()
            print(f"Error: {err}")
            if debug:
                print(f"Debug info: {debug}")
            self.stop()
            # Only quit the loop if not in interactive mode
            if self.loop and not self.interactive_mode:
                self.loop.quit()
        elif t == Gst.MessageType.STATE_CHANGED:
            if message.src == self.player:
                old_state, new_state, pending_state = message.parse_state_changed()
                if new_state == Gst.State.PLAYING:
                    self.is_playing = True
                    self.is_paused = False
                elif new_state == Gst.State.PAUSED:
                    self.is_playing = False
                    self.is_paused = True
                elif new_state == Gst.State.NULL:
                    self.is_playing = False
                    self.is_paused = False
    
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
        
        # Set the URI
        uri = f"file://{absolute_path}"
        self.player.set_property("uri", uri)
        self.current_file = absolute_path
        
        print(f"Loaded: {filepath}")
        return True
    
    def play(self):
        """
        Start or resume playback.
        
        Returns:
            bool: True if playback started successfully, False otherwise.
        """
        if not self.current_file:
            print("Error: No file loaded")
            return False
        
        # If we're paused, just resume
        if self.is_paused:
            ret = self.player.set_state(Gst.State.PLAYING)
            if ret == Gst.StateChangeReturn.FAILURE:
                print("Error: Unable to resume playback")
                return False
            print("Playback resumed")
            return True
        
        # Reset repeat count for new playback session (perpetual loop mode)
        self.repeat_count = 0
        
        # Otherwise start/restart playback
        ret = self.player.set_state(Gst.State.PLAYING)
        if ret == Gst.StateChangeReturn.FAILURE:
            print("Error: Unable to start playback")
            return False
        
        print("Playback started")
        return True
    
    def pause(self):
        """
        Pause playback.
        
        Returns:
            bool: True if paused successfully, False otherwise.
        """
        if not self.is_playing:
            print("Player is not currently playing")
            return False
        
        ret = self.player.set_state(Gst.State.PAUSED)
        if ret == Gst.StateChangeReturn.FAILURE:
            print("Error: Unable to pause playback")
            return False
        
        print("Playback paused")
        return True
    
    def resume(self):
        """
        Resume paused playback.
        
        Returns:
            bool: True if resumed successfully, False otherwise.
        """
        if not self.is_paused:
            print("Player is not currently paused")
            return False
        
        return self.play()
    
    def stop(self):
        """
        Stop playback.
        
        Returns:
            bool: True if stopped successfully, False otherwise.
        """
        ret = self.player.set_state(Gst.State.NULL)
        if ret == Gst.StateChangeReturn.FAILURE:
            print("Error: Unable to stop playback")
            return False
        
        self.is_playing = False
        self.is_paused = False
        return True
    
    def set_volume(self, volume):
        """
        Set playback volume.
        
        Args:
            volume (float): Volume level between 0.0 and 1.0.
            
        Returns:
            bool: True if volume set successfully, False otherwise.
        """
        if volume < 0.0 or volume > 1.0:
            print("Error: Volume must be between 0.0 and 1.0")
            return False
        
        self.player.set_property("volume", volume)
        self.volume = volume
        print(f"Volume set to {volume:.2f}")
        return True
    
    def get_volume(self):
        """
        Get current volume level.
        
        Returns:
            float: Current volume between 0.0 and 1.0.
        """
        return self.player.get_property("volume")
    
    def seek(self, position_seconds):
        """
        Seek to a specific position in the audio.
        
        Args:
            position_seconds (float): Position to seek to in seconds.
            
        Returns:
            bool: True if seek successful, False otherwise.
        """
        seek_time = position_seconds * Gst.SECOND
        ret = self.player.seek_simple(
            Gst.Format.TIME,
            Gst.SeekFlags.FLUSH | Gst.SeekFlags.KEY_UNIT,
            seek_time
        )
        if not ret:
            print(f"Error: Unable to seek to {position_seconds} seconds")
            return False
        
        print(f"Seeked to {position_seconds} seconds")
        return True
    
    def get_position(self):
        """
        Get current playback position.
        
        Returns:
            float: Current position in seconds.
        """
        ret, position = self.player.query_position(Gst.Format.TIME)
        if ret:
            return position / Gst.SECOND
        return 0
    
    def get_duration(self):
        """
        Get total duration of the current audio file.
        
        Returns:
            float: Total duration in seconds.
        """
        ret, duration = self.player.query_duration(Gst.Format.TIME)
        if ret:
            return duration / Gst.SECOND
        return 0
    
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
        
        # Create main loop
        self.loop = GLib.MainLoop()
        
        # Start input thread
        input_thread = threading.Thread(target=self.handle_input, daemon=True)
        input_thread.start()
        
        try:
            self.loop.run()
        except KeyboardInterrupt:
            pass
        finally:
            self.stop()
    
    def handle_input(self):
        """
        Handle user input in interactive mode.
        
        Processes user commands in a separate thread while
        audio playback continues in the main thread.
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
                    if self.loop:
                        self.loop.quit()
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
            except Exception as e:
                print(f"Error handling input: {e}")

def play_audio(filepath):
    """
    Simple playback function for command-line compatibility.
    
    Args:
        filepath (str): Path to the audio file to play.
        
    Returns:
        bool: True if playback completed successfully, False otherwise.
    """
    if not GST_AVAILABLE:
        print("Error: GStreamer Python bindings not available.")
        print("Install with: pip install PyGObject")
        return False
    
    try:
        player = AudioPlayer()
        
        if not player.load_file(filepath):
            return False
        
        if not player.play():
            return False
        
        # Create main loop for playback
        loop = GLib.MainLoop()
        player.loop = loop
        
        try:
            loop.run()
        except KeyboardInterrupt:
            print("\nPlayback interrupted by user.")
        finally:
            player.stop()
        
        return True
    except Exception as e:
        print(f"Error: {e}")
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
    
    if not GST_AVAILABLE:
        print("Error: GStreamer Python bindings not available.")
        print("Please install with one of:")
        print("  pip install PyGObject")
        print("  sudo apt install python3-gi python3-gi-cairo gir1.2-gst-1.0")
        print("  sudo dnf install python3-gobject gstreamer1-devel")
        sys.exit(1)
    
    try:
        player = AudioPlayer()
        
        # Handle different modes
        if args.interactive:
            if args.filepath:
                if not player.load_file(args.filepath):
                    sys.exit(1)
            # Set loop mode if specified
            if args.loop:
                player.set_loop_mode(args.loop)
            player.run_interactive()
        elif args.daemon:
            # Daemon mode - load file and wait for external commands
            if args.filepath:
                if not player.load_file(args.filepath):
                    sys.exit(1)
                # Set loop mode if specified
                if args.loop:
                    player.set_loop_mode(args.loop)
                player.play()
            
            # Create main loop and wait
            loop = GLib.MainLoop()
            player.loop = loop
            try:
                loop.run()
            except KeyboardInterrupt:
                pass
            finally:
                player.stop()
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