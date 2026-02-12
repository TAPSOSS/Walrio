#!/usr/bin/env python3
"""
detect and fix playlist case conflict (uppercase/lowercase filename variations)
"""

import os
import sys
import argparse
import logging
import shutil
from pathlib import Path
from typing import List, Dict, Optional
from collections import defaultdict

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger('PlaylistCaseConflicts')

# Supported playlist formats
SUPPORTED_FORMATS = {'.m3u', '.m3u8', '.pls'}


class PlaylistCaseConflicts:
    """Detect and repair case-sensitive filename conflicts in playlists."""
    
    def __init__(self, fix_conflicts: bool = False, create_backup: bool = True):
        """
        Initialize the playlist repair tool.
        
        Args:
            fix_conflicts: Whether to automatically fix detected conflicts
            create_backup: Whether to create backup before modifying playlists
        """
        self.fix_conflicts = fix_conflicts
        self.create_backup = create_backup
        self.playlists_checked = 0
        self.conflicts_found = 0
        self.conflicts_fixed = 0
        self.error_count = 0
    
    def is_supported_playlist(self, filepath: str) -> bool:
        """
        Check if file is a supported playlist format.
        
        Args:
            filepath: Path to file to check
            
        Returns:
            True if supported playlist format
        """
        return Path(filepath).suffix.lower() in SUPPORTED_FORMATS
    
    def detect_case_conflicts(self, playlist_path: str) -> Dict[str, List[str]]:
        """
        Detect case conflicts in a playlist file.
        
        Args:
            playlist_path: Path to playlist file
            
        Returns:
            Dictionary mapping normalized paths to list of actual path variations
        """
        conflicts = defaultdict(list)
        
        try:
            with open(playlist_path, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    
                    # Skip empty lines and metadata
                    if not line or line.startswith('#'):
                        continue
                    
                    # Normalize path for comparison (lowercase)
                    normalized = line.lower()
                    conflicts[normalized].append(line)
            
            # Filter out entries with no conflicts (only one variation)
            conflicts = {k: v for k, v in conflicts.items() if len(v) > 1}
            
            return conflicts
            
        except Exception as e:
            logger.error(f"Error reading playlist {playlist_path}: {e}")
            self.error_count += 1
            return {}
    
    def find_real_path(self, variations: List[str], playlist_dir: str) -> Optional[str]:
        """
        Determine the real (correct) path from variations.
        Prefers the path that actually exists on the filesystem.
        
        Args:
            variations: List of path variations
            playlist_dir: Directory containing the playlist
            
        Returns:
            Real path, or None if can't determine
        """
        # Check which variations actually exist on filesystem
        existing = []
        for var in variations:
            # Handle both absolute and relative paths
            if os.path.isabs(var):
                check_path = var
            else:
                check_path = os.path.join(playlist_dir, var)
            
            if os.path.exists(check_path):
                existing.append(var)
        
        # If exactly one exists, use that
        if len(existing) == 1:
            return existing[0]
        
        # If multiple exist or none exist, prefer the most common case pattern
        # (alphabetically first as tiebreaker)
        return sorted(variations)[0]
    
    def fix_playlist_conflicts(self, playlist_path: str, conflicts: Dict[str, List[str]]) -> bool:
        """
        Fix case conflicts in a playlist by replacing variations with real paths.
        
        Args:
            playlist_path: Path to playlist file
            conflicts: Dictionary of detected conflicts
            
        Returns:
            True if fixes were applied successfully
        """
        try:
            playlist_dir = os.path.dirname(playlist_path)
            
            # Create backup if requested
            if self.create_backup:
                backup_path = f"{playlist_path}.backup"
                shutil.copy2(playlist_path, backup_path)
                logger.info(f"Created backup: {backup_path}")
            
            # Read entire playlist
            with open(playlist_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()
            
            # Build replacement mapping
            replacements = {}
            for normalized, variations in conflicts.items():
                real_path = self.find_real_path(variations, playlist_dir)
                if real_path:
                    for var in variations:
                        if var != real_path:
                            replacements[var] = real_path
            
            # Apply replacements
            modified = False
            for i, line in enumerate(lines):
                stripped = line.rstrip('\n\r')
                if stripped in replacements:
                    lines[i] = replacements[stripped] + '\n'
                    modified = True
                    logger.debug(f"Replaced: {stripped} -> {replacements[stripped]}")
            
            # Write back if modified
            if modified:
                with open(playlist_path, 'w', encoding='utf-8') as f:
                    f.writelines(lines)
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"Error fixing playlist {playlist_path}: {e}")
            self.error_count += 1
            return False
    
    def check_playlist(self, playlist_path: str) -> None:
        """
        Check a single playlist for case conflicts.
        
        Args:
            playlist_path: Path to playlist file
        """
        logger.info(f"Checking: {playlist_path}")
        
        conflicts = self.detect_case_conflicts(playlist_path)
        
        if conflicts:
            self.conflicts_found += len(conflicts)
            logger.warning(f"Found {len(conflicts)} case conflict(s)")
            
            # Display conflicts
            for normalized, variations in conflicts.items():
                logger.warning(f"  Conflict in normalized path: {normalized}")
                for var in variations:
                    logger.warning(f"    - {var}")
            
            # Fix if requested
            if self.fix_conflicts:
                logger.info("Attempting to fix conflicts...")
                if self.fix_playlist_conflicts(playlist_path, conflicts):
                    self.conflicts_fixed += len(conflicts)
                    logger.info(f"Fixed {len(conflicts)} conflict(s)")
                else:
                    logger.warning("No changes applied")
        else:
            logger.info("No case conflicts detected")
        
        self.playlists_checked += 1
    
    def process_directory(self, directory: str, recursive: bool = False) -> None:
        """
        Process all playlists in a directory.
        
        Args:
            directory: Directory to process
            recursive: Whether to process subdirectories recursively
        """
        directory_path = Path(directory)
        
        if not directory_path.exists():
            logger.error(f"Directory not found: {directory}")
            return
        
        if not directory_path.is_dir():
            logger.error(f"Not a directory: {directory}")
            return
        
        # Collect playlist files
        if recursive:
            playlist_files = []
            for ext in SUPPORTED_FORMATS:
                playlist_files.extend(directory_path.rglob(f'*{ext}'))
        else:
            playlist_files = []
            for ext in SUPPORTED_FORMATS:
                playlist_files.extend(directory_path.glob(f'*{ext}'))
        
        if not playlist_files:
            logger.warning(f"No playlist files found in {directory}")
            return
        
        logger.info(f"Found {len(playlist_files)} playlist(s) to check")
        
        for playlist_path in sorted(playlist_files):
            self.check_playlist(str(playlist_path))
    
    def print_summary(self) -> None:
        """Print summary of repair operations."""
        print("\n" + "=" * 60)
        print("PLAYLIST CASE CONFLICTS SUMMARY")
        print("=" * 60)
        print(f"Playlists checked: {self.playlists_checked}")
        print(f"Case conflicts found: {self.conflicts_found}")
        
        if self.fix_conflicts:
            print(f"Conflicts fixed: {self.conflicts_fixed}")
        
        if self.error_count > 0:
            print(f"Errors encountered: {self.error_count}")
        
        print("=" * 60 + "\n")


def main():
    """Main entry point for playlist case conflict tool."""
    parser = argparse.ArgumentParser(
        description='Check and repair case conflicts in playlist files',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  Check a single playlist:
    %(prog)s /path/to/playlist.m3u
  
  Check all playlists in a directory:
    %(prog)s /path/to/playlists/ --recursive
  
  Check and fix conflicts automatically:
    %(prog)s /path/to/playlist.m3u --fix
  
  Fix without creating backups:
    %(prog)s /path/to/playlist.m3u --fix --no-backup

Supported formats: .m3u, .m3u8, .pls
        """
    )
    
    parser.add_argument('input', help='Playlist file or directory containing playlists')
    parser.add_argument('--fix', action='store_true', help='Automatically fix detected conflicts')
    parser.add_argument('--no-backup', action='store_true', help='Do not create backup files before fixing')
    parser.add_argument('--recursive', action='store_true', help='Process directories recursively')
    
    args = parser.parse_args()
    
    # Create checker instance
    checker = PlaylistCaseConflicts(
        fix_conflicts=args.fix,
        create_backup=not args.no_backup
    )
    
    # Process input
    input_path = Path(args.input)
    
    if not input_path.exists():
        logger.error(f"Input not found: {args.input}")
        return 1
    
    if input_path.is_file():
        # Single playlist file
        if not checker.is_supported_playlist(str(input_path)):
            logger.error(f"Unsupported file format: {input_path.suffix}")
            logger.info(f"Supported formats: {', '.join(SUPPORTED_FORMATS)}")
            return 1
        
        checker.check_playlist(str(input_path))
    elif input_path.is_dir():
        # Directory of playlists
        checker.process_directory(str(input_path), recursive=args.recursive)
    else:
        logger.error(f"Invalid input: {args.input}")
        return 1
    
    # Print summary
    checker.print_summary()
    
    # Return non-zero exit code if errors occurred
    return 1 if checker.error_count > 0 else 0


if __name__ == '__main__':
    sys.exit(main())
