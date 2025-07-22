#!/usr/bin/env python3
"""
Audio Player using GStreamer

Copyright (c) 2025 TAPS OSS
Project: https://github.com/TAPSOSS/Walrio
Licensed under the BSD-3-Clause License (see LICENSE file for details)

A simple audio player that uses GStreamer Python bindings for full playback control.
Sample Usage: python player.py <filepath>
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
    def __init__(self):
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
        
        # Setup signal handlers
        signal.signal(signal.SIGINT, self.signal_handler)
        signal.signal(signal.SIGTERM, self.signal_handler)
    
    def signal_handler(self, signum, frame):
        """Handle termination signals"""
        print(f"\nReceived signal {signum}, stopping playback...")
        self.stop()
        self.should_quit = True
        if self.loop:
            self.loop.quit()
    
    def on_message(self, bus, message):
        """Handle GStreamer bus messages"""
        t = message.type
        
        if t == Gst.MessageType.EOS:
            print("End of stream reached")
            self.stop()
            if self.loop:
                self.loop.quit()
        elif t == Gst.MessageType.ERROR:
            err, debug = message.parse_error()
            print(f"Error: {err}")
            if debug:
                print(f"Debug info: {debug}")
            self.stop()
            if self.loop:
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
        """Load an audio file for playback"""
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
        """Start or resume playback"""
        if not self.current_file:
            print("Error: No file loaded")
            return False
        
        ret = self.player.set_state(Gst.State.PLAYING)
        if ret == Gst.StateChangeReturn.FAILURE:
            print("Error: Unable to start playback")
            return False
        
        print("Playback started")
        return True
    
    def pause(self):
        """Pause playback"""
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
        """Resume paused playback"""
        if not self.is_paused:
            print("Player is not currently paused")
            return False
        
        return self.play()
    
    def stop(self):
        """Stop playback"""
        ret = self.player.set_state(Gst.State.NULL)
        if ret == Gst.StateChangeReturn.FAILURE:
            print("Error: Unable to stop playback")
            return False
        
        self.is_playing = False
        self.is_paused = False
        print("Playback stopped")
        return True
    
    def set_volume(self, volume):
        """Set playback volume (0.0 to 1.0)"""
        if volume < 0.0 or volume > 1.0:
            print("Error: Volume must be between 0.0 and 1.0")
            return False
        
        self.player.set_property("volume", volume)
        self.volume = volume
        print(f"Volume set to {volume:.2f}")
        return True
    
    def get_volume(self):
        """Get current volume"""
        return self.player.get_property("volume")
    
    def seek(self, position_seconds):
        """Seek to a specific position in seconds"""
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
        """Get current playback position in seconds"""
        ret, position = self.player.query_position(Gst.Format.TIME)
        if ret:
            return position / Gst.SECOND
        return 0
    
    def get_duration(self):
        """Get total duration in seconds"""
        ret, duration = self.player.query_duration(Gst.Format.TIME)
        if ret:
            return duration / Gst.SECOND
        return 0
    
    def get_state(self):
        """Get current player state"""
        return {
            "is_playing": self.is_playing,
            "is_paused": self.is_paused,
            "current_file": self.current_file,
            "position": self.get_position(),
            "duration": self.get_duration(),
            "volume": self.get_volume()
        }
    
    def run_interactive(self):
        """Run in interactive mode with command input"""
        print("\nInteractive Audio Player")
        print("Commands:")
        print("  play/p    - Start/resume playback")
        print("  pause     - Pause playback")
        print("  stop/s    - Stop playback")
        print("  volume <0.0-1.0> - Set volume")
        print("  seek <seconds>   - Seek to position")
        print("  status    - Show current status")
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
        """Handle user input in interactive mode"""
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
                elif command == 'pause':
                    self.pause()
                elif command in ['stop', 's']:
                    self.stop()
                elif command == 'volume' and len(parts) > 1:
                    try:
                        vol = float(parts[1])
                        self.set_volume(vol)
                    except ValueError:
                        print("Error: Invalid volume value")
                elif command == 'seek' and len(parts) > 1:
                    try:
                        pos = float(parts[1])
                        self.seek(pos)
                    except ValueError:
                        print("Error: Invalid seek position")
                elif command == 'status':
                    state = self.get_state()
                    print(f"File: {state['current_file'] or 'None'}")
                    print(f"Status: {'Playing' if state['is_playing'] else 'Paused' if state['is_paused'] else 'Stopped'}")
                    print(f"Position: {state['position']:.1f}s / {state['duration']:.1f}s")
                    print(f"Volume: {state['volume']:.2f}")
                else:
                    print("Unknown command. Type 'quit' to exit.")
            except EOFError:
                break
            except Exception as e:
                print(f"Error handling input: {e}")

# Simple playback function for command-line compatibility
def play_audio(filepath):
    """Simple playback function for backward compatibility"""
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

# main function to handle command line arguments and play audio
def main():
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
            player.run_interactive()
        elif args.daemon:
            # Daemon mode - load file and wait for external commands
            if args.filepath:
                if not player.load_file(args.filepath):
                    sys.exit(1)
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
            
            success = play_audio(args.filepath)
            sys.exit(0 if success else 1)
        
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)

# run file
if __name__ == "__main__":
    main()