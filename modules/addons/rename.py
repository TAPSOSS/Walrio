#!/usr/bin/env python3
"""
rename audio files based on metadata tags
"""

import argparse
import json
import logging
import os
import re
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
logger = logging.getLogger('AudioRenamer')

# Standard character set for safe filenames
ALLOWED_FILE_CHARS = set('abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789[]()-_~@=+! ')

# Audio file extensions
AUDIO_EXTENSIONS = {'.mp3', '.flac', '.wav', '.ogg', '.m4a', '.aac', '.opus', '.wma', '.ape', '.wv'}

# Default naming format
DEFAULT_FORMAT = "{title} - {album} - {albumartist} - {year}"

# Metadata tag mappings for common fields
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
    'comment': ['comment', 'Comment', 'COMMENT', 'COMM'],
}


class AudioRenamer:
    """
    Audio file renamer with character sanitization and playlist updating
    """
    
    def __init__(self, format_string: str = DEFAULT_FORMAT, 
                 char_replacements: Optional[Dict[str, str]] = None,
                 dont_sanitize: bool = False,
                 auto_sanitize: bool = False,
                 force_allow_special: bool = False,
                 skip_no_metadata: bool = False,
                 full_date: bool = False,
                 update_playlists: Optional[List[Path]] = None,
                 dry_run: bool = False):
        """
        Args:
            format_string: Pattern like "{track} - {artist} - {title}"
            char_replacements: Dict of characters to replace (e.g., {':': '-'})
            dont_sanitize: Skip character filtering (only apply replacements)
            auto_sanitize: Auto-sanitize without prompting
            force_allow_special: Always allow special characters
            skip_no_metadata: Skip files with missing critical metadata
            full_date: Keep full date instead of just year
            update_playlists: List of playlist files to update with new paths
            dry_run: Preview changes without applying
        """
        self.format_string = format_string
        self.char_replacements = char_replacements or {}
        self.dont_sanitize = dont_sanitize
        self.auto_sanitize = auto_sanitize
        self.force_allow_special = force_allow_special
        self.skip_no_metadata = skip_no_metadata
        self.full_date = full_date
        self.dry_run = dry_run
        
        # Stats
        self.renamed_count = 0
        self.error_count = 0
        self.skipped_count = 0
        self.metadata_error_count = 0
        self.conflict_count = 0
        
        # Interactive prompt state
        self.allow_special_all = False
        self.skip_special_all = False
        
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
    
    def prompt_allow_special_chars(self, original: str, sanitized: str) -> bool:
        """
        Prompt whether to allow special characters
        
        Args:
            original: Original filename
            sanitized: Sanitized filename
            
        Returns:
            True to keep special chars, False to use sanitized
        """
        if self.force_allow_special:
            return True
        if self.allow_special_all:
            return True
        if self.skip_special_all:
            return False
        
        print(f"\nSpecial characters detected:")
        print(f"  Original:  {original}")
        print(f"  Sanitized: {sanitized}")
        
        while True:
            response = input("Keep special characters? (y/n/ya/na): ").lower().strip()
            
            if response in ['y', 'yes']:
                return True
            elif response in ['n', 'no']:
                return False
            elif response in ['ya', 'yesall', 'yes to all']:
                self.allow_special_all = True
                return True
            elif response in ['na', 'noall', 'no to all']:
                self.skip_special_all = True
                return False
            else:
                print("Enter y, n, ya, or na")
    
    def sanitize_filename(self, text: str) -> str:
        """
        Sanitize text for use as filename
        
        Args:
            text: Text to sanitize
            
        Returns:
            Sanitized text
        """
        if not text:
            return "Unknown"
        
        original_text = text
        
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
        
        # Apply character replacements
        sanitized = text
        
        # First, handle filesystem-illegal characters with defaults or user overrides
        for illegal_char, default_replacement in filesystem_illegal_defaults.items():
            if illegal_char in sanitized:
                # Use user's replacement if specified, otherwise use default
                replacement = self.char_replacements.get(illegal_char, default_replacement)
                sanitized = sanitized.replace(illegal_char, replacement)
                if illegal_char not in self.char_replacements and default_replacement:
                    print(f"DEBUG: '{illegal_char}' automatically replaced with '{replacement}'")
                elif illegal_char not in self.char_replacements and not default_replacement:
                    print(f"DEBUG: '{illegal_char}' automatically removed")
        
        # Then apply other character replacements
        for old_char, new_char in self.char_replacements.items():
            if old_char not in filesystem_illegal_defaults:
                sanitized = sanitized.replace(old_char, new_char)
        
        # Apply character filtering if enabled
        if not self.dont_sanitize:
            final_sanitized = ""
            for char in sanitized:
                if char in ALLOWED_FILE_CHARS:
                    final_sanitized += char
                elif char in "!.,&%;'":
                    # Remove additional problematic characters
                    pass
                else:
                    # Replace with space
                    final_sanitized += " "
        else:
            final_sanitized = sanitized
        
        # Clean up multiple spaces
        final_sanitized = re.sub(r'\s+', ' ', final_sanitized).strip()
        
        # Check if there are differences BEYOND just filesystem-illegal character replacement
        # Only prompt if special characters (other than filesystem-illegal) would be removed
        if not self.dont_sanitize and not self.auto_sanitize:
            # Create a version with just filesystem-illegal chars replaced for comparison
            temp_text = original_text
            for illegal_char, default_replacement in filesystem_illegal_defaults.items():
                replacement = self.char_replacements.get(illegal_char, default_replacement)
                temp_text = temp_text.replace(illegal_char, replacement)
            temp_text = re.sub(r'\s+', ' ', temp_text).strip()
            
            # Only prompt if sanitization removes MORE than just filesystem-illegal characters
            if final_sanitized != temp_text:
                if self.prompt_allow_special_chars(original_text, final_sanitized):
                    # Keep special chars with replacements (but still handle filesystem-illegal chars)
                    result = original_text
                    # Apply filesystem-illegal replacements first
                    for illegal_char, default_replacement in filesystem_illegal_defaults.items():
                        replacement = self.char_replacements.get(illegal_char, default_replacement)
                        result = result.replace(illegal_char, replacement)
                    # Then apply other character replacements
                    for old_char, new_char in self.char_replacements.items():
                        if old_char not in filesystem_illegal_defaults:
                            result = result.replace(old_char, new_char)
                    final_sanitized = re.sub(r'\s+', ' ', result).strip()
        
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
                
                # Special handling for year
                if 'year' in metadata and not self.full_date:
                    date_value = metadata['year']
                    year_match = re.search(r'\b(19|20)\d{2}\b', str(date_value))
                    if year_match:
                        metadata['year'] = year_match.group(0)
                
                # Store all raw tags for custom access
                for key, value in tags.items():
                    metadata[key] = value
            
            return metadata
            
        except (subprocess.CalledProcessError, json.JSONDecodeError) as e:
            logger.warning(f"Could not read metadata from {filepath.name}: {e}")
            self.metadata_error_count += 1
            return {}
    
    def generate_new_filename(self, filepath: Path) -> Optional[str]:
        """
        Generate new filename from metadata
        
        Args:
            filepath: Audio file
            
        Returns:
            New filename or None if cannot generate
        """
        metadata = self.get_file_metadata(filepath)
        file_ext = filepath.suffix.lower()
        
        # Parse format fields
        import string
        formatter = string.Formatter()
        format_fields = [field_name for _, field_name, _, _ 
                        in formatter.parse(self.format_string) if field_name]
        
        # Build format values
        missing_fields = []
        format_values = {}
        
        for field in format_fields:
            if field in metadata and metadata[field].strip():
                format_values[field] = self.sanitize_filename(metadata[field].strip())
            else:
                if field in METADATA_TAG_MAPPINGS:
                    missing_fields.append(field)
                    format_values[field] = ""
                else:
                    logger.warning(f"Custom field '{field}' not found in {filepath.name}")
                    format_values[field] = ""
        
        if missing_fields:
            logger.warning(f"Missing fields {missing_fields} in {filepath.name}")
        
        # Skip if missing critical metadata
        if self.skip_no_metadata:
            critical_fields = {'title', 'album'} & set(format_fields)
            if critical_fields and any(not format_values.get(field, '') for field in critical_fields):
                return None
        
        # Handle no metadata case
        if all(not value for value in format_values.values()):
            if not self.skip_no_metadata:
                original_name = filepath.stem
                if 'title' in format_values:
                    format_values['title'] = self.sanitize_filename(original_name)
                for field in format_values:
                    if not format_values[field] and field != 'title':
                        format_values[field] = f"Unknown {field.title()}"
            else:
                return None
        
        try:
            # Apply format
            new_filename_base = self.format_string.format(**format_values)
            new_filename_base = re.sub(r'\s+', ' ', new_filename_base).strip()
            new_filename_base = new_filename_base.strip(' -_')
            
            if not new_filename_base:
                new_filename_base = "Unknown"
            
            return f"{new_filename_base}{file_ext}"
            
        except (KeyError, Exception) as e:
            logger.error(f"Error formatting filename for {filepath.name}: {e}")
            return None
    
    def resolve_filename_conflict(self, filepath: Path, new_filename: str, 
                                  directory: Path) -> str:
        """
        Resolve conflicts by adding counter to title
        
        Args:
            filepath: Original file
            new_filename: Proposed filename
            directory: Target directory
            
        Returns:
            Unique filename
        """
        new_filepath = directory / new_filename
        
        if not new_filepath.exists():
            return new_filename
        
        file_ext = Path(new_filename).suffix
        metadata = self.get_file_metadata(filepath)
        
        # Parse format fields
        import string
        formatter = string.Formatter()
        format_fields = [field_name for _, field_name, _, _ 
                        in formatter.parse(self.format_string) if field_name]
        
        counter = 2
        
        # Try to add counter to title field
        if 'title' in format_fields and 'title' in metadata:
            original_title = metadata['title']
            
            while new_filepath.exists():
                modified_metadata = metadata.copy()
                modified_metadata['title'] = f"{original_title} ({counter})"
                
                # Build format values with modified title
                format_values = {}
                for field in format_fields:
                    if field in modified_metadata and modified_metadata[field].strip():
                        format_values[field] = self.sanitize_filename(modified_metadata[field].strip())
                    else:
                        format_values[field] = ""
                
                try:
                    new_filename_base = self.format_string.format(**format_values)
                    new_filename_base = re.sub(r'\s+', ' ', new_filename_base).strip()
                    new_filename_base = new_filename_base.strip(' -_')
                    
                    if not new_filename_base:
                        new_filename_base = "Unknown"
                    
                    new_filename = f"{new_filename_base}{file_ext}"
                    new_filepath = directory / new_filename
                    counter += 1
                    
                except Exception:
                    break
            else:
                return new_filename
        
        # Fallback: add counter to whole filename
        counter = 2
        filename_base = Path(new_filename).stem
        new_filename = f"{filename_base} ({counter}){file_ext}"
        new_filepath = directory / new_filename
        
        while new_filepath.exists():
            counter += 1
            new_filename = f"{filename_base} ({counter}){file_ext}"
            new_filepath = directory / new_filename
        
        self.conflict_count += 1
        return new_filename
    
    def rename_file(self, filepath: Path) -> bool:
        """
        Rename single audio file
        
        Args:
            filepath: File to rename
            
        Returns:
            True if renamed successfully
        """
        if filepath.suffix.lower() not in AUDIO_EXTENSIONS:
            return False
        
        new_filename = self.generate_new_filename(filepath)
        if not new_filename:
            logger.info(f"Skipped {filepath.name} (no metadata)")
            self.skipped_count += 1
            return False
        
        # Check if already has desired name
        if filepath.name == new_filename:
            logger.debug(f"Skipped {filepath.name} (already correct)")
            self.skipped_count += 1
            return False
        
        # Resolve conflicts
        directory = filepath.parent
        new_filename = self.resolve_filename_conflict(filepath, new_filename, directory)
        new_filepath = directory / new_filename
        
        # Rename
        try:
            if self.dry_run:
                logger.info(f"[DRY RUN] {filepath.name} -> {new_filename}")
            else:
                filepath.rename(new_filepath)
                logger.info(f"Renamed: {filepath.name} -> {new_filename}")
                
                # Track for playlist updates
                self.path_mapping[str(filepath.resolve())] = str(new_filepath.resolve())
            
            self.renamed_count += 1
            return True
            
        except Exception as e:
            logger.error(f"Error renaming {filepath.name}: {e}")
            self.error_count += 1
            return False
    
    def rename_directory(self, directory: Path, recursive: bool = True) -> Dict[str, int]:
        """
        Rename all audio files in directory
        
        Args:
            directory: Directory to process
            recursive: Process subdirectories
            
        Returns:
            Statistics dictionary
        """
        if not directory.is_dir():
            raise NotADirectoryError(f"Not a directory: {directory}")
        
        # Find audio files (case-insensitive extension matching)
        files = []
        if recursive:
            # Get all files recursively and filter by extension
            for file_path in directory.rglob('*'):
                if file_path.is_file() and file_path.suffix.lower() in AUDIO_EXTENSIONS:
                    files.append(file_path)
        else:
            # Get files in directory only and filter by extension
            for file_path in directory.glob('*'):
                if file_path.is_file() and file_path.suffix.lower() in AUDIO_EXTENSIONS:
                    files.append(file_path)
        
        print(f"DEBUG: Scanning directory: {directory}")
        print(f"DEBUG: Recursive: {recursive}")
        print(f"DEBUG: Found {len(files)} audio files to process")
        logger.info(f"Found {len(files)} audio files to process")
        
        # Rename each file
        total_files = len(files)
        for idx, file_path in enumerate(files, 1):
            print(f"\nFile {idx}/{total_files}: {file_path.name}")
            self.rename_file(file_path)
        
        # Update playlists
        if self.playlist_updater and self.path_mapping:
            logger.info("Updating playlists...")
            self.playlist_updater.update_all(self.path_mapping)
        
        return {
            'renamed': self.renamed_count,
            'skipped': self.skipped_count,
            'errors': self.error_count,
            'conflicts': self.conflict_count,
            'metadata_errors': self.metadata_error_count
        }


def main():
    parser = argparse.ArgumentParser(
        description='Rename audio files based on metadata'
    )
    parser.add_argument('input', type=Path, help='File or directory to rename')
    parser.add_argument('-f', '--format', default=DEFAULT_FORMAT,
                       help=f'Filename format (default: {DEFAULT_FORMAT})')
    parser.add_argument('-r', '--recursive', action='store_true',
                       help='Process subdirectories')
    parser.add_argument('--dry-run', action='store_true',
                       help='Preview without renaming')
    parser.add_argument('--rc', action='append', nargs=2, metavar=('OLD', 'NEW'),
                       help='Replace character OLD with NEW (e.g., --rc : -)')
    parser.add_argument('--dont-sanitize', action='store_true',
                       help='Skip character filtering')
    parser.add_argument('--auto-sanitize', action='store_true',
                       help='Auto-sanitize without prompting')
    parser.add_argument('--force-allow-special', action='store_true',
                       help='Always allow special characters')
    parser.add_argument('--skip-no-metadata', action='store_true',
                       help='Skip files missing critical metadata')
    parser.add_argument('--full-date', action='store_true',
                       help='Keep full date instead of just year')
    parser.add_argument('-p', '--update-playlists', action='append', type=Path,
                       help='Update specified playlists with new paths')
    
    args = parser.parse_args()
    
    # Build character replacements
    char_replacements = {}
    if args.rc:
        for old, new in args.rc:
            char_replacements[old] = new
    
    try:
        renamer = AudioRenamer(
            format_string=args.format,
            char_replacements=char_replacements,
            dont_sanitize=args.dont_sanitize,
            auto_sanitize=args.auto_sanitize,
            force_allow_special=args.force_allow_special,
            skip_no_metadata=args.skip_no_metadata,
            full_date=args.full_date,
            update_playlists=args.update_playlists,
            dry_run=args.dry_run
        )
        
        if args.input.is_dir():
            stats = renamer.rename_directory(args.input, args.recursive)
        else:
            renamer.rename_file(args.input)
            stats = {
                'renamed': renamer.renamed_count,
                'skipped': renamer.skipped_count,
                'errors': renamer.error_count,
                'conflicts': renamer.conflict_count,
                'metadata_errors': renamer.metadata_error_count
            }
        
        print(f"\nRename complete:")
        print(f"  Renamed: {stats['renamed']}")
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