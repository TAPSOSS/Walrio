#!/usr/bin/env python3
"""
Playlist Deleter
Copyright (c) 2025 TAPS OSS
Project: https://github.com/TAPSOSS/Walrio
Licensed under the BSD-3-Clause License (see LICENSE file for details)

Deletes all audio files referenced in a playlist.
WARNING: This is a destructive operation! Use with caution.
"""

import os
import sys
import argparse
import logging
from pathlib import Path
from typing import List, Tuple

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger('PlaylistDeleter')


class PlaylistDeleter:
    """
    Deletes all audio files referenced in a playlist.
    """
    
    def __init__(self, 
                 playlist_path: str,
                 delete_empty_dirs: bool = False,
                 dry_run: bool = False,
                 force: bool = False):
        """
        Initialize the PlaylistDeleter.
        
        Args:
            playlist_path (str): Path to the M3U playlist file
            delete_empty_dirs (bool): If True, delete empty directories after deleting files
            dry_run (bool): If True, show what would be deleted without actually deleting
            force (bool): If True, skip confirmation prompt
        """
        self.playlist_path = playlist_path
        self.delete_empty_dirs = delete_empty_dirs
        self.dry_run = dry_run
        self.force = force
        
        # Statistics
        self.total_files = 0
        self.deleted_files = 0
        self.missing_files = 0
        self.error_files = 0
        self.deleted_dirs = 0
        
        # Validate playlist exists
        if not os.path.isfile(playlist_path):
            raise FileNotFoundError(f"Playlist file not found: {playlist_path}")
    
    def _load_playlist_paths(self) -> List[str]:
        """
        Load file paths from the M3U playlist.
        
        Returns:
            List[str]: List of absolute file paths
        """
        paths = []
        playlist_dir = os.path.dirname(os.path.abspath(self.playlist_path))
        
        try:
            with open(self.playlist_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()
            
            for line in lines:
                line = line.strip()
                
                # Skip empty lines and comments
                if not line or line.startswith('#'):
                    continue
                
                # Convert relative paths to absolute
                if not os.path.isabs(line):
                    file_path = os.path.abspath(os.path.join(playlist_dir, line))
                else:
                    file_path = line
                
                paths.append(file_path)
            
            return paths
        except Exception as e:
            logger.error(f"Error loading playlist: {str(e)}")
            return []
    
    def _confirm_deletion(self, file_paths: List[str]) -> bool:
        """
        Ask user to confirm deletion.
        
        Args:
            file_paths (List[str]): List of files to be deleted
            
        Returns:
            bool: True if user confirms, False otherwise
        """
        if self.force or self.dry_run:
            return True
        
        print("\n" + "=" * 80)
        print("WARNING: You are about to DELETE the following files:")
        print("=" * 80)
        
        # Show first 10 files
        for i, path in enumerate(file_paths[:10], 1):
            exists = "EXISTS" if os.path.exists(path) else "MISSING"
            print(f"  {i}. [{exists}] {path}")
        
        if len(file_paths) > 10:
            print(f"  ... and {len(file_paths) - 10} more files")
        
        print("=" * 80)
        print(f"Total files to delete: {len(file_paths)}")
        
        if self.delete_empty_dirs:
            print("Empty directories will also be deleted.")
        
        print("\nThis action CANNOT be undone!")
        response = input("\nAre you sure you want to continue? Type 'yes' to confirm: ")
        
        return response.lower() == 'yes'
    
    def _delete_empty_parent_dirs(self, file_path: str):
        """
        Delete empty parent directories after deleting a file.
        
        Args:
            file_path (str): Path of the deleted file
        """
        if not self.delete_empty_dirs:
            return
        
        parent_dir = os.path.dirname(file_path)
        
        # Walk up the directory tree and delete empty directories
        while parent_dir and parent_dir != '/':
            try:
                # Check if directory is empty
                if os.path.isdir(parent_dir) and not os.listdir(parent_dir):
                    if self.dry_run:
                        logger.info(f"  Would delete empty directory: {parent_dir}")
                    else:
                        os.rmdir(parent_dir)
                        logger.info(f"  Deleted empty directory: {parent_dir}")
                        self.deleted_dirs += 1
                    parent_dir = os.path.dirname(parent_dir)
                else:
                    # Directory not empty, stop
                    break
            except Exception as e:
                logger.debug(f"Could not delete directory {parent_dir}: {str(e)}")
                break
    
    def delete_playlist_files(self) -> Tuple[int, int, int, int]:
        """
        Delete all files from the playlist.
        
        Returns:
            Tuple[int, int, int, int]: (total, deleted, missing, errors)
        """
        logger.info(f"Loading playlist: {self.playlist_path}")
        file_paths = self._load_playlist_paths()
        
        if not file_paths:
            logger.error("No files found in playlist")
            return 0, 0, 0, 0
        
        self.total_files = len(file_paths)
        
        # Check which files exist
        existing_files = []
        for path in file_paths:
            if os.path.exists(path):
                existing_files.append(path)
            else:
                self.missing_files += 1
        
        logger.info(f"Found {len(existing_files)} existing files (out of {self.total_files} total)")
        if self.missing_files > 0:
            logger.warning(f"{self.missing_files} files are already missing")
        
        if not existing_files:
            logger.info("No files to delete")
            return self.total_files, 0, self.missing_files, 0
        
        # Confirm deletion
        if not self._confirm_deletion(existing_files):
            logger.info("Deletion cancelled by user")
            return self.total_files, 0, self.missing_files, 0
        
        if self.dry_run:
            logger.info("\n[DRY RUN MODE] - No files will be deleted")
        
        logger.info("\n" + "=" * 80)
        logger.info("Starting deletion...")
        logger.info("=" * 80 + "\n")
        
        # Delete files
        for idx, file_path in enumerate(existing_files, 1):
            filename = os.path.basename(file_path)
            logger.info(f"[{idx}/{len(existing_files)}] Processing: {filename}")
            
            if self.dry_run:
                logger.info(f"  Would delete: {file_path}")
                self.deleted_files += 1
            else:
                try:
                    os.remove(file_path)
                    logger.info(f"  ✓ Deleted: {file_path}")
                    self.deleted_files += 1
                    
                    # Delete empty parent directories if requested
                    self._delete_empty_parent_dirs(file_path)
                    
                except Exception as e:
                    logger.error(f"  ✗ Failed to delete: {str(e)}")
                    self.error_files += 1
        
        logger.info("\n" + "=" * 80)
        logger.info("Deletion completed!")
        logger.info(f"Total files in playlist: {self.total_files}")
        logger.info(f"Deleted: {self.deleted_files}")
        logger.info(f"Already missing: {self.missing_files}")
        logger.info(f"Errors: {self.error_files}")
        
        if self.delete_empty_dirs and self.deleted_dirs > 0:
            logger.info(f"Empty directories removed: {self.deleted_dirs}")
        
        logger.info("=" * 80)
        
        return self.total_files, self.deleted_files, self.missing_files, self.error_files


def parse_arguments():
    """
    Parse command line arguments.
    
    Returns:
        argparse.Namespace: Parsed arguments
    """
    parser = argparse.ArgumentParser(
        description="Delete all audio files referenced in a playlist (DESTRUCTIVE OPERATION!)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""Examples:
  # Dry run to see what would be deleted (ALWAYS DO THIS FIRST!)
  python playlist_deleter.py my_playlist.m3u --dry-run
  
  # Delete files with confirmation prompt
  python playlist_deleter.py my_playlist.m3u
  
  # Delete files and empty directories with confirmation
  python playlist_deleter.py my_playlist.m3u --delete-empty-dirs
  
  # Delete without confirmation (DANGEROUS!)
  python playlist_deleter.py my_playlist.m3u --force
  
  # Delete files and all empty parent directories without confirmation (VERY DANGEROUS!)
  python playlist_deleter.py my_playlist.m3u --delete-empty-dirs --force

WARNING: This tool permanently deletes files! There is no undo!
ALWAYS run with --dry-run first to verify what will be deleted!
"""
    )
    
    parser.add_argument(
        'playlist',
        help='Path to the M3U playlist file'
    )
    
    parser.add_argument(
        '--delete-empty-dirs', '--ded',
        action='store_true',
        help='Delete empty directories after deleting files'
    )
    
    parser.add_argument(
        '--dry-run', '-d',
        action='store_true',
        help='Show what would be deleted without actually deleting (RECOMMENDED!)'
    )
    
    parser.add_argument(
        '--force', '-f',
        action='store_true',
        help='Skip confirmation prompt (DANGEROUS!)'
    )
    
    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='Enable verbose logging'
    )
    
    return parser.parse_args()


def main():
    """
    Main entry point for the playlist deleter.
    """
    args = parse_arguments()
    
    # Set logging level
    if args.verbose:
        logger.setLevel(logging.DEBUG)
    
    # Show warning for force mode
    if args.force and not args.dry_run:
        print("\n" + "!" * 80)
        print("WARNING: Running in FORCE mode without dry-run!")
        print("Files will be deleted WITHOUT confirmation!")
        print("!" * 80 + "\n")
    
    try:
        # Create playlist deleter
        deleter = PlaylistDeleter(
            playlist_path=args.playlist,
            delete_empty_dirs=args.delete_empty_dirs,
            dry_run=args.dry_run,
            force=args.force
        )
        
        # Delete files
        total, deleted, missing, errors = deleter.delete_playlist_files()
        
        # Exit with error code if there were errors
        if errors > 0:
            sys.exit(1)
        else:
            sys.exit(0)
            
    except KeyboardInterrupt:
        logger.info("\nOperation cancelled by user")
        sys.exit(130)
    except Exception as e:
        logger.error(f"Fatal error: {str(e)}")
        sys.exit(1)


if __name__ == '__main__':
    main()
