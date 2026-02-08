#!/usr/bin/env python3
import os
import sys
import argparse
from pathlib import Path

class PlaylistFixer:
    """Fix broken paths in M3U playlists."""
    
    def __init__(self, playlist_path, output_path=None, remove_missing=False):
        """Initialize PlaylistFixer."""
        self.playlist_path = playlist_path
        self.output_path = output_path or playlist_path
        self.remove_missing = remove_missing
    
    def fix_playlist(self):
        """Fix broken paths in the playlist."""
        if not os.path.exists(self.playlist_path):
            print(f"Error: Playlist not found: {self.playlist_path}")
            return False
        
        playlist_dir = Path(self.playlist_path).parent
        lines = []
        fixed_count = 0
        removed_count = 0
        
        with open(self.playlist_path, 'r', encoding='utf-8') as f:
            for line in f:
                original_line = line
                line = line.strip()
                
                # Keep comments and empty lines
                if not line or line.startswith('#'):
                    lines.append(original_line)
                    continue
                
                # Process file path
                file_path = line
                
                # Convert to absolute
                if not os.path.isabs(file_path):
                    file_path = os.path.abspath(os.path.join(playlist_dir, file_path))
                
                # Check if exists
                if os.path.exists(file_path):
                    # Convert back to relative
                    try:
                        rel_path = os.path.relpath(file_path, playlist_dir)
                        lines.append(f"{rel_path}\n")
                    except:
                        lines.append(f"{file_path}\n")
                else:
                    if self.remove_missing:
                        removed_count += 1
                        print(f"Removing missing: {file_path}")
                    else:
                        lines.append(original_line)
                        print(f"Missing: {file_path}")
                    fixed_count += 1
        
        # Write fixed playlist
        with open(self.output_path, 'w', encoding='utf-8') as f:
            f.writelines(lines)
        
        print(f"\nFixed playlist saved to: {self.output_path}")
        print(f"  Fixed/checked: {fixed_count}")
        if self.remove_missing:
            print(f"  Removed: {removed_count}")
        
        return True

def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description='Fix broken M3U playlist paths')
    parser.add_argument('playlist', help='M3U playlist file to fix')
    parser.add_argument('-o', '--output', help='Output playlist file (default: overwrite input)')
    parser.add_argument('--remove-missing', action='store_true',
                       help='Remove missing files from playlist')
    
    args = parser.parse_args()
    
    fixer = PlaylistFixer(args.playlist, args.output, args.remove_missing)
    return 0 if fixer.fix_playlist() else 1

if __name__ == '__main__':
    sys.exit(main())
