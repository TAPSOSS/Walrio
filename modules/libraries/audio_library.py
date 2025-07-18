#!/usr/bin/env python3
"""
Audio Library Analyzer

Copyright (c) 2025 TAPS OSS
Project: https://github.com/TAPSOSS/Walrio
Licensed under the BSD-3-Clause License (see LICENSE file for details)

A script that analyzes audio files in a directory and stores metadata in SQLite database.
Sample Usage: python audio_library.py <directory_path> [--db-path <database_path>]
"""

import sys
import os
import sqlite3
import argparse
import hashlib
import time
from pathlib import Path
from mutagen import File
from mutagen.id3 import ID3NoHeaderError

# Import playlist loading function
try:
    from playlist import load_m3u_playlist
except ImportError:
    print("Warning: playlist.py not found. Playlist loading functionality will be disabled.")
    load_m3u_playlist = None

# Supported audio file extensions
AUDIO_EXTENSIONS = {'.mp3', '.flac', '.ogg', '.wav', '.m4a', '.aac', '.wma', '.opus', '.ape', '.mpc'}

def create_database(db_path):
    # Create the SQLite database with music library schema
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Create main songs table heavily based on Strawberry Music Player schema (https://github.com/strawberrymusicplayer/strawberry)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS songs (
            -- Basic metadata
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT,
            album TEXT,
            artist TEXT,
            albumartist TEXT,
            track INTEGER,
            disc INTEGER,
            year INTEGER,
            originalyear INTEGER,
            genre TEXT,
            composer TEXT,
            performer TEXT,
            grouping TEXT,
            comment TEXT,
            lyrics TEXT,
            
            -- File information
            url TEXT UNIQUE,
            directory_id INTEGER,
            basefilename TEXT,
            filetype TEXT,
            filesize INTEGER,
            mtime INTEGER,
            ctime INTEGER,
            unavailable INTEGER DEFAULT 0,
            
            -- Audio properties
            length INTEGER,  -- duration in seconds
            bitrate INTEGER,
            samplerate INTEGER,
            bitdepth INTEGER,
            
            -- User data
            playcount INTEGER DEFAULT 0,
            skipcount INTEGER DEFAULT 0,
            lastplayed INTEGER DEFAULT 0,
            lastseen INTEGER,
            rating REAL DEFAULT 0.0,
            
            -- Compilation handling
            compilation INTEGER DEFAULT 0,
            compilation_detected INTEGER DEFAULT 0,
            compilation_on INTEGER DEFAULT 0,
            compilation_off INTEGER DEFAULT 0,
            
            -- Album art
            art_embedded INTEGER DEFAULT 0,
            art_automatic TEXT,
            art_manual TEXT,
            art_unset INTEGER DEFAULT 0,
            
            -- Identifiers
            artist_id TEXT,
            album_id TEXT,
            song_id TEXT,
            fingerprint TEXT,
            
            -- MusicBrainz IDs
            musicbrainz_album_artist_id TEXT,
            musicbrainz_artist_id TEXT,
            musicbrainz_original_artist_id TEXT,
            musicbrainz_album_id TEXT,
            musicbrainz_original_album_id TEXT,
            musicbrainz_recording_id TEXT,
            musicbrainz_track_id TEXT,
            musicbrainz_disc_id TEXT,
            musicbrainz_release_group_id TEXT,
            musicbrainz_work_id TEXT,
            
            -- Other
            source INTEGER DEFAULT 1,  -- 1 = LocalFile, 2 = Collection
            cue_path TEXT
        )
    ''')
    
    # Create directories table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS directories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            path TEXT UNIQUE,
            subdirs INTEGER DEFAULT 0,
            mtime INTEGER
        )
    ''')
    
    # Create indexes for better performance
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_songs_artist ON songs(artist)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_songs_album ON songs(album)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_songs_title ON songs(title)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_songs_url ON songs(url)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_songs_directory_id ON songs(directory_id)')
    
    conn.commit()
    return conn

# Generate a simple hash for the file based on path and size
def get_file_hash(filepath):
    stat = os.stat(filepath)
    hash_string = f"{filepath}:{stat.st_size}:{stat.st_mtime}"
    return hashlib.md5(hash_string.encode()).hexdigest()

#Extract metadata from audio file using mutagen
def extract_metadata(filepath):
    try:
        audio_file = File(filepath)
        if audio_file is None:
            return None
            
        metadata = {
            'title': '',
            'album': '',
            'artist': '',
            'albumartist': '',
            'track': 0,
            'disc': 0,
            'year': 0,
            'originalyear': 0,
            'genre': '',
            'composer': '',
            'performer': '',
            'grouping': '',
            'comment': '',
            'lyrics': '',
            'length': 0,
            'bitrate': 0,
            'samplerate': 0,
            'bitdepth': 0,
            'compilation': 0,
            'art_embedded': 0
        }
        
        # Extract basic metadata
        if audio_file.get('TIT2'):  # ID3v2 title
            metadata['title'] = str(audio_file['TIT2'][0])
        elif audio_file.get('TITLE'):  # Vorbis comment
            metadata['title'] = str(audio_file['TITLE'][0])
        elif audio_file.get('\xa9nam'):  # MP4
            metadata['title'] = str(audio_file['\xa9nam'][0])
            
        if audio_file.get('TALB'):  # Album
            metadata['album'] = str(audio_file['TALB'][0])
        elif audio_file.get('ALBUM'):
            metadata['album'] = str(audio_file['ALBUM'][0])
        elif audio_file.get('\xa9alb'):
            metadata['album'] = str(audio_file['\xa9alb'][0])
            
        if audio_file.get('TPE1'):  # Artist
            metadata['artist'] = str(audio_file['TPE1'][0])
        elif audio_file.get('ARTIST'):
            metadata['artist'] = str(audio_file['ARTIST'][0])
        elif audio_file.get('\xa9ART'):
            metadata['artist'] = str(audio_file['\xa9ART'][0])
            
        if audio_file.get('TPE2'):  # Album artist
            metadata['albumartist'] = str(audio_file['TPE2'][0])
        elif audio_file.get('ALBUMARTIST'):
            metadata['albumartist'] = str(audio_file['ALBUMARTIST'][0])
        elif audio_file.get('aART'):
            metadata['albumartist'] = str(audio_file['aART'][0])
            
        # Track number
        if audio_file.get('TRCK'):
            track_str = str(audio_file['TRCK'][0])
            metadata['track'] = int(track_str.split('/')[0]) if track_str else 0
        elif audio_file.get('TRACKNUMBER'):
            metadata['track'] = int(audio_file['TRACKNUMBER'][0])
        elif audio_file.get('trkn'):
            metadata['track'] = int(audio_file['trkn'][0][0])
            
        # Disc number
        if audio_file.get('TPOS'):
            disc_str = str(audio_file['TPOS'][0])
            metadata['disc'] = int(disc_str.split('/')[0]) if disc_str else 0
        elif audio_file.get('DISCNUMBER'):
            metadata['disc'] = int(audio_file['DISCNUMBER'][0])
        elif audio_file.get('disk'):
            metadata['disc'] = int(audio_file['disk'][0][0])
            
        # Year
        if audio_file.get('TDRC'):  # Recording date
            year_str = str(audio_file['TDRC'][0])
            metadata['year'] = int(year_str[:4]) if len(year_str) >= 4 else 0
        elif audio_file.get('DATE'):
            year_str = str(audio_file['DATE'][0])
            metadata['year'] = int(year_str[:4]) if len(year_str) >= 4 else 0
        elif audio_file.get('\xa9day'):
            year_str = str(audio_file['\xa9day'][0])
            metadata['year'] = int(year_str[:4]) if len(year_str) >= 4 else 0
            
        # Genre
        if audio_file.get('TCON'):
            metadata['genre'] = str(audio_file['TCON'][0])
        elif audio_file.get('GENRE'):
            metadata['genre'] = str(audio_file['GENRE'][0])
        elif audio_file.get('\xa9gen'):
            metadata['genre'] = str(audio_file['\xa9gen'][0])
            
        # Composer
        if audio_file.get('TCOM'):
            metadata['composer'] = str(audio_file['TCOM'][0])
        elif audio_file.get('COMPOSER'):
            metadata['composer'] = str(audio_file['COMPOSER'][0])
        elif audio_file.get('\xa9wrt'):
            metadata['composer'] = str(audio_file['\xa9wrt'][0])
            
        # Comment
        if audio_file.get('COMM'):
            metadata['comment'] = str(audio_file['COMM'][0])
        elif audio_file.get('COMMENT'):
            metadata['comment'] = str(audio_file['COMMENT'][0])
        elif audio_file.get('\xa9cmt'):
            metadata['comment'] = str(audio_file['\xa9cmt'][0])
            
        # Audio properties
        if hasattr(audio_file, 'info'):
            info = audio_file.info
            metadata['length'] = int(info.length) if hasattr(info, 'length') else 0
            metadata['bitrate'] = int(info.bitrate) if hasattr(info, 'bitrate') else 0
            metadata['samplerate'] = int(info.sample_rate) if hasattr(info, 'sample_rate') else 0
            
        # Check for embedded artwork
        if hasattr(audio_file, 'tags') and audio_file.tags:
            # Check for various artwork tags
            artwork_tags = ['APIC', 'APIC:', 'covr', 'METADATA_BLOCK_PICTURE']
            for tag in artwork_tags:
                if tag in audio_file.tags:
                    metadata['art_embedded'] = 1
                    break
                    
        # Use filename as title if no title found
        if not metadata['title']:
            metadata['title'] = Path(filepath).stem
            
        return metadata
        
    except Exception as e:
        print(f"Error extracting metadata from {filepath}: {e}")
        return None

# Scan directory for audio files and add to database
def scan_directory(directory_path, conn):
    cursor = conn.cursor()
    
    # Add directory to directories table
    dir_stat = os.stat(directory_path)
    cursor.execute('''
        INSERT OR IGNORE INTO directories (path, mtime) 
        VALUES (?, ?)
    ''', (str(directory_path), int(dir_stat.st_mtime)))
    
    # Get directory ID
    cursor.execute('SELECT id FROM directories WHERE path = ?', (str(directory_path),))
    directory_id = cursor.fetchone()[0]
    
    audio_files_found = 0
    audio_files_processed = 0
    
    print(f"Scanning directory: {directory_path}")
    
    # Walk through directory recursively
    for root, dirs, files in os.walk(directory_path):
        for file in files:
            filepath = os.path.join(root, file)
            file_ext = Path(filepath).suffix.lower()
            
            # Check if it's an audio file
            if file_ext in AUDIO_EXTENSIONS:
                audio_files_found += 1
                
                # Get file stats
                try:
                    stat = os.stat(filepath)
                    file_url = f"file://{filepath}"
                    
                    # Check if file already exists in database
                    cursor.execute('SELECT id FROM songs WHERE url = ?', (file_url,))
                    existing = cursor.fetchone()
                    
                    if existing:
                        print(f"Skipping (already in database): {filepath}")
                        continue
                    
                    print(f"Processing: {filepath}")
                    
                    # Extract metadata
                    metadata = extract_metadata(filepath)
                    if metadata is None:
                        print(f"Warning: Could not extract metadata from {filepath}")
                        continue
                    
                    # Generate IDs
                    fingerprint = get_file_hash(filepath)
                    song_id = fingerprint
                    artist_id = hashlib.md5(metadata['artist'].encode()).hexdigest() if metadata['artist'] else ''
                    album_id = hashlib.md5(f"{metadata['albumartist'] or metadata['artist']}:{metadata['album']}".encode()).hexdigest() if metadata['album'] else ''
                    
                    # Check if song already exists in database
                    cursor.execute('SELECT id FROM songs WHERE url = ?', (file_url,))
                    existing_song = cursor.fetchone()
                    
                    if existing_song:
                        # Update lastseen timestamp for existing song
                        cursor.execute('UPDATE songs SET lastseen = ? WHERE id = ?', (int(time.time()), existing_song[0]))
                        continue
                    
                    # Insert into database
                    cursor.execute('''
                        INSERT INTO songs (
                            title, album, artist, albumartist, track, disc, year, originalyear,
                            genre, composer, performer, grouping, comment, lyrics,
                            url, directory_id, basefilename, filetype, filesize, mtime, ctime,
                            length, bitrate, samplerate, bitdepth,
                            compilation, art_embedded, fingerprint, song_id, artist_id, album_id,
                            lastseen, source
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ''', (
                        metadata['title'], metadata['album'], metadata['artist'], metadata['albumartist'],
                        metadata['track'], metadata['disc'], metadata['year'], metadata['originalyear'],
                        metadata['genre'], metadata['composer'], metadata['performer'], metadata['grouping'],
                        metadata['comment'], metadata['lyrics'],
                        file_url, directory_id, Path(filepath).name, file_ext[1:], stat.st_size,
                        int(stat.st_mtime), int(stat.st_ctime),
                        metadata['length'], metadata['bitrate'], metadata['samplerate'], metadata['bitdepth'],
                        metadata['compilation'], metadata['art_embedded'], fingerprint, song_id, artist_id, album_id,
                        int(time.time()), 2  # source = 2 (Collection)
                    ))
                    
                    audio_files_processed += 1
                    
                except Exception as e:
                    print(f"Error processing {filepath}: {e}")
                    continue
    
    conn.commit()
    
    print(f"\nScan complete!")
    print(f"Audio files found: {audio_files_found}")
    print(f"Audio files processed: {audio_files_processed}")
    print(f"Database updated: {audio_files_processed} songs added")

# Load songs from playlist and add to database
def load_playlist_to_database(playlist_path, conn):
    if load_m3u_playlist is None:
        print("Error: Playlist loading functionality is not available.")
        return False
    
    if not os.path.exists(playlist_path):
        print(f"Error: Playlist file '{playlist_path}' not found.")
        return False
    
    print(f"Loading playlist: {playlist_path}")
    
    # Load playlist
    songs = load_m3u_playlist(playlist_path)
    if not songs:
        print("No songs found in playlist or failed to load playlist.")
        return False
    
    print(f"Found {len(songs)} songs in playlist.")
    
    cursor = conn.cursor()
    added_count = 0
    skipped_count = 0
    
    for i, song in enumerate(songs):
        file_path = song['url']
        if file_path.startswith('file://'):
            file_path = file_path[7:]  # Remove 'file://' prefix
        
        # Convert to absolute path if relative
        if not os.path.isabs(file_path):
            playlist_dir = Path(playlist_path).parent
            file_path = os.path.abspath(os.path.join(playlist_dir, file_path))
        
        print(f"Processing [{i+1}/{len(songs)}]: {os.path.basename(file_path)}")
        
        # Check if file exists
        if not os.path.exists(file_path):
            print(f"  Warning: File not found: {file_path}")
            skipped_count += 1
            continue
        
        try:
            # Get file stats
            stat = os.stat(file_path)
            file_url = f"file://{file_path}"
            
            # Check if file already exists in database
            cursor.execute('SELECT id FROM songs WHERE url = ?', (file_url,))
            existing = cursor.fetchone()
            
            if existing:
                print(f"  Skipping (already in database): {os.path.basename(file_path)}")
                skipped_count += 1
                continue
            
            # Get directory for this file
            dir_path = str(Path(file_path).parent)
            
            # Add directory to directories table if not exists
            dir_stat = os.stat(dir_path)
            cursor.execute('''
                INSERT OR IGNORE INTO directories (path, mtime) 
                VALUES (?, ?)
            ''', (str(dir_path), int(dir_stat.st_mtime)))
            
            # Get directory ID
            cursor.execute('SELECT id FROM directories WHERE path = ?', (str(dir_path),))
            directory_id = cursor.fetchone()[0]
            
            # Extract metadata
            metadata = extract_metadata(file_path)
            if metadata is None:
                print(f"  Warning: Could not extract metadata from {file_path}")
                skipped_count += 1
                continue
            
            # Generate IDs
            fingerprint = get_file_hash(file_path)
            song_id = fingerprint
            artist_id = hashlib.md5(metadata['artist'].encode()).hexdigest() if metadata['artist'] else ''
            album_id = hashlib.md5(f"{metadata['albumartist'] or metadata['artist']}:{metadata['album']}".encode()).hexdigest() if metadata['album'] else ''
            
            # Check if song already exists in database
            cursor.execute('SELECT id FROM songs WHERE url = ?', (file_url,))
            existing_song = cursor.fetchone()
            
            if existing_song:
                print(f"  Already exists: {metadata['artist']} - {metadata['title']}")
                skipped_count += 1
                continue
            
            # Insert into database
            file_ext = Path(file_path).suffix.lower()
            cursor.execute('''
                INSERT INTO songs (
                    title, album, artist, albumartist, track, disc, year, originalyear,
                    genre, composer, performer, grouping, comment, lyrics,
                    url, directory_id, basefilename, filetype, filesize, mtime, ctime,
                    length, bitrate, samplerate, bitdepth,
                    compilation, art_embedded, fingerprint, song_id, artist_id, album_id,
                    lastseen, source
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                metadata['title'], metadata['album'], metadata['artist'], metadata['albumartist'],
                metadata['track'], metadata['disc'], metadata['year'], metadata['originalyear'],
                metadata['genre'], metadata['composer'], metadata['performer'], metadata['grouping'],
                metadata['comment'], metadata['lyrics'],
                file_url, directory_id, Path(file_path).name, file_ext[1:], stat.st_size,
                int(stat.st_mtime), int(stat.st_ctime),
                metadata['length'], metadata['bitrate'], metadata['samplerate'], metadata['bitdepth'],
                metadata['compilation'], metadata['art_embedded'], fingerprint, song_id, artist_id, album_id,
                int(time.time()), 3  # source = 3 (Playlist)
            ))
            
            added_count += 1
            print(f"  Added: {metadata['artist']} - {metadata['title']}")
                
        except Exception as e:
            print(f"  Error processing {file_path}: {e}")
            skipped_count += 1
    
    conn.commit()
    
    print(f"\nPlaylist processing complete:")
    print(f"  Added: {added_count} songs")
    print(f"  Skipped: {skipped_count} songs")
    
    return True

# Analyze audio files in directory and store related info in SQLite database
def analyze_directory(directory_path, db_path):
    # Convert to absolute path
    directory_path = os.path.abspath(directory_path)
    
    # Check if directory exists
    if not os.path.exists(directory_path):
        print(f"Error: Directory '{directory_path}' not found.")
        return False
    
    # Check that it's a directory
    if not os.path.isdir(directory_path):
        print(f"Error: '{directory_path}' is not a directory.")
        return False
    
    try:
        # Create database
        print(f"Creating/opening database: {db_path}")
        conn = create_database(db_path)
        
        # Scan directory
        scan_directory(directory_path, conn)
        
        # Print summary
        cursor = conn.cursor()
        cursor.execute('SELECT COUNT(*) FROM songs')
        total_songs = cursor.fetchone()[0]
        
        cursor.execute('SELECT COUNT(*) FROM directories')
        total_dirs = cursor.fetchone()[0]
        
        print(f"\nDatabase Summary:")
        print(f"Total songs: {total_songs}")
        print(f"Total directories: {total_dirs}")
        print(f"Database file: {db_path}")
        
        conn.close()
        return True
        
    except Exception as e:
        print(f"Error analyzing directory: {e}")
        return False

# Main function to handle command line arguments and analyze directory
def main():
    parser = argparse.ArgumentParser(
        description="Audio Library Analyzer - Scans directory for audio files and stores metadata in SQLite database",
        epilog="Examples:\n"
               "  python audio_library.py /path/to/music --db-path ~/music.db\n"
               "  python audio_library.py --playlist myplaylist.m3u --db-path ~/music.db",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    # Make directory argument optional when using playlist
    parser.add_argument(
        "directory",
        nargs='?',
        help="Path to the directory containing audio files"
    )
    parser.add_argument(
        "--db-path",
        default="walrio_library.db",
        help="Path to SQLite database file (default: walrio_library.db)"
    )
    parser.add_argument(
        "--playlist",
        help="Load songs from an M3U playlist file into the database"
    )

    # Parse arguments
    args = parser.parse_args()
    
    # Validate arguments
    if not args.directory and not args.playlist:
        print("Error: Either directory or --playlist must be specified.")
        parser.print_help()
        sys.exit(1)
    
    success = True
    
    # Handle playlist loading
    if args.playlist:
        print(f"Loading playlist into database: {args.db_path}")
        conn = create_database(args.db_path)
        success = load_playlist_to_database(args.playlist, conn)
        
        if success:
            # Print summary
            cursor = conn.cursor()
            cursor.execute('SELECT COUNT(*) FROM songs')
            total_songs = cursor.fetchone()[0]
            
            cursor.execute('SELECT COUNT(*) FROM directories')
            total_dirs = cursor.fetchone()[0]
            
            print(f"\nDatabase Summary:")
            print(f"Total songs: {total_songs}")
            print(f"Total directories: {total_dirs}")
            print(f"Database file: {args.db_path}")
        
        conn.close()
    
    # Handle directory scanning
    if args.directory:
        if args.playlist:
            print(f"\nAlso scanning directory: {args.directory}")
        else:
            print(f"Scanning directory: {args.directory}")
        
        directory_success = analyze_directory(args.directory, args.db_path)
        success = success and directory_success
    
    # Exit with appropriate code for success or failure
    sys.exit(0 if success else 1)

# Run file
if __name__ == "__main__":
    main()
