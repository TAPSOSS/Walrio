#!/usr/bin/env python3
"""
Walrio - Unified Audio Processing Tool
Copyright (c) 2025 TAPS OSS
Project: https://github.com/TAPSOSS/Walrio
Licensed under the BSD-3-Clause License (see LICENSE file for details)

A unified command-line interface for all Walrio audio processing modules.
Provides a single entry point to access everything.
"""

import os
import sys
import argparse
import subprocess
from pathlib import Path

# Add the current directory to Python path for imports
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, current_dir)

def get_module_path(module_name: str) -> str:
    """
    Get the full path to a module file.
    
    Args:
        module_name (str): Name of the module
        
    Returns:
        str: Full path to the module file
    """
    module_paths = {
        # Addons modules
        'convert': 'addons/convert.py',
        'rename': 'addons/rename.py', 
        'replaygain': 'addons/replaygain.py',
        'imageconverter': 'addons/imageconverter.py',
        'file_relocater': 'addons/file_relocater.py',
        
        # Niche modules
        'applyloudness': 'niche/applyloudness.py',
        'resizealbumart': 'niche/resizealbumart.py',
        
        # Core modules
        'database': 'core/database.py',
        'metadata': 'core/metadata.py',
        'player': 'core/player.py',
        'playlist': 'core/playlist.py',
        'queue': 'core/queue.py'
    }
    
    if module_name not in module_paths:
        return None
        
    return os.path.join(current_dir, module_paths[module_name])

def run_module(module_name: str, args: list) -> int:
    """
    Run a specific module with the given arguments.
    
    Args:
        module_name (str): Name of the module to run
        args (list): Command-line arguments to pass to the module
        
    Returns:
        int: Exit code from the module
    """
    module_path = get_module_path(module_name)
    
    if not module_path:
        print(f"Error: Unknown module '{module_name}'", file=sys.stderr)
        return 1
        
    if not os.path.exists(module_path):
        print(f"Error: Module file not found: {module_path}", file=sys.stderr)
        return 1
    
    # Execute the module with the provided arguments
    cmd = [sys.executable, module_path] + args
    
    try:
        result = subprocess.run(cmd, cwd=current_dir)
        return result.returncode
    except KeyboardInterrupt:
        print("\nOperation cancelled by user", file=sys.stderr)
        return 130
    except Exception as e:
        print(f"Error running module '{module_name}': {e}", file=sys.stderr)
        return 1

def print_help():
    """Print the main help message."""
    help_text = """
Walrio - Unified Audio Processing Tool

Usage: python walrio.py <module> [module_args...]

Available modules:

ADDONS (Audio Processing Tools):
  convert          Convert audio files between formats using FFmpeg
  rename           Rename audio files using metadata with customizable patterns
  replaygain       Analyze and apply ReplayGain tags using LUFS measurements
  imageconverter   Convert and resize images using ImageMagick
  file_relocater   Relocate and organize audio files based on metadata

NICHE (Specialized Tools):
  applyloudness    Apply gain adjustments to audio files based on ReplayGain or fixed values
  resizealbumart   Extract, resize, and re-embed album art in audio files

CORE (Library Components):
  database         Database operations for music library management
  metadata         Audio metadata reading and writing operations
  player           Audio playback functionality
  playlist         Playlist management operations
  queue            Audio queue management

Examples:
  # Get help for a specific module
  python walrio.py convert --help
  python walrio.py rename --help
  
  # Convert audio files
  python walrio.py convert input.wav --format mp3
  
  # Rename files using metadata
  python walrio.py rename /music/directory --format "{artist} - {title}"
  
  # Analyze and tag files with ReplayGain
  python walrio.py replaygain /music/directory --tag
  
  # Apply ReplayGain adjustments
  python walrio.py applyloudness /music/directory --replaygain
  
  # Resize album art
  python walrio.py resizealbumart /music/directory --recursive
  
  # Convert images
  python walrio.py imageconverter input.png --output output.jpg --size 1000x1000
  
  # Relocate files based on metadata
  python walrio.py file_relocater /music/source --output /music/organized

Module Descriptions:

ADDONS:
convert - A flexible audio conversion tool that supports multiple input formats and provides
  various conversion options including output format selection, metadata preservation,
  bitrate adjustment, and bit depth selection.

rename - Rename audio files to a standardized format using metadata fields like title, album,
  artist, etc. Supports custom naming patterns and character sanitization.

replaygain - Analyze audio files for ReplayGain values using LUFS (Loudness Units relative to 
  Full Scale) and optionally apply ReplayGain tags to normalize loudness across tracks.

imageconverter - Convert and resize images using ImageMagick with support for various formats,
  geometry strings, quality settings, and metadata handling.

file_relocater - Organize and relocate audio files into structured directories based on
  metadata such as artist, album, and other tags.

NICHE:
applyloudness - Apply gain adjustments directly to audio files using FFmpeg while preserving
  metadata and album art. Can apply gain based on ReplayGain values or direct dB adjustments.

resizealbumart - Extract album art from audio files, resize it using ImageMagick, and embed
  it back into the original audio file. Useful for standardizing album art sizes.

CORE:
database - Database operations and library management functionality for organizing and
  querying music collections.

metadata - Core metadata reading and writing operations for audio files using various
  tools and libraries.

player - Audio playback functionality and player control operations.

playlist - Playlist creation, management, and manipulation operations.

queue - Audio queue management for controlling playback order and queue operations.

For detailed help on any module, use:
  python walrio.py <module> --help
"""
    print(help_text)

def print_version():
    """Print version information."""
    print("Walrio Audio Processing Tool")
    print("Copyright (c) 2025 TAPS OSS")
    print("Project: https://github.com/TAPSOSS/Walrio")
    print("Licensed under the BSD-3-Clause License")

def main():
    """Main function for the unified Walrio interface."""
    if len(sys.argv) < 2:
        print_help()
        return 0
    
    # Handle special cases
    if sys.argv[1] in ['--help', '-h', 'help']:
        print_help()
        return 0
    elif sys.argv[1] in ['--version', '-v', 'version']:
        print_version()
        return 0
    elif sys.argv[1] == 'list':
        print("Available modules:")
        print("  ADDONS: convert, rename, replaygain, imageconverter, file_relocater")
        print("  NICHE: applyloudness, resizealbumart") 
        print("  CORE: database, metadata, player, playlist, queue")
        return 0
    
    # Get module name and arguments
    module_name = sys.argv[1]
    module_args = sys.argv[2:] if len(sys.argv) > 2 else []
    
    # Validate module name
    valid_modules = [
        'convert', 'rename', 'replaygain', 'imageconverter', 'file_relocater',  # addons
        'applyloudness', 'resizealbumart',  # niche
        'database', 'metadata', 'player', 'playlist', 'queue'  # core
    ]
    if module_name not in valid_modules:
        print(f"Error: Unknown module '{module_name}'", file=sys.stderr)
        print(f"Available modules: {', '.join(valid_modules)}", file=sys.stderr)
        print("Use 'python walrio.py --help' for more information", file=sys.stderr)
        return 1
    
    # Run the specified module
    return run_module(module_name, module_args)

if __name__ == "__main__":
    sys.exit(main())
