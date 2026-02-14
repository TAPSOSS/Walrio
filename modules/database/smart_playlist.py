#!/usr/bin/env python3
"""
smart/dynamic playlist manager for database-powered playlists.
"""
import os
import sys
import json
import sqlite3
import argparse
from typing import List, Dict, Optional, Any
from pathlib import Path

# Add parent directory for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from core.playlist import create_m3u_playlist


class SmartPlaylistManager:
    """
    Manages smart playlists that generate song lists based on database queries.
    """
    
    def __init__(self, db_path: str = 'walrio_library.db'):
        """
        Initialize smart playlist manager.
        
        Args:
            db_path: Path to the SQLite database file
            
        Raises:
            FileNotFoundError: If database doesn't exist
        """
        if not os.path.exists(db_path):
            raise FileNotFoundError(f"Database not found: {db_path}")
        
        self.db_path = db_path
        self.conn = sqlite3.connect(db_path)
        self.conn.row_factory = sqlite3.Row
        self._ensure_tables()
    
    def __del__(self):
        """Close database connection."""
        if hasattr(self, 'conn'):
            self.conn.close()
    
    def _ensure_tables(self):
        """Create smart_playlists table if it doesn't exist."""
        cursor = self.conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS smart_playlists (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE NOT NULL,
                rules TEXT NOT NULL,
                sort_by TEXT DEFAULT 'artist, album, disc, track',
                sort_desc INTEGER DEFAULT 0,
                limit_count INTEGER DEFAULT NULL,
                created INTEGER DEFAULT (strftime('%s', 'now')),
                modified INTEGER DEFAULT (strftime('%s', 'now'))
            )
        ''')
        self.conn.commit()
    
    def create_playlist(self, name: str, rules: List[Dict[str, Any]], 
                       sort_by: str = 'artist, album, disc, track',
                       sort_desc: bool = False,
                       limit_count: Optional[int] = None) -> int:
        """
        Create a new smart playlist.
        
        Args:
            name: Playlist name
            rules: List of rule dictionaries with keys:
                   - field: Column name (genre, artist, playcount, etc.)
                   - operator: Comparison operator (=, !=, >, <, >=, <=, LIKE, NOT LIKE)
                   - value: Value to compare against
                   - logic: 'AND' or 'OR' (for combining with next rule)
            sort_by: Column(s) to sort by (comma-separated)
            sort_desc: Sort descending if True
            limit_count: Maximum number of songs (None for unlimited)
            
        Returns:
            Playlist ID
            
        Example:
            rules = [
                {'field': 'genre', 'operator': 'LIKE', 'value': '%Jazz%', 'logic': 'AND'},
                {'field': 'playcount', 'operator': '>', 'value': 5}
            ]
        """
        cursor = self.conn.cursor()
        
        # Validate rules
        if not rules:
            raise ValueError("At least one rule is required")
        
        # Serialize rules to JSON
        rules_json = json.dumps(rules)
        
        cursor.execute('''
            INSERT INTO smart_playlists (name, rules, sort_by, sort_desc, limit_count)
            VALUES (?, ?, ?, ?, ?)
        ''', (name, rules_json, sort_by, 1 if sort_desc else 0, limit_count))
        
        self.conn.commit()
        return cursor.lastrowid
    
    def update_playlist(self, playlist_id: int, name: Optional[str] = None,
                       rules: Optional[List[Dict[str, Any]]] = None,
                       sort_by: Optional[str] = None,
                       sort_desc: Optional[bool] = None,
                       limit_count: Optional[int] = None):
        """
        Update an existing smart playlist.
        
        Args:
            playlist_id: ID of playlist to update
            name: New name (if provided)
            rules: New rules (if provided)
            sort_by: New sort column(s) (if provided)
            sort_desc: New sort direction (if provided)
            limit_count: New limit (if provided)
        """
        updates = []
        params = []
        
        if name is not None:
            updates.append("name = ?")
            params.append(name)
        
        if rules is not None:
            updates.append("rules = ?")
            params.append(json.dumps(rules))
        
        if sort_by is not None:
            updates.append("sort_by = ?")
            params.append(sort_by)
        
        if sort_desc is not None:
            updates.append("sort_desc = ?")
            params.append(1 if sort_desc else 0)
        
        if limit_count is not None:
            updates.append("limit_count = ?")
            params.append(limit_count)
        
        if updates:
            updates.append("modified = strftime('%s', 'now')")
            params.append(playlist_id)
            
            cursor = self.conn.cursor()
            cursor.execute(f'''
                UPDATE smart_playlists
                SET {', '.join(updates)}
                WHERE id = ?
            ''', params)
            self.conn.commit()
    
    def delete_playlist(self, playlist_id: int):
        """Delete a smart playlist by ID."""
        cursor = self.conn.cursor()
        cursor.execute("DELETE FROM smart_playlists WHERE id = ?", (playlist_id,))
        self.conn.commit()
    
    def get_playlist(self, playlist_id: int) -> Optional[Dict]:
        """Get smart playlist definition by ID.
        
        Returns:
            Optional[Dict]: Dictionary containing playlist data, or None if not found.
        """
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM smart_playlists WHERE id = ?", (playlist_id,))
        row = cursor.fetchone()
        
        if row:
            return {
                'id': row['id'],
                'name': row['name'],
                'rules': json.loads(row['rules']),
                'sort_by': row['sort_by'],
                'sort_desc': bool(row['sort_desc']),
                'limit_count': row['limit_count'],
                'created': row['created'],
                'modified': row['modified']
            }
        return None
    
    def get_playlist_by_name(self, name: str) -> Optional[Dict]:
        """Get smart playlist definition by name.
        
        Returns:
            Optional[Dict]: Dictionary containing playlist data, or None if not found.
        """
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM smart_playlists WHERE name = ?", (name,))
        row = cursor.fetchone()
        
        if row:
            return {
                'id': row['id'],
                'name': row['name'],
                'rules': json.loads(row['rules']),
                'sort_by': row['sort_by'],
                'sort_desc': bool(row['sort_desc']),
                'limit_count': row['limit_count'],
                'created': row['created'],
                'modified': row['modified']
            }
        return None
    
    def list_playlists(self) -> List[Dict]:
        """List all smart playlists.
        
        Returns:
            List[Dict]: List of dictionaries containing playlist data.
        """
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM smart_playlists ORDER BY name")
        
        playlists = []
        for row in cursor.fetchall():
            playlists.append({
                'id': row['id'],
                'name': row['name'],
                'rules': json.loads(row['rules']),
                'sort_by': row['sort_by'],
                'sort_desc': bool(row['sort_desc']),
                'limit_count': row['limit_count'],
                'created': row['created'],
                'modified': row['modified']
            })
        
        return playlists
    
    def _build_query(self, rules: List[Dict[str, Any]], sort_by: str, 
                     sort_desc: bool, limit_count: Optional[int]) -> tuple:
        """
        Build SQL query from rules.
        
        Returns:
            Tuple of (query_string, parameters)
        """
        query = "SELECT * FROM songs WHERE unavailable = 0"
        params = []
        
        if rules:
            conditions = []
            for i, rule in enumerate(rules):
                field = rule['field']
                operator = rule['operator'].upper()
                value = rule['value']
                
                # Build condition
                conditions.append(f"{field} {operator} ?")
                params.append(value)
                
                # Add logic connector if not last rule
                if i < len(rules) - 1:
                    logic = rule.get('logic', 'AND').upper()
                    conditions.append(logic)
            
            query += " AND (" + " ".join(conditions) + ")"
        
        # Add sorting
        if sort_by:
            query += f" ORDER BY {sort_by}"
            if sort_desc:
                query += " DESC"
        
        # Add limit
        if limit_count:
            query += f" LIMIT {limit_count}"
        
        return query, params
    
    def generate_songs(self, playlist_id: int) -> List[Dict]:
        """
        Generate song list from smart playlist rules.
        
        Args:
            playlist_id: ID of smart playlist
            
        Returns:
            List of song dictionaries matching the rules
        """
        playlist = self.get_playlist(playlist_id)
        if not playlist:
            raise ValueError(f"Playlist {playlist_id} not found")
        
        query, params = self._build_query(
            playlist['rules'],
            playlist['sort_by'],
            playlist['sort_desc'],
            playlist['limit_count']
        )
        
        cursor = self.conn.cursor()
        cursor.execute(query, params)
        
        songs = []
        for row in cursor.fetchall():
            songs.append(dict(row))
        
        return songs
    
    def export_to_m3u(self, playlist_id: int, output_path: str, 
                      use_absolute_paths: bool = False) -> bool:
        """
        Export smart playlist to M3U file.
        
        Args:
            playlist_id: ID of smart playlist
            output_path: Path for output M3U file
            use_absolute_paths: Use absolute paths instead of relative
            
        Returns:
            True if successful
        """
        playlist = self.get_playlist(playlist_id)
        if not playlist:
            print(f"Playlist {playlist_id} not found")
            return False
        
        songs = self.generate_songs(playlist_id)
        if not songs:
            print(f"No songs match playlist rules")
            return False
        
        return create_m3u_playlist(songs, output_path, use_absolute_paths, playlist['name'])


def interactive_mode(db_path: str = 'walrio_library.db'):
    """
    Interactive mode for managing smart playlists.
    
    Args:
        db_path: Path to database file
    """
    try:
        manager = SmartPlaylistManager(db_path)
    except FileNotFoundError as e:
        print(f"Error: {e}")
        return 1
    
    print("=== Smart Playlist Manager ===")
    print(f"Database: {db_path}")
    print("\nCommands:")
    print("  create - Create new smart playlist")
    print("  list - List all smart playlists")
    print("  show <id|name> - Show playlist details and songs")
    print("  export <id|name> <file> - Export playlist to M3U")
    print("  delete <id|name> - Delete smart playlist")
    print("  templates - Show example playlist templates")
    print("  quit - Exit")
    
    while True:
        try:
            command = input("\nplaylist> ").strip()
            
            if not command:
                continue
            
            if command in ['quit', 'q']:
                break
            
            elif command == 'list':
                playlists = manager.list_playlists()
                if not playlists:
                    print("No smart playlists created yet")
                else:
                    print(f"\n{len(playlists)} Smart Playlists:")
                    for pl in playlists:
                        song_count = len(manager.generate_songs(pl['id']))
                        print(f"  [{pl['id']}] {pl['name']} - {song_count} songs")
            
            elif command.startswith('show '):
                target = command[5:].strip()
                
                # Try as ID first, then name
                try:
                    playlist_id = int(target)
                    playlist = manager.get_playlist(playlist_id)
                except ValueError:
                    playlist = manager.get_playlist_by_name(target)
                
                if not playlist:
                    print(f"Playlist not found: {target}")
                    continue
                
                print(f"\nPlaylist: {playlist['name']} (ID: {playlist['id']})")
                print(f"Rules:")
                for i, rule in enumerate(playlist['rules']):
                    logic = f" {rule.get('logic', '')}" if i < len(playlist['rules']) - 1 else ""
                    print(f"  {rule['field']} {rule['operator']} {rule['value']}{logic}")
                print(f"Sort: {playlist['sort_by']} {'DESC' if playlist['sort_desc'] else 'ASC'}")
                if playlist['limit_count']:
                    print(f"Limit: {playlist['limit_count']} songs")
                
                songs = manager.generate_songs(playlist['id'])
                print(f"\n{len(songs)} songs:")
                for i, song in enumerate(songs[:20], 1):
                    artist = song.get('artist', 'Unknown')
                    title = song.get('title', 'Unknown')
                    album = song.get('album', 'Unknown')
                    playcount = song.get('playcount', 0)
                    print(f"  {i}. {artist} - {title} ({album}) [plays: {playcount}]")
                
                if len(songs) > 20:
                    print(f"  ... and {len(songs) - 20} more")
            
            elif command.startswith('export '):
                parts = command[7:].split(maxsplit=1)
                if len(parts) != 2:
                    print("Usage: export <id|name> <output_file>")
                    continue
                
                target, output_file = parts
                
                # Try as ID first, then name
                try:
                    playlist_id = int(target)
                    playlist = manager.get_playlist(playlist_id)
                except ValueError:
                    playlist = manager.get_playlist_by_name(target)
                    if playlist:
                        playlist_id = playlist['id']
                
                if not playlist:
                    print(f"Playlist not found: {target}")
                    continue
                
                if manager.export_to_m3u(playlist_id, output_file):
                    print(f"Exported to {output_file}")
            
            elif command.startswith('delete '):
                target = command[7:].strip()
                
                # Try as ID first, then name
                try:
                    playlist_id = int(target)
                    playlist = manager.get_playlist(playlist_id)
                except ValueError:
                    playlist = manager.get_playlist_by_name(target)
                    if playlist:
                        playlist_id = playlist['id']
                
                if not playlist:
                    print(f"Playlist not found: {target}")
                    continue
                
                confirm = input(f"Delete playlist '{playlist['name']}'? (y/n): ")
                if confirm.lower() == 'y':
                    manager.delete_playlist(playlist_id)
                    print("Deleted")
            
            elif command == 'create':
                print("\n=== Create Smart Playlist ===")
                name = input("Playlist name: ").strip()
                if not name:
                    print("Name required")
                    continue
                
                rules = []
                print("\nAdd rules (blank line to finish):")
                print("Available fields: genre, artist, album, albumartist, year, playcount, skipcount, rating, lastplayed, length")
                print("Operators: =, !=, >, <, >=, <=, LIKE, NOT LIKE")
                
                while True:
                    field = input("  Field: ").strip()
                    if not field:
                        break
                    
                    operator = input("  Operator: ").strip()
                    if not operator:
                        break
                    
                    value = input("  Value: ").strip()
                    if not value:
                        break
                    
                    # Try to convert numeric values
                    try:
                        value = int(value)
                    except ValueError:
                        try:
                            value = float(value)
                        except ValueError:
                            pass  # Keep as string
                    
                    logic = 'AND'
                    if len(rules) > 0 or input("  Add another rule? (y/n): ").lower() == 'y':
                        logic = input("  Logic (AND/OR): ").strip().upper() or 'AND'
                    
                    rules.append({
                        'field': field,
                        'operator': operator,
                        'value': value,
                        'logic': logic
                    })
                    
                    if logic == '':
                        break
                
                if not rules:
                    print("No rules added")
                    continue
                
                sort_by = input("\nSort by (default: artist, album, disc, track): ").strip()
                if not sort_by:
                    sort_by = 'artist, album, disc, track'
                
                sort_desc = input("Sort descending? (y/n): ").lower() == 'y'
                
                limit_str = input("Limit count (blank for none): ").strip()
                limit_count = int(limit_str) if limit_str else None
                
                try:
                    playlist_id = manager.create_playlist(name, rules, sort_by, sort_desc, limit_count)
                    song_count = len(manager.generate_songs(playlist_id))
                    print(f"\nCreated playlist '{name}' (ID: {playlist_id}) with {song_count} songs")
                except Exception as e:
                    print(f"Error creating playlist: {e}")
            
            elif command == 'templates':
                print("\n=== Smart Playlist Templates ===")
                print("\n1. Most Played (top 50):")
                print("   Field: playcount, Operator: >, Value: 0")
                print("   Sort: playcount DESC, Limit: 50")
                
                print("\n2. Never Played:")
                print("   Field: playcount, Operator: =, Value: 0")
                
                print("\n3. Jazz Collection:")
                print("   Field: genre, Operator: LIKE, Value: %Jazz%")
                
                print("\n4. Recently Added (30 days):")
                print("   Field: ctime, Operator: >, Value: <current_timestamp - 30 days>")
                
                print("\n5. High Rated (4+ stars):")
                print("   Field: rating, Operator: >=, Value: 4.0")
                
                print("\n6. Long Songs (>5 min):")
                print("   Field: length, Operator: >, Value: 300")
                
                print("\n7. Often Skipped:")
                print("   Field: skipcount, Operator: >, Value: 3")
                print("   Logic: AND")
                print("   Field: playcount, Operator: <, Value: 5")
            
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
        description="Smart/dynamic playlist manager for database-powered playlists"
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
        return 0


if __name__ == "__main__":
    sys.exit(main())
