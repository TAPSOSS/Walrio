#!/usr/bin/env python3
"""
file metadata viewer and editor, largley a mutegen wrapper for less outward dependency
"""

import os
import sys
import argparse
import logging
from pathlib import Path
from typing import Dict, Any, Optional, List

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger('MetadataEditor')

try:
    from mutagen import File as MutagenFile
    from mutagen.id3 import ID3, APIC, TIT2, TPE1, TALB, TPE2, TDRC, TCON, TRCK, TPOS, COMM, TCOM, TPE3, TIT1, USLT, TORY, TCMP
    from mutagen.flac import FLAC, Picture
    from mutagen.oggvorbis import OggVorbis
    from mutagen.oggopus import OggOpus
    from mutagen.mp4 import MP4, MP4Cover
    from mutagen.mp3 import MP3
    MUTAGEN_AVAILABLE = True
except ImportError:
    MUTAGEN_AVAILABLE = False
    logger.warning("mutagen library not available. Install with: pip install mutagen")

try:
    from PIL import Image
    PILLOW_AVAILABLE = True
except ImportError:
    PILLOW_AVAILABLE = False
    logger.debug("PIL/Pillow not available. Some image processing features will be limited.")

# Supported formats - frozenset for faster lookups
AUDIO_EXTENSIONS = frozenset({'.mp3', '.flac', '.ogg', '.oga', '.opus', '.m4a', '.mp4', 
                               '.aac', '.wv', '.ape', '.mpc', '.wav'})


class MetadataEditor:
    """Efficient metadata editor using mutagen library."""
    
    def __init__(self):
        """Initialize MetadataEditor for working with audio file metadata."""
        self.supported_formats = AUDIO_EXTENSIONS
        self.processed_count = 0
        self.error_count = 0
    
    def is_supported_format(self, filepath: str) -> bool:
        """
        Check if the file format is supported.
        
        Args:
            filepath: Path to the file to check.
            
        Returns:
            True if format is supported, False otherwise.
        """
        return Path(filepath).suffix.lower() in self.supported_formats
    
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
            logger.error("mutagen library not available")
            return {}
        
        filepath_obj = Path(filepath)
        if not filepath_obj.exists():
            logger.error(f"File not found: {filepath}")
            return {}
        
        try:
            audio = MutagenFile(filepath)
            if audio is None:
                return {}
            
            metadata = {}
            
            # Handle different file types
            if hasattr(audio, 'tags') and audio.tags:
                if isinstance(audio.tags, ID3):
                    metadata = self._extract_id3(audio.tags)
                elif hasattr(audio.tags, 'get'):  # Vorbis-style comments
                    metadata = self._extract_vorbis(audio.tags)
            elif isinstance(audio, MP4):
                metadata = self._extract_mp4(audio)
            
            # Add audio info
            if hasattr(audio, 'info'):
                info = audio.info
                metadata['length'] = int(getattr(info, 'length', 0))
                metadata['bitrate'] = int(getattr(info, 'bitrate', 0))
                metadata['samplerate'] = int(getattr(info, 'sample_rate', 0))
                metadata['bitdepth'] = int(getattr(info, 'bits_per_sample', 0))
                metadata['channels'] = int(getattr(info, 'channels', 0))
            
            # Check for album art
            metadata['art_embedded'] = 1 if self._has_album_art(audio) else 0
            
            return metadata
        except Exception as e:
            logger.error(f"Error reading metadata from {filepath}: {e}")
            return {}
    
    def _extract_id3(self, tags) -> Dict[str, Any]:
        """Extract metadata from ID3 tags (MP3) - optimized with dict comprehension where possible."""
        # Use .get() with default empty list for safer access
        return {
            'title': str(tags.get('TIT2', [''])[0]) if tags.get('TIT2') else '',
            'artist': str(tags.get('TPE1', [''])[0]) if tags.get('TPE1') else '',
            'album': str(tags.get('TALB', [''])[0]) if tags.get('TALB') else '',
            'albumartist': str(tags.get('TPE2', [''])[0]) if tags.get('TPE2') else '',
            'year': int(str(tags.get('TDRC', ['0'])[0])[:4]) if tags.get('TDRC') else 0,
            'originalyear': int(str(tags.get('TORY', ['0'])[0])[:4]) if tags.get('TORY') else 0,
            'genre': str(tags.get('TCON', [''])[0]) if tags.get('TCON') else '',
            'track': self._parse_number(str(tags.get('TRCK', ['0'])[0])) if tags.get('TRCK') else 0,
            'disc': self._parse_number(str(tags.get('TPOS', ['0'])[0])) if tags.get('TPOS') else 0,
            'comment': str(tags.get('COMM::eng', [''])[0]) if tags.get('COMM::eng') else '',
            'composer': str(tags.get('TCOM', [''])[0]) if tags.get('TCOM') else '',
            'performer': str(tags.get('TPE3', [''])[0]) if tags.get('TPE3') else '',
            'grouping': str(tags.get('TIT1', [''])[0]) if tags.get('TIT1') else '',
            'lyrics': str(tags.get('USLT::eng', [''])[0]) if tags.get('USLT::eng') else '',
            'compilation': 1 if tags.get('TCMP') and str(tags.get('TCMP', ['0'])[0]) == '1' else 0,
        }
    
    def _extract_vorbis(self, tags) -> Dict[str, Any]:
        """Extract metadata from Vorbis comments (FLAC, OGG, OPUS) - optimized."""
        return {
            'title': tags.get('TITLE', [''])[0] if tags.get('TITLE') else '',
            'artist': tags.get('ARTIST', [''])[0] if tags.get('ARTIST') else '',
            'album': tags.get('ALBUM', [''])[0] if tags.get('ALBUM') else '',
            'albumartist': (tags.get('ALBUMARTIST') or tags.get('ALBUM ARTIST', ['']))[0] if (tags.get('ALBUMARTIST') or tags.get('ALBUM ARTIST')) else '',
            'year': int(str((tags.get('DATE') or tags.get('YEAR', ['0']))[0])[:4]) if (tags.get('DATE') or tags.get('YEAR')) else 0,
            'originalyear': int(str((tags.get('ORIGINALYEAR') or tags.get('ORIGINALDATE', ['0']))[0])[:4]) if (tags.get('ORIGINALYEAR') or tags.get('ORIGINALDATE')) else 0,
            'genre': tags.get('GENRE', [''])[0] if tags.get('GENRE') else '',
            'track': self._parse_number(tags.get('TRACKNUMBER', ['0'])[0]) if tags.get('TRACKNUMBER') else 0,
            'disc': self._parse_number(tags.get('DISCNUMBER', ['0'])[0]) if tags.get('DISCNUMBER') else 0,
            'comment': tags.get('COMMENT', [''])[0] if tags.get('COMMENT') else '',
            'composer': tags.get('COMPOSER', [''])[0] if tags.get('COMPOSER') else '',
            'performer': tags.get('PERFORMER', [''])[0] if tags.get('PERFORMER') else '',
            'grouping': tags.get('GROUPING', [''])[0] if tags.get('GROUPING') else '',
            'lyrics': tags.get('LYRICS', [''])[0] if tags.get('LYRICS') else '',
            'compilation': 1 if tags.get('COMPILATION', ['0'])[0] == '1' else 0,
        }
    
    def _extract_mp4(self, audio) -> Dict[str, Any]:
        """Extract metadata from MP4/M4A tags - optimized."""
        tags = audio.tags if hasattr(audio, 'tags') and audio.tags else {}
        return {
            'title': tags.get('\xa9nam', [''])[0] if tags.get('\xa9nam') else '',
            'artist': tags.get('\xa9ART', [''])[0] if tags.get('\xa9ART') else '',
            'album': tags.get('\xa9alb', [''])[0] if tags.get('\xa9alb') else '',
            'albumartist': tags.get('aART', [''])[0] if tags.get('aART') else '',
            'year': int(str(tags.get('\xa9day', ['0'])[0])[:4]) if tags.get('\xa9day') else 0,
            'originalyear': 0,  # MP4 doesn't have standard original year tag
            'genre': tags.get('\xa9gen', [''])[0] if tags.get('\xa9gen') else '',
            'track': tags.get('trkn', [(0, 0)])[0][0] if tags.get('trkn') else 0,
            'disc': tags.get('disk', [(0, 0)])[0][0] if tags.get('disk') else 0,
            'comment': tags.get('\xa9cmt', [''])[0] if tags.get('\xa9cmt') else '',
            'composer': tags.get('\xa9wrt', [''])[0] if tags.get('\xa9wrt') else '',
            'performer': '',  # MP4 doesn't have standard performer tag
            'grouping': tags.get('\xa9grp', [''])[0] if tags.get('\xa9grp') else '',
            'lyrics': tags.get('\xa9lyr', [''])[0] if tags.get('\xa9lyr') else '',
            'compilation': 1 if tags.get('cpil') and tags.get('cpil', [False])[0] else 0,
        }
    
    def _has_album_art(self, audio) -> bool:
        """Check if the audio file has album art - optimized with early returns."""
        if not audio or not hasattr(audio, 'tags') or not audio.tags:
            return False
        
        try:
            if isinstance(audio.tags, ID3):
                # Use any() with generator for efficiency
                return any(k.startswith('APIC:') for k in audio.tags)
            elif isinstance(audio, (FLAC, OggVorbis, OggOpus)):
                return hasattr(audio, 'pictures') and len(audio.pictures) > 0
            elif isinstance(audio, MP4):
                return 'covr' in audio.tags
            return False
        except:
            return False
    
    def _parse_number(self, value: str) -> int:
        """Parse track/disc numbers that may be in 'X/Y' format - optimized."""
        try:
            return int(str(value).split('/')[0])
        except (ValueError, AttributeError, IndexError):
            return 0
    
    def get_tag(self, filepath: str, tag_name: str) -> Optional[str]:
        """
        Get a specific tag from an audio file.
        More efficient than get_all_tags when you only need one tag.
        
        Args:
            filepath: Path to the audio file
            tag_name: Name of the tag to retrieve (case-insensitive)
            
        Returns:
            Tag value as string, or None if not found
        """
        if not MUTAGEN_AVAILABLE:
            logger.error("mutagen library not available")
            return None
        
        if not Path(filepath).exists():
            logger.error(f"File not found: {filepath}")
            return None
        
        try:
            audio = MutagenFile(filepath)
            if audio is None or not hasattr(audio, 'tags') or audio.tags is None:
                return None
            
            # Search for tag (case-insensitive)
            tag_name_lower = tag_name.lower()
            
            for key in audio.tags.keys():
                if key.lower() == tag_name_lower:
                    value = audio.tags[key]
                    # Handle different value types
                    if isinstance(value, (list, tuple)) and value:
                        return str(value[0])
                    else:
                        return str(value)
            
            return None
        except Exception as e:
            logger.debug(f"Error reading tag '{tag_name}' from {filepath}: {e}")
            return None
    
    def get_all_tags(self, filepath: str) -> Dict[str, Any]:
        """
        Get ALL raw tags from an audio file including non-standard tags.
        Useful for debugging and seeing everything in the file.
        
        Args:
            filepath: Path to the audio file
            
        Returns:
            Dictionary containing all raw tags
        """
        if not MUTAGEN_AVAILABLE:
            logger.error("mutagen library not available")
            return {}
        
        if not Path(filepath).exists():
            logger.error(f"File not found: {filepath}")
            return {}
        
        try:
            audio = MutagenFile(filepath)
            if audio is None or not hasattr(audio, 'tags') or audio.tags is None:
                return {}
            
            all_tags = {}
            
            # Convert all tags to string representations
            for key in audio.tags.keys():
                try:
                    value = audio.tags[key]
                    # Handle different value types
                    if isinstance(value, (list, tuple)) and value:
                        all_tags[key] = str(value[0]) if len(value) == 1 else [str(v) for v in value]
                    else:
                        all_tags[key] = str(value)
                except:
                    all_tags[key] = '<unable to decode>'
            
            return all_tags
        except Exception as e:
            logger.error(f"Error reading all tags from {filepath}: {e}")
            return {}
    
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
            logger.error("mutagen library not available")
            return False
        
        filepath_obj = Path(filepath)
        if not filepath_obj.exists():
            logger.error(f"File not found: {filepath}")
            return False
        
        if not self.is_supported_format(filepath):
            logger.error(f"Unsupported file format: {filepath}")
            return False
        
        try:
            audio = MutagenFile(filepath)
            if audio is None:
                return False
            
            # Initialize tags if they don't exist
            if not hasattr(audio, 'tags') or audio.tags is None:
                audio.add_tags()
            
            # Set metadata based on file type
            if isinstance(audio.tags, ID3):
                self._set_id3(audio.tags, metadata)
            elif hasattr(audio.tags, '__setitem__'):  # Vorbis-style
                self._set_vorbis(audio.tags, metadata)
            elif isinstance(audio, MP4):
                self._set_mp4(audio.tags, metadata)
            
            audio.save()
            logger.debug(f"Successfully set metadata for: {filepath}")
            return True
        except Exception as e:
            logger.error(f"Error setting metadata for {filepath}: {e}")
            return False
    
    def _set_id3(self, tags, metadata: Dict[str, Any]):
        """Set ID3 tags - optimized to avoid redundant checks."""
        # Use dict mapping for cleaner code
        tag_mapping = {
            'title': (TIT2, 'title'),
            'artist': (TPE1, 'artist'),
            'album': (TALB, 'album'),
            'albumartist': (TPE2, 'albumartist'),
            'year': (TDRC, 'year'),
            'genre': (TCON, 'genre'),
            'track': (TRCK, 'track'),
            'disc': (TPOS, 'disc'),
            'composer': (TCOM, 'composer'),
        }
        
        for meta_key, (tag_class, _) in tag_mapping.items():
            if meta_key in metadata and metadata[meta_key]:
                tags.add(tag_class(encoding=3, text=str(metadata[meta_key])))
        
        # Special handling for comment
        if 'comment' in metadata and metadata['comment']:
            tags.add(COMM(encoding=3, lang='eng', desc='', text=metadata['comment']))
    
    def _set_vorbis(self, tags, metadata: Dict[str, Any]):
        """Set Vorbis comments - optimized with dict mapping."""
        vorbis_mapping = {
            'title': 'TITLE',
            'artist': 'ARTIST',
            'album': 'ALBUM',
            'albumartist': 'ALBUMARTIST',
            'year': 'DATE',
            'genre': 'GENRE',
            'track': 'TRACKNUMBER',
            'disc': 'DISCNUMBER',
            'comment': 'COMMENT',
            'composer': 'COMPOSER',
        }
        
        for meta_key, vorbis_key in vorbis_mapping.items():
            if meta_key in metadata and metadata[meta_key]:
                tags[vorbis_key] = str(metadata[meta_key])
    
    def _set_mp4(self, tags, metadata: Dict[str, Any]):
        """Set MP4 tags - optimized with dict mapping."""
        mp4_mapping = {
            'title': '\xa9nam',
            'artist': '\xa9ART',
            'album': '\xa9alb',
            'albumartist': 'aART',
            'year': '\xa9day',
            'genre': '\xa9gen',
            'comment': '\xa9cmt',
            'composer': '\xa9wrt',
        }
        
        for meta_key, mp4_key in mp4_mapping.items():
            if meta_key in metadata and metadata[meta_key]:
                tags[mp4_key] = str(metadata[meta_key])
        
        # Special handling for track and disc (tuples)
        if 'track' in metadata and metadata['track']:
            tags['trkn'] = [(int(metadata['track']), 0)]
        if 'disc' in metadata and metadata['disc']:
            tags['disk'] = [(int(metadata['disc']), 0)]
    
    def set_album_art(self, filepath: str, image_path: str) -> bool:
        """
        Set album art for an audio file.
        
        Args:
            filepath (str): Path to the audio file to modify
            image_path (str): Path to the image file to embed as album art
            
        Returns:
            bool: True if album art was successfully set, False otherwise
        """
        if not MUTAGEN_AVAILABLE:
            logger.error("mutagen library not available")
            return False
        
        # Use Path for existence checks
        filepath_obj, image_obj = Path(filepath), Path(image_path)
        if not filepath_obj.exists():
            logger.error(f"Audio file not found: {filepath}")
            return False
        if not image_obj.exists():
            logger.error(f"Image file not found: {image_path}")
            return False
        
        try:
            audio = MutagenFile(filepath)
            if audio is None:
                return False
            
            # Read image data once
            img_data = image_obj.read_bytes()
            
            # Detect image format efficiently
            mime = 'image/jpeg'
            if img_data[:4] == b'\x89PNG':
                mime = 'image/png'
            
            if isinstance(audio, MP3):
                if audio.tags is None:
                    audio.add_tags()
                audio.tags.add(APIC(encoding=3, mime=mime, type=3, desc='Cover', data=img_data))
            elif isinstance(audio, FLAC):
                pic = Picture()
                pic.data = img_data
                pic.type = 3
                pic.mime = mime
                audio.clear_pictures()
                audio.add_picture(pic)
            elif isinstance(audio, (OggVorbis, OggOpus)):
                pic = Picture()
                pic.data = img_data
                pic.type = 3
                pic.mime = mime
                audio.clear_pictures()
                audio.add_picture(pic)
            elif isinstance(audio, MP4):
                if audio.tags is None:
                    audio.add_tags()
                format_type = MP4Cover.FORMAT_JPEG if mime == 'image/jpeg' else MP4Cover.FORMAT_PNG
                audio.tags['covr'] = [MP4Cover(img_data, imageformat=format_type)]
            
            audio.save()
            logger.debug(f"Successfully set album art for: {filepath}")
            return True
        except Exception as e:
            logger.error(f"Error setting album art for {filepath}: {e}")
            return False
    
    def remove_album_art(self, filepath: str) -> bool:
        """
        Remove album art from an audio file.
        
        Args:
            filepath: Path to the audio file
            
        Returns:
            True if album art was successfully removed
        """
        if not MUTAGEN_AVAILABLE:
            logger.error("mutagen library not available")
            return False
        
        if not Path(filepath).exists():
            logger.error(f"File not found: {filepath}")
            return False
        
        try:
            audio = MutagenFile(filepath)
            if audio is None or not hasattr(audio, 'tags') or audio.tags is None:
                return False
            
            if isinstance(audio, MP3):
                # Remove all APIC frames
                audio.tags.delall('APIC')
            elif isinstance(audio, (FLAC, OggVorbis, OggOpus)):
                audio.clear_pictures()
            elif isinstance(audio, MP4):
                if 'covr' in audio.tags:
                    del audio.tags['covr']
            
            audio.save()
            logger.info(f"✓ Removed album art from: {filepath}")
            return True
        except Exception as e:
            logger.error(f"Error removing album art from {filepath}: {e}")
            return False
    
    def remove_tag(self, filepath: str, tag_name: str) -> bool:
        """
        Remove a specific tag from an audio file.
        
        Args:
            filepath: Path to the audio file
            tag_name: Name of the tag to remove (case-insensitive)
            
        Returns:
            True if tag was successfully removed
        """
        if not MUTAGEN_AVAILABLE:
            logger.error("mutagen library not available")
            return False
        
        if not Path(filepath).exists():
            logger.error(f"File not found: {filepath}")
            return False
        
        try:
            audio = MutagenFile(filepath)
            if audio is None or not hasattr(audio, 'tags') or audio.tags is None:
                return False
            
            # Normalize tag name to uppercase for case-insensitive matching
            tag_upper = tag_name.upper()
            removed = False
            
            # Find matching tags (case-insensitive)
            tags_to_remove = [k for k in audio.tags.keys() if k.upper() == tag_upper or k.upper().startswith(tag_upper)]
            
            for tag in tags_to_remove:
                try:
                    if isinstance(audio.tags, ID3):
                        audio.tags.delall(tag)
                    else:
                        del audio.tags[tag]
                    logger.info(f"✓ Removed tag '{tag}' from: {Path(filepath).name}")
                    removed = True
                except:
                    pass
            
            if removed:
                audio.save()
                return True
            else:
                logger.warning(f"Tag '{tag_name}' not found in: {Path(filepath).name}")
                return False
        except Exception as e:
            logger.error(f"Error removing tag from {filepath}: {e}")
            return False
    
    def batch_edit_metadata(self, file_paths: List[str], metadata: Dict[str, Any]) -> Dict[str, int]:
        """
        Apply the same metadata changes to multiple files efficiently.
        
        Args:
            file_paths: List of file paths to modify
            metadata: Metadata dictionary to apply to all files
            
        Returns:
            Dictionary with 'success' and 'failed' counts
        """
        results = {'success': 0, 'failed': 0}
        
        logger.info(f"Batch editing metadata for {len(file_paths)} file(s)...")
        
        for idx, filepath in enumerate(file_paths, 1):
            logger.info(f"[{idx}/{len(file_paths)}] Processing: {Path(filepath).name}")
            
            if self.set_metadata(filepath, metadata):
                results['success'] += 1
                self.processed_count += 1
            else:
                results['failed'] += 1
                self.error_count += 1
        
        logger.info(f"\nBatch edit complete: {results['success']} succeeded, {results['failed']} failed")
        return results
    
    def display_metadata(self, filepath: str):
        """
        Display metadata for a file in a readable format.
        
        Args:
            filepath (str): Path to the audio file to display metadata for
        """
        metadata = self.get_metadata(filepath)
        if not metadata:
            logger.error(f"Could not read metadata from: {filepath}")
            return
        
        print(f"\nMetadata for: {Path(filepath).name}")
        print("-" * 70)
        for key, value in sorted(metadata.items()):
            if value:
                print(f"{key:20}: {value}")
        print("-" * 70)
    
    def extract_metadata_for_database(self, filepath: str) -> Optional[Dict[str, Any]]:
        """
        Extract metadata from an audio file in database format.
        
        Args:
            filepath: Path to the audio file.
            
        Returns:
            Dictionary with all metadata fields for database storage, or None if extraction fails.
        """
        return self.get_metadata(filepath)
    
    def extract_metadata_for_playlist(self, filepath: str) -> Optional[Dict[str, Any]]:
        """
        Extract metadata from an audio file in playlist format.
        
        Args:
            filepath: Path to the audio file.
            
        Returns:
            Dictionary with simplified metadata for playlist display, or None if extraction fails.
        """
        metadata = self.get_metadata(filepath)
        if not metadata:
            return None
        return {
            'url': f"file://{filepath}",
            'title': metadata.get('title') or Path(filepath).stem,
            'artist': metadata.get('artist') or 'Unknown Artist',
            'album': metadata.get('album') or 'Unknown Album',
            'length': metadata.get('length', 0)
        }

# Global instance for convenience functions - lazy initialization
_editor = None

def _get_editor():
    """Get or create global MetadataEditor instance."""
    global _editor
    if _editor is None:
        _editor = MetadataEditor()
    return _editor

def extract_metadata(filepath: str) -> Optional[Dict[str, Any]]:
    """
    Convenience function for database.py compatibility.
    Extract metadata from an audio file in database format.
    """
    return _get_editor().extract_metadata_for_database(filepath)

def extract_metadata_for_playlist(filepath: str) -> Optional[Dict[str, Any]]:
    """
    Convenience function for playlist.py compatibility.
    Extract metadata from an audio file in playlist format.
    """
    return _get_editor().extract_metadata_for_playlist(filepath)

def set_metadata(filepath: str, metadata: Dict[str, Any]) -> bool:
    """Convenience function to set metadata for a file."""
    return _get_editor().set_metadata(filepath, metadata)

def set_album_art(filepath: str, image_path: str) -> bool:
    """Convenience function to set album art for a file."""
    return _get_editor().set_album_art(filepath, image_path)

def embed_opus_album_art(opus_filepath: str, image_path: str) -> bool:
    """
    Convenience function to embed album art in OPUS files.
    OPUS files use the same method as OGG Vorbis.
    """
    return set_album_art(opus_filepath, image_path)

def get_duration(filepath: str) -> float:
    """Get the duration of an audio file in seconds."""
    metadata = extract_metadata(filepath)
    return float(metadata.get('length', 0)) if metadata else 0.0

def _get_specific_tag(filepath: str, tag_key: str, alt_keys=None) -> str:
    """Helper function to extract a specific tag from an audio file without loading all metadata."""
    # For efficiency, this could be optimized to only read specific tags
    # For now, reuse get_metadata
    metadata = extract_metadata(filepath)
    if not metadata:
        return ''
    
    value = metadata.get(tag_key, '')
    if not value and alt_keys:
        for alt_key in alt_keys:
            value = metadata.get(alt_key, '')
            if value:
                break
    return str(value)

def get_title(filepath: str) -> str:
    """Get the title tag from an audio file."""
    return _get_specific_tag(filepath, 'title')

def get_artist(filepath: str) -> str:
    """Get the artist tag from an audio file."""
    return _get_specific_tag(filepath, 'artist')

def get_album(filepath: str) -> str:
    """Get the album tag from an audio file."""
    return _get_specific_tag(filepath, 'album')

def get_albumartist(filepath: str) -> str:
    """Get the albumartist tag from an audio file."""
    return _get_specific_tag(filepath, 'albumartist')

def get_year(filepath: str) -> str:
    """Get the year/date tag from an audio file."""
    return str(_get_specific_tag(filepath, 'year'))

def get_genre(filepath: str) -> str:
    """Get the genre tag from an audio file."""
    return _get_specific_tag(filepath, 'genre')

def get_track(filepath: str) -> str:
    """Get the track number from an audio file."""
    return str(_get_specific_tag(filepath, 'track'))

def get_disc(filepath: str) -> str:
    """Get the disc number from an audio file."""
    return str(_get_specific_tag(filepath, 'disc'))

def get_comment(filepath: str) -> str:
    """Get the comment from an audio file."""
    return _get_specific_tag(filepath, 'comment')

def get_composer(filepath: str) -> str:
    """Get the composer from an audio file."""
    return _get_specific_tag(filepath, 'composer')

def get_performer(filepath: str) -> str:
    """Get the performer from an audio file."""
    return _get_specific_tag(filepath, 'performer')

def get_grouping(filepath: str) -> str:
    """Get the grouping from an audio file."""
    return _get_specific_tag(filepath, 'grouping')

def main():
    """
    Main function for command-line usage.
    
    Returns:
        int: Exit code (0 for success, 1 for failure)
    """
    parser = argparse.ArgumentParser(
        description='Modify audio file metadata using mutagen',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Display metadata
  python metadata_remade.py --show song.mp3
  
  # Show all raw tags (including non-standard tags)
  python metadata_remade.py --show-all-tags song.mp3
  
  # Show only duration
  python metadata_remade.py --duration song.mp3
  
  # Set title and artist
  python metadata_remade.py --set-title "New Title" --set-artist "New Artist" song.mp3
  
  # Set album art
  python metadata_remade.py --set-album-art cover.jpg song.mp3
  
  # Remove album art
  python metadata_remade.py --remove-album-art song.mp3
  
  # Remove a specific tag (e.g., playcount)
  python metadata_remade.py --remove-tag FMPS_PLAYCOUNT song.flac
  
  # Remove tag from all files in directory recursively
  python metadata_remade.py --remove-tag fmps_playcount --recursive /path/to/music
  
  # Batch edit multiple files
  python metadata_remade.py --set-album "Album Name" *.mp3
  
  # Batch edit directory recursively
  python metadata_remade.py --set-genre "Jazz" --recursive /music/jazz
        """
    )
    
    parser.add_argument('files', nargs='*', help='Audio files or directories to process')
    parser.add_argument('--show', action='store_true', help='Display current metadata')
    parser.add_argument('--show-all-tags', action='store_true', help='Display all raw tags in the file')
    parser.add_argument('--duration', action='store_true', help='Show only duration in seconds')
    parser.add_argument('--recursive', '-r', action='store_true', help='Process directories recursively')
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
    parser.add_argument('--remove-tag', help='Remove a specific tag by name')
    parser.add_argument('--verbose', '-v', action='store_true', help='Enable verbose logging')
    
    args = parser.parse_args()
    
    if args.verbose:
        logger.setLevel(logging.DEBUG)
    
    if not args.files:
        parser.print_help()
        return 1
    
    editor = MetadataEditor()
    
    # Expand directories if recursive flag is set
    file_list = []
    
    for path_str in args.files:
        path = Path(path_str)
        if path.is_file():
            if path.suffix.lower() in AUDIO_EXTENSIONS:
                file_list.append(str(path))
        elif path.is_dir():
            if args.recursive:
                # Use rglob for recursive, glob for non-recursive
                for ext in AUDIO_EXTENSIONS:
                    file_list.extend(str(f) for f in path.rglob(f'*{ext}'))
            else:
                for ext in AUDIO_EXTENSIONS:
                    file_list.extend(str(f) for f in path.glob(f'*{ext}'))
    
    if not file_list:
        logger.error("No audio files found")
        return 1
    
    # Check if we're just displaying metadata
    if args.show:
        for filepath in file_list:
            editor.display_metadata(filepath)
        return 0
    
    # Check if we're showing all raw tags
    if args.show_all_tags:
        for filepath in file_list:
            all_tags = editor.get_all_tags(filepath)
            if all_tags:
                print(f"\nAll tags in: {Path(filepath).name}")
                print("-" * 70)
                for key, value in sorted(all_tags.items()):
                    print(f"{key:30}: {value}")
                print("-" * 70)
        return 0
    
    # Check if we're just getting duration
    if args.duration:
        for filepath in file_list:
            duration = get_duration(filepath)
            print(f"{Path(filepath).name}: {duration:.2f} seconds")
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
    
    for idx, filepath in enumerate(file_list, 1):
        logger.info(f"[{idx}/{len(file_list)}] Processing: {Path(filepath).name}")
        
        # Apply metadata changes
        if metadata:
            if editor.set_metadata(filepath, metadata):
                success_count += 1
        
        # Set album art
        if args.set_album_art:
            if editor.set_album_art(filepath, args.set_album_art):
                success_count += 1
        
        # Remove album art
        if args.remove_album_art:
            if editor.remove_album_art(filepath):
                success_count += 1
        
        # Remove specific tag
        if args.remove_tag:
            if editor.remove_tag(filepath, args.remove_tag):
                success_count += 1
    
    logger.info(f"\nSuccessfully processed {success_count} operation(s) on {len(file_list)} file(s)")
    return 0 if success_count > 0 else 1


if __name__ == "__main__":
    sys.exit(main())
