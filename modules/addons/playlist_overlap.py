#!/usr/bin/env python3
"""
Playlist Overlap Finder
Copyright (c) 2025 TAPS OSS
Project: https://github.com/TAPSOSS/Walrio
Licensed under the BSD-3-Clause License (see LICENSE file for details)

This script finds songs that appear in multiple playlists (overlap) and creates
a new playlist containing only those overlapping songs.
"""

import os
import sys
import argparse
import logging
from pathlib import Path
from typing import List, Set, Dict, Tuple

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger('PlaylistOverlap')


class PlaylistOverlapFinder:
    """
    Find overlapping songs between playlists and create a new playlist with the results.
    """
    
    def __init__(self):
        """Initialize the PlaylistOverlapFinder."""
        pass
    
    def _load_m3u_paths(self, playlist_path: str) -> List[str]:
        """
        Load file paths from an M3U playlist (without metadata extraction).
        
        Args:
            playlist_path (str): Path to the M3U playlist file
            
        Returns:
            list: List of file paths from the playlist
        """
        paths = []
        playlist_dir = os.path.dirname(os.path.abspath(playlist_path))
        
        try:
            with open(playlist_path, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    
                    # Skip empty lines and comment lines (but not EXTINF)
                    if not line or (line.startswith('#') and not line.startswith('#EXTINF')):
                        continue
                    
                    # Skip EXTINF lines (metadata)
                    if line.startswith('#EXTINF'):
                        continue
                    
                    # This is a file path
                    file_path = line
                    
                    # Convert relative paths to absolute
                    if not os.path.isabs(file_path):
                        file_path = os.path.normpath(os.path.join(playlist_dir, file_path))
                    
                    paths.append(file_path)
            
            logger.debug(f"Loaded {len(paths)} paths from {os.path.basename(playlist_path)}")
            return paths
            
        except Exception as e:
            logger.error(f"Error loading playlist {playlist_path}: {str(e)}")
            return []
    
    def _normalize_path(self, path: str) -> str:
        """
        Normalize a file path for comparison.
        
        Args:
            path (str): File path to normalize
            
        Returns:
            str: Normalized absolute path
        """
        return os.path.normpath(os.path.abspath(path))
    
    def find_overlap(self, playlist_paths: List[str]) -> Set[str]:
        """
        Find songs that appear in all provided playlists.
        
        Args:
            playlist_paths (list): List of playlist file paths
            
        Returns:
            set: Set of file paths that appear in all playlists
        """
        if len(playlist_paths) < 2:
            logger.error("Need at least 2 playlists to find overlap")
            return set()
        
        # Load all playlists and normalize paths
        all_paths = []
        for playlist_path in playlist_paths:
            if not os.path.exists(playlist_path):
                logger.error(f"Playlist not found: {playlist_path}")
                return set()
            
            paths = self._load_m3u_paths(playlist_path)
            normalized_paths = set(self._normalize_path(p) for p in paths)
            all_paths.append(normalized_paths)
            
            logger.info(f"Loaded {len(normalized_paths)} songs from {os.path.basename(playlist_path)}")
        
        # Find intersection of all playlists
        overlap = all_paths[0]
        for path_set in all_paths[1:]:
            overlap = overlap.intersection(path_set)
        
        logger.info(f"Found {len(overlap)} overlapping songs")
        return overlap
    
    def find_unique_to_first(self, playlist_paths: List[str]) -> Set[str]:
        """
        Find songs that appear only in the first playlist but not in any others.
        
        Args:
            playlist_paths (list): List of playlist file paths
            
        Returns:
            set: Set of file paths that appear only in the first playlist
        """
        if len(playlist_paths) < 2:
            logger.error("Need at least 2 playlists to find unique songs")
            return set()
        
        # Load all playlists and normalize paths
        all_paths = []
        for playlist_path in playlist_paths:
            if not os.path.exists(playlist_path):
                logger.error(f"Playlist not found: {playlist_path}")
                return set()
            
            paths = self._load_m3u_paths(playlist_path)
            normalized_paths = set(self._normalize_path(p) for p in paths)
            all_paths.append(normalized_paths)
            
            logger.info(f"Loaded {len(normalized_paths)} songs from {os.path.basename(playlist_path)}")
        
        # Find songs only in first playlist
        unique = all_paths[0]
        for path_set in all_paths[1:]:
            unique = unique - path_set
        
        logger.info(f"Found {len(unique)} songs unique to {os.path.basename(playlist_paths[0])}")
        return unique
    
    def find_non_overlapping(self, playlist_paths: List[str]) -> Set[str]:
        """
        Find songs that don't overlap (appear in only one playlist, not in all).
        
        Args:
            playlist_paths (list): List of playlist file paths
            
        Returns:
            set: Set of file paths that appear in at least one playlist but not all
        """
        if len(playlist_paths) < 2:
            logger.error("Need at least 2 playlists to find non-overlapping songs")
            return set()
        
        # Load all playlists and normalize paths
        all_paths = []
        for playlist_path in playlist_paths:
            if not os.path.exists(playlist_path):
                logger.error(f"Playlist not found: {playlist_path}")
                return set()
            
            paths = self._load_m3u_paths(playlist_path)
            normalized_paths = set(self._normalize_path(p) for p in paths)
            all_paths.append(normalized_paths)
            
            logger.info(f"Loaded {len(normalized_paths)} songs from {os.path.basename(playlist_path)}")
        
        # Find union of all playlists
        all_songs = set()
        for path_set in all_paths:
            all_songs = all_songs.union(path_set)
        
        # Find intersection (overlap)
        overlap = all_paths[0]
        for path_set in all_paths[1:]:
            overlap = overlap.intersection(path_set)
        
        # Non-overlapping = all songs minus overlapping songs
        non_overlapping = all_songs - overlap
        
        logger.info(f"Found {len(non_overlapping)} non-overlapping songs")
        return non_overlapping
    
    def create_overlap_playlist(self, playlist_paths: List[str], output_path: str, 
                               use_relative_paths: bool = True, mode: str = 'overlap') -> bool:
        """
        Create a new playlist containing overlapping or non-overlapping songs.
        
        Args:
            playlist_paths (list): List of playlist file paths to compare
            output_path (str): Path for the output playlist file
            use_relative_paths (bool): Whether to use relative paths in output
            mode (str): 'overlap', 'unique-first', or 'non-overlapping'
            
        Returns:
            bool: True if successful, False otherwise
        """
        # Find songs based on mode
        if mode == 'overlap':
            result_songs = self.find_overlap(playlist_paths)
            mode_description = "overlapping songs"
        elif mode == 'unique-first':
            result_songs = self.find_unique_to_first(playlist_paths)
            mode_description = f"songs unique to {os.path.basename(playlist_paths[0])}"
        elif mode == 'non-overlapping':
            result_songs = self.find_non_overlapping(playlist_paths)
            mode_description = "non-overlapping songs"
        else:
            logger.error(f"Invalid mode: {mode}")
            return False
        
        if not result_songs:
            logger.warning(f"No {mode_description} found between playlists")
            return False
        
        # Sort paths for consistent output
        sorted_songs = sorted(result_songs)
        
        # Determine output directory for relative path calculation
        output_dir = os.path.dirname(os.path.abspath(output_path))
        
        # Create output directory if it doesn't exist
        os.makedirs(output_dir, exist_ok=True)
        
        # Write the playlist
        try:
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write("#EXTM3U\n")
                f.write(f"# Playlist {mode_description} from {len(playlist_paths)} playlists\n")
                f.write(f"# Contains {len(sorted_songs)} songs\n")
                
                for file_path in sorted_songs:
                    # Convert to relative path if requested
                    if use_relative_paths:
                        try:
                            rel_path = os.path.relpath(file_path, output_dir)
                            f.write(f"{rel_path}\n")
                        except ValueError:
                            # Can't create relative path (different drives on Windows)
                            f.write(f"{file_path}\n")
                    else:
                        f.write(f"{file_path}\n")
            
            logger.info(f"Created playlist: {output_path}")
            logger.info(f"  Contains {len(sorted_songs)} songs ({mode_description})")
            return True
            
        except Exception as e:
            logger.error(f"Error creating playlist: {str(e)}")
            return False
    
    def display_overlap_info(self, playlist_paths: List[str], mode: str = 'overlap') -> None:
        """
        Display information about songs without creating a playlist.
        
        Args:
            playlist_paths (list): List of playlist file paths to compare
            mode (str): 'overlap', 'unique-first', or 'non-overlapping'
        """
        # Find songs based on mode
        if mode == 'overlap':
            result_songs = self.find_overlap(playlist_paths)
            mode_title = "Overlapping Songs"
            mode_description = "songs that appear in ALL playlists"
        elif mode == 'unique-first':
            result_songs = self.find_unique_to_first(playlist_paths)
            mode_title = f"Songs Unique to {os.path.basename(playlist_paths[0])}"
            mode_description = f"songs ONLY in {os.path.basename(playlist_paths[0])}"
        elif mode == 'non-overlapping':
            result_songs = self.find_non_overlapping(playlist_paths)
            mode_title = "Non-Overlapping Songs"
            mode_description = "songs that DON'T appear in all playlists"
        else:
            logger.error(f"Invalid mode: {mode}")
            return
        
        if not result_songs:
            print(f"\nNo {mode_description} found between the playlists.")
            return
        
        # Sort paths for display
        sorted_songs = sorted(result_songs)
        
        print(f"\n{'='*70}")
        print(f"Playlist Analysis: {mode_title}")
        print(f"{'='*70}")
        print(f"Playlists compared: {len(playlist_paths)}")
        for i, path in enumerate(playlist_paths, 1):
            print(f"  {i}. {os.path.basename(path)}")
        print(f"\nFound {len(sorted_songs)} {mode_description}")
        print(f"{'='*70}")
        
        # Display first 20 songs
        display_count = min(20, len(sorted_songs))
        print(f"\nFirst {display_count} songs:")
        for i, file_path in enumerate(sorted_songs[:display_count], 1):
            print(f"  {i}. {os.path.basename(file_path)}")
        
        if len(sorted_songs) > display_count:
            print(f"\n... and {len(sorted_songs) - display_count} more")
        
        print(f"\n{'='*70}")


def parse_arguments():
    """
    Parse command line arguments.
    
    Returns:
        argparse.Namespace: Parsed arguments
    """
    parser = argparse.ArgumentParser(
        description="Find overlapping songs between playlists",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Find overlap between 2 playlists and create a new playlist
  python playlist_overlap.py playlist1.m3u playlist2.m3u -o overlap.m3u
  
  # Find songs ONLY in first playlist (not in second)
  python playlist_overlap.py playlist1.m3u playlist2.m3u -o unique.m3u --unique-first
  
  # Find songs that are NOT in all playlists (from both/all playlists)
  python playlist_overlap.py playlist1.m3u playlist2.m3u -o non_overlap.m3u --non-overlapping
  
  # Find overlap between 3 playlists
  python playlist_overlap.py playlist1.m3u playlist2.m3u playlist3.m3u -o overlap.m3u
  
  # Show overlap information without creating a playlist
  python playlist_overlap.py playlist1.m3u playlist2.m3u --info
  
  # Show unique songs with info mode
  python playlist_overlap.py playlist1.m3u playlist2.m3u --info --unique-first
  
  # Use absolute paths in output playlist
  python playlist_overlap.py playlist1.m3u playlist2.m3u -o overlap.m3u --absolute-paths
        """
    )
    
    parser.add_argument(
        'playlists',
        nargs='+',
        help='Playlist files to compare (minimum 2)'
    )
    
    parser.add_argument(
        '-o', '--output',
        help='Output playlist file for overlapping songs'
    )
    
    parser.add_argument(
        '--info',
        action='store_true',
        help='Display overlap information without creating a playlist'
    )
    
    parser.add_argument(
        '--absolute-paths',
        action='store_true',
        help='Use absolute paths in output playlist (default: relative paths)'
    )
    
    parser.add_argument(
        '--unique-first',
        action='store_true',
        help='Find songs ONLY in the first playlist (not in any others)'
    )
    
    parser.add_argument(
        '--non-overlapping',
        action='store_true',
        help='Find songs that are NOT in all playlists (opposite of overlap)'
    )
    
    parser.add_argument(
        '--logging',
        choices=['low', 'high'],
        default='low',
        help='Logging level: low (default) or high (verbose)'
    )
    
    return parser.parse_args()


def main():
    """Main entry point for the playlist overlap finder."""
    args = parse_arguments()
    
    # Set logging level
    if args.logging == 'high':
        logger.setLevel(logging.DEBUG)
    
    # Validate input
    if len(args.playlists) < 2:
        logger.error("Need at least 2 playlists to find overlap")
        sys.exit(1)
    
    # Validate playlist files exist
    for playlist_path in args.playlists:
        if not os.path.exists(playlist_path):
            logger.error(f"Playlist not found: {playlist_path}")
            sys.exit(1)
        if not playlist_path.lower().endswith('.m3u'):
            logger.warning(f"File may not be a valid M3U playlist: {playlist_path}")
    
    # Create finder
    finder = PlaylistOverlapFinder()
    
    # Determine mode
    mode = 'overlap'  # default
    if args.unique_first:
        mode = 'unique-first'
    elif args.non_overlapping:
        mode = 'non-overlapping'
    
    # Check for conflicting flags
    if args.unique_first and args.non_overlapping:
        logger.error("Cannot use both --unique-first and --non-overlapping at the same time")
        sys.exit(1)
    
    # Display info mode
    if args.info:
        finder.display_overlap_info(args.playlists, mode=mode)
        return
    
    # Create overlap playlist mode
    if not args.output:
        logger.error("Output file required (use -o/--output or --info to just display)")
        sys.exit(1)
    
    # Create the playlist
    success = finder.create_overlap_playlist(
        args.playlists,
        args.output,
        use_relative_paths=not args.absolute_paths,
        mode=mode
    )
    
    if success:
        print(f"\nSuccessfully created playlist: {args.output}")
    else:
        logger.error("Failed to create playlist")
        sys.exit(1)


if __name__ == "__main__":
    main()
