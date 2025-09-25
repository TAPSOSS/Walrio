
'''
Walrio Import Pipeline - Complete audio library import processing
Copyright (c) 2025 TAPS OSS
Project: https://github.com/TAPSOSS/Walrio
Licensed under the BSD-3-Clause License (see LICENSE file for details)

This script orchestrates a complete import pipeline for audio files through the Walrio system.
It processes input directories through the following stages in order:
1. Convert to FLAC format with 48kHz/16-bit specifications
2. Rename files with standardized character filtering
3. Apply ReplayGain analysis with -16 LUFS target
4. Apply loudness normalization using ReplayGain tags
5. Resize album artwork to 1000x1000 JPEG format
'''

import sys
import argparse
import subprocess
from pathlib import Path

def get_walrio_path():
    """
    Get the path to the walrio.py unified interface.

    Returns:
        str: Absolute path to walrio.py
    """
    # Get the parent directory (modules) from current file location
    current_dir = Path(__file__).parent
    walrio_path = current_dir.parent / "walrio.py"
    
    if not walrio_path.exists():
        raise FileNotFoundError(f"Could not find walrio.py at {walrio_path}")
    
    return str(walrio_path)

def run_walrio_command(module_name, input_path, extra_args=None, recursive=False):
    """
    Run a walrio module command with the given arguments.
    
    Args:
        module_name (str): Name of the module to run
        input_path (str): Input file or directory path
        extra_args (list): Additional arguments for the module
        recursive (bool): Whether to add recursive flag
    
    Returns:
        bool: True if command succeeded, False otherwise
    """
    walrio_path = get_walrio_path()
    cmd = ["python", walrio_path, module_name]
    
    # Add recursive flag if needed and supported
    if recursive and module_name in ['convert', 'rename', 'replaygain', 'applyloudness', 'resizealbumart']:
        cmd.append("--recursive")
    
    # Add input path
    cmd.append(input_path)
    
    # Add extra arguments
    if extra_args:
        cmd.extend(extra_args)
    
    print(f"Running: {' '.join(cmd)}")
    print("-" * 50)
    
    try:
        # Run with live output and user interaction enabled
        result = subprocess.run(cmd, check=True)
        print("-" * 50)
        print(f"SUCCESS: {module_name} completed successfully")
        return True
    except subprocess.CalledProcessError as e:
        print("-" * 50)
        print(f"ERROR: {module_name} failed with exit code {e.returncode}")
        return False

def process_import_pipeline(input_path, recursive=False, dry_run=False):
    """
    Run the complete import pipeline on the input path.
    
    Args:
        input_path (str): Path to input file or directory
        recursive (bool): Whether to process recursively
        dry_run (bool): Whether to show commands without executing
    
    Returns:
        bool: True if all steps succeeded, False otherwise
    """
    print(f"Starting Walrio Import Pipeline for: {input_path}")
    print(f"Recursive mode: {'enabled' if recursive else 'disabled'}")
    print(f"Dry run mode: {'enabled' if dry_run else 'disabled'}")
    print("=" * 60)
    
    # Define the pipeline stages with their arguments
    pipeline_stages = [
        {
            'name': 'convert',
            'description': 'Convert to FLAC 48kHz/16-bit',
            'args': ['--format', 'flac', '--sample-rate', '48000', '--bit-depth', '16']
        },
        {
            'name': 'rename',
            'description': 'Rename with character filtering',
            'args': [
                '--sanitize', 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789[]()-_~@=+ ',
                '--rc', '/', '~',           # Forward slash to tilde
                '--rc', '\\', '~',          # Backslash to tilde  
                '--rc', '&', '+',           # Ampersand to plus
                '--rc', '?', '',            # Remove question marks
                '--rc', '!', '',            # Remove exclamation marks
                '--rc', '|', '~',           # Pipe to tilde
                '--rc', '.', '',            # Remove periods
                '--rc', ',', '~',           # Comma to tilde
                '--rc', '%', '',            # Remove percent signs
                '--rc', '*', '',            # Remove asterisks
                '--rc', '"', '',            # Remove double quotes
                '--rc', ':', '~',           # Colon to tilde
                '--rc', ';', '~',           # Semicolon to tilde
                '--rc', "'", '',            # Remove single quotes
                '--rc', '>', '',            # Remove greater than
                '--rc', '<', '',            # Remove less than
                '--rc', '{', '(',           # Left curly brace to left parenthesis
                '--rc', '}', ')',           # Right curly brace to right parenthesis
                # Common accented characters to base forms
                '--rc', 'á', 'a', '--rc', 'à', 'a', '--rc', 'ä', 'a', '--rc', 'â', 'a', '--rc', 'ã', 'a',
                '--rc', 'é', 'e', '--rc', 'è', 'e', '--rc', 'ë', 'e', '--rc', 'ê', 'e',
                '--rc', 'í', 'i', '--rc', 'ì', 'i', '--rc', 'ï', 'i', '--rc', 'î', 'i',
                '--rc', 'ó', 'o', '--rc', 'ò', 'o', '--rc', 'ö', 'o', '--rc', 'ô', 'o', '--rc', 'õ', 'o',
                '--rc', 'ú', 'u', '--rc', 'ù', 'u', '--rc', 'ü', 'u', '--rc', 'û', 'u',
                '--rc', 'ñ', 'n', '--rc', 'ç', 'c',
                # Uppercase versions
                '--rc', 'Á', 'A', '--rc', 'À', 'A', '--rc', 'Ä', 'A', '--rc', 'Â', 'A', '--rc', 'Ã', 'A',
                '--rc', 'É', 'E', '--rc', 'È', 'E', '--rc', 'Ë', 'E', '--rc', 'Ê', 'E',
                '--rc', 'Í', 'I', '--rc', 'Ì', 'I', '--rc', 'Ï', 'I', '--rc', 'Î', 'I',
                '--rc', 'Ó', 'O', '--rc', 'Ò', 'O', '--rc', 'Ö', 'O', '--rc', 'Ô', 'O', '--rc', 'Õ', 'O',
                '--rc', 'Ú', 'U', '--rc', 'Ù', 'U', '--rc', 'Ü', 'U', '--rc', 'Û', 'U',
                '--rc', 'Ñ', 'N', '--rc', 'Ç', 'C',
            ]
        },
        {
            'name': 'replaygain',
            'description': 'Apply ReplayGain analysis (-16 LUFS)',
            'args': ['--tag', '--target-lufs', '-16']
        },
        {
            'name': 'applyloudness',
            'description': 'Apply loudness using ReplayGain tags',
            'args': ['--replaygain', '--backup', 'false']
        },
        {
            'name': 'resizealbumart',
            'description': 'Resize album art to 1000x1000 JPEG',
            'args': ['--size', '1000x1000', '--format', 'jpg', '--quality', '100']
        }
    ]
    
    if dry_run:
        print("DRY RUN - Commands that would be executed:")
        print("-" * 40)
        walrio_path = get_walrio_path()
        for stage in pipeline_stages:
            cmd_parts = ["python", walrio_path, stage['name']]
            if recursive and stage['name'] in ['convert', 'rename', 'replaygain', 'applyloudness', 'resizealbumart']:
                cmd_parts.append("--recursive")
            cmd_parts.append(input_path)
            cmd_parts.extend(stage['args'])
            print(f"{stage['description']}:")
            print(f"  {' '.join(cmd_parts)}")
            print()
        return True
    
    # Execute each stage
    success_count = 0
    total_stages = len(pipeline_stages)
    
    for i, stage in enumerate(pipeline_stages, 1):
        print(f"\nStage {i}/{total_stages}: {stage['description']}")
        print("-" * 40)
        
        success = run_walrio_command(
            stage['name'],
            input_path,
            stage['args'],
            recursive
        )
        
        if success:
            success_count += 1
        else:
            print(f"ERROR: Pipeline failed at stage {i}: {stage['name']}")
            print(f"Completed {success_count}/{total_stages} stages successfully")
            return False
    
    print("\n" + "=" * 60)
    print(f"SUCCESS: Import pipeline completed successfully!")
    print(f"All {total_stages} stages completed for: {input_path}")
    return True

def main():
    """Main entry point for the walrio import pipeline."""
    parser = argparse.ArgumentParser(
        description="Walrio Import Pipeline - Complete audio library import processing",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Pipeline Stages (executed in order):
  1. Convert to FLAC format (48kHz, 16-bit)
  2. Rename files with character filtering
  3. Apply ReplayGain analysis (-16 LUFS target)
  4. Apply loudness normalization using ReplayGain tags
  5. Resize album artwork to 1000x1000 JPEG

Examples:
  # Process a single directory
  python walrio_import.py /path/to/music

  # Process recursively through subdirectories
  python walrio_import.py /path/to/music --recursive

  # Show what would be executed without running
  python walrio_import.py /path/to/music --dry-run
        """
    )
    
    parser.add_argument(
        'input',
        help='Input directory or file to process through the import pipeline'
    )
    
    parser.add_argument(
        '--recursive', '-r',
        action='store_true',
        help='Process directories recursively (passed to all applicable modules)'
    )
    
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Show commands that would be executed without actually running them'
    )
    

    
    args = parser.parse_args()
    
    # Validate input path
    input_path = Path(args.input)
    if not input_path.exists():
        print(f"Error: Input path does not exist: {args.input}")
        sys.exit(1)
    
    try:
        success = process_import_pipeline(
            str(input_path),
            recursive=args.recursive,
            dry_run=args.dry_run
        )
        
        if not success:
            sys.exit(1)
            
    except KeyboardInterrupt:
        print("\n\nImport pipeline interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\nError during import pipeline: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
