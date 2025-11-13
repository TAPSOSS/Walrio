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
                
                # Load playlist
                logger.debug(f"Loading playlist: {playlist_path}")
                playlist_data = playlist_module.load_m3u_playlist(playlist_path)
                
                if not playlist_data:
                    logger.warning(f"Could not load playlist: {playlist_path}")
                    continue
                
                # Update paths in playlist
                changes_made = False
                changes_count = 0
                
                for idx, track in enumerate(playlist_data, 1):
                    old_url = os.path.abspath(track.get('url', ''))
                    
                    if old_url in path_mapping:
                        new_url = path_mapping[old_url]
                        track['url'] = new_url
                        changes_made = True
                        changes_count += 1
                        
                        # Log the change with track info
                        track_title = track.get('title', 'Unknown')
                        track_artist = track.get('artist', 'Unknown')
                        logger.info(f"  Track #{idx}: {track_artist} - {track_title}")
                        logger.info(f"    Old: {old_url}")
                        logger.info(f"    New: {new_url}")
                
                # Save playlist if changes were made
                if changes_made:
                    if self.dry_run:
                        logger.info(f"\n[DRY RUN] Would update {changes_count} track(s) in playlist: {playlist_name}")
                    else:
                        playlist_module.create_m3u_playlist(
                            playlist_data,
                            playlist_path,
                            use_absolute_paths=True,  # Use absolute paths for reliability
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
