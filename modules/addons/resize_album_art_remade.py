#!/usr/bin/env python3
"""
Resize Album Art - Extract, resize, and re-embed album art in audio files
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
    # Try alternative import paths
    try:
        from addons.image_converter_remade import convert_image
    except ImportError:
        convert_image = None
    
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


def resize_album_art(audio_file: Path,
                    size: str = "1000x1000",
                    quality: int = 100,
                    format: str = "png",
                    maintain_aspect: bool = False,
                    backup: bool = False,
                    backup_dir: Optional[Path] = None) -> bool:
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
        
    Returns:
        True if successful
    """
    if not audio_file.exists():
        logger.error(f"Audio file not found: {audio_file}")
        return False
    
    if audio_file.suffix.lower() not in AUDIO_EXTENSIONS:
        logger.error(f"Unsupported audio format: {audio_file}")
        return False
    
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
            logger.info(f"Extracting album art from {audio_file.name}")
            if not extract_album_art(audio_file, temp_extracted):
                return False
            
            # Step 2: Resize the extracted image
            logger.info(f"Resizing album art to {size}")
            
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
            
            # Step 3: Embed the resized image
            logger.info(f"Embedding resized album art into {audio_file.name}")
            success = embed_album_art(audio_file, temp_resized)
            
            if success:
                logger.info(f"Successfully resized album art in {audio_file.name}")
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
                    backup=backup,
                    backup_dir=backup_dir
                ):
                    successful += 1
            except Exception as e:
                logger.error(f"Error processing {audio_file}: {e}")
        
        logger.info(f"Successfully processed {successful}/{len(audio_files)} files")
        return successful, len(audio_files)
        
    except Exception as e:
        logger.error(f"Error scanning directory {directory}: {e}")
        return 0, 0


def main():
    parser = argparse.ArgumentParser(
        description='Resize album art in audio files',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Resize album art to default 1000x1000 PNG
  resize_album_art song.mp3

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
    parser.add_argument('input', type=Path, help='Audio file or directory')
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
    
    # Check dependencies
    if convert_image is None:
        logger.error("image_converter module not available")
        return 1
    
    try:
        if args.input.is_dir():
            successful, total = process_directory(
                directory=args.input,
                size=args.size,
                quality=args.quality,
                format=args.format,
                maintain_aspect=not args.no_maintain_aspect,
                backup=args.backup,
                backup_dir=args.backup_dir,
                recursive=args.recursive
            )
            
            print(f"\nProcessing complete:")
            print(f"  Successful: {successful}")
            print(f"  Total: {total}")
            
            return 0 if successful == total else 1
        else:
            success = resize_album_art(
                audio_file=args.input,
                size=args.size,
                quality=args.quality,
                format=args.format,
                maintain_aspect=not args.no_maintain_aspect,
                backup=args.backup,
                backup_dir=args.backup_dir
            )
            
            return 0 if success else 1
        
    except Exception as e:
        logger.error(f"Error: {e}")
        return 1


if __name__ == '__main__':
    sys.exit(main())
