#!/usr/bin/env python3
"""
Walrio Import - Pipeline orchestrator to run multiple Walrio modules in sequence
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
            'args': ['--format', 'flac', '--sample-rate', '48000', '--bit-depth', '16', '--force-overwrite']
        },
        {
            'name': 'rename',
            'description': 'Rename with character filtering',
            'args': [
                '--auto-sanitize',
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
                # Accented characters
                '--rc', 'á', 'a', '--rc', 'à', 'a', '--rc', 'ä', 'a',
                '--rc', 'é', 'e', '--rc', 'è', 'e', '--rc', 'ë', 'e',
                '--rc', 'í', 'i', '--rc', 'ì', 'i', '--rc', 'ï', 'i',
                '--rc', 'ó', 'o', '--rc', 'ò', 'o', '--rc', 'ö', 'o',
                '--rc', 'ú', 'u', '--rc', 'ù', 'u', '--rc', 'ü', 'u',
                '--rc', 'ñ', 'n', '--rc', 'ç', 'c',
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
            'args': ['--replaygain', '--backup', 'false']
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
        description='Run Walrio import pipeline on audio files'
    )
    parser.add_argument('input', type=Path, help='Input file or directory')
    parser.add_argument('-r', '--recursive', action='store_true',
                       help='Process directories recursively')
    parser.add_argument('-n', '--dry-run', action='store_true',
                       help='Show commands without executing')
    parser.add_argument('-p', '--playlist-dir', type=Path,
                       help='Directory containing playlists to update after rename')
    parser.add_argument('--delete-originals', action='store_true',
                       help='Delete original files after conversion')
    
    args = parser.parse_args()
    
    try:
        success = run_import_pipeline(
            args.input, 
            args.recursive, 
            args.dry_run,
            args.playlist_dir,
            args.delete_originals
        )
        return 0 if success else 1
        
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
