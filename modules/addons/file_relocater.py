#!/usr/bin/env python3
"""
relocate audio files into organized folders based on their metadata
"""

import argparse
import json
import logging
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Optional, Any

# Add parent directory for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

try:
    from addons.playlist_updater import PlaylistUpdater
except ImportError:
    PlaylistUpdater = None
    logging.warning("PlaylistUpdater not available - playlist updating disabled")

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger('FileRelocater')

# Standard character set for folder names
ALLOWED_FOLDER_CHARS = set('abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_~ ')

# Audio file extensions
AUDIO_EXTENSIONS = {'.mp3', '.flac', '.wav', '.ogg', '.m4a', '.aac', '.opus', '.wma', '.ape', '.wv'}

# Default folder structure
DEFAULT_FOLDER_FORMAT = "{album}_{albumartist}_{year}"

# Metadata tag mappings
METADATA_TAG_MAPPINGS = {
    'title': ['title', 'Title', 'TITLE', 'TIT2', 'track_title', 'Track Title'],
    'album': ['album', 'Album', 'ALBUM', 'TALB', 'album_title', 'Album Title'],
    'artist': ['artist', 'Artist', 'ARTIST', 'TPE1', 'AlbumArtist', 'albumartist', 'ALBUMARTIST'],
    'albumartist': ['albumartist', 'AlbumArtist', 'ALBUMARTIST', 'TPE2', 'album_artist', 'Album Artist', 'ALBUM ARTIST'],
    'track': ['track', 'Track', 'TRACK', 'TRCK', 'tracknumber', 'TrackNumber', 'track_number'],
    'year': ['year', 'Year', 'YEAR', 'date', 'Date', 'DATE', 'TYER', 'TDRC'],
    'genre': ['genre', 'Genre', 'GENRE', 'TCON'],
    'disc': ['disc', 'Disc', 'DISC', 'discnumber', 'DiscNumber', 'disc_number', 'TPOS'],
    'composer': ['composer', 'Composer', 'COMPOSER', 'TCOM'],
}


class FileRelocater:
    """
    Audio library organizer with character sanitization and playlist updating
    """
    
    def __init__(self, target_dir: Path, folder_format: str = DEFAULT_FOLDER_FORMAT,
                 char_replacements: Optional[Dict[str, str]] = None,
                 dont_sanitize: bool = False,
                 skip_no_metadata: bool = False,
                 update_playlists: Optional[List[Path]] = None,
                 delete_originals: bool = False,
                 dry_run: bool = False):
        """
        Args:
            target_dir: Target directory for organized files
            folder_format: Pattern like "{album}_{albumartist}_{year}"
            char_replacements: Dict of characters to replace
            dont_sanitize: Skip character filtering
            skip_no_metadata: Skip files with missing critical metadata
            update_playlists: List of playlist files to update
            delete_originals: Delete source files after moving
            dry_run: Preview without moving
        """
        self.target_dir = target_dir
        self.folder_format = folder_format
        self.char_replacements = char_replacements or {}
        self.dont_sanitize = dont_sanitize
        self.skip_no_metadata = skip_no_metadata
        self.delete_originals = delete_originals
        self.dry_run = dry_run
        
        # Stats
        self.moved_count = 0
        self.error_count = 0
        self.skipped_count = 0
        self.metadata_error_count = 0
        self.conflict_count = 0
        self.skipped_files = []
        self.error_messages = []
        
        # Track source files that were successfully moved
        self.moved_source_files = []
        
        # Path mapping for playlist updates
        self.path_mapping = {}
        
        # Playlist updater
        self.playlist_updater = None
        if update_playlists and PlaylistUpdater:
            self.playlist_updater = PlaylistUpdater(update_playlists, dry_run)
        
        self._check_ffprobe()
    
    def _check_ffprobe(self):
        """Check FFprobe availability"""
        try:
            subprocess.run(['ffprobe', '-version'], 
                          capture_output=True, check=True)
        except (subprocess.CalledProcessError, FileNotFoundError):
            raise RuntimeError("FFprobe not found. Install FFmpeg.")
    
    def sanitize_folder_name(self, text: str) -> str:
        """
        Sanitize text for folder name
        
        Args:
            text: Text to sanitize
            
        Returns:
            Sanitized text
        """
        if not text:
            return "Unknown"
        
        # Default replacements for filesystem-illegal characters
        filesystem_illegal_defaults = {
            '/': '-',
            '\\': '-',
            ':': '-',
            '*': '-',
            '?': '-',
            '"': "-",
            '<': '-',
            '>': '-',
            '|': '-'
        }
        
        # Apply character replacements (user --rc flags take precedence)
        sanitized = text
        
        # First, handle filesystem-illegal characters with defaults or user overrides
        for illegal_char, default_replacement in filesystem_illegal_defaults.items():
            if illegal_char in sanitized:
                # Use user's replacement if specified, otherwise use default
                replacement = self.char_replacements.get(illegal_char, default_replacement)
                sanitized = sanitized.replace(illegal_char, replacement)
                if illegal_char not in self.char_replacements and default_replacement:
                    print(f"DEBUG: '{illegal_char}' automatically replaced with '{replacement}'")
        
        # Then apply other character replacements
        for old_char, new_char in self.char_replacements.items():
            if old_char not in filesystem_illegal_defaults:
                sanitized = sanitized.replace(old_char, new_char)
        
        # Apply character filtering if enabled
        if not self.dont_sanitize:
            final_sanitized = ""
            for char in sanitized:
                if char in ALLOWED_FOLDER_CHARS:
                    final_sanitized += char
                elif char in ".,&%;'":
                    # Remove additional problematic characters
                    pass
                else:
                    # Replace with space
                    final_sanitized += " "
        else:
            final_sanitized = sanitized
        
        # Clean up multiple spaces
        final_sanitized = re.sub(r'\s+', ' ', final_sanitized).strip()
        
        return final_sanitized or "Unknown"
    
    def get_file_metadata(self, filepath: Path) -> Dict[str, str]:
        """
        Extract metadata using FFprobe
        
        Args:
            filepath: Audio file path
            
        Returns:
            Metadata dictionary
        """
        try:
            cmd = [
                'ffprobe', '-v', 'quiet', 
                '-print_format', 'json', 
                '-show_format', str(filepath)
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            file_info = json.loads(result.stdout)
            
            metadata = {}
            if 'format' in file_info and 'tags' in file_info['format']:
                tags = file_info['format']['tags']
                
                # Map pre-defined fields
                for field_name, tag_variants in METADATA_TAG_MAPPINGS.items():
                    for tag_key in tag_variants:
                        if tag_key in tags:
                            metadata[field_name] = tags[tag_key]
                            break
                
                # Extract year from date
                if 'year' in metadata:
                    date_value = metadata['year']
                    year_match = re.search(r'\b(19|20)\d{2}\b', str(date_value))
                    if year_match:
                        metadata['year'] = year_match.group(0)
                
                # Store all raw tags
                for key, value in tags.items():
                    metadata[key] = value
            
            return metadata
            
        except (subprocess.CalledProcessError, json.JSONDecodeError) as e:
            logger.warning(f"Could not read metadata from {filepath.name}: {e}")
            self.metadata_error_count += 1
            return {}
    
    def generate_folder_path(self, filepath: Path) -> Optional[Path]:
        """
        Generate folder path from metadata
        
        Args:
            filepath: Audio file
            
        Returns:
            Folder path or None if cannot generate
        """
        metadata = self.get_file_metadata(filepath)
        
        # Parse format fields
        import string
        formatter = string.Formatter()
        format_fields = [field_name for _, field_name, _, _ 
                        in formatter.parse(self.folder_format) if field_name]
        
        # Build format values
        missing_fields = []
        format_values = {}
        
        for field in format_fields:
            if field in metadata and metadata[field].strip():
                format_values[field] = self.sanitize_folder_name(metadata[field].strip())
            else:
                if field in METADATA_TAG_MAPPINGS:
                    missing_fields.append(field)
                    format_values[field] = ""
                else:
                    format_values[field] = ""
        
        if missing_fields:
            logger.warning(f"Missing fields {missing_fields} in {filepath.name}")
        
        # Skip if missing critical metadata
        if self.skip_no_metadata:
            critical_fields = {'album', 'albumartist'} & set(format_fields)
            if critical_fields and any(not format_values.get(field, '') for field in critical_fields):
                return None
        
        # Handle no metadata case
        if all(not value for value in format_values.values()):
            if not self.skip_no_metadata:
                for field in format_values:
                    format_values[field] = "Unknown"
            else:
                return None
        
        try:
            # Apply format
            folder_name = self.folder_format.format(**format_values)
            folder_name = re.sub(r'\s+', ' ', folder_name).strip()
            folder_name = folder_name.strip(' -_')
            
            if not folder_name:
                folder_name = "Unknown"
            
            return self.target_dir / folder_name
            
        except (KeyError, Exception) as e:
            logger.error(f"Error formatting folder path for {filepath.name}: {e}")
            return None
    
    def move_file(self, filepath: Path) -> bool:
        """
        Move audio file to organized structure
        
        Args:
            filepath: File to move
            
        Returns:
            True if moved successfully
        """
        if filepath.suffix.lower() not in AUDIO_EXTENSIONS:
            return False
        
        folder_path = self.generate_folder_path(filepath)
        if not folder_path:
            logger.info(f"Skipped {filepath.name} (no metadata)")
            self.skipped_count += 1
            self.skipped_files.append(str(filepath))
            return False
        
        # Check if already in target location
        if filepath.parent == folder_path:
            logger.debug(f"Skipped {filepath.name} (already in target)")
            self.skipped_count += 1
            return False
        
        # Handle filename conflicts
        target_path = folder_path / filepath.name
        if target_path.exists() and target_path != filepath:
            counter = 2
            while target_path.exists():
                target_path = folder_path / f"{filepath.stem} ({counter}){filepath.suffix}"
                counter += 1
            self.conflict_count += 1
        
        # Move file
        try:
            if self.dry_run:
                logger.info(f"[DRY RUN] {filepath.name} -> {folder_path.name}")
            else:
                folder_path.mkdir(parents=True, exist_ok=True)
                shutil.move(str(filepath), str(target_path))
                logger.info(f"Moved: {filepath.name} -> {folder_path.name}")
                
                # Track source file for potential deletion
                self.moved_source_files.append(filepath)
                
                # Track for playlist updates
                self.path_mapping[str(filepath.resolve())] = str(target_path.resolve())
            
            self.moved_count += 1
            return True
            
        except Exception as e:
            error_msg = f"Error moving {filepath.name}: {e}"
            logger.error(error_msg)
            self.error_messages.append(error_msg)
            self.error_count += 1
            return False
    
    def organize_directory(self, source_dir: Path, recursive: bool = True) -> Dict[str, int]:
        """
        Organize all audio files in directory
        
        Args:
            source_dir: Source directory
            recursive: Process subdirectories
            
        Returns:
            Statistics dictionary
        """
        if not source_dir.is_dir():
            raise NotADirectoryError(f"Not a directory: {source_dir}")
        
        # Find audio files
        if recursive:
            files = []
            for ext in AUDIO_EXTENSIONS:
                files.extend(source_dir.rglob(f'*{ext}'))
        else:
            files = []
            for ext in AUDIO_EXTENSIONS:
                files.extend(source_dir.glob(f'*{ext}'))
        
        # Move each file
        for file_path in files:
            self.move_file(file_path)
        
        # Update playlists
        if self.playlist_updater and self.path_mapping:
            logger.info("Updating playlists...")
            self.playlist_updater.update_all(self.path_mapping)
        
        # Delete original source files if requested
        if self.delete_originals and self.moved_source_files and not self.dry_run:
            logger.info(f"Deleting {len(self.moved_source_files)} original source files...")
            deleted_count = 0
            for source_file in self.moved_source_files:
                try:
                    # Check if file still exists (shutil.move already moved it)
                    # This is a safeguard in case the file path still exists somehow
                    if source_file.exists():
                        source_file.unlink()
                        deleted_count += 1
                        logger.debug(f"Deleted: {source_file}")
                except Exception as e:
                    logger.warning(f"Could not delete {source_file}: {e}")
            
            if deleted_count > 0:
                logger.info(f"Deleted {deleted_count} original files")
        
        # Display errors if any
        if self.error_messages:
            logger.info("\nErrors encountered:")
            for msg in self.error_messages:
                logger.info(f"  {msg}")
        
        return {
            'moved': self.moved_count,
            'skipped': self.skipped_count,
            'errors': self.error_count,
            'conflicts': self.conflict_count,
            'metadata_errors': self.metadata_error_count
        }


def main():
    parser = argparse.ArgumentParser(
        description='Organize audio library into folder structures based on metadata'
    )
    parser.add_argument('source', type=Path, help='Source file or directory')
    parser.add_argument('target', type=Path, help='Target directory')
    parser.add_argument('-f', '--format', default=DEFAULT_FOLDER_FORMAT,
                       help=f'Folder format (default: {DEFAULT_FOLDER_FORMAT})')
    parser.add_argument('-r', '--recursive', action='store_true',
                       help='Process subdirectories')
    parser.add_argument('--dry-run', action='store_true',
                       help='Preview without moving')
    parser.add_argument('--rc', action='append', nargs=2, metavar=('OLD', 'NEW'),
                       help='Replace character OLD with NEW (e.g., --rc : -)')
    parser.add_argument('--dont-sanitize', action='store_true',
                       help='Skip character filtering')
    parser.add_argument('--skip-no-metadata', action='store_true',
                       help='Skip files missing critical metadata')
    parser.add_argument('-p', '--update-playlists', action='append', type=Path,
                       help='Update specified playlists with new paths')
    parser.add_argument('--delete-originals', action='store_true',
                       help='Delete source files after moving (happens after playlist updates)')
    
    args = parser.parse_args()
    
    # Build character replacements
    char_replacements = {}
    if args.rc:
        for old, new in args.rc:
            char_replacements[old] = new
    
    try:
        relocater = FileRelocater(
            target_dir=args.target,
            folder_format=args.format,
            char_replacements=char_replacements,
            dont_sanitize=args.dont_sanitize,
            skip_no_metadata=args.skip_no_metadata,
            update_playlists=args.update_playlists,
            delete_originals=args.delete_originals,
            dry_run=args.dry_run
        )
        
        if args.source.is_dir():
            stats = relocater.organize_directory(args.source, args.recursive)
        else:
            relocater.move_file(args.source)
            stats = {
                'moved': relocater.moved_count,
                'skipped': relocater.skipped_count,
                'errors': relocater.error_count,
                'conflicts': relocater.conflict_count,
                'metadata_errors': relocater.metadata_error_count
            }
        
        print(f"\nOrganize complete:")
        print(f"  Moved: {stats['moved']}")
        print(f"  Skipped: {stats['skipped']}")
        print(f"  Conflicts resolved: {stats['conflicts']}")
        if stats['errors']:
            print(f"  Errors: {stats['errors']}")
        if stats['metadata_errors']:
            print(f"  Metadata errors: {stats['metadata_errors']}")
        
        return 1 if stats['errors'] else 0
        
    except Exception as e:
        logger.error(f"Error: {e}")
        return 1


if __name__ == '__main__':
    sys.exit(main())