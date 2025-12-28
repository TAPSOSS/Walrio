#!/usr/bin/env python3
"""
Playlist Repair Tool
Copyright (c) 2025 TAPS OSS
Project: https://github.com/TAPSOSS/Walrio
Licensed under the BSD-3-Clause License (see LICENSE file for details)

A tool to detect and repair case conflicts in playlist files.
Checks for entries that point to the same file with different case variations,
which can cause issues on case-insensitive filesystems.
"""

import os
import sys
import argparse
import logging
from pathlib import Path
from typing import List, Dict, Set, Tuple, Optional
from collections import defaultdict

# Add parent directory to path for module imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
from modules.core import playlist

# Configure logging format
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger('PlaylistRepair')

# Supported playlist formats
SUPPORTED_FORMATS = {'.m3u', '.m3u8', '.pls'}


class PlaylistRepair:
    """
    Playlist repair tool for detecting and fixing case conflicts
    """
    
    def __init__(self, fix_conflicts: bool = False, create_backup: bool = True):
        """
        Initialize the playlist repair tool.
        
        Args:
            fix_conflicts (bool): Whether to automatically fix detected conflicts
            create_backup (bool): Whether to create backup before modifying playlists
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
            filepath (str): Path to file to check
            
        Returns:
            bool: True if supported playlist format
        """
        return Path(filepath).suffix.lower() in SUPPORTED_FORMATS
    
    def detect_case_conflicts(self, playlist_path: str) -> Dict[str, List[str]]:
        """
        Detect case conflicts in a playlist file.
        
        Args:
            playlist_path (str): Path to playlist file
            
        Returns:
            Dict[str, List[str]]: Dictionary mapping normalized paths to list of actual path variations
        """
        conflicts = defaultdict(list)
        
        try:
            # Read playlist entries
            pl = playlist.Playlist(playlist_path)
            
            # Group entries by normalized (lowercase) path
            for entry in pl.entries:
                if entry.startswith('#'):
                    continue  # Skip metadata lines
                    
                # Normalize path for comparison
                normalized = entry.lower()
                conflicts[normalized].append(entry)
            
            # Filter out entries with no conflicts (only one variation)
            conflicts = {k: v for k, v in conflicts.items() if len(v) > 1}
            
            return conflicts
            
        except Exception as e:
            logger.error(f"Error reading playlist {playlist_path}: {e}")
            self.error_count += 1
            return {}
    
    def get_canonical_path(self, variations: List[str], playlist_dir: str) -> Optional[str]:
        """
        Determine the canonical (correct) path from variations.
        Prefers the path that actually exists on the filesystem.
        
        Args:
            variations (List[str]): List of path variations
            playlist_dir (str): Directory containing the playlist
            
        Returns:
            Optional[str]: Canonical path, or None if can't determine
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
        Fix case conflicts in a playlist by replacing variations with canonical paths.
        
        Args:
            playlist_path (str): Path to playlist file
            conflicts (Dict[str, List[str]]): Dictionary of detected conflicts
            
        Returns:
            bool: True if fixes were applied successfully
        """
        try:
            playlist_dir = os.path.dirname(playlist_path)
            
            # Create backup if requested
            if self.create_backup:
                backup_path = f"{playlist_path}.backup"
                import shutil
                shutil.copy2(playlist_path, backup_path)
                logger.info(f"Created backup: {backup_path}")
            
            # Read entire playlist
            with open(playlist_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()
            
            # Build replacement mapping
            replacements = {}
            for normalized, variations in conflicts.items():
                canonical = self.get_canonical_path(variations, playlist_dir)
                if canonical:
                    for var in variations:
                        if var != canonical:
                            replacements[var] = canonical
            
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
            playlist_path (str): Path to playlist file
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
            directory (str): Directory to process
            recursive (bool): Whether to process subdirectories recursively
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
        """
        Print summary of repair operations.
        """
        logger.info("="*60)
        logger.info("PLAYLIST REPAIR SUMMARY")
        logger.info("="*60)
        logger.info(f"Playlists checked: {self.playlists_checked}")
        logger.info(f"Case conflicts found: {self.conflicts_found}")
        
        if self.fix_conflicts:
            logger.info(f"Conflicts fixed: {self.conflicts_fixed}")
        
        if self.error_count > 0:
            logger.warning(f"Errors encountered: {self.error_count}")
        
        logger.info("="*60)


def main():
    """
    Main entry point for playlist repair tool.
    """
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
        """
    )
    
    parser.add_argument(
        'input',
        help='Playlist file or directory containing playlists'
    )
    
    parser.add_argument(
        '--fix',
        action='store_true',
        help='Automatically fix detected conflicts'
    )
    
    parser.add_argument(
        '--no-backup',
        action='store_true',
        help='Do not create backup files before fixing (use with caution)'
    )
    
    parser.add_argument(
        '--recursive',
        action='store_true',
        help='Process directories recursively'
    )
    
    parser.add_argument(
        '--verbose',
        action='store_true',
        help='Enable verbose debug output'
    )
    
    args = parser.parse_args()
    
    # Configure logging level
    if args.verbose:
        logger.setLevel(logging.DEBUG)
    
    # Create repair instance
    repair = PlaylistRepair(
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
        if not repair.is_supported_playlist(str(input_path)):
            logger.error(f"Unsupported file format: {input_path.suffix}")
            logger.info(f"Supported formats: {', '.join(SUPPORTED_FORMATS)}")
            return 1
        
        repair.check_playlist(str(input_path))
    elif input_path.is_dir():
        # Directory of playlists
        repair.process_directory(str(input_path), recursive=args.recursive)
    else:
        logger.error(f"Invalid input: {args.input}")
        return 1
    
    # Print summary
    repair.print_summary()
    
    # Return non-zero exit code if errors occurred
    return 1 if repair.error_count > 0 else 0


if __name__ == '__main__':
    sys.exit(main())
