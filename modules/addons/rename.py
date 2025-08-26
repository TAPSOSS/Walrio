#!/usr/bin/env python3
"""
Audio File Renamer
Copyright (c) 2025 TAPS OSS
Project: https://github.com/TAPSOSS/Walrio
Licensed under the BSD-3-Clause License (see LICENSE file for details)

A tool to rename audio files to a standardized format: "(track name) - (album)"
while removing special characters that can cause issues with music players.

For file names, includes: abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ[]()-_~@=+
"""

import os
import sys
import argparse
import subprocess
import logging
import json
import re
from pathlib import Path
from typing import List, Dict, Any, Optional, Union

# Configure logging format
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger('AudioRenamer')

# Standard character set for file names (as defined by tapscodes)
ALLOWED_FILE_CHARS = set('abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789[]()-_~@=+ ')

# Audio file extensions to process
AUDIO_EXTENSIONS = {'.mp3', '.flac', '.wav', '.ogg', '.m4a', '.aac', '.opus', '.wma', '.ape', '.wv'}

# Default naming format
DEFAULT_FORMAT = "{title} - {album} - {albumartist} - {year}"

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

class AudioRenamer:
    """
    Audio file renamer that standardizes filenames based on metadata
    """
    
    def __init__(self, options: Dict[str, Any]):
        """
        Initialize the AudioRenamer with the specified options.
        
        Args:
            options (dict): Dictionary of renaming options
        """
        self.options = options
        self.renamed_count = 0
        self.error_count = 0
        self.skipped_count = 0
        self.metadata_error_count = 0
        self.conflict_count = 0
        
        # Interactive special character handling state
        self.allow_special_all = False
        self.skip_special_all = False
        
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
    
    def prompt_allow_special_chars(self, original_name: str, sanitized_name: str) -> bool:
        """
        Prompt user whether to allow special characters when sanitization removes them.
        
        Args:
            original_name (str): Original filename before sanitization
            sanitized_name (str): Filename after sanitization
            
        Returns:
            bool: True if should allow special chars, False if should use sanitized version
        """
        if self.options.get('force_allow_special', False):
            return True
        
        if self.allow_special_all:
            return True
        
        if self.skip_special_all:
            return False
        
        print(f"\nSpecial characters detected in filename:")
        print(f"  Original:  {original_name}")
        print(f"  Sanitized: {sanitized_name}")
        print(f"Some characters were removed during sanitization.")
        
        while True:
            response = input("Keep special characters? (y)es, (n)o, (ya) yes to all, (na) no to all: ").lower().strip()
            
            if response in ['y', 'yes']:
                return True
            elif response in ['n', 'no']:
                return False
            elif response in ['ya', 'yes to all', 'yesall']:
                self.allow_special_all = True
                return True
            elif response in ['na', 'no to all', 'noall']:
                self.skip_special_all = True
                return False
            else:
                print("Please enter 'y', 'n', 'ya', or 'na'")
    
    def sanitize_filename(self, text: str) -> str:
        """
        Clean a string to be safe for use as a filename.
        
        Args:
            text (str): Text to sanitize
            
        Returns:
            str: Sanitized text
        """
        if not text:
            return "Unknown"
        
        # Store original for comparison
        original_text = text
        
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
            allowed_chars = self.options.get('custom_sanitize_chars', ALLOWED_FILE_CHARS)
            
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
        
        # Check if sanitization removed characters and prompt user if needed
        if (final_sanitized != original_text and 
            not self.options.get('dont_sanitize', False) and 
            not self.options.get('auto_sanitize', False)):
            
            # Check if there's a meaningful difference (not just whitespace cleanup)
            original_cleaned = re.sub(r'\s+', ' ', original_text).strip()
            if final_sanitized != original_cleaned:
                # Prompt user about keeping special characters
                if self.prompt_allow_special_chars(original_text, final_sanitized):
                    # User wants to keep special characters, return original with basic cleanup
                    # Still apply character replacements but skip filtering
                    result = original_text
                    for old_char, new_char in char_replacements.items():
                        result = result.replace(old_char, new_char)
                    final_sanitized = re.sub(r'\s+', ' ', result).strip()
        
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
            logger.error(f"WARNING: METADATA ERROR: Could not read metadata from {os.path.basename(filepath)}: {str(e)}")
            self.metadata_error_count += 1
            return {}
    
    def generate_new_filename(self, filepath: str) -> Optional[str]:
        """
        Generate a new filename based on metadata using the specified format.
        
        Args:
            filepath (str): Path to the audio file
            
        Returns:
            str or None: New filename, or None if format cannot be resolved
        """
        metadata = self.get_file_metadata(filepath)
        
        # Get the naming format from options
        format_string = self.options.get('format', DEFAULT_FORMAT)
        
        # Get file extension
        file_ext = os.path.splitext(filepath)[1].lower()
        
        # Parse the format string to find all required fields
        import string
        formatter = string.Formatter()
        format_fields = [field_name for _, field_name, _, _ in formatter.parse(format_string) if field_name]
        
        # Check if we have all required metadata
        missing_fields = []
        format_values = {}
        
        for field in format_fields:
            if field in metadata and metadata[field].strip():
                format_values[field] = self.sanitize_filename(metadata[field].strip())
            else:
                # Check if this is a pre-defined field that we should try harder to find
                if field in METADATA_TAG_MAPPINGS:
                    missing_fields.append(field)
                    format_values[field] = ""
                else:
                    # For custom fields, log warning and use empty string
                    logger.warning(f"WARNING: Custom metadata field '{field}' not found in {os.path.basename(filepath)} - using empty value")
                    format_values[field] = ""
        
        # Log missing pre-defined fields
        if missing_fields:
            logger.warning(f"WARNING: Missing metadata fields {missing_fields} in {os.path.basename(filepath)} - using empty values")
        
        # If skip_no_metadata is enabled and we're missing critical fields, skip the file
        if self.options.get('skip_no_metadata', False):
            # Check if any of the critical fields (title, album) are missing
            critical_fields = {'title', 'album'} & set(format_fields)
            if critical_fields and any(not format_values.get(field, '') for field in critical_fields):
                return None
        
        # Handle special case where we have no metadata at all for any field
        if all(not value for value in format_values.values()):
            if not self.options.get('skip_no_metadata', False):
                # Use original filename without extension as title
                original_name = os.path.splitext(os.path.basename(filepath))[0]
                # If format contains {title}, use original name for it
                if 'title' in format_values:
                    format_values['title'] = self.sanitize_filename(original_name)
                # For other fields, use "Unknown" prefix
                for field in format_values:
                    if not format_values[field] and field != 'title':
                        format_values[field] = f"Unknown {field.title()}"
            else:
                return None
        
        try:
            # Apply the format string
            new_filename_base = format_string.format(**format_values)
            
            # Clean up any double spaces or other formatting issues
            new_filename_base = re.sub(r'\s+', ' ', new_filename_base).strip()
            
            # Remove any leading/trailing separators
            new_filename_base = new_filename_base.strip(' -_')
            
            # Ensure we don't end up with an empty filename
            if not new_filename_base:
                new_filename_base = "Unknown"
            
            new_filename = f"{new_filename_base}{file_ext}"
            return new_filename
            
        except KeyError as e:
            logger.error(f"Invalid format string - unknown field {e} in format: {format_string}")
            return None
        except Exception as e:
            logger.error(f"Error formatting filename for {os.path.basename(filepath)}: {str(e)}")
            return None
    
    def resolve_filename_conflict(self, filepath: str, new_filename: str, directory: str) -> str:
        """
        Resolve filename conflicts by adding a counter to the title portion of the filename.
        
        Args:
            filepath (str): Original file path
            new_filename (str): Proposed new filename
            directory (str): Target directory
            
        Returns:
            str: Resolved filename with counter added to title if needed
        """
        new_filepath = os.path.join(directory, new_filename)
        
        # If no conflict, return original filename
        if not os.path.exists(new_filepath):
            return new_filename
        
        # Get file extension
        file_ext = os.path.splitext(new_filename)[1]
        filename_base = os.path.splitext(new_filename)[0]
        
        # Try to parse the filename format to identify the title portion
        format_string = self.options.get('format', DEFAULT_FORMAT)
        metadata = self.get_file_metadata(filepath)
        
        # Create a mapping to find where title appears in the format
        import string
        formatter = string.Formatter()
        format_fields = [field_name for _, field_name, _, _ in formatter.parse(format_string) if field_name]
        
        counter = 2  # Start with (2) since the original is like (1)
        
        # If we can identify the title field, add counter to it
        if 'title' in format_fields and 'title' in metadata:
            original_title = metadata['title']
            
            while os.path.exists(new_filepath):
                # Create new metadata with modified title
                modified_metadata = metadata.copy()
                modified_metadata['title'] = f"{original_title} ({counter})"
                
                # Sanitize the modified title
                sanitized_title = self.sanitize_filename(modified_metadata['title'])
                modified_metadata['title'] = sanitized_title
                
                # Generate new filename with modified title
                try:
                    # Build format values
                    format_values = {}
                    for field in format_fields:
                        if field in modified_metadata and modified_metadata[field].strip():
                            if field == 'title':
                                format_values[field] = modified_metadata[field]  # Already sanitized above
                            else:
                                format_values[field] = self.sanitize_filename(modified_metadata[field].strip())
                        else:
                            format_values[field] = ""
                    
                    # Apply the format string
                    new_filename_base = format_string.format(**format_values)
                    new_filename_base = re.sub(r'\s+', ' ', new_filename_base).strip()
                    new_filename_base = new_filename_base.strip(' -_')
                    
                    if not new_filename_base:
                        new_filename_base = "Unknown"
                    
                    new_filename = f"{new_filename_base}{file_ext}"
                    new_filepath = os.path.join(directory, new_filename)
                    counter += 1
                    
                except Exception:
                    # If format parsing fails, fall back to simple counter on whole filename
                    break
            else:
                # Successfully found a unique filename using title modification
                return new_filename
        
        # Fallback: add counter to the end of the entire filename
        counter = 2
        base_name = filename_base
        new_filename = f"{base_name} ({counter}){file_ext}"
        new_filepath = os.path.join(directory, new_filename)
        
        while os.path.exists(new_filepath):
            counter += 1
            new_filename = f"{base_name} ({counter}){file_ext}"
            new_filepath = os.path.join(directory, new_filename)
        
        return new_filename
    
    def rename_file(self, filepath: str) -> bool:
        """
        Rename a single audio file based on its metadata.
        
        Args:
            filepath (str): Path to the audio file
            
        Returns:
            bool: True if rename was successful, False otherwise
        """
        if not os.path.isfile(filepath):
            logger.error(f"File does not exist: {filepath}")
            return False
        
        # Check if it's an audio file
        file_ext = os.path.splitext(filepath)[1].lower()
        if file_ext not in AUDIO_EXTENSIONS:
            logger.debug(f"Skipping non-audio file: {os.path.basename(filepath)}")
            return True
        
        # Generate new filename
        new_filename = self.generate_new_filename(filepath)
        if not new_filename:
            logger.error(f"SKIPPED: File has insufficient metadata for renaming: {os.path.basename(filepath)}")
            self.skipped_count += 1
            return True
        
        # Get directory and construct new path
        directory = os.path.dirname(filepath)
        new_filepath = os.path.join(directory, new_filename)
        
        # Check if the new filename is the same as the current one
        if os.path.basename(filepath) == new_filename:
            logger.debug(f"File already has correct name: {new_filename}")
            return True
        
        # Check if target file already exists
        if os.path.exists(new_filepath):
            if self.options.get('skip_existing', True):
                logger.error(f"CONFLICT: Target file already exists, skipping: {new_filename}")
                self.conflict_count += 1
                return True
            else:
                # Resolve conflict by adding counter to title
                resolved_filename = self.resolve_filename_conflict(filepath, new_filename, directory)
                if resolved_filename != new_filename:
                    logger.warning(f"File conflict resolved by modifying title: {resolved_filename}")
                    new_filename = resolved_filename
                    new_filepath = os.path.join(directory, new_filename)
        
        # Perform the rename
        try:
            if self.options.get('dry_run', False):
                logger.info(f"[DRY RUN] Would rename: {os.path.basename(filepath)} -> {new_filename}")
            else:
                os.rename(filepath, new_filepath)
                logger.info(f"Renamed: {os.path.basename(filepath)} -> {new_filename}")
            
            self.renamed_count += 1
            return True
            
        except OSError as e:
            logger.error(f"Failed to rename {os.path.basename(filepath)}: {str(e)}")
            self.error_count += 1
            return False
    
    def rename_directory(self, directory: str) -> tuple[int, int]:
        """
        Rename all audio files in a directory.
        
        Args:
            directory (str): Directory containing audio files
            
        Returns:
            tuple: (number of successful renames, total number of files processed)
        """
        if not os.path.isdir(directory):
            logger.error(f"Directory does not exist: {directory}")
            return (0, 0)
        
        # Get list of audio files
        files_to_process = []
        
        if self.options.get('recursive', False):
            # Walk through directory tree recursively
            for root, _, files in os.walk(directory):
                for file in files:
                    file_path = os.path.join(root, file)
                    if os.path.splitext(file)[1].lower() in AUDIO_EXTENSIONS:
                        files_to_process.append(file_path)
        else:
            # Non-recursive: just get files in the top directory
            files_to_process = [
                os.path.join(directory, file) 
                for file in os.listdir(directory) 
                if os.path.isfile(os.path.join(directory, file)) and
                os.path.splitext(file)[1].lower() in AUDIO_EXTENSIONS
            ]
        
        total_files = len(files_to_process)
        initial_renamed_count = self.renamed_count
        
        logger.info(f"Found {total_files} audio files to process")
        
        # Process each file
        for i, file_path in enumerate(files_to_process, 1):
            logger.debug(f"Processing file {i}/{total_files}: {os.path.basename(file_path)}")
            self.rename_file(file_path)
        
        successful_renames = self.renamed_count - initial_renamed_count
        return (successful_renames, total_files)


def parse_arguments():
    """
    Parse command line arguments.
    
    Returns:
        argparse.Namespace: Parsed arguments
    """
    parser = argparse.ArgumentParser(
        description="Audio File Renamer - Rename files using custom metadata formats",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""Examples:
  # Rename using default format: title - album
  python rename.py song.mp3

  # Custom format with artist and year
  python rename.py /music --format "{artist} - {title} ({year})"

  # Track number prefix format
  python rename.py /music --format "{track:02d} - {title}"

  # Album folder organization format
  python rename.py /music --format "{albumartist} - {album} - {title}"

  # Resolve conflicts by adding counter to title (default behavior)
  python rename.py /music

  # Disable conflict resolution, skip conflicting files instead
  python rename.py /music --resolve-conflicts false

  # Custom format with conflict resolution
  python rename.py /music --format "{artist} - {title}" --resolve-conflicts

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

Character replacement examples (default: / and \\ become ~):
  --replace-char "/" "~"             # Replace forward slashes with tildes (default)
  --rc "\\" "~"                      # Replace backslashes with tildes (default, using shortcut)
  --replace-char "&" "and"           # Replace ampersands with 'and'
  --rc "/" "~" --rc "&" "and"        # Multiple replacements using shortcuts
  --replace-char "?" ""              # Remove question marks (replace with nothing)
  --dontreplace --rc "/" "-"         # Disable defaults, only replace / with -
  --dr --rc "=" "_"                  # Disable defaults using shortcut, replace = with _

Sanitization examples (default: sanitize enabled, prompt for special chars):
  --sanitize                         # Explicitly enable character filtering (default behavior)
  --s                                # Same as above using shortcut
  --dont-sanitize                    # Disable character filtering, keep all characters (default)
  --ds                               # Same as above using shortcut
  --ds --rc "/" "~"                  # No filtering, but still replace / with ~
  --dont-sanitize --dontreplace      # No filtering or replacements at all
  --sanitize "abcABC123-_ "          # Enable filtering with custom allowed character set
  --s "0123456789"                   # Only allow numbers using shortcut
  --sanitize ""                      # Enable filtering with default character set
  --auto-sanitize                    # Automatically remove special chars without prompting
  --force-allow-special              # Always keep special chars without prompting

Conflict resolution examples (default: resolve conflicts enabled):
  python rename.py /music                       # Resolve conflicts by adding (2), (3) to title (default)
  python rename.py /music --resolve-conflicts false # Skip files with conflicting names instead
  python rename.py /music --resolve-conflicts true  # Explicitly enable conflict resolution
  python rename.py /music --skip-existing        # Also skip existing files (when combined with --resolve-conflicts false)

Custom sanitization examples:
  --sanitize "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_ "  # Basic english set
  --sanitize "abcABC123[]()-_~@=+ "        # Include brackets and symbols
  --sanitize "αβγδεζηθικλμνξοπρστυφχψω"  # Greek letters only
  --s "あいうえおかきくけこ"              # Japanese characters

Format string tips:
  - Use Python string formatting: {track:02d} for zero-padded numbers
  - Missing fields will be empty (logged as warnings)
  - Use --skip-no-metadata to skip files missing critical metadata
  - Character replacements are applied before sanitization
  - When sanitization is enabled, problematic characters are removed/replaced
  - Use --sanitize "your_chars" to define your own allowed character set
""")
    
    # Input options
    parser.add_argument(
        "input",
        nargs='+',
        help="Input file(s) or directory to process"
    )
    parser.add_argument(
        "--type",
        choices=["file", "directory", "auto"],
        default="auto",
        help="Explicitly specify if inputs are files or a directory (default: auto-detect)"
    )
    parser.add_argument(
        "-r", "--recursive",
        action="store_true",
        default=False,
        help="Recursively process subdirectories (default: False)"
    )
    
    # Format options
    parser.add_argument(
        "-f", "--format",
        default=DEFAULT_FORMAT,
        help=f"Naming format using metadata fields in {{field}} syntax (default: '{DEFAULT_FORMAT}')"
    )
    parser.add_argument(
        "--replace-char", "--rc",
        action="append",
        nargs=2,
        metavar=("OLD", "NEW"),
        help="Replace a specific character in filenames. Takes two arguments: old character and new character (e.g., --replace-char '/' '~'). Use multiple times for multiple replacements."
    )
    parser.add_argument(
        "--dontreplace", "--dr",
        action="store_true",
        help="Disable default character replacements (/ and \\ to ~). Only use custom --replace-char replacements."
    )
    parser.add_argument(
        "--sanitize", "--s",
        metavar="CHARS",
        help="Enable filename sanitization with custom character set. Provide all allowed characters as a string (e.g., --sanitize 'abcABC123-_ '). If no characters provided, uses default set."
    )
    parser.add_argument(
        "--dont-sanitize", "--ds",
        action="store_true",
        help="Disable filename sanitization (default: disabled). Use this to explicitly override --sanitize in longer commands where you might have accidentally included it."
    )
    parser.add_argument(
        "--auto-sanitize",
        action="store_true",
        help="Automatically sanitize filenames without prompting when special characters are detected (disabled by default)"
    )
    parser.add_argument(
        "--force-allow-special",
        action="store_true",
        help="Always allow special characters without prompting (disabled by default, equivalent to --dont-sanitize but still applies replacements)"
    )
    
    # Behavior options
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be renamed without actually renaming files"
    )
    parser.add_argument(
        "--skip-existing",
        action="store_true",
        default=True,
        help="Skip renaming if target filename already exists (default: True, but overridden by conflict resolution)"
    )
    parser.add_argument(
        "--resolve-conflicts",
        choices=["true", "false"],
        default="true",
        help="Resolve filename conflicts by adding counter to title (default: true)"
    )
    parser.add_argument(
        "--skip-no-metadata",
        action="store_true",
        help="Skip files that have no metadata for the specified format fields"
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
        no_defaults (bool): If True, don't include any default replacements (deprecated parameter)
        
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
    Main function for the audio renamer.
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
            # Create a temporary renamer to get metadata
            temp_renamer = AudioRenamer({})
            metadata = temp_renamer.get_file_metadata(args.list_metadata)
            
            print(f"\nMetadata for: {os.path.basename(args.list_metadata)}")
            print("-" * 60)
            
            if not metadata:
                print("No metadata found in this file.")
                return
            
            # Show pre-defined fields first
            print("Pre-defined fields (use these in format strings):")
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
            
            print(f"\nExample format strings:")
            print(f"  --format \"{{title}} - {{album}}\"")
            print(f"  --format \"{{artist}} - {{title}} ({{year}})\"")
            print(f"  --format \"{{track:02d}} - {{title}}\"")
            
        except Exception as e:
            logger.error(f"Error reading metadata: {str(e)}")
            sys.exit(1)
        return
    
    # Parse character replacements
    char_replacements = parse_character_replacements(args.replace_char, args.dontreplace)
    
    # Determine sanitization setting (default is False - disabled)
    sanitize_enabled = False  # Default is disabled
    custom_sanitize_chars = None
    
    if args.sanitize is not None:
        sanitize_enabled = True
        custom_sanitize_chars = args.sanitize if args.sanitize else None
        if args.dont_sanitize:
            logger.warning("Both --sanitize and --dont-sanitize specified. --dont-sanitize takes priority - sanitization disabled.")
            sanitize_enabled = False
    elif args.dont_sanitize:
        sanitize_enabled = False
    # If neither flag is specified, use default (False - disabled)
    
    # Handle conflict resolution
    resolve_conflicts = args.resolve_conflicts == "true"
    
    # Prepare options
    options = {
        'recursive': args.recursive,
        'dry_run': args.dry_run,
        'skip_existing': args.skip_existing and not resolve_conflicts,  # Override skip if resolve is enabled
        'skip_no_metadata': args.skip_no_metadata,
        'format': args.format,
        'char_replacements': char_replacements,
        'dont_sanitize': not sanitize_enabled,
        'auto_sanitize': args.auto_sanitize,
        'force_allow_special': args.force_allow_special,
    }
    
    # Add custom sanitization character set if provided
    if custom_sanitize_chars:
        options['custom_sanitize_chars'] = set(custom_sanitize_chars)
        logger.info(f"Using custom character set for sanitization: '{custom_sanitize_chars}'")
    
    # Create renamer
    try:
        renamer = AudioRenamer(options)
        
        # Process inputs based on type parameter
        input_files = []
        input_dirs = []
        
        for input_path in args.input:
            if args.type == "file":
                if not os.path.isfile(input_path):
                    logger.error(f"Input was specified as a file, but '{input_path}' is not a file")
                    sys.exit(1)
                input_files.append(input_path)
            elif args.type == "directory":
                if not os.path.isdir(input_path):
                    logger.error(f"Input was specified as a directory, but '{input_path}' is not a directory")
                    sys.exit(1)
                input_dirs.append(input_path)
            else:  # auto-detect
                if os.path.isfile(input_path):
                    input_files.append(input_path)
                elif os.path.isdir(input_path):
                    input_dirs.append(input_path)
                else:
                    logger.error(f"Input path '{input_path}' doesn't exist")
                    sys.exit(1)
        
        # Show format being used
        logger.info(f"Using naming format: '{args.format}'")
        if char_replacements:
            replacement_info = ", ".join([f"'{old}' -> '{new}'" for old, new in char_replacements.items()])
            logger.info(f"Character replacements: {replacement_info}")
        if not sanitize_enabled:
            logger.info("Filename sanitization disabled - keeping all characters except replacements")
        elif args.auto_sanitize:
            logger.info("Auto-sanitization enabled - special characters will be removed automatically")
        elif args.force_allow_special:
            logger.info("Force allow special characters enabled - special characters will be kept automatically")
        
        # Show conflict resolution behavior
        if resolve_conflicts:
            logger.info("Conflict resolution enabled - duplicates will have counter added to title")
        else:
            logger.info("Conflict resolution disabled - conflicting files will be skipped")
        
        # Process all files first
        if input_files:
            logger.info(f"Processing {len(input_files)} individual file(s)")
            
            for file_path in input_files:
                renamer.rename_file(file_path)
        
        # Then process all directories
        total_dir_files = 0
        total_dir_renamed = 0
        
        for dir_path in input_dirs:
            logger.info(f"Processing files in directory: {dir_path}")
            dir_renamed, dir_total = renamer.rename_directory(dir_path)
            total_dir_files += dir_total
            total_dir_renamed += dir_renamed
        
        # Final summary
        if args.dry_run:
            logger.info(f"Dry run completed: {renamer.renamed_count} files would be renamed")
        else:
            logger.info(f"Renaming completed: {renamer.renamed_count} files renamed successfully")
        
        # Report any issues that occurred
        issues_found = False
        if renamer.error_count > 0:
            logger.error(f"ERRORS: {renamer.error_count} files failed to rename due to system errors")
            issues_found = True
        
        if renamer.metadata_error_count > 0:
            logger.error(f"METADATA ERRORS: {renamer.metadata_error_count} files had unreadable metadata")
            issues_found = True
        
        if renamer.conflict_count > 0:
            logger.error(f"FILE CONFLICTS: {renamer.conflict_count} files skipped due to existing target files")
            issues_found = True
        
        if renamer.skipped_count > 0:
            logger.error(f"SKIPPED FILES: {renamer.skipped_count} files skipped due to insufficient metadata")
            issues_found = True
        
        if issues_found:
            logger.error("=" * 60)
            logger.error("ATTENTION: Issues were encountered during processing!")
            logger.error("Please review the errors above and consider:")
            logger.error("- For metadata errors: Check if FFmpeg/FFprobe can read the files")
            logger.error("- For file conflicts: Use --skip-existing=false to auto-rename")
            logger.error("- For skipped files: Use --skip-no-metadata=false to force renaming")
            logger.error("=" * 60)
            sys.exit(1)
        
    except Exception as e:
        logger.error(f"Error: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    main()
