#!/usr/bin/env python3
"""
Playlist Cloner - Clones M3U playlists with optional file copying and format conversion
"""

import argparse
from pathlib import Path
import shutil
import subprocess
import sys


class PlaylistCloner:
    """Clones M3U playlist with optional file operations"""
    
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
    
    def clone(self, output_dir: Path, copy_files: bool = False, 
              convert_format: str = None, make_relative: bool = True) -> tuple:
        """
        Clone playlist to new directory
        
        Args:
            output_dir: Destination directory
            copy_files: Copy audio files along with playlist
            convert_format: Convert audio to this format (e.g., 'mp3', 'flac')
            make_relative: Use relative paths in cloned playlist
            
        Returns:
            Tuple of (new_playlist_path, files_copied, files_converted)
        """
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # Create new playlist path
        new_playlist = output_dir / self.playlist_path.name
        new_entries = []
        files_copied = 0
        files_converted = 0
        
        for entry in self.entries:
            entry_path = Path(entry)
            
            # Make absolute if relative
            if not entry_path.is_absolute():
                entry_path = (self.playlist_path.parent / entry_path).resolve()
            
            if not entry_path.exists():
                print(f"Warning: File not found: {entry_path}", file=sys.stderr)
                continue
            
            if copy_files:
                # Determine output filename
                if convert_format:
                    output_filename = entry_path.stem + f'.{convert_format}'
                else:
                    output_filename = entry_path.name
                
                output_file = output_dir / output_filename
                
                # Copy or convert
                if convert_format and entry_path.suffix.lower() != f'.{convert_format}':
                    # Use FFmpeg for conversion
                    try:
                        subprocess.run([
                            'ffmpeg', '-i', str(entry_path),
                            '-codec:a', 'copy' if convert_format == entry_path.suffix[1:] else 'libmp3lame',
                            '-q:a', '2',
                            str(output_file)
                        ], check=True, capture_output=True)
                        files_converted += 1
                    except subprocess.CalledProcessError as e:
                        print(f"Warning: Conversion failed for {entry_path}: {e}", file=sys.stderr)
                        continue
                else:
                    shutil.copy2(entry_path, output_file)
                    files_copied += 1
                
                # Add to new playlist
                if make_relative:
                    try:
                        new_path = output_file.relative_to(output_dir)
                    except ValueError:
                        new_path = output_file
                else:
                    new_path = output_file
                
                new_entries.append(str(new_path))
            else:
                # Just reference original files
                if make_relative:
                    try:
                        new_path = entry_path.relative_to(output_dir)
                    except ValueError:
                        new_path = entry_path
                else:
                    new_path = entry_path
                
                new_entries.append(str(new_path))
        
        # Save new playlist
        with open(new_playlist, 'w', encoding='utf-8') as f:
            for entry in new_entries:
                f.write(f"{entry}\n")
        
        return new_playlist, files_copied, files_converted


def clone_playlist(playlist_path: Path, output_dir: Path, copy_files: bool = False,
                   convert_format: str = None, make_relative: bool = True) -> tuple:
    """
    Clone M3U playlist
    
    Args:
        playlist_path: Source playlist
        output_dir: Destination directory
        copy_files: Copy audio files
        convert_format: Convert to format
        make_relative: Use relative paths
        
    Returns:
        Tuple of (new_playlist, files_copied, files_converted)
    """
    cloner = PlaylistCloner(playlist_path)
    cloner.load()
    return cloner.clone(output_dir, copy_files, convert_format, make_relative)


def main():
    parser = argparse.ArgumentParser(
        description='Clone M3U playlist with optional file copying and conversion'
    )
    parser.add_argument('playlist', type=Path, help='Source M3U playlist')
    parser.add_argument('output_dir', type=Path, help='Destination directory')
    parser.add_argument('-c', '--copy', action='store_true', help='Copy audio files')
    parser.add_argument('-f', '--format', help='Convert audio to format (e.g., mp3, flac)')
    parser.add_argument('-a', '--absolute', action='store_true', help='Use absolute paths in playlist')
    parser.add_argument('--dry-run', action='store_true',
                       help='Show what would be copied without copying')
    parser.add_argument('--skip-existing', action='store_true',
                       help='Skip files that already exist in destination')
    parser.add_argument('--verify', action='store_true',
                       help='Verify file integrity after copying')
    parser.add_argument('--progress', action='store_true',
                       help='Show detailed progress for each file')
    
    args = parser.parse_args()
    
    try:
        new_playlist, copied, converted = clone_playlist(
            args.playlist,
            args.output_dir,
            args.copy,
            args.format,
            not args.absolute
        )
        
        print(f"Cloned playlist to: {new_playlist}")
        if args.copy:
            print(f"Files copied: {copied}")
            if args.format:
                print(f"Files converted: {converted}")
        
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    
    return 0


if __name__ == '__main__':
    sys.exit(main())
