#!/usr/bin/env python3
"""
ReplayGain - Apply ReplayGain tags to audio files for volume normalization
"""

import argparse
from pathlib import Path
import subprocess
import sys


class ReplayGainApplier:
    """Applies ReplayGain using rsgain tool"""
    
    def __init__(self, mode: str = 'auto', preserve_mtimes: bool = True):
        """
        Args:
            mode: 'album' or 'track' or 'auto'
            preserve_mtimes: Preserve file modification times
        """
        self.mode = mode
        self.preserve_mtimes = preserve_mtimes
        self._check_rsgain()
    
    def _check_rsgain(self) -> None:
        """Check if rsgain is available"""
        try:
            subprocess.run(['rsgain', '--version'], capture_output=True, check=True)
        except (subprocess.CalledProcessError, FileNotFoundError):
            raise RuntimeError("rsgain not found. Install with: apt install rsgain (or equivalent)")
    
    def apply_to_files(self, files: list, album_mode: bool = False) -> bool:
        """
        Apply ReplayGain to files
        
        Args:
            files: List of audio file paths
            album_mode: Use album mode (analyze together)
            
        Returns:
            True if successful
        """
        if not files:
            return True
        
        # Convert to strings
        file_paths = [str(f) for f in files]
        
        # Build command
        cmd = ['rsgain', 'easy']
        
        if album_mode:
            cmd.append('-a')  # Album mode
        
        if self.preserve_mtimes:
            cmd.append('-p')  # Preserve mtimes
        
        cmd.extend(file_paths)
        
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            return True
        except subprocess.CalledProcessError as e:
            print(f"rsgain error: {e.stderr}", file=sys.stderr)
            raise RuntimeError(f"ReplayGain failed: {e}")
    
    def apply_to_directory(self, directory: Path, recursive: bool = True) -> dict:
        """
        Apply ReplayGain to directory
        
        Args:
            directory: Directory path
            recursive: Process subdirectories
            
        Returns:
            Dictionary with processing stats
        """
        # Find audio files
        audio_exts = {'.mp3', '.flac', '.ogg', '.opus', '.m4a', '.mp4', '.wv'}
        
        if recursive:
            pattern = '**/*'
        else:
            pattern = '*'
        
        files = []
        for ext in audio_exts:
            files.extend(directory.glob(f'{pattern}{ext}'))
        
        if not files:
            return {'processed': 0, 'errors': 0}
        
        # Group by directory if using album mode
        if self.mode == 'album':
            # Group files by parent directory
            by_dir = {}
            for f in files:
                parent = f.parent
                if parent not in by_dir:
                    by_dir[parent] = []
                by_dir[parent].append(f)
            
            # Process each album directory
            errors = 0
            processed = 0
            for dir_path, dir_files in by_dir.items():
                try:
                    self.apply_to_files(dir_files, album_mode=True)
                    processed += len(dir_files)
                except Exception as e:
                    print(f"Error processing {dir_path}: {e}", file=sys.stderr)
                    errors += len(dir_files)
            
            return {'processed': processed, 'errors': errors}
        
        elif self.mode == 'track':
            # Process each file individually
            errors = 0
            processed = 0
            for f in files:
                try:
                    self.apply_to_files([f], album_mode=False)
                    processed += 1
                except Exception as e:
                    print(f"Error processing {f}: {e}", file=sys.stderr)
                    errors += 1
            
            return {'processed': processed, 'errors': errors}
        
        else:  # auto mode
            # Let rsgain decide (process all at once)
            try:
                self.apply_to_files(files, album_mode=False)
                return {'processed': len(files), 'errors': 0}
            except Exception as e:
                return {'processed': 0, 'errors': len(files)}
    
    def apply_to_playlist(self, playlist_path: Path) -> dict:
        """
        Apply ReplayGain to files in M3U playlist
        
        Args:
            playlist_path: Path to M3U playlist
            
        Returns:
            Dictionary with processing stats
        """
        if not playlist_path.exists():
            raise FileNotFoundError(f"Playlist not found: {playlist_path}")
        
        # Load playlist
        files = []
        with open(playlist_path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.rstrip('\n\r')
                if line and not line.startswith('#'):
                    entry_path = Path(line)
                    
                    # Handle relative paths
                    if not entry_path.is_absolute():
                        entry_path = playlist_path.parent / entry_path
                    
                    if entry_path.exists():
                        files.append(entry_path)
        
        # Apply based on mode
        if self.mode == 'album':
            # Treat whole playlist as album
            try:
                self.apply_to_files(files, album_mode=True)
                return {'processed': len(files), 'errors': 0}
            except Exception:
                return {'processed': 0, 'errors': len(files)}
        else:
            # Track mode or auto
            errors = 0
            processed = 0
            for f in files:
                try:
                    self.apply_to_files([f], album_mode=False)
                    processed += 1
                except Exception as e:
                    errors += 1
            
            return {'processed': processed, 'errors': errors}


def apply_replaygain(target: Path, mode: str = 'auto', recursive: bool = True,
                     is_playlist: bool = False) -> dict:
    """
    Apply ReplayGain to audio files
    
    Args:
        target: File, directory, or playlist path
        mode: 'album', 'track', or 'auto'
        recursive: Process subdirectories
        is_playlist: Target is M3U playlist
        
    Returns:
        Processing statistics
    """
    applier = ReplayGainApplier(mode)
    
    if is_playlist:
        return applier.apply_to_playlist(target)
    elif target.is_dir():
        return applier.apply_to_directory(target, recursive)
    else:
        # Single file
        applier.apply_to_files([target])
        return {'processed': 1, 'errors': 0}


def main():
    parser = argparse.ArgumentParser(
        description='Apply ReplayGain tags for volume normalization'
    )
    parser.add_argument('target', type=Path, help='Audio file, directory, or playlist')
    parser.add_argument('-m', '--mode', choices=['album', 'track', 'auto'], 
                       default='auto', help='ReplayGain mode (default: auto)')
    parser.add_argument('-p', '--playlist', action='store_true', 
                       help='Target is M3U playlist')
    parser.add_argument('-n', '--no-recursive', action='store_true',
                       help='Don\'t process subdirectories')
    
    args = parser.parse_args()
    
    try:
        results = apply_replaygain(
            args.target,
            args.mode,
            not args.no_recursive,
            args.playlist
        )
        
        print(f"Processed: {results['processed']}")
        if results['errors']:
            print(f"Errors: {results['errors']}", file=sys.stderr)
            return 1
        
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    
    return 0


if __name__ == '__main__':
    sys.exit(main())
