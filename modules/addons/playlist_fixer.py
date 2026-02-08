#!/usr/bin/env python3

import os
import sys
import argparse
import logging
from pathlib import Path
from typing import List, Dict, Optional, Tuple

# Add parent directory to path for module imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from core import playlist as playlist_module

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger('PlaylistFixer')

# Audio file extensions to search for
AUDIO_EXTENSIONS = {'.mp3', '.flac', '.wav', '.ogg', '.m4a', '.aac', '.opus', '.wma', '.ape', '.wv'}


class PlaylistFixer:
    """
    Tool to fix missing songs in playlists by searching for replacements or prompting users.
    """
    
    def __init__(self, playlist_path: str, search_dirs: List[str] = None):
        """
        Initialize the PlaylistFixer.
        
        Args:
            playlist_path (str): Path to the playlist file to fix
            search_dirs (List[str]): Optional list of directories to search for missing files
        """
        self.playlist_path = playlist_path
        self.search_dirs = search_dirs or []
        self.playlist_data = None
        self.missing_songs = []
        self.fixed_count = 0
        self.removed_count = 0
        self.skipped_count = 0
        self.file_cache = {}  # Cache of filename -> full paths
        
    def load_playlist(self) -> Optional[List[Dict]]:
        """
        Load the playlist using the playlist module.
        
        Returns:
            Optional[List[Dict]]: List of track dictionaries or None if failed
        """
        try:
            self.playlist_data = playlist_module.load_playlist(self.playlist_path)
            if not self.playlist_data:
                logger.error("Playlist is empty or could not be loaded")
                return None
            
            logger.info(f"Loaded playlist: {os.path.basename(self.playlist_path)}")
            logger.info(f"Total tracks: {len(self.playlist_data)}")
            return self.playlist_data
        except Exception as e:
            logger.error(f"Failed to load playlist: {str(e)}")
            return None
    
    def find_missing_songs(self) -> List[Tuple[int, Dict]]:
        """
        Identify all missing songs in the playlist.
        
        Returns:
            List[Tuple[int, Dict]]: List of (index, track_data) tuples for missing songs
        """
        missing = []
        for idx, track in enumerate(self.playlist_data):
            filepath = track.get('url', '')
            if not os.path.exists(filepath):
                missing.append((idx, track))
                logger.debug(f"Missing: {filepath}")
        
        logger.info(f"Found {len(missing)} missing songs")
        return missing
    
    def build_file_cache(self):
        """
        Build a cache of audio files in the search directories.
        Maps filename -> list of full paths for quick lookup.
        """
        logger.info(f"Building file cache from {len(self.search_dirs)} search directories...")
        
        for search_dir in self.search_dirs:
            if not os.path.exists(search_dir):
                logger.warning(f"Search directory does not exist: {search_dir}")
                continue
            
            for root, _, files in os.walk(search_dir):
                for file in files:
                    if Path(file).suffix.lower() in AUDIO_EXTENSIONS:
                        full_path = os.path.join(root, file)
                        filename = os.path.basename(file)
                        
                        if filename not in self.file_cache:
                            self.file_cache[filename] = []
                        self.file_cache[filename].append(full_path)
        
        total_files = sum(len(paths) for paths in self.file_cache.values())
        logger.info(f"File cache built: {len(self.file_cache)} unique filenames, {total_files} total files")
    
    def find_replacement_candidates(self, missing_path: str) -> List[str]:
        """
        Find potential replacement files based on filename matching.
        
        Args:
            missing_path (str): Path to the missing file
            
        Returns:
            List[str]: List of candidate replacement paths
        """
        filename = os.path.basename(missing_path)
        candidates = self.file_cache.get(filename, [])
        
        # Filter out the original missing path if it somehow got cached
        candidates = [c for c in candidates if os.path.abspath(c) != os.path.abspath(missing_path)]
        
        return candidates
    
    def prompt_user_for_replacement(self, missing_track: Dict, candidates: List[str]) -> Optional[str]:
        """
        Prompt the user to select a replacement or take another action.
        
        Args:
            missing_track (Dict): Track data for the missing song
            candidates (List[str]): List of candidate replacement paths
            
        Returns:
            Optional[str]: Replacement path, 'REMOVE' to remove, 'SKIP' to skip, or None
        """
        missing_path = missing_track.get('url', '')
        title = missing_track.get('title', 'Unknown')
        artist = missing_track.get('artist', 'Unknown')
        
        print("\n" + "=" * 80)
        print(f"Missing Song:")
        print(f"  Title: {title}")
        print(f"  Artist: {artist}")
        print(f"  Path: {missing_path}")
        print("=" * 80)
        
        if candidates:
            print(f"\nFound {len(candidates)} potential replacement(s):")
            for idx, candidate in enumerate(candidates, 1):
                print(f"  {idx}. {candidate}")
            print(f"  {len(candidates) + 1}. Enter custom path")
            print(f"  {len(candidates) + 2}. Remove from playlist")
            print(f"  {len(candidates) + 3}. Skip (fix later)")
            
            while True:
                try:
                    choice = input("\nSelect an option (number): ").strip()
                    choice_num = int(choice)
                    
                    if 1 <= choice_num <= len(candidates):
                        selected = candidates[choice_num - 1]
                        confirm = input(f"Use '{selected}'? (y/n): ").lower().strip()
                        if confirm in ['y', 'yes']:
                            return selected
                    elif choice_num == len(candidates) + 1:
                        custom_path = input("Enter full path to replacement file: ").strip()
                        if os.path.exists(custom_path):
                            return custom_path
                        else:
                            print(f"File not found: {custom_path}")
                    elif choice_num == len(candidates) + 2:
                        confirm = input("Remove this song from playlist? (y/n): ").lower().strip()
                        if confirm in ['y', 'yes']:
                            return 'REMOVE'
                    elif choice_num == len(candidates) + 3:
                        return 'SKIP'
                    else:
                        print("Invalid choice. Please try again.")
                except ValueError:
                    print("Invalid input. Please enter a number.")
                except (KeyboardInterrupt, EOFError):
                    print("\nOperation cancelled by user.")
                    return 'SKIP'
        else:
            print("\nNo automatic replacements found.")
            print("  1. Enter custom path")
            print("  2. Remove from playlist")
            print("  3. Skip (fix later)")
            
            while True:
                try:
                    choice = input("\nSelect an option (1-3): ").strip()
                    
                    if choice == '1':
                        custom_path = input("Enter full path to replacement file: ").strip()
                        if os.path.exists(custom_path):
                            return custom_path
                        else:
                            print(f"File not found: {custom_path}")
                    elif choice == '2':
                        confirm = input("Remove this song from playlist? (y/n): ").lower().strip()
                        if confirm in ['y', 'yes']:
                            return 'REMOVE'
                    elif choice == '3':
                        return 'SKIP'
                    else:
                        print("Invalid choice. Please enter 1, 2, or 3.")
                except (KeyboardInterrupt, EOFError):
                    print("\nOperation cancelled by user.")
                    return 'SKIP'
        
        return 'SKIP'
    
    def fix_playlist(self, dry_run: bool = False) -> bool:
        """
        Fix missing songs in the playlist.
        
        Args:
            dry_run (bool): If True, show what would be fixed without saving
            
        Returns:
            bool: True if playlist was modified (or would be in dry run), False otherwise
        """
        # Load playlist
        if not self.load_playlist():
            return False
        
        # Find missing songs
        missing_songs = self.find_missing_songs()
        if not missing_songs:
            logger.info("No missing songs found. Playlist is already complete!")
            return False
        
        # Build file cache if search directories provided
        if self.search_dirs:
            self.build_file_cache()
        
        # Process each missing song
        tracks_to_remove = []
        
        for idx, track in missing_songs:
            missing_path = track.get('url', '')
            
            # Find replacement candidates
            candidates = self.find_replacement_candidates(missing_path)
            
            # Prompt user for action
            action = self.prompt_user_for_replacement(track, candidates)
            
            if action == 'REMOVE':
                tracks_to_remove.append(idx)
                self.removed_count += 1
                logger.info(f"Marked for removal: {missing_path}")
            elif action == 'SKIP':
                self.skipped_count += 1
                logger.info(f"Skipped: {missing_path}")
            elif action and action != 'SKIP':
                # Update the track path
                if dry_run:
                    logger.info(f"[DRY RUN] Would replace: {missing_path} -> {action}")
                else:
                    self.playlist_data[idx]['url'] = action
                    logger.info(f"Replaced: {missing_path} -> {action}")
                self.fixed_count += 1
        
        # Remove tracks marked for removal (in reverse order to maintain indices)
        if tracks_to_remove:
            for idx in sorted(tracks_to_remove, reverse=True):
                if dry_run:
                    logger.info(f"[DRY RUN] Would remove track at index {idx}")
                else:
                    self.playlist_data.pop(idx)
        
        # Save playlist if changes were made
        if (self.fixed_count > 0 or self.removed_count > 0) and not dry_run:
            try:
                playlist_module.save_playlist(self.playlist_path, self.playlist_data)
                logger.info(f"Playlist saved: {self.playlist_path}")
            except Exception as e:
                logger.error(f"Failed to save playlist: {str(e)}")
                return False
        
        # Print summary
        print("\n" + "=" * 80)
        print("Playlist Fix Summary:")
        print(f"  Fixed: {self.fixed_count}")
        print(f"  Removed: {self.removed_count}")
        print(f"  Skipped: {self.skipped_count}")
        print(f"  Total missing: {len(missing_songs)}")
        if dry_run:
            print("\n[DRY RUN] No changes were saved.")
        print("=" * 80)
        
        return self.fixed_count > 0 or self.removed_count > 0


def main():
    """
    Main entry point for the playlist fixer tool.
    """
    parser = argparse.ArgumentParser(
        description="Fix missing songs in playlists by searching for replacements",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Fix a playlist by searching in a specific directory
  python modules/walrio.py playlist_fixer playlist.m3u --search /path/to/music

  # Fix a playlist with multiple search directories
  python modules/walrio.py playlist_fixer playlist.m3u --search /music/folder1 --search /music/folder2

  # Dry run to see what would be fixed
  python modules/walrio.py playlist_fixer playlist.m3u --search /music --dry-run

  # Fix a playlist without automatic search (manual prompts only)
  python modules/walrio.py playlist_fixer playlist.m3u
        """
    )
    
    parser.add_argument(
        'playlist',
        help='Path to the playlist file to fix'
    )
    parser.add_argument(
        '--search', '-s',
        action='append',
        dest='search_dirs',
        help='Directory to search for missing files (can be used multiple times)'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Show what would be fixed without saving changes'
    )
    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='Enable verbose logging'
    )
    
    args = parser.parse_args()
    
    # Set logging level
    if args.verbose:
        logger.setLevel(logging.DEBUG)
    
    # Validate playlist path
    if not os.path.exists(args.playlist):
        logger.error(f"Playlist file not found: {args.playlist}")
        sys.exit(1)
    
    # Validate search directories
    search_dirs = args.search_dirs or []
    for search_dir in search_dirs:
        if not os.path.exists(search_dir):
            logger.warning(f"Search directory does not exist: {search_dir}")
    
    # Create fixer and run
    try:
        fixer = PlaylistFixer(args.playlist, search_dirs)
        success = fixer.fix_playlist(dry_run=args.dry_run)
        
        if success:
            logger.info("Playlist fixing completed successfully!")
            sys.exit(0)
        else:
            logger.info("No changes were made to the playlist.")
            sys.exit(0)
            
    except KeyboardInterrupt:
        print("\n\nPlaylist fixing interrupted by user.")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Error during playlist fixing: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
