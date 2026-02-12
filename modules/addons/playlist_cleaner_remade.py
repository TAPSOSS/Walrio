#!/usr/bin/env python3
"""
Playlist Cleaner - Removes missing, duplicate, and invalid entries from M3U playlists
"""

import argparse
import logging
import shutil
from pathlib import Path
from typing import List, Tuple
import sys

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)


class PlaylistCleaner:
    """Handle cleaning of M3U playlists"""

    def __init__(self, playlist_path: str):
        """
        Initialize the playlist cleaner
        
        Args:
            playlist_path: Path to the M3U playlist file
        """
        self.playlist_path = Path(playlist_path)
        if not self.playlist_path.exists():
            raise FileNotFoundError(f"Playlist not found: {playlist_path}")
        
        self.playlist_dir = self.playlist_path.parent
        self.entries = []
        self.duplicates = []
        self.unavailable = []
    
    def read_playlist(self) -> List[str]:
        """
        Read the playlist file and return all lines
        
        Returns:
            List of lines from the playlist file
        """
        with open(self.playlist_path, 'r', encoding='utf-8') as f:
            return f.readlines()
    
    def parse_playlist(self) -> List[Tuple[str, str]]:
        """
        Parse the playlist and extract file paths with their full entry context
        
        Returns:
            List of tuples (full_entry, file_path) where full_entry includes
            any EXTINF lines and the file path line
        """
        lines = self.read_playlist()
        entries = []
        current_extinf = None
        
        for line in lines:
            line = line.rstrip('\n\r')
            
            # Skip empty lines and comments that aren't EXTINF
            if not line or (line.startswith('#') and not line.startswith('#EXTINF')):
                continue
            
            # Track EXTINF metadata lines
            if line.startswith('#EXTINF'):
                current_extinf = line
                continue
            
            # This is a file path line
            if current_extinf:
                full_entry = f"{current_extinf}\n{line}"
                current_extinf = None
            else:
                full_entry = line
            
            entries.append((full_entry, line))
        
        return entries
    
    def resolve_path(self, file_path: str) -> Path:
        """
        Resolve a file path relative to the playlist directory
        
        Args:
            file_path: File path from the playlist (may be relative)
            
        Returns:
            Absolute Path object
        """
        path = Path(file_path)
        
        # If it's already absolute, return it
        if path.is_absolute():
            return path
        
        # Otherwise, resolve relative to playlist directory
        return (self.playlist_dir / path).resolve()
    
    def find_duplicates(self, entries: List[Tuple[str, str]]) -> List[int]:
        """
        Find duplicate entries in the playlist
        
        Args:
            entries: List of (full_entry, file_path) tuples
            
        Returns:
            List of indices for duplicate entries (keeps first occurrence)
        """
        seen_paths = set()
        duplicate_indices = []
        
        for idx, (full_entry, file_path) in enumerate(entries):
            # Normalize the path for comparison
            normalized_path = str(self.resolve_path(file_path))
            
            if normalized_path in seen_paths:
                duplicate_indices.append(idx)
            else:
                seen_paths.add(normalized_path)
        
        return duplicate_indices
    
    def find_unavailable(self, entries: List[Tuple[str, str]]) -> List[int]:
        """
        Find entries for files that don't exist on disk
        
        Args:
            entries: List of (full_entry, file_path) tuples
            
        Returns:
            List of indices for unavailable entries
        """
        unavailable_indices = []
        
        for idx, (full_entry, file_path) in enumerate(entries):
            resolved_path = self.resolve_path(file_path)
            
            if not resolved_path.exists():
                unavailable_indices.append(idx)
        
        return unavailable_indices
    
    def analyze(self, check_duplicates: bool = True, check_unavailable: bool = True):
        """
        Analyze the playlist for issues
        
        Args:
            check_duplicates: Whether to check for duplicates
            check_unavailable: Whether to check for unavailable files
        """
        logger.info(f"Analyzing playlist: {self.playlist_path.name}")
        
        self.entries = self.parse_playlist()
        total_entries = len(self.entries)
        
        logger.info(f"Total entries: {total_entries}")
        
        if check_duplicates:
            duplicate_indices = self.find_duplicates(self.entries)
            self.duplicates = [(idx, self.entries[idx]) for idx in duplicate_indices]
            logger.info(f"Found {len(self.duplicates)} duplicate entries")
        
        if check_unavailable:
            unavailable_indices = self.find_unavailable(self.entries)
            self.unavailable = [(idx, self.entries[idx]) for idx in unavailable_indices]
            logger.info(f"Found {len(self.unavailable)} unavailable entries")
    
    def list_issues(self, show_duplicates: bool = True, show_unavailable: bool = True):
        """
        List all found issues
        
        Args:
            show_duplicates: Whether to show duplicates
            show_unavailable: Whether to show unavailable files
        """
        if show_duplicates and self.duplicates:
            logger.info("\n" + "=" * 80)
            logger.info(f"DUPLICATE ENTRIES ({len(self.duplicates)}):")
            logger.info("=" * 80)
            for idx, (full_entry, file_path) in self.duplicates:
                logger.info(f"  Entry #{idx + 1}: {file_path}")
        
        if show_unavailable and self.unavailable:
            logger.info("\n" + "=" * 80)
            logger.info(f"UNAVAILABLE ENTRIES ({len(self.unavailable)}):")
            logger.info("=" * 80)
            for idx, (full_entry, file_path) in self.unavailable:
                resolved = self.resolve_path(file_path)
                logger.info(f"  Entry #{idx + 1}: {file_path}")
                logger.info(f"    Resolved to: {resolved}")
    
    def clean(self, remove_duplicates: bool = True, remove_unavailable: bool = True, 
             dry_run: bool = False, no_backup: bool = False):
        """
        Clean the playlist by removing problematic entries
        
        Args:
            remove_duplicates: Whether to remove duplicates
            remove_unavailable: Whether to remove unavailable files
            dry_run: If True, don't actually modify the file
            no_backup: If True, skip creating a backup file
        """
        # Collect indices to remove
        indices_to_remove = set()
        
        if remove_duplicates:
            indices_to_remove.update(idx for idx, _ in self.duplicates)
        
        if remove_unavailable:
            indices_to_remove.update(idx for idx, _ in self.unavailable)
        
        if not indices_to_remove:
            logger.info("No entries to remove - playlist is clean!")
            return
        
        # Create cleaned playlist
        cleaned_entries = [
            entry for idx, entry in enumerate(self.entries)
            if idx not in indices_to_remove
        ]
        
        original_count = len(self.entries)
        cleaned_count = len(cleaned_entries)
        removed_count = original_count - cleaned_count
        
        logger.info(f"\n{'[DRY RUN] ' if dry_run else ''}Removing {removed_count} entries...")
        logger.info(f"  Original entries: {original_count}")
        logger.info(f"  Cleaned entries: {cleaned_count}")
        
        if dry_run:
            logger.info("\nDry run - no changes made to playlist")
            return
        
        # Create backup unless disabled
        if not no_backup:
            backup_path = self.playlist_path.with_suffix('.m3u.backup')
            logger.info(f"Creating backup: {backup_path.name}")
            shutil.copy2(self.playlist_path, backup_path)
        else:
            logger.info("Skipping backup creation (--no-backup specified)")
        
        # Write cleaned playlist
        logger.info(f"Writing cleaned playlist...")
        
        with open(self.playlist_path, 'w', encoding='utf-8') as f:
            # Write header if original had one
            lines = self.read_playlist()
            if lines and lines[0].startswith('#EXTM3U'):
                f.write('#EXTM3U\n')
            
            # Write cleaned entries
            for full_entry, file_path in cleaned_entries:
                f.write(full_entry + '\n')
        
        logger.info("✓ Playlist cleaned successfully!")


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description='Clean M3U playlists by removing duplicates and unavailable entries',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Analyze and clean both duplicates and unavailable entries
  %(prog)s myplaylist.m3u
  
  # Only list issues without cleaning
  %(prog)s myplaylist.m3u --list-only
  
  # Preview what would be removed (dry run)
  %(prog)s myplaylist.m3u --dry-run
  
  # Clean without creating a backup
  %(prog)s myplaylist.m3u --no-backup
  
  # Only remove duplicates
  %(prog)s myplaylist.m3u --duplicates-only
  
  # Only remove unavailable files
  %(prog)s myplaylist.m3u --unavailable-only
  
  # List only duplicates
  %(prog)s myplaylist.m3u --list-only --duplicates-only
        """
    )
    
    parser.add_argument(
        'playlist',
        help='Path to the M3U playlist file'
    )
    
    parser.add_argument(
        '--list-only',
        '--dont-clean',
        action='store_true',
        help='Only list issues without cleaning the playlist'
    )
    
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Show what would be removed without actually modifying the playlist'
    )
    
    parser.add_argument(
        '--duplicates-only',
        action='store_true',
        help='Only check/clean duplicate entries'
    )
    
    parser.add_argument(
        '--unavailable-only',
        action='store_true',
        help='Only check/clean unavailable file entries'
    )
    
    parser.add_argument(
        '--no-backup',
        action='store_true',
        help='Skip creating a backup file before cleaning'
    )
    
    args = parser.parse_args()
    
    # Determine what to check
    check_duplicates = not args.unavailable_only
    check_unavailable = not args.duplicates_only
    
    try:
        cleaner = PlaylistCleaner(args.playlist)
        
        # Analyze the playlist
        cleaner.analyze(
            check_duplicates=check_duplicates,
            check_unavailable=check_unavailable
        )
        
        # List the issues
        cleaner.list_issues(
            show_duplicates=check_duplicates,
            show_unavailable=check_unavailable
        )
        
        # Clean if requested
        if not args.list_only:
            cleaner.clean(
                remove_duplicates=check_duplicates,
                remove_unavailable=check_unavailable,
                dry_run=args.dry_run,
                no_backup=args.no_backup
            )
        else:
            logger.info("\n--list-only specified, no changes made to playlist")
        
        return 0
        
    except FileNotFoundError as e:
        logger.error(f"Error: {e}")
        return 1
    except KeyboardInterrupt:
        logger.info("\nOperation cancelled by user")
        return 130
    except Exception as e:
        logger.error(f"Unexpected error: {e}", exc_info=True)
        return 1


if __name__ == '__main__':
    sys.exit(main())
