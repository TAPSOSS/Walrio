#!/usr/bin/env python3
"""
play your audio files
"""

import sys
import os
import json
import argparse
import threading
import time
import socket
import tempfile

import gi
gi.require_version('Gst', '1.0')
from gi.repository import Gst, GLib


def _init_gstreamer():
    """Initialize GStreamer if not already initialized."""
    if not Gst.is_initialized():
        Gst.init(None)


class AudioPlayer:
    """GStreamer-based audio player with real-time control."""
    
    def __init__(self, debug=False):
        _init_gstreamer()
        self.debug = debug
        self.pipeline = None
        self.bus = None
        self.bus_watch_thread = None
        self.current_file = None
        self.is_playing = False
        self.is_paused = False
        self.is_finished = False
        self.duration = 0
        self.volume_value = 1.0
        self.loop_mode = 'none'
        self.repeat_count = 0
        self.should_quit = False
        self.interactive_mode = False
        self.event_listeners = []
    
    def _log(self, message):
        """Log debug messages if debug mode is enabled."""
        if self.debug:
            print(f"DEBUG: {message}")
    
    def _bus_watch_loop(self):
        """Poll the bus for messages in a background thread."""
        while not self.should_quit and self.pipeline:
            if self.bus:
                # Poll for messages with 100ms timeout
                message = self.bus.timed_pop(100000000)  # 100ms in nanoseconds
                if message:
                    self._process_bus_message(message)
            else:
                time.sleep(0.1)
    
    def _process_bus_message(self, message):
        """Process a GStreamer bus message."""
        msg_type = message.type
        
        if msg_type == Gst.MessageType.EOS:
            self._handle_eos()
        elif msg_type == Gst.MessageType.ERROR:
            err, debug_info = message.parse_error()
            print(f"Error: {err.message}")
            self._log(f"Debug info: {debug_info}")
            self.stop()
        elif msg_type == Gst.MessageType.STATE_CHANGED:
            if message.src == self.pipeline:
                old_state, new_state, pending_state = message.parse_state_changed()
                self._log(f"State changed: {old_state.value_nick} -> {new_state.value_nick}")
    
    def _handle_eos(self):
        """Handle end of stream for looping."""
        if self.should_quit or self.get_position() < 1.0:
            return
        
        self._send_event("song_finished", {
            "file": self.current_file,
            "repeat_count": self.repeat_count,
            "loop_mode": self.loop_mode
        })
        
        should_loop = (
            self.loop_mode == 'infinite' or
            (self.loop_mode.isdigit() and self.repeat_count < int(self.loop_mode))
        )
        
        if should_loop:
            self.repeat_count += 1
            self._log(f"Looping song (repeat #{self.repeat_count})")
            self._send_event("song_starting", {
                "file": self.current_file,
                "repeat_count": self.repeat_count,
                "is_repeat": True
            })
            self.seek(0.0)
        else:
            self._log(f"Finished looping after {self.repeat_count} repeats")
            self._send_event("playback_complete", {
                "file": self.current_file,
                "total_repeats": self.repeat_count
            })
            # Mark as finished but don't stop the pipeline yet (allows position queries)
            self.is_playing = False
            self.is_finished = True
            print("Playback finished")
            if self.interactive_mode:
                print("player> ", end="", flush=True)
    
    def load_file(self, filepath):
        """Load an audio file for playback."""
        absolute_path = os.path.abspath(filepath)
        if not os.path.isfile(absolute_path):
            print(f"Error: File '{filepath}' not found or is not a file.")
            return False
        
        if self.pipeline:
            self.stop()
        
        self.current_file = absolute_path
        self.pipeline = Gst.ElementFactory.make("playbin", None)
        
        if not self.pipeline:
            print("ERROR: Failed to create playbin element!")
            return False
        
        self.pipeline.set_property("uri", f"file://{absolute_path}")
        self.pipeline.set_property("volume", self.volume_value)
        
        # Setup bus message handling with polling thread
        self.bus = self.pipeline.get_bus()
        if not self.bus_watch_thread or not self.bus_watch_thread.is_alive():
            self.bus_watch_thread = threading.Thread(target=self._bus_watch_loop, daemon=True)
            self.bus_watch_thread.start()
        
        self.duration = self._get_file_duration(absolute_path)
        print(f"Loaded: {filepath}")
        if self.duration > 0:
            print(f"Duration: {self.duration:.1f} seconds")
        
        return True
    
    def play(self, seek_position=None):
        """Start or resume playback."""
        if not self.current_file:
            print("Error: No file loaded")
            return False
        
        # If song finished, seek to start before playing again
        if self.is_finished:
            if not self.pipeline:
                # Pipeline was destroyed, need to reload
                if not self.load_file(self.current_file):
                    return False
            self.seek(0.0)
            self.is_finished = False
            self.repeat_count = 0
        
        if not self.pipeline and not self.load_file(self.current_file):
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
        
        print("Playback started")
        return True
    
    def pause(self):
        """Pause playback."""
        if not self.is_playing or not self.pipeline:
            print("Player is not currently playing")
            return False
        
        self.pipeline.set_state(Gst.State.PAUSED)
        self.is_playing = False
        self.is_paused = True
        print("Playback paused")
        return True
    
    def resume(self):
        """Resume paused playback."""
        if not self.is_paused or not self.pipeline:
            print("Player is not currently paused")
            return False
        
        self.pipeline.set_state(Gst.State.PLAYING)
        self.is_playing = True
        self.is_paused = False
        print("Playback resumed")
        return True
    
    def stop(self):
        """Stop playback."""
        if self.pipeline:
            self.pipeline.set_state(Gst.State.NULL)
            self.pipeline = None
            self.bus = None
        
        self.is_playing = False
        self.is_paused = False
        self.is_finished = False
        print("Playback stopped")
        return True
    
    def set_volume(self, volume):
        """Set playback volume in real-time."""
        if not 0.0 <= volume <= 1.0:
            print("Error: Volume must be between 0.0 and 1.0")
            return False
        
        self.volume_value = volume
        if self.pipeline:
            self.pipeline.set_property("volume", volume)
        
        print(f"Volume set to {volume:.2f}")
        return True
    
    def get_volume(self):
        """Get current volume level."""
        return self.volume_value
    
    def seek(self, position_seconds):
        """Seek to a specific position in the audio."""
        if not self.current_file:
            print("Error: No file loaded")
            return False
        
        try:
            position_seconds = float(position_seconds)
        except (ValueError, TypeError):
            print(f"Error: Invalid seek position: {position_seconds}")
            return False
        
        if position_seconds < 0 or (self.duration > 0 and position_seconds > self.duration):
            print(f"Error: Seek position out of range (0-{self.duration:.1f}s)")
            return False
        
        if not self.pipeline:
            print("Error: No pipeline available for seeking")
            return False
        
        seek_event = Gst.Event.new_seek(
            1.0, Gst.Format.TIME,
            Gst.SeekFlags.FLUSH | Gst.SeekFlags.KEY_UNIT,
            Gst.SeekType.SET, int(position_seconds * Gst.SECOND),
            Gst.SeekType.NONE, -1
        )
        
        if self.pipeline.send_event(seek_event):
            print(f"Seeked to {position_seconds:.1f} seconds")
            return True
        
        print(f"Error seeking to {position_seconds} seconds")
        return False
    
    def get_position(self):
        """Get current playback position in seconds."""
        if self.pipeline:
            success, position = self.pipeline.query_position(Gst.Format.TIME)
            if success:
                return position / Gst.SECOND
        return 0.0
    
    def get_duration(self):
        """Get total duration of the current audio file."""
        if self.pipeline:
            success, duration = self.pipeline.query_duration(Gst.Format.TIME)
            if success and duration > 0:
                self.duration = duration / Gst.SECOND
        return self.duration
    
    def set_loop_mode(self, mode):
        """Set loop mode for playback."""
        if mode not in ['none', 'infinite'] and not (mode.isdigit() and int(mode) > 0):
            print("Error: Loop mode must be 'none', 'infinite', or a positive number")
            return False
        
        self.loop_mode = mode
        
        mode_desc = {
            'none': 'Off',
            'infinite': 'Infinite repeats'
        }.get(mode, f'Repeat {mode} times')
        
        print(f"Loop mode: {mode_desc}")
        return True
    
    def get_loop_mode(self):
        """Get current loop mode."""
        return self.loop_mode
    
    def get_repeat_count(self):
        """Get number of times the current song has repeated."""
        return self.repeat_count
    
    def get_state(self):
        """Get current player state information."""
        return {
            "is_playing": self.is_playing,
            "is_paused": self.is_paused,
            "is_finished": self.is_finished,
            "current_file": self.current_file,
            "position": self.get_position(),
            "duration": self.get_duration(),
            "volume": self.get_volume(),
            "loop_mode": self.loop_mode,
            "repeat_count": self.repeat_count
        }
    
    def run_interactive(self):
        """Run the player in interactive mode with command input."""
        self.interactive_mode = True
        print("\nInteractive Audio Player")
        print("Commands:")
        print("  play/p    - Start/resume playback")
        print("  pause/ps  - Pause playback")
        print("  stop/s    - Stop playback")
        print("  volume/v <0.0-1.0> - Set volume")
        print("  seek/sk <seconds>   - Seek to position")
        print("  loop/l <none|number|infinite> - Set loop mode")
        print("  status/st - Show current status")
        print("  quit/q    - Quit player")
        print()
        
        self._handle_interactive_input()
    
    def _handle_interactive_input(self):
        """Handle user input in interactive mode."""
        command_map = {
            'play': lambda: self.resume() if self.is_paused else self.play(),
            'p': lambda: self.resume() if self.is_paused else self.play(),
            'pause': self.pause,
            'ps': self.pause,
            'stop': self.stop,
            's': self.stop,
            'status': self._print_status,
            'st': self._print_status,
        }
        
        while not self.should_quit:
            try:
                cmd_input = input("player> ").strip()
                if not cmd_input:
                    continue
                
                parts = cmd_input.split()
                command = parts[0].lower()
                
                if command in ['quit', 'q']:
                    self.should_quit = True
                    self.stop()
                    break
                elif command in command_map:
                    command_map[command]()
                elif command in ['volume', 'v'] and len(parts) > 1:
                    try:
                        self.set_volume(float(parts[1]))
                    except ValueError:
                        print("Error: Invalid volume value")
                elif command in ['seek', 'sk'] and len(parts) > 1:
                    try:
                        self.seek(float(parts[1]))
                    except ValueError:
                        print("Error: Invalid seek position")
                elif command in ['loop', 'l'] and len(parts) > 1:
                    self.set_loop_mode(parts[1])
                else:
                    print("Unknown command. Type 'quit' to exit.")
                    
            except (EOFError, KeyboardInterrupt):
                print("\nExiting...")
                self.stop()
                break
            except Exception as e:
                print(f"Error: {e}")
    
    def _print_status(self):
        """Print current player status."""
        state = self.get_state()
        if state['is_finished']:
            status_str = 'Finished'
        elif state['is_playing']:
            status_str = 'Playing'
        elif state['is_paused']:
            status_str = 'Paused'
        else:
            status_str = 'Stopped'
        
        print(f"File: {state['current_file'] or 'None'}")
        print(f"Status: {status_str}")
        print(f"Position: {state['position']:.1f}s / {state['duration']:.1f}s")
        print(f"Volume: {state['volume']:.2f}")
        print(f"Loop mode: {state['loop_mode']}")
        
        if state['repeat_count'] > 0:
            if state['loop_mode'] == 'infinite':
                print(f"Repeat count: {state['repeat_count']} (infinite)")
            elif state['loop_mode'].isdigit():
                print(f"Repeat count: {state['repeat_count']}/{state['loop_mode']}")
    
    def run_daemon(self):
        """Run the player in daemon mode with socket-based command interface."""
        self.socket_path = os.path.join(tempfile.gettempdir(), f"walrio_player_{os.getpid()}.sock")
        
        if os.path.exists(self.socket_path):
            os.unlink(self.socket_path)
        
        self.daemon_socket = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.daemon_socket.bind(self.socket_path)
        self.daemon_socket.listen(5)
        
        print(f"Daemon mode started. Socket: {self.socket_path}")
        
        command_thread = threading.Thread(target=self._command_server, daemon=True)
        command_thread.start()
        
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
                self.daemon_socket.settimeout(0.5)
                try:
                    conn, _ = self.daemon_socket.accept()
                except socket.timeout:
                    continue
                
                threading.Thread(target=self._handle_connection, args=(conn,), daemon=True).start()
            except Exception as e:
                if not self.should_quit:
                    self._log(f"Error in command server: {e}")
                break
    
    def _handle_connection(self, conn):
        """Handle a single client connection."""
        is_subscription = False
        try:
            data = conn.recv(1024).decode('utf-8').strip()
            if not data:
                return
            
            if data.lower() == 'subscribe':
                is_subscription = True
                self.event_listeners.append(conn)
                conn.send(b"OK: Subscribed to events\n")
                while not self.should_quit:
                    time.sleep(0.1)
            else:
                response = self._process_daemon_command(data)
                conn.send(response.encode('utf-8'))
        except Exception as e:
            if not self.should_quit:
                self._log(f"Connection error: {e}")
        finally:
            if not is_subscription:
                if conn in self.event_listeners:
                    self.event_listeners.remove(conn)
                try:
                    conn.close()
                except:
                    pass
    
    def _process_daemon_command(self, command):
        """Process a daemon command and return response."""
        try:
            parts = command.strip().split()
            if not parts:
                return "ERROR: Empty command"
            
            cmd = parts[0].lower()
            
            commands = {
                'play': lambda: self.resume() if self.is_paused else self.play(),
                'p': lambda: self.resume() if self.is_paused else self.play(),
                'pause': self.pause,
                'ps': self.pause,
                'stop': self.stop,
                's': self.stop,
                'resume': self.resume,
                'r': self.resume,
            }
            
            if cmd in commands:
                result = commands[cmd]()
                return f"OK: {cmd.title()}" if result else f"ERROR: Failed to {cmd}"
            elif cmd == 'status':
                if self.is_finished:
                    status = 'Finished'
                elif self.is_playing:
                    status = 'Playing'
                elif self.is_paused:
                    status = 'Paused'
                else:
                    status = 'Stopped'
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
                return f"OK: {self.get_position():.3f}"
            elif cmd == 'loop' and len(parts) > 1:
                result = self.set_loop_mode(parts[1])
                return f"OK: Loop mode set to {parts[1]}" if result else "ERROR: Failed to set loop mode"
            elif cmd == 'load' and len(parts) > 1:
                filepath = ' '.join(parts[1:])
                self.stop()
                result = self.load_file(filepath)
                if result:
                    self._send_event("song_loaded", {"file": filepath})
                    return f"OK: Loaded {filepath}"
                return f"ERROR: Failed to load {filepath}"
            elif cmd == 'subscribe':
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
            self._log(f"Cleanup error: {e}")
    
    def _send_event(self, event_type, data):
        """Send an event to all registered listeners."""
        if not self.event_listeners:
            return
        
        event_message = json.dumps({
            "type": "event",
            "event": event_type,
            "data": data,
            "timestamp": time.time()
        }) + "\n"
        
        dead_listeners = []
        for listener in self.event_listeners:
            try:
                listener.send(event_message.encode('utf-8'))
            except Exception:
                dead_listeners.append(listener)
        
        for dead in dead_listeners:
            self.event_listeners.remove(dead)
            try:
                dead.close()
            except:
                pass
    
    def _get_file_duration(self, filepath):
        """Get the duration of an audio file using metadata module."""
        try:
            # Try importing from parent package
            from . import metadata
            metadata_info = metadata.extract_metadata(filepath)
            if metadata_info and metadata_info.get('length', 0) > 0:
                return float(metadata_info['length'])
        except (ImportError, AttributeError):
            try:
                # Fallback to non-remade version
                from . import metadata
                metadata_info = metadata.extract_metadata(filepath)
                if metadata_info and metadata_info.get('length', 0) > 0:
                    return float(metadata_info['length'])
            except:
                pass
        return 0.0


def play_audio(filepath, debug=False):
    """Simple playback function for command-line compatibility."""
    try:
        player = AudioPlayer(debug=debug)
        
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


def send_daemon_command(command):
    """Send a command to a running daemon instance."""
    temp_dir = tempfile.gettempdir()
    socket_files = [
        (os.path.join(temp_dir, f), os.path.getmtime(os.path.join(temp_dir, f)))
        for f in os.listdir(temp_dir)
        if f.startswith("walrio_player_") and f.endswith(".sock")
    ]
    
    if not socket_files:
        print("Error: No running daemon instance found")
        return False
    
    socket_path = max(socket_files, key=lambda x: x[1])[0]
    
    try:
        client_socket = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        client_socket.connect(socket_path)
        client_socket.send(command.encode('utf-8'))
        response = client_socket.recv(1024).decode('utf-8')
        print(response)
        client_socket.close()
        return response.startswith("OK:")
    except Exception as e:
        print(f"Error sending command to daemon: {e}")
        return False


def main():
    """Main function to handle command line arguments and play audio."""
    parser = argparse.ArgumentParser(
        description="Audio Player using GStreamer with full playback control",
        epilog="Examples:\n"
               "  player_remade.py song.mp3              # Simple playback\n"
               "  player_remade.py -i song.mp3           # Interactive mode\n"
               "  player_remade.py -d song.mp3           # Daemon mode",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("filepath", nargs='?', help="Path to the audio file to play")
    parser.add_argument("-i", "--interactive", action="store_true", help="Run in interactive mode")
    parser.add_argument("-d", "--daemon", action="store_true", help="Run in daemon mode")
    parser.add_argument("-c", "--command", choices=['play', 'pause', 'stop', 'resume', 'status'],
                       help="Send command to running daemon")
    parser.add_argument("-v", "--volume", type=float, help="Set volume (0.0 to 1.0)")
    parser.add_argument("-s", "--seek", type=float, help="Seek to position in seconds")
    parser.add_argument("-l", "--loop", default='none', help="Set loop mode: 'none', number, or 'infinite'")
    parser.add_argument("--debug", action="store_true", help="Enable debug output")
    
    args = parser.parse_args()
    
    try:
        if args.command:
            sys.exit(0 if send_daemon_command(args.command) else 1)
        
        player = AudioPlayer(debug=args.debug)
        
        if args.interactive:
            if args.filepath and not player.load_file(args.filepath):
                sys.exit(1)
            if args.loop:
                player.set_loop_mode(args.loop)
            player.run_interactive()
        elif args.daemon:
            if args.filepath:
                if not player.load_file(args.filepath):
                    sys.exit(1)
                if args.loop:
                    player.set_loop_mode(args.loop)
                player.play()
            player.run_daemon()
        else:
            if not args.filepath:
                print("Error: filepath required for simple playback mode")
                parser.print_help()
                sys.exit(1)
            
            if args.volume is not None:
                player.set_volume(args.volume)
            if args.loop:
                player.set_loop_mode(args.loop)
            
            sys.exit(0 if play_audio(args.filepath, debug=args.debug) else 1)
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()