#!/usr/bin/env python3
"""
Metadata Editor Tool
Copyright (c) 2025 TAPS OSS
Project: https://github.com/TAPSOSS/Walrio
Licensed under the BSD-3-Clause License (see LICENSE file for details)

A tool to modify audio file metadata (tags, album art, etc.) using mutagen CLI tools.
Supports all major audio formats including MP3, FLAC, OGG, MP4, OPUS, and more.
"""

import os
import sys
import argparse
import logging
import subprocess
import json
import tempfile
from pathlib import Path
from typing import List, Dict, Any, Optional, Union

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger('MetadataEditor')

class MetadataEditor:
    """
    A comprehensive metadata editor for audio files using mutagen CLI tools.
    Supports reading and writing metadata for all major audio formats.
    """
    
    def __init__(self):
        self.supported_formats = {
            '.mp3': 'MP3',
            '.flac': 'FLAC', 
            '.ogg': 'OGG Vorbis',
            '.oga': 'OGG Vorbis',
            '.opus': 'OPUS',
            '.m4a': 'MP4/M4A',
            '.mp4': 'MP4',
            '.aac': 'AAC',
            '.wv': 'WavPack',
            '.ape': 'Monkey\'s Audio',
            '.mpc': 'Musepack',
            '.wav': 'WAV (if ID3 tags present)'
        }
        self.processed_count = 0
        self.error_count = 0
        
        # Check for mutagen CLI tools
        self._check_mutagen_tools()
    
    def _check_mutagen_tools(self):
        """Check if mutagen CLI tools are available."""
        tools = ['mid3v2', 'mutagen-pony', 'mutagen-inspect']
        available_tools = []
        
        for tool in tools:
            try:
                result = subprocess.run([tool, '--help'], capture_output=True, text=True, timeout=5)
                if result.returncode == 0:
                    available_tools.append(tool)
            except (subprocess.TimeoutExpired, FileNotFoundError):
                pass
        
        if not available_tools:
            logger.warning("No mutagen CLI tools found. Please install mutagen-tools package.")
            logger.warning("Ubuntu/Debian: sudo apt install python3-mutagen")
            logger.warning("Or via pip: pip install mutagen")
        else:
            logger.debug(f"Available mutagen tools: {', '.join(available_tools)}")
    
    def is_supported_format(self, filepath: str) -> bool:
        """Check if the file format is supported."""
        ext = Path(filepath).suffix.lower()
        return ext in self.supported_formats
    
    def get_metadata(self, filepath: str) -> Dict[str, Any]:
        """
        Get all metadata from an audio file using mutagen CLI tools.
        Returns a dictionary with standardized tag names.
        """
        if not os.path.exists(filepath):
            logger.error(f"File not found: {filepath}")
            return {}
        
        try:
            # Use mutagen-inspect to get raw metadata
            cmd = ['mutagen-inspect', str(filepath)]
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=False,
                timeout=30
            )
            
            if result.returncode != 0:
                logger.error(f"Could not read metadata from {os.path.basename(filepath)}")
                logger.debug(f"mutagen-inspect error: {result.stderr}")
                return {}
            
            # Parse the output
            metadata = self._parse_mutagen_output(result.stdout)
            metadata['filepath'] = filepath
            metadata['format'] = self._detect_format(filepath)
            
            return metadata
            
        except subprocess.TimeoutExpired:
            logger.error(f"Timeout reading metadata from {os.path.basename(filepath)}")
            return {}
        except Exception as e:
            logger.error(f"Error reading metadata from {os.path.basename(filepath)}: {str(e)}")
            return {}
    
    def _parse_mutagen_output(self, output: str) -> Dict[str, Any]:
        """Parse mutagen-inspect output into a standardized dictionary."""
        metadata = {}
        lines = output.strip().split('\n')
        
        # Standard tag mappings
        tag_mappings = {
            'TIT2': 'title',
            'TITLE': 'title',
            '\xa9nam': 'title',
            'TPE1': 'artist', 
            'ARTIST': 'artist',
            '\xa9ART': 'artist',
            'TALB': 'album',
            'ALBUM': 'album', 
            '\xa9alb': 'album',
            'TPE2': 'albumartist',
            'ALBUMARTIST': 'albumartist',
            'aART': 'albumartist',
            'TDRC': 'date',
            'DATE': 'date',
            '\xa9day': 'date',
            'TYER': 'year',
            'YEAR': 'year',
            'TCON': 'genre',
            'GENRE': 'genre',
            '\xa9gen': 'genre',
            'TRCK': 'track',
            'TRACKNUMBER': 'track',
            'trkn': 'track',
            'TPOS': 'disc',
            'DISCNUMBER': 'disc',
            'disk': 'disc',
            'COMM::eng': 'comment',
            'COMMENT': 'comment',
            '\xa9cmt': 'comment'
        }
        
        for line in lines:
            if '=' in line:
                key, value = line.split('=', 1)
                key = key.strip()
                value = value.strip()
                
                # Remove quotes if present
                if value.startswith('"') and value.endswith('"'):
                    value = value[1:-1]
                elif value.startswith("'") and value.endswith("'"):
                    value = value[1:-1]
                
                # Map to standardized keys
                standard_key = tag_mappings.get(key, key.lower())
                metadata[standard_key] = value
        
        # Check for album art
        metadata['has_album_art'] = self._has_album_art(metadata.get('filepath', ''))
        
        return metadata
    
    def _detect_format(self, filepath: str) -> str:
        """Detect the audio format from file extension."""
        ext = Path(filepath).suffix.lower()
        return self.supported_formats.get(ext, 'Unknown')
    
    def _has_album_art(self, filepath: str) -> bool:
        """Check if the audio file has album art using mutagen CLI."""
        if not filepath or not os.path.exists(filepath):
            return False
        
        try:
            # Use mutagen-inspect to check for album art
            cmd = ['mutagen-inspect', str(filepath)]
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=False,
                timeout=10
            )
            
            if result.returncode == 0:
                output = result.stdout.lower()
                # Look for common album art indicators
                art_indicators = ['apic:', 'covr', 'metadata_block_picture', 'picture']
                return any(indicator in output for indicator in art_indicators)
            
            return False
            
        except Exception:
            return False
    
    def set_metadata(self, filepath: str, metadata: Dict[str, Any]) -> bool:
        """
        Set metadata for an audio file using appropriate CLI tools.
        """
        if not os.path.exists(filepath):
            logger.error(f"File not found: {filepath}")
            return False
        
        if not self.is_supported_format(filepath):
            logger.error(f"Unsupported format: {os.path.basename(filepath)}")
            return False
        
        try:
            ext = Path(filepath).suffix.lower()
            
            # Use different tools based on format
            if ext == '.mp3':
                return self._set_mp3_metadata(filepath, metadata)
            else:
                return self._set_generic_metadata(filepath, metadata)
                
        except Exception as e:
            logger.error(f"Error setting metadata for {os.path.basename(filepath)}: {str(e)}")
            self.error_count += 1
            return False
    
    def _set_mp3_metadata(self, filepath: str, metadata: Dict[str, Any]) -> bool:
        """Set metadata for MP3 files using mid3v2."""
        try:
            cmd = ['mid3v2']
            
            # Map metadata to mid3v2 options
            tag_map = {
                'title': '--TIT2',
                'artist': '--TPE1',
                'album': '--TALB',
                'albumartist': '--TPE2',
                'date': '--TDRC',
                'year': '--TDRC',
                'genre': '--TCON',
                'track': '--TRCK',
                'disc': '--TPOS',
                'comment': '--COMM'
            }
            
            for key, value in metadata.items():
                if key in tag_map and value:
                    cmd.extend([tag_map[key], str(value)])
            
            cmd.append(str(filepath))
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=False,
                timeout=30
            )
            
            if result.returncode == 0:
                logger.info(f"Successfully updated MP3 metadata for {os.path.basename(filepath)}")
                self.processed_count += 1
                return True
            else:
                logger.error(f"mid3v2 error: {result.stderr}")
                return False
                
        except subprocess.TimeoutExpired:
            logger.error(f"Timeout setting MP3 metadata for {os.path.basename(filepath)}")
            return False
        except Exception as e:
            logger.error(f"Error setting MP3 metadata: {str(e)}")
            return False
    
    def _set_generic_metadata(self, filepath: str, metadata: Dict[str, Any]) -> bool:
        """Set metadata for non-MP3 files using mutagen-pony."""
        try:
            # Build mutagen-pony command
            cmd = ['mutagen-pony']
            
            # Add metadata as key=value pairs
            for key, value in metadata.items():
                if value:
                    # Use uppercase for standard Vorbis comment tags
                    if key in ['title', 'artist', 'album', 'albumartist', 'date', 'year', 'genre', 'track', 'disc', 'comment']:
                        tag_name = key.upper()
                        if key == 'track':
                            tag_name = 'TRACKNUMBER'
                        elif key == 'disc':
                            tag_name = 'DISCNUMBER'
                        elif key == 'albumartist':
                            tag_name = 'ALBUMARTIST'
                        
                        cmd.extend(['-t', f'{tag_name}={value}'])
            
            cmd.append(str(filepath))
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=False,
                timeout=30
            )
            
            if result.returncode == 0:
                logger.info(f"Successfully updated metadata for {os.path.basename(filepath)}")
                self.processed_count += 1
                return True
            else:
                logger.error(f"mutagen-pony error: {result.stderr}")
                return False
                
        except subprocess.TimeoutExpired:
            logger.error(f"Timeout setting metadata for {os.path.basename(filepath)}")
            return False
        except Exception as e:
            logger.error(f"Error setting metadata: {str(e)}")
            return False
    
    def set_album_art(self, filepath: str, image_path: str) -> bool:
        """
        Set album art for an audio file using CLI tools.
        """
        if not os.path.exists(image_path):
            logger.error(f"Image file not found: {image_path}")
            return False
        
        if not os.path.exists(filepath):
            logger.error(f"Audio file not found: {filepath}")
            return False
        
        try:
            ext = Path(filepath).suffix.lower()
            
            if ext == '.mp3':
                return self._set_mp3_album_art(filepath, image_path)
            else:
                return self._set_generic_album_art(filepath, image_path)
                
        except Exception as e:
            logger.error(f"Error setting album art for {os.path.basename(filepath)}: {str(e)}")
            return False
    
    def _set_mp3_album_art(self, filepath: str, image_path: str) -> bool:
        """Set album art for MP3 files using mid3v2."""
        try:
            cmd = [
                'mid3v2',
                '--APIC',
                f'{image_path}:Cover (front)',
                str(filepath)
            ]
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=False,
                timeout=30
            )
            
            if result.returncode == 0:
                logger.info(f"Successfully set album art for {os.path.basename(filepath)}")
                return True
            else:
                logger.error(f"mid3v2 album art error: {result.stderr}")
                return False
                
        except Exception as e:
            logger.error(f"Error setting MP3 album art: {str(e)}")
            return False
    
    def _set_generic_album_art(self, filepath: str, image_path: str) -> bool:
        """Set album art for non-MP3 files using eyeD3 or ffmpeg as fallback."""
        try:
            # Try eyeD3 first (if available)
            try:
                cmd = ['eyeD3', '--add-image', f'{image_path}:FRONT_COVER', str(filepath)]
                result = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    check=False,
                    timeout=30
                )
                
                if result.returncode == 0:
                    logger.info(f"Successfully set album art for {os.path.basename(filepath)} using eyeD3")
                    return True
            except FileNotFoundError:
                pass
            
            # Fallback to ffmpeg for supported formats
            logger.info(f"Using FFmpeg fallback for album art embedding in {os.path.basename(filepath)}")
            return self._set_album_art_ffmpeg(filepath, image_path)
            
        except Exception as e:
            logger.error(f"Error setting album art: {str(e)}")
            return False
    
    def _set_album_art_ffmpeg(self, filepath: str, image_path: str) -> bool:
        """Set album art using FFmpeg as a fallback method."""
        try:
            # Create temporary output file
            temp_file = filepath + '.tmp'
            
            cmd = [
                'ffmpeg', '-y',
                '-i', str(filepath),
                '-i', str(image_path),
                '-map', '0',
                '-map', '1',
                '-c', 'copy',
                '-id3v2_version', '3',
                '-metadata:s:v', 'title=Cover (front)',
                '-metadata:s:v', 'comment=Cover (front)',
                temp_file
            ]
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=False,
                timeout=60
            )
            
            if result.returncode == 0 and os.path.exists(temp_file):
                # Replace original file with the new one
                os.replace(temp_file, filepath)
                logger.info(f"Successfully set album art for {os.path.basename(filepath)} using FFmpeg")
                return True
            else:
                logger.error(f"FFmpeg album art error: {result.stderr}")
                # Clean up temp file if it exists
                if os.path.exists(temp_file):
                    os.unlink(temp_file)
                return False
                
        except Exception as e:
            logger.error(f"Error setting album art with FFmpeg: {str(e)}")
            return False
    
    def remove_album_art(self, filepath: str) -> bool:
        """Remove album art from an audio file using CLI tools."""
        if not os.path.exists(filepath):
            logger.error(f"File not found: {filepath}")
            return False
        
        try:
            ext = Path(filepath).suffix.lower()
            
            if ext == '.mp3':
                return self._remove_mp3_album_art(filepath)
            else:
                return self._remove_generic_album_art(filepath)
                
        except Exception as e:
            logger.error(f"Error removing album art from {os.path.basename(filepath)}: {str(e)}")
            return False
    
    def _remove_mp3_album_art(self, filepath: str) -> bool:
        """Remove album art from MP3 files using mid3v2."""
        try:
            cmd = ['mid3v2', '--delete-frames', 'APIC', str(filepath)]
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=False,
                timeout=30
            )
            
            if result.returncode == 0:
                logger.info(f"Successfully removed album art from {os.path.basename(filepath)}")
                return True
            else:
                logger.error(f"mid3v2 remove art error: {result.stderr}")
                return False
                
        except Exception as e:
            logger.error(f"Error removing MP3 album art: {str(e)}")
            return False
    
    def _remove_generic_album_art(self, filepath: str) -> bool:
        """Remove album art from non-MP3 files using available tools."""
        try:
            # Try eyeD3 first
            try:
                cmd = ['eyeD3', '--remove-images', str(filepath)]
                result = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    check=False,
                    timeout=30
                )
                
                if result.returncode == 0:
                    logger.info(f"Successfully removed album art from {os.path.basename(filepath)}")
                    return True
            except FileNotFoundError:
                pass
            
            # If eyeD3 not available, warn user
            logger.warning(f"Cannot remove album art from {os.path.basename(filepath)} - eyeD3 not available")
            logger.warning("Install eyeD3: pip install eyed3")
            return False
            
        except Exception as e:
            logger.error(f"Error removing album art: {str(e)}")
            return False
    
    def batch_edit_metadata(self, file_paths: List[str], metadata: Dict[str, Any]) -> Dict[str, int]:
        """
        Edit metadata for multiple files.
        Returns statistics about the operation.
        """
        self.processed_count = 0
        self.error_count = 0
        
        for filepath in file_paths:
            if not os.path.exists(filepath):
                logger.warning(f"File not found: {filepath}")
                self.error_count += 1
                continue
            
            if not self.is_supported_format(filepath):
                logger.warning(f"Unsupported format: {os.path.basename(filepath)}")
                self.error_count += 1
                continue
            
            self.set_metadata(filepath, metadata)
        
        return {
            'processed': self.processed_count,
            'errors': self.error_count,
            'total': len(file_paths)
        }
    
    def display_metadata(self, filepath: str):
        """Display metadata for a file in a readable format."""
        metadata = self.get_metadata(filepath)
        
        if not metadata:
            logger.error(f"Could not read metadata from {os.path.basename(filepath)}")
            return
        
        print(f"\nMetadata for: {os.path.basename(filepath)}")
        print("=" * 50)
        print(f"Format: {metadata.get('format', 'Unknown')}")
        print(f"Title: {metadata.get('title', 'Unknown')}")
        print(f"Artist: {metadata.get('artist', 'Unknown')}")
        print(f"Album: {metadata.get('album', 'Unknown')}")
        print(f"Album Artist: {metadata.get('albumartist', 'Unknown')}")
        print(f"Date/Year: {metadata.get('date', metadata.get('year', 'Unknown'))}")
        print(f"Genre: {metadata.get('genre', 'Unknown')}")
        print(f"Track: {metadata.get('track', 'Unknown')}")
        print(f"Disc: {metadata.get('disc', 'Unknown')}")
        print(f"Comment: {metadata.get('comment', 'None')}")
        print(f"Album Art: {'Yes' if metadata.get('has_album_art') else 'No'}")


def main():
    """Main function for command-line usage."""
    parser = argparse.ArgumentParser(
        description="Modify audio file metadata using mutagen",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Display metadata
  python metadata.py --show song.mp3
  
  # Set title and artist
  python metadata.py --set-title "New Title" --set-artist "New Artist" song.mp3
  
  # Set album art
  python metadata.py --set-album-art cover.jpg song.mp3
  
  # Remove album art
  python metadata.py --remove-album-art song.mp3
  
  # Batch edit multiple files
  python metadata.py --set-album "Album Name" *.mp3
        """
    )
    
    parser.add_argument('files', nargs='*', help='Audio files to process')
    parser.add_argument('--show', action='store_true', help='Display current metadata')
    parser.add_argument('--set-title', help='Set title tag')
    parser.add_argument('--set-artist', help='Set artist tag')
    parser.add_argument('--set-album', help='Set album tag')
    parser.add_argument('--set-albumartist', help='Set album artist tag')
    parser.add_argument('--set-date', help='Set date tag')
    parser.add_argument('--set-year', help='Set year tag')
    parser.add_argument('--set-genre', help='Set genre tag')
    parser.add_argument('--set-track', help='Set track number')
    parser.add_argument('--set-disc', help='Set disc number')
    parser.add_argument('--set-comment', help='Set comment tag')
    parser.add_argument('--set-album-art', help='Set album art from image file')
    parser.add_argument('--remove-album-art', action='store_true', help='Remove album art')
    parser.add_argument('--verbose', '-v', action='store_true', help='Enable verbose logging')
    
    args = parser.parse_args()
    
    if args.verbose:
        logger.setLevel(logging.DEBUG)
    
    if not args.files:
        parser.print_help()
        return 1
    
    editor = MetadataEditor()
    
    # Check if we're just displaying metadata
    if args.show:
        for filepath in args.files:
            if os.path.exists(filepath):
                editor.display_metadata(filepath)
            else:
                logger.error(f"File not found: {filepath}")
        return 0
    
    # Build metadata dictionary from arguments
    metadata = {}
    if args.set_title:
        metadata['title'] = args.set_title
    if args.set_artist:
        metadata['artist'] = args.set_artist
    if args.set_album:
        metadata['album'] = args.set_album
    if args.set_albumartist:
        metadata['albumartist'] = args.set_albumartist
    if args.set_date:
        metadata['date'] = args.set_date
    if args.set_year:
        metadata['year'] = args.set_year
    if args.set_genre:
        metadata['genre'] = args.set_genre
    if args.set_track:
        metadata['track'] = args.set_track
    if args.set_disc:
        metadata['disc'] = args.set_disc
    if args.set_comment:
        metadata['comment'] = args.set_comment
    
    # Process files
    success_count = 0
    
    for filepath in args.files:
        if not os.path.exists(filepath):
            logger.error(f"File not found: {filepath}")
            continue
        
        if not editor.is_supported_format(filepath):
            logger.error(f"Unsupported format: {os.path.basename(filepath)}")
            continue
        
        # Set standard metadata
        if metadata:
            if editor.set_metadata(filepath, metadata):
                success_count += 1
        
        # Handle album art operations
        if args.set_album_art:
            if editor.set_album_art(filepath, args.set_album_art):
                success_count += 1
        
        if args.remove_album_art:
            if editor.remove_album_art(filepath):
                success_count += 1
    
    logger.info(f"Successfully processed {success_count} out of {len(args.files)} files")
    return 0 if success_count > 0 else 1


if __name__ == "__main__":
    sys.exit(main())
