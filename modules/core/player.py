#!/usr/bin/env python3
"""
Audio Player using GStreamer Command-Line Tools
Copyright (c) 2025 TAPS OSS
Project: https://github.com/TAPSOSS/Walrio
Licensed under the BSD-3-Clause License (see LICENSE file for details)

A simple audio player that uses GStreamer command-line tools (gst-launch-1.0) 
for playback control.
"""

import sys
import os
import signal
import json
import argparse
import threading
import time
from pathlib import Path

import subprocess
import shlex

class AudioPlayer:
    """
    A GStreamer command-line based audio player with playback control.
    
    This class provides audio playback functionality using GStreamer's
    command-line tools (gst-launch-1.0) including play, pause, stop,
    volume control, and looping capabilities. No PyGObject bindings required.
    """
    
    def __init__(self):
        """
        Initialize the AudioPlayer with command-line GStreamer support.
        
        Raises:
            RuntimeError: If gst-launch-1.0 is not available.
        """
        # Check if gst-launch-1.0 is available
        try:
            subprocess.run(['gst-launch-1.0', '--version'], 
                         capture_output=True, check=True)
        except (subprocess.CalledProcessError, FileNotFoundError):
            raise RuntimeError("gst-launch-1.0 not found. Please install GStreamer.")
        
        # Player state
        self.process = None
        self.is_playing = False
        self.is_paused = False
        self.current_file = None
        self.duration = 0
        self.position = 0
        self.volume = 1.0
        self.should_quit = False
        self.loop_mode = 'none'  # 'none', number (e.g. '3'), or 'infinite'
        self.repeat_count = 0
        self.interactive_mode = False  # Track if we're in interactive mode
        self.start_time = None  # Track when playback started
        self.pause_time = None  # Track when playback was paused
        self.position_thread = None  # Thread for position tracking
        
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
    
    def _handle_looping(self):
        """Handle looping functionality by monitoring process completion."""
        if not self.process:
            return
            
        try:
            # Wait for process to complete
            self.process.wait()
            
            # Check if we should loop
            if self.should_quit or not self.is_playing:
                return
                
            should_loop = False
            if self.loop_mode == 'infinite':
                should_loop = True
            elif self.loop_mode.isdigit():
                if self.repeat_count < int(self.loop_mode):
                    should_loop = True
            
            if should_loop:
                self.repeat_count += 1
                print(f"Looping song (repeat #{self.repeat_count})")
                # Restart playback
                self.is_playing = False  # Reset state
                self.play()
            else:
                print(f"Finished looping after {self.repeat_count} repeats")
                self.is_playing = False
                if self.interactive_mode:
                    print("player> ", end="", flush=True)
                
        except Exception as e:
            print(f"Error in looping handler: {e}")
    
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
        
        # Store the file path for playback
        self.current_file = absolute_path
        
        # Reset position for new file
        self.position = 0
        self._stop_position_tracking()
        
        # Get the duration of the file
        self.duration = self._get_file_duration(absolute_path)
        
        print(f"Loaded: {filepath}")
        if self.duration > 0:
            print(f"Duration: {self.duration:.1f} seconds")
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
            return self.resume()
        
        # Stop any existing playback
        if self.process:
            self.stop()
        
        # Reset repeat count for new playback session
        self.repeat_count = 0
        
        try:
            # Build GStreamer pipeline command
            cmd = [
                'gst-launch-1.0',
                'filesrc', f'location={shlex.quote(self.current_file)}',
                '!', 'decodebin',
                '!', 'audioconvert',
                '!', 'audioresample',
                '!', 'volume', f'volume={self.volume}',
                '!', 'autoaudiosink'
            ]
            
            # Start process
            self.process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                stdin=subprocess.PIPE
            )
            
            self.is_playing = True
            self.is_paused = False
            print("Playback started")
            
            # Start position tracking
            self._start_position_tracking()
            
            # Handle looping in a separate thread
            if self.loop_mode != 'none':
                threading.Thread(target=self._handle_looping, daemon=True).start()
            
            return True
            
        except Exception as e:
            print(f"Error starting playback: {e}")
            return False
    
    def pause(self):
        """
        Pause playback.
        
        Returns:
            bool: True if paused successfully, False otherwise.
        """
        if not self.is_playing or not self.process:
            print("Player is not currently playing")
            return False
        
        try:
            # Send SIGSTOP to pause the process
            self.process.send_signal(signal.SIGSTOP)
            # Store pause time to maintain position accuracy
            self.pause_time = time.time()
            self.is_paused = True
            self.is_playing = False
            print("Playback paused")
            return True
        except Exception as e:
            print(f"Error pausing playback: {e}")
            return False
    
    def resume(self):
        """
        Resume paused playback.
        
        Returns:
            bool: True if resumed successfully, False otherwise.
        """
        if not self.is_paused or not self.process:
            print("Player is not currently paused")
            return False
        
        try:
            # Send SIGCONT to resume the process
            self.process.send_signal(signal.SIGCONT)
            # Adjust start time to account for pause duration
            if self.pause_time and self.start_time:
                pause_duration = time.time() - self.pause_time
                self.start_time += pause_duration
            self.pause_time = None
            self.is_paused = False
            self.is_playing = True
            print("Playback resumed")
            return True
        except Exception as e:
            print(f"Error resuming playback: {e}")
            return False
    
    def stop(self):
        """
        Stop playback.
        
        Returns:
            bool: True if stopped successfully, False otherwise.
        """
        if self.process:
            try:
                self.process.terminate()
                # Give it a moment to terminate gracefully
                try:
                    self.process.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    # Force kill if it doesn't terminate
                    self.process.kill()
                    self.process.wait()
            except Exception as e:
                print(f"Error stopping playback: {e}")
                return False
            finally:
                self.process = None
        
        self.is_playing = False
        self.is_paused = False
        self._stop_position_tracking()
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
        
        self.volume = volume
        print(f"Volume set to {volume:.2f}")
        # Note: Volume will be applied when next playback starts
        return True
    
    def get_volume(self):
        """
        Get current volume level.
        
        Returns:
            float: Current volume between 0.0 and 1.0.
        """
        return self.volume
    
    def seek(self, position_seconds):
        """
        Seek to a specific position in the audio.
        
        Args:
            position_seconds (float): Position to seek to in seconds.
            
        Returns:
            bool: True if seek successful, False otherwise.
        """
        if not self.current_file:
            print("Error: No file loaded")
            return False
        
        if position_seconds < 0:
            print("Error: Seek position cannot be negative")
            return False
        
        if self.duration > 0 and position_seconds > self.duration:
            print(f"Error: Seek position {position_seconds:.1f}s exceeds duration {self.duration:.1f}s")
            return False
        
        # Store current playing state
        was_playing = self.is_playing
        
        try:
            # Stop current playback if any
            if self.process:
                self.stop()
            
            # Use ffmpeg to create a temporary stream starting at the seek position
            # This is more reliable than trying to seek with gst-launch-1.0
            cmd = [
                'ffmpeg',
                '-ss', str(position_seconds),  # Seek to position
                '-i', self.current_file,       # Input file
                '-f', 'wav',                   # Output format
                '-af', f'volume={self.volume}', # Apply volume
                '-',                           # Output to stdout
            ]
            
            # Pipe ffmpeg output to gst-launch-1.0 for playback
            ffmpeg_process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            
            gst_cmd = [
                'gst-launch-1.0',
                'fdsrc', 'fd=0',
                '!', 'wavparse',
                '!', 'audioconvert',
                '!', 'audioresample', 
                '!', 'autoaudiosink'
            ]
            
            self.process = subprocess.Popen(
                gst_cmd,
                stdin=ffmpeg_process.stdout,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            
            # Close the ffmpeg stdout in the parent process
            ffmpeg_process.stdout.close()
            
            # Update our position tracking
            self.position = position_seconds
            
            if was_playing:
                self.is_playing = True
                self.is_paused = False
                # Adjust start time to account for the seek position
                self.start_time = time.time() - position_seconds
                
                # Start position tracking
                if self.position_thread is None or not self.position_thread.is_alive():
                    self.position_thread = threading.Thread(target=self._update_position, daemon=True)
                    self.position_thread.start()
                
                print(f"Seeked to {position_seconds:.1f} seconds and resumed playback")
            else:
                self.is_playing = False
                self.is_paused = True
                # Pause the process immediately after seeking
                time.sleep(0.1)
                self.process.send_signal(signal.SIGSTOP)
                print(f"Seeked to {position_seconds:.1f} seconds")
            
            return True
            
        except Exception as e:
            print(f"Error seeking to {position_seconds} seconds: {e}")
            return False
    
    def get_position(self):
        """
        Get current playback position.
        
        Returns:
            float: Current position in seconds.
        """
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
    
    def _update_position(self):
        """Update position tracking while playing."""
        while self.is_playing and not self.should_quit:
            if self.start_time and not self.is_paused:
                elapsed = time.time() - self.start_time
                self.position = elapsed
            time.sleep(0.1)  # Update every 100ms
    
    def _start_position_tracking(self):
        """Start position tracking in a separate thread."""
        if self.position_thread and self.position_thread.is_alive():
            return
        
        self.start_time = time.time()
        self.position_thread = threading.Thread(target=self._update_position, daemon=True)
        self.position_thread.start()
    
    def _stop_position_tracking(self):
        """Stop position tracking."""
        self.start_time = None
        self.pause_time = None
        if self.position_thread:
            self.position_thread = None

    def _get_file_duration(self, filepath):
        """
        Get the duration of an audio file using ffprobe.
        
        Args:
            filepath (str): Path to the audio file.
            
        Returns:
            float: Duration in seconds, or 0 if unable to determine.
        """
        try:
            # Use ffprobe to get duration
            cmd = [
                'ffprobe', 
                '-v', 'quiet',
                '-show_entries', 'format=duration',
                '-of', 'csv=p=0',
                filepath
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
            if result.returncode == 0 and result.stdout.strip():
                duration = float(result.stdout.strip())
                return duration
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired, ValueError, FileNotFoundError):
            # Fallback: try using gst-discoverer-1.0 if ffprobe fails
            try:
                cmd = [
                    'gst-discoverer-1.0',
                    '-v',
                    filepath
                ]
                
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
                if result.returncode == 0:
                    # Parse duration from gst-discoverer output
                    for line in result.stdout.split('\n'):
                        if 'Duration:' in line:
                            # Format is usually "Duration: 0:03:45.123456789"
                            duration_str = line.split('Duration:')[1].strip()
                            # Convert time format to seconds
                            time_parts = duration_str.split(':')
                            if len(time_parts) >= 3:
                                hours = float(time_parts[0])
                                minutes = float(time_parts[1])
                                seconds = float(time_parts[2])
                                total_seconds = hours * 3600 + minutes * 60 + seconds
                                return total_seconds
            except (subprocess.CalledProcessError, subprocess.TimeoutExpired, ValueError, FileNotFoundError):
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
            
            # Wait for playback or user interruption
            try:
                while not player.should_quit:
                    time.sleep(0.1)
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