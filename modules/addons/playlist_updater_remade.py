#!/usr/bin/env python3
"""
PlaylistUpdater - Shared utility for updating playlists when file paths change
"""

import logging
import os
from pathlib import Path
from typing import Dict, List, Optional

logger = logging.getLogger('PlaylistUpdater')


class PlaylistUpdater:
    """
    Centralized utility for updating playlists when file paths change.
    Preserves EXTINF metadata lines.
    """
    
    def __init__(self, playlist_paths: List[Path], dry_run: bool = False):
        """
        Args:
            playlist_paths: List of playlist file/directory paths to update
            dry_run: If True, show what would be updated without saving
        """
        self.dry_run = dry_run
        self.playlists_to_update = []
        self.updated_count = 0
        
        self._load_playlists(playlist_paths)
    
    @staticmethod
    def _load_m3u_paths_only(playlist_path: Path) -> List[Dict[str, str]]:
        """
        Load file paths from M3U playlist preserving EXTINF lines
        
        Args:
            playlist_path: Path to M3U playlist
            
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
        Save tracks to M3U playlist preserving EXTINF tags
        
        Args:
            playlist_path: Path to save playlist
            tracks: List of track dicts with 'url' and optional 'extinf'
            playlist_name: Optional playlist name for header
        """
        try:
            with open(playlist_path, 'w', encoding='utf-8') as f:
                f.write('#EXTM3U\n')
                
                for track in tracks:
                    url = track.get('url', '')
                    extinf = track.get('extinf', '')
                    
                    # Write EXTINF line if present
                    if extinf:
                        f.write(f'{extinf}\n')
                    
                    f.write(f'{url}\n')
            
            logger.debug(f"Saved playlist: {playlist_path}")
        except Exception as e:
            logger.error(f"Error saving playlist {playlist_path}: {e}")
    
    def _load_playlists(self, playlist_paths: List[Path]):
        """
        Load playlist files from specified paths
        
        Args:
            playlist_paths: List of paths to load playlists from
        """
        for path in playlist_paths:
            path = Path(path)
            
            if path.is_file():
                if path.suffix.lower() == '.m3u':
                    self.playlists_to_update.append(path)
                    logger.debug(f"Added playlist to update: {path}")
                else:
                    logger.warning(f"Skipping non-M3U file: {path}")
            elif path.is_dir():
                for file in path.glob('*.m3u'):
                    self.playlists_to_update.append(file)
                    logger.debug(f"Added playlist to update: {file}")
            else:
                logger.warning(f"Playlist path does not exist: {path}")
        
        if self.playlists_to_update:
            logger.info(f"Loaded {len(self.playlists_to_update)} playlist(s) for updating")
    
    def update_all(self, path_mapping: Dict[str, str]) -> int:
        """
        Update all loaded playlists with new file paths
        
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
        
        self.updated_count = 0
        
        for playlist_path in self.playlists_to_update:
            try:
                playlist_name = playlist_path.name
                logger.info(f"\nProcessing playlist: {playlist_name}")
                
                # Load playlist
                playlist_data = self._load_m3u_paths_only(playlist_path)
                
                if not playlist_data:
                    logger.warning(f"Could not load playlist: {playlist_path}")
                    continue
                
                logger.info(f"  Playlist contains {len(playlist_data)} track(s)")
                
                # Update paths
                changes_made = False
                changes_count = 0
                
                for idx, track in enumerate(playlist_data, 1):
                    track_url = track.get('url', '')
                    
                    # Convert relative paths to absolute
                    if not os.path.isabs(track_url):
                        playlist_dir = playlist_path.parent
                        old_url = str((playlist_dir / track_url).resolve())
                    else:
                        old_url = os.path.abspath(track_url)
                    
                    # Check if this path needs updating
                    if old_url in path_mapping:
                        new_url = path_mapping[old_url]
                        
                        # Convert back to relative path if original was relative
                        if not os.path.isabs(track_url):
                            try:
                                new_url = os.path.relpath(new_url, playlist_path.parent)
                            except ValueError:
                                # Can't make relative (different drives on Windows)
                                pass
                        
                        logger.info(f"  Track #{idx}: {Path(track_url).name}")
                        logger.info(f"    Old: {track_url}")
                        logger.info(f"    New: {new_url}")
                        
                        track['url'] = new_url
                        changes_made = True
                        changes_count += 1
                
                # Save updated playlist
                if changes_made:
                    if self.dry_run:
                        logger.info(f"  [DRY RUN] Would update {changes_count} track(s)")
                    else:
                        self._save_m3u_playlist(playlist_path, playlist_data, playlist_name)
                        logger.info(f"  ✓ Updated {changes_count} track(s)")
                        self.updated_count += 1
                else:
                    logger.info(f"  No changes needed")
            
            except Exception as e:
                logger.error(f"Error updating playlist {playlist_path}: {e}")
        
        if self.updated_count > 0:
            logger.info(f"\n{'[DRY RUN] Would have updated' if self.dry_run else 'Successfully updated'} {self.updated_count} playlist(s)")
        
        return self.updated_count
    
    def update_single_playlist(self, playlist_path: Path, 
                              path_mapping: Dict[str, str]) -> bool:
        """
        Update single playlist with new file paths
        
        Args:
            playlist_path: Playlist to update
            path_mapping: Dictionary mapping old paths to new paths
            
        Returns:
            True if updated successfully
        """
        try:
            # Temporarily set playlists
            original_playlists = self.playlists_to_update
            self.playlists_to_update = [playlist_path]
            
            count = self.update_all(path_mapping)
            
            # Restore original playlists
            self.playlists_to_update = original_playlists
            
            return count > 0
        
        except Exception as e:
            logger.error(f"Error updating playlist {playlist_path}: {e}")
            return False


def main():
    """CLI for testing playlist updating"""
    import argparse
    import json
    
    parser = argparse.ArgumentParser(
        description='Update playlists with new file paths'
    )
    parser.add_argument('playlists', nargs='+', type=Path,
                       help='Playlist file(s) or directory containing playlists')
    parser.add_argument('-m', '--mapping', type=Path, required=True,
                       help='JSON file with path mapping (old -> new)')
    parser.add_argument('--dry-run', action='store_true',
                       help='Preview changes without applying')
    
    args = parser.parse_args()
    
    # Load path mapping
    try:
        with open(args.mapping, 'r') as f:
            path_mapping = json.load(f)
    except Exception as e:
        print(f"Error loading mapping file: {e}")
        return 1
    
    # Update playlists
    try:
        updater = PlaylistUpdater(args.playlists, args.dry_run)
        count = updater.update_all(path_mapping)
        
        if count > 0:
            print(f"\nUpdated {count} playlist(s)")
        else:
            print("\nNo playlists updated")
        
        return 0
    
    except Exception as e:
        print(f"Error: {e}")
        return 1


if __name__ == '__main__':
    import sys
    sys.exit(main())
