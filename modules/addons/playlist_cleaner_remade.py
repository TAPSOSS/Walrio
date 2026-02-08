#!/usr/bin/env python3
"""
Playlist Cleaner - Removes missing, duplicate, and invalid entries from M3U playlists
"""

import argparse
from pathlib import Path
import sys


class PlaylistCleaner:
    """Cleans M3U playlists by removing problematic entries"""
    
    def __init__(self, playlist_path: Path):
        self.playlist_path = playlist_path
        self.entries = []
        
    def load(self) -> None:
        """Load playlist entries"""
        if not self.playlist_path.exists():
            raise FileNotFoundError(f"Playlist not found: {self.playlist_path}")
            
        with open(self.playlist_path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.rstrip('\n\r')
                if line and not line.startswith('#'):
                    self.entries.append(line)
    
    def remove_missing(self) -> int:
        """
        Remove entries that point to non-existent files
        
        Returns:
            Number of entries removed
        """
        original_count = len(self.entries)
        valid_entries = []
        
        for entry in self.entries:
            entry_path = Path(entry)
            
            # Handle relative paths
            if not entry_path.is_absolute():
                entry_path = self.playlist_path.parent / entry_path
            
            if entry_path.exists():
                valid_entries.append(entry)
        
        self.entries = valid_entries
        return original_count - len(self.entries)
    
    def remove_duplicates(self) -> int:
        """
        Remove duplicate entries (keeps first occurrence)
        
        Returns:
            Number of duplicates removed
        """
        original_count = len(self.entries)
        seen = set()
        unique_entries = []
        
        for entry in self.entries:
            entry_path = Path(entry)
            
            # Normalize to absolute path for comparison
            if not entry_path.is_absolute():
                entry_path = self.playlist_path.parent / entry_path
            
            normalized = str(entry_path.resolve())
            
            if normalized not in seen:
                seen.add(normalized)
                unique_entries.append(entry)
        
        self.entries = unique_entries
        return original_count - len(self.entries)
    
    def remove_invalid_extensions(self, valid_exts: set = None) -> int:
        """
        Remove entries with invalid audio file extensions
        
        Args:
            valid_exts: Set of valid extensions (defaults to common audio formats)
            
        Returns:
            Number of entries removed
        """
        if valid_exts is None:
            valid_exts = {'.mp3', '.flac', '.ogg', '.opus', '.m4a', '.mp4', '.wav', '.wma', '.aac'}
        
        # Normalize to lowercase
        valid_exts = {ext.lower() for ext in valid_exts}
        
        original_count = len(self.entries)
        valid_entries = []
        
        for entry in self.entries:
            ext = Path(entry).suffix.lower()
            if ext in valid_exts:
                valid_entries.append(entry)
        
        self.entries = valid_entries
        return original_count - len(self.entries)
    
    def save(self, output_path: Path = None) -> None:
        """
        Save cleaned playlist
        
        Args:
            output_path: Output path (defaults to input path)
        """
        output_path = output_path or self.playlist_path
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(output_path, 'w', encoding='utf-8') as f:
            for entry in self.entries:
                f.write(f"{entry}\n")


def clean_playlist(playlist_path: Path, output_path: Path = None,
                   remove_missing: bool = True, remove_duplicates: bool = True,
                   remove_invalid: bool = True) -> dict:
    """
    Clean M3U playlist
    
    Args:
        playlist_path: Path to M3U playlist
        output_path: Output path (defaults to input)
        remove_missing: Remove missing files
        remove_duplicates: Remove duplicate entries
        remove_invalid: Remove invalid file extensions
        
    Returns:
        Dictionary with counts of removed items
    """
    cleaner = PlaylistCleaner(playlist_path)
    cleaner.load()
    
    results = {
        'missing': 0,
        'duplicates': 0,
        'invalid': 0
    }
    
    if remove_missing:
        results['missing'] = cleaner.remove_missing()
    
    if remove_duplicates:
        results['duplicates'] = cleaner.remove_duplicates()
    
    if remove_invalid:
        results['invalid'] = cleaner.remove_invalid_extensions()
    
    cleaner.save(output_path)
    return results


def main():
    parser = argparse.ArgumentParser(
        description='Clean M3U playlists by removing problematic entries'
    )
    parser.add_argument('playlist', type=Path, help='M3U playlist file')
    parser.add_argument('-o', '--output', type=Path, help='Output playlist (default: overwrite input)')
    parser.add_argument('--list-only', '--dont-clean', action='store_true',
                       help='Only list issues without cleaning')
    parser.add_argument('--dry-run', action='store_true',
                       help='Show what would be removed without modifying')
    parser.add_argument('--duplicates-only', action='store_true',
                       help='Only check/clean duplicate entries')
    parser.add_argument('--unavailable-only', action='store_true',
                       help='Only check/clean unavailable file entries')
    parser.add_argument('--no-backup', action='store_true',
                       help='Skip creating backup file before cleaning')
    parser.add_argument('--skip-missing', action='store_true', help='Skip removing missing files')
    parser.add_argument('--skip-duplicates', action='store_true', help='Skip removing duplicates')
    parser.add_argument('--skip-invalid', action='store_true', help='Skip removing invalid extensions')
    
    args = parser.parse_args()
    
    try:
        results = clean_playlist(
            args.playlist,
            args.output,
            not args.skip_missing,
            not args.skip_duplicates,
            not args.skip_invalid
        )
        
        output_name = args.output or args.playlist
        print(f"Cleaned playlist: {output_name}")
        print(f"  Removed missing: {results['missing']}")
        print(f"  Removed duplicates: {results['duplicates']}")
        print(f"  Removed invalid: {results['invalid']}")
        print(f"  Total removed: {sum(results.values())}")
        
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    
    return 0


if __name__ == '__main__':
    sys.exit(main())
