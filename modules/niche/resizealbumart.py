#!/usr/bin/env python3
"""
Resize Album Art Tool
Copyright (c) 2025 TAPS OSS
Project: https://github.com/TAPSOSS/Walrio
Licensed under the BSD-3-Clause License (see LICENSE file for details)

A utility to extract album art from audio files, resize it using imageconverter,
and embed it back into the original audio file. Useful for standardizing
album art sizes across a music collection.
"""

import os
import sys
import argparse
import logging
import tempfile
import subprocess
from pathlib import Path
from typing import List

# Add parent directory to path for module imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
from modules.addons.imageconverter import convert_image
from modules.core.metadata import MetadataEditor


def setup_logging(level: str = "INFO") -> logging.Logger:
    """
    Set up logging configuration.
    
    Args:
        level (str): Logging level ('DEBUG', 'INFO', 'WARNING', 'ERROR')
        
    Returns:
        logging.Logger: Configured logger instance
    """
    log_level = getattr(logging, level.upper(), logging.INFO)
    logging.basicConfig(
        level=log_level,
        format='%(asctime)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    return logging.getLogger(__name__)


def extract_album_art(audio_file: str, output_image: str) -> bool:
    """
    Extract album art from an audio file using FFmpeg.
    
    Args:
        audio_file (str): Path to the audio file
        output_image (str): Path where to save the extracted album art
        
    Returns:
        bool: True if extraction successful, False otherwise
    """
    logger = logging.getLogger(__name__)
    
    try:
        # Use FFmpeg to extract album art
        cmd = [
            'ffmpeg',
            '-i', audio_file,
            '-an',  # No audio
            '-vcodec', 'copy',  # Copy video stream (album art)
            '-y',  # Overwrite output file
            output_image
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        
        if result.returncode == 0 and os.path.exists(output_image):
            logger.info(f"Successfully extracted album art from {os.path.basename(audio_file)}")
            return True
        else:
            logger.warning(f"No album art found in {os.path.basename(audio_file)}")
            return False
            
    except subprocess.TimeoutExpired:
        logger.error(f"Timeout extracting album art from {audio_file}")
        return False
    except Exception as e:
        logger.error(f"Error extracting album art from {audio_file}: {e}")
        return False


def get_supported_audio_formats() -> List[str]:
    """
    Get list of supported audio file extensions.
    
    Returns:
        list: List of supported audio file extensions
    """
    return ['.mp3', '.flac', '.ogg', '.oga', '.opus', '.m4a', '.mp4', '.aac', '.wav']


def is_audio_file(filepath: str) -> bool:
    """
    Check if a file is a supported audio file.
    
    Args:
        filepath (str): Path to the file to check
        
    Returns:
        bool: True if file is a supported audio format
    """
    return Path(filepath).suffix.lower() in get_supported_audio_formats()


def resize_album_art(audio_file: str, 
                    size: str = "1000x1000",
                    quality: int = 95,
                    format: str = "jpeg",
                    maintain_aspect: bool = False,
                    backup: bool | str = False) -> bool:
    """
    Resize album art in an audio file.
    
    Args:
        audio_file (str): Path to the audio file
        size (str): Target size (e.g., "1000x1000")
        quality (int): JPEG quality (1-100)
        format (str): Output format for the resized image
        maintain_aspect (bool): Whether to maintain aspect ratio
        backup (bool): Whether to create a backup of the original file
        backup_dir (str): Directory to store backup files (default: same as original)
        
    Returns:
        bool: True if resize operation successful, False otherwise
    """
    logger = logging.getLogger(__name__)
    
    if not os.path.exists(audio_file):
        logger.error(f"Audio file not found: {audio_file}")
        return False
    
    if not is_audio_file(audio_file):
        logger.error(f"Unsupported audio format: {audio_file}")
        return False
    
    # Create backup if requested
    if backup:
        if isinstance(backup, str):
            # Create backup directory if it doesn't exist
            os.makedirs(backup, exist_ok=True)
            backup_filename = os.path.basename(audio_file) + ".backup"
            backup_path = os.path.join(backup, backup_filename)
        else:
            # Default: store backup next to original file
            backup_path = f"{audio_file}.backup"
            
        try:
            import shutil
            shutil.copy2(audio_file, backup_path)
            logger.info(f"Created backup: {backup_path}")
        except Exception as e:
            logger.warning(f"Could not create backup: {e}")
    
    # Create temporary files
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_extracted = os.path.join(temp_dir, f"extracted.{format}")
        temp_resized = os.path.join(temp_dir, f"resized.{format}")
        
        try:
            # Step 1: Extract album art
            logger.info(f"Extracting album art from {os.path.basename(audio_file)}")
            if not extract_album_art(audio_file, temp_extracted):
                logger.error(f"Failed to extract album art from {audio_file}")
                return False
            
            # Step 2: Resize the extracted image
            logger.info(f"Resizing album art to {size}")
            success = convert_image(
                input_path=temp_extracted,
                output_path=temp_resized,
                output_format=format,
                geometry=f"{size}!" if not maintain_aspect else size,
                quality=quality,
                auto_orient=True,
                strip_metadata=True,
                background_color="white"
            )
            
            if not success:
                logger.error("Failed to resize album art")
                return False
            
            # Step 3: Embed the resized image back into the audio file
            logger.info(f"Embedding resized album art back into {os.path.basename(audio_file)}")
            metadata_editor = MetadataEditor(audio_file)
            
            # Remove old album art first
            metadata_editor.remove_album_art(audio_file)
            
            # Set new album art
            success = metadata_editor.set_album_art(audio_file, temp_resized)
            
            if success:
                logger.info(f"Successfully resized album art in {os.path.basename(audio_file)}")
                return True
            else:
                logger.error(f"Failed to embed resized album art into {audio_file}")
                return False
                
        except Exception as e:
            logger.error(f"Error processing {audio_file}: {e}")
            return False


def process_directory(directory: str,
                     size: str = "1000x1000",
                     quality: int = 95,
                     format: str = "jpeg", 
                     maintain_aspect: bool = False,
                     backup: bool | str = False,
                     recursive: bool = False) -> tuple[int, int]:
    """
    Process all audio files in a directory.
    
    Args:
        directory (str): Directory path to process
        size (str): Target size for album art
        quality (int): JPEG quality
        format (str): Output format for resized images
        maintain_aspect (bool): Whether to maintain aspect ratio
        backup (bool | str): Whether to create backups, or directory path for backups
        recursive (bool): Whether to process subdirectories
        
    Returns:
        tuple: (successful_count, total_count)
    """
    logger = logging.getLogger(__name__)
    
    audio_files = []
    
    try:
        if recursive:
            for root, _, files in os.walk(directory):
                for file in files:
                    file_path = os.path.join(root, file)
                    if is_audio_file(file_path):
                        audio_files.append(file_path)
        else:
            for file in os.listdir(directory):
                file_path = os.path.join(directory, file)
                if os.path.isfile(file_path) and is_audio_file(file_path):
                    audio_files.append(file_path)
        
        logger.info(f"Found {len(audio_files)} audio files to process")
        
        successful = 0
        for audio_file in audio_files:
            try:
                if resize_album_art(
                    audio_file=audio_file,
                    size=size,
                    quality=quality,
                    format=format,
                    maintain_aspect=maintain_aspect,
                    backup=backup
                ):
                    successful += 1
            except Exception as e:
                logger.error(f"Error processing {audio_file}: {e}")
        
        logger.info(f"Successfully processed {successful}/{len(audio_files)} files")
        return successful, len(audio_files)
        
    except Exception as e:
        logger.error(f"Error scanning directory {directory}: {e}")
        return 0, 0


def parse_arguments():
    """
    Parse command line arguments.
    
    Returns:
        argparse.Namespace: Parsed arguments
    """
    parser = argparse.ArgumentParser(
        description="Resize Album Art - Extract, resize, and re-embed album art in audio files",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Resize album art to default 1000x1000 JPEG in a single file
  python resizealbumart.py song.mp3

  # Resize to custom dimensions with quality setting
  python resizealbumart.py song.mp3 --size 800x800 --quality 90

  # Maintain aspect ratio instead of stretching
  python resizealbumart.py song.mp3 --maintain-aspect

  # Process an entire directory recursively
  python resizealbumart.py /path/to/music/directory --recursive

  # Process with creating backups  
  python resizealbumart.py song.mp3 --backup

  # Store backups in a specific directory
  python resizealbumart.py song.mp3 --backup /path/to/backups

  # Use PNG format instead of JPEG
  python resizealbumart.py song.mp3 --format png

Supported audio formats: {}
        """.format(', '.join(get_supported_audio_formats()))
    )
    
    parser.add_argument(
        'input',
        nargs='+',
        help='Input audio file(s) or directory'
    )
    
    parser.add_argument(
        '-s', '--size',
        default='1000x1000',
        help='Target size for album art (default: 1000x1000)'
    )
    
    parser.add_argument(
        '-q', '--quality',
        type=int,
        default=95,
        help='JPEG quality for resized images (1-100, default: 95)'
    )
    
    parser.add_argument(
        '-f', '--format',
        default='jpeg',
        choices=['jpeg', 'jpg', 'png', 'webp'],
        help='Output format for resized album art (default: jpeg)'
    )
    
    parser.add_argument(
        '--maintain-aspect',
        action='store_true',
        help='Maintain aspect ratio instead of stretching to exact dimensions'
    )
    
    parser.add_argument(
        '--backup',
        nargs='?',
        const=True,
        help='Create backup files before processing. Optionally specify a directory path to store backups (default: same location as original files)'
    )
    
    parser.add_argument(
        '-r', '--recursive',
        action='store_true',
        help='Process directories recursively'
    )
    
    parser.add_argument(
        '--logging',
        choices=['DEBUG', 'INFO', 'WARNING', 'ERROR'],
        default='INFO',
        help='Logging level (default: INFO)'
    )
    
    return parser.parse_args()


def main():
    """
    Main function for the resize album art tool.
    """
    args = parse_arguments()
    
    # Set up logging
    logger = setup_logging(args.logging)
    
    # Check dependencies
    try:
        # Check if FFmpeg is available
        subprocess.run(['ffmpeg', '-version'], capture_output=True, timeout=5)
    except (subprocess.TimeoutExpired, FileNotFoundError):
        logger.error("FFmpeg is not installed or not in PATH")
        logger.error("Please install FFmpeg to extract album art")
        sys.exit(1)
    
    # Validate quality
    if not 1 <= args.quality <= 100:
        logger.error("Quality must be between 1 and 100")
        sys.exit(1)
    
    # Validate size format
    if not ('x' in args.size or args.size.endswith('%')):
        logger.error("Size must be in format 'WIDTHxHEIGHT' or percentage (e.g., '50%')")
        sys.exit(1)
    
    # Validate backup directory if specified as a string
    if isinstance(args.backup, str):
        try:
            os.makedirs(args.backup, exist_ok=True)
        except Exception as e:
            logger.error(f"Cannot create backup directory '{args.backup}': {e}")
            sys.exit(1)
    
    # Collect input files
    input_files = []
    for input_path in args.input:
        if os.path.isfile(input_path):
            if is_audio_file(input_path):
                input_files.append(input_path)
            else:
                logger.warning(f"Skipping unsupported file: {input_path}")
        elif os.path.isdir(input_path):
            successful, total = process_directory(
                directory=input_path,
                size=args.size,
                quality=args.quality,
                format=args.format,
                maintain_aspect=args.maintain_aspect,
                backup=args.backup,
                recursive=args.recursive
            )
            logger.info(f"Directory processing complete: {successful}/{total} successful")
        else:
            logger.warning(f"Input path does not exist: {input_path}")
    
    if not input_files and not any(os.path.isdir(path) for path in args.input):
        logger.error("No valid audio files found")
        sys.exit(1)
    
    # Process individual files
    successful = 0
    for audio_file in input_files:
        try:
            if resize_album_art(
                audio_file=audio_file,
                size=args.size,
                quality=args.quality,
                format=args.format,
                maintain_aspect=args.maintain_aspect,
                backup=args.backup
            ):
                successful += 1
        except Exception as e:
            logger.error(f"Error processing {audio_file}: {e}")
    
    if input_files:
        logger.info(f"Individual file processing complete: {successful}/{len(input_files)} successful")
    
    # Exit with appropriate code
    total_files = len(input_files)
    if total_files > 0:
        sys.exit(0 if successful == total_files else 1)
    else:
        sys.exit(0)


if __name__ == "__main__":
    main()
