#!/usr/bin/env python3
"""
database-powered audio queue requires walrio_library.db to be set up first via database.py module
"""
import os
import sys
import argparse
import sqlite3
import random
import time
import threading
from enum import Enum
from typing import List, Dict, Optional, Tuple

# Add parent directory for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from core.player import AudioPlayer
from core import database

class RepeatMode(Enum):
    """Repeat modes for audio playback."""
    OFF = 0
    TRACK = 1
    QUEUE = 2


class DatabaseQueue:
    """
    Audio queue manager that loads songs directly from database.
    Assumes walrio_library.db exists and is properly configured.
    """
    
    def __init__(self, db_path: str = 'walrio_library.db', track_stats: bool = True):
        """
        Initialize database queue.
        
        Args:
            db_path: Path to the SQLite database file
            track_stats: Enable playcount/skipcount tracking (default: True)
            
        Raises:
            FileNotFoundError: If database doesn't exist
        """
        if not os.path.exists(db_path):
            raise FileNotFoundError(f"Database not found: {db_path}. Run database.py first to create it.")
        
        self.db_path = db_path
        self.conn = sqlite3.connect(db_path)
        self.conn.row_factory = sqlite3.Row  # Enable column access by name
        
        self.queue = []
        self.current_index = 0
        self.playback_history = []
        self.forward_history = []
        
        self.shuffle = False
        self.repeat_mode = RepeatMode.OFF
        self.track_stats = track_stats
        
        # Filters
        self.filters = {
            'artist': None,
            'album': None,
            'albumartist': None,
            'genre': None,
            'year': None
        }
    
    def __del__(self):
        """Close database connection."""
        if hasattr(self, 'conn'):
            self.conn.close()
    
    def set_filter(self, filter_type: str, value: str):
        """Set a filter for querying songs."""
        if filter_type in self.filters:
            self.filters[filter_type] = value
    
    def clear_filters(self):
        """Clear all filters."""
        for key in self.filters:
            self.filters[key] = None
    
    def get_all_songs(self, limit: Optional[int] = None) -> List[Dict]:
        """
        Get all songs from database.
        
        Args:
            limit: Optional limit on number of songs
            
        Returns:
            List of song dictionaries
        """
        query = "SELECT * FROM songs WHERE 1=1"
        params = []
        
        # Apply filters
        if self.filters['artist']:
            query += " AND artist LIKE ?"
            params.append(f"%{self.filters['artist']}%")
        if self.filters['album']:
            query += " AND album LIKE ?"
            params.append(f"%{self.filters['album']}%")
        if self.filters['albumartist']:
            query += " AND albumartist LIKE ?"
            params.append(f"%{self.filters['albumartist']}%")
        if self.filters['genre']:
            query += " AND genre LIKE ?"
            params.append(f"%{self.filters['genre']}%")
        if self.filters['year']:
            query += " AND year = ?"
            params.append(self.filters['year'])
        
        if limit:
            query += f" LIMIT {limit}"
        
        cursor = self.conn.cursor()
        cursor.execute(query, params)
        
        songs = []
        for row in cursor.fetchall():
            songs.append(dict(row))
        
        return songs
    
    def search_songs(self, search_term: str) -> List[Dict]:
        """
        Search for songs by title, artist, or album.
        
        Args:
            search_term: Text to search for
            
        Returns:
            List of matching songs
        """
        query = """
            SELECT * FROM songs 
            WHERE title LIKE ? OR artist LIKE ? OR album LIKE ? OR albumartist LIKE ?
        """
        search_pattern = f"%{search_term}%"
        params = [search_pattern] * 4
        
        cursor = self.conn.cursor()
        cursor.execute(query, params)
        
        songs = []
        for row in cursor.fetchall():
            songs.append(dict(row))
        
        return songs
    
    def get_artists(self) -> List[str]:
        """
        Get all unique artists from database.
        
        Returns:
            List of unique artist names sorted alphabetically.
        """
        cursor = self.conn.cursor()
        cursor.execute("SELECT DISTINCT artist FROM songs WHERE artist != '' ORDER BY artist")
        return [row[0] for row in cursor.fetchall()]
    
    def get_albums(self) -> List[str]:
        """
        Get all unique albums from database.
        
        Returns:
            List of unique album names sorted alphabetically.
        """
        cursor = self.conn.cursor()
        cursor.execute("SELECT DISTINCT album FROM songs WHERE album != '' ORDER BY album")
        return [row[0] for row in cursor.fetchall()]
    
    def get_genres(self) -> List[str]:
        """
        Get all unique genres from database.
        
        Returns:
            List of unique genre names sorted alphabetically.
        """
        cursor = self.conn.cursor()
        cursor.execute("SELECT DISTINCT genre FROM songs WHERE genre != '' ORDER BY genre")
        return [row[0] for row in cursor.fetchall()]
    
    def load_from_filters(self):
        """Load queue from current filters."""
        songs = self.get_all_songs()
        if songs:
            self.queue = songs
            self.current_index = 0
            print(f"Loaded {len(songs)} songs from database")
        else:
            print("No songs match current filters")
    
    def load_random(self, count: int = 50):
        """
        Load random songs from database.
        
        Args:
            count: Number of random songs to load
        """
        songs = self.get_all_songs()
        if songs:
            selected = random.sample(songs, min(count, len(songs)))
            self.queue = selected
            self.current_index = 0
            print(f"Loaded {len(selected)} random songs")
        else:
            print("No songs in database")
    
    def load_album(self, album_name: str):
        """Load all songs from a specific album."""
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM songs WHERE album LIKE ? ORDER BY disc, track", (f"%{album_name}%",))
        
        songs = []
        for row in cursor.fetchall():
            songs.append(dict(row))
        
        if songs:
            self.queue = songs
            self.current_index = 0
            print(f"Loaded album '{album_name}' ({len(songs)} songs)")
        else:
            print(f"No album found matching '{album_name}'")
    
    def load_artist(self, artist_name: str):
        """Load all songs from a specific artist."""
        cursor = self.conn.cursor()
        cursor.execute(
            "SELECT * FROM songs WHERE artist LIKE ? OR albumartist LIKE ? ORDER BY album, disc, track",
            (f"%{artist_name}%", f"%{artist_name}%")
        )
        
        songs = []
        for row in cursor.fetchall():
            songs.append(dict(row))
        
        if songs:
            self.queue = songs
            self.current_index = 0
            print(f"Loaded artist '{artist_name}' ({len(songs)} songs)")
        else:
            print(f"No artist found matching '{artist_name}'")
    
    def show_queue(self, context: int = 10):
        """Show current queue with context around current position."""
        if not self.queue:
            print("Queue is empty")
            return
        
        print(f"\n=== Queue ({len(self.queue)} songs) ===")
        start = max(0, self.current_index - context // 2)
        end = min(len(self.queue), start + context)
        
        for i in range(start, end):
            song = self.queue[i]
            marker = ">" if i == self.current_index else " "
            mins, secs = divmod(int(song.get('length', 0)), 60)
            title = song.get('title', 'Unknown')
            artist = song.get('artist', 'Unknown')
            album = song.get('album', 'Unknown')
            print(f"{marker} {i+1:3d}. {artist} - {title} ({album}) [{mins}:{secs:02d}]")
        
        if end < len(self.queue):
            print(f"  ... and {len(self.queue) - end} more songs")
    
    def play_queue(self):
        """
        Play current queue with playback statistics tracking.
        Tracks playcount, skipcount, and last_played for database songs.
        """
        if not self.queue:
            print("Queue is empty. Load songs first.")
            return
        
        # Create audio player
        player = AudioPlayer(debug=False)
        
        # Playback control flags
        playback_active = {'running': True, 'skip_requested': False, 'previous_requested': False}
        playback_lock = threading.Lock()
        
        # Track song start time to detect skips
        song_start_time = None
        last_song_id = None
        
        def playback_thread():
            """Background thread that handles actual playback."""
            nonlocal song_start_time, last_song_id
            
            try:
                while playback_active['running'] and self.queue:
                    if self.current_index >= len(self.queue):
                        break
                    
                    song = self.queue[self.current_index]
                    song_id = song.get('id')
                    
                    # Get file path
                    file_path = song.get('url', '')
                    if file_path.startswith('file://'):
                        file_path = file_path[7:]
                    
                    # Check if file exists
                    if not os.path.exists(file_path):
                        print(f"\nFile not found: {file_path}")
                        self.current_index += 1
                        continue
                    
                    # Display song info
                    mins, secs = divmod(int(song.get('length', 0)), 60)
                    title = song.get('title', 'Unknown')
                    artist = song.get('artist', 'Unknown')
                    album = song.get('album', 'Unknown')
                    print(f"\n[{self.current_index + 1}/{len(self.queue)}] Now playing: {artist} - {title} ({album}) [{mins}:{secs:02d}]")
                    print(f"File: {file_path}")
                    
                    # Load and play the song
                    if not player.load_file(file_path):
                        self.current_index += 1
                        continue
                    
                    if not player.play():
                        self.current_index += 1
                        continue
                    
                    # Track song start
                    song_start_time = time.time()
                    last_song_id = song_id
                    
                    print("queue/play> ", end="", flush=True)
                    
                    # Track if we manually changed tracks
                    manual_skip = False
                    
                    # Wait for playback to complete or command
                    while player.is_playing and playback_active['running']:
                        with playback_lock:
                            if playback_active['skip_requested']:
                                playback_active['skip_requested'] = False
                                manual_skip = True
                                player.stop()
                                
                                # Update skipcount if song was skipped early
                                if self.track_stats and song_id and song_start_time:
                                    elapsed = time.time() - song_start_time
                                    song_length = song.get('length', 0)
                                    # Count as skip if less than 80% played
                                    if song_length > 0 and elapsed < song_length * 0.8:
                                        database.update_skipcount(self.conn, song_id)
                                
                                self.current_index += 1
                                break
                            
                            if playback_active['previous_requested']:
                                playback_active['previous_requested'] = False
                                manual_skip = True
                                player.stop()
                                
                                # Update skipcount for current song
                                if self.track_stats and song_id and song_start_time:
                                    elapsed = time.time() - song_start_time
                                    song_length = song.get('length', 0)
                                    if song_length > 0 and elapsed < song_length * 0.8:
                                        database.update_skipcount(self.conn, song_id)
                                
                                # Go to previous song
                                if self.playback_history:
                                    self.forward_history.append(self.current_index)
                                    self.current_index = self.playback_history.pop()
                                else:
                                    print("Already at beginning of playback history.")
                                    manual_skip = False
                                break
                        time.sleep(0.1)
                    
                    if not playback_active['running']:
                        player.stop()
                        break
                    
                    # Song finished naturally - update playcount
                    if self.track_stats and not manual_skip and song_id:
                        database.update_playcount(self.conn, song_id)
                    
                    # Move to next track after natural completion
                    if not manual_skip:
                        self.playback_history.append(self.current_index)
                        
                        # Handle repeat modes
                        if self.repeat_mode == RepeatMode.TRACK:
                            pass  # Stay on same track
                        elif self.repeat_mode == RepeatMode.QUEUE:
                            self.current_index = (self.current_index + 1) % len(self.queue)
                        else:
                            self.current_index += 1
                            if self.current_index >= len(self.queue):
                                break
            
            finally:
                player.stop()
                playback_active['running'] = False
        
        # Start playback thread
        thread = threading.Thread(target=playback_thread, daemon=True)
        thread.start()
        
        # Print initial status
        print(f"\n=== Playing {len(self.queue)} songs ===")
        print(f"Repeat mode: {self.repeat_mode.name}")
        print(f"Shuffle: {'ON' if self.shuffle else 'OFF'}")
        print(f"Volume: {player.get_volume():.2f}")
        print("\nPlayback running in background. Type commands below:")
        print("Commands: next, previous, pause, resume, stop, current, show, help")
        
        # Command loop
        while playback_active['running'] and thread.is_alive():
            try:
                command = input("queue/play> ").strip().lower()
                
                if not command:
                    continue
                
                if command in ['quit', 'q', 'stop']:
                    playback_active['running'] = False
                    player.should_quit = True
                    print("Stopping playback...")
                    break
                
                elif command in ['next', 'n', 'skip']:
                    with playback_lock:
                        playback_active['skip_requested'] = True
                    print("Skipping to next track...")
                
                elif command in ['previous', 'p', 'prev']:
                    with playback_lock:
                        playback_active['previous_requested'] = True
                
                elif command == 'pause':
                    player.pause()
                    print("Paused")
                
                elif command == 'resume':
                    player.resume()
                    print("Resumed")
                
                elif command in ['current', 'c']:
                    if self.current_index < len(self.queue):
                        song = self.queue[self.current_index]
                        position = player.get_position()
                        duration = player.get_duration()
                        
                        mins, secs = divmod(int(song.get('length', 0)), 60)
                        title = song.get('title', 'Unknown')
                        artist = song.get('artist', 'Unknown')
                        album = song.get('album', 'Unknown')
                        print(f"\nCurrent: {artist} - {title} ({album}) [{mins}:{secs:02d}]")
                        
                        if position >= 0 and duration > 0:
                            pos_mins, pos_secs = divmod(int(position), 60)
                            dur_mins, dur_secs = divmod(int(duration), 60)
                            print(f"Position: {pos_mins}:{pos_secs:02d} / {dur_mins}:{dur_secs:02d}")
                
                elif command in ['show', 'queue']:
                    self.show_queue()
                
                elif command.startswith('volume '):
                    try:
                        vol_str = command.split()[1]
                        if vol_str.startswith('+') or vol_str.startswith('-'):
                            current_vol = player.get_volume()
                            volume = current_vol + float(vol_str)
                        else:
                            volume = float(vol_str)
                        
                        volume = max(0.0, min(1.0, volume))
                        player.set_volume(volume)
                        print(f"Volume: {volume:.2f}")
                    except (ValueError, IndexError):
                        print("Usage: volume <0.0-1.0> or volume +0.1 or volume -0.1")
                
                elif command == 'help':
                    print("\nPlayback Commands:")
                    print("  next/n - Skip to next track")
                    print("  previous/p - Go to previous track")
                    print("  pause - Pause playback")
                    print("  resume - Resume playback")
                    print("  stop/quit - Stop playback and return")
                    print("  current/c - Show current song info")
                    print("  show - Show queue around current position")
                    print("  volume <0.0-1.0> - Set volume (or +0.1, -0.1)")
                    print("  help - Show this help")
                
                else:
                    print(f"Unknown command: {command}")
            
            except KeyboardInterrupt:
                playback_active['running'] = False
                player.should_quit = True
                print("\nStopping playback...")
                break
            except Exception as e:
                print(f"Error: {e}")
        
        thread.join(timeout=2)
        print("Playback finished.")


def interactive_mode(db_path: str = 'walrio_library.db', track_stats: bool = True):
    """
    Run interactive queue mode with database.
    
    Args:
        db_path: Path to database file
        track_stats: Enable playcount/skipcount tracking
    """
    try:
        queue_mgr = DatabaseQueue(db_path, track_stats=track_stats)
    except FileNotFoundError as e:
        print(f"Error: {e}")
        print("\nTo create a database:")
        print("  python database.py /path/to/music/directory")
        return 1
    
    print("=== Interactive Database Queue Mode ===")
    print(f"Database: {db_path}")
    
    # Show database stats
    cursor = queue_mgr.conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM songs")
    total_songs = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(DISTINCT artist) FROM songs WHERE artist != ''")
    total_artists = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(DISTINCT album) FROM songs WHERE album != ''")
    total_albums = cursor.fetchone()[0]
    
    print(f"Library: {total_songs} songs, {total_artists} artists, {total_albums} albums")
    print(f"Stats tracking: {'ON' if queue_mgr.track_stats else 'OFF'}")
    print("\nCommands:")
    print("  all - Load all songs")
    print("  random [N] - Load N random songs (default 50)")
    print("  artist <name> - Load all songs by artist")
    print("  album <name> - Load all songs from album")
    print("  search <term> - Search and load results")
    print("  filter - Set filters (artist/album/genre)")
    print("  show - Show current queue")
    print("  play - Play current queue")
    print("  shuffle - Toggle shuffle mode")
    print("  repeat - Cycle repeat modes (off → track → queue)")
    print("  stats - Toggle playcount tracking")
    print("  quit - Exit")
    
    while True:
        try:
            command = input("\ndb_queue> ").strip().lower()
            
            if not command:
                continue
            
            if command == 'quit' or command == 'q':
                break
            
            elif command == 'all':
                queue_mgr.load_from_filters()
            
            elif command.startswith('random'):
                parts = command.split()
                count = int(parts[1]) if len(parts) > 1 else 50
                queue_mgr.load_random(count)
            
            elif command.startswith('artist '):
                artist_name = command[7:].strip()
                queue_mgr.load_artist(artist_name)
            
            elif command.startswith('album '):
                album_name = command[6:].strip()
                queue_mgr.load_album(album_name)
            
            elif command.startswith('search '):
                search_term = command[7:].strip()
                songs = queue_mgr.search_songs(search_term)
                if songs:
                    queue_mgr.queue = songs
                    queue_mgr.current_index = 0
                    print(f"Found {len(songs)} songs")
                else:
                    print("No songs found")
            
            elif command == 'show':
                queue_mgr.show_queue()
            
            elif command == 'filter':
                print("\nAvailable filters:")
                print("  artist, album, genre")
                print("Enter filter (or 'clear' to reset):")
                filter_cmd = input("filter> ").strip().lower()
                
                if filter_cmd == 'clear':
                    queue_mgr.clear_filters()
                    print("Filters cleared")
                elif filter_cmd in queue_mgr.filters:
                    value = input(f"Enter {filter_cmd}: ").strip()
                    queue_mgr.set_filter(filter_cmd, value)
                    print(f"Filter set: {filter_cmd} = {value}")
            
            elif command == 'shuffle':
                queue_mgr.shuffle = not queue_mgr.shuffle
                print(f"Shuffle: {'ON' if queue_mgr.shuffle else 'OFF'}")
            
            elif command == 'repeat':
                # Cycle through repeat modes: OFF -> TRACK -> QUEUE -> OFF
                if queue_mgr.repeat_mode == RepeatMode.OFF:
                    queue_mgr.repeat_mode = RepeatMode.TRACK
                elif queue_mgr.repeat_mode == RepeatMode.TRACK:
                    queue_mgr.repeat_mode = RepeatMode.QUEUE
                else:
                    queue_mgr.repeat_mode = RepeatMode.OFF
                print(f"Repeat mode: {queue_mgr.repeat_mode.name}")
            
            elif command == 'stats':
                queue_mgr.track_stats = not queue_mgr.track_stats
                print(f"Stats tracking: {'ON' if queue_mgr.track_stats else 'OFF'}")
            
            elif command == 'play':
                if not queue_mgr.queue:
                    print("Queue is empty. Load songs first.")
                    continue
                
                queue_mgr.play_queue()
            
            else:
                print(f"Unknown command: {command}")
        
        except KeyboardInterrupt:
            print("\n")
            break
        except Exception as e:
            print(f"Error: {e}")
    
    print("Goodbye!")
    return 0


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Database-powered audio queue manager",
        epilog="Requires walrio_library.db to be created first with database.py"
    )
    
    parser.add_argument(
        '--db-path',
        default='walrio_library.db',
        help='Path to database file (default: walrio_library.db)'
    )
    
    parser.add_argument(
        '--interactive', '-i',
        action='store_true',
        help='Run in interactive mode'
    )
    
    parser.add_argument(
        '--no-stats',
        action='store_true',
        help='Disable playcount/skipcount tracking'
    )
    
    args = parser.parse_args()
    
    if args.interactive:
        return interactive_mode(args.db_path, track_stats=not args.no_stats)
    else:
        parser.print_help()
        return 1


if __name__ == "__main__":
    sys.exit(main())
