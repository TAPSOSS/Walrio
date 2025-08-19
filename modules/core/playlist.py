#!/usr/bin/env python3
"""
Playlist Manager
Copyright (c) 2025 TAPS OSS
Project: https://github.com/TAPSOSS/Walrio
Licensed under the BSD-3-Clause License (see LICENSE file for details)

A script that creates and manages M3U playlists from the audio library database.
"""

import sys
import os
import sqlite3
import argparse
from pathlib import Path
from . import metadata

# Default database path
DEFAULT_DB_PATH = "walrio_library.db"

# Supported audio file extensions
AUDIO_EXTENSIONS = {'.mp3', '.flac', '.ogg', '.wav', '.m4a', '.aac', '.wma', '.opus', '.ape', '.mpc'}

def connect_to_database(db_path):
    """
    Connect to the SQLite database and return connection.
    
    Args:
        db_path (str): Path to the SQLite database file.
        
    Returns:
        sqlite3.Connection or None: Database connection object, or None if connection fails.
    """
    if not os.path.exists(db_path):
        print(f"Error: Database file '{db_path}' not found.")
        print("Please run database.py first to create the database.")
        return None
    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row  # Enable dict-like access to rows
        return conn
    except sqlite3.Error as e:
        print(f"Error connecting to database: {e}")
        return None

def get_songs_from_database(conn, filters=None):
    """
    Get songs from database based on filters.
    
    Args:
        conn (sqlite3.Connection): Database connection object.
        filters (dict, optional): Dictionary with filter criteria.
            Supported keys: 'artist', 'album', 'genre' (all use partial matching).
            
    Returns:
        list: List of song records as sqlite3.Row objects.
    """
    cursor = conn.cursor()
    
    # Base query
    query = """
        SELECT id, title, artist, album, albumartist, url, length, track, disc, year, genre
        FROM songs
        WHERE unavailable = 0
    """
    params = []
    
    # Apply filters if provided
    if filters:
        if filters.get('artist'):
            query += " AND (artist LIKE ? OR albumartist LIKE ?)"
            artist_filter = f"%{filters['artist']}%"
            params.extend([artist_filter, artist_filter])
        
        if filters.get('album'):
            query += " AND album LIKE ?"
            params.append(f"%{filters['album']}%")
        
        if filters.get('genre'):
            query += " AND genre LIKE ?"
            params.append(f"%{filters['genre']}%")
    
    # Order by artist, album, disc, track for logical playback order
    query += " ORDER BY artist, album, disc, track"
    
    try:
        cursor.execute(query, params)
        return cursor.fetchall()
    except sqlite3.Error as e:
        print(f"Error querying database: {e}")
        return []

def format_song_info(song):
    """
    Format song information for display.
    
    Args:
        song (dict or sqlite3.Row): Song record with metadata.
        
    Returns:
        str: Formatted song information string with track number, artist, title, album, and duration.
    """
    artist = song['artist'] or "Unknown Artist"
    title = song['title'] or "Unknown Title"
    album = song['album'] or "Unknown Album"
    
    # Format duration
    duration = ""
    if song['length']:
        minutes = song['length'] // 60
        seconds = song['length'] % 60
        duration = f" [{minutes}:{seconds:02d}]"
    
    # Format track number
    track = ""
    if song['track']:
        track = f"{song['track']:02d}. "
    
    return f"{track}{artist} - {title} ({album}){duration}"

def get_relative_path(file_path, playlist_path):
    """
    Convert file path to relative path from playlist location.
    
    Args:
        file_path (str): Path to the audio file.
        playlist_path (str): Path to the playlist file.
        
    Returns:
        str: Relative path from playlist directory to audio file.
    """
    # Remove file:// prefix if present
    if file_path.startswith('file://'):
        file_path = file_path[7:]
    
    try:
        file_path = Path(file_path).resolve()
        playlist_dir = Path(playlist_path).parent.resolve()
        return os.path.relpath(file_path, playlist_dir)
    except (ValueError, OSError):
        # If relative path calculation fails, return original path
        return file_path

def create_m3u_playlist(songs, playlist_path, use_absolute_paths=False, playlist_name="Playlist"):
    """
    Create M3U playlist file from a list of songs.
    
    Args:
        songs (list): List of song dictionaries or database records.
        playlist_path (str): Path where the playlist file will be saved.
        use_absolute_paths (bool, optional): Use absolute paths instead of relative. Defaults to False.
        playlist_name (str, optional): Name of the playlist. Defaults to "Playlist".
        
    Returns:
        bool: True if playlist created successfully, False otherwise.
    """
    try:
        # Ensure directory exists
        playlist_dir = Path(playlist_path).parent
        playlist_dir.mkdir(parents=True, exist_ok=True)
        
        with open(playlist_path, 'w', encoding='utf-8') as f:
            # Write M3U header
            f.write("#EXTM3U\n")
            f.write(f"#PLAYLIST:{playlist_name}\n")
            f.write(f"#EXTENC:UTF-8\n")
            f.write(f"# Generated by Walrio Playlist Manager\n")
            f.write(f"# Total tracks: {len(songs)}\n\n")
            
            for song in songs:
                # Get file path
                file_path = song['url']
                if file_path.startswith('file://'):
                    file_path = file_path[7:]  # Remove 'file://' prefix
                
                # Use absolute or relative path based on option
                if use_absolute_paths:
                    path_to_write = os.path.abspath(file_path)
                else:
                    path_to_write = get_relative_path(song['url'], playlist_path)
                
                # Write song info
                artist = song['artist'] or "Unknown Artist"
                title = song['title'] or "Unknown Title"
                length = song['length'] or -1
                
                f.write(f"#EXTINF:{length},{artist} - {title}\n")
                f.write(f"{path_to_write}\n")
        
        return True
    except Exception as e:
        print(f"Error creating playlist: {e}")
        return False

def load_m3u_playlist(playlist_path):
    """
    Load songs from M3U playlist file.
    
    Args:
        playlist_path (str): Path to the M3U playlist file.
        
    Returns:
        list: List of song dictionaries parsed from the playlist.
    """
    songs = []
    try:
        with open(playlist_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        
        current_info = {}
        for line in lines:
            line = line.strip()
            
            # Skip empty lines and comments (except EXTINF)
            if not line or (line.startswith('#') and not line.startswith('#EXTINF')):
                continue
            
            # Parse EXTINF line
            if line.startswith('#EXTINF:'):
                # Format: #EXTINF:duration,artist - title
                try:
                    parts = line[8:].split(',', 1)  # Remove #EXTINF: and split on first comma
                    duration = int(parts[0]) if parts[0].isdigit() else 0
                    if len(parts) > 1 and ' - ' in parts[1]:
                        artist, title = parts[1].split(' - ', 1)
                        current_info = {
                            'artist': artist.strip(),
                            'title': title.strip(),
                            'length': duration
                        }
                except (ValueError, IndexError):
                    current_info = {}
            else:
                # This should be a file path
                file_path = line
                
                # Convert relative path to absolute if needed
                if not os.path.isabs(file_path):
                    playlist_dir = Path(playlist_path).parent
                    file_path = os.path.abspath(os.path.join(playlist_dir, file_path))
                
                # Create song entry
                song = {
                    'url': file_path,
                    'artist': current_info.get('artist', 'Unknown Artist'),
                    'title': current_info.get('title', 'Unknown Title'),
                    'album': 'Unknown Album',
                    'albumartist': current_info.get('artist', 'Unknown Artist'),
                    'length': current_info.get('length', 0),
                    'track': 0,
                    'disc': 0,
                    'year': 0,
                    'genre': 'Unknown'
                }
                songs.append(song)
                current_info = {}
        
        return songs
    except Exception as e:
        print(f"Error loading playlist: {e}")
        return []

def extract_metadata(file_path):
    """
    Extract metadata from audio file using the centralized metadata module.
    
    Args:
        file_path (str): Path to the audio file.
        
    Returns:
        dict or None: Dictionary containing extracted metadata, or None if extraction fails.
            Keys include: url, title, artist, album, albumartist, length, track,
            disc, year, genre.
    """
    try:
        return metadata.extract_metadata_for_playlist(file_path)
    except Exception as e:
        print(f"Warning: Could not extract metadata from {file_path}: {e}")
        return {
            'url': file_path,
            'title': Path(file_path).stem,
            'artist': 'Unknown Artist',
            'album': 'Unknown Album',
            'albumartist': 'Unknown Artist',
            'length': 0,
            'track': 0,
            'disc': 0,
            'year': 0,
            'genre': 'Unknown'
        }

def scan_directory(directory_path):
    """
    Scan directory recursively for audio files.
    
    Args:
        directory_path (str): Path to the directory to scan.
        
    Returns:
        list: List of audio file paths found in the directory.
    """
    audio_files = []
    try:
        directory = Path(directory_path)
        if not directory.exists():
            print(f"Error: Directory '{directory_path}' does not exist.")
            return []
        
        if not directory.is_dir():
            print(f"Error: '{directory_path}' is not a directory.")
            return []
        
        # Recursively find audio files
        for file_path in directory.rglob('*'):
            if file_path.is_file() and file_path.suffix.lower() in AUDIO_EXTENSIONS:
                audio_files.append(str(file_path))
        
        # Sort files for consistent ordering
        audio_files.sort()
        return audio_files
    except Exception as e:
        print(f"Error scanning directory '{directory_path}': {e}")
        return []

def create_playlist_from_inputs(inputs, playlist_path, use_absolute_paths=False, playlist_name="Playlist"):
    """
    Create playlist from list of files and folders.
    
    Args:
        inputs (list): List of file paths and/or directory paths.
        playlist_path (str): Path where the playlist file will be saved.
        use_absolute_paths (bool, optional): Use absolute paths instead of relative. Defaults to False.
        playlist_name (str, optional): Name of the playlist. Defaults to "Playlist".
        
    Returns:
        bool: True if playlist created successfully, False otherwise.
    """
    songs = []
    
    for input_path in inputs:
        input_path = input_path.strip()
        if not input_path:
            continue
        
        path = Path(input_path)
        if not path.exists():
            print(f"Warning: Path '{input_path}' does not exist. Skipping.")
            continue
        
        if path.is_file():
            # Check if it's an audio file
            if path.suffix.lower() in AUDIO_EXTENSIONS:
                metadata = extract_metadata(str(path))
                if metadata:
                    songs.append(metadata)
            else:
                print(f"Warning: '{input_path}' is not a supported audio file. Skipping.")
        elif path.is_dir():
            # Scan directory for audio files
            audio_files = scan_directory(str(path))
            print(f"Found {len(audio_files)} audio files in '{input_path}'")
            
            for audio_file in audio_files:
                metadata = extract_metadata(audio_file)
                if metadata:
                    songs.append(metadata)
        else:
            print(f"Warning: '{input_path}' is neither a file nor directory. Skipping.")
    
    if not songs:
        print("No audio files found from the provided inputs.")
        return False
    
    print(f"Creating playlist with {len(songs)} songs...")
    return create_m3u_playlist(songs, playlist_path, use_absolute_paths, playlist_name)

def main():
    """
    Main function for playlist management command-line interface.
    
    Parses command-line arguments and performs playlist operations including
    creating playlists from database queries, files/directories, or loading
    existing playlists.
    
    Examples:
        Create playlist from database with artist filter:
            python playlist.py --name "My Playlist" --artist "Pink Floyd" --output playlists/
            
        Create playlist from files and directories:
            python playlist.py --name "Files" --inputs song1.mp3 song2.flac /path/to/music/
            
        Create playlist from input file:
            python playlist.py --name "From File" --input-file mylist.txt --output playlists/
            
        Load and display existing playlist:
            python playlist.py --load existing_playlist.m3u
    """
    parser = argparse.ArgumentParser(
        description="Playlist Manager - Create and manage M3U playlists",
        epilog="Examples:\n"
               "  python playlist.py --name \"My Playlist\" --artist \"Pink Floyd\" --output playlists/\n"
               "  python playlist.py --name \"Files\" --inputs song1.mp3 song2.flac /path/to/music/\n"
               "  python playlist.py --name \"From File\" --input-file mylist.txt --output playlists/",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "--db-path",
        default=DEFAULT_DB_PATH,
        help=f"Path to the SQLite database file (default: {DEFAULT_DB_PATH})"
    )
    parser.add_argument(
        "--name",
        help="Name of the playlist (required for database mode)"
    )
    parser.add_argument(
        "--output",
        default="./",
        help="Directory to save the playlist file (default: current directory)"
    )
    parser.add_argument(
        "--absolute",
        action="store_true",
        help="Use absolute paths instead of relative paths"
    )
    parser.add_argument(
        "--artist",
        help="Filter songs by artist name (partial match)"
    )
    parser.add_argument(
        "--album",
        help="Filter songs by album name (partial match)"
    )
    parser.add_argument(
        "--genre",
        help="Filter songs by genre (partial match)"
    )
    parser.add_argument(
        "--load",
        help="Load and display contents of an existing M3U playlist"
    )
    parser.add_argument(
        "--inputs",
        nargs='+',
        help="List of audio files and/or directories to include in the playlist"
    )
    parser.add_argument(
        "--input-file",
        help="Text file containing list of audio files/directories (one per line)"
    )
    
    args = parser.parse_args()
    
    # Load playlist mode
    if args.load:
        if not os.path.exists(args.load):
            print(f"Error: Playlist file '{args.load}' not found.")
            sys.exit(1)
        
        songs = load_m3u_playlist(args.load)
        if songs:
            print(f"Loaded {len(songs)} songs from playlist '{args.load}':")
            for i, song in enumerate(songs):
                print(f"  {i+1:3d}. {format_song_info(song)}")
        else:
            print("No songs found in playlist.")
        return
    
    # File/folder input mode
    if args.inputs or args.input_file:
        if not args.name:
            print("Error: --name is required when creating playlists from inputs.")
            sys.exit(1)
        
        inputs = []
        
        # Get inputs from command line
        if args.inputs:
            inputs.extend(args.inputs)
        
        # Get inputs from file
        if args.input_file:
            if not os.path.exists(args.input_file):
                print(f"Error: Input file '{args.input_file}' not found.")
                sys.exit(1)
            
            try:
                with open(args.input_file, 'r', encoding='utf-8') as f:
                    for line in f:
                        line = line.strip()
                        if line and not line.startswith('#'):  # Skip empty lines and comments
                            inputs.append(line)
            except Exception as e:
                print(f"Error reading input file: {e}")
                sys.exit(1)
        
        if not inputs:
            print("Error: No inputs provided.")
            sys.exit(1)
        
        # Create playlist filename
        safe_name = "".join(c if c.isalnum() or c in (' ', '-', '_') else '' for c in args.name)
        safe_name = safe_name.replace(' ', '_')
        playlist_filename = f"{safe_name}.m3u"
        playlist_path = os.path.join(args.output, playlist_filename)
        
        # Create playlist from inputs
        success = create_playlist_from_inputs(inputs, playlist_path, args.absolute, args.name)
        
        if success:
            print(f"Playlist '{args.name}' created successfully!")
            print(f"Saved to: {playlist_path}")
            print(f"Path format: {'Absolute' if args.absolute else 'Relative'}")
        else:
            print("Failed to create playlist.")
            sys.exit(1)
        
        return
    
    # Database mode (existing functionality)
    if not args.name:
        print("Error: --name is required.")
        sys.exit(1)
    
    # Connect to database
    conn = connect_to_database(args.db_path)
    if not conn:
        sys.exit(1)
    
    try:
        # Build filters from command line arguments
        filters = {}
        if args.artist:
            filters['artist'] = args.artist
        if args.album:
            filters['album'] = args.album
        if args.genre:
            filters['genre'] = args.genre
        
        # Get songs from database
        songs = get_songs_from_database(conn, filters)
        
        if not songs:
            print("No songs found matching the specified criteria.")
            sys.exit(1)
        
        print(f"Found {len(songs)} songs matching criteria.")
        
        # Create playlist filename
        safe_name = "".join(c if c.isalnum() or c in (' ', '-', '_') else '' for c in args.name)
        safe_name = safe_name.replace(' ', '_')
        playlist_filename = f"{safe_name}.m3u"
        playlist_path = os.path.join(args.output, playlist_filename)
        
        # Create playlist
        success = create_m3u_playlist(songs, playlist_path, args.absolute, args.name)
        
        if success:
            print(f"Playlist '{args.name}' created successfully!")
            print(f"Saved to: {playlist_path}")
            print(f"Contains {len(songs)} songs")
            print(f"Path format: {'Absolute' if args.absolute else 'Relative'}")
        else:
            print("Failed to create playlist.")
            sys.exit(1)
            
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)
    finally:
        conn.close()

# Run file
if __name__ == "__main__":
    main()
