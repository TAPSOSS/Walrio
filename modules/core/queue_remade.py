#!/usr/bin/env python3
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
        self.shuffle_history = []
        self.history = []
        self.forward_history = []
    
    def set_repeat_mode(self, mode):
        """Set repeat mode: "off", "track", or "queue"."""
        if isinstance(mode, str):
            mode = RepeatMode(mode.lower())
        self.repeat_mode = mode
    
    def set_shuffle_mode(self, enabled):
        """Set shuffle mode on/off."""
        self.shuffle = enabled
        if enabled:
            self.shuffle_history = [self.current_index]
    
    def is_shuffle_effective(self):
        """Check if shuffle is actively being used."""
        return self.shuffle and self.repeat_mode == RepeatMode.OFF
    
    def current_song(self):
        """Get the currently playing song."""
        if 0 <= self.current_index < len(self.songs):
            return self.songs[self.current_index]
        return None
    
    def _get_next_shuffle_song(self):
        """Get next random song that hasn't been played recently."""
        unplayed = [i for i in range(len(self.songs)) if i not in self.shuffle_history[-len(self.songs):]]
        if not unplayed:
            # All songs played, reset history (keep current)
            self.shuffle_history = [self.current_index]
            unplayed = [i for i in range(len(self.songs)) if i != self.current_index]
        return random.choice(unplayed) if unplayed else self.current_index
    
    def has_songs(self):
        """Check if there are songs in the queue."""
        return len(self.songs) > 0
    
    def next_track(self):
        """
        Move to next track. Prioritizes forward history (from previous button) over normal progression.
        Returns True if moved successfully, False if at end.
        """
        if not self.has_songs():
            return False
        
        # Check for forward history first
        if self.forward_history:
            self.history.append(self.current_index)
            self.current_index = self.forward_history.pop()
            return True
        
        # Handle track repeat
        if self.repeat_mode == RepeatMode.TRACK:
            return True  # Stay on same track
        
        # Handle shuffle
        if self.is_shuffle_effective():
            self.history.append(self.current_index)
            next_idx = self._get_next_shuffle_song()
            self.shuffle_history.append(next_idx)
            self.current_index = next_idx
            return True
        
        # Normal progression
        self.history.append(self.current_index)
        self.current_index += 1
        
        # Check if we reached the end
        if self.current_index >= len(self.songs):
            if self.repeat_mode == RepeatMode.QUEUE:
                self.current_index = 0
                return True
            return False  # Reached end
        
        return True
    
    def next_track_skip_missing(self):
        """Move to next track, skipping unavailable songs."""
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
                    return True
            attempts += 1
        
        return False
    
    def previous_track(self):
        """
        Move to previous track. When going back, adds current song to forward history for next button.
        Returns True if moved successfully, False if at beginning.
        """
        if not self.has_songs() or not self.history:
            return False
        
        self.forward_history.append(self.current_index)
        self.current_index = self.history.pop()
        return True
    
    def set_current_index(self, index):
        """Set current playback index. History tracking ensures proper previous button functionality."""
        if 0 <= index < len(self.songs):
            self.history.append(self.current_index)
            self.current_index = index
            return True
        return False
    
    def add_song(self, song):
        """Add a song to the queue."""
        self.songs.append(song)
    
    def remove_song(self, index):
        """Remove a song from the queue."""
        if 0 <= index < len(self.songs):
            self.songs.pop(index)
            if self.current_index >= index:
                self.current_index = max(0, self.current_index - 1)
            return True
        return False
    
    def shuffle_physically(self):
        """Shuffle the entire queue by randomly reordering all songs."""
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
        
        print("Queue physically shuffled")
        return True
    
    def jump_random(self):
        """Jump to a completely random song in the queue."""
        if not self.songs:
            return False
        
        random_index = random.randint(0, len(self.songs) - 1)
        self.history.append(self.current_index)
        self.current_index = random_index
        
        song = self.current_song()
        if song:
            print(f"Jumped to random song: {song.get('title', 'Unknown')}")
        return True
    
    def clear(self):
        """Clear the entire queue."""
        self.songs = []
        self.current_index = 0
        self.history = []
        self.forward_history = []
        self.shuffle_history = []

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
    track = song.get('track', 0)
    artist = song.get('artist', 'Unknown')
    title = song.get('title', 'Unknown')
    albumartist = song.get('albumartist', '')
    album = song.get('album', 'Unknown')
    year = song.get('year', 0)
    length = song.get('length', 0)
    
    minutes = int(length // 60)
    seconds = int(length % 60)
    
    info = f"{track:02d}. {artist} - {title}"
    if albumartist and albumartist != artist:
        info += f" (AlbumArtist: {albumartist})"
    info += f" [{album}"
    if year:
        info += f", {year}"
    info += f"] ({minutes}:{seconds:02d})"
    
    return info

def display_queue(queue, current_index=0):
    """Display the current queue with highlighting for current song."""
    print(f"\nQueue ({len(queue)} songs):")
    print("-" * 80)
    
    for i, song in enumerate(queue):
        marker = "►" if i == current_index else " "
        print(f"{marker} {i+1:3d}. {format_song_info(song)}")

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
    """Play songs using QueueManager with dynamic repeat mode support."""
    if not songs:
        print("No songs in queue.")
        return
    
    queue_manager = QueueManager(songs)
    queue_manager.set_repeat_mode(repeat_mode)
    queue_manager.set_shuffle_mode(shuffle)
    queue_manager.current_index = start_index
    
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
            if conn:
                print("  [Attempting to auto-add from filesystem...]")
                add_missing_song_to_database(file_path, conn)
            
            if not queue_manager.next_track_skip_missing():
                break
            continue
        
        # Display song info
        print(f"\nNow playing: {format_song_info(song)}")
        print(f"File: {file_path}")
        
        try:
            # Play the song
            play_audio(file_path)
            
            # Move to next track after playback completes
            if not queue_manager.next_track():
                break  # End of queue reached
        
        except KeyboardInterrupt:
            print("\nPlayback interrupted by user.")
            break
        except Exception as e:
            print(f"Error during playback: {e}")
            if not queue_manager.next_track():
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
