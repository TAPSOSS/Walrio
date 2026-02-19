#!/usr/bin/env python3
"""Simplified script to clone playlists and files onto a Opus player."""

import sys
import argparse
import subprocess
from pathlib import Path


def get_walrio_path():
    """Get path to walrio.py unified interface.
    
    Returns:
        str: Path to walrio.py
    """
    current_dir = Path(__file__).parent
    walrio_path = current_dir.parent / "walrio.py"
    
    if not walrio_path.exists():
        raise FileNotFoundError(f"Could not find walrio.py at {walrio_path}")
    
    return str(walrio_path)


def sync_to_player(playlist_dirs, output_dir):
    """Sync playlists to Opus player with format conversion.
    
    Converts audio to 192kbps Opus and resizes album art to 600x600 JPG.
    
    Args:
        playlist_dirs: List of playlist directory paths
        output_dir: Output directory (Opus player location)
        
    Returns:
        int: Exit code (0 for success, 1 for failure)
    """
    walrio_path = get_walrio_path()
    
    # Build command for playlist_mover with conversion settings
    cmd = [
        sys.executable, walrio_path, 'playlist_mover',
        '--output-dir', str(output_dir),
        '--format', 'opus',
        '--bitrate', '192k',
        '--album-art-size', '600x600',
        '--album-art-format', 'jpg'
    ]
    
    # Add all playlist directories
    for playlist_dir in playlist_dirs:
        cmd.append(str(playlist_dir))
    
    print(f"Syncing playlists to Opus player: {output_dir}")
    print(f"Format: Opus 192kbps, Album art: 600x600 JPG")
    print("-" * 60)
    
    try:
        result = subprocess.run(cmd, check=True)
        print("-" * 60)
        print("Sync completed successfully!")
        return 0
    except subprocess.CalledProcessError as e:
        print("-" * 60)
        print(f"Sync failed with exit code {e.returncode}")
        return 1


def main():
    """Main entry point for Opus player sync tool."""
    parser = argparse.ArgumentParser(
        description='Sync playlists to Opus player with 192kbps Opus conversion',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Converts audio files to 192kbps Opus and resizes album art to 600x600 JPG
while copying playlists and their files to the Opus player.

Examples:
  # Sync single playlist directory
  walrio opusplayer_sync /path/to/playlists /media/opusplayer

  # Sync multiple playlist directories
  walrio opusplayer_sync /path/to/playlists1 /path/to/playlists2 /media/opusplayer
"""
    )
    parser.add_argument(
        'playlist_dirs',
        nargs='+',
        type=Path,
        help='Playlist directory(ies) to sync. Last argument is the output directory (Opus player location).'
    )
    
    args = parser.parse_args()
    
    # Last argument is output directory, all others are playlist directories
    if len(args.playlist_dirs) < 2:
        print("Error: Need at least one playlist directory and one output directory", file=sys.stderr)
        return 1
    
    playlist_dirs = args.playlist_dirs[:-1]
    output_dir = args.playlist_dirs[-1]
    
    # Validate playlist directories
    for playlist_dir in playlist_dirs:
        if not playlist_dir.exists():
            print(f"Error: Playlist directory does not exist: {playlist_dir}", file=sys.stderr)
            return 1
        if not playlist_dir.is_dir():
            print(f"Error: Not a directory: {playlist_dir}", file=sys.stderr)
            return 1
    
    # Create output directory if it doesn't exist
    if not output_dir.exists():
        print(f"Creating output directory: {output_dir}")
        output_dir.mkdir(parents=True, exist_ok=True)
    
    try:
        return sync_to_player(playlist_dirs, output_dir)
    except KeyboardInterrupt:
        print("\n\nSync interrupted by user", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
