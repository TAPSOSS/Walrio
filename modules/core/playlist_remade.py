#!/usr/bin/env python3
import sys
import os
import sqlite3
import argparse
from pathlib import Path
from . import metadata

# Supported audio extensions
AUDIO_EXTENSIONS = {'.mp3', '.flac', '.ogg', '.oga', '.opus', '.m4a', '.mp4', '.aac', '.wv', '.ape', '.mpc', '.wav'}

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
    
    query += " ORDER BY artist, album, track"
    cursor.execute(query, params)
    return cursor.fetchall()

def format_song_info(song):
    """Format song information for display."""
    track = song['track'] if 'track' in song.keys() else 0
    artist = song['artist'] if 'artist' in song.keys() else 'Unknown'
    title = song['title'] if 'title' in song.keys() else 'Unknown'
    album = song['album'] if 'album' in song.keys() else 'Unknown'
    length = song['length'] if 'length' in song.keys() else 0
    
    minutes = int(length // 60)
    seconds = int(length % 60)
    
    return f"{track:02d}. {artist} - {title} [{album}] ({minutes}:{seconds:02d})"

def get_relative_path(file_path, playlist_path):
    """Convert file path to relative path from playlist location."""
    try:
        file_p = Path(file_path).resolve()
        playlist_dir = Path(playlist_path).parent.resolve()
        return os.path.relpath(file_p, playlist_dir)
    except:
        return file_path

def create_m3u_playlist(songs, playlist_path, use_absolute_paths=False, playlist_name="Playlist"):
    """Create M3U playlist file from a list of songs."""
    try:
        with open(playlist_path, 'w', encoding='utf-8') as f:
            f.write("#EXTM3U\n")
            f.write(f"#PLAYLIST:{playlist_name}\n")
            
            for song in songs:
                # Get file path
                if 'url' in song and song['url']:
                    file_path = song['url']
                    if file_path.startswith('file://'):
                        file_path = file_path[7:]
                elif 'filepath' in song:
                    file_path = song['filepath']
                else:
                    continue
                
                # Get metadata
                title = song.get('title', Path(file_path).stem)
                artist = song.get('artist', 'Unknown Artist')
                length = int(song.get('length', 0))
                
                # Write EXTINF line
                f.write(f"#EXTINF:{length},{artist} - {title}\n")
                
                # Write file path (relative or absolute)
                if use_absolute_paths:
                    f.write(f"{file_path}\n")
                else:
                    rel_path = get_relative_path(file_path, playlist_path)
                    f.write(f"{rel_path}\n")
        
        print(f"Playlist created: {playlist_path} ({len(songs)} songs)")
        return True
    except Exception as e:
        print(f"Error creating playlist: {e}")
        return False

def load_m3u_playlist(playlist_path):
    """Load songs from M3U playlist file."""
    if not os.path.exists(playlist_path):
        print(f"Error: Playlist not found: {playlist_path}")
        return []
    
    songs = []
    playlist_dir = Path(playlist_path).parent
    
    try:
        with open(playlist_path, 'r', encoding='utf-8') as f:
            current_info = {}
            
            for line in f:
                line = line.strip()
                
                if line.startswith('#EXTINF:'):
                    # Parse EXTINF line: #EXTINF:duration,artist - title
                    parts = line[8:].split(',', 1)
                    if len(parts) == 2:
                        try:
                            current_info['length'] = int(parts[0])
                        except:
                            current_info['length'] = 0
                        
                        # Try to parse artist - title
                        if ' - ' in parts[1]:
                            artist, title = parts[1].split(' - ', 1)
                            current_info['artist'] = artist.strip()
                            current_info['title'] = title.strip()
                        else:
                            current_info['title'] = parts[1].strip()
                
                elif line and not line.startswith('#'):
                    # This is a file path
                    file_path = line
                    
                    # Convert relative paths to absolute
                    if not os.path.isabs(file_path):
                        file_path = os.path.abspath(os.path.join(playlist_dir, file_path))
                    
                    # Create song entry
                    song = {
                        'url': f"file://{file_path}",
                        'filepath': file_path,
                        'title': current_info.get('title', Path(file_path).stem),
                        'artist': current_info.get('artist', 'Unknown Artist'),
                        'album': 'Unknown Album',
                        'length': current_info.get('length', 0)
                    }
                    songs.append(song)
                    current_info = {}
        
        return songs
    except Exception as e:
        print(f"Error loading playlist: {e}")
        return []

def extract_metadata(file_path):
    """Extract metadata from audio file using the centralized metadata module."""
    try:
        meta = metadata.extract_metadata_for_playlist(file_path)
        return meta if meta else None
    except:
        return None

def scan_directory(directory_path):
    """Scan directory recursively for audio files."""
    audio_files = []
    
    for root, dirs, files in os.walk(directory_path):
        for file in sorted(files):
            file_path = os.path.join(root, file)
            if Path(file_path).suffix.lower() in AUDIO_EXTENSIONS:
                audio_files.append(file_path)
    
    return audio_files

def create_playlist_from_inputs(inputs, playlist_path, use_absolute_paths=False, playlist_name="Playlist"):
    """Create playlist from list of files and folders."""
    songs = []
    
    for input_path in inputs:
        if not os.path.exists(input_path):
            print(f"Warning: Path not found: {input_path}")
            continue
        
        if os.path.isfile(input_path):
            # Single file
            if Path(input_path).suffix.lower() in AUDIO_EXTENSIONS:
                meta = extract_metadata(input_path)
                if meta:
                    songs.append(meta)
                else:
                    # Add without metadata
                    songs.append({
                        'url': f"file://{input_path}",
                        'filepath': input_path,
                        'title': Path(input_path).stem,
                        'artist': 'Unknown Artist',
                        'album': 'Unknown Album',
                        'length': 0
                    })
        elif os.path.isdir(input_path):
            # Directory - scan recursively
            print(f"Scanning directory: {input_path}")
            audio_files = scan_directory(input_path)
            
            for file_path in audio_files:
                meta = extract_metadata(file_path)
                if meta:
                    songs.append(meta)
                else:
                    songs.append({
                        'url': f"file://{file_path}",
                        'filepath': file_path,
                        'title': Path(file_path).stem,
                        'artist': 'Unknown Artist',
                        'album': 'Unknown Album',
                        'length': 0
                    })
    
    if not songs:
        print("No songs found in specified inputs.")
        return False
    
    return create_m3u_playlist(songs, playlist_path, use_absolute_paths, playlist_name)

def main():
    """Main function for playlist management command-line interface."""
    parser = argparse.ArgumentParser(
        description='Playlist Manager - Create and manage M3U playlists',
        epilog='Examples:\n'
               '  python playlist.py --name "My Playlist" --artist "Pink Floyd" --output playlists/\n'
               '  python playlist.py --name "Files" --inputs song1.mp3 /path/to/music/\n'
               '  python playlist.py --load existing_playlist.m3u',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    # Playlist creation options
    parser.add_argument('--name', help='Name of the playlist')
    parser.add_argument('--output', '-o', help='Output directory or full path for playlist file')
    parser.add_argument('--absolute', action='store_true', help='Use absolute paths instead of relative')
    
    # Database query options
    parser.add_argument('--db', default='walrio_library.db', help='Path to database file')
    parser.add_argument('--artist', help='Filter by artist (partial match)')
    parser.add_argument('--album', help='Filter by album (partial match)')
    parser.add_argument('--genre', help='Filter by genre (partial match)')
    
    # File/directory input options
    parser.add_argument('--inputs', nargs='+', help='Files or directories to include in playlist')
    parser.add_argument('--input-file', help='Text file containing list of files (one per line)')
    
    # Load existing playlist
    parser.add_argument('--load', help='Load and display existing M3U playlist')
    
    args = parser.parse_args()
    
    # Load existing playlist
    if args.load:
        songs = load_m3u_playlist(args.load)
        if songs:
            print(f"\nPlaylist: {args.load}")
            print(f"Total songs: {len(songs)}\n")
            for i, song in enumerate(songs[:20], 1):
                print(f"{i}. {song.get('artist', 'Unknown')} - {song.get('title', 'Unknown')}")
            if len(songs) > 20:
                print(f"\n... and {len(songs) - 20} more songs")
        return 0 if songs else 1
    
    # Validate name and output
    if not args.name:
        print("Error: --name is required for playlist creation")
        return 1
    
    # Determine output path
    if args.output:
        if os.path.isdir(args.output):
            output_path = os.path.join(args.output, f"{args.name}.m3u")
        else:
            output_path = args.output
    else:
        output_path = f"{args.name}.m3u"
    
    # Create playlist from database or inputs
    if args.inputs or args.input_file:
        # Create from files/directories
        inputs = args.inputs or []
        
        if args.input_file:
            if os.path.exists(args.input_file):
                with open(args.input_file, 'r') as f:
                    inputs.extend([line.strip() for line in f if line.strip()])
            else:
                print(f"Error: Input file not found: {args.input_file}")
                return 1
        
        if create_playlist_from_inputs(inputs, output_path, args.absolute, args.name):
            return 0
        else:
            return 1
    else:
        # Create from database
        conn = connect_to_database(args.db)
        if not conn:
            return 1
        
        # Build filters
        filters = {}
        if args.artist:
            filters['artist'] = args.artist
        if args.album:
            filters['album'] = args.album
        if args.genre:
            filters['genre'] = args.genre
        
        # Get songs
        songs = get_songs_from_database(conn, filters)
        conn.close()
        
        if not songs:
            print("No songs found matching the specified criteria.")
            return 1
        
        print(f"Found {len(songs)} songs")
        
        if create_m3u_playlist(songs, output_path, args.absolute, args.name):
            return 0
        else:
            return 1

if __name__ == '__main__':
    sys.exit(main())
