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
    walrio_path = current_dir.parent / "walrio.py"
    
    if not walrio_path.exists():
        raise FileNotFoundError(f"Could not find walrio.py at {walrio_path}")
    
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


def run_import_pipeline(input_path, recursive=False, dry_run=False, playlist_dir=None, delete_originals=False, force_reconvert=False, stop_on_error=False, output_dir=None):
    """
    Run complete import pipeline
    
    Pipeline stages:
    1. Convert to FLAC 48kHz/16-bit (creates new files in output directory)
    2. Resize album art to 1000x1000 PNG (only on converted files in output directory)
    3. Rename with comprehensive character sanitization (only on converted files in output directory)
    4. Analyze and apply loudness normalization -16 LUFS (only on converted files in output directory)
    
    Important: Original files in input_path are NEVER modified unless --delete-originals is set.
    All operations work on files in the output directory.
    
    Args:
        input_path: Input file/directory
        recursive: Process recursively
        dry_run: Show commands without executing
        playlist_dir: Directory containing playlists to update after rename
        delete_originals: Delete original files after conversion
        force_reconvert: Force reconvert all files regardless of current specs
        stop_on_error: Stop pipeline if any stage has errors (default: continue through all stages)
        output_dir: Output directory for converted files (default: ./imported_files)
        
    Returns:
        True if all stages succeeded
    """
    print(f"Starting Walrio Import Pipeline: {input_path}")
    print(f"Recursive: {recursive}")
    print(f"Dry run: {dry_run}")
    
    # Set default output directory
    if output_dir is None:
        output_dir = Path.cwd() / "imported_files"
    
    print(f"Output directory: {output_dir}")
    print("=" * 60)
    
    # Define pipeline stages with comprehensive configuration
    # IMPORTANT: Convert outputs to separate directory, then all subsequent operations work ONLY on that directory
    stages = [
        {
            'name': 'convert',
            'description': 'Convert to FLAC 48kHz/16-bit',
            'args': ['--format', 'flac', '--sample-rate', '48000', '--bit-depth', '16', '--force-overwrite', '--output', str(output_dir)],
            'target_path': input_path  # Convert processes input_path
        },
        {
            'name': 'resize_album_art',
            'description': 'Resize album art to 1000x1000 PNG',
            'args': ['--size', '1000x1000', '--format', 'png', '--quality', '100'],
            'target_path': output_dir  # Subsequent steps process output_dir ONLY
        },
        {
            'name': 'rename',
            'description': 'Rename with character filtering',
            'args': [
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
            ],
            'target_path': output_dir  # Subsequent steps process output_dir ONLY
        },
        {
            'name': 'apply_loudness',
            'description': 'Analyze and apply loudness normalization (-16 LUFS)',
            'args': ['--replaygain', '--rescan-lufs', '-16', '--backup', 'false', '--force'],
            'target_path': output_dir  # Subsequent steps process output_dir ONLY
        }
    ]
    
    # Add delete-originals to convert if requested (convert is stage 0, index 0)
    if delete_originals:
        stages[0]['args'].append('--delete-original')
    
    # Add force-reconvert to convert if requested (convert is stage 0, index 0)
    if force_reconvert:
        stages[0]['args'].append('--force-reconvert')
    
    # Add playlist updating to rename if specified (rename is now stage 2, index 2)
    if playlist_dir:
        stages[2]['args'].extend(['--update-playlists', str(playlist_dir)])
    
    if dry_run:
        print("\nDRY RUN - Commands that would be executed:\n")
        for stage in stages:
            walrio_path = get_walrio_path()
            cmd = [sys.executable, walrio_path, stage['name']]
            if recursive:
                cmd.append('--recursive')
            cmd.append(str(stage['target_path']))
            if stage['args']:
                cmd.extend(stage['args'])
            print(f"  {' '.join(cmd)}")
        print()
        return True
    
    # Execute pipeline
    failed_stages = []
    for i, stage in enumerate(stages, 1):
        print(f"\n[Stage {i}/{len(stages)}] {stage['description']}")
        print("=" * 60)
        
        if not run_module(stage['name'], stage['target_path'], stage['args'], recursive):
            failed_stages.append(stage['name'])
            if stop_on_error:
                print(f"\nPipeline STOPPED at stage {i}: {stage['name']}")
                return False
            else:
                print(f"\nWARNING: Stage {i} ({stage['name']}) had errors, continuing...")
    
    print("\n" + "=" * 60)
    if failed_stages:
        print(f"Pipeline completed with errors in: {', '.join(failed_stages)}")
    else:
        print("Pipeline completed successfully!")
        print(f"\nConverted files are in: {output_dir}")
    return len(failed_stages) == 0


def main():
    """Main entry point for Walrio Import tool - execute Walrio module pipelines."""
    parser = argparse.ArgumentParser(
        description='Walrio Import Pipeline - Complete audio library import processing',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""\nPipeline Stages (executed in order):
  1. Convert to FLAC format (48kHz, 16-bit)
  2. Resize album artwork to 1000x1000 PNG
  3. Rename files with character filtering
  4. Analyze and apply loudness normalization (-16 LUFS)

Important Notes:
  - Converted files go to --output-dir (default: ./imported_files)
  - Original files in input directory are NEVER modified unless --delete-originals
  - --force-reconvert with wrong specs prompts to replace original (yes/no)
  - --force-replace combines --force-reconvert and --delete-originals (no prompts)
  - All operations (rename, album art, loudness) work ONLY on files in output directory

Examples:
  # Process to default ./imported_files directory
  python walrio_import_remade.py /path/to/music

  # Process recursively to custom output directory
  python walrio_import_remade.py /path/to/music -r --output-dir /path/to/converted

  # Force reconvert all files (prompts for files with wrong specs)
  python walrio_import_remade.py /path/to/music --force-reconvert

  # Force reconvert AND delete originals in one step (no prompts)
  python walrio_import_remade.py /path/to/music --force-replace --recursive

  # Process and update playlists after renaming
  python walrio_import_remade.py /path/to/music --playlist-dir /path/to/playlists

  # Show what would be executed without running
  python walrio_import_remade.py /path/to/music --dry-run
"""
    )
    parser.add_argument('input', type=Path, help='Input file or directory')
    parser.add_argument('-r', '--recursive', action='store_true',
                       help='Process directories recursively')
    parser.add_argument('-o', '--output-dir', type=Path, dest='output_dir',
                       help='Output directory for converted files (default: ./imported_files)')
    parser.add_argument('-n', '--dry-run', action='store_true',
                       help='Show commands without executing')
    parser.add_argument('-p', '--playlist-dir', type=Path,
                       help='Directory containing playlists to update after rename')
    parser.add_argument('--delete-originals', '--do', action='store_true',
                       dest='delete_originals',
                       help='Delete original files after conversion (use with caution!)')
    parser.add_argument('--force-reconvert', '--fr', action='store_true',
                       dest='force_reconvert',
                       help='Force reconvert all files regardless of current audio specs')
    parser.add_argument('--force-replace', action='store_true',
                       dest='force_replace',
                       help='Force reconvert AND delete originals (combines --force-reconvert and --delete-originals)')
    
    parser.add_argument('--dont-continue', '--dc', action='store_true',
                       dest='dont_continue',
                       help='Stop pipeline execution if any stage has errors (default: continue through all stages)')
    
    args = parser.parse_args()
    
    # Handle --force-replace flag (combines force-reconvert and delete-originals)
    if args.force_replace:
        args.force_reconvert = True
        args.delete_originals = True
    
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
            args.delete_originals,
            args.force_reconvert,
            args.dont_continue,
            args.output_dir
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
