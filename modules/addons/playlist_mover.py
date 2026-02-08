#!/usr/bin/env python3

import os
import sys
import shutil
import argparse
from pathlib import Path


def parse_m3u_playlist(playlist_path):
    """
    Parse an M3U playlist file and extract all entries.
    
    Args:
        playlist_path (str): Path to the M3U playlist file.
        
    Returns:
        tuple: (metadata_lines, file_paths) where metadata_lines is a list of
               tuples (line_number, content) for metadata lines, and file_paths
               is a list of tuples (line_number, path) for file paths.
    """
    metadata_lines = []
    file_paths = []
    
    try:
        with open(playlist_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        
        for i, line in enumerate(lines):
            stripped = line.strip()
            
            # Empty lines
            if not stripped:
                metadata_lines.append((i, line))
                continue
            
            # Metadata/comment lines
            if stripped.startswith('#'):
                metadata_lines.append((i, line))
            else:
                # This is a file path
                file_paths.append((i, stripped))
                
        return metadata_lines, file_paths
        
    except Exception as e:
        print(f"Error parsing playlist '{playlist_path}': {e}")
        return [], []


def convert_path_to_absolute(relative_path, playlist_dir):
    """
    Convert a relative path to an absolute path based on playlist directory.
    
    Args:
        relative_path (str): The relative path from the playlist file.
        playlist_dir (str): Directory containing the playlist file.
        
    Returns:
        str: Absolute path to the audio file.
    """
    if os.path.isabs(relative_path):
        return relative_path
    
    return os.path.abspath(os.path.join(playlist_dir, relative_path))


def convert_absolute_to_relative(absolute_path, new_playlist_dir):
    """
    Convert an absolute path to a relative path from the new playlist directory.
    
    Args:
        absolute_path (str): The absolute path to the audio file.
        new_playlist_dir (str): The new directory where the playlist will be located.
        
    Returns:
        str: Relative path from new playlist directory to the audio file.
    """
    try:
        return os.path.relpath(absolute_path, new_playlist_dir)
    except ValueError:
        # If paths are on different drives (Windows), return absolute path
        return absolute_path


def update_playlist_paths(playlist_path, source_dir, dest_dir, dry_run=False):
    """
    Update file paths in a playlist file for its new location.
    
    Args:
        playlist_path (str): Path to the playlist file in source directory.
        source_dir (str): Source directory where playlist currently is.
        dest_dir (str): Destination directory where playlist will be moved.
        dry_run (bool): If True, only show what would be done without making changes.
        
    Returns:
        list: Updated lines for the playlist file.
    """
    metadata_lines, file_paths = parse_m3u_playlist(playlist_path)
    
    if not file_paths:
        print(f"  Warning: No file paths found in '{os.path.basename(playlist_path)}'")
        return None
    
    # Reconstruct the playlist
    all_lines = {}
    
    # Add metadata lines
    for line_num, content in metadata_lines:
        all_lines[line_num] = content
    
    # Process file paths
    source_playlist_dir = os.path.dirname(playlist_path)
    updated_count = 0
    error_count = 0
    
    for line_num, relative_path in file_paths:
        # Convert to absolute path first
        absolute_path = convert_path_to_absolute(relative_path, source_playlist_dir)
        
        # Check if file exists
        if not os.path.exists(absolute_path):
            print(f"  Warning: File not found: {absolute_path}")
            error_count += 1
            # Keep the original path even if file doesn't exist
            all_lines[line_num] = relative_path + '\n'
        else:
            # Convert to relative path from new location
            new_relative_path = convert_absolute_to_relative(absolute_path, dest_dir)
            
            # Use forward slashes for cross-platform compatibility
            new_relative_path = new_relative_path.replace('\\', '/')
            
            all_lines[line_num] = new_relative_path + '\n'
            
            if not dry_run and new_relative_path != relative_path:
                updated_count += 1
    
    # Sort by line number and reconstruct file
    sorted_lines = [all_lines[i] for i in sorted(all_lines.keys())]
    
    if not dry_run:
        if updated_count > 0:
            print(f"  Updated {updated_count} path(s) in '{os.path.basename(playlist_path)}'")
        if error_count > 0:
            print(f"  Found {error_count} missing file(s)")
    
    return sorted_lines


def move_playlist(playlist_path, source_dir, dest_dir, dry_run=False, overwrite=False):
    """
    Move a single playlist file to destination directory with updated paths.
    
    Args:
        playlist_path (str): Full path to the playlist file.
        source_dir (str): Source directory.
        dest_dir (str): Destination directory.
        dry_run (bool): If True, only show what would be done.
        overwrite (bool): If True, overwrite existing files.
        
    Returns:
        bool: True if successful, False otherwise.
    """
    playlist_name = os.path.basename(playlist_path)
    dest_path = os.path.join(dest_dir, playlist_name)
    
    print(f"\nProcessing: {playlist_name}")
    
    # Check if destination already exists
    if os.path.exists(dest_path) and not overwrite:
        print(f"  Skipped: File already exists at destination (use --overwrite to replace)")
        return False
    
    # Update the playlist paths
    updated_lines = update_playlist_paths(playlist_path, source_dir, dest_dir, dry_run)
    
    if updated_lines is None:
        return False
    
    if dry_run:
        print(f"  Would move to: {dest_path}")
        return True
    
    try:
        # Write the updated playlist to destination
        with open(dest_path, 'w', encoding='utf-8') as f:
            f.writelines(updated_lines)
        
        print(f"  Successfully moved to: {dest_path}")
        
        # Remove original file after successful copy
        os.remove(playlist_path)
        print(f"  Removed original file")
        
        return True
        
    except Exception as e:
        print(f"  Error moving playlist: {e}")
        return False


def move_all_playlists(source_dir, dest_dir, dry_run=False, overwrite=False, recursive=False):
    """
    Move all playlist files from source to destination directory.
    
    Args:
        source_dir (str): Source directory containing playlists.
        dest_dir (str): Destination directory for playlists.
        dry_run (bool): If True, only show what would be done.
        overwrite (bool): If True, overwrite existing files.
        recursive (bool): If True, search subdirectories as well.
        
    Returns:
        tuple: (success_count, skip_count, error_count)
    """
    # Validate directories
    if not os.path.isdir(source_dir):
        print(f"Error: Source directory '{source_dir}' does not exist.")
        return 0, 0, 1
    
    # Create destination directory if it doesn't exist
    if not dry_run and not os.path.exists(dest_dir):
        os.makedirs(dest_dir)
        print(f"Created destination directory: {dest_dir}")
    
    # Find all playlist files
    playlist_extensions = {'.m3u', '.m3u8', '.pls', '.wpl', '.asx', '.xspf'}
    playlist_files = []
    
    if recursive:
        for root, dirs, files in os.walk(source_dir):
            for file in files:
                if os.path.splitext(file)[1].lower() in playlist_extensions:
                    playlist_files.append(os.path.join(root, file))
    else:
        for file in os.listdir(source_dir):
            file_path = os.path.join(source_dir, file)
            if os.path.isfile(file_path) and os.path.splitext(file)[1].lower() in playlist_extensions:
                playlist_files.append(file_path)
    
    if not playlist_files:
        print(f"No playlist files found in '{source_dir}'")
        return 0, 0, 0
    
    print(f"\nFound {len(playlist_files)} playlist file(s)")
    
    if dry_run:
        print("\n--- DRY RUN MODE (no changes will be made) ---")
    
    # Process each playlist
    success_count = 0
    skip_count = 0
    error_count = 0
    
    for playlist_path in playlist_files:
        result = move_playlist(playlist_path, source_dir, dest_dir, dry_run, overwrite)
        if result:
            success_count += 1
        elif os.path.exists(os.path.join(dest_dir, os.path.basename(playlist_path))):
            skip_count += 1
        else:
            error_count += 1
    
    return success_count, skip_count, error_count


def main():
    """Main entry point for the playlist mover script."""
    parser = argparse.ArgumentParser(
        description='Move playlist files from one directory to another while updating relative paths.',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Move all playlists from ~/Music/old to ~/Music/new
  %(prog)s ~/Music/old ~/Music/new
  
  # Dry run to see what would happen
  %(prog)s ~/Music/old ~/Music/new --dry-run
  
  # Move playlists and overwrite existing files
  %(prog)s ~/Music/old ~/Music/new --overwrite
  
  # Move playlists from subdirectories as well
  %(prog)s ~/Music/old ~/Music/new --recursive
"""
    )
    
    parser.add_argument(
        'source',
        help='Source directory containing playlist files'
    )
    
    parser.add_argument(
        'destination',
        help='Destination directory for playlist files'
    )
    
    parser.add_argument(
        '-d', '--dry-run',
        action='store_true',
        help='Show what would be done without making changes'
    )
    
    parser.add_argument(
        '-o', '--overwrite',
        action='store_true',
        help='Overwrite existing playlist files in destination'
    )
    
    parser.add_argument(
        '-r', '--recursive',
        action='store_true',
        help='Search for playlists in subdirectories'
    )
    
    parser.add_argument(
        '-v', '--version',
        action='version',
        version='Walrio Playlist Mover 1.0'
    )
    
    args = parser.parse_args()
    
    # Expand user paths and convert to absolute
    source_dir = os.path.abspath(os.path.expanduser(args.source))
    dest_dir = os.path.abspath(os.path.expanduser(args.destination))
    
    # Validate that source and destination are different
    if source_dir == dest_dir:
        print("Error: Source and destination directories must be different.")
        return 1
    
    print(f"Source directory: {source_dir}")
    print(f"Destination directory: {dest_dir}")
    
    # Move playlists
    success, skip, error = move_all_playlists(
        source_dir,
        dest_dir,
        dry_run=args.dry_run,
        overwrite=args.overwrite,
        recursive=args.recursive
    )
    
    # Print summary
    print("\n" + "="*60)
    print("SUMMARY")
    print("="*60)
    
    if args.dry_run:
        print(f"Would move: {success} playlist(s)")
        print(f"Would skip: {skip} playlist(s) (already exist)")
    else:
        print(f"Successfully moved: {success} playlist(s)")
        print(f"Skipped: {skip} playlist(s) (already exist)")
        print(f"Errors: {error} playlist(s)")
    
    return 0 if error == 0 else 1


if __name__ == '__main__':
    sys.exit(main())
