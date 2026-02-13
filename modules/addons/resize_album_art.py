#!/usr/bin/env python3
"""
extract, resize, and embed album art into audio files
"""
import argparse
import logging
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import List, Optional, Tuple

# Add parent directory for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

try:
    from modules.addons.image_converter import convert_image
    from modules.core.metadata import MetadataEditor
except ImportError:
    MetadataEditor = None

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

# Supported audio formats
AUDIO_EXTENSIONS = {'.mp3', '.flac', '.ogg', '.oga', '.opus', '.m4a', '.mp4', '.aac', '.wav'}


def extract_album_art(audio_file: Path, output_image: Path) -> bool:
    """
    Extract album art from audio file using FFmpeg
    
    Args:
        audio_file: Path to audio file
        output_image: Path to save extracted album art
        
    Returns:
        True if extraction successful
    """
    try:
        # Use FFmpeg to extract album art
        cmd = [
            'ffmpeg',
            '-i', str(audio_file),
            '-an',  # No audio
            '-vcodec', 'copy',  # Copy video stream (album art)
            '-y',  # Overwrite output file
            str(output_image)
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        
        if result.returncode == 0 and output_image.exists():
            logger.info(f"Extracted album art from {audio_file.name}")
            return True
        else:
            logger.warning(f"No album art found in {audio_file.name}")
            return False
            
    except subprocess.TimeoutExpired:
        logger.error(f"Timeout extracting album art from {audio_file}")
        return False
    except Exception as e:
        logger.error(f"Error extracting album art from {audio_file}: {e}")
        return False


def embed_album_art(audio_file: Path, image_file: Path) -> bool:
    """
    Embed album art into audio file
    
    Uses MetadataEditor if available, otherwise falls back to format-specific methods
    
    Args:
        audio_file: Path to audio file
        image_file: Path to image file to embed
        
    Returns:
        True if embedding successful
    """
    if MetadataEditor:
        try:
            editor = MetadataEditor()
            # Remove old album art first
            editor.remove_album_art(str(audio_file))
            # Set new album art
            success = editor.set_album_art(str(audio_file), str(image_file))
            if success:
                logger.info(f"Embedded album art into {audio_file.name}")
            return success
        except Exception as e:
            logger.error(f"Error embedding album art: {e}")
            return False
    else:
        # Fallback: use FFmpeg for embedding
        logger.warning("MetadataEditor not available, using FFmpeg fallback")
        return embed_album_art_ffmpeg(audio_file, image_file)


def embed_album_art_ffmpeg(audio_file: Path, image_file: Path) -> bool:
    """
    Embed album art using FFmpeg (fallback method)
    
    Args:
        audio_file: Path to audio file
        image_file: Path to image file
        
    Returns:
        True if successful
    """
    try:
        temp_output = audio_file.with_suffix('.tmp' + audio_file.suffix)
        
        cmd = [
            'ffmpeg', '-i', str(audio_file),
            '-i', str(image_file),
            '-map', '0:a',  # Map audio from first input
            '-map', '1:v',  # Map video (image) from second input
            '-c', 'copy',   # Copy streams
            '-disposition:v:0', 'attached_pic',  # Mark as album art
            '-y',
            str(temp_output)
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        
        if result.returncode == 0 and temp_output.exists():
            # Replace original with temp
            shutil.move(str(temp_output), str(audio_file))
            logger.info(f"Embedded album art into {audio_file.name}")
            return True
        else:
            if temp_output.exists():
                temp_output.unlink()
            logger.error(f"Failed to embed album art: {result.stderr}")
            return False
            
    except Exception as e:
        logger.error(f"Error embedding album art: {e}")
        return False


def print_settings(size: str, quality: int, format: str, maintain_aspect: bool, backup: bool):
    """
    Print resize settings.
    
    Args:
        size: Target size for album art.
        quality: Quality setting (1-100).
        format: Output format for resized images.
        maintain_aspect: Maintain aspect ratio.
        backup: Create backups.
    """
    print("\n" + "=" * 60)
    print(f"Album Art Resize Settings:")
    print(f"  Target Size: {size}")
    print(f"  Quality: {quality}")
    print(f"  Format: {format.upper()}")
    print(f"  Maintain Aspect Ratio: {'Yes' if maintain_aspect else 'No'}")
    print(f"  Create Backups: {'Yes' if backup else 'No'}")
    print("=" * 60 + "\n")


def resize_album_art(audio_file: Path,
                    size: str = "1000x1000",
                    quality: int = 100,
                    format: str = "png",
                    maintain_aspect: bool = False,
                    backup: bool = False,
                    backup_dir: Optional[Path] = None,
                    current_file: int = None,
                    total_files: int = None) -> bool:
    """
    Resize album art in audio file
    
    Process:
    1. Extract album art using FFmpeg
    2. Resize using image_converter
    3. Re-embed using MetadataEditor/FFmpeg
    
    Args:
        audio_file: Path to audio file
        size: Target size (e.g., "1000x1000", "800x800!")
        quality: Quality setting (1-100)
        format: Output format for resized image (png, jpeg, webp)
        maintain_aspect: Whether to maintain aspect ratio
        backup: Whether to create backup
        backup_dir: Directory for backups (default: same as original)
        current_file: Current file number (for progress display)
        total_files: Total number of files (for progress display)
        
    Returns:
        True if successful
    """
    if not audio_file.exists():
        logger.error(f"Audio file not found: {audio_file}")
        return False
    
    if audio_file.suffix.lower() not in AUDIO_EXTENSIONS:
        logger.error(f"Unsupported audio format: {audio_file}")
        return False
    
    # Display progress
    if current_file and total_files:
        print(f"\nFile {current_file}/{total_files}: Processing {audio_file.name}")
    else:
        print(f"\nProcessing {audio_file.name}")
    
    # Create backup if requested
    if backup:
        if backup_dir:
            backup_dir.mkdir(parents=True, exist_ok=True)
            backup_path = backup_dir / (audio_file.name + ".backup")
        else:
            backup_path = Path(str(audio_file) + ".backup")
        
        try:
            shutil.copy2(audio_file, backup_path)
            logger.info(f"Created backup: {backup_path}")
        except Exception as e:
            logger.warning(f"Could not create backup: {e}")
    
    # Process with temporary directory
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_dir_path = Path(temp_dir)
        temp_extracted = temp_dir_path / f"extracted.{format}"
        temp_resized = temp_dir_path / f"resized.{format}"
        
        try:
            # Step 1: Extract album art
            print(f"  → Extracting album art...")
            if not extract_album_art(audio_file, temp_extracted):
                return False
            print(f"  [OK] Extraction complete")
            
            # Step 2: Resize the extracted image
            print(f"  → Resizing to {size}...")
            
            # Build geometry string
            if maintain_aspect:
                geometry = size
            else:
                # Force exact size
                if 'x' in size and not size.endswith('!'):
                    geometry = f"{size}!"
                else:
                    geometry = size
            
            if convert_image:
                success = convert_image(
                    input_path=temp_extracted,
                    output_path=temp_resized,
                    output_format=format,
                    geometry=geometry,
                    quality=quality,
                    auto_orient=True,
                    strip_metadata=True,
                    background_color="white"
                )
            else:
                logger.error("image_converter not available")
                return False
            
            if not success:
                logger.error("Failed to resize album art")
                return False
            print(f"  [OK] Resize complete")
            
            # Step 3: Embed the resized image
            print(f"  → Embedding resized album art...")
            success = embed_album_art(audio_file, temp_resized)
            
            if success:
                print(f"  [OK] Successfully resized album art in {audio_file.name}\n")
                return True
            else:
                logger.error(f"Failed to embed resized album art")
                return False
                
        except Exception as e:
            logger.error(f"Error processing {audio_file}: {e}")
            return False


def process_directory(directory: Path,
                     size: str = "1000x1000",
                     quality: int = 100,
                     format: str = "png",
                     maintain_aspect: bool = False,
                     backup: bool = False,
                     backup_dir: Optional[Path] = None,
                     recursive: bool = False) -> Tuple[int, int]:
    """
    Process all audio files in directory
    
    Args:
        directory: Directory path
        size: Target size for album art
        quality: Quality setting (1-100)
        format: Output format for resized images
        maintain_aspect: Maintain aspect ratio
        backup: Create backups
        backup_dir: Backup directory
        recursive: Process subdirectories
        
    Returns:
        Tuple of (successful_count, total_count)
    """
    audio_files = []
    
    try:
        if recursive:
            for ext in AUDIO_EXTENSIONS:
                audio_files.extend(directory.rglob(f'*{ext}'))
        else:
            for ext in AUDIO_EXTENSIONS:
                audio_files.extend(directory.glob(f'*{ext}'))
        
        if not audio_files:
            logger.warning(f"No audio files found in {directory}")
            return 0, 0
        
        # Print settings and file count
        print_settings(size, quality, format, maintain_aspect, backup)
        print(f"Found {len(audio_files)} audio file(s) to process\n")
        
        successful = 0
        for idx, audio_file in enumerate(audio_files, 1):
            try:
                if resize_album_art(
                    audio_file=audio_file,
                    size=size,
                    quality=quality,
                    format=format,
                    maintain_aspect=maintain_aspect,
                    backup=backup,
                    backup_dir=backup_dir,
                    current_file=idx,
                    total_files=len(audio_files)
                ):
                    successful += 1
            except Exception as e:
                logger.error(f"Error processing {audio_file}: {e}")
        
        print(f"\nProcessing complete:")
        print(f"  Successful: {successful}")
        print(f"  Total: {len(audio_files)}")
        if successful < len(audio_files):
            print(f"  Failed: {len(audio_files) - successful}")
        
        return successful, len(audio_files)
        
    except Exception as e:
        logger.error(f"Error scanning directory {directory}: {e}")
        return 0, 0


def main():
    """Main entry point for album art resizer - resize embedded album art in audio files."""
    parser = argparse.ArgumentParser(
        description='Resize album art in audio files',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Resize album art to default 1000x1000 PNG
  resize_album_art song.mp3

  # Process multiple files
  resize_album_art song1.mp3 song2.mp3 song3.flac

  # Resize to custom dimensions with quality setting
  resize_album_art song.mp3 --size 800x800 --quality 90

  # Force exact dimensions (ignore aspect ratio)
  resize_album_art song.mp3 --size 800x800 --no-maintain-aspect

  # Process entire directory recursively
  resize_album_art /path/to/music --recursive

  # Create backups
  resize_album_art song.mp3 --backup

  # Store backups in specific directory
  resize_album_art song.mp3 --backup --backup-dir /path/to/backups

  # Use JPEG format instead of PNG
  resize_album_art song.mp3 --format jpeg --quality 95

Supported audio formats: mp3, flac, ogg, opus, m4a, aac, wav
        """
    )
    parser.add_argument('input', type=Path, nargs='+',
                       help='Audio file(s) or directory/directories')
    parser.add_argument('-s', '--size', default='1000x1000',
                       help='Target size (default: 1000x1000)')
    parser.add_argument('-q', '--quality', type=int, default=100,
                       help='Quality (1-100, default: 100)')
    parser.add_argument('-f', '--format', default='png', choices=['png', 'jpeg', 'jpg', 'webp'],
                       help='Output format (default: png)')
    parser.add_argument('--no-maintain-aspect', action='store_true',
                       help='Force exact dimensions (ignore aspect ratio)')
    parser.add_argument('-b', '--backup', action='store_true',
                       help='Create backup of original files')
    parser.add_argument('--backup-dir', type=Path,
                       help='Directory for backups (default: same as original)')
    parser.add_argument('-r', '--recursive', action='store_true',
                       help='Process subdirectories')
    parser.add_argument('--log-level', default='INFO',
                       choices=['DEBUG', 'INFO', 'WARNING', 'ERROR'],
                       help='Logging level (default: INFO)')
    
    args = parser.parse_args()
    
    # Set log level
    logging.getLogger().setLevel(getattr(logging, args.log_level))
    
    # Validate quality
    if not 1 <= args.quality <= 100:
        logger.error("Quality must be between 1 and 100")
        return 1
    
    # Validate size format
    if not ('x' in args.size.lower() or args.size.endswith('%')):
        logger.error("Size must be in format 'WIDTHxHEIGHT' or percentage (e.g., '50%')")
        return 1
    
    # Check dependencies
    if convert_image is None:
        logger.error("image_converter module not available")
        return 1
    
    try:
        # Separate files and directories
        input_files = []
        input_dirs = []
        
        for input_path in args.input:
            if input_path.is_dir():
                input_dirs.append(input_path)
            elif input_path.is_file():
                if input_path.suffix.lower() in AUDIO_EXTENSIONS:
                    input_files.append(input_path)
                else:
                    logger.warning(f"Skipping unsupported file: {input_path}")
            else:
                logger.warning(f"Path does not exist: {input_path}")
        
        total_successful = 0
        total_files = 0
        
        # Process directories
        for directory in input_dirs:
            successful, total = process_directory(
                directory=directory,
                size=args.size,
                quality=args.quality,
                format=args.format,
                maintain_aspect=not args.no_maintain_aspect,
                backup=args.backup,
                backup_dir=args.backup_dir,
                recursive=args.recursive
            )
            total_successful += successful
            total_files += total
        
        # Process individual files
        if input_files:
            print_settings(args.size, args.quality, args.format, 
                          not args.no_maintain_aspect, args.backup)
            print(f"Found {len(input_files)} audio file(s) to process\n")
            
            for idx, audio_file in enumerate(input_files, 1):
                if resize_album_art(
                    audio_file=audio_file,
                    size=args.size,
                    quality=args.quality,
                    format=args.format,
                    maintain_aspect=not args.no_maintain_aspect,
                    backup=args.backup,
                    backup_dir=args.backup_dir,
                    current_file=idx,
                    total_files=len(input_files)
                ):
                    total_successful += 1
            total_files += len(input_files)
            
            if len(input_files) > 0:
                print(f"\nProcessing complete:")
                print(f"  Successful: {total_successful - (total_files - len(input_files))}")
                print(f"  Total: {len(input_files)}")
        
        return 0 if total_successful == total_files else 1
        
    except Exception as e:
        logger.error(f"Error: {e}")
        return 1


if __name__ == '__main__':
    sys.exit(main())