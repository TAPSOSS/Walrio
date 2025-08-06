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

# Character set for file names
ALLOWED_FILE_CHARS = set('abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789[]()-_~@=+ ')

# Audio file extensions to process
AUDIO_EXTENSIONS = {'.mp3', '.flac', '.wav', '.ogg', '.m4a', '.aac', '.opus', '.wma', '.ape', '.wv'}

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
        
        # Replace problematic characters with safe alternatives
        sanitized = ""
        for char in text:
            if char in ALLOWED_FILE_CHARS:
                sanitized += char
            elif char in "?!/\\|.,&%*\":;'><":
                # Remove these completely as they can cause issues
                pass
            else:
                # Replace other characters with space
                sanitized += " "
        
        # Clean up multiple spaces and strip whitespace
        sanitized = re.sub(r'\s+', ' ', sanitized).strip()
        
        # Ensure we don't end up with an empty string
        if not sanitized:
            sanitized = "Unknown"
        
        return sanitized
    
    def get_file_metadata(self, filepath: str) -> Dict[str, str]:
        """
        Extract metadata from an audio file using FFprobe.
        
        Args:
            filepath (str): Path to the audio file
            
        Returns:
            dict: Dictionary containing title and album metadata
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
                
                # Try different common tag names for title
                for title_key in ['title', 'Title', 'TITLE', 'TIT2']:
                    if title_key in tags:
                        metadata['title'] = tags[title_key]
                        break
                
                # Try different common tag names for album
                for album_key in ['album', 'Album', 'ALBUM', 'TALB']:
                    if album_key in tags:
                        metadata['album'] = tags[album_key]
                        break
            
            return metadata
            
        except (subprocess.CalledProcessError, json.JSONDecodeError) as e:
            logger.warning(f"Could not get metadata for {filepath}: {str(e)}")
            return {}
    
    def generate_new_filename(self, filepath: str) -> Optional[str]:
        """
        Generate a new filename based on metadata in the format "(title) - (album).ext"
        
        Args:
            filepath (str): Path to the audio file
            
        Returns:
            str or None: New filename, or None if no metadata available
        """
        metadata = self.get_file_metadata(filepath)
        
        title = metadata.get('title', '').strip()
        album = metadata.get('album', '').strip()
        
        # Get file extension
        file_ext = os.path.splitext(filepath)[1].lower()
        
        # If we don't have both title and album, use fallback strategy
        if not title and not album:
            logger.warning(f"No title or album metadata found for {os.path.basename(filepath)}")
            if not self.options.get('skip_no_metadata', False):
                # Use original filename without extension as title
                original_name = os.path.splitext(os.path.basename(filepath))[0]
                title = original_name
                album = "Unknown Album"
            else:
                return None
        elif not title:
            # Use original filename without extension as title
            original_name = os.path.splitext(os.path.basename(filepath))[0]
            title = original_name
        elif not album:
            album = "Unknown Album"
        
        # Sanitize the title and album
        clean_title = self.sanitize_filename(title)
        clean_album = self.sanitize_filename(album)
        
        # Create the new filename in format: "title - album.ext"
        new_filename = f"{clean_title} - {clean_album}{file_ext}"
        
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
            logger.info(f"Skipping file with no metadata: {os.path.basename(filepath)}")
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
                logger.warning(f"Target file already exists, skipping: {new_filename}")
                return True
            else:
                # Add a number suffix to make it unique
                base_name, ext = os.path.splitext(new_filename)
                counter = 1
                while os.path.exists(new_filepath):
                    new_filename = f"{base_name} ({counter}){ext}"
                    new_filepath = os.path.join(directory, new_filename)
                    counter += 1
        
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
        description="Audio File Renamer - Rename files to '(title) - (album)' format",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="Examples:\n"
               "  # Rename a single file\n"
               "  python rename.py song.mp3\n\n"
               "  # Rename multiple files\n"
               "  python rename.py song1.mp3 song2.flac song3.wav\n\n"
               "  # Rename all files in a directory\n"
               "  python rename.py /music/directory\n\n"
               "  # Rename files recursively in subdirectories\n"
               "  python rename.py /music/directory --recursive\n\n"
               "  # Dry run to see what would be renamed\n"
               "  python rename.py /music/directory --dry-run\n\n"
               "  # Skip files without metadata\n"
               "  python rename.py /music/directory --skip-no-metadata\n"
    )
    
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
        help="Recursively process subdirectories"
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
        help="Skip renaming if target filename already exists (default: True)"
    )
    parser.add_argument(
        "--skip-no-metadata",
        action="store_true",
        help="Skip files that have no title or album metadata"
    )
    
    # Utility options
    parser.add_argument(
        "--logging",
        choices=["low", "high"],
        default="low",
        help="Logging level: low (default) or high (verbose)"
    )
    
    return parser.parse_args()


def main():
    """
    Main function for the audio renamer.
    """
    args = parse_arguments()
    
    # Set logging level
    if args.logging == "high":
        logger.setLevel(logging.DEBUG)
    
    # Prepare options
    options = {
        'recursive': args.recursive,
        'dry_run': args.dry_run,
        'skip_existing': args.skip_existing,
        'skip_no_metadata': args.skip_no_metadata,
    }
    
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
            
        if renamer.error_count > 0:
            logger.warning(f"Encountered {renamer.error_count} errors during processing")
            sys.exit(1)
        
    except Exception as e:
        logger.error(f"Error: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    main()
