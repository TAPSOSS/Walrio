#!/usr/bin/env python3
import os
import sys
import argparse
from pathlib import Path

class PlaylistDeleter:
    """Delete all audio files referenced in an M3U playlist."""
    
    def __init__(self, playlist_path, delete_empty_dirs=False, dry_run=False, force=False):
        """Initialize the PlaylistDeleter."""
        self.playlist_path = playlist_path
        self.delete_empty_dirs = delete_empty_dirs
        self.dry_run = dry_run
        self.force = force
    
    def _load_playlist_paths(self):
        """Load file paths from the M3U playlist."""
        if not os.path.exists(self.playlist_path):
            print(f"Error: Playlist not found: {self.playlist_path}")
            return []
        
        paths = []
        playlist_dir = Path(self.playlist_path).parent
        
        with open(self.playlist_path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#'):
                    # Convert relative to absolute path
                    if not os.path.isabs(line):
                        line = os.path.abspath(os.path.join(playlist_dir, line))
                    paths.append(line)
        
        return paths
    
    def _confirm_deletion(self, file_paths):
        """Ask user to confirm deletion."""
        print(f"\nWARNING: This will permanently delete {len(file_paths)} files!")
        print("Files to delete:")
        for path in file_paths[:10]:
            print(f"  {path}")
        if len(file_paths) > 10:
            print(f"  ... and {len(file_paths) - 10} more")
        
        response = input("\nAre you sure you want to continue? (yes/no): ")
        return response.lower() in ['yes', 'y']
    
    def _delete_empty_parent_dirs(self, file_path):
        """Delete empty parent directories after deleting a file."""
        try:
            parent = Path(file_path).parent
            while parent and parent != Path('/'):
                if not any(parent.iterdir()):
                    print(f"  Deleting empty directory: {parent}")
                    parent.rmdir()
                    parent = parent.parent
                else:
                    break
        except:
            pass
    
    def delete_playlist_files(self):
        """Delete all files from the playlist."""
        file_paths = self._load_playlist_paths()
        
        if not file_paths:
            print("No files found in playlist.")
            return (0, 0, 0, 0)
        
        # Check what exists
        existing = [p for p in file_paths if os.path.exists(p)]
        missing = len(file_paths) - len(existing)
        
        if not existing:
            print(f"No files to delete ({missing} already missing).")
            return (len(file_paths), 0, missing, 0)
        
        # Confirm deletion
        if not self.force and not self.dry_run:
            if not self._confirm_deletion(existing):
                print("Operation cancelled.")
                return (len(file_paths), 0, missing, 0)
        
        # Delete files
        deleted = 0
        errors = 0
        
        for file_path in existing:
            try:
                if self.dry_run:
                    print(f"Would delete: {file_path}")
                    deleted += 1
                else:
                    os.remove(file_path)
                    print(f"Deleted: {file_path}")
                    deleted += 1
                    
                    if self.delete_empty_dirs:
                        self._delete_empty_parent_dirs(file_path)
            except Exception as e:
                print(f"Error deleting {file_path}: {e}")
                errors += 1
        
        return (len(file_paths), deleted, missing, errors)

def parse_arguments():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description='Playlist Deleter - Delete all files referenced in a playlist',
        epilog='WARNING: This permanently deletes files!'
    )
    parser.add_argument('playlist', help='M3U playlist file')
    parser.add_argument('--delete-empty-dirs', action='store_true',
                       help='Delete empty parent directories after deleting files')
    parser.add_argument('--dry-run', action='store_true',
                       help='Show what would be deleted without actually deleting')
    parser.add_argument('--force', action='store_true',
                       help='Skip confirmation prompt')
    return parser.parse_args()

def main():
    """Main entry point for the playlist deleter."""
    args = parse_arguments()
    
    deleter = PlaylistDeleter(
        args.playlist,
        delete_empty_dirs=args.delete_empty_dirs,
        dry_run=args.dry_run,
        force=args.force
    )
    
    total, deleted, missing, errors = deleter.delete_playlist_files()
    
    print(f"\nSummary:")
    print(f"  Total files in playlist: {total}")
    print(f"  Files deleted: {deleted}")
    print(f"  Files already missing: {missing}")
    print(f"  Errors: {errors}")
    
    return 0 if errors == 0 else 1

if __name__ == '__main__':
    sys.exit(main())

