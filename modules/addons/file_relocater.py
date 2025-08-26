#!/usr/bin/env python3
"""
File Relocater
Copyright (c) 2025 TAPS OSS
Project: https://github.com/TAPSOSS/Walrio
Licensed under the BSD-3-Clause License (see LICENSE file for details)

A tool to move audio files into folder structures based on metadata.
Moves files from a source library into organized subfolders under a specified root directory.

Default folder structure: /(album)/(year)/(albumartist)/ with sanitized folder names but can be changed by user.
"""

import os
import sys
import argparse
import subprocess
import logging
import json
import re
import shutil
from pathlib import Path
from typing import List, Dict, Any, Optional, Union

# Configure logging format
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger('FileRelocater')

# Standard character set for folder names as defined by tapscodes (conservative for music player compatibility)
ALLOWED_FOLDER_CHARS = set('abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_ ')

# Audio file extensions to process
AUDIO_EXTENSIONS = {'.mp3', '.flac', '.wav', '.ogg', '.m4a', '.aac', '.opus', '.wma', '.ape', '.wv'}

# Default folder structure format
DEFAULT_FOLDER_FORMAT = "{album}/{year}/{albumartist}"

# Standard character replacements (applied before other sanitization when --standard is used)
STANDARD_CHAR_REPLACEMENTS = {'/': '-', '\\': '-', ':': '-', '|': '-'}

# Pre-defined metadata tag mappings for common fields
METADATA_TAG_MAPPINGS = {
    'title': ['title', 'Title', 'TITLE', 'TIT2', 'track_title', 'Track Title'],
    'album': ['album', 'Album', 'ALBUM', 'TALB', 'album_title', 'Album Title'],
    'artist': ['artist', 'Artist', 'ARTIST', 'TPE1', 'AlbumArtist', 'albumartist', 'ALBUMARTIST'],
    'albumartist': ['albumartist', 'AlbumArtist', 'ALBUMARTIST', 'TPE2', 'album_artist', 'Album Artist'],
    'track': ['track', 'Track', 'TRACK', 'TRCK', 'tracknumber', 'TrackNumber', 'track_number'],
    'year': ['year', 'Year', 'YEAR', 'date', 'Date', 'DATE', 'TYER', 'TDRC'],
    'genre': ['genre', 'Genre', 'GENRE', 'TCON'],
    'disc': ['disc', 'Disc', 'DISC', 'discnumber', 'DiscNumber', 'disc_number', 'TPOS'],
    'composer': ['composer', 'Composer', 'COMPOSER', 'TCOM'],
    'comment': ['comment', 'Comment', 'COMMENT', 'COMM'],
}

class FileRelocater:
    """
    Audio library organizer that moves files into folder structures based on metadata
    """
    
    def __init__(self, options: Dict[str, Any]):
        """
        Initialize the FileRelocater with the specified options.
        
        Args:
            options (dict): Dictionary of organization options
        """
        self.options = options
        self.moved_count = 0
        self.error_count = 0
        self.skipped_count = 0
        self.skipped_files = []  # Track files skipped due to no metadata
        self.metadata_error_count = 0
        self.conflict_count = 0
        
        # Validate FFprobe availability
        self._check_ffprobe()
    
    def _check_ffprobe(self):
        """
        Check if FFprobe is available for metadata extraction.
        
        Raises:
            RuntimeError: If FFprobe is not found.
        """
        try:
            result = subprocess.run(
                ['ffprobe', '-version'],
                capture_output=True,
                text=True,
                check=True
            )
            logger.debug("FFprobe is available for metadata extraction")
        except (subprocess.CalledProcessError, FileNotFoundError):
            raise RuntimeError(
                "FFprobe not found. Please install FFmpeg and make sure it's in your PATH."
            )
    
    def sanitize_folder_name(self, text: str) -> str:
        """
        Clean a string to be safe for use as a folder name.
        
        Args:
            text (str): Text to sanitize
            
        Returns:
            str: Sanitized text
        """
        if not text:
            return "Unknown"
        
        # Get character replacements from options (default to no replacements)
        char_replacements = self.options.get('char_replacements', {})
        
        # Apply custom character replacements first
        sanitized = text
        for old_char, new_char in char_replacements.items():
            sanitized = sanitized.replace(old_char, new_char)
        
        # Check if sanitization is disabled
        if self.options.get('dont_sanitize', True):  # Default to disabled sanitization
            # Only apply character replacements, skip character filtering
            final_sanitized = sanitized
        else:
            # Get the allowed character set (custom or default)
            allowed_chars = self.options.get('custom_sanitize_chars', ALLOWED_FOLDER_CHARS)
            
            # Apply character filtering
            final_sanitized = ""
            for char in sanitized:
                if char in allowed_chars:
                    final_sanitized += char
                elif char in "?!/\\|.,&%*\":;'><":
                    # Remove these completely as they can cause issues
                    # (unless they were already replaced above)
                    pass
                else:
                    # Replace other characters with space
                    final_sanitized += " "
        
        # Clean up multiple spaces and strip whitespace (always do this)
        final_sanitized = re.sub(r'\s+', ' ', final_sanitized).strip()
        
        # Ensure we don't end up with an empty string
        if not final_sanitized:
            final_sanitized = "Unknown"
        
        return final_sanitized
    
    def get_file_metadata(self, filepath: str) -> Dict[str, str]:
        """
        Extract metadata from an audio file using FFprobe.
        
        Args:
            filepath (str): Path to the audio file
            
        Returns:
            dict: Dictionary containing all available metadata
        """
        try:
            cmd = [
                'ffprobe', 
                '-v', 'quiet', 
                '-print_format', 'json', 
                '-show_format', 
                filepath
            ]
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=True
            )
            
            file_info = json.loads(result.stdout)
            
            # Extract metadata tags
            metadata = {}
            if 'format' in file_info and 'tags' in file_info['format']:
                tags = file_info['format']['tags']
                
                # For each pre-defined metadata field, try to find it in the tags
                for field_name, tag_variants in METADATA_TAG_MAPPINGS.items():
                    for tag_key in tag_variants:
                        if tag_key in tags:
                            metadata[field_name] = tags[tag_key]
                            break
                
                # Also store all raw tags for custom metadata access
                for key, value in tags.items():
                    # Store with original key name for custom format strings
                    metadata[key] = value
            
            return metadata
            
        except (subprocess.CalledProcessError, json.JSONDecodeError) as e:
            logger.error(f"METADATA ERROR: Could not read metadata from {os.path.basename(filepath)}: {str(e)}")
            self.metadata_error_count += 1
            return {}
    
    def generate_folder_path(self, filepath: str) -> Optional[str]:
        """
        Generate a folder path based on metadata using the specified format.
        
        Args:
            filepath (str): Path to the audio file
            
        Returns:
            str or None: Relative folder path, or None if format cannot be resolved
        """
        metadata = self.get_file_metadata(filepath)
        
        # Get the folder format from options
        format_string = self.options.get('folder_format', DEFAULT_FOLDER_FORMAT)
        
        # Parse the format string to find all required fields
        import string
        formatter = string.Formatter()
        format_fields = [field_name for _, field_name, _, _ in formatter.parse(format_string) if field_name]
        
        # Check if we have all required metadata
        missing_fields = []
        format_values = {}
        
        for field in format_fields:
            if field in metadata and metadata[field].strip():
                format_values[field] = self.sanitize_folder_name(metadata[field].strip())
            else:
                # Check if this is a pre-defined field that we should try harder to find
                if field in METADATA_TAG_MAPPINGS:
                    missing_fields.append(field)
                    format_values[field] = ""
                else:
                    # For custom fields, log warning and use empty string
                    logger.warning(f"Custom metadata field '{field}' not found in {os.path.basename(filepath)} - using empty value")
                    format_values[field] = ""
        
        # Log missing pre-defined fields
        if missing_fields:
            logger.warning(f"Missing metadata fields {missing_fields} in {os.path.basename(filepath)} - using empty values")
        
        # If skip_no_metadata is enabled and we're missing critical fields, skip the file
        if self.options.get('skip_no_metadata', False):
            # Check if any of the critical fields (album, albumartist) are missing
            critical_fields = {'album', 'albumartist'} & set(format_fields)
            if critical_fields and any(not format_values.get(field, '') for field in critical_fields):
                return None
        
        # Handle special case where we have no metadata at all for any field
        if all(not value for value in format_values.values()):
            if self.options.get('skip_no_metadata', True):
                return None
            elif self.options.get('process_no_metadata', False):
                # Use filename (without extension) as the folder name
                filename = os.path.splitext(os.path.basename(filepath))[0]
                sanitized_filename = self.sanitize_folder_name(filename)
                return sanitized_filename
            else:
                # Use "Unknown" values (legacy behavior)
                for field in format_values:
                    if not format_values[field]:
                        format_values[field] = f"Unknown {field.title()}"
        
        try:
            # Apply the format string
            folder_path = format_string.format(**format_values)
            
            # Clean up any double spaces or other formatting issues
            folder_path = re.sub(r'\s+', ' ', folder_path).strip()
            
            # Remove any leading/trailing separators
            folder_path = folder_path.strip(' /-_')
            
            # Ensure we don't end up with an empty path
            if not folder_path:
                folder_path = "Unknown"
            
            return folder_path
            
        except KeyError as e:
            logger.error(f"Invalid format string - unknown field {e} in format: {format_string}")
            return None
        except Exception as e:
            logger.error(f"Error formatting folder path for {os.path.basename(filepath)}: {str(e)}")
            return None
    
    def move_file(self, source_filepath: str, destination_root: str) -> bool:
        """
        Move a single audio file to the organized folder structure.
        
        Args:
            source_filepath (str): Path to the source audio file
            destination_root (str): Root directory for organized files
            
        Returns:
            bool: True if move was successful, False otherwise
        """
        if not os.path.isfile(source_filepath):
            logger.error(f"File does not exist: {source_filepath}")
            return False
        
        # Check if it's an audio file
        file_ext = os.path.splitext(source_filepath)[1].lower()
        if file_ext not in AUDIO_EXTENSIONS:
            logger.debug(f"Skipping non-audio file: {os.path.basename(source_filepath)}")
            return True
        
        # Generate folder path
        folder_path = self.generate_folder_path(source_filepath)
        if not folder_path:
            logger.debug(f"SKIPPED (no metadata): {os.path.basename(source_filepath)}")
            self.skipped_count += 1
            self.skipped_files.append(source_filepath)  # Track the full path
            return True
        
        # Construct destination path
        destination_folder = os.path.join(destination_root, folder_path)
        filename = os.path.basename(source_filepath)
        destination_filepath = os.path.join(destination_folder, filename)
        
        # Check if source and destination are the same
        if os.path.abspath(source_filepath) == os.path.abspath(destination_filepath):
            logger.debug(f"File already in correct location: {filename}")
            return True
        
        # Create destination folder if it doesn't exist
        try:
            os.makedirs(destination_folder, exist_ok=True)
        except OSError as e:
            logger.error(f"Failed to create destination folder {destination_folder}: {str(e)}")
            self.error_count += 1
            return False
        
        # Check if target file already exists
        if os.path.exists(destination_filepath):
            if self.options.get('skip_existing', True):
                logger.error(f"FILE CONFLICT: Target file already exists, skipping: {destination_filepath}")
                self.conflict_count += 1
                return True
            else:
                # Add a number suffix to make it unique
                base_name, ext = os.path.splitext(filename)
                counter = 1
                while os.path.exists(destination_filepath):
                    new_filename = f"{base_name} ({counter}){ext}"
                    destination_filepath = os.path.join(destination_folder, new_filename)
                    counter += 1
                logger.warning(f"File conflict resolved by adding suffix: {new_filename}")
        
        # Perform the move
        try:
            if self.options.get('dry_run', False):
                logger.info(f"[DRY RUN] Would move: {source_filepath} -> {destination_filepath}")
            else:
                if self.options.get('copy_mode', False):
                    shutil.copy2(source_filepath, destination_filepath)
                    logger.info(f"Copied: {source_filepath} -> {destination_filepath}")
                else:
                    shutil.move(source_filepath, destination_filepath)
                    logger.info(f"Moved: {source_filepath} -> {destination_filepath}")
            
            self.moved_count += 1
            return True
            
        except OSError as e:
            logger.error(f"Failed to move {source_filepath}: {str(e)}")
            self.error_count += 1
            return False
    
    def organize_directory(self, source_directory: str, destination_root: str) -> tuple[int, int]:
        """
        Organize all audio files in a directory.
        
        Args:
            source_directory (str): Directory containing audio files to organize
            destination_root (str): Root directory for organized files
            
        Returns:
            tuple: (number of successful moves, total number of files processed)
        """
        if not os.path.isdir(source_directory):
            logger.error(f"Source directory does not exist: {source_directory}")
            return (0, 0)
        
        if not os.path.exists(destination_root):
            try:
                os.makedirs(destination_root, exist_ok=True)
                logger.info(f"Created destination root directory: {destination_root}")
            except OSError as e:
                logger.error(f"Failed to create destination root directory {destination_root}: {str(e)}")
                return (0, 0)
        
        # Get list of audio files
        files_to_process = []
        
        if self.options.get('recursive', False):
            # Walk through directory tree recursively
            for root, _, files in os.walk(source_directory):
                for file in files:
                    file_path = os.path.join(root, file)
                    if os.path.splitext(file)[1].lower() in AUDIO_EXTENSIONS:
                        files_to_process.append(file_path)
        else:
            # Non-recursive: just get files in the top directory
            files_to_process = [
                os.path.join(source_directory, file) 
                for file in os.listdir(source_directory) 
                if os.path.isfile(os.path.join(source_directory, file)) and
                os.path.splitext(file)[1].lower() in AUDIO_EXTENSIONS
            ]
        
        total_files = len(files_to_process)
        initial_moved_count = self.moved_count
        
        logger.info(f"Found {total_files} audio files to organize")
        
        # Process each file
        for i, file_path in enumerate(files_to_process, 1):
            logger.debug(f"Processing file {i}/{total_files}: {os.path.basename(file_path)}")
            self.move_file(file_path, destination_root)
        
        # Log summary of skipped files during processing
        if self.skipped_count > 0:
            logger.info(f"Processed {total_files} files: {self.moved_count - initial_moved_count} organized, {self.skipped_count} skipped (no metadata)")
        
        successful_moves = self.moved_count - initial_moved_count
        return (successful_moves, total_files)


def parse_arguments():
    """
    Parse command line arguments.
    
    Returns:
        argparse.Namespace: Parsed arguments
    """
    parser = argparse.ArgumentParser(
        description="Audio Library Organizer - Organize files into folder structures using metadata",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""Examples:
  # Organize music library using default format (copies files, skips files with no metadata): album/albumartist
  python organize.py /path/to/music/library /path/to/organized/library

  # Move files instead of copying them
  python organize.py /music /organized --copy n

  # Process files with no metadata using filename as folder name
  python organize.py /music /organized --process-no-metadata y
  python organize.py /music /organized --pnm y

  # For music player compatibility (in the english language), use conservative character replacements and sanitization
  python organize.py /music /organized --replace-char "/" "-" --replace-char ":" "-" --sanitize "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_ "

  # Custom folder format with year and genre (copying files, skipping files with no metadata)
  python organize.py /music /organized --folder-format "{year}/{genre}/{albumartist}/{album}"

  # Artist-based organization with conservative sanitization, process files with no metadata, move files
  python organize.py /music /organized --folder-format "{artist}/{album}" --sanitize --pnm y --copy n

  # Detailed organization with track info and custom character replacement
  python organize.py /music /organized --folder-format "{albumartist}/{year} - {album}" --replace-char ":" "-"

Available pre-defined metadata fields:
  {title}       - Song title (searches: title, Title, TITLE, TIT2, etc.)
  {album}       - Album name (searches: album, Album, ALBUM, TALB, etc.)
  {artist}      - Track artist (searches: artist, Artist, TPE1, etc.)
  {albumartist} - Album artist (searches: albumartist, AlbumArtist, TPE2, etc.)
  {track}       - Track number (searches: track, Track, tracknumber, etc.)
  {year}        - Release year (searches: year, Year, date, Date, etc.)
  {genre}       - Music genre (searches: genre, Genre, GENRE, etc.)
  {disc}        - Disc number (searches: disc, Disc, discnumber, etc.)
  {composer}    - Composer (searches: composer, Composer, TCOM, etc.)
  {comment}     - Comment field (searches: comment, Comment, COMM, etc.)

You can also use any raw metadata tag name (case-sensitive):
  {ARTIST}      - Use exact tag name from file
  {TPE1}        - Use ID3v2 tag directly
  {Custom_Tag}  - Use any custom tag present in the file

Character replacement examples (default: no replacements, files kept as-is):
  --replace-char "/" "-"             # Replace forward slashes with dashes only
  --rc ":" "-"                       # Replace colons with dashes only (using shortcut)
  --replace-char "&" "and"           # Replace ampersands with 'and'
  --rc "/" "-" --rc "&" "and"        # Multiple replacements using shortcuts
  --replace-char "?" ""              # Remove question marks (replace with nothing)
  --rc "/" "-" --rc "\\" "-" --rc ":" "-" --rc "|" "-"  # Conservative set for music players

Sanitization examples (default: no sanitization, keep all characters):
  --sanitize                         # Enable character filtering using conservative character set
  -s                                 # Same as above using shortcut
  --dont-sanitize                    # Explicitly disable character filtering (default behavior)
  --ds                               # Same as above using shortcut
  --sanitize "abcABC123-_ "          # Enable filtering with custom allowed character set
  --s "0123456789"                   # Only allow numbers using shortcut
  --sanitize ""                      # Enable filtering with default character set

Custom sanitization examples:
  --sanitize "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_ "  # Basic set
  --sanitize "abcABC123[]()-_~@=+ "        # Include brackets and symbols (may cause issues)
  --sanitize "αβγδεζηθικλμνξοπρστυφχψω"  # Greek letters only
  --s "あいうえおかきくけこ"              # Japanese characters

Folder format tips:
  - Use forward slashes (/) to separate folder levels: "{artist}/{album}"
  - Missing fields will be empty (logged as warnings)
  - Files with no metadata are skipped by default (use --process-no-metadata y to include them)
  - When --process-no-metadata y is used, files with no metadata use filename as folder name
  - Character replacements are applied before sanitization
  - When sanitization is enabled, problematic characters are removed/replaced
  - For music player compatibility (with the english language), consider using: --sanitize "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_ " --rc "/" "-" --rc ":" "-" --rc "\\" "-" --rc "|" "-"
  - Default character set excludes apostrophes and special chars for maximum compatibility
""")
    
    # Input/Output options
    parser.add_argument(
        "source",
        help="Source directory containing audio files to organize"
    )
    parser.add_argument(
        "destination",
        help="Destination root directory for organized library"
    )
    parser.add_argument(
        "-r", "--recursive",
        action="store_true",
        default=False,
        help="Recursively process subdirectories in source (default: False)"
    )
    
    # Organization options
    parser.add_argument(
        "--folder-format",
        default=DEFAULT_FOLDER_FORMAT,
        help=f"Folder structure format using metadata fields in {{field}} syntax (default: '{DEFAULT_FOLDER_FORMAT}')"
    )
    parser.add_argument(
        "--replace-char", "--rc",
        action="append",
        nargs=2,
        metavar=("OLD", "NEW"),
        help="Replace a specific character in folder names. Takes two arguments: old character and new character (e.g., --replace-char '/' '-'). Use multiple times for multiple replacements."
    )
    parser.add_argument(
        "--dontreplace", "--dr",
        action="store_true",
        help="Disable standard character replacements. Only use custom --replace-char replacements."
    )
    parser.add_argument(
        "--sanitize", "-s",
        metavar="CHARS",
        help="Enable folder name sanitization with custom character set. Provide all allowed characters as a string (e.g., --sanitize 'abcABC123-_ '). If no characters provided, uses default set."
    )
    parser.add_argument(
        "--dont-sanitize", "--ds",
        action="store_true",
        help="Disable folder name sanitization (default: disabled). Use this to explicitly override --sanitize in longer commands where you might have accidentally included it."
    )
    
    # Behavior options
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be organized without actually moving files"
    )
    parser.add_argument(
        "--copy",
        choices=["y", "n"],
        default="y",
        help="Copy files instead of moving them: y=yes (copy, default), n=no (move files)"
    )
    parser.add_argument(
        "--skip-existing",
        action="store_true",
        default=True,
        help="Skip organization if target file already exists (default: True)"
    )
    parser.add_argument(
        "--process-no-metadata", "--pnm",
        choices=["y", "n"],
        default="n",
        help="Process files with no metadata: y=yes (use filename as folder), n=no (skip files, default)"
    )
    
    # Utility options
    parser.add_argument(
        "--logging",
        choices=["low", "high"],
        default="low",
        help="Logging level: low (default) or high (verbose)"
    )
    parser.add_argument(
        "--list-metadata",
        metavar="FILE",
        help="Show all available metadata fields for a specific file and exit"
    )
    
    return parser.parse_args()


def parse_character_replacements(replace_char_list, no_defaults=False):
    """
    Parse character replacement arguments from command line.
    
    Args:
        replace_char_list (list): List of [old_char, new_char] pairs
        no_defaults (bool): If True, don't include any default replacements
        
    Returns:
        dict: Dictionary mapping old characters to new characters
    """
    replacements = {}
    
    # Note: By default, no character replacements are applied
    # Users can add custom replacements using --replace-char
    
    # Add custom replacements
    if replace_char_list:
        for replacement_pair in replace_char_list:
            if len(replacement_pair) != 2:
                logger.error(f"Invalid character replacement: expected 2 arguments, got {len(replacement_pair)}")
                continue
                
            old_char, new_char = replacement_pair
            
            if len(old_char) != 1:
                logger.warning(f"Character replacement '{old_char}' should be a single character")
            
            replacements[old_char] = new_char
            logger.debug(f"Character replacement: '{old_char}' -> '{new_char}'")
    
    return replacements


def main():
    """
    Main function for the audio organizer.
    """
    args = parse_arguments()
    
    # Set logging level
    if args.logging == "high":
        logger.setLevel(logging.DEBUG)
    
    # Handle metadata listing request
    if args.list_metadata:
        if not os.path.isfile(args.list_metadata):
            logger.error(f"File not found: {args.list_metadata}")
            sys.exit(1)
        
        try:
            # Create a temporary organizer to get metadata
            temp_organizer = FileRelocater({})
            metadata = temp_organizer.get_file_metadata(args.list_metadata)
            
            print(f"\nMetadata for: {os.path.basename(args.list_metadata)}")
            print("-" * 60)
            
            if not metadata:
                print("No metadata found in this file.")
                return
            
            # Show pre-defined fields first
            print("Pre-defined fields (use these in folder format strings):")
            for field_name in METADATA_TAG_MAPPINGS.keys():
                value = metadata.get(field_name, '')
                status = f"'{value}'" if value else "(not found)"
                print(f"  {{{field_name}:<12}} -> {status}")
            
            # Show all raw metadata tags
            print(f"\nAll raw metadata tags (case-sensitive):")
            raw_tags = {k: v for k, v in metadata.items() if k not in METADATA_TAG_MAPPINGS}
            if raw_tags:
                for key, value in sorted(raw_tags.items()):
                    print(f"  {{{key}:<15}} -> '{value}'")
            else:
                print("  No additional raw tags found.")
            
            print(f"\nExample folder format strings:")
            print(f"  --folder-format \"{{albumartist}}/{{album}}\"")
            print(f"  --folder-format \"{{year}}/{{genre}}/{{artist}}/{{album}}\"")
            print(f"  --folder-format \"{{artist}}/{{year}} - {{album}}\"")
            
        except Exception as e:
            logger.error(f"Error reading metadata: {str(e)}")
            sys.exit(1)
        return
    
    # Validate source and destination
    if not os.path.exists(args.source):
        logger.error(f"Source directory does not exist: {args.source}")
        sys.exit(1)
    
    if not os.path.isdir(args.source):
        logger.error(f"Source must be a directory: {args.source}")
        sys.exit(1)
    
    # Parse character replacements
    char_replacements = parse_character_replacements(args.replace_char, args.dontreplace)
    
    # Determine sanitization setting (default is False)
    sanitize_enabled = False  # Default to disabled
    custom_sanitize_chars = None
    
    if args.sanitize is not None:
        sanitize_enabled = True
        custom_sanitize_chars = args.sanitize if args.sanitize else None
        if args.dont_sanitize:
            logger.warning("Both --sanitize and --dont-sanitize specified. --dont-sanitize takes priority - sanitization disabled.")
            sanitize_enabled = False
    elif args.dont_sanitize:
        sanitize_enabled = False
    
    # Determine metadata processing behavior
    process_no_metadata = args.process_no_metadata == 'y'
    skip_no_metadata = not process_no_metadata
    
    # Prepare options
    options = {
        'recursive': args.recursive,
        'dry_run': args.dry_run,
        'copy_mode': args.copy == 'y',
        'skip_existing': args.skip_existing,
        'skip_no_metadata': skip_no_metadata,
        'process_no_metadata': process_no_metadata,
        'folder_format': args.folder_format,
        'char_replacements': char_replacements,
        'dont_sanitize': not sanitize_enabled,
    }
    
    # Add custom sanitization character set if provided
    if custom_sanitize_chars:
        options['custom_sanitize_chars'] = set(custom_sanitize_chars)
        logger.info(f"Using custom character set for sanitization: '{custom_sanitize_chars}'")
    
    # Create organizer
    try:
        organizer = FileRelocater(options)
        
        # Show organization settings
        operation = "copy" if args.copy == 'y' else "move"
        logger.info(f"Using folder format: '{args.folder_format}'")
        logger.info(f"Operation mode: {operation} files")
        if char_replacements:
            replacement_info = ", ".join([f"'{old}' -> '{new}'" for old, new in char_replacements.items()])
            logger.info(f"Character replacements: {replacement_info}")
        else:
            logger.info("Character replacements: none (keeping original characters)")
        if not sanitize_enabled:
            logger.info("Folder name sanitization disabled - keeping all characters except replacements")
        else:
            logger.info("Folder name sanitization enabled - filtering to allowed character set")
        
        # Organize the library
        logger.info(f"Organizing audio library from: {args.source}")
        logger.info(f"Destination root: {args.destination}")
        
        moved_count, total_files = organizer.organize_directory(args.source, args.destination)
        
        # Final summary
        operation_verb = "copied" if args.copy == 'y' else "moved"
        if args.dry_run:
            logger.info(f"Dry run completed: {organizer.moved_count} files would be {operation_verb}")
        else:
            logger.info(f"Organization completed: {organizer.moved_count} files {operation_verb} successfully")
        
        # Show summary of what was processed
        total_processed = organizer.moved_count + organizer.skipped_count + organizer.error_count + organizer.conflict_count
        if total_processed > 0:
            logger.info(f"Summary: {organizer.moved_count} organized, {organizer.skipped_count} skipped, {organizer.error_count + organizer.conflict_count} errors")
        
        # Report any issues that occurred
        issues_found = False
        operation = "copy" if args.copy == 'y' else "move"
        if organizer.error_count > 0:
            logger.error(f"ERRORS: {organizer.error_count} files failed to {operation} due to system errors")
            issues_found = True
        
        if organizer.metadata_error_count > 0:
            logger.error(f"METADATA ERRORS: {organizer.metadata_error_count} files had unreadable metadata")
            issues_found = True
        
        if organizer.conflict_count > 0:
            logger.error(f"FILE CONFLICTS: {organizer.conflict_count} files skipped due to existing target files")
            issues_found = True
        
        if organizer.skipped_count > 0:
            logger.error(f"SKIPPED FILES: {organizer.skipped_count} files skipped due to insufficient metadata")
            logger.error("Files skipped (no metadata):")
            for skipped_file in organizer.skipped_files:
                logger.error(f"  - {skipped_file}")
            issues_found = True
        
        if issues_found:
            logger.error("=" * 60)
            logger.error("ATTENTION: Issues were encountered during processing!")
            logger.error("Please review the errors above and consider:")
            logger.error("- For metadata errors: Check if FFmpeg/FFprobe can read the files")
            logger.error("- For file conflicts: Use --skip-existing=false to auto-rename")
            logger.error("- For skipped files: Use --process-no-metadata y to include files with no metadata")
            logger.error("=" * 60)
            sys.exit(1)
        
    except Exception as e:
        logger.error(f"Error: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    main()
