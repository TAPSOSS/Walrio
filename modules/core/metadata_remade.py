#!/usr/bin/env python3
import os
import sys
import argparse
from pathlib import Path
from typing import Dict, Any, Optional

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
    print("Warning: mutagen library not available. Install with: pip install mutagen")

# Supported formats
AUDIO_EXTENSIONS = {'.mp3', '.flac', '.ogg', '.oga', '.opus', '.m4a', '.mp4', '.aac', '.wv', '.ape', '.mpc', '.wav'}

class MetadataEditor:
    """Efficient metadata editor using mutagen library."""
    
    def __init__(self):
        """Initialize MetadataEditor for working with audio file metadata."""
        self.supported_formats = AUDIO_EXTENSIONS
    
    def get_metadata(self, filepath: str) -> Dict[str, Any]:
        """
        Get all metadata from an audio file using mutagen library directly.
        
        Args:
            filepath (str): Path to the audio file to extract metadata from
            
        Returns:
            Dict[str, Any]: Dictionary with standardized tag names and metadata values,
                          or empty dict if extraction fails
        """
        if not MUTAGEN_AVAILABLE or not os.path.exists(filepath):
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
                metadata['length'] = int(getattr(audio.info, 'length', 0))
                metadata['bitrate'] = int(getattr(audio.info, 'bitrate', 0))
                metadata['samplerate'] = int(getattr(audio.info, 'sample_rate', 0))
                metadata['bitdepth'] = int(getattr(audio.info, 'bits_per_sample', 0))
            
            # Check for album art
            metadata['art_embedded'] = 1 if self._has_album_art_mutagen(audio) else 0
            
            return metadata
        except Exception as e:
            print(f"Error reading metadata from {filepath}: {e}")
            return {}
    
    def _extract_id3(self, tags) -> Dict[str, Any]:
        """Extract metadata from ID3 tags (MP3)."""
        return {
            'title': str(tags.get('TIT2', [''])[0]) if 'TIT2' in tags else '',
            'artist': str(tags.get('TPE1', [''])[0]) if 'TPE1' in tags else '',
            'album': str(tags.get('TALB', [''])[0]) if 'TALB' in tags else '',
            'albumartist': str(tags.get('TPE2', [''])[0]) if 'TPE2' in tags else '',
            'year': int(str(tags.get('TDRC', ['0'])[0])[:4]) if 'TDRC' in tags else 0,
            'originalyear': int(str(tags.get('TORY', ['0'])[0])[:4]) if 'TORY' in tags else 0,
            'genre': str(tags.get('TCON', [''])[0]) if 'TCON' in tags else '',
            'track': self._parse_number(str(tags.get('TRCK', ['0'])[0])) if 'TRCK' in tags else 0,
            'disc': self._parse_number(str(tags.get('TPOS', ['0'])[0])) if 'TPOS' in tags else 0,
            'comment': str(tags.get('COMM::eng', [''])[0]) if 'COMM::eng' in tags else '',
            'composer': str(tags.get('TCOM', [''])[0]) if 'TCOM' in tags else '',
            'performer': str(tags.get('TPE3', [''])[0]) if 'TPE3' in tags else '',
            'grouping': str(tags.get('TIT1', [''])[0]) if 'TIT1' in tags else '',
            'lyrics': str(tags.get('USLT::eng', [''])[0]) if 'USLT::eng' in tags else '',
            'compilation': 1 if 'TCMP' in tags and str(tags.get('TCMP', ['0'])[0]) == '1' else 0,
        }
    
    def _extract_vorbis(self, tags) -> Dict[str, Any]:
        """Extract metadata from Vorbis comments (FLAC, OGG, OPUS)."""
        return {
            'title': tags.get('TITLE', [''])[0] if tags.get('TITLE') else '',
            'artist': tags.get('ARTIST', [''])[0] if tags.get('ARTIST') else '',
            'album': tags.get('ALBUM', [''])[0] if tags.get('ALBUM') else '',
            'albumartist': tags.get('ALBUMARTIST', tags.get('ALBUM ARTIST', ['']))[0] if tags.get('ALBUMARTIST') or tags.get('ALBUM ARTIST') else '',
            'year': int(str(tags.get('DATE', tags.get('YEAR', ['0']))[0])[:4]) if tags.get('DATE') or tags.get('YEAR') else 0,
            'originalyear': int(str(tags.get('ORIGINALYEAR', tags.get('ORIGINALDATE', ['0']))[0])[:4]) if tags.get('ORIGINALYEAR') or tags.get('ORIGINALDATE') else 0,
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
        """Extract metadata from MP4/M4A tags."""
        tags = audio.tags if hasattr(audio, 'tags') and audio.tags else {}
        return {
            'title': tags.get('\xa9nam', [''])[0] if '\xa9nam' in tags else '',
            'artist': tags.get('\xa9ART', [''])[0] if '\xa9ART' in tags else '',
            'album': tags.get('\xa9alb', [''])[0] if '\xa9alb' in tags else '',
            'albumartist': tags.get('aART', [''])[0] if 'aART' in tags else '',
            'year': int(str(tags.get('\xa9day', ['0'])[0])[:4]) if '\xa9day' in tags else 0,
            'originalyear': 0,  # MP4 doesn't have standard original year tag
            'genre': tags.get('\xa9gen', [''])[0] if '\xa9gen' in tags else '',
            'track': tags.get('trkn', [(0, 0)])[0][0] if 'trkn' in tags else 0,
            'disc': tags.get('disk', [(0, 0)])[0][0] if 'disk' in tags else 0,
            'comment': tags.get('\xa9cmt', [''])[0] if '\xa9cmt' in tags else '',
            'composer': tags.get('\xa9wrt', [''])[0] if '\xa9wrt' in tags else '',
            'performer': '',  # MP4 doesn't have standard performer tag
            'grouping': tags.get('\xa9grp', [''])[0] if '\xa9grp' in tags else '',
            'lyrics': tags.get('\xa9lyr', [''])[0] if '\xa9lyr' in tags else '',
            'compilation': 1 if 'cpil' in tags and tags.get('cpil', [False])[0] else 0,
        }
    
    def _has_album_art_mutagen(self, audio) -> bool:
        """Check if the audio file has album art using mutagen directly."""
        try:
            if hasattr(audio, 'tags') and audio.tags:
                if isinstance(audio.tags, ID3):
                    return any(k.startswith('APIC:') for k in audio.tags.keys())
                elif isinstance(audio, (FLAC, OggVorbis, OggOpus)):
                    return hasattr(audio, 'pictures') and len(audio.pictures) > 0
                elif isinstance(audio, MP4):
                    return 'covr' in audio.tags
            return False
        except:
            return False
    
    def _parse_number(self, value: str) -> int:
        """Parse track/disc numbers that may be in 'X/Y' format."""
        try:
            return int(str(value).split('/')[0])
        except:
            return 0
    
    def set_metadata(self, filepath: str, metadata: Dict[str, Any]) -> bool:
        """
        Set metadata for an audio file using mutagen library directly.
        
        Args:
            filepath (str): Path to the audio file to modify
            metadata (Dict[str, Any]): Dictionary containing metadata to set
            
        Returns:
            bool: True if metadata was successfully set, False otherwise
        """
        if not MUTAGEN_AVAILABLE or not os.path.exists(filepath):
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
            return True
        except Exception as e:
            print(f"Error setting metadata for {filepath}: {e}")
            return False
    
    def _set_id3(self, tags, metadata: Dict[str, Any]):
        """Set ID3 tags."""
        if 'title' in metadata and metadata['title']:
            tags.add(TIT2(encoding=3, text=metadata['title']))
        if 'artist' in metadata and metadata['artist']:
            tags.add(TPE1(encoding=3, text=metadata['artist']))
        if 'album' in metadata and metadata['album']:
            tags.add(TALB(encoding=3, text=metadata['album']))
        if 'albumartist' in metadata and metadata['albumartist']:
            tags.add(TPE2(encoding=3, text=metadata['albumartist']))
        if 'year' in metadata and metadata['year']:
            tags.add(TDRC(encoding=3, text=str(metadata['year'])))
        if 'genre' in metadata and metadata['genre']:
            tags.add(TCON(encoding=3, text=metadata['genre']))
        if 'track' in metadata and metadata['track']:
            tags.add(TRCK(encoding=3, text=str(metadata['track'])))
        if 'disc' in metadata and metadata['disc']:
            tags.add(TPOS(encoding=3, text=str(metadata['disc'])))
        if 'comment' in metadata and metadata['comment']:
            tags.add(COMM(encoding=3, lang='eng', desc='', text=metadata['comment']))
        if 'composer' in metadata and metadata['composer']:
            tags.add(TCOM(encoding=3, text=metadata['composer']))
    
    def _set_vorbis(self, tags, metadata: Dict[str, Any]):
        """Set Vorbis comments."""
        if 'title' in metadata and metadata['title']:
            tags['TITLE'] = metadata['title']
        if 'artist' in metadata and metadata['artist']:
            tags['ARTIST'] = metadata['artist']
        if 'album' in metadata and metadata['album']:
            tags['ALBUM'] = metadata['album']
        if 'albumartist' in metadata and metadata['albumartist']:
            tags['ALBUMARTIST'] = metadata['albumartist']
        if 'year' in metadata and metadata['year']:
            tags['DATE'] = str(metadata['year'])
        if 'genre' in metadata and metadata['genre']:
            tags['GENRE'] = metadata['genre']
        if 'track' in metadata and metadata['track']:
            tags['TRACKNUMBER'] = str(metadata['track'])
        if 'disc' in metadata and metadata['disc']:
            tags['DISCNUMBER'] = str(metadata['disc'])
        if 'comment' in metadata and metadata['comment']:
            tags['COMMENT'] = metadata['comment']
        if 'composer' in metadata and metadata['composer']:
            tags['COMPOSER'] = metadata['composer']
    
    def _set_mp4(self, tags, metadata: Dict[str, Any]):
        """Set MP4 tags."""
        if 'title' in metadata and metadata['title']:
            tags['\xa9nam'] = metadata['title']
        if 'artist' in metadata and metadata['artist']:
            tags['\xa9ART'] = metadata['artist']
        if 'album' in metadata and metadata['album']:
            tags['\xa9alb'] = metadata['album']
        if 'albumartist' in metadata and metadata['albumartist']:
            tags['aART'] = metadata['albumartist']
        if 'year' in metadata and metadata['year']:
            tags['\xa9day'] = str(metadata['year'])
        if 'genre' in metadata and metadata['genre']:
            tags['\xa9gen'] = metadata['genre']
        if 'track' in metadata and metadata['track']:
            tags['trkn'] = [(metadata['track'], 0)]
        if 'disc' in metadata and metadata['disc']:
            tags['disk'] = [(metadata['disc'], 0)]
        if 'comment' in metadata and metadata['comment']:
            tags['\xa9cmt'] = metadata['comment']
        if 'composer' in metadata and metadata['composer']:
            tags['\xa9wrt'] = metadata['composer']
    
    def set_album_art(self, filepath: str, image_path: str) -> bool:
        """
        Set album art for an audio file.
        
        Args:
            filepath (str): Path to the audio file to modify
            image_path (str): Path to the image file to embed as album art
            
        Returns:
            bool: True if album art was successfully set, False otherwise
        """
        if not MUTAGEN_AVAILABLE or not os.path.exists(filepath) or not os.path.exists(image_path):
            return False
        
        try:
            audio = MutagenFile(filepath)
            if audio is None:
                return False
            
            with open(image_path, 'rb') as img_file:
                img_data = img_file.read()
            
            # Detect image format
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
                audio.tags['covr'] = [MP4Cover(img_data, imageformat=MP4Cover.FORMAT_JPEG if mime == 'image/jpeg' else MP4Cover.FORMAT_PNG)]
            
            audio.save()
            return True
        except Exception as e:
            print(f"Error setting album art for {filepath}: {e}")
            return False
    
    def display_metadata(self, filepath: str):
        """
        Display metadata for a file in a readable format.
        
        Args:
            filepath (str): Path to the audio file to display metadata for
        """
        metadata = self.get_metadata(filepath)
        if not metadata:
            print(f"Could not read metadata from: {filepath}")
            return
        
        print(f"\nMetadata for: {os.path.basename(filepath)}")
        print("-" * 60)
        for key, value in metadata.items():
            if value:
                print(f"{key:20}: {value}")
    
    def extract_metadata_for_database(self, filepath: str) -> Optional[Dict[str, Any]]:
        """
        Extract metadata from an audio file in database format.
        
        Returns metadata with all fields needed for database storage.
        """
        return self.get_metadata(filepath)
    
    def extract_metadata_for_playlist(self, filepath: str) -> Optional[Dict[str, Any]]:
        """
        Extract metadata from an audio file in playlist format.
        
        Returns simplified metadata for playlist display.
        """
        metadata = self.get_metadata(filepath)
        if not metadata:
            return None
        return {
            'url': f"file://{filepath}",
            'title': metadata.get('title', Path(filepath).stem),
            'artist': metadata.get('artist', 'Unknown Artist'),
            'album': metadata.get('album', 'Unknown Album'),
            'length': metadata.get('length', 0)
        }

# Global instance for convenience functions
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
    """Helper function to extract a specific tag from an audio file."""
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
    parser = argparse.ArgumentParser(description='Audio Metadata Editor')
    parser.add_argument('file', help='Audio file to process')
    parser.add_argument('--show', action='store_true', help='Display current metadata')
    parser.add_argument('--set-title', help='Set title tag')
    parser.add_argument('--set-artist', help='Set artist tag')
    parser.add_argument('--set-album', help='Set album tag')
    parser.add_argument('--set-album-art', help='Set album art from image file')
    
    args = parser.parse_args()
    
    if not os.path.exists(args.file):
        print(f"Error: File not found: {args.file}")
        return 1
    
    editor = MetadataEditor()
    
    if args.show:
        editor.display_metadata(args.file)
        return 0
    
    # Build metadata dict from arguments
    metadata = {}
    if args.set_title:
        metadata['title'] = args.set_title
    if args.set_artist:
        metadata['artist'] = args.set_artist
    if args.set_album:
        metadata['album'] = args.set_album
    
    if metadata:
        if editor.set_metadata(args.file, metadata):
            print(f"Successfully updated metadata for: {args.file}")
        else:
            print(f"Failed to update metadata for: {args.file}")
            return 1
    
    if args.set_album_art:
        if editor.set_album_art(args.file, args.set_album_art):
            print(f"Successfully set album art for: {args.file}")
        else:
            print(f"Failed to set album art for: {args.file}")
            return 1
    
    return 0

if __name__ == '__main__':
    sys.exit(main())
