#!/usr/bin/env python3
"""
File Relocater - Organize audio files into directory structure based on metadata
"""

import argparse
from pathlib import Path
import shutil
import sys

try:
    from mutagen import File as MutagenFile
except ImportError:
    print("Error: mutagen required. Install with: pip install mutagen", file=sys.stderr)
    sys.exit(1)


class FileRelocater:
    """Organizes audio files by metadata"""
    
    def __init__(self, pattern: str = "{artist}/{album}/{track} - {title}",
                 copy_mode: bool = False):
        """
        Args:
            pattern: Directory/filename pattern using {artist}, {album}, {title}, {track}
            copy_mode: Copy instead of move
        """
        self.pattern = pattern
        self.copy_mode = copy_mode
    
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
                'artist': 'Unknown Artist',
                'album': 'Unknown Album',
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
                'artist': 'Unknown Artist',
                'album': 'Unknown Album',
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
    
    def build_path(self, metadata: dict, original_ext: str) -> Path:
        """
        Build target path from pattern and metadata
        
        Args:
            metadata: Metadata dictionary
            original_ext: Original file extension
            
        Returns:
            Relative path based on pattern
        """
        # Format pattern with metadata
        path_str = self.pattern.format(**metadata)
        
        # Sanitize each component
        parts = path_str.split('/')
        parts = [self.sanitize_filename(part) for part in parts]
        
        # Add extension to filename
        parts[-1] = parts[-1] + original_ext
        
        return Path(*parts)
    
    def relocate_file(self, file_path: Path, output_dir: Path,
                     dry_run: bool = False) -> tuple:
        """
        Relocate a single file
        
        Args:
            file_path: Source file
            output_dir: Output root directory
            dry_run: Don't actually move files
            
        Returns:
            Tuple of (source_path, target_path, success)
        """
        # Extract metadata
        metadata = self.extract_metadata(file_path)
        
        # Build target path
        rel_path = self.build_path(metadata, file_path.suffix)
        target_path = output_dir / rel_path
        
        if dry_run:
            return (file_path, target_path, True)
        
        # Create target directory
        target_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Move or copy
        try:
            if self.copy_mode:
                shutil.copy2(file_path, target_path)
            else:
                shutil.move(str(file_path), str(target_path))
            
            return (file_path, target_path, True)
            
        except Exception as e:
            print(f"Error relocating {file_path}: {e}", file=sys.stderr)
            return (file_path, target_path, False)
    
    def relocate_directory(self, input_dir: Path, output_dir: Path,
                          recursive: bool = True, dry_run: bool = False) -> dict:
        """
        Relocate all audio files in directory
        
        Args:
            input_dir: Source directory
            output_dir: Target root directory
            recursive: Process subdirectories
            dry_run: Preview changes without moving
            
        Returns:
            Dictionary with relocation stats
        """
        # Find audio files
        audio_exts = {'.mp3', '.flac', '.ogg', '.opus', '.m4a', '.mp4', '.wav'}
        
        if recursive:
            pattern = '**/*'
        else:
            pattern = '*'
        
        files = []
        for ext in audio_exts:
            files.extend(input_dir.glob(f'{pattern}{ext}'))
        
        # Relocate each file
        stats = {'success': 0, 'errors': 0}
        
        for file_path in files:
            source, target, success = self.relocate_file(file_path, output_dir, dry_run)
            
            if success:
                action = "Would move" if dry_run else ("Copied" if self.copy_mode else "Moved")
                print(f"{action}: {source} -> {target}")
                stats['success'] += 1
            else:
                stats['errors'] += 1
        
        return stats


def relocate_files(input_path: Path, output_dir: Path, pattern: str = None,
                  copy_mode: bool = False, recursive: bool = True,
                  dry_run: bool = False) -> dict:
    """
    Relocate audio files based on metadata
    
    Args:
        input_path: Source file or directory
        output_dir: Target root directory
        pattern: Directory structure pattern
        copy_mode: Copy instead of move
        recursive: Process subdirectories
        dry_run: Preview without moving
        
    Returns:
        Relocation statistics
    """
    if pattern is None:
        pattern = "{artist}/{album}/{track} - {title}"
    
    relocater = FileRelocater(pattern, copy_mode)
    
    if input_path.is_dir():
        return relocater.relocate_directory(input_path, output_dir, recursive, dry_run)
    else:
        source, target, success = relocater.relocate_file(input_path, output_dir, dry_run)
        if success:
            action = "Would move" if dry_run else ("Copied" if copy_mode else "Moved")
            print(f"{action}: {source} -> {target}")
            return {'success': 1, 'errors': 0}
        else:
            return {'success': 0, 'errors': 1}


def main():
    parser = argparse.ArgumentParser(
        description='Organize audio files by metadata',
        epilog='Pattern variables: {artist}, {album}, {title}, {track}, {year}, {genre}'
    )
    parser.add_argument('input', type=Path, help='Input file or directory')
    parser.add_argument('output', type=Path, help='Output root directory')
    parser.add_argument('-p', '--pattern', 
                       default='{artist}/{album}/{track} - {title}',
                       help='Directory structure pattern (default: {artist}/{album}/{track} - {title})')
    parser.add_argument('-c', '--copy', action='store_true', help='Copy instead of move')
    parser.add_argument('-r', '--recursive', action='store_true', help='Process subdirectories')
    parser.add_argument('-n', '--dry-run', action='store_true', help='Preview without moving files')
    
    args = parser.parse_args()
    
    try:
        stats = relocate_files(
            args.input,
            args.output,
            args.pattern,
            args.copy,
            args.recursive,
            args.dry_run
        )
        
        print(f"\n{'Would relocate' if args.dry_run else 'Relocated'}: {stats['success']} files")
        if stats['errors']:
            print(f"Errors: {stats['errors']}")
            return 1
        
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    
    return 0


if __name__ == '__main__':
    sys.exit(main())
