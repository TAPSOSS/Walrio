#!/usr/bin/env python3
"""
clone a playlist somewhere else with options for conversion
"""

import os
import sys
import argparse
import logging
import shutil
from pathlib import Path
from typing import List, Dict, Optional, Tuple

# Add parent directory to path for module imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from addons.convert import AudioConverter, SUPPORTED_OUTPUT_FORMATS, BITRATE_PRESETS
from addons.resize_album_art import resize_album_art

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger('PlaylistCloner')


class PlaylistCloner:
    """
    Clones audio files from a playlist to a destination directory with optional format conversion.
    """
    
    def __init__(self, 
                 playlist_path: str,
                 output_dir: str,
                 output_format: str = 'aac',
                 bitrate: str = '256k',
                 preserve_structure: bool = True,
                 skip_existing: bool = True,
                 dry_run: bool = False,
                 album_art_size: str = '1000x1000',
                 album_art_format: str = 'jpg',
                 dont_resize: bool = True,
                 dont_convert: bool = True):
        """
        Initialize the PlaylistCloner.
        
        Args:
            playlist_path (str): Path to the M3U playlist file
            output_dir (str): Destination directory for cloned files
            output_format (str): Output audio format (default: aac)
            bitrate (str): Bitrate for lossy formats (default: 256k)
            preserve_structure (bool): If True, preserve folder structure; if False, flatten (default: True)
            skip_existing (bool): Skip files that already exist in destination
            dry_run (bool): If True, show what would be done without actually doing it
            album_art_size (str): Album art size for resizing (default: 1000x1000)
            album_art_format (str): Album art format (jpg, png, etc.) (default: jpg)
            dont_resize (bool): Skip album art resizing (default: False)
            dont_convert (bool): Skip format conversion, only copy files (default: False)
        """
        self.playlist_path = playlist_path
        self.output_dir = output_dir
        self.output_format = output_format
        self.bitrate = bitrate
        self.preserve_structure = preserve_structure
        self.skip_existing = skip_existing
        self.dry_run = dry_run
        self.album_art_size = album_art_size
        self.album_art_format = album_art_format
        self.dont_resize = dont_resize
        self.dont_convert = dont_convert
        
        # Statistics
        self.total_files = 0
        self.converted_files = 0
        self.copied_files = 0
        self.skipped_files = 0
        self.error_files = 0
        
        # Validate playlist exists
        if not os.path.isfile(playlist_path):
            raise FileNotFoundError(f"Playlist file not found: {playlist_path}")
        
        # Validate output format
        if output_format not in SUPPORTED_OUTPUT_FORMATS:
            raise ValueError(f"Unsupported output format: {output_format}")
    
    def _load_playlist_paths(self) -> List[str]:
        """
        Load file paths from the M3U playlist.
        
        Returns:
            List[str]: List of absolute file paths
        """
        paths = []
        playlist_dir = os.path.dirname(os.path.abspath(self.playlist_path))
        
        try:
            with open(self.playlist_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()
            
            for line in lines:
                line = line.strip()
                
                # Skip empty lines and comments
                if not line or line.startswith('#'):
                    continue
                
                # Convert relative paths to absolute
                if not os.path.isabs(line):
                    file_path = os.path.abspath(os.path.join(playlist_dir, line))
                else:
                    file_path = line
                
                # Check if file exists
                if os.path.isfile(file_path):
                    paths.append(file_path)
                else:
                    logger.warning(f"File not found: {file_path}")
                    self.error_files += 1
            
            return paths
        except Exception as e:
            logger.error(f"Error loading playlist: {str(e)}")
            return []
    
    def _get_output_path(self, input_file: str) -> str:
        """
        Determine the output path for a file.
        
        Args:
            input_file (str): Input file path
            
        Returns:
            str: Output file path
        """
        # Get output extension
        output_ext = SUPPORTED_OUTPUT_FORMATS[self.output_format]['ext']
        base_name = os.path.splitext(os.path.basename(input_file))[0]
        
        # Create Music subfolder within output directory
        music_output_dir = os.path.join(self.output_dir, 'Music')
        
        if self.preserve_structure:
            # Preserve the directory structure relative to the playlist location
            playlist_dir = os.path.dirname(os.path.abspath(self.playlist_path))
            input_abs = os.path.abspath(input_file)
            
            # Try to get relative path from playlist directory
            try:
                rel_path = os.path.relpath(os.path.dirname(input_abs), playlist_dir)
                output_subdir = os.path.join(music_output_dir, rel_path)
            except ValueError:
                # If files are on different drives, just use basename
                output_subdir = music_output_dir
            
            os.makedirs(output_subdir, exist_ok=True)
            return os.path.join(output_subdir, f"{base_name}.{output_ext}")
        else:
            # Flatten to Music directory
            os.makedirs(music_output_dir, exist_ok=True)
            return os.path.join(music_output_dir, f"{base_name}.{output_ext}")
    
    def _needs_conversion(self, input_file: str) -> bool:
        """
        Check if file needs conversion or can be copied.
        
        Args:
            input_file (str): Input file path
            
        Returns:
            bool: True if conversion needed, False if can be copied
        """
        input_ext = os.path.splitext(input_file)[1].lower().lstrip('.')
        output_ext = SUPPORTED_OUTPUT_FORMATS[self.output_format]['ext']
        
        # If extensions match, no conversion needed
        return input_ext != output_ext
    
    def clone_playlist(self) -> Tuple[int, int, int, int]:
        """
        Clone all files from the playlist to the output directory.
        
        Returns:
            Tuple[int, int, int, int]: (total, converted, copied, skipped, errors)
        """
        logger.info(f"Loading playlist: {self.playlist_path}")
        file_paths = self._load_playlist_paths()
        
        if not file_paths:
            logger.error("No valid files found in playlist")
            return 0, 0, 0, 0, self.error_files
        
        self.total_files = len(file_paths)
        logger.info(f"Found {self.total_files} files in playlist")
        logger.info(f"Output directory: {self.output_dir}")
        logger.info(f"Output format: {self.output_format} @ {self.bitrate}")
        logger.info(f"Structure: {'Preserved' if self.preserve_structure else 'Flattened'}")
        
        if self.dry_run:
            logger.info("[DRY RUN MODE] - No files will be modified")
        
        logger.info("=" * 80)
        
        # Create output directory
        if not self.dry_run:
            os.makedirs(self.output_dir, exist_ok=True)
        
        # Setup converter
        converter_options = {
            'output_format': self.output_format,
            'bitrate': self.bitrate,
            'metadata': 'y',
            'skip_existing': self.skip_existing,
            'force_overwrite': False,
        }
        converter = AudioConverter(converter_options)
        
        # Step 1: Update playlist file first (before converting files)
        if not self.dry_run:
            output_ext = SUPPORTED_OUTPUT_FORMATS[self.output_format]['ext']
            playlist_name = os.path.basename(self.playlist_path)
            output_playlist_path = os.path.join(self.output_dir, playlist_name)
            
            logger.info(f"Updating playlist file: {playlist_name}")
            
            # Read original playlist
            with open(self.playlist_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()
            
            # Update file extensions and paths in playlist
            updated_lines = []
            for line in lines:
                stripped = line.strip()
                if stripped and not stripped.startswith('#'):
                    # This is a file path - update extension and prepend Music/ folder
                    base = os.path.splitext(stripped)[0]
                    # If path starts with ../ (relative), keep it; otherwise make it relative to Music folder
                    if stripped.startswith('../'):
                        updated_line = f"{base}.{output_ext}\n"
                    else:
                        # Extract just the relative path portion and prepend Music/
                        updated_line = f"Music/{base}.{output_ext}\n"
                    updated_lines.append(updated_line)
                else:
                    # Comment or empty line - keep as is
                    updated_lines.append(line)
            
            # Write updated playlist
            with open(output_playlist_path, 'w', encoding='utf-8') as f:
                f.writelines(updated_lines)
            
            logger.info(f"  ✓ Playlist file updated: {playlist_name}")
            logger.info("=" * 80)
        
        # Step 2: Process each audio file
        logger.info("Converting audio files...")
        logger.info("=" * 80)
        
        for idx, input_file in enumerate(file_paths, 1):
            output_path = self._get_output_path(input_file)
            filename = os.path.basename(input_file)
            
            logger.info(f"[{idx}/{self.total_files}] Processing: {filename}")
            
            # Check if output file already exists
            if self.skip_existing and os.path.exists(output_path):
                logger.info(f"  → Skipped (already exists): {os.path.basename(output_path)}")
                self.skipped_files += 1
                continue
            
            if self.dry_run:
                if self._needs_conversion(input_file):
                    logger.info(f"  → Would convert to: {os.path.basename(output_path)}")
                else:
                    logger.info(f"  → Would copy to: {os.path.basename(output_path)}")
                continue
            
            # Check if conversion is needed
            if self._needs_conversion(input_file) and not self.dont_convert:
                # Convert the file
                output_subdir = os.path.dirname(output_path)
                success, reason = converter.convert_file(input_file, output_subdir)
                
                if success and reason == 'converted':
                    logger.info(f"  ✓ Converted to: {os.path.basename(output_path)}")
                    self.converted_files += 1
                    
                    # Resize album art if requested and not disabled
                    if self.album_art_size and not self.dont_resize:
                        try:
                            format_map = {
                                'jpg': 'jpeg',
                                'jpeg': 'jpeg',
                                'png': 'png',
                                'gif': 'gif',
                                'webp': 'webp',
                            }
                            resize_format = format_map.get(self.album_art_format.lower(), 'jpeg')
                            
                            logger.info(f"  Resizing album art to {self.album_art_size} ({self.album_art_format})")
                            success = resize_album_art(
                                audio_file=output_path,
                                size=self.album_art_size,
                                quality=100,
                                format=resize_format,
                                maintain_aspect=False,
                                backup=False
                            )
                            
                            if success:
                                logger.info(f"  ✓ Album art resized successfully")
                            else:
                                logger.warning(f"  ⚠ Failed to resize album art")
                        except Exception as e:
                            logger.warning(f"  ⚠ Error resizing album art: {str(e)}")
                elif success and reason in ('already_target_format', 'skipped_existing'):
                    logger.info(f"  → Skipped: {reason}")
                    self.skipped_files += 1
                else:
                    logger.error(f"  ✗ Conversion failed")
                    self.error_files += 1
            else:
                # Copy the file (already in target format)
                try:
                    os.makedirs(os.path.dirname(output_path), exist_ok=True)
                    shutil.copy2(input_file, output_path)
                    logger.info(f"  ✓ Copied to: {os.path.basename(output_path)}")
                    self.copied_files += 1
                except Exception as e:
                    logger.error(f"  ✗ Copy failed: {str(e)}")
                    self.error_files += 1
        
        logger.info("=" * 80)
        logger.info(f"Cloning completed!")
        logger.info(f"Total files: {self.total_files}")
        logger.info(f"Converted: {self.converted_files}")
        logger.info(f"Copied: {self.copied_files}")
        logger.info(f"Skipped: {self.skipped_files}")
        logger.info(f"Errors: {self.error_files}")
        
        return self.total_files, self.converted_files, self.copied_files, self.skipped_files, self.error_files


def parse_arguments():
    """
    Parse command line arguments.
    
    Returns:
        argparse.Namespace: Parsed arguments
    """
    parser = argparse.ArgumentParser(
        description="Clone audio files from playlist(s) to a new directory with optional format conversion",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""Examples:
  # Clone single playlist (just copy files, no conversion or resizing by default)
  python playlist_cloner.py my_playlist.m3u /media/usb/music/
  
  # Clone multiple playlists
  python playlist_cloner.py playlist1.m3u playlist2.m3u playlist3.m3u /output/
  
  # Clone all playlists from a directory
  python playlist_cloner.py --playlist-dir /path/to/playlists /output/
  
  # Clone all playlists from directory with separate subdirectories for each
  python playlist_cloner.py --playlist-dir /path/to/playlists /output/ --separate-dirs
  
  # Clone all playlists with 256kbps AAC conversion
  python playlist_cloner.py --playlist-dir /path/to/playlists /output/ --format aac --bitrate 256k
  
  # Clone with MP3 format at 320kbps, no resizing
  python playlist_cloner.py my_playlist.m3u /output/ --format mp3 --bitrate 320k --dont-resize
  
  # Clone with preserved folder structure and resize album art to 1000x1000
  python playlist_cloner.py my_playlist.m3u /output/ --preserve-structure --album-art-size 1000x1000 --album-art-format jpg
  
  # Clone to FLAC (lossless) - good for archival
  python playlist_cloner.py my_playlist.m3u /backup/ --format flac
  
  # Dry run to see what would happen
  python playlist_cloner.py --playlist-dir /path/to/playlists /output/ --dry-run

Supported output formats:
  mp3   - MP3 (MPEG Layer III)
  aac   - AAC (Advanced Audio Coding)
  opus  - Opus (default - best quality/size ratio)
  ogg   - Ogg Vorbis
  flac  - FLAC (lossless)
  alac  - Apple Lossless
  wav   - WAV (uncompressed)

Common bitrate presets:
  Opus: 64k (low), 128k (medium), 192k (high - default), 256k (maximum)
  MP3:  96k (low), 192k (medium), 320k (high)
  AAC:  96k (low), 192k (medium), 256k (high)
"""
    )
    
    parser.add_argument(
        'playlist',
        nargs='*',
        help='Path to one or more M3U playlist files (or use --playlist-dir)'
    )
    
    parser.add_argument(
        'output_dir',
        nargs='?',
        help='Destination directory for cloned files (or use --output)'
    )
    
    parser.add_argument(
        '--playlist-dir', '--pd',
        dest='playlist_dir',
        help='Directory containing M3U playlist files to process'
    )
    
    parser.add_argument(
        '--output', '-o',
        dest='output_option',
        help='Output directory (alternative to positional argument)'
    )
    
    parser.add_argument(
        '--format', '-f',
        dest='output_format',
        choices=list(SUPPORTED_OUTPUT_FORMATS.keys()),
        default='aac',
        help='Output audio format (default: aac)'
    )
    
    parser.add_argument(
        '--bitrate', '-b',
        default='256k',
        help='Bitrate for lossy formats (e.g., 192k, 320k) (default: 256k)'
    )
    
    parser.add_argument(
        '--flatten', '--fl',
        action='store_true',
        help='Flatten folder structure (default: preserve structure from source)'
    )
    
    parser.add_argument(
        '--skip-existing', '-s',
        action='store_true',
        default=True,
        help='Skip files that already exist in destination (default: True)'
    )
    
    parser.add_argument(
        '--overwrite', '--ow',
        action='store_true',
        help='Overwrite existing files in destination'
    )
    
    parser.add_argument(
        '--dry-run', '-d',
        action='store_true',
        help='Show what would be done without actually doing it'
    )
    
    parser.add_argument(
        '--album-art-size', '-as',
        default='1000x1000',
        help='Album art size for resizing during cloning (default: 1000x1000)'
    )
    
    parser.add_argument(
        '--album-art-format', '-af',
        default='jpg',
        help='Album art format for resizing (jpg, png, etc.) (default: jpg)'
    )
    
    parser.add_argument(
        '--dont-resize', '--dr',
        action='store_true',
        dest='dont_resize',
        help='Skip album art resizing during cloning'
    )
    
    parser.add_argument(
        '--dont-convert', '--dc',
        action='store_true',
        dest='dont_convert',
        help='Skip format conversion, only copy files'
    )
    
    parser.add_argument(
        '--separate-dirs', '--sd',
        action='store_true',
        dest='separate_dirs',
        help='Create separate subdirectories for each playlist (uses playlist name as subdirectory)'
    )
    
    parser.add_argument(
        '--batch', '--batch-mode',
        action='store_true',
        dest='batch_mode',
        help='Use batch mode: update all playlists first, then convert unique files once (recommended for multiple playlists)'
    )
    
    return parser.parse_args()


def clone_playlists_batch(playlist_files: List[str], 
                          output_dir: str,
                          output_format: str = 'opus',
                          bitrate: str = '160k',
                          preserve_structure: bool = True,
                          skip_existing: bool = True,
                          dry_run: bool = False,
                          album_art_size: str = '1000x1000',
                          album_art_format: str = 'jpg',
                          dont_resize: bool = True,
                          dont_convert: bool = False,
                          separate_dirs: bool = False) -> Tuple[int, int, int, int, int]:
    """
    Clone multiple playlists in an optimized batch mode.
    First updates all playlist files, then converts unique files only once.
    
    Args:
        playlist_files (List[str]): List of playlist file paths
        output_dir (str): Output directory
        output_format (str): Target audio format
        bitrate (str): Bitrate for lossy formats
        preserve_structure (bool): Preserve directory structure
        skip_existing (bool): Skip existing files
        dry_run (bool): Preview mode
        album_art_size (str): Album art resize dimensions
        album_art_format (str): Album art format
        dont_resize (bool): Skip album art resizing
        dont_convert (bool): Skip conversion, only copy
        separate_dirs (bool): Create separate directories per playlist
        
    Returns:
        Tuple of (total, converted, copied, skipped, errors)
    """
    logger.info("=" * 80)
    logger.info("BATCH MODE: Processing all playlists efficiently")
    logger.info("=" * 80)
    
    # Step 1: Collect all unique files from all playlists
    logger.info("Step 1: Scanning all playlists to find unique files...")
    all_files = set()
    playlist_mappings = {}  # Maps playlist to its files
    
    for playlist_path in playlist_files:
        logger.info(f"  Scanning: {os.path.basename(playlist_path)}")
        cloner = PlaylistCloner(
            playlist_path=playlist_path,
            output_dir=output_dir,
            output_format=output_format,
            bitrate=bitrate,
            preserve_structure=preserve_structure,
            skip_existing=skip_existing,
            dry_run=dry_run,
            album_art_size=album_art_size,
            album_art_format=album_art_format,
            dont_resize=dont_resize,
            dont_convert=dont_convert
        )
        
        file_paths = cloner._load_playlist_paths()
        playlist_mappings[playlist_path] = file_paths
        all_files.update(file_paths)
    
    total_files = len(all_files)
    logger.info(f"Found {total_files} unique files across {len(playlist_files)} playlists")
    
    # Step 2: Update all playlist files to reference new format
    logger.info("\nStep 2: Updating playlist files to reference new format...")
    output_ext = SUPPORTED_OUTPUT_FORMATS[output_format]['ext']
    
    for playlist_path in playlist_files:
        playlist_name = os.path.basename(playlist_path)
        
        # Determine output playlist directory
        if separate_dirs:
            playlist_basename = os.path.splitext(playlist_name)[0]
            playlist_output_dir = os.path.join(output_dir, playlist_basename)
        else:
            playlist_output_dir = output_dir
        
        output_playlist_path = os.path.join(playlist_output_dir, playlist_name)
        
        if not dry_run:
            os.makedirs(playlist_output_dir, exist_ok=True)
            
            # Read original playlist
            with open(playlist_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()
            
            # Update file extensions and paths in playlist
            updated_lines = []
            for line in lines:
                stripped = line.strip()
                if stripped and not stripped.startswith('#'):
                    # This is a file path - update extension and prepend Music/ folder
                    base = os.path.splitext(stripped)[0]
                    # If path starts with ../ (relative), keep it; otherwise make it relative to Music folder
                    if stripped.startswith('../'):
                        updated_line = f"{base}.{output_ext}\n"
                    else:
                        # Extract just the relative path portion and prepend Music/
                        updated_line = f"Music/{base}.{output_ext}\n"
                    updated_lines.append(updated_line)
                else:
                    # Comment or empty line - keep as is
                    updated_lines.append(line)
            
            # Write updated playlist
            with open(output_playlist_path, 'w', encoding='utf-8') as f:
                f.writelines(updated_lines)
            
            logger.info(f"  ✓ Updated: {playlist_name}")
        else:
            logger.info(f"  Would update: {playlist_name}")
    
    # Step 3: Convert all unique files once
    logger.info("\nStep 3: Converting unique audio files...")
    logger.info("=" * 80)
    
    converter_options = {
        'output_format': output_format,
        'bitrate': bitrate,
        'metadata': 'y',
        'skip_existing': skip_existing,
        'force_overwrite': False,
    }
    converter = AudioConverter(converter_options)
    
    converted_count = 0
    copied_count = 0
    skipped_count = 0
    error_count = 0
    
    # Use first playlist's cloner for structure logic
    first_cloner = PlaylistCloner(
        playlist_path=playlist_files[0],
        output_dir=output_dir,
        output_format=output_format,
        bitrate=bitrate,
        preserve_structure=preserve_structure,
        skip_existing=skip_existing,
        dry_run=dry_run,
        album_art_size=album_art_size,
        album_art_format=album_art_format,
        dont_resize=dont_resize,
        dont_convert=dont_convert
    )
    
    for idx, input_file in enumerate(sorted(all_files), 1):
        filename = os.path.basename(input_file)
        logger.info(f"[{idx}/{total_files}] Processing: {filename}")
        
        # Determine output path
        output_path = first_cloner._get_output_path(input_file)
        
        # Check if output file already exists
        if skip_existing and os.path.exists(output_path):
            logger.info(f"  → Skipped (already exists): {os.path.basename(output_path)}")
            skipped_count += 1
            continue
        
        if dry_run:
            if first_cloner._needs_conversion(input_file):
                logger.info(f"  → Would convert to: {os.path.basename(output_path)}")
            else:
                logger.info(f"  → Would copy to: {os.path.basename(output_path)}")
            continue
        
        # Convert or copy file
        if first_cloner._needs_conversion(input_file) and not dont_convert:
            output_subdir = os.path.dirname(output_path)
            success, reason = converter.convert_file(input_file, output_subdir)
            
            if success and reason == 'converted':
                logger.info(f"  ✓ Converted to: {os.path.basename(output_path)}")
                converted_count += 1
                
                # Resize album art if requested
                if album_art_size and not dont_resize:
                    try:
                        format_map = {
                            'jpg': 'jpeg', 'jpeg': 'jpeg', 'png': 'png',
                            'gif': 'gif', 'webp': 'webp',
                        }
                        resize_format = format_map.get(album_art_format.lower(), 'jpeg')
                        
                        logger.info(f"  Resizing album art to {album_art_size} ({album_art_format})")
                        success = resize_album_art(
                            audio_file=output_path,
                            size=album_art_size,
                            quality=100,
                            format=resize_format,
                            maintain_aspect=False,
                            backup=False
                        )
                        
                        if success:
                            logger.info(f"  ✓ Album art resized successfully")
                        else:
                            logger.warning(f"  ⚠ Failed to resize album art")
                    except Exception as e:
                        logger.warning(f"  ⚠ Error resizing album art: {str(e)}")
            elif success and reason in ('already_target_format', 'skipped_existing'):
                logger.info(f"  → Skipped: {reason}")
                skipped_count += 1
            else:
                logger.error(f"  ✗ Conversion failed")
                error_count += 1
        else:
            # Copy the file
            try:
                os.makedirs(os.path.dirname(output_path), exist_ok=True)
                shutil.copy2(input_file, output_path)
                logger.info(f"  ✓ Copied to: {os.path.basename(output_path)}")
                copied_count += 1
            except Exception as e:
                logger.error(f"  ✗ Copy failed: {str(e)}")
                error_count += 1
    
    logger.info("=" * 80)
    logger.info(f"Batch cloning completed!")
    logger.info(f"Total unique files: {total_files}")
    logger.info(f"Converted: {converted_count}")
    logger.info(f"Copied: {copied_count}")
    logger.info(f"Skipped: {skipped_count}")
    logger.info(f"Errors: {error_count}")
    logger.info(f"Playlists updated: {len(playlist_files)}")
    
    return total_files, converted_count, copied_count, skipped_count, error_count


def main():
    """
    Main entry point for the playlist cloner.
    """
    args = parse_arguments()
    
    # Handle overwrite flag
    skip_existing = not args.overwrite if args.overwrite else args.skip_existing
    
    # Handle flatten flag (inverts preserve_structure default)
    preserve_structure = not args.flatten if args.flatten else True
    
    # Collect playlist files to process
    playlist_files = []
    
    if args.playlist_dir:
        # Process all .m3u and .m3u8 files in the directory
        if not os.path.isdir(args.playlist_dir):
            logger.error(f"Playlist directory not found: {args.playlist_dir}")
            sys.exit(1)
        
        for file in os.listdir(args.playlist_dir):
            if file.lower().endswith(('.m3u', '.m3u8')):
                playlist_files.append(os.path.join(args.playlist_dir, file))
        
        if not playlist_files:
            logger.error(f"No playlist files found in: {args.playlist_dir}")
            sys.exit(1)
        
        logger.info(f"Found {len(playlist_files)} playlist(s) in directory")
    elif args.playlist:
        # Process specified playlist file(s)
        playlist_files = args.playlist
    else:
        logger.error("Please specify either a playlist file or use --playlist-dir")
        sys.exit(1)
    
    # Validate output directory - accept either positional or --output option
    output_dir = args.output_option if args.output_option else args.output_dir
    if not output_dir:
        # Default to "cloned_library" subfolder in the playlist directory
        if args.playlist_dir:
            output_dir = os.path.join(args.playlist_dir, "cloned_library")
            logger.info(f"No output directory specified, using default: {output_dir}")
        else:
            logger.error("Output directory is required (specify as positional argument or use --output)")
            sys.exit(1)
    
    try:
        # Process each playlist
        total_errors = 0
        total_playlists = len(playlist_files)
        
        # Use batch mode if explicitly requested or if processing multiple playlists from directory
        use_batch_mode = args.batch_mode or (args.playlist_dir and total_playlists > 1)
        
        if use_batch_mode and total_playlists > 1:
            logger.info(f"Using BATCH MODE for {total_playlists} playlists (converts each unique file only once)")
            
            total, converted, copied, skipped, errors = clone_playlists_batch(
                playlist_files=playlist_files,
                output_dir=output_dir,
                output_format=args.output_format,
                bitrate=args.bitrate,
                preserve_structure=preserve_structure,
                skip_existing=skip_existing,
                dry_run=args.dry_run,
                album_art_size=args.album_art_size,
                album_art_format=args.album_art_format,
                dont_resize=args.dont_resize,
                dont_convert=args.dont_convert,
                separate_dirs=args.separate_dirs
            )
            total_errors = errors
        else:
            # Original sequential mode
            for idx, playlist_path in enumerate(playlist_files, 1):
                # Determine output directory for this playlist
                if args.separate_dirs and total_playlists > 1:
                    # Create a subdirectory based on playlist name
                    playlist_name = os.path.splitext(os.path.basename(playlist_path))[0]
                    playlist_output_dir = os.path.join(output_dir, playlist_name)
                else:
                    playlist_output_dir = output_dir
                
                if total_playlists > 1:
                    logger.info("\n" + "=" * 80)
                    logger.info(f"Processing playlist {idx}/{total_playlists}: {os.path.basename(playlist_path)}")
                    logger.info("=" * 80)
                
                # Create playlist cloner
                cloner = PlaylistCloner(
                    playlist_path=playlist_path,
                    output_dir=playlist_output_dir,
                    output_format=args.output_format,
                    bitrate=args.bitrate,
                    preserve_structure=preserve_structure,
                    skip_existing=skip_existing,
                    dry_run=args.dry_run,
                    album_art_size=args.album_art_size,
                    album_art_format=args.album_art_format,
                    dont_resize=args.dont_resize,
                    dont_convert=args.dont_convert
                )
                
                # Clone the playlist
                total, converted, copied, skipped, errors = cloner.clone_playlist()
                total_errors += errors
            
            # Final summary if multiple playlists
            if total_playlists > 1:
                logger.info("\n" + "=" * 80)
                logger.info(f"All playlists processed! Total playlists: {total_playlists}")
                if total_errors > 0:
                    logger.warning(f"Total errors across all playlists: {total_errors}")
                logger.info("=" * 80)
        
        # Exit with error code if there were errors
        if total_errors > 0:
            sys.exit(1)
        else:
            sys.exit(0)
            
    except Exception as e:
        logger.error(f"Fatal error: {str(e)}")
        sys.exit(1)


if __name__ == '__main__':
    main()
