#!/usr/bin/env python3
import os
import sys
import argparse
from pathlib import Path
from collections import defaultdict

class PlaylistCaseConflicts:
    """Detect case-sensitive filename conflicts in playlists."""
    
    def __init__(self, playlist_path):
        """Initialize conflict checker."""
        self.playlist_path = playlist_path
    
    def check_conflicts(self):
        """Check for case conflicts."""
        if not os.path.exists(self.playlist_path):
            print(f"Error: Playlist not found: {self.playlist_path}")
            return False
        
        # Track filenames (lowercased) -> actual paths
        files_by_lower = defaultdict(list)
        playlist_dir = Path(self.playlist_path).parent
        
        with open(self.playlist_path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#'):
                    # Get absolute path
                    if not os.path.isabs(line):
                        line = os.path.abspath(os.path.join(playlist_dir, line))
                    
                    # Group by lowercase
                    lower_path = line.lower()
                    files_by_lower[lower_path].append(line)
        
        # Find conflicts
        conflicts = {k: v for k, v in files_by_lower.items() if len(v) > 1}
        
        if conflicts:
            print(f"Found {len(conflicts)} case conflicts:\n")
            for lower_path, paths in conflicts.items():
                print(f"Conflict group ({len(paths)} files):")
                for path in paths:
                    exists = "✓" if os.path.exists(path) else "✗"
                    print(f"  {exists} {path}")
                print()
        else:
            print("No case conflicts found.")
        
        return True

def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description='Detect case-sensitive filename conflicts in M3U playlists'
    )
    parser.add_argument('playlist', help='M3U playlist file to check')
    
    args = parser.parse_args()
    
    checker = PlaylistCaseConflicts(args.playlist)
    return 0 if checker.check_conflicts() else 1

if __name__ == '__main__':
    sys.exit(main())
