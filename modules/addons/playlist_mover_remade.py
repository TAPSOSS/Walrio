#!/usr/bin/env python3
import os
import sys
import argparse
import shutil
from pathlib import Path

class PlaylistMover:
    """Move M3U playlist and update file paths."""
    
    def __init__(self, playlist_path, dest_dir, copy_files=False):
        """Initialize PlaylistMover."""
        self.playlist_path = playlist_path
        self.dest_dir = dest_dir
        self.copy_files = copy_files
    
    def move_playlist(self):
        """Move playlist and optionally copy/move audio files."""
        if not os.path.exists(self.playlist_path):
            print(f"Error: Playlist not found: {self.playlist_path}")
            return False
        
        os.makedirs(self.dest_dir, exist_ok=True)
        
        # Determine new playlist path
        playlist_name = Path(self.playlist_path).name
        new_playlist_path = os.path.join(self.dest_dir, playlist_name)
        
        # Load current playlist
        playlist_dir = Path(self.playlist_path).parent
        lines = []
        
        with open(self.playlist_path, 'r', encoding='utf-8') as f:
            for line in f:
                original_line = line
                line = line.strip()
                
                if not line or line.startswith('#'):
                    lines.append(original_line)
                    continue
                
                # Get absolute path
                file_path = line
                if not os.path.isabs(file_path):
                    file_path = os.path.abspath(os.path.join(playlist_dir, file_path))
                
                if not os.path.exists(file_path):
                    print(f"Warning: File not found: {file_path}")
                    lines.append(original_line)
                    continue
                
                if self.copy_files:
                    # Copy file to destination
                    file_name = Path(file_path).name
                    new_file_path = os.path.join(self.dest_dir, file_name)
                    shutil.copy2(file_path, new_file_path)
                    print(f"Copied: {file_name}")
                    lines.append(f"{file_name}\n")
                else:
                    # Update path to be relative to new location
                    try:
                        rel_path = os.path.relpath(file_path, self.dest_dir)
                        lines.append(f"{rel_path}\n")
                    except:
                        lines.append(f"{file_path}\n")
        
        # Write new playlist
        with open(new_playlist_path, 'w', encoding='utf-8') as f:
            f.writelines(lines)
        
        print(f"\nPlaylist moved to: {new_playlist_path}")
        return True

def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description='Move M3U playlist to new location')
    parser.add_argument('playlist', help='M3U playlist file')
    parser.add_argument('destination', help='Destination directory')
    parser.add_argument('--copy-files', action='store_true',
                       help='Copy audio files along with playlist')
    
    args = parser.parse_args()
    
    mover = PlaylistMover(args.playlist, args.destination, args.copy_files)
    return 0 if mover.move_playlist() else 1

if __name__ == '__main__':
    sys.exit(main())
