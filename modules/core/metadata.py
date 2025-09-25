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
import base64
import io
import re
from pathlib import Path
from typing import List, Dict, Any, Optional

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger('MetadataEditor')

# Import mutagen directly
try:
    from mutagen import File as MutagenFile
    from mutagen.id3 import ID3, APIC, TIT2, TPE1, TALB, TPE2, TDRC, TCON, TRCK, TPOS, COMM
    from mutagen.mp3 import MP3
    from mutagen.flac import FLAC, Picture
    from mutagen.oggvorbis import OggVorbis
    from mutagen.oggopus import OggOpus
    from mutagen.mp4 import MP4
    MUTAGEN_AVAILABLE = True
except ImportError:
    MUTAGEN_AVAILABLE = False

# Import Pillow for image processing
try:
    from PIL import Image
    PILLOW_AVAILABLE = True
except ImportError:
    PILLOW_AVAILABLE = False

class MetadataEditor:
    """
    A comprehensive metadata editor for audio files using mutagen CLI tools.
    Supports reading and writing metadata for all major audio formats.
    """
    
    def __init__(self):
        """
        Initialize MetadataEditor for working with audio file metadata.
        """
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
        
        # Check for mutagen library
        self._check_mutagen_library()
    
    def _check_mutagen_library(self):
        """
        Check if mutagen library is available and log warnings if needed.
        
        Logs availability of mutagen library and PIL for image processing.
        """
        if not MUTAGEN_AVAILABLE:
            logger.error("Mutagen library not found. Please install with: pip install mutagen")
            logger.error("This module requires mutagen for direct metadata manipulation.")
            
        if not PILLOW_AVAILABLE:
            logger.warning("Pillow not found. Image format detection will be limited.")
            logger.warning("Install with: pip install Pillow")
            
        if MUTAGEN_AVAILABLE:
            logger.debug("Mutagen library loaded successfully - using direct metadata access")
    
    def is_supported_format(self, filepath: str) -> bool:
        """
        Check if the file format is supported.
        
        Args:
            filepath (str): Path to the audio file to check
            
        Returns:
            bool: True if the file format is supported, False otherwise
        """
        ext = Path(filepath).suffix.lower()
        return ext in self.supported_formats
    
    def _detect_format(self, filepath: str) -> str:
        """
        Detect the audio format from file extension.
        
        Args:
            filepath (str): Path to the audio file
            
        Returns:
            str: Human-readable format name (e.g., 'MP3', 'FLAC', 'Unknown')
        """
        ext = Path(filepath).suffix.lower()
        return self.supported_formats.get(ext, 'Unknown')
    
    def get_metadata(self, filepath: str) -> Dict[str, Any]:
        """
        Get all metadata from an audio file using mutagen library directly.
        
        Args:
            filepath (str): Path to the audio file to extract metadata from
            
        Returns:
            Dict[str, Any]: Dictionary with standardized tag names and metadata values,
                          or empty dict if extraction fails
        """
        if not MUTAGEN_AVAILABLE:
            logger.error("Mutagen library not available")
            return {}
            
        if not os.path.exists(filepath):
            logger.error(f"File not found: {filepath}")
            return {}
        
        try:
            # Load the audio file using mutagen
            audio_file = MutagenFile(filepath)
            if audio_file is None:
                logger.error(f"Could not load audio file: {os.path.basename(filepath)}")
                return {}
            
            # Extract metadata using mutagen's direct access
            metadata = self._extract_mutagen_metadata(audio_file)
            metadata['filepath'] = filepath
            metadata['format'] = self._detect_format(filepath)
            metadata['has_album_art'] = self._has_album_art_mutagen(audio_file)
            
            return metadata
            
        except Exception as e:
            logger.error(f"Error reading metadata from {os.path.basename(filepath)}: {str(e)}")
            return {}
    
    def _extract_mutagen_metadata(self, audio_file) -> Dict[str, Any]:
        """
        Extract metadata from a mutagen audio file object.
        
        Args:
            audio_file: Mutagen audio file object
            
        Returns:
            Dict[str, Any]: Dictionary containing parsed metadata with standardized keys
        """
        metadata = {}
        
        if audio_file is None:
            return metadata
            
        # Handle different file formats
        # Check for ID3 tags first (can be in MP3, WAV, or other formats)
        if hasattr(audio_file, 'tags') and audio_file.tags and isinstance(audio_file.tags, ID3):
            metadata = self._extract_id3_metadata(audio_file)
        elif isinstance(audio_file, FLAC):
            metadata = self._extract_vorbis_metadata(audio_file)
        elif isinstance(audio_file, (OggVorbis, OggOpus)):
            metadata = self._extract_vorbis_metadata(audio_file)
        elif isinstance(audio_file, MP4):
            metadata = self._extract_mp4_metadata(audio_file)
        else:
            # Generic extraction for other formats
            metadata = self._extract_generic_metadata(audio_file)
            
        # Add audio properties if available
        if hasattr(audio_file, 'info') and audio_file.info:
            info = audio_file.info
            if hasattr(info, 'length'):
                metadata['length'] = getattr(info, 'length', 0)
            if hasattr(info, 'bitrate'):
                metadata['bitrate'] = getattr(info, 'bitrate', 0)
            if hasattr(info, 'sample_rate'):
                metadata['sample_rate'] = getattr(info, 'sample_rate', 0)
            if hasattr(info, 'bits_per_sample'):
                metadata['bit_depth'] = getattr(info, 'bits_per_sample', 0)
                
        return metadata
    
    def _extract_id3_metadata(self, audio_file) -> Dict[str, Any]:
        """Extract metadata from ID3 tags (MP3).
        
        Args:
            audio_file: Mutagen audio file object with ID3 tags.
            
        Returns:
            Dict[str, Any]: Dictionary containing extracted metadata.
        """
        metadata = {}
        
        if not hasattr(audio_file, 'tags') or audio_file.tags is None:
            return metadata
            
        tags = audio_file.tags
        
        # ID3 tag mappings
        tag_map = {
            'TIT2': 'title',
            'TPE1': 'artist', 
            'TALB': 'album',
            'TPE2': 'albumartist',
            'TDRC': 'date',
            'TYER': 'year',
            'TCON': 'genre',
            'TRCK': 'track',
            'TPOS': 'disc',
            'COMM::eng': 'comment',
            'TCOM': 'composer',
            'TPE3': 'performer',
            'TIT1': 'grouping',
            'USLT::eng': 'lyrics',
            'TORY': 'originalyear',
            'TCMP': 'compilation'
        }
        
        for tag_id, std_key in tag_map.items():
            if tag_id in tags:
                value = str(tags[tag_id].text[0]) if tags[tag_id].text else ''
                if value:
                    metadata[std_key] = value
                    
        return metadata
    
    def _extract_vorbis_metadata(self, audio_file) -> Dict[str, Any]:
        """Extract metadata from Vorbis comments (FLAC, OGG, OPUS).
        
        Args:
            audio_file: Mutagen audio file object with Vorbis comments.
            
        Returns:
            Dict[str, Any]: Dictionary containing extracted metadata.
        """
        metadata = {}
        
        if not hasattr(audio_file, 'tags') or audio_file.tags is None:
            return metadata
            
        tags = audio_file.tags
        
        # Vorbis comment mappings
        tag_map = {
            'TITLE': 'title',
            'ARTIST': 'artist',
            'ALBUM': 'album',
            'ALBUMARTIST': 'albumartist',
            'ALBUM ARTIST': 'albumartist',  # Alternative format with space
            'DATE': 'date',
            'YEAR': 'year',
            'GENRE': 'genre',
            'TRACKNUMBER': 'track',
            'DISCNUMBER': 'disc',
            'COMMENT': 'comment',
            'COMPOSER': 'composer',
            'PERFORMER': 'performer',
            'GROUPING': 'grouping',
            'LYRICS': 'lyrics',
            'ORIGINALDATE': 'originaldate',
            'ORIGINALYEAR': 'originalyear',
            'COMPILATION': 'compilation'
        }
        
        for tag_name, std_key in tag_map.items():
            if tag_name in tags:
                value = tags[tag_name][0] if tags[tag_name] else ''
                if value:
                    metadata[std_key] = value
                    
        return metadata
    
    def _extract_mp4_metadata(self, audio_file) -> Dict[str, Any]:
        """Extract metadata from MP4/M4A tags.
        
        Args:
            audio_file: Mutagen audio file object with MP4 tags.
            
        Returns:
            Dict[str, Any]: Dictionary containing extracted metadata.
        """
        metadata = {}
        
        if not hasattr(audio_file, 'tags') or audio_file.tags is None:
            return metadata
            
        tags = audio_file.tags
        
        # MP4 tag mappings
        tag_map = {
            '\xa9nam': 'title',
            '\xa9ART': 'artist',
            '\xa9alb': 'album', 
            'aART': 'albumartist',
            '\xa9day': 'date',
            '\xa9gen': 'genre',
            'trkn': 'track',
            'disk': 'disc',
            '\xa9cmt': 'comment',
            '\xa9wrt': 'composer',
            '\xa9grp': 'grouping',
            '\xa9lyr': 'lyrics',
            'cpil': 'compilation'
        }
        
        for tag_name, std_key in tag_map.items():
            if tag_name in tags:
                value = tags[tag_name]
                if isinstance(value, list) and value:
                    if tag_name in ['trkn', 'disk'] and isinstance(value[0], tuple):
                        metadata[std_key] = str(value[0][0])
                    else:
                        metadata[std_key] = str(value[0])
                elif value:
                    metadata[std_key] = str(value)
                    
        return metadata
    
    def _extract_generic_metadata(self, audio_file) -> Dict[str, Any]:
        """Extract metadata from generic formats.
        
        Args:
            audio_file: Mutagen audio file object.
            
        Returns:
            Dict[str, Any]: Dictionary containing extracted metadata.
        """
        metadata = {}
        
        if not hasattr(audio_file, 'tags') or audio_file.tags is None:
            return metadata
            
        # Try to extract common fields
        tags = audio_file.tags
        
        # Common field names to try
        common_fields = ['title', 'artist', 'album', 'albumartist', 'date', 'year', 
                        'genre', 'track', 'disc', 'comment', 'composer']
                        
        for field in common_fields:
            for case_variant in [field.upper(), field.lower(), field.title()]:
                if case_variant in tags:
                    value = tags[case_variant]
                    if isinstance(value, list) and value:
                        metadata[field] = str(value[0])
                    elif value:
                        metadata[field] = str(value)
                    break
                    
        return metadata
    
    def _has_album_art_mutagen(self, audio_file) -> bool:
        """
        Check if the audio file has album art using mutagen directly.
        
        Args:
            audio_file: Mutagen audio file object
            
        Returns:
            bool: True if file contains embedded album art, False otherwise
        """
        if audio_file is None or not hasattr(audio_file, 'tags') or audio_file.tags is None:
            return False
            
        try:
            # Check for album art based on file type
            if isinstance(audio_file, MP3):
                # Check for APIC frames in ID3 tags
                return any(key.startswith('APIC:') for key in audio_file.tags.keys())
            elif isinstance(audio_file, FLAC):
                # Check for pictures in FLAC
                return len(audio_file.pictures) > 0
            elif isinstance(audio_file, (OggVorbis, OggOpus)):
                # Check for METADATA_BLOCK_PICTURE in Vorbis comments
                return 'METADATA_BLOCK_PICTURE' in audio_file.tags
            elif isinstance(audio_file, MP4):
                # Check for cover art in MP4
                return 'covr' in audio_file.tags
            else:
                # Generic check for picture-related tags
                tags = audio_file.tags
                picture_indicators = ['APIC', 'covr', 'METADATA_BLOCK_PICTURE', 'PICTURE']
                return any(any(indicator in str(key) for indicator in picture_indicators) 
                          for key in tags.keys())
                          
        except Exception:
            return False
    
    def set_metadata(self, filepath: str, metadata: Dict[str, Any]) -> bool:
        """
        Set metadata for an audio file using mutagen library directly.
        
        Args:
            filepath (str): Path to the audio file to modify
            metadata (Dict[str, Any]): Dictionary containing metadata to set
            
        Returns:
            bool: True if metadata was successfully set, False otherwise
        """
        if not MUTAGEN_AVAILABLE:
            logger.error("Mutagen library not available")
            return False
            
        if not os.path.exists(filepath):
            logger.error(f"File not found: {filepath}")
            return False
        
        if not self.is_supported_format(filepath):
            logger.error(f"Unsupported format: {os.path.basename(filepath)}")
            return False
        
        try:
            # Load the audio file using mutagen
            audio_file = MutagenFile(filepath)
            if audio_file is None:
                logger.error(f"Could not load audio file: {os.path.basename(filepath)}")
                return False
                
            # Set metadata based on file type
            success = self._set_metadata_mutagen(audio_file, metadata, filepath)
            
            if success:
                logger.info(f"Successfully updated metadata for {os.path.basename(filepath)}")
                self.processed_count += 1
                return True
            else:
                self.error_count += 1
                return False
                
        except Exception as e:
            logger.error(f"Error setting metadata for {os.path.basename(filepath)}: {str(e)}")
            self.error_count += 1
            return False
    
    def _set_metadata_mutagen(self, audio_file, metadata: Dict[str, Any], filepath: str) -> bool:
        """
        Set metadata using mutagen library directly.
        
        Args:
            audio_file: Mutagen audio file object
            metadata (Dict[str, Any]): Dictionary containing metadata to set
            filepath (str): Path to the audio file for saving
            
        Returns:
            bool: True if metadata was successfully set, False otherwise
        """
        try:
            # Handle different file formats
            if isinstance(audio_file, MP3):
                return self._set_id3_metadata(audio_file, metadata, filepath)
            elif isinstance(audio_file, FLAC):
                return self._set_vorbis_metadata(audio_file, metadata, filepath)
            elif isinstance(audio_file, (OggVorbis, OggOpus)):
                return self._set_vorbis_metadata(audio_file, metadata, filepath)
            elif isinstance(audio_file, MP4):
                return self._set_mp4_metadata(audio_file, metadata, filepath)
            else:
                return self._set_generic_metadata_mutagen(audio_file, metadata, filepath)
                
        except Exception as e:
            logger.error(f"Error setting metadata with mutagen: {str(e)}")
            return False
    
    def _set_id3_metadata(self, audio_file, metadata: Dict[str, Any], filepath: str) -> bool:
        """Set metadata for MP3 files using ID3 tags.
        
        Args:
            audio_file: Mutagen MP3 audio file object.
            metadata: Dictionary containing metadata to set.
            filepath: Path to the audio file.
            
        Returns:
            bool: True if metadata was successfully set, False otherwise.
        """
        try:
            # Ensure ID3 tags exist
            if audio_file.tags is None:
                audio_file.add_tags()
                
            tags = audio_file.tags
            
            # ID3 tag mappings
            if 'title' in metadata and metadata['title']:
                tags['TIT2'] = TIT2(encoding=3, text=metadata['title'])
            if 'artist' in metadata and metadata['artist']:
                tags['TPE1'] = TPE1(encoding=3, text=metadata['artist'])
            if 'album' in metadata and metadata['album']:
                tags['TALB'] = TALB(encoding=3, text=metadata['album'])
            if 'albumartist' in metadata and metadata['albumartist']:
                tags['TPE2'] = TPE2(encoding=3, text=metadata['albumartist'])
            if 'date' in metadata and metadata['date']:
                tags['TDRC'] = TDRC(encoding=3, text=metadata['date'])
            elif 'year' in metadata and metadata['year']:
                tags['TDRC'] = TDRC(encoding=3, text=metadata['year'])
            if 'genre' in metadata and metadata['genre']:
                tags['TCON'] = TCON(encoding=3, text=metadata['genre'])
            if 'track' in metadata and metadata['track']:
                tags['TRCK'] = TRCK(encoding=3, text=str(metadata['track']))
            if 'disc' in metadata and metadata['disc']:
                tags['TPOS'] = TPOS(encoding=3, text=str(metadata['disc']))
            if 'comment' in metadata and metadata['comment']:
                tags['COMM::eng'] = COMM(encoding=3, lang='eng', desc='', text=metadata['comment'])
                
            audio_file.save()
            return True
            
        except Exception as e:
            logger.error(f"Error setting ID3 metadata: {str(e)}")
            return False
    
    def _set_vorbis_metadata(self, audio_file, metadata: Dict[str, Any], filepath: str) -> bool:
        """Set metadata for Vorbis comment based files (FLAC, OGG, OPUS).
        
        Args:
            audio_file: Mutagen audio file object with Vorbis comments.
            metadata: Dictionary containing metadata to set.
            filepath: Path to the audio file.
            
        Returns:
            bool: True if metadata was successfully set, False otherwise.
        """
        try:
            # Ensure tags exist
            if audio_file.tags is None:
                audio_file.add_tags()
                
            tags = audio_file.tags
            
            # Vorbis comment mappings
            if 'title' in metadata and metadata['title']:
                tags['TITLE'] = [metadata['title']]
            if 'artist' in metadata and metadata['artist']:
                tags['ARTIST'] = [metadata['artist']]
            if 'album' in metadata and metadata['album']:
                tags['ALBUM'] = [metadata['album']]
            if 'albumartist' in metadata and metadata['albumartist']:
                tags['ALBUMARTIST'] = [metadata['albumartist']]
            if 'date' in metadata and metadata['date']:
                tags['DATE'] = [metadata['date']]
            elif 'year' in metadata and metadata['year']:
                tags['DATE'] = [metadata['year']]
            if 'genre' in metadata and metadata['genre']:
                tags['GENRE'] = [metadata['genre']]
            if 'track' in metadata and metadata['track']:
                tags['TRACKNUMBER'] = [str(metadata['track'])]
            if 'disc' in metadata and metadata['disc']:
                tags['DISCNUMBER'] = [str(metadata['disc'])]
            if 'comment' in metadata and metadata['comment']:
                tags['COMMENT'] = [metadata['comment']]
                
            audio_file.save()
            return True
            
        except Exception as e:
            logger.error(f"Error setting Vorbis metadata: {str(e)}")
            return False
    
    def _set_mp4_metadata(self, audio_file, metadata: Dict[str, Any], filepath: str) -> bool:
        """Set metadata for MP4/M4A files.
        
        Args:
            audio_file: Mutagen MP4 audio file object.
            metadata: Dictionary containing metadata to set.
            filepath: Path to the audio file.
            
        Returns:
            bool: True if metadata was successfully set, False otherwise.
        """
        try:
            # Ensure tags exist
            if audio_file.tags is None:
                audio_file.add_tags()
                
            tags = audio_file.tags
            
            # MP4 tag mappings
            if 'title' in metadata and metadata['title']:
                tags['\xa9nam'] = [metadata['title']]
            if 'artist' in metadata and metadata['artist']:
                tags['\xa9ART'] = [metadata['artist']]
            if 'album' in metadata and metadata['album']:
                tags['\xa9alb'] = [metadata['album']]
            if 'albumartist' in metadata and metadata['albumartist']:
                tags['aART'] = [metadata['albumartist']]
            if 'date' in metadata and metadata['date']:
                tags['\xa9day'] = [metadata['date']]
            elif 'year' in metadata and metadata['year']:
                tags['\xa9day'] = [metadata['year']]
            if 'genre' in metadata and metadata['genre']:
                tags['\xa9gen'] = [metadata['genre']]
            if 'track' in metadata and metadata['track']:
                try:
                    track_num = int(metadata['track'])
                    tags['trkn'] = [(track_num, 0)]
                except ValueError:
                    pass
            if 'disc' in metadata and metadata['disc']:
                try:
                    disc_num = int(metadata['disc'])
                    tags['disk'] = [(disc_num, 0)]
                except ValueError:
                    pass
            if 'comment' in metadata and metadata['comment']:
                tags['\xa9cmt'] = [metadata['comment']]
                
            audio_file.save()
            return True
            
        except Exception as e:
            logger.error(f"Error setting MP4 metadata: {str(e)}")
            return False
    
    def _set_generic_metadata_mutagen(self, audio_file, metadata: Dict[str, Any], filepath: str) -> bool:
        """Set metadata for generic formats.
        
        Args:
            audio_file: Mutagen audio file object.
            metadata: Dictionary containing metadata to set.
            filepath: Path to the audio file.
            
        Returns:
            bool: True if metadata was successfully set, False otherwise.
        """
        try:
            # Ensure tags exist
            if audio_file.tags is None:
                audio_file.add_tags()
                
            tags = audio_file.tags
            
            # Try to set common fields
            for key, value in metadata.items():
                if value:
                    # Try uppercase version (common for many formats)
                    tags[key.upper()] = [str(value)]
                    
            audio_file.save()
            return True
            
        except Exception as e:
            logger.error(f"Error setting generic metadata: {str(e)}")
            return False
    
    def set_album_art(self, filepath: str, image_path: str) -> bool:
        """
        Set album art for an audio file using mutagen library directly.
        
        Args:
            filepath (str): Path to the audio file to modify
            image_path (str): Path to the image file to embed as album art
            
        Returns:
            bool: True if album art was successfully set, False otherwise
        """
        if not MUTAGEN_AVAILABLE:
            logger.error("Mutagen library not available")
            return False
            
        if not os.path.exists(image_path):
            logger.error(f"Image file not found: {image_path}")
            return False
        
        if not os.path.exists(filepath):
            logger.error(f"Audio file not found: {filepath}")
            return False
        
        try:
            # Load the audio file using mutagen
            audio_file = MutagenFile(filepath)
            if audio_file is None:
                logger.error(f"Could not load audio file: {os.path.basename(filepath)}")
                return False
                
            # Set album art based on file type
            success = self._set_album_art_mutagen(audio_file, image_path, filepath)
            
            if success:
                logger.info(f"Successfully set album art for {os.path.basename(filepath)} using mutagen")
                return True
            else:
                # Fallback to FFmpeg if mutagen fails
                logger.info(f"Mutagen album art failed, falling back to FFmpeg for {os.path.basename(filepath)}")
                return self._set_album_art_ffmpeg(filepath, image_path)
                
        except Exception as e:
            logger.error(f"Error setting album art for {os.path.basename(filepath)}: {str(e)}")
            # Fallback to FFmpeg
            return self._set_album_art_ffmpeg(filepath, image_path)
    
    def _set_album_art_mutagen(self, audio_file, image_path: str, filepath: str) -> bool:
        """
        Set album art using mutagen library directly.
        
        Args:
            audio_file: Mutagen audio file object
            image_path (str): Path to the image file to embed as album art
            filepath (str): Path to the audio file for saving
            
        Returns:
            bool: True if album art was successfully set, False otherwise
        """
        try:
            # Read the image file
            with open(image_path, 'rb') as img_file:
                image_data = img_file.read()
            
            # Detect image format
            image_format = self._detect_image_format(image_data, image_path)
            if not image_format:
                logger.error(f"Unsupported image format: {os.path.basename(image_path)}")
                return False
                
            # Set album art based on audio file type
            if isinstance(audio_file, MP3):
                return self._set_mp3_album_art(audio_file, image_data, image_format, filepath)
            elif isinstance(audio_file, FLAC):
                return self._set_flac_album_art(audio_file, image_data, image_format, filepath)
            elif isinstance(audio_file, (OggVorbis, OggOpus)):
                return self._set_ogg_album_art(audio_file, image_data, image_format, filepath)
            elif isinstance(audio_file, MP4):
                return self._set_mp4_album_art(audio_file, image_data, image_format, filepath)
            else:
                logger.warning(f"Album art embedding not supported for this format via mutagen: {type(audio_file)}")
                return False
                
        except Exception as e:
            logger.error(f"Error setting album art with mutagen: {str(e)}")
            return False
    
    def _detect_image_format(self, image_data: bytes, image_path: str) -> Optional[str]:
        """Detect image format from data or filename.
        
        Args:
            image_data: Binary data of the image.
            image_path: Path to the image file.
            
        Returns:
            Optional[str]: MIME type of the image format, or None if unsupported.
        """
        # Try to detect from data first
        if image_data.startswith(b'\xff\xd8\xff'):
            return 'image/jpeg'
        elif image_data.startswith(b'\x89PNG\r\n\x1a\n'):
            return 'image/png'
        elif image_data.startswith(b'GIF87a') or image_data.startswith(b'GIF89a'):
            return 'image/gif'
        elif image_data.startswith(b'WEBP', 8):
            return 'image/webp'
        
        # Fallback to file extension
        ext = Path(image_path).suffix.lower()
        format_map = {
            '.jpg': 'image/jpeg',
            '.jpeg': 'image/jpeg',
            '.png': 'image/png',
            '.gif': 'image/gif',
            '.webp': 'image/webp'
        }
        return format_map.get(ext)
    
    def _set_mp3_album_art(self, audio_file, image_data: bytes, image_format: str, filepath: str) -> bool:
        """Set album art for MP3 files using ID3 APIC frame.
        
        Args:
            audio_file: Mutagen MP3 audio file object.
            image_data: Binary data of the image.
            image_format: MIME type of the image.
            filepath: Path to the audio file.
            
        Returns:
            bool: True if album art was successfully set, False otherwise.
        """
        try:
            # Ensure ID3 tags exist
            if audio_file.tags is None:
                audio_file.add_tags()
                
            # Remove existing album art
            audio_file.tags.delall('APIC')
            
            # Add new album art
            audio_file.tags.add(
                APIC(
                    encoding=3,  # UTF-8
                    mime=image_format,
                    type=3,  # Cover (front)
                    desc='Cover',
                    data=image_data
                )
            )
            
            audio_file.save()
            return True
            
        except Exception as e:
            logger.error(f"Error setting MP3 album art: {str(e)}")
            return False
    
    def _set_flac_album_art(self, audio_file, image_data: bytes, image_format: str, filepath: str) -> bool:
        """Set album art for FLAC files using Picture blocks.
        
        Args:
            audio_file: Mutagen FLAC audio file object.
            image_data: Binary data of the image.
            image_format: MIME type of the image.
            filepath: Path to the audio file.
            
        Returns:
            bool: True if album art was successfully set, False otherwise.
        """
        try:
            # Clear existing pictures
            audio_file.clear_pictures()
            
            # Create new picture
            picture = Picture()
            picture.type = 3  # Cover (front)
            picture.mime = image_format
            picture.desc = 'Cover'
            picture.data = image_data
            
            # Add picture dimensions if possible
            if PILLOW_AVAILABLE:
                try:
                    from PIL import Image
                    img = Image.open(io.BytesIO(image_data))
                    picture.width, picture.height = img.size
                    picture.depth = img.mode.count('A') and 32 or 24  # 32 for RGBA, 24 for RGB
                except Exception:
                    pass
            
            audio_file.add_picture(picture)
            audio_file.save()
            return True
            
        except Exception as e:
            logger.error(f"Error setting FLAC album art: {str(e)}")
            return False
    
    def _set_ogg_album_art(self, audio_file, image_data: bytes, image_format: str, filepath: str) -> bool:
        """Set album art for OGG files using METADATA_BLOCK_PICTURE.
        
        Args:
            audio_file: Mutagen OGG audio file object.
            image_data: Binary data of the image.
            image_format: MIME type of the image.
            filepath: Path to the audio file.
            
        Returns:
            bool: True if album art was successfully set, False otherwise.
        """
        try:
            # Ensure tags exist
            if audio_file.tags is None:
                audio_file.add_tags()
                
            # Create FLAC picture block for embedding in Vorbis comment
            picture = Picture()
            picture.type = 3  # Cover (front)
            picture.mime = image_format
            picture.desc = 'Cover'
            picture.data = image_data
            
            # Add picture dimensions if possible
            if PILLOW_AVAILABLE:
                try:
                    from PIL import Image
                    img = Image.open(io.BytesIO(image_data))
                    picture.width, picture.height = img.size
                    picture.depth = img.mode.count('A') and 32 or 24
                except Exception:
                    pass
            
            # Encode picture as base64 for METADATA_BLOCK_PICTURE
            picture_data = picture.write()
            encoded_data = base64.b64encode(picture_data).decode('ascii')
            
            # Remove existing album art
            if 'METADATA_BLOCK_PICTURE' in audio_file.tags:
                del audio_file.tags['METADATA_BLOCK_PICTURE']
                
            # Add new album art
            audio_file.tags['METADATA_BLOCK_PICTURE'] = [encoded_data]
            
            audio_file.save()
            return True
            
        except Exception as e:
            logger.error(f"Error setting OGG album art: {str(e)}")
            return False
    
    def _set_mp4_album_art(self, audio_file, image_data: bytes, image_format: str, filepath: str) -> bool:
        """Set album art for MP4/M4A files.
        
        Args:
            audio_file: Mutagen MP4 audio file object.
            image_data: Binary data of the image.
            image_format: MIME type of the image.
            filepath: Path to the audio file.
            
        Returns:
            bool: True if album art was successfully set, False otherwise.
        """
        try:
            # Ensure tags exist
            if audio_file.tags is None:
                audio_file.add_tags()
                
            # Determine format code for MP4
            if image_format == 'image/jpeg':
                format_code = MP4.MP4Cover.FORMAT_JPEG
            elif image_format == 'image/png':
                format_code = MP4.MP4Cover.FORMAT_PNG
            else:
                # Default to JPEG for other formats
                format_code = MP4.MP4Cover.FORMAT_JPEG
            
            # Create cover object
            cover = MP4.MP4Cover(image_data, format_code)
            
            # Set album art
            audio_file.tags['covr'] = [cover]
            
            audio_file.save()
            return True
            
        except Exception as e:
            logger.error(f"Error setting MP4 album art: {str(e)}")
            return False
    
    def _set_album_art_ffmpeg(self, filepath: str, image_path: str) -> bool:
        """
        Set album art using FFmpeg.
        
        Args:
            filepath (str): Path to the audio file to modify
            image_path (str): Path to the image file to embed as album art
            
        Returns:
            bool: True if album art was successfully set, False otherwise
        """
        try:
            # Get file extension to determine format
            file_ext = os.path.splitext(filepath)[1].lower()
            # Create temporary output file with proper extension
            temp_file = filepath + '.tmp' + file_ext
            
            cmd = [
                'ffmpeg', '-y',
                '-i', str(filepath),
                '-i', str(image_path),
                '-map', '0',
                '-map', '1',
                '-c', 'copy',
                '-disposition:v:0', 'attached_pic'
            ]
            
            # Add metadata for the attached picture
            if file_ext == '.mp3':
                cmd.extend(['-id3v2_version', '3'])
            
            cmd.extend([
                '-metadata:s:v', 'title=Cover (front)',
                '-metadata:s:v', 'comment=Cover (front)'
            ])
            
            # Add format specification for files that need it
            if file_ext in ['.flac', '.ogg', '.opus']:
                if file_ext == '.flac':
                    cmd.extend(['-f', 'flac'])
                elif file_ext == '.ogg':
                    cmd.extend(['-f', 'ogg'])
                elif file_ext == '.opus':
                    cmd.extend(['-f', 'opus'])
            
            cmd.append(temp_file)
            
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
        """
        Remove album art from an audio file using mutagen library directly.
        
        Args:
            filepath (str): Path to the audio file to modify
            
        Returns:
            bool: True if album art was successfully removed, False otherwise
        """
        if not MUTAGEN_AVAILABLE:
            logger.error("Mutagen library not available")
            return False
            
        if not os.path.exists(filepath):
            logger.error(f"File not found: {filepath}")
            return False
        
        try:
            # Load the audio file using mutagen
            audio_file = MutagenFile(filepath)
            if audio_file is None:
                logger.error(f"Could not load audio file: {os.path.basename(filepath)}")
                return False
                
            # Remove album art based on file type
            success = self._remove_album_art_mutagen(audio_file, filepath)
            
            if success:
                logger.info(f"Successfully removed album art from {os.path.basename(filepath)} using mutagen")
                return True
            else:
                # Fallback to FFmpeg if mutagen fails
                logger.info(f"Mutagen album art removal failed, falling back to FFmpeg for {os.path.basename(filepath)}")
                return self._remove_album_art_ffmpeg(filepath)
                
        except Exception as e:
            logger.error(f"Error removing album art from {os.path.basename(filepath)}: {str(e)}")
            # Fallback to FFmpeg
            return self._remove_album_art_ffmpeg(filepath)
    
    def _remove_album_art_mutagen(self, audio_file, filepath: str) -> bool:
        """
        Remove album art using mutagen library directly.
        
        Args:
            audio_file: Mutagen audio file object
            filepath (str): Path to the audio file for saving
            
        Returns:
            bool: True if album art was successfully removed, False otherwise
        """
        try:
            # Remove album art based on audio file type
            if isinstance(audio_file, MP3):
                if audio_file.tags is not None:
                    audio_file.tags.delall('APIC')
                    audio_file.save()
                    return True
            elif isinstance(audio_file, FLAC):
                audio_file.clear_pictures()
                audio_file.save()
                return True
            elif isinstance(audio_file, (OggVorbis, OggOpus)):
                if audio_file.tags is not None and 'METADATA_BLOCK_PICTURE' in audio_file.tags:
                    del audio_file.tags['METADATA_BLOCK_PICTURE']
                    audio_file.save()
                    return True
            elif isinstance(audio_file, MP4):
                if audio_file.tags is not None and 'covr' in audio_file.tags:
                    del audio_file.tags['covr']
                    audio_file.save()
                    return True
            else:
                logger.warning(f"Album art removal not supported for this format via mutagen: {type(audio_file)}")
                return False
                
            return True
            
        except Exception as e:
            logger.error(f"Error removing album art with mutagen: {str(e)}")
            return False
    
    def _remove_album_art_ffmpeg(self, filepath: str) -> bool:
        """
        Remove album art using FFmpeg by copying audio streams without video.
        
        Args:
            filepath (str): Path to the audio file to modify
            
        Returns:
            bool: True if album art was successfully removed, False otherwise
        """
        try:
            # Get file extension to determine format
            file_ext = os.path.splitext(filepath)[1].lower()
            # Create temporary output file with proper extension
            temp_file = filepath + '.tmp' + file_ext
            
            cmd = [
                'ffmpeg', '-y',
                '-i', str(filepath),
                '-map', '0:a',
                '-c', 'copy'
            ]
            
            # Add format specification for files that need it
            if file_ext in ['.flac', '.ogg', '.opus']:
                if file_ext == '.flac':
                    cmd.extend(['-f', 'flac'])
                elif file_ext == '.ogg':
                    cmd.extend(['-f', 'ogg'])
                elif file_ext == '.opus':
                    cmd.extend(['-f', 'opus'])
            
            cmd.append(temp_file)
            
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
                logger.info(f"Successfully removed album art from {os.path.basename(filepath)} using FFmpeg")
                return True
            else:
                logger.error(f"FFmpeg album art removal error: {result.stderr}")
                # Clean up temp file if it exists
                if os.path.exists(temp_file):
                    os.unlink(temp_file)
                return False
                
        except Exception as e:
            logger.error(f"Error removing album art with FFmpeg: {str(e)}")
            return False
    
    def batch_edit_metadata(self, file_paths: List[str], metadata: Dict[str, Any]) -> Dict[str, int]:
        """
        Edit metadata for multiple files.
        
        Args:
            file_paths (List[str]): List of file paths to modify
            metadata (Dict[str, Any]): Dictionary containing metadata to set
            
        Returns:
            Dict[str, int]: Statistics about the operation with keys:
                - processed: Number of successfully processed files
                - errors: Number of files that failed processing
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
        """
        Display metadata for a file in a readable format.
        
        Args:
            filepath (str): Path to the audio file to display metadata for
        """
        metadata = self.get_metadata(filepath)
        
        if not metadata:
            logger.error(f"Could not read metadata from {os.path.basename(filepath)}")
            return
        
        # Get audio properties including duration
        audio_info = self._get_audio_info(filepath)
        
        print(f"\nMetadata for: {os.path.basename(filepath)}")
        print("=" * 50)
        print(f"Format: {metadata.get('format', 'Unknown')}")
        print(f"Title: {metadata.get('title', '')}")
        print(f"Artist: {metadata.get('artist', '')}")
        print(f"Album: {metadata.get('album', '')}")
        print(f"Album Artist: {metadata.get('albumartist', '')}")
        print(f"Date/Year: {metadata.get('date', metadata.get('year', ''))}")
        print(f"Genre: {metadata.get('genre', '')}")
        print(f"Track: {metadata.get('track', '')}")
        print(f"Disc: {metadata.get('disc', '')}")
        print(f"Comment: {metadata.get('comment', '')}")
        print(f"Album Art: {'Yes' if metadata.get('has_album_art') else 'No'}")
        
        # Display audio properties
        if audio_info.get('duration', 0) > 0:
            duration = audio_info['duration']
            minutes = int(duration // 60)
            seconds = int(duration % 60)
            print(f"Duration: {minutes:02d}:{seconds:02d} ({duration:.1f} seconds)")
        else:
            print("Duration: Unknown")
        
        if audio_info.get('bitrate', 0) > 0:
            print(f"Bitrate: {audio_info['bitrate']} kbps")
        if audio_info.get('sample_rate', 0) > 0:
            print(f"Sample Rate: {audio_info['sample_rate']} Hz")
        if audio_info.get('bit_depth', 0) > 0:
            print(f"Bit Depth: {audio_info['bit_depth']} bits")

    def extract_metadata_for_database(self, filepath: str) -> Dict[str, Any]:
        """
        Extract metadata in the format expected by database.py.
        
        Args:
            filepath (str): Path to the audio file to extract metadata from
            
        Returns:
            Dict[str, Any]: Dictionary with all metadata fields that database.py expects,
                          or None if metadata extraction fails
        """
        metadata = self.get_metadata(filepath)
        if not metadata:
            return None
            
        # Get audio properties using FFprobe
        audio_info = self._get_audio_info(filepath)
        
        # Convert to database format
        db_metadata = {
            'title': metadata.get('title', ''),
            'album': metadata.get('album', ''),
            'artist': metadata.get('artist', ''),
            'albumartist': metadata.get('albumartist', ''),
            'track': self._parse_number(metadata.get('track', '0')),
            'disc': self._parse_number(metadata.get('disc', '0')),
            'year': self._parse_number(metadata.get('date', metadata.get('year', '0'))),
            'originalyear': self._parse_number(metadata.get('originaldate', metadata.get('originalyear', '0'))),
            'genre': metadata.get('genre', ''),
            'composer': metadata.get('composer', ''),
            'performer': metadata.get('performer', ''),
            'grouping': metadata.get('grouping', ''),
            'comment': metadata.get('comment', ''),
            'lyrics': metadata.get('lyrics', ''),
            'length': audio_info.get('duration', 0),
            'bitrate': audio_info.get('bitrate', 0),
            'samplerate': audio_info.get('sample_rate', 0),
            'bitdepth': audio_info.get('bit_depth', 0),
            'compilation': 1 if metadata.get('compilation', '').lower() in ['1', 'true', 'yes'] else 0,
            'art_embedded': 1 if metadata.get('has_album_art', False) else 0
        }
        
        return db_metadata
    
    def extract_metadata_for_playlist(self, filepath: str) -> Dict[str, Any]:
        """
        Extract metadata in the format expected by playlist.py.
        
        Args:
            filepath (str): Path to the audio file to extract metadata from
            
        Returns:
            Dict[str, Any]: Dictionary with metadata fields that playlist.py expects,
                          or None if metadata extraction fails
        """
        metadata = self.get_metadata(filepath)
        if not metadata:
            return None
            
        # Get audio properties
        audio_info = self._get_audio_info(filepath)
        
        # Convert to playlist format
        playlist_metadata = {
            'url': filepath,
            'title': metadata.get('title', ''),
            'artist': metadata.get('artist', ''),
            'album': metadata.get('album', ''),
            'albumartist': metadata.get('albumartist', ''),
            'length': audio_info.get('duration', 0),
            'track': self._parse_number(metadata.get('track', '0')),
            'disc': self._parse_number(metadata.get('disc', '0')),
            'year': self._parse_number(metadata.get('date', metadata.get('year', '0'))),
            'genre': metadata.get('genre', '')
        }
        
        return playlist_metadata
    
    def _get_audio_info(self, filepath: str) -> Dict[str, Any]:
        """
        Get audio information using FFprobe.
        
        Args:
            filepath (str): Path to the audio file to analyze
            
        Returns:
            Dict[str, Any]: Dictionary containing audio properties like duration,
                          bitrate, sample rate, etc., or empty dict if analysis fails
        """
        try:
            info = {}
            
            # Get duration
            duration_cmd = [
                'ffprobe', '-v', 'quiet',
                '-show_entries', 'format=duration',
                '-of', 'csv=p=0',
                str(filepath)
            ]
            duration_result = subprocess.run(duration_cmd, capture_output=True, text=True, check=True, timeout=30)
            if duration_result.stdout.strip():
                try:
                    info['duration'] = float(duration_result.stdout.strip())
                except ValueError:
                    pass
            
            # Get bit rate
            bitrate_cmd = [
                'ffprobe', '-v', 'quiet',
                '-show_entries', 'format=bit_rate',
                '-of', 'csv=p=0',
                str(filepath)
            ]
            bitrate_result = subprocess.run(bitrate_cmd, capture_output=True, text=True, check=True, timeout=30)
            if bitrate_result.stdout.strip():
                try:
                    info['bitrate'] = int(float(bitrate_result.stdout.strip())) // 1000  # Convert to kbps
                except ValueError:
                    pass
            
            # Get sample rate
            samplerate_cmd = [
                'ffprobe', '-v', 'quiet',
                '-show_entries', 'stream=sample_rate',
                '-of', 'csv=p=0',
                str(filepath)
            ]
            samplerate_result = subprocess.run(samplerate_cmd, capture_output=True, text=True, check=True, timeout=30)
            if samplerate_result.stdout.strip():
                try:
                    info['sample_rate'] = int(samplerate_result.stdout.strip())
                except ValueError:
                    pass
            
            return info
            
        except Exception:
            return {}
    
    def _parse_number(self, value: str) -> int:
        """
        Parse a string value to extract a numeric value for track/disc numbers.
        
        Args:
            value (str): The string value to parse (e.g., "3/10" or "3")
            
        Returns:
            int: The parsed numeric value, or 0 if parsing fails
        """
        if not value:
            return 0
        
        # Handle track numbers like "1/10" or "1"
        if '/' in str(value):
            value = str(value).split('/')[0]
        
        try:
            return int(float(str(value)))
        except (ValueError, TypeError):
            return 0
    
    def embed_opus_album_art(self, opus_filepath: str, image_path: str) -> bool:
        """
        Embed album art into OPUS files.
        
        Args:
            opus_filepath (str): Path to the OPUS audio file to modify
            image_path (str): Path to the image file to embed as album art
            
        Returns:
            bool: True if album art was successfully embedded, False otherwise
        """
        if not os.path.exists(image_path):
            logger.error(f"Image file not found: {image_path}")
            return False
            
        if not os.path.exists(opus_filepath):
            logger.error(f"OPUS file not found: {opus_filepath}")
            return False
        
        try:
            return self.set_album_art(opus_filepath, image_path)
            
        except Exception as e:
            logger.error(f"Error embedding OPUS album art: {str(e)}")
            return False


def main():
    """
    Main function for command-line usage.
    
    Returns:
        int: Exit code (0 for success, 1 for failure)
    """
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
    parser.add_argument('--duration', action='store_true', help='Show only duration in seconds')
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
    
    # Check if we're just getting duration
    if args.duration:
        for filepath in args.files:
            if os.path.exists(filepath):
                audio_info = editor._get_audio_info(filepath)
                duration = audio_info.get('duration', 0)
                print(f"{duration}")
            else:
                logger.error(f"File not found: {filepath}")
                print("0")
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


# Convenience functions for easy importing by other modules
def extract_metadata(filepath: str) -> Dict[str, Any]:
    """
    Convenience function for database.py compatibility.
    Extract metadata from an audio file in database format.
    
    Args:
        filepath (str): Path to the audio file to extract metadata from
        
    Returns:
        Dict[str, Any]: Dictionary with metadata fields in database format,
                      or None if extraction fails
    """
    editor = MetadataEditor()
    return editor.extract_metadata_for_database(filepath)


def extract_metadata_for_playlist(filepath: str) -> Dict[str, Any]:
    """
    Convenience function for playlist.py compatibility.
    Extract metadata from an audio file in playlist format.
    
    Args:
        filepath (str): Path to the audio file to extract metadata from
        
    Returns:
        Dict[str, Any]: Dictionary with metadata fields in playlist format,
                      or None if extraction fails
    """
    editor = MetadataEditor()
    return editor.extract_metadata_for_playlist(filepath)


def set_metadata(filepath: str, metadata: Dict[str, Any]) -> bool:
    """
    Convenience function to set metadata for a file.
    
    Args:
        filepath (str): Path to the audio file to modify
        metadata (Dict[str, Any]): Dictionary containing metadata to set
        
    Returns:
        bool: True if metadata was successfully set, False otherwise
    """
    editor = MetadataEditor()
    return editor.set_metadata(filepath, metadata)


def set_album_art(filepath: str, image_path: str) -> bool:
    """
    Convenience function to set album art for a file.
    
    Args:
        filepath (str): Path to the audio file to modify
        image_path (str): Path to the image file to embed as album art
        
    Returns:
        bool: True if album art was successfully set, False otherwise
    """
    editor = MetadataEditor()
    return editor.set_album_art(filepath, image_path)


def embed_opus_album_art(opus_filepath: str, image_path: str) -> bool:
    """
    Convenience function to embed album art in OPUS files.
    
    Args:
        opus_filepath (str): Path to the OPUS audio file to modify
        image_path (str): Path to the image file to embed as album art
        
    Returns:
        bool: True if album art was successfully embedded, False otherwise
    """
    editor = MetadataEditor()
    return editor.embed_opus_album_art(opus_filepath, image_path)


def get_duration(filepath: str) -> float:
    """
    Get the duration of an audio file in seconds.
    
    Args:
        filepath (str): Path to the audio file
        
    Returns:
        float: Duration in seconds, or 0.0 if unable to determine
    """
    try:
        metadata = extract_metadata(filepath)
        if metadata and 'length' in metadata:
            return float(metadata['length'])
    except Exception:
        pass
    return 0.0


# Specific metadata extraction functions
def _get_specific_tag(filepath: str, tag_key: str, alt_keys: list = None) -> str:
    """
    Helper function to extract a specific tag from an audio file without loading all metadata.
    
    Args:
        filepath (str): Path to the audio file
        tag_key (str): Primary tag key to look for
        alt_keys (list): Alternative tag keys to check if primary is not found
        
    Returns:
        str: The tag value or empty string if not found
    """
    if not MUTAGEN_AVAILABLE:
        return ''
    
    try:
        audio_file = MutagenFile(filepath)
        if audio_file is None:
            return ''
        
        # Try primary tag key first
        if hasattr(audio_file, 'tags') and audio_file.tags:
            # Check primary key
            if tag_key in audio_file.tags:
                value = audio_file.tags[tag_key]
                if isinstance(value, list) and value:
                    return str(value[0]).strip()
                elif value:
                    return str(value).strip()
            
            # Check alternative keys if provided
            if alt_keys:
                for alt_key in alt_keys:
                    if alt_key in audio_file.tags:
                        value = audio_file.tags[alt_key]
                        if isinstance(value, list) and value:
                            return str(value[0]).strip()
                        elif value:
                            return str(value).strip()
        
        return ''
    except Exception:
        return ''


def get_title(filepath: str) -> str:
    """
    Get the title tag from an audio file.
    
    Args:
        filepath (str): Path to the audio file.
        
    Returns:
        str: The title tag value or empty string if not found.
    """
    return _get_specific_tag(filepath, 'TIT2', ['TITLE', 'Title'])


def get_artist(filepath: str) -> str:
    """
    Get the artist tag from an audio file.
    
    Args:
        filepath (str): Path to the audio file.
        
    Returns:
        str: The artist tag value or empty string if not found.
    """
    return _get_specific_tag(filepath, 'TPE1', ['ARTIST', 'Artist'])


def get_album(filepath: str) -> str:
    """
    Get the album tag from an audio file.
    
    Args:
        filepath (str): Path to the audio file.
        
    Returns:
        str: The album tag value or empty string if not found.
    """
    return _get_specific_tag(filepath, 'TALB', ['ALBUM', 'Album'])


def get_albumartist(filepath: str) -> str:
    """
    Get the albumartist tag from an audio file.
    
    Args:
        filepath (str): Path to the audio file.
        
    Returns:
        str: The album artist tag value or empty string if not found.
    """
    return _get_specific_tag(filepath, 'TPE2', ['ALBUMARTIST', 'AlbumArtist', 'ALBUM ARTIST', 'Album Artist'])


def get_year(filepath: str) -> str:
    """
    Get the year/date tag from an audio file.
    
    Args:
        filepath (str): Path to the audio file.
        
    Returns:
        str: The year value or empty string if not found.
    """
    # Try year first, then date
    year = _get_specific_tag(filepath, 'TDRC', ['DATE', 'YEAR', 'Year'])
    if year:
        # Extract just the year part if it's a full date
        year_match = re.match(r'(\d{4})', year)
        if year_match:
            return year_match.group(1)
    
    # Try alternative date tags
    date = _get_specific_tag(filepath, 'TYER', ['date'])
    if date:
        year_match = re.match(r'(\d{4})', date)
        if year_match:
            return year_match.group(1)
    
    return ''


def get_genre(filepath: str) -> str:
    """
    Get the genre tag from an audio file.
    
    Args:
        filepath (str): Path to the audio file.
        
    Returns:
        str: The genre tag value or empty string if not found.
    """
    return _get_specific_tag(filepath, 'TCON', ['GENRE', 'Genre'])


def get_track(filepath: str) -> str:
    """
    Get the track number from an audio file.
    
    Args:
        filepath (str): Path to the audio file.
        
    Returns:
        str: The track number or empty string if not found.
    """
    track = _get_specific_tag(filepath, 'TRCK', ['TRACKNUMBER', 'Track'])
    # Extract just the track number (remove "/total" if present)
    if track and '/' in track:
        return track.split('/')[0]
    return track


def get_disc(filepath: str) -> str:
    """
    Get the disc number from an audio file.
    
    Args:
        filepath (str): Path to the audio file.
        
    Returns:
        str: The disc number or empty string if not found.
    """
    disc = _get_specific_tag(filepath, 'TPOS', ['DISCNUMBER', 'Disc'])
    # Extract just the disc number (remove "/total" if present)
    if disc and '/' in disc:
        return disc.split('/')[0]
    return disc


def get_comment(filepath: str) -> str:
    """
    Get the comment from an audio file.
    
    Args:
        filepath (str): Path to the audio file.
        
    Returns:
        str: The comment or empty string if not found.
    """
    return _get_specific_tag(filepath, 'COMM::eng', ['COMMENT', 'Comment'])


def get_composer(filepath: str) -> str:
    """
    Get the composer from an audio file.
    
    Args:
        filepath (str): Path to the audio file.
        
    Returns:
        str: The composer or empty string if not found.
    """
    return _get_specific_tag(filepath, 'TCOM', ['COMPOSER', 'Composer'])


def get_performer(filepath: str) -> str:
    """
    Get the performer from an audio file.
    
    Args:
        filepath (str): Path to the audio file.
        
    Returns:
        str: The performer or empty string if not found.
    """
    return _get_specific_tag(filepath, 'TPE3', ['PERFORMER', 'Performer'])


def get_grouping(filepath: str) -> str:
    """
    Get the grouping from an audio file.
    
    Args:
        filepath (str): Path to the audio file.
        
    Returns:
        str: The grouping or empty string if not found.
    """
    return _get_specific_tag(filepath, 'TIT1', ['GROUPING', 'Grouping'])
