#!/usr/bin/env python3
"""
'import' script which converts to standard filetype, normalizes file loudness, normalizes album art, and renames files. combination of multiple other scripts runnign one after another to normalize a music library.
"""

import sys
import argparse
import subprocess
from pathlib import Path


def get_walrio_path():
    """Get path to walrio_remade.py unified interface"""
    current_dir = Path(__file__).parent
    walrio_path = current_dir.parent / "walrio_remade.py"
    
    if not walrio_path.exists():
        raise FileNotFoundError(f"Could not find walrio_remade.py at {walrio_path}")
    
    return str(walrio_path)


def run_module(module_name, input_path, args=None, recursive=False):
    """
    Run a Walrio module with given arguments
    
    Args:
        module_name: Module to run
        input_path: Input file/directory
        args: Additional arguments
        recursive: Add recursive flag
        
    Returns:
        True if successful
    """
    walrio_path = get_walrio_path()
    cmd = [sys.executable, walrio_path, module_name]
    
    if recursive:
        cmd.append('--recursive')
    
    cmd.append(str(input_path))
    
    if args:
        cmd.extend(args)
    
    print(f"Running: {' '.join(cmd)}")
    print("-" * 50)
    
    try:
        subprocess.run(cmd, check=True)
        print("-" * 50)
        print(f"SUCCESS: {module_name} completed")
        return True
    except subprocess.CalledProcessError as e:
        print("-" * 50)
        print(f"ERROR: {module_name} failed with exit code {e.returncode}")
        return False


def run_import_pipeline(input_path, recursive=False, dry_run=False, playlist_dir=None, delete_originals=False):
    """
    Run complete import pipeline
    
    Pipeline stages:
    1. Convert to FLAC 48kHz/16-bit
    2. Rename with comprehensive character sanitization
    3. Apply ReplayGain analysis (-16 LUFS)
    4. Apply loudness normalization using ReplayGain tags
    5. Resize album art to 1000x1000 PNG
    
    Args:
        input_path: Input file/directory
        recursive: Process recursively
        dry_run: Show commands without executing
        playlist_dir: Directory containing playlists to update after rename
        delete_originals: Delete original files after conversion
        
    Returns:
        True if all stages succeeded
    """
    print(f"Starting Walrio Import Pipeline: {input_path}")
    print(f"Recursive: {recursive}")
    print(f"Dry run: {dry_run}")
    print("=" * 60)
    
    # Define pipeline stages with comprehensive configuration
    stages = [
        {
            'name': 'convert',
            'description': 'Convert to FLAC 48kHz/16-bit',
            'args': ['--format', 'flac', '--sample-rate', '48000', '--bit-depth', '16', '--force-overwrite', 'y']
        },
        {
            'name': 'rename',
            'description': 'Rename with character filtering',
            'args': [
                '--auto-sanitize',
                '--sanitize', 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789[]()-_~@=+! ',
                '--rc', '?', '~',
                '--rc', '/', '~',
                '--rc', '\\', '~',
                '--rc', '&', '+',
                '--rc', '|', '~',
                '--rc', '.', '',
                '--rc', ',', '~',
                '--rc', '%', '',
                '--rc', '*', '',
                '--rc', '"', '',
                '--rc', ':', '~',
                '--rc', ';', '~',
                '--rc', "'", '',
                '--rc', '>', '',
                '--rc', '<', '',
                '--rc', '{', '(',
                '--rc', '}', ')',
                # Lowercase accented characters
                '--rc', 'á', 'a', '--rc', 'à', 'a', '--rc', 'ä', 'a', '--rc', 'â', 'a', '--rc', 'ã', 'a',
                '--rc', 'é', 'e', '--rc', 'è', 'e', '--rc', 'ë', 'e', '--rc', 'ê', 'e',
                '--rc', 'í', 'i', '--rc', 'ì', 'i', '--rc', 'ï', 'i', '--rc', 'î', 'i',
                '--rc', 'ó', 'o', '--rc', 'ò', 'o', '--rc', 'ö', 'o', '--rc', 'ô', 'o', '--rc', 'õ', 'o',
                '--rc', 'ú', 'u', '--rc', 'ù', 'u', '--rc', 'ü', 'u', '--rc', 'û', 'u',
                '--rc', 'ñ', 'n', '--rc', 'ç', 'c',
                # Uppercase accented characters
                '--rc', 'Á', 'A', '--rc', 'À', 'A', '--rc', 'Ä', 'A', '--rc', 'Â', 'A', '--rc', 'Ã', 'A',
                '--rc', 'É', 'E', '--rc', 'È', 'E', '--rc', 'Ë', 'E', '--rc', 'Ê', 'E',
                '--rc', 'Í', 'I', '--rc', 'Ì', 'I', '--rc', 'Ï', 'I', '--rc', 'Î', 'I',
                '--rc', 'Ó', 'O', '--rc', 'Ò', 'O', '--rc', 'Ö', 'O', '--rc', 'Ô', 'O', '--rc', 'Õ', 'O',
                '--rc', 'Ú', 'U', '--rc', 'Ù', 'U', '--rc', 'Ü', 'U', '--rc', 'Û', 'U',
                '--rc', 'Ñ', 'N', '--rc', 'Ç', 'C',
            ]
        },
        {
            'name': 'replay_gain',
            'description': 'Apply ReplayGain analysis (-16 LUFS)',
            'args': ['--tag', '--target-lufs', '-16']
        },
        {
            'name': 'apply_loudness',
            'description': 'Apply loudness using ReplayGain tags',
            'args': ['--replaygain', '--backup', 'false', '--force']
        },
        {
            'name': 'resize_album_art',
            'description': 'Resize album art to 1000x1000 PNG',
            'args': ['--size', '1000x1000', '--format', 'png', '--quality', '100']
        }
    ]
    
    # Add delete-originals to convert if requested
    if delete_originals:
        stages[0]['args'].append('--delete-original')
    
    # Add playlist updating to rename if specified
    if playlist_dir:
        stages[1]['args'].extend(['--update-playlists', str(playlist_dir)])
    
    if dry_run:
        print("\nDRY RUN - Commands that would be executed:\n")
        for stage in stages:
            walrio_path = get_walrio_path()
            cmd = [sys.executable, walrio_path, stage['name']]
            if recursive:
                cmd.append('--recursive')
            cmd.append(str(input_path))
            if stage['args']:
                cmd.extend(stage['args'])
            print(f"  {' '.join(cmd)}")
        print()
        return True
    
    # Execute pipeline
    for i, stage in enumerate(stages, 1):
        print(f"\n[Stage {i}/{len(stages)}] {stage['description']}")
        print("=" * 60)
        
        if not run_module(stage['name'], input_path, stage['args'], recursive):
            print(f"\nPipeline FAILED at stage {i}: {stage['name']}")
            return False
    
    print("\n" + "=" * 60)
    print("Pipeline completed successfully!")
    return True


def main():
    parser = argparse.ArgumentParser(
        description='Walrio Import Pipeline - Complete audio library import processing',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""\nPipeline Stages (executed in order):
  1. Convert to FLAC format (48kHz, 16-bit)
  2. Rename files with character filtering
  3. Apply ReplayGain analysis (-16 LUFS target)
  4. Apply loudness normalization using ReplayGain tags
  5. Resize album artwork to 1000x1000 PNG

Examples:
  # Process a single directory
  python walrio_import_remade.py /path/to/music

  # Process recursively through subdirectories
  python walrio_import_remade.py /path/to/music --recursive

  # Process and update playlists after renaming
  python walrio_import_remade.py /path/to/music --playlist-dir /path/to/playlists

  # Process and delete original files after conversion (use with caution!)
  python walrio_import_remade.py /path/to/music --recursive --delete-originals

  # Show what would be executed without running
  python walrio_import_remade.py /path/to/music --dry-run
"""
    )
    parser.add_argument('input', type=Path, help='Input file or directory')
    parser.add_argument('-r', '--recursive', action='store_true',
                       help='Process directories recursively')
    parser.add_argument('-n', '--dry-run', action='store_true',
                       help='Show commands without executing')
    parser.add_argument('-p', '--playlist-dir', type=Path,
                       help='Directory containing playlists to update after rename')
    parser.add_argument('--delete-originals', '--do', action='store_true',
                       dest='delete_originals',
                       help='Delete original files after conversion (use with caution!)')
    
    args = parser.parse_args()
    
    # Validate input path
    if not args.input.exists():
        print(f"Error: Input path does not exist: {args.input}", file=sys.stderr)
        return 1
    
    # Validate playlist directory if provided
    if args.playlist_dir:
        if not args.playlist_dir.exists():
            print(f"Error: Playlist directory does not exist: {args.playlist_dir}", file=sys.stderr)
            return 1
        if not args.playlist_dir.is_dir():
            print(f"Error: Playlist path is not a directory: {args.playlist_dir}", file=sys.stderr)
            return 1
    
    try:
        success = run_import_pipeline(
            args.input, 
            args.recursive, 
            args.dry_run,
            args.playlist_dir,
            args.delete_originals
        )
        return 0 if success else 1
    
    except KeyboardInterrupt:
        print("\n\nImport pipeline interrupted by user", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
