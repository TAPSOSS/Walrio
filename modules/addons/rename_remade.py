#!/usr/bin/env python3
"""
Rename - Rename audio files based on metadata tags
"""

import argparse
from pathlib import Path
import sys

try:
    from mutagen import File as MutagenFile
except ImportError:
    print("Error: mutagen required. Install with: pip install mutagen", file=sys.stderr)
    sys.exit(1)


class FileRenamer:
    """Renames audio files based on metadata"""
    
    def __init__(self, pattern: str = "{track} - {artist} - {title}"):
        """
        Args:
            pattern: Filename pattern using {artist}, {album}, {title}, {track}, etc.
        """
        self.pattern = pattern
    
    def extract_metadata(self, file_path: Path) -> dict:
        """
        Extract metadata from audio file
        
        Args:
            file_path: Audio file path
            
        Returns:
            Dictionary with metadata fields
        """
        try:
            audio = MutagenFile(file_path, easy=True)
            if audio is None:
                return {}
            
            # Extract common fields
            metadata = {
                'artist': 'Unknown',
                'album': 'Unknown',
                'title': file_path.stem,
                'track': '00',
                'year': '',
                'genre': ''
            }
            
            # Try to get artist
            for key in ['artist', 'albumartist', 'TPE1', 'TPE2', '\xa9ART', 'ARTIST']:
                if key in audio:
                    val = audio[key]
                    if isinstance(val, list):
                        val = val[0]
                    metadata['artist'] = str(val)
                    break
            
            # Try to get album
            for key in ['album', 'TALB', '\xa9alb', 'ALBUM']:
                if key in audio:
                    val = audio[key]
                    if isinstance(val, list):
                        val = val[0]
                    metadata['album'] = str(val)
                    break
            
            # Try to get title
            for key in ['title', 'TIT2', '\xa9nam', 'TITLE']:
                if key in audio:
                    val = audio[key]
                    if isinstance(val, list):
                        val = val[0]
                    metadata['title'] = str(val)
                    break
            
            # Try to get track number
            for key in ['tracknumber', 'TRCK', 'trkn', 'TRACKNUMBER']:
                if key in audio:
                    val = audio[key]
                    if isinstance(val, list):
                        val = val[0]
                    # Extract number from "5/12" format
                    track_str = str(val).split('/')[0].zfill(2)
                    metadata['track'] = track_str
                    break
            
            # Try to get year
            for key in ['date', 'year', 'TDRC', '\xa9day', 'DATE', 'YEAR']:
                if key in audio:
                    val = audio[key]
                    if isinstance(val, list):
                        val = val[0]
                    metadata['year'] = str(val)[:4]  # Extract year part
                    break
            
            # Try to get genre
            for key in ['genre', 'TCON', '\xa9gen', 'GENRE']:
                if key in audio:
                    val = audio[key]
                    if isinstance(val, list):
                        val = val[0]
                    metadata['genre'] = str(val)
                    break
            
            return metadata
            
        except Exception as e:
            print(f"Warning: Could not read metadata from {file_path}: {e}", file=sys.stderr)
            return {
                'artist': 'Unknown',
                'album': 'Unknown',
                'title': file_path.stem,
                'track': '00',
                'year': '',
                'genre': ''
            }
    
    def sanitize_filename(self, name: str) -> str:
        """Remove invalid filename characters"""
        invalid_chars = '<>:"/\\|?*'
        for char in invalid_chars:
            name = name.replace(char, '_')
        return name.strip()
    
    def build_filename(self, metadata: dict, original_ext: str) -> str:
        """
        Build filename from pattern and metadata
        
        Args:
            metadata: Metadata dictionary
            original_ext: Original file extension
            
        Returns:
            New filename
        """
        # Format pattern with metadata
        filename = self.pattern.format(**metadata)
        
        # Sanitize
        filename = self.sanitize_filename(filename)
        
        # Add extension
        return filename + original_ext
    
    def rename_file(self, file_path: Path, dry_run: bool = False) -> tuple:
        """
        Rename a single file based on metadata
        
        Args:
            file_path: Source file
            dry_run: Don't actually rename
            
        Returns:
            Tuple of (old_path, new_path, success)
        """
        # Extract metadata
        metadata = self.extract_metadata(file_path)
        
        # Build new filename
        new_filename = self.build_filename(metadata, file_path.suffix)
        new_path = file_path.parent / new_filename
        
        # Check if already correct
        if new_path == file_path:
            return (file_path, new_path, True)
        
        # Check if target exists
        if new_path.exists():
            print(f"Warning: Target exists: {new_path}", file=sys.stderr)
            return (file_path, new_path, False)
        
        if dry_run:
            return (file_path, new_path, True)
        
        # Rename
        try:
            file_path.rename(new_path)
            return (file_path, new_path, True)
            
        except Exception as e:
            print(f"Error renaming {file_path}: {e}", file=sys.stderr)
            return (file_path, new_path, False)
    
    def rename_directory(self, directory: Path, recursive: bool = True,
                        dry_run: bool = False) -> dict:
        """
        Rename all audio files in directory
        
        Args:
            directory: Directory path
            recursive: Process subdirectories
            dry_run: Preview changes without renaming
            
        Returns:
            Dictionary with rename stats
        """
        # Find audio files
        audio_exts = {'.mp3', '.flac', '.ogg', '.opus', '.m4a', '.mp4', '.wav'}
        
        if recursive:
            pattern = '**/*'
        else:
            pattern = '*'
        
        files = []
        for ext in audio_exts:
            files.extend(directory.glob(f'{pattern}{ext}'))
        
        # Rename each file
        stats = {'renamed': 0, 'skipped': 0, 'errors': 0}
        
        for file_path in files:
            old_path, new_path, success = self.rename_file(file_path, dry_run)
            
            if old_path == new_path:
                stats['skipped'] += 1
            elif success:
                action = "Would rename" if dry_run else "Renamed"
                print(f"{action}: {old_path.name} -> {new_path.name}")
                stats['renamed'] += 1
            else:
                stats['errors'] += 1
        
        return stats


def rename_files(input_path: Path, pattern: str = None, recursive: bool = True,
                dry_run: bool = False) -> dict:
    """
    Rename audio files based on metadata
    
    Args:
        input_path: File or directory
        pattern: Filename pattern
        recursive: Process subdirectories
        dry_run: Preview without renaming
        
    Returns:
        Rename statistics
    """
    if pattern is None:
        pattern = "{track} - {artist} - {title}"
    
    renamer = FileRenamer(pattern)
    
    if input_path.is_dir():
        return renamer.rename_directory(input_path, recursive, dry_run)
    else:
        old_path, new_path, success = renamer.rename_file(input_path, dry_run)
        if old_path == new_path:
            print(f"Filename already correct: {old_path.name}")
            return {'renamed': 0, 'skipped': 1, 'errors': 0}
        elif success:
            action = "Would rename" if dry_run else "Renamed"
            print(f"{action}: {old_path.name} -> {new_path.name}")
            return {'renamed': 1, 'skipped': 0, 'errors': 0}
        else:
            return {'renamed': 0, 'skipped': 0, 'errors': 1}


def main():
    parser = argparse.ArgumentParser(
        description='Rename audio files based on metadata',
        epilog='Pattern variables: {artist}, {album}, {title}, {track}, {year}, {genre}'
    )
    parser.add_argument('input', type=Path, help='Input file or directory')
    parser.add_argument('-p', '--pattern',
                       default='{track} - {artist} - {title}',
                       help='Filename pattern (default: {track} - {artist} - {title})')
    parser.add_argument('-r', '--recursive', action='store_true',
                       help='Process subdirectories')
    parser.add_argument('-n', '--dry-run', action='store_true',
                       help='Preview without renaming')
    
    args = parser.parse_args()
    
    try:
        stats = rename_files(
            args.input,
            args.pattern,
            args.recursive,
            args.dry_run
        )
        
        print(f"\n{'Would rename' if args.dry_run else 'Renamed'}: {stats['renamed']} files")
        print(f"Skipped: {stats['skipped']}")
        if stats['errors']:
            print(f"Errors: {stats['errors']}")
            return 1
        
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    
    return 0


if __name__ == '__main__':
    sys.exit(main())
