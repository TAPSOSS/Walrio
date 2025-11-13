#!/usr/bin/env python3
"""
Playlist Updater
Copyright (c) 2025 TAPS OSS
Project: https://github.com/TAPSOSS/Walrio
Licensed under the BSD-3-Clause License (see LICENSE file for details)

A centralized utility for updating M3U playlist files when audio file paths change.
Provides detailed logging and can be used by any module that modifies file paths.
"""

import os
import sys
import logging
from pathlib import Path
from typing import List, Dict, Optional

# Add parent directory to path for module imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from core import playlist as playlist_module

# Configure logging
logger = logging.getLogger('PlaylistUpdater')


class PlaylistUpdater:
    """
    Centralized utility for updating playlists when file paths change.
    Provides detailed logging of all changes made to playlists.
    """
    
    def __init__(self, playlist_paths: List[str], dry_run: bool = False):
        """
        Initialize the PlaylistUpdater.
        
        Args:
            playlist_paths (List[str]): List of playlist file/directory paths to update
            dry_run (bool): If True, show what would be updated without saving
        """
        self.dry_run = dry_run
        self.playlists_to_update = []
        self.updated_count = 0
        
        # Load playlists from provided paths
        self._load_playlists(playlist_paths)
    
    @staticmethod
    def _load_m3u_paths_only(playlist_path: str) -> List[Dict[str, str]]:
        """
        Load only the file paths from an M3U playlist without extracting metadata.
        This is much faster than loading full metadata for all tracks.
        
        Args:
            playlist_path (str): Path to the M3U playlist file
            
        Returns:
            List[Dict[str, str]]: List of dicts with 'url', 'artist', 'title' from M3U tags
        """
        tracks = []
        try:
            with open(playlist_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()
            
            current_info = {}
            for line in lines:
                line = line.strip()
                
                # Skip empty lines and comments (except EXTINF)
                if not line or (line.startswith('#') and not line.startswith('#EXTINF')):
                    continue
                
                # Parse EXTINF line for artist/title (for logging only)
                if line.startswith('#EXTINF:'):
                    # Store the entire EXTINF line to preserve it exactly
                    current_info['extinf'] = line
                    
                    # Parse artist/title for logging purposes only
                    try:
                        parts = line[8:].split(',', 1)
                        if len(parts) > 1 and ' - ' in parts[1]:
                            artist, title = parts[1].split(' - ', 1)
                            current_info['artist'] = artist.strip()
                            current_info['title'] = title.strip()
                    except (ValueError, IndexError):
                        pass
                else:
                    # This is a file path
                    file_path = line
                    
                    # Store path and EXTINF line (if any) for exact preservation
                    track = {'url': file_path}
                    if 'extinf' in current_info:
                        track['extinf'] = current_info['extinf']
                    # Include artist/title only for logging
                    if 'artist' in current_info:
                        track['artist'] = current_info['artist']
                    if 'title' in current_info:
                        track['title'] = current_info['title']
                    
                    tracks.append(track)
                    current_info = {}
            
            return tracks
        except Exception as e:
            logger.error(f"Error loading playlist {playlist_path}: {str(e)}")
            return []
    
    @staticmethod
    def _save_m3u_playlist(playlist_path: str, tracks: List[Dict[str, str]], playlist_name: str = None):
        """
        Save tracks to an M3U playlist file, preserving original format.
        Only writes EXTINF tags if they were present in the original playlist.
        
        Args:
            playlist_path (str): Path to save the playlist
            tracks (List[Dict[str, str]]): List of track dicts with 'url' and optional 'extinf'
            playlist_name (str): Optional playlist name for header
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
            logger.error(f"Error saving playlist {playlist_path}: {str(e)}")
    
    def _load_playlists(self, playlist_paths: List[str]):
        """
        Load playlist files from the specified paths.
        Supports both individual files and directories.
        
        Args:
            playlist_paths (List[str]): List of paths to load playlists from
        """
        for path in playlist_paths:
            if os.path.isfile(path):
                # Individual playlist file
                if path.lower().endswith('.m3u'):
                    self.playlists_to_update.append(path)
                    logger.debug(f"Added playlist to update: {path}")
                else:
                    logger.warning(f"Skipping non-M3U file: {path}")
            elif os.path.isdir(path):
                # Directory of playlists
                for file in os.listdir(path):
                    if file.lower().endswith('.m3u'):
                        full_path = os.path.join(path, file)
                        self.playlists_to_update.append(full_path)
                        logger.debug(f"Added playlist to update: {full_path}")
            else:
                logger.warning(f"Playlist path does not exist: {path}")
        
        if self.playlists_to_update:
            logger.info(f"Loaded {len(self.playlists_to_update)} playlist(s) for updating")
    
    def update_playlists(self, path_mapping: Dict[str, str]) -> int:
        """
        Update all loaded playlists with new file paths.
        Provides detailed logging for each change made.
        
        Args:
            path_mapping (Dict[str, str]): Dictionary mapping old paths to new paths
            
        Returns:
            int: Number of playlists successfully updated
        """
        if not self.playlists_to_update:
            logger.debug("No playlists to update")
            return 0
        
        if not path_mapping:
            logger.info("No files were moved, skipping playlist updates")
            return 0
        
        logger.info(f"Updating {len(self.playlists_to_update)} playlist(s) with new file paths...")
        logger.info("=" * 80)
        
        self.updated_count = 0
        
        for playlist_path in self.playlists_to_update:
            try:
                playlist_name = os.path.basename(playlist_path)
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
                        playlist_dir = os.path.dirname(playlist_path)
                        old_url = os.path.abspath(os.path.join(playlist_dir, track_url))
                    else:
                        old_url = os.path.abspath(track_url)
                    
                    # Debug: Show first few tracks being checked
                    if idx <= 3:
                        logger.debug(f"  Track #{idx} original: {track_url}")
                        logger.debug(f"  Track #{idx} absolute: {old_url}")
                        logger.debug(f"    Looking for match in path_mapping...")
                    
                    if old_url in path_mapping:
                        new_url_absolute = path_mapping[old_url]
                        
                        # Convert back to relative path if original was relative
                        if not os.path.isabs(track_url):
                            playlist_dir = os.path.dirname(playlist_path)
                            new_url = os.path.relpath(new_url_absolute, playlist_dir)
                        else:
                            new_url = new_url_absolute
                        
                        track['url'] = new_url
                        changes_made = True
                        changes_count += 1
                        
                        # Log the change with track info
                        track_artist = track.get('artist', '')
                        track_title = track.get('title', '')
                        
                        # Format track info for display
                        if track_artist and track_title:
                            track_info = f"{track_artist} - {track_title}"
                        else:
                            track_info = os.path.basename(track_url)
                        
                        logger.info(f"  Track #{idx}: {track_info}")
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
                            playlist_name=os.path.splitext(playlist_name)[0]
                        )
                        logger.info(f"\n✓ Updated {changes_count} track(s) in playlist: {playlist_name}")
                    
                    self.updated_count += 1
                else:
                    logger.info(f"  No changes needed for this playlist")
                    
            except Exception as e:
                logger.error(f"Error updating playlist {playlist_path}: {str(e)}")
        
        logger.info("=" * 80)
        if self.dry_run:
            logger.info(f"[DRY RUN] Would update {self.updated_count} playlist(s)")
        else:
            logger.info(f"Successfully updated {self.updated_count} playlist(s)")
        
        return self.updated_count


def load_playlists_from_paths(playlist_paths: List[str]) -> List[str]:
    """
    Helper function to load playlist file paths from a list of file/directory paths.
    
    Args:
        playlist_paths (List[str]): List of paths (files or directories)
        
    Returns:
        List[str]: List of playlist file paths
    """
    playlists = []
    
    for path in playlist_paths:
        if os.path.isfile(path):
            if path.lower().endswith('.m3u'):
                playlists.append(path)
        elif os.path.isdir(path):
            for file in os.listdir(path):
                if file.lower().endswith('.m3u'):
                    full_path = os.path.join(path, file)
                    playlists.append(full_path)
    
    return playlists
