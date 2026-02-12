#!/usr/bin/env python3
"""
updates file paths in playlists when the new path is known (unlike fixer which tries to find the new files afterward)
"""

import logging
import os
from pathlib import Path
from typing import Dict, List, Optional, Set
import difflib

logger = logging.getLogger('PlaylistUpdater')

# Pre-compiled audio extensions for efficiency
AUDIO_EXTENSIONS = frozenset({'.mp3', '.flac', '.wav', '.ogg', '.m4a', '.aac', 
                               '.opus', '.wma', '.ape', '.wv'})


class PlaylistUpdater:
    """
    Centralized utility for updating playlists when file paths change.
    Provides detailed logging of all changes made to playlists.
    """
    
    def __init__(self, playlist_paths: List[str], dry_run: bool = False):
        """
        Initialize the PlaylistUpdater.
        
        Args:
            playlist_paths: List of playlist file/directory paths to update
            dry_run: If True, show what would be updated without saving
        """
        self.dry_run = dry_run
        self.playlists_to_update = []
        self.updated_count = 0
        
        # Load playlists from provided paths
        self._load_playlists(playlist_paths)
    
    @staticmethod
    def _load_m3u_paths_only(playlist_path: Path) -> List[Dict[str, str]]:
        """
        Load only the file paths from an M3U playlist without extracting metadata.
        Preserves EXTINF lines exactly as-is for later writing.
        
        Args:
            playlist_path: Path to the M3U playlist file
            
        Returns:
            List of dicts with 'url' and optional 'extinf'
        """
        tracks = []
        try:
            with open(playlist_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()
            
            current_extinf = None
            for line in lines:
                line = line.strip()
                
                # Skip empty lines and non-EXTINF comments
                if not line or (line.startswith('#') and not line.startswith('#EXTINF')):
                    continue
                
                # Store EXTINF line to write back later
                if line.startswith('#EXTINF:'):
                    current_extinf = line
                else:
                    # This is a file path
                    track = {'url': line}
                    if current_extinf:
                        track['extinf'] = current_extinf
                    
                    tracks.append(track)
                    current_extinf = None
            
            return tracks
        except Exception as e:
            logger.error(f"Error loading playlist {playlist_path}: {e}")
            return []
    
    @staticmethod
    def _save_m3u_playlist(playlist_path: Path, tracks: List[Dict[str, str]], 
                          playlist_name: Optional[str] = None):
        """
        Save tracks to an M3U playlist file, preserving original format.
        Only writes EXTINF tags if they were present in the original playlist.
        
        Args:
            playlist_path: Path to save the playlist
            tracks: List of track dicts with 'url' and optional 'extinf'
            playlist_name: Optional playlist name for header
        """
        try:
            with open(playlist_path, 'w', encoding='utf-8') as f:
                f.write('#EXTM3U\n')
                
                for track in tracks:
                    url = track.get('url', '')
                    extinf = track.get('extinf', '')
                    
                    # Write EXTINF line if it was present in the original
                    if extinf:
                        f.write(f'{extinf}\n')
                    
                    f.write(f'{url}\n')
                    
            logger.debug(f"Saved playlist: {playlist_path}")
        except Exception as e:
            logger.error(f"Error saving playlist {playlist_path}: {e}")
    
    def _load_playlists(self, playlist_paths: List[str]):
        """
        Load playlist files from the specified paths.
        Supports both individual files and directories.
        
        Args:
            playlist_paths: List of paths to load playlists from
        """
        for path_str in playlist_paths:
            path = Path(path_str)
            
            if path.is_file():
                # Individual playlist file
                if path.suffix.lower() == '.m3u':
                    self.playlists_to_update.append(path)
                    logger.debug(f"Added playlist to update: {path}")
                else:
                    logger.warning(f"Skipping non-M3U file: {path}")
            elif path.is_dir():
                # Directory of playlists - use glob for efficiency
                for file in path.glob('*.m3u'):
                    self.playlists_to_update.append(file)
                    logger.debug(f"Added playlist to update: {file}")
            else:
                logger.warning(f"Playlist path does not exist: {path}")
        
        if self.playlists_to_update:
            logger.info(f"Loaded {len(self.playlists_to_update)} playlist(s) for updating")
    
    def update_playlists(self, path_mapping: Dict[str, str]) -> int:
        """
        Update all loaded playlists with new file paths.
        Provides detailed logging for each change made.
        
        Args:
            path_mapping: Dictionary mapping old paths to new paths
            
        Returns:
            Number of playlists successfully updated
        """
        if not self.playlists_to_update:
            logger.debug("No playlists to update")
            return 0
        
        if not path_mapping:
            logger.info("No files were moved, skipping playlist updates")
            return 0
        
        logger.info(f"Updating {len(self.playlists_to_update)} playlist(s) with new file paths...")
        logger.info(f"Path mapping contains {len(path_mapping)} entries")
        
        # Debug: Show first few path mappings
        logger.info("Sample path mappings (first 3):")
        for idx, (old, new) in enumerate(list(path_mapping.items())[:3], 1):
            logger.info(f"  Mapping #{idx}:")
            logger.info(f"    Old: {old}")
            logger.info(f"    New: {new}")
        
        logger.info("=" * 80)
        
        self.updated_count = 0
        
        # Convert path_mapping to use normalized paths for faster lookups
        normalized_mapping = {os.path.normpath(k): v for k, v in path_mapping.items()}
        
        for playlist_path in self.playlists_to_update:
            try:
                playlist_name = playlist_path.name
                logger.info(f"\nProcessing playlist: {playlist_name}")
                logger.info("-" * 80)
                
                # Load playlist (paths only, no metadata extraction for speed)
                logger.debug(f"Loading playlist: {playlist_path}")
                playlist_data = self._load_m3u_paths_only(playlist_path)
                
                if not playlist_data:
                    logger.warning(f"Could not load playlist: {playlist_path}")
                    continue
                
                logger.info(f"  Playlist contains {len(playlist_data)} track(s)")
                logger.info(f"  Checking against {len(path_mapping)} path mapping(s)")
                
                # Update paths in playlist
                changes_made = False
                changes_count = 0
                
                for idx, track in enumerate(playlist_data, 1):
                    track_url = track.get('url', '')
                    
                    # Convert relative paths to absolute based on playlist location
                    if not os.path.isabs(track_url):
                        old_url = os.path.normpath((playlist_path.parent / track_url).resolve())
                    else:
                        old_url = os.path.normpath(Path(track_url).resolve())
                    
                    # Debug: Show first few tracks being checked
                    if idx <= 3:
                        logger.info(f"  Track #{idx} original: {track_url}")
                        logger.info(f"  Track #{idx} absolute: {old_url}")
                        logger.info(f"    File exists: {Path(old_url).exists()}")
                        logger.info(f"    In path_mapping: {old_url in normalized_mapping}")
                        if old_url in normalized_mapping:
                            logger.info(f"    Would map to: {normalized_mapping[old_url]}")
                        else:
                            # Show close matches for debugging
                            logger.info(f"    Looking for close matches in path_mapping...")
                            for key in list(normalized_mapping.keys())[:3]:
                                logger.info(f"      Available key: {key}")
                    
                    if old_url in normalized_mapping:
                        new_url_absolute = normalized_mapping[old_url]
                        
                        # Convert back to relative path if original was relative
                        if not os.path.isabs(track_url):
                            try:
                                new_url = os.path.relpath(new_url_absolute, playlist_path.parent)
                            except ValueError:
                                # Can't make relative (different drives on Windows)
                                new_url = new_url_absolute
                        else:
                            new_url = new_url_absolute
                        
                        track['url'] = new_url
                        changes_made = True
                        changes_count += 1
                        
                        # Log the change showing full paths
                        logger.info(f"  Track #{idx} in {playlist_name}:")
                        logger.info(f"    Old: {track_url}")
                        logger.info(f"    New: {new_url}")
                
                # Save playlist if changes were made
                if changes_made:
                    if self.dry_run:
                        logger.info(f"\n[DRY RUN] Would update {changes_count} track(s) in playlist: {playlist_name}")
                    else:
                        # Save using our simple M3U writer (preserves path format)
                        self._save_m3u_playlist(
                            playlist_path,
                            playlist_data,
                            playlist_name=playlist_path.stem
                        )
                        logger.info(f"\n✓ Updated {changes_count} track(s) in playlist: {playlist_name}")
                    
                    self.updated_count += 1
                else:
                    logger.info(f"  No changes needed for this playlist")
                    
            except Exception as e:
                logger.error(f"Error updating playlist {playlist_path}: {e}")
        
        logger.info("=" * 80)
        if self.dry_run:
            logger.info(f"[DRY RUN] Would update {self.updated_count} playlist(s)")
        else:
            logger.info(f"Successfully updated {self.updated_count} playlist(s)")
        
        return self.updated_count


def load_playlists_from_paths(playlist_paths: List[str]) -> List[Path]:
    """
    Helper function to load playlist file paths from a list of file/directory paths.
    
    Args:
        playlist_paths: List of paths (files or directories)
        
    Returns:
        List of playlist Path objects
    """
    playlists = []
    
    for path_str in playlist_paths:
        path = Path(path_str)
        if path.is_file():
            if path.suffix.lower() == '.m3u':
                playlists.append(path)
        elif path.is_dir():
            # Use glob for efficiency
            playlists.extend(path.glob('*.m3u'))
    
    return playlists


def auto_detect_renamed_files(music_dir: str, playlist_paths: List[str], 
                              recursive: bool = False) -> Dict[str, str]:
    """
    Automatically detect renamed files by comparing playlist entries with actual files.
    Attempts to match playlist entries (with problematic characters) to existing files.
    
    Args:
        music_dir: Directory containing music files to scan
        playlist_paths: List of playlist files or directories
        recursive: Whether to scan music directory recursively
        
    Returns:
        Dictionary mapping old paths (from playlists) to new paths (actual files)
    """
    logger.info(f"Scanning music directory: {music_dir}")
    
    music_path = Path(music_dir)
    actual_files = []
    
    # Scan for audio files - use pathlib for efficiency
    if recursive:
        for ext in AUDIO_EXTENSIONS:
            actual_files.extend(music_path.rglob(f'*{ext}'))
    else:
        for ext in AUDIO_EXTENSIONS:
            actual_files.extend(music_path.glob(f'*{ext}'))
    
    # Convert to normalized absolute paths and build basename lookup dict
    actual_files_normalized = [os.path.normpath(f.resolve()) for f in actual_files]
    basename_to_paths = {}
    for filepath in actual_files_normalized:
        basename = os.path.basename(filepath).lower()
        basename_to_paths.setdefault(basename, []).append(filepath)
    
    logger.info(f"Found {len(actual_files_normalized)} audio files in music directory")
    
    # Load all unique paths from playlists
    updater = PlaylistUpdater(playlist_paths, dry_run=True)
    playlist_entries = set()
    
    for playlist_path in updater.playlists_to_update:
        tracks = updater._load_m3u_paths_only(playlist_path)
        
        for track in tracks:
            track_url = track.get('url', '')
            if not os.path.isabs(track_url):
                abs_path = os.path.normpath((playlist_path.parent / track_url).resolve())
            else:
                abs_path = os.path.normpath(Path(track_url).resolve())
            
            # Only add entries that don't exist (likely renamed)
            if not Path(abs_path).exists():
                playlist_entries.add(abs_path)
    
    logger.info(f"Found {len(playlist_entries)} missing entries in playlists (likely renamed)")
    
    # Try to match missing entries to actual files
    path_mapping = {}
    
    for missing_path in playlist_entries:
        # Strategy: Find best match by comparing filenames
        missing_filename = os.path.basename(missing_path)
        missing_filename_lower = missing_filename.lower()
        missing_dir = os.path.dirname(missing_path)
        missing_ext = os.path.splitext(missing_filename)[1].lower()
        
        # Quick check: if basename matches exactly (case-insensitive), use it
        if missing_filename_lower in basename_to_paths:
            candidates = basename_to_paths[missing_filename_lower]
            # If only one match, use it
            if len(candidates) == 1:
                path_mapping[missing_path] = candidates[0]
                logger.info(f"Exact match: {missing_filename} -> {os.path.basename(candidates[0])}")
                continue
            # Multiple matches - prefer same directory
            same_dir = [c for c in candidates if os.path.dirname(c) == missing_dir]
            if same_dir:
                path_mapping[missing_path] = same_dir[0]
                logger.info(f"Exact match (same dir): {missing_filename} -> {os.path.basename(same_dir[0])}")
                continue
        
        best_match = None
        best_ratio = 0
        
        # First, try exact directory match with fuzzy filename match
        # Filter by same directory and extension first for efficiency
        same_dir_candidates = [f for f in actual_files_normalized 
                              if os.path.dirname(f) == missing_dir 
                              and os.path.splitext(f)[1].lower() == missing_ext]
        
        if same_dir_candidates:
            for actual_file in same_dir_candidates:
                actual_filename = os.path.basename(actual_file)
                ratio = difflib.SequenceMatcher(None, missing_filename_lower, 
                                               actual_filename.lower()).ratio()
                if ratio > best_ratio and ratio > 0.7:  # 70% similarity threshold
                    best_ratio = ratio
                    best_match = actual_file
        
        # If no match in same directory, try any file with high similarity and same extension
        if not best_match:
            same_ext_candidates = [f for f in actual_files_normalized 
                                  if os.path.splitext(f)[1].lower() == missing_ext]
            
            for actual_file in same_ext_candidates:
                actual_filename = os.path.basename(actual_file)
                ratio = difflib.SequenceMatcher(None, missing_filename_lower, 
                                               actual_filename.lower()).ratio()
                if ratio > best_ratio and ratio > 0.8:  # Higher threshold for different directory
                    best_ratio = ratio
                    best_match = actual_file
        
        if best_match:
            path_mapping[missing_path] = best_match
            logger.info(f"Matched: {missing_filename} -> {os.path.basename(best_match)} ({best_ratio:.1%} similarity)")
        else:
            logger.warning(f"Could not find match for: {missing_path}")
    
    logger.info(f"Successfully matched {len(path_mapping)} of {len(playlist_entries)} missing entries")
    
    return path_mapping


def main():
    """Main entry point for standalone playlist updater."""
    import argparse
    import json
    import sys
    
    parser = argparse.ArgumentParser(
        description="Playlist Updater - Update M3U playlists with new file paths",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
This tool updates M3U playlist files when audio file paths have changed.

Usage Modes:

1. Manual mapping from JSON file:
   python playlist_updater_remade.py playlists/ --mapping-file mappings.json
   
   JSON format: {"old_path": "new_path", ...}

2. Auto-detect renamed files:
   python playlist_updater_remade.py playlists/ --auto-detect /path/to/music --recursive
   
   Automatically finds renamed files by matching playlist entries to existing files.

3. Interactive mode:
   python playlist_updater_remade.py playlists/
   
   Prompts for each missing file to enter the new path.

Examples:
  # Auto-detect and fix playlists after renaming
  python playlist_updater_remade.py /path/to/playlists --auto-detect /path/to/music --recursive
  
  # Use a mapping file
  python playlist_updater_remade.py playlist.m3u --mapping-file path_mappings.json
  
  # Dry run to preview changes
  python playlist_updater_remade.py playlists/ --auto-detect /music --dry-run
        """
    )
    
    parser.add_argument(
        'playlists',
        nargs='+',
        help='Playlist file(s) or directory containing playlists to update'
    )
    
    parser.add_argument(
        '--auto-detect', '--ad',
        metavar='MUSIC_DIR',
        help='Automatically detect renamed files by scanning this music directory'
    )
    
    parser.add_argument(
        '--mapping-file', '--mf',
        metavar='JSON_FILE',
        help='JSON file containing old->new path mappings'
    )
    
    parser.add_argument(
        '--recursive', '-r',
        action='store_true',
        help='Scan music directory recursively (used with --auto-detect)'
    )
    
    parser.add_argument(
        '--dry-run', '-n',
        action='store_true',
        help='Preview changes without modifying playlists'
    )
    
    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='Enable verbose logging'
    )
    
    args = parser.parse_args()
    
    # Set logging level
    if args.verbose:
        logging.basicConfig(level=logging.DEBUG, format='%(levelname)s: %(message)s')
    else:
        logging.basicConfig(level=logging.INFO, format='%(message)s')
    
    # Validate playlist paths
    for path in args.playlists:
        if not Path(path).exists():
            logger.error(f"Playlist path does not exist: {path}")
            sys.exit(1)
    
    # Determine the path mapping
    path_mapping = {}
    
    if args.mapping_file:
        # Load mapping from JSON file
        logger.info(f"Loading path mappings from: {args.mapping_file}")
        try:
            with open(args.mapping_file, 'r', encoding='utf-8') as f:
                path_mapping = json.load(f)
            logger.info(f"Loaded {len(path_mapping)} path mappings")
        except Exception as e:
            logger.error(f"Failed to load mapping file: {e}")
            sys.exit(1)
    
    elif args.auto_detect:
        # Auto-detect renamed files
        if not Path(args.auto_detect).is_dir():
            logger.error(f"Music directory does not exist: {args.auto_detect}")
            sys.exit(1)
        
        logger.info("Auto-detecting renamed files...")
        logger.info("=" * 80)
        path_mapping = auto_detect_renamed_files(
            args.auto_detect,
            args.playlists,
            recursive=args.recursive
        )
        
        if not path_mapping:
            logger.warning("No renamed files detected. Playlists may already be up to date.")
            sys.exit(0)
    
    else:
        logger.error("Please specify either --mapping-file or --auto-detect")
        parser.print_help()
        sys.exit(1)
    
    # Update playlists
    logger.info("")
    logger.info("=" * 80)
    logger.info("Updating playlists...")
    logger.info("=" * 80)
    
    updater = PlaylistUpdater(args.playlists, dry_run=args.dry_run)
    updated_count = updater.update_playlists(path_mapping)
    
    logger.info("")
    logger.info("=" * 80)
    if args.dry_run:
        logger.info(f"[DRY RUN] Would update {updated_count} playlist(s)")
    else:
        logger.info(f"Successfully updated {updated_count} playlist(s)")
    logger.info("=" * 80)


if __name__ == "__main__":
    main()
