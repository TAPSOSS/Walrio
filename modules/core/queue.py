#!/usr/bin/env python3
"""
play and manage a song queue with shuffle, repeat, and more
"""

import sys
import os
import sqlite3
import argparse
import random
import hashlib
import time
from pathlib import Path
from enum import Enum
from .player import play_audio
from .playlist import load_m3u_playlist
from . import metadata

# Debug mode - set to False to disable debug logging for efficiency
DEBUG_MODE = False

def debug_log(message):
    """Print debug message only if DEBUG_MODE is enabled."""
    if DEBUG_MODE:
        print(f"[DEBUG] {message}")

class RepeatMode(Enum):
    """Repeat modes for audio playback"""
    OFF = "off"
    TRACK = "track"
    QUEUE = "queue"

class QueueManager:
    """Manages audio playback queue with shuffle, repeat, and history tracking."""
    
    def __init__(self, songs=None):
        """Initialize QueueManager with a list of songs."""
        self.songs = songs or []
        self.current_index = 0
        self.repeat_mode = RepeatMode.OFF
        self.shuffle = False
        self.playback_history = []  # Global history for universal previous
        self.forward_queue = []  # Predicted future songs for shuffle
        self.forward_history = []  # Songs to return to when hitting next after previous
    
    def set_repeat_mode(self, mode):
        """Set repeat mode: "off", "track", or "queue". Mode changes preserve forward queue."""
        if isinstance(mode, str):
            mode = RepeatMode(mode.lower())
        
        old_mode = self.repeat_mode
        self.repeat_mode = mode
        
        debug_log(f"set_repeat_mode(): Changed from {old_mode.value} to {mode.value}, "
                 f"current: {self.current_index}, forward_queue: {len(self.forward_queue)} items")
        
        print(f"Repeat mode set to: {mode.value}")
    
    def set_shuffle_mode(self, enabled):
        """Set shuffle mode on/off. Mode changes preserve forward queue."""
        old_shuffle = self.shuffle
        self.shuffle = enabled
        effective = self.is_shuffle_effective()
        
        debug_log(f"set_shuffle_mode(): Changed from {old_shuffle} to {enabled}, "
                 f"effective: {effective}, forward_queue: {len(self.forward_queue)} items")
        
        print(f"Shuffle mode: {'ON' if enabled else 'OFF'}" + 
              (f" (disabled by repeat mode)" if enabled and not effective else ""))
    
    def is_shuffle_effective(self):
        """Check if shuffle is actively being used (only with repeat OFF)."""
        return self.shuffle and self.repeat_mode == RepeatMode.OFF
    
    def current_song(self):
        """Get the currently playing song."""
        if 0 <= self.current_index < len(self.songs):
            return self.songs[self.current_index]
        return None
    
    def _get_next_shuffle_song(self):
        """Get next song in shuffle mode using forward queue for consistency."""
        # If we have a forward queue, use it
        if self.forward_queue:
            return self.forward_queue[0]
        
        # Generate new forward queue with remaining unplayed songs
        recent_history = self.playback_history[-len(self.songs):] if len(self.playback_history) >= len(self.songs) else self.playback_history
        unplayed = [i for i in range(len(self.songs)) 
                   if recent_history.count(i) == 0 and i != self.current_index]
        
        if unplayed:
            # Shuffle unplayed songs and store as forward queue
            random.shuffle(unplayed)
            self.forward_queue = unplayed
            debug_log(f"_get_next_shuffle_song(): Generated forward_queue with {len(unplayed)} unplayed songs")
            return self.forward_queue[0]
        else:
            # All songs played recently, generate new random sequence
            all_indices = [i for i in range(len(self.songs)) if i != self.current_index]
            random.shuffle(all_indices)
            self.forward_queue = all_indices
            debug_log(f"_get_next_shuffle_song(): All played, generated new forward_queue with {len(all_indices)} songs")
            return self.forward_queue[0] if self.forward_queue else self.current_index
    
    def has_songs(self):
        """Check if there are songs in the queue."""
        return len(self.songs) > 0
    
    def next_track(self):
        """
        Move to next track. Prioritizes forward history (from previous button) over normal progression.
        Always adds current song to global history for universal previous functionality.
        Returns True if moved successfully, False if at end.
        """
        if not self.has_songs():
            return False
        
        # Check for forward history first (from previous button usage)
        if self.forward_history:
            self.playback_history.append(self.current_index)
            self.current_index = self.forward_history.pop()
            debug_log(f"next_track(): Using forward history, going to {self.current_index}")
            return True
        
        # Add current to history (except track repeat)
        if self.repeat_mode != RepeatMode.TRACK:
            self.playback_history.append(self.current_index)
        
        # Handle track repeat
        if self.repeat_mode == RepeatMode.TRACK:
            return True  # Stay on same track
        
        # Handle queue repeat
        if self.repeat_mode == RepeatMode.QUEUE:
            self.current_index = (self.current_index + 1) % len(self.songs)
            debug_log(f"next_track(): Queue repeat, moved to {self.current_index}")
            return True
        
        # Handle shuffle
        if self.is_shuffle_effective():
            next_idx = self._get_next_shuffle_song()
            
            # Remove used song from forward queue
            if self.forward_queue and next_idx == self.forward_queue[0]:
                self.forward_queue.pop(0)
            
            self.current_index = next_idx
            debug_log(f"next_track(): Shuffle, moved to {self.current_index}, "
                     f"forward_queue remaining: {len(self.forward_queue)}")
            return True
        
        # Normal progression
        self.current_index += 1
        
        # Check if we reached the end
        if self.current_index >= len(self.songs):
            debug_log(f"next_track(): Reached end of queue")
            return False
        
        debug_log(f"next_track(): Normal progression to {self.current_index}")
        return True
    
    def next_track_skip_missing(self):
        """
        Move to next track, skipping unavailable songs. For auto-progression after song ends.
        Returns True if there's a next available track, False if queue ended.
        """
        if not self.has_songs():
            return False
        
        # Special case: If current song is missing and in track repeat, skip to next
        if self.repeat_mode == RepeatMode.TRACK:
            current_song = self.current_song()
            if current_song and current_song.get('file_missing', False):
                # Force next even in track repeat
                self.repeat_mode = RepeatMode.OFF
                result = self.next_track()
                self.repeat_mode = RepeatMode.TRACK
                return result
            return True  # Stay on current track
        
        # Try to find next available song
        max_attempts = len(self.songs)
        attempts = 0
        
        while attempts < max_attempts:
            if not self.next_track():
                return False
            
            song = self.current_song()
            if song:
                file_path = song.get('url', song.get('filepath', ''))
                if file_path.startswith('file://'):
                    file_path = file_path[7:]
                if os.path.exists(file_path):
                    debug_log(f"next_track_skip_missing(): Found available song at {self.current_index}")
                    return True
            attempts += 1
        
        debug_log(f"next_track_skip_missing(): No more available files in queue")
        return False
    
    def previous_track(self):
        """
        Move to previous track using global playback history.
        When going back, adds current song to forward history for next button.
        Returns True if moved successfully, False if at beginning.
        """
        if not self.has_songs():
            return False
        
        if self.repeat_mode == RepeatMode.TRACK:
            debug_log(f"previous_track(): In track repeat, staying at {self.current_index}")
            return False
        
        if self.playback_history:
            # Save current for forward history
            self.forward_history.append(self.current_index)
            self.current_index = self.playback_history.pop()
            debug_log(f"previous_track(): Moved to {self.current_index}, "
                     f"forward_history: {len(self.forward_history)} items")
            return True
        
        debug_log(f"previous_track(): No history available")
        return False
    
    def set_current_index(self, index):
        """
        Set current playback index. Manual song selection clears forward queue to resync predictions.
        History tracking ensures proper previous button functionality.
        """
        if 0 <= index < len(self.songs):
            # Save current to history
            if self.current_index != index:
                self.playback_history.append(self.current_index)
            
            self.current_index = index
            
            # Clear forward queue and forward history on manual selection
            self.forward_queue.clear()
            self.forward_history.clear()
            
            debug_log(f"set_current_index(): Set to {index}, cleared forward queue/history")
            return True
        return False
    
    def add_song(self, song):
        """Add a song to the queue."""
        self.songs.append(song)
        debug_log(f"add_song(): Added '{song.get('title', 'Unknown')}', total: {len(self.songs)}")
    
    def add_songs(self, songs):
        """Add multiple songs to the queue."""
        self.songs.extend(songs)
        self.playback_history.clear()
        debug_log(f"add_songs(): Added {len(songs)} songs, cleared history")
        print(f"Added {len(songs)} songs to queue")
    
    def remove_song(self, index):
        """Remove a song from the queue."""
        if 0 <= index < len(self.songs):
            removed = self.songs.pop(index)
            if self.current_index >= index:
                self.current_index = max(0, self.current_index - 1)
            debug_log(f"remove_song(): Removed song at {index}, current now: {self.current_index}")
            return True
        return False
    
    def shuffle_queue(self):
        """
        Shuffle the entire queue by randomly reordering all songs.
        This physically reorders the songs list and resets the current index.
        """
        if not self.songs:
            return False
        
        # Get current song before shuffle
        current_song = self.current_song()
        
        # Shuffle the songs list
        random.shuffle(self.songs)
        
        # Find new index of current song
        if current_song:
            for i, song in enumerate(self.songs):
                if song == current_song:
                    self.current_index = i
                    break
        else:
            self.current_index = 0
        
        debug_log(f"shuffle_queue(): Physically shuffled queue, current now at {self.current_index}")
        print("Queue shuffled - song order randomized")
        return True
    
    def play_random_song(self):
        """
        Jump to a completely random song in the queue.
        This doesn't reorder the queue, just changes the current playing position.
        """
        if not self.songs:
            return False
        
        # Select random index
        random_index = random.randint(0, len(self.songs) - 1)
        
        # Save current to history
        self.playback_history.append(self.current_index)
        self.current_index = random_index
        
        # Clear forward queue on manual jump
        self.forward_queue.clear()
        
        song = self.current_song()
        song_title = song.get('title', 'Unknown') if song else 'Unknown'
        debug_log(f"play_random_song(): Jumped to {random_index}")
        print(f"Jumped to random song: {song_title} (position {random_index + 1}/{len(self.songs)})")
        return True
    
    def clear_queue(self):
        """Clear the entire queue and reset all state."""
        self.songs.clear()
        self.current_index = 0
        self.playback_history.clear()
        self.forward_history.clear()
        self.forward_queue.clear()
        debug_log(f"clear_queue(): Queue cleared")
        print("Queue cleared")
    
    def handle_song_finished(self):
        """
        Handle when current song finishes playing. Auto-skips missing files during progression.
        Returns tuple: (should_continue: bool, next_song: dict or None)
        """
        current_song = self.current_song()
        if current_song:
            debug_log(f"handle_song_finished(): Finished '{current_song.get('title', 'Unknown')}'")
        
        # Use next_track_skip_missing to skip missing files during auto-progression
        if self.next_track_skip_missing():
            next_song = self.current_song()
            if next_song:
                debug_log(f"handle_song_finished(): Next song is '{next_song.get('title', 'Unknown')}'")
                return (True, next_song)
        
        debug_log(f"handle_song_finished(): No more songs to play")
        print("Queue finished - no more songs to play")
        return (False, None)

def connect_to_database(db_path):
    """Connect to the SQLite database and return connection."""
    if not os.path.exists(db_path):
        print(f"Error: Database not found: {db_path}")
        return None
    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        return conn
    except Exception as e:
        print(f"Error connecting to database: {e}")
        return None

def get_songs_from_database(conn, filters=None):
    """Get songs from database based on filters."""
    cursor = conn.cursor()
    query = "SELECT * FROM songs WHERE unavailable = 0"
    params = []
    
    if filters:
        if 'artist' in filters and filters['artist']:
            query += " AND artist LIKE ?"
            params.append(f"%{filters['artist']}%")
        if 'album' in filters and filters['album']:
            query += " AND album LIKE ?"
            params.append(f"%{filters['album']}%")
        if 'genre' in filters and filters['genre']:
            query += " AND genre LIKE ?"
            params.append(f"%{filters['genre']}%")
    
    query += " ORDER BY artist, album, disc, track"
    cursor.execute(query, params)
    return cursor.fetchall()

def format_song_info(song):
    """Format song information for display with comprehensive metadata."""
    artist = song.get('artist') or "Unknown Artist"
    albumartist = song.get('albumartist') or artist
    title = song.get('title') or "Unknown Title"
    album = song.get('album') or "Unknown Album"
    
    # Format duration
    duration = ""
    length = song.get('length', 0)
    if length:
        minutes, seconds = divmod(length, 60)
        duration = f" [{minutes}:{seconds:02d}]"
    
    # Format track number
    track = song.get('track', 0)
    track_str = f"{track:02d}. " if track else ""
    
    # Format year
    year = song.get('year', 0)
    year_str = f" ({year})" if year else ""
    
    return f"{track_str}{artist} - {title} ({albumartist} - {album}{year_str}){duration}"

def display_queue(queue, current_index=0):
    """Display the current queue with highlighting for current song."""
    if not queue:
        print("Queue is empty.")
        return
    
    print(f"\n=== Audio Queue ({len(queue)} songs) ===")
    for i, song in enumerate(queue):
        marker = "> " if i == current_index else "  "
        print(f"{marker}{i+1:3d}. {format_song_info(song)}")
    print()

def add_missing_song_to_database(file_path, conn):
    """Add missing song to database automatically during playback."""
    if not conn:
        return False
    
    try:
        from . import database
        
        # Get metadata
        meta = metadata.extract_metadata(file_path)
        if not meta:
            return False
        
        # Get directory
        dir_path = str(Path(file_path).parent)
        cursor = conn.cursor()
        
        # Add directory if not exists
        dir_stat = os.stat(dir_path)
        cursor.execute('INSERT OR IGNORE INTO directories (path, mtime) VALUES (?, ?)',
                      (dir_path, int(dir_stat.st_mtime)))
        
        # Get directory ID
        cursor.execute('SELECT id FROM directories WHERE path = ?', (dir_path,))
        directory_id = cursor.fetchone()[0]
        
        # Generate IDs
        stat = os.stat(file_path)
        fingerprint = hashlib.md5(f"{file_path}:{stat.st_size}:{stat.st_mtime}".encode()).hexdigest()
        file_url = f"file://{file_path}"
        
        # Insert song
        cursor.execute('''
            INSERT INTO songs (
                title, album, artist, albumartist, track, disc, year, genre,
                url, directory_id, basefilename, filetype, filesize, mtime, ctime,
                length, bitrate, samplerate, bitdepth, compilation, art_embedded,
                fingerprint, lastseen, source
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            meta['title'], meta['album'], meta['artist'], meta['albumartist'],
            meta['track'], meta['disc'], meta['year'], meta['genre'],
            file_url, directory_id, Path(file_path).name, Path(file_path).suffix[1:],
            stat.st_size, int(stat.st_mtime), int(stat.st_ctime),
            meta['length'], meta['bitrate'], meta['samplerate'], meta['bitdepth'],
            meta['compilation'], meta['art_embedded'], fingerprint,
            int(time.time()), 2
        ))
        
        conn.commit()
        print(f"  [Added to database: {meta['artist']} - {meta['title']}]")
        return True
    except Exception as e:
        print(f"  [Failed to add to database: {e}]")
        return False

def play_queue_with_manager(songs, repeat_mode="off", shuffle=False, start_index=0, conn=None):
    """
    Play songs using QueueManager with dynamic repeat mode support and interactive controls.
    
    Args:
        songs: List of song dictionaries or database records
        repeat_mode: Repeat mode - "off", "track", or "queue"
        shuffle: Enable shuffle mode
        start_index: Index to start playback from
        conn: Database connection for auto-adding missing songs
    """
    if not songs:
        print("Queue is empty. Nothing to play.")
        return
    
    # Create queue manager
    queue_manager = QueueManager(songs)
    queue_manager.set_repeat_mode(repeat_mode)
    queue_manager.set_shuffle_mode(shuffle)
    queue_manager.current_index = start_index
    
    print(f"\n=== Playing {len(songs)} songs ===")
    print(f"Repeat mode: {repeat_mode}")
    print(f"Shuffle: {'ON' if shuffle else 'OFF'}")
    print("Press Ctrl+C to control playback")
    print("Controls: 'q'=quit, 'n'=next, 'p'=previous, 's'=toggle shuffle, 'i'=instant shuffle, 'r'=repeat mode\n")
    
    while queue_manager.has_songs():
        song = queue_manager.current_song()
        if not song:
            break
        
        # Get file path
        file_path = song.get('url', song.get('filepath', ''))
        if file_path.startswith('file://'):
            file_path = file_path[7:]
        
        # Check if file exists
        if not os.path.exists(file_path):
            print(f"\nFile not found: {file_path}")
            song['file_missing'] = True
            if conn:
                print("  [Attempting to auto-add from filesystem...]")
                add_missing_song_to_database(file_path, conn)
            
            if not queue_manager.next_track_skip_missing():
                break
            continue
        
        # Display song info
        print(f"\n[{queue_manager.current_index + 1}/{len(songs)}] Now playing: {format_song_info(song)}")
        print(f"File: {file_path}")
        
        try:
            # Play the song
            play_audio(file_path)
            
            # Move to next track after playback completes
            if not queue_manager.next_track_skip_missing():
                break  # End of queue reached
        
        except KeyboardInterrupt:
            # Interactive control menu
            print("\n\nPlayback paused.")
            print("Commands: [q]uit, [n]ext, [p]revious, [s]huffle, [i]nstant shuffle, [r]epeat")
            
            try:
                choice = input("Choose action: ").strip().lower()
                
                if choice == 'q':
                    print("Quitting playback...")
                    break
                elif choice == 'n':
                    if not queue_manager.next_track_skip_missing():
                        print("Reached end of queue.")
                        break
                    print("Skipped to next track.")
                elif choice == 'p':
                    if queue_manager.previous_track():
                        print("Went to previous track.")
                    else:
                        print("Already at beginning or in track repeat mode.")
                elif choice == 's':
                    # Toggle shuffle
                    new_shuffle = not queue_manager.shuffle
                    queue_manager.set_shuffle_mode(new_shuffle)
                elif choice == 'i':
                    # Instant shuffle - physically reorder queue
                    if queue_manager.shuffle_queue():
                        print("Queue has been instantly shuffled!")
                elif choice == 'r':
                    # Cycle through repeat modes: off → track → queue → off
                    modes = [RepeatMode.OFF, RepeatMode.TRACK, RepeatMode.QUEUE]
                    current_idx = modes.index(queue_manager.repeat_mode)
                    next_mode = modes[(current_idx + 1) % len(modes)]
                    queue_manager.set_repeat_mode(next_mode)
                else:
                    print("Invalid choice. Resuming playback...")
            
            except KeyboardInterrupt:
                print("\n\nQuitting playback...")
                break
        
        except Exception as e:
            print(f"Error during playback: {e}")
            if not queue_manager.next_track_skip_missing():
                break
    
    print("\nPlayback finished.")

def play_queue(queue, shuffle=False, repeat=False, repeat_track=False, start_index=0, conn=None):
    """Play songs in the queue with various playback options."""
    # Determine repeat mode
    if repeat_track:
        repeat_mode = "track"
    elif repeat:
        repeat_mode = "queue"
    else:
        repeat_mode = "off"
    
    play_queue_with_manager(queue, repeat_mode, shuffle, start_index, conn)

def interactive_mode(conn):
    """
    Interactive mode for queue management.
    
    Provides a command-line interface for managing audio queues with
    commands for filtering, loading, and playing songs.
    
    Args:
        conn (sqlite3.Connection): Database connection object.
    """
    queue = []
    filters = {}
    
    print("\n=== Interactive Audio Queue Mode ===")
    print("Commands:")
    print("  list - Show all songs in library")
    print("  filter - Set filters (artist, album, genre)")
    print("  load - Load songs based on current filters")
    print("  playlist - Load songs from M3U playlist file")
    print("  show - Show current queue")
    print("  play - Play current queue")
    print("  shuffle - Toggle shuffle mode")
    print("  repeat - Toggle repeat mode")
    print("  clear - Clear current queue")
    print("  quit - Exit interactive mode")
    print()
    
    shuffle_mode = False
    repeat_mode = False
    
    while True:
        try:
            command = input("queue> ").strip().lower()
            
            if command in ['quit', 'q', 'exit']:
                break
            elif command == 'list':
                songs = get_songs_from_database(conn)
                if songs:
                    print(f"\nFound {len(songs)} songs in library:")
                    for i, song in enumerate(songs[:20]):  # Show first 20
                        print(f"  {i+1:3d}. {format_song_info(song)}")
                    if len(songs) > 20:
                        print(f"  ... and {len(songs) - 20} more")
                else:
                    print("No songs found in library.")
            elif command == 'filter':
                print("Set filters (press Enter to skip):")
                artist = input("Artist: ").strip()
                album = input("Album: ").strip()
                genre = input("Genre: ").strip()
                
                filters = {}
                if artist:
                    filters['artist'] = artist
                if album:
                    filters['album'] = album
                if genre:
                    filters['genre'] = genre
                
                print(f"Filters set: {filters}")
            elif command == 'load':
                songs = get_songs_from_database(conn, filters)
                if songs:
                    queue = list(songs)
                    print(f"Loaded {len(queue)} songs into queue.")
                else:
                    print("No songs found matching current filters.")
            elif command == 'show':
                display_queue(queue)
            elif command == 'play':
                if queue:
                    play_queue(queue, shuffle_mode, repeat_mode, False, 0, conn)
                else:
                    print("Queue is empty. Use 'load' to add songs first.")
            elif command == 'shuffle':
                shuffle_mode = not shuffle_mode
                print(f"Shuffle mode: {'ON' if shuffle_mode else 'OFF'}")
            elif command == 'repeat':
                repeat_mode = not repeat_mode
                print(f"Repeat mode: {'ON' if repeat_mode else 'OFF'}")
            elif command == 'playlist':
                playlist_path = input("Enter playlist file path: ").strip()
                if not os.path.exists(playlist_path):
                    print(f"Error: Playlist file '{playlist_path}' not found.")
                    continue
                
                songs = load_m3u_playlist(playlist_path)
                if songs:
                    queue = list(songs)
                    print(f"Loaded {len(queue)} songs from playlist '{playlist_path}'.")
                else:
                    print("No songs found in playlist or failed to load.")
            elif command == 'clear':
                queue = []
                print("Queue cleared.")
            elif command == 'help':
                print("Commands: list, filter, load, playlist, show, play, shuffle, repeat, clear, quit")
            else:
                print("Unknown command. Type 'help' for available commands.")
                
        except KeyboardInterrupt:
            print("\nExiting interactive mode...")
            break
        except Exception as e:
            print(f"Error: {e}")

def main():
    """
    Main function for audio queue management command-line interface.
    
    Provides a command-line interface for managing audio queues with
    support for database queries, playlist loading, shuffle, repeat modes.
    """
    parser = argparse.ArgumentParser(
        description='Audio Queue Manager - Manage and play audio queues',
        epilog='Examples:\n'
               '  python queue.py --db music.db --artist "Pink Floyd" --shuffle\n'
               '  python queue.py --playlist myplaylist.m3u --repeat\n'
               '  python queue.py --db music.db --album "Dark Side" --repeat-track',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    # Database options
    parser.add_argument('--db', default='walrio_library.db', help='Path to database file')
    parser.add_argument('--artist', help='Filter by artist')
    parser.add_argument('--album', help='Filter by album')
    parser.add_argument('--genre', help='Filter by genre')
    
    # Playlist loading
    parser.add_argument('--playlist', help='Load M3U playlist')
    
    # Playback options
    parser.add_argument('--shuffle', action='store_true', help='Enable shuffle mode')
    parser.add_argument('--repeat', action='store_true', help='Enable queue repeat')
    parser.add_argument('--repeat-track', action='store_true', help='Enable track repeat')
    parser.add_argument('--start', type=int, default=0, help='Start index (0-based)')
    
    # Display options
    parser.add_argument('--list', action='store_true', help='List all songs in library and exit')
    
    # Interactive mode
    parser.add_argument('--interactive', action='store_true', help='Enter interactive mode')
    
    args = parser.parse_args()
    
    # Load songs
    songs = []
    conn = None
    
    if args.playlist:
        # Load from playlist
        songs = load_m3u_playlist(args.playlist)
        if not songs:
            print(f"Failed to load playlist: {args.playlist}")
            return 1
        print(f"Loaded {len(songs)} songs from playlist")
    else:
        # Load from database
        conn = connect_to_database(args.db)
        if not conn:
            return 1
        
        filters = {}
        if args.artist:
            filters['artist'] = args.artist
        if args.album:
            filters['album'] = args.album
        if args.genre:
            filters['genre'] = args.genre
        
        songs = get_songs_from_database(conn, filters)
        if not songs:
            print("No songs found matching criteria.")
            if conn:
                conn.close()
            return 1
        
        print(f"Found {len(songs)} songs")
        
        # List mode - just show songs and exit
        if args.list:
            print(f"\nListing {len(songs)} songs:")
            for i, song in enumerate(songs):
                print(f"  {i+1:3d}. {format_song_info(song)}")
            if conn:
                conn.close()
            return 0
    
    # Start playback
    if args.interactive:
        interactive_mode(conn)
    else:
        play_queue(songs, args.shuffle, args.repeat, args.repeat_track, args.start, conn)
    
    if conn:
        conn.close()
    
    return 0

if __name__ == '__main__':
    sys.exit(main())
