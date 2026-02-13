#!/usr/bin/env python3
"""
Database-powered audio queue - requires walrio_library.db to be set up first.
Optimized version that assumes database exists and skips fallback checks.
"""

import os
import sys
import argparse
import sqlite3
import random
from enum import Enum
from typing import List, Dict, Optional, Tuple

# Add parent directory for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from core.player import AudioPlayer

# Enum for repeat modes
class RepeatMode(Enum):
    OFF = 0
    TRACK = 1
    QUEUE = 2


class DatabaseQueue:
    """
    Audio queue manager that loads songs directly from database.
    Assumes walrio_library.db exists and is properly configured.
    """
    
    def __init__(self, db_path: str = 'walrio_library.db'):
        """
        Initialize database queue.
        
        Args:
            db_path: Path to the SQLite database file
            
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
        """Get all unique artists from database."""
        cursor = self.conn.cursor()
        cursor.execute("SELECT DISTINCT artist FROM songs WHERE artist != '' ORDER BY artist")
        return [row[0] for row in cursor.fetchall()]
    
    def get_albums(self) -> List[str]:
        """Get all unique albums from database."""
        cursor = self.conn.cursor()
        cursor.execute("SELECT DISTINCT album FROM songs WHERE album != '' ORDER BY album")
        return [row[0] for row in cursor.fetchall()]
    
    def get_genres(self) -> List[str]:
        """Get all unique genres from database."""
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


def interactive_mode(db_path: str = 'walrio_library.db'):
    """
    Run interactive queue mode with database.
    
    Args:
        db_path: Path to database file
    """
    try:
        queue_mgr = DatabaseQueue(db_path)
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
            
            elif command == 'play':
                if not queue_mgr.queue:
                    print("Queue is empty. Load songs first.")
                    continue
                
                print(f"\n=== Playing {len(queue_mgr.queue)} songs ===")
                print("Shuffle:", 'ON' if queue_mgr.shuffle else 'OFF')
                print("(Playback controls coming soon)")
                # TODO: Integrate with AudioPlayer like queue.py does
            
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
    
    args = parser.parse_args()
    
    if args.interactive:
        return interactive_mode(args.db_path)
    else:
        parser.print_help()
        return 1


if __name__ == "__main__":
    sys.exit(main())
