#!/usr/bin/env python3

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

# Lazy import of Gst/GLib
Gst = None
GLib = None

def _ensure_gstreamer_imported():
    """Import GStreamer modules if not already imported (allows runtime hooks to run first)."""
    global Gst, GLib
    if Gst is None:
        from gi.repository import Gst as _Gst, GLib as _GLib
        Gst = _Gst
        GLib = _GLib
        if not Gst.is_initialized():
            Gst.init(None)


class AudioPlayer:
    """
    GStreamer-based audio player with real-time control.
    """
    def __init__(self):
        _ensure_gstreamer_imported()
        self.pipeline = None
        self.bus = None
        self.current_file = None
        self.is_playing = False
        self.is_paused = False
        self.duration = 0
        self.volume_value = 1.0
        self.loop_mode = 'none'
        self.repeat_count = 0
        self.position_callback = None
        self.position_update_interval = 500
        self.position_timeout_id = None
        self.should_quit = False
        self.interactive_mode = False
        self.position = 0.0
        self.event_listeners = []
    
    def _start_position_updates(self):
        """Start sending position updates via callback."""
        pass
    
    def _stop_position_updates(self):
        """Stop sending position updates."""
        pass
    
    def _emit_position_update(self):
        """Emit position update via callback. Returns True to keep timeout active."""
        return False
    
    def _handle_eos(self):
        """Handle end of stream for looping."""
        pass
    
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
        
        self.current_file = absolute_path
        print(f"Loaded: {filepath}")
        return True
    
    def play(self, seek_position=None):
        """
        Start or resume playback.
        """
        if not self.current_file:
            print("Error: No file loaded")
            return False
        
        self.is_playing = True
        self.is_paused = False
        print("Playback started")
        return True
    
    def _run_loop(self):
        """Run the GLib main loop."""
        pass
    
    def pause(self):
        """
        Pause playback.
        """
        if not self.is_playing or not self.pipeline:
            print("Player is not currently playing")
            return False
        
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
        
        self.is_playing = True
        self.is_paused = False
        print("Playback resumed")
        return True
    
    def stop(self):
        """
        Stop playback.
        """
        self.is_playing = False
        self.is_paused = False
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
        print(f"Volume set to {volume:.2f}")
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
        
        print(f"Seeked to {position_seconds:.1f} seconds")
        return True
    
    def get_position(self):
        """
        Get current playback position from VLC player.
        """
        return self.position
    
    def get_duration(self):
        """
        Get total duration of the current audio file.
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
        if mode != 'none' and mode != 'infinite' and not mode.isdigit():
            print("Error: Loop mode must be 'none', a number (e.g. '3'), or 'infinite'")
            return False
        
        if mode.isdigit() and int(mode) <= 0:
            print("Error: Loop count must be a positive number")
            return False
        
        self.loop_mode = mode
        
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
                        print(f"Repeat count: {state['repeat_count']}")
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
    
    def _update_position(self):
        """Update position tracking using VLC player queries."""
        while self.is_playing and not self.should_quit:
            time.sleep(0.1)
    
    def _start_position_tracking(self):
        """Start position tracking in a separate thread."""
        pass
    
    def _stop_position_tracking(self):
        """Stop position tracking."""
        pass

    def _get_file_duration(self, filepath):
        """
        Get the duration of an audio file using the centralized metadata module.
        """
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


def main():
    """
    Main function to handle command line arguments and play audio.
    
    Parses command-line arguments and initiates appropriate playback mode
    (simple or interactive).
    
    Examples:
        Simple playback:
            python player.py /path/to/song.mp3
            
        Interactive mode with controls:
            python player.py --interactive /path/to/song.mp3
    """
    parser = argparse.ArgumentParser(
        description="Audio Player using GStreamer with full playback control",
        epilog="Examples:\n"
               "  python player.py /path/to/song.mp3              # Simple playback\n"
               "  python player.py --interactive /path/to/song.mp3 # Interactive mode",
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
        
        if args.interactive:
            if args.filepath:
                if not player.load_file(args.filepath):
                    sys.exit(1)
            if args.loop:
                player.set_loop_mode(args.loop)
            player.run_interactive()
            
        else:
            if not args.filepath:
                print("Error: filepath required for simple playback mode")
                parser.print_help()
                sys.exit(1)
            
            if args.volume is not None:
                player.set_volume(args.volume)
            
            if args.loop:
                player.set_loop_mode(args.loop)
            
            success = play_audio(args.filepath)
            sys.exit(0 if success else 1)
        
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
