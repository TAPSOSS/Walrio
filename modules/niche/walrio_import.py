#!/usr/bin/env python3
"""
'import' script which converts to standard filetype, normalizes file loudness, normalizes album art, and renames files. combination of multiple other scripts runnign one after another to normalize a music library.
"""
import sys
import argparse
import subprocess
import signal
import atexit
from pathlib import Path

# Audio file extensions that will be processed
AUDIO_EXTENSIONS = {'.mp3', '.flac', '.ogg', '.opus', '.m4a', '.mp4', '.wav', '.wma', '.aac', '.wv', '.ape'}

# Global state for cleanup tracking
_cleanup_state = {
    'output_dir': None,
    'existing_files': set(),
    'cleanup_enabled': False,
    'completed_successfully': False
}


def collect_audio_files(path, recursive=False):
    """
    Collect all audio files from a path
    
    Args:
        path: File or directory path
        recursive: Process directories recursively
        
    Returns:
        List of Path objects for audio files
    """
    audio_files = []
    
    if path.is_file():
        if path.suffix.lower() in AUDIO_EXTENSIONS:
            audio_files.append(path)
    elif path.is_dir():
        if recursive:
            for file_path in path.rglob('*'):
                if file_path.is_file() and file_path.suffix.lower() in AUDIO_EXTENSIONS:
                    audio_files.append(file_path)
        else:
            for file_path in path.glob('*'):
                if file_path.is_file() and file_path.suffix.lower() in AUDIO_EXTENSIONS:
                    audio_files.append(file_path)
    
    return audio_files


def collect_all_files(path):
    """
    Collect all files from a directory (recursively)
    
    Args:
        path: Directory path
        
    Returns:
        Set of Path objects for all files
    """
    if not path.exists() or not path.is_dir():
        return set()
    
    return {f for f in path.rglob('*') if f.is_file()}


def cleanup_new_files():
    """
    Clean up files added during this run if process is cancelled.
    Only removes files that didn't exist before the pipeline started.
    """
    if not _cleanup_state['cleanup_enabled']:
        return
    
    if _cleanup_state['completed_successfully']:
        return
    
    output_dir = _cleanup_state['output_dir']
    existing_files = _cleanup_state['existing_files']
    
    if output_dir is None or not output_dir.exists():
        return
    
    print("\n" + "=" * 60)
    print("Process cancelled - cleaning up newly added files...")
    print("=" * 60)
    
    current_files = collect_all_files(output_dir)
    new_files = current_files - existing_files
    
    if not new_files:
        print("No new files to clean up")
        return
    
    cleaned = 0
    errors = 0
    
    for file_path in new_files:
        try:
            file_path.unlink()
            cleaned += 1
            print(f"Removed: {file_path.relative_to(output_dir)}")
        except Exception as e:
            errors += 1
            print(f"Error removing {file_path.relative_to(output_dir)}: {e}")
    
    print(f"\nCleaned up {cleaned} new files")
    if errors > 0:
        print(f"Failed to remove {errors} files")
    
    # Remove empty directories
    try:
        for dir_path in sorted(output_dir.rglob('*'), reverse=True):
            if dir_path.is_dir() and not any(dir_path.iterdir()):
                dir_path.rmdir()
                print(f"Removed empty directory: {dir_path.relative_to(output_dir)}")
    except Exception:
        pass


def signal_handler(signum, frame):
    """
    Handle interrupt signals (Ctrl+C, etc.)
    """
    print("\n\nReceived interrupt signal...")
    cleanup_new_files()
    sys.exit(1)


def prompt_delete_with_errors(error_details):
    """
    Prompt user whether to delete originals despite pipeline errors
    
    Args:
        error_details: Dictionary mapping stage names to error information
        
    Returns:
        True if user wants to proceed with deletion, False otherwise
    """
    print("\n" + "=" * 60)
    print("PIPELINE COMPLETED WITH ERRORS")
    print("=" * 60)
    print("\nThe following stages encountered errors:\n")
    
    for stage_name, info in error_details.items():
        print(f"  • {stage_name}: {info}")
    
    print("\n" + "=" * 60)
    print("Delete original files anyway?")
    print("  (y)es - Delete originals despite errors")
    print("  (n)o  - Keep originals safe")
    print("=" * 60)
    
    while True:
        response = input("Your choice: ").strip().lower()
        if response in ['y', 'yes']:
            return True
        elif response in ['n', 'no']:
            return False
        else:
            print("Invalid input. Please enter 'y' or 'n'")


def delete_original_files(files, dry_run=False):
    """
    Delete original audio files after successful processing
    
    Args:
        files: List of Path objects to delete
        dry_run: If True, only show what would be deleted
    """
    print("\n" + "=" * 60)
    print("Deleting original files...")
    print("=" * 60)
    
    if dry_run:
        print("DRY RUN - Files that would be deleted:")
        for file_path in files:
            print(f"  {file_path}")
        return
    
    deleted = 0
    errors = 0
    
    for file_path in files:
        try:
            file_path.unlink()
            deleted += 1
            print(f"Deleted: {file_path}")
        except Exception as e:
            errors += 1
            print(f"Error deleting {file_path}: {e}")
    
    print(f"\nDeleted {deleted} files")
    if errors > 0:
        print(f"Failed to delete {errors} files")


def move_processed_files_back(output_dir, input_path, recursive=False, dry_run=False):
    """
    Move processed files from output_dir back to input_path location,
    then clean up output_dir.
    
    Args:
        output_dir: Directory containing processed files
        input_path: Original input path (file or directory)
        recursive: Whether original processing was recursive
        dry_run: If True, only show what would be moved
    """
    if not output_dir.exists():
        return
    
    print("\n" + "=" * 60)
    print("Moving processed files back to original location...")
    print("=" * 60)
    
    # Collect processed files from output_dir
    processed_files = collect_all_files(output_dir)
    
    if not processed_files:
        print("No processed files to move")
        return
    
    if dry_run:
        print("DRY RUN - Files that would be moved:")
        for file_path in processed_files:
            relative = file_path.relative_to(output_dir)
            if input_path.is_dir():
                target = input_path / relative
            else:
                target = input_path.parent / file_path.name
            print(f"  {file_path} -> {target}")
        print(f"\nWould then delete output directory: {output_dir}")
        return
    
    moved = 0
    errors = 0
    
    for file_path in processed_files:
        try:
            # Determine target location
            relative = file_path.relative_to(output_dir)
            
            if input_path.is_dir():
                # Preserve directory structure
                target = input_path / relative
            else:
                # Single file input - put in same directory as original
                target = input_path.parent / file_path.name
            
            # Create parent directories if needed
            target.parent.mkdir(parents=True, exist_ok=True)
            
            # Move file
            file_path.rename(target)
            moved += 1
            print(f"Moved: {relative} -> {target}")
        except Exception as e:
            errors += 1
            print(f"Error moving {file_path}: {e}")
    
    print(f"\nMoved {moved} files back to original location")
    if errors > 0:
        print(f"Failed to move {errors} files")
    
    # Clean up output_dir
    print("\nCleaning up output directory...")
    try:
        # Remove empty directories
        for dir_path in sorted(output_dir.rglob('*'), reverse=True):
            if dir_path.is_dir() and not any(dir_path.iterdir()):
                dir_path.rmdir()
        
        # Remove output_dir itself if empty
        if not any(output_dir.iterdir()):
            output_dir.rmdir()
            print(f"Removed output directory: {output_dir}")
        else:
            print(f"Output directory not empty, keeping: {output_dir}")
    except Exception as e:
        print(f"Error cleaning up output directory: {e}")


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
        Tuple of (success: bool, error_info: str or None)
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
        return True, None
    except subprocess.CalledProcessError as e:
        print("-" * 50)
        error_msg = f"Failed with exit code {e.returncode}"
        print(f"ERROR: {module_name} {error_msg}")
        return False, error_msg


def run_import_pipeline(input_path, recursive=False, dry_run=False, playlist_dir=None, delete_originals=False, force_reconvert=False, stop_on_error=False, output_dir=None):
    """
    Run complete import pipeline
    
    Pipeline stages:
    1. Convert to FLAC 48kHz/16-bit (creates new files in output directory)
       - Prompts if files already exist in output_dir: (y)es, (n)o, (ya) yes to all, (na) no to all
    2. Resize album art to 1000x1000 PNG (only on converted files in output directory)
    3. Rename with comprehensive character sanitization (only on converted files in output directory)
    4. Analyze and apply loudness normalization -16 LUFS (only on converted files in output directory)
    5. Delete originals (if --delete-originals is set, AFTER all processing completes)
       - With default output_dir: Processed files moved back to replace originals, output_dir cleaned up
       - With custom output_dir: Originals deleted, processed files remain in custom location
    
    Important: All operations work on files in the output directory.
    If errors occur during processing, user is prompted whether to delete originals anyway.
    If process is cancelled (Ctrl+C), only newly added files are removed from output_dir.
    
    Args:
        input_path: Input file/directory
        recursive: Process recursively
        dry_run: Show commands without executing
        playlist_dir: Directory containing playlists to update after rename
        delete_originals: Delete original files after conversion
        force_reconvert: Force reconvert all files regardless of current specs
        stop_on_error: Stop pipeline if any stage has errors (default: continue through all stages)
        output_dir: Output directory for converted files (default: ./output_dir)
        
    Returns:
        True if all stages succeeded
    """
    print(f"Starting Walrio Import Pipeline: {input_path}")
    print(f"Recursive: {recursive}")
    print(f"Dry run: {dry_run}")
    
    # Set default output directory and track if user specified custom location
    user_specified_output_dir = output_dir is not None
    if output_dir is None:
        output_dir = Path.cwd() / "output_dir"
    
    print(f"Output directory: {output_dir}")
    print("=" * 60)
    
    # Set up cleanup tracking and signal handlers
    if not dry_run:
        _cleanup_state['output_dir'] = output_dir
        _cleanup_state['existing_files'] = collect_all_files(output_dir)
        _cleanup_state['cleanup_enabled'] = True
        _cleanup_state['completed_successfully'] = False
        
        # Register cleanup handlers
        signal.signal(signal.SIGINT, signal_handler)  # Ctrl+C
        signal.signal(signal.SIGTERM, signal_handler)  # Termination
        atexit.register(cleanup_new_files)
        
        if _cleanup_state['existing_files']:
            print(f"\nFound {len(_cleanup_state['existing_files'])} existing files in output directory")
            print("(These will be preserved if process is cancelled)")
            print("=" * 60)
    
    # Collect source files if we need to delete them later
    source_files = []
    if delete_originals:
        print("\nCollecting source files for deletion after processing...")
        source_files = collect_audio_files(input_path, recursive)
        print(f"Found {len(source_files)} audio files to process")
        print("=" * 60)
    
    # Define pipeline stages with comprehensive configuration
    # IMPORTANT: Convert outputs to separate directory, then all subsequent operations work ONLY on that directory
    stages = [
        {
            'name': 'convert',
            'description': 'Convert to FLAC 48kHz/16-bit',
            'args': ['--format', 'flac', '--sample-rate', '48000', '--bit-depth', '16', '--output', str(output_dir)],
            'target_path': input_path  # Convert processes input_path
            # Note: --force-overwrite NOT included so user is prompted when files exist in output_dir
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
    
    # Note: We do NOT pass --delete-original to convert anymore.
    # Instead, we delete source files AFTER all stages complete successfully.
    # This ensures all processing happens on files in output_dir before originals are removed.
    
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
        
        # Show files that would be deleted
        if delete_originals and source_files:
            print("\nFiles that would be deleted after successful processing:")
            for file_path in source_files:
                print(f"  {file_path}")
            
            if user_specified_output_dir:
                print("\nProcessed files would remain in output directory")
                print(f"Output directory: {output_dir}")
            else:
                print("\nProcessed files would be moved back to original location")
                print(f"Output directory would be cleaned up: {output_dir}")
        
        print()
        return True
    
    # Execute pipeline
    failed_stages = {}  # Dict mapping stage name to error info
    for i, stage in enumerate(stages, 1):
        print(f"\n[Stage {i}/{len(stages)}] {stage['description']}")
        print("=" * 60)
        
        success, error_info = run_module(stage['name'], stage['target_path'], stage['args'], recursive)
        if not success:
            failed_stages[stage['name']] = error_info
            if stop_on_error:
                print(f"\nPipeline STOPPED at stage {i}: {stage['name']}")
                return False
            else:
                print(f"\nWARNING: Stage {i} ({stage['name']}) had errors, continuing...")
    
    print("\n" + "=" * 60)
    if failed_stages:
        print(f"Pipeline completed with errors in: {', '.join(failed_stages.keys())}")
        
        # Prompt user about deleting originals despite errors
        if delete_originals and source_files:
            if dry_run:
                print("\n[DRY RUN] Would prompt user about deleting originals despite errors")
            else:
                should_delete = prompt_delete_with_errors(failed_stages)
                if should_delete:
                    delete_original_files(source_files, dry_run=False)
                    
                    # Only move files back if using default output_dir
                    if not user_specified_output_dir:
                        move_processed_files_back(output_dir, input_path, recursive, dry_run=False)
                        print(f"\nOriginal files have been replaced with processed versions")
                    else:
                        print(f"\nOriginal files deleted, processed files are in: {output_dir}")
                else:
                    print("\nOriginal files preserved")
                    print(f"Processed files are in: {output_dir}")
    else:
        print("Pipeline completed successfully!")
        
        # Delete original files if requested and all stages succeeded
        if delete_originals and source_files:
            print(f"\nProcessed files are in: {output_dir}")
            delete_original_files(source_files, dry_run)
            if not dry_run:
                # Only move files back if using default output_dir
                if not user_specified_output_dir:
                    move_processed_files_back(output_dir, input_path, recursive, dry_run=False)
                    print(f"\nOriginal files have been replaced with processed versions")
                else:
                    print(f"\nOriginal files deleted, processed files remain in: {output_dir}")
        else:
            print(f"\nProcessed files are in: {output_dir}")
    
    # Mark as successfully completed (disables cleanup on exit)
    _cleanup_state['completed_successfully'] = True
    
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
  - All files are processed in --output-dir (default: ./output_dir)
  - Original files are NEVER modified - all work happens on copies in output_dir
  - If files exist in output_dir, prompts: (y)es, (n)o, (ya) yes to all, (na) no to all
  - If process cancelled (Ctrl+C): Only newly added files cleaned up, existing preserved
  - With --delete-originals (default output_dir): Processed files replace originals in place
  - With --delete-originals (custom output_dir): Originals deleted, files stay in output_dir
  - With --delete-originals + errors: Prompted whether to delete anyway
  - Without --delete-originals: Processed files stay in output_dir, originals untouched
  - --force-reconvert with wrong specs prompts to replace file (yes/no/yes all/no all)
  - --force-replace combines --force-reconvert and --delete-originals
  - Safer workflow: convert → resize → rename → loudness → replace originals

Examples:
  # Process to default ./output_dir directory (keeps originals)
  python walrio_import_remade.py /path/to/music

  # Process to custom output directory (keeps originals)
  python walrio_import_remade.py /path/to/music -r --output-dir /path/to/converted

  # Replace originals in-place (processed files moved back, temp dir cleaned up)
  python walrio_import_remade.py /path/to/music --force-replace --recursive

  # Delete originals, keep processed files in custom location
  python walrio_import_remade.py /path/to/music --delete-originals -o /path/to/converted

  # Force reconvert all files (prompts for files with wrong specs)
  python walrio_import_remade.py /path/to/music --force-reconvert

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
                       help='Output directory for converted files (default: ./output_dir)')
    parser.add_argument('-n', '--dry-run', action='store_true',
                       help='Show commands without executing')
    parser.add_argument('-p', '--playlist-dir', type=Path,
                       help='Directory containing playlists to update after rename')
    parser.add_argument('--delete-originals', '--do', action='store_true',
                       dest='delete_originals',
                       help='Delete original files after processing. With default output_dir: replaces originals in place. With custom output_dir: keeps processed files in specified location.')
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
