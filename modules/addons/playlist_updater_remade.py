#!/usr/bin/env python3
"""
Playlist Updater - Updates M3U playlists after files have been moved/renamed
"""

import argparse
from pathlib import Path
import sys


class PlaylistUpdater:
    """Updates M3U playlist paths after files have been moved"""
    
    def __init__(self, playlist_path: Path):
        self.playlist_path = playlist_path
        self.entries = []
        
    def load(self) -> None:
        """Load playlist entries"""
        if not self.playlist_path.exists():
            raise FileNotFoundError(f"Playlist not found: {self.playlist_path}")
            
        with open(self.playlist_path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.rstrip('\n\r')
                if line and not line.startswith('#'):
                    self.entries.append(line)
    
    def update_paths(self, old_dir: Path, new_dir: Path, make_relative: bool = False) -> int:
        """
        Update all paths from old directory to new directory
        
        Args:
            old_dir: Old directory path
            new_dir: New directory path
            make_relative: Convert paths to relative format
            
        Returns:
            Number of paths updated
        """
        old_dir = old_dir.resolve()
        new_dir = new_dir.resolve()
        updated_count = 0
        
        new_entries = []
        for entry in self.entries:
            entry_path = Path(entry)
            
            # Make absolute if relative
            if not entry_path.is_absolute():
                entry_path = (self.playlist_path.parent / entry_path).resolve()
            
            # Check if entry is under old_dir
            try:
                rel = entry_path.relative_to(old_dir)
                # Update to new directory
                new_path = new_dir / rel
                
                if make_relative:
                    # Make relative to playlist location
                    try:
                        new_path = new_path.relative_to(self.playlist_path.parent)
                    except ValueError:
                        pass  # Keep absolute if can't make relative
                
                new_entries.append(str(new_path))
                updated_count += 1
            except ValueError:
                # Not under old_dir, keep as is
                new_entries.append(entry)
        
        self.entries = new_entries
        return updated_count
    
    def save(self, output_path: Path = None) -> None:
        """
        Save updated playlist
        
        Args:
            output_path: Output path (defaults to input path)
        """
        output_path = output_path or self.playlist_path
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(output_path, 'w', encoding='utf-8') as f:
            for entry in self.entries:
                f.write(f"{entry}\n")


def update_playlist(playlist_path: Path, old_dir: Path, new_dir: Path, 
                    output_path: Path = None, make_relative: bool = False) -> int:
    """
    Update playlist paths after directory move
    
    Args:
        playlist_path: Path to M3U playlist
        old_dir: Old directory path
        new_dir: New directory path
        output_path: Output path (defaults to input)
        make_relative: Convert to relative paths
        
    Returns:
        Number of paths updated
    """
    updater = PlaylistUpdater(playlist_path)
    updater.load()
    count = updater.update_paths(old_dir, new_dir, make_relative)
    updater.save(output_path)
    return count


def main():
    parser = argparse.ArgumentParser(
        description='Update M3U playlist paths after files have been moved'
    )
    parser.add_argument('playlist', type=Path, help='M3U playlist file')
    parser.add_argument('old_dir', type=Path, help='Old directory path')
    parser.add_argument('new_dir', type=Path, help='New directory path')
    parser.add_argument('-o', '--output', type=Path, help='Output playlist (default: overwrite input)')
    parser.add_argument('-r', '--relative', action='store_true', help='Convert paths to relative format')
    
    args = parser.parse_args()
    
    try:
        count = update_playlist(
            args.playlist,
            args.old_dir,
            args.new_dir,
            args.output,
            args.relative
        )
        
        output_name = args.output or args.playlist
        print(f"Updated {count} paths in {output_name}")
        
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    
    return 0


if __name__ == '__main__':
    sys.exit(main())
