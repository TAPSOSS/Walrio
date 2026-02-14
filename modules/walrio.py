#!/usr/bin/env python3
import os
import sys
import subprocess
from pathlib import Path

# Module categories
CORE_MODULES = ['metadata', 'player', 'playlist', 'queue']
DATABASE_MODULES = ['database', 'song_queue', 'smart_playlist']
ADDON_MODULES = [
    'apply_loudness', 'convert', 'file_relocater', 'image_converter',
    'playlist_case_conflicts', 'playlist_cleaner', 'playlist_cloner',
    'playlist_deleter', 'playlist_fixer', 'playlist_mover',
    'playlist_overlap', 'playlist_updater', 'rename', 'replay_gain',
    'resize_album_art'
]
NICHE_MODULES = ['walrio_import']

def discover_modules():
    """Dynamically discover all modules in the core, database, addons, and niche directories."""
    modules_dir = Path(__file__).parent
    modules = {
        'core': {},
        'database': {},
        'addons': {},
        'niche': {}
    }
    
    # Scan each directory for Python files
    for category in ['core', 'database', 'addons', 'niche']:
        category_dir = modules_dir / category
        if category_dir.exists():
            for py_file in category_dir.glob('*.py'):
                # Skip __init__.py and private files
                if py_file.name.startswith('_'):
                    continue
                
                # Use the full file name (without .py extension) as the module name
                module_name = py_file.stem
                
                modules[category][module_name] = str(py_file)
    
    return modules

def extract_module_description(file_path):
    """Extract description from a Python module's docstring or header comments."""
    try:
        with open(file_path, 'r') as f:
            lines = f.readlines()
            
            # Look for module docstring
            in_docstring = False
            docstring = []
            
            for line in lines[:50]:  # Check first 50 lines
                if '"""' in line or "'''" in line:
                    if in_docstring:
                        break
                    in_docstring = True
                    continue
                if in_docstring:
                    docstring.append(line.strip())
            
            if docstring:
                return ' '.join(docstring[:2])  # First 2 lines
            
            # Fall back to file name conversion
            name = Path(file_path).stem
            return name.replace('_', ' ').title()
    except:
        return "No description available"

def get_all_modules():
    """Get a flattened dictionary of all modules and their paths."""
    discovered = discover_modules()
    all_modules = {}
    for category in discovered.values():
        all_modules.update(category)
    
    # Add aliases for common variations (without underscores)
    module_aliases = {
        'replaygain': 'replay_gain',
        'applyloudness': 'apply_loudness',
        'filerelocater': 'file_relocater',
        'imageconverter': 'image_converter',
        'resizealbum': 'resize_album_art',
        'resizealbumart': 'resize_album_art',
        'playlistcase': 'playlist_case_conflicts',
        'playlistcaseconflicts': 'playlist_case_conflicts',
        'playlistclean': 'playlist_cleaner',
        'playlistcleaner': 'playlist_cleaner',
        'playlistclone': 'playlist_cloner',
        'playlistcloner': 'playlist_cloner',
        'playlistdelete': 'playlist_deleter',
        'playlistdeleter': 'playlist_deleter',
        'playlistfix': 'playlist_fixer',
        'playlistfixer': 'playlist_fixer',
        'playlistoverlap': 'playlist_overlap',
        'playlistupdate': 'playlist_updater',
        'playlistupdater': 'playlist_updater',
        'walrioimport': 'walrio_import',
        # Database module aliases (old names)
        'db_queue': 'song_queue',
        'dbqueue': 'song_queue',
        'db_playlist': 'smart_playlist',
        'dbplaylist': 'smart_playlist',
        'smartplaylist': 'smart_playlist',
        'songqueue': 'song_queue',
    }
    
    for alias, actual_name in module_aliases.items():
        if actual_name in all_modules:
            all_modules[alias] = all_modules[actual_name]
    
    return all_modules

def get_module_path(module_name):
    """Get the path to a module by its name."""
    all_modules = get_all_modules()
    return all_modules.get(module_name)

def run_module(module_name, args):
    """Run a specific module with the given arguments."""
    module_path = get_module_path(module_name)
    
    if not module_path:
        print(f"Error: Module '{module_name}' not found.")
        print(f"Use 'walrio --help-more' to see available modules.")
        return 1
    
    try:
        # Run the module
        cmd = [sys.executable, module_path] + args
        result = subprocess.run(cmd)
        return result.returncode
    except Exception as e:
        print(f"Error running module '{module_name}': {e}")
        return 1

def print_help():
    """Print basic help information with simple examples."""
    print("Walrio - Unified Audio Library Management System")
    print()
    print("Usage: walrio <module> [options]")
    print()
    print("Core Modules:")
    print("  metadata     - Edit audio file metadata tags")
    print("  player       - Play audio files with GStreamer")
    print("  playlist     - Create and manage M3U playlists")
    print("  queue        - Manage playback queues")
    print()
    print("Database Modules (require walrio_library.db):")
    print("  database     - Scan music directories and build SQLite database")
    print("  song_queue   - Database-powered playback queue with statistics")
    print("  smart_playlist - Create dynamic playlists based on rules/queries")
    print()
    print("Examples:")
    print("  walrio database /path/to/music --db-path library.db")
    print("  walrio song_queue --interactive")
    print("  walrio smart_playlist --interactive")
    print("  walrio player song.mp3")
    print("  walrio metadata song.mp3 --show")
    print()
    print("Options:")
    print("  --help-more  Show all available modules with descriptions")
    print("  --version    Show version information")
    print()

def print_help_more():
    """Print detailed help information about all available modules."""
    print("Walrio - Complete Module List")
    print("=" * 70)
    print()
    
    modules = discover_modules()
    
    print("CORE MODULES:")
    print("-" * 70)
    for name in sorted(modules['core'].keys()):
        desc = extract_module_description(modules['core'][name])
        print(f"  {name:20} - {desc}")
    print()
    
    print("DATABASE MODULES (they ALL require a database file created from database.py in core modules):")
    print("-" * 70)z
    for name in sorted(modules['database'].keys()):
        desc = extract_module_description(modules['database'][name])
        print(f"  {name:20} - {desc}")
    print()
    
    print("ADDON MODULES:")
    print("-" * 70)
    for name in sorted(modules['addons'].keys()):
        desc = extract_module_description(modules['addons'][name])
        print(f"  {name:20} - {desc}")
    print()
    
    print("NICHE MODULES:")
    print("-" * 70)
    for name in sorted(modules['niche'].keys()):
        desc = extract_module_description(modules['niche'][name])
        print(f"  {name:20} - {desc}")
    print()
    print("Usage: walrio <module> [module-specific-options]")
    print()

def print_version():
    """Print version information."""
    print("Walrio v2.0 (Remade Edition)")
    print("Audio Library Management System")
    print()

def main():
    """Main entry point for the unified Walrio interface."""
    if len(sys.argv) < 2:
        print_help()
        return 0
    
    command = sys.argv[1]
    
    # Handle special commands
    if command in ['--help', '-h', 'help']:
        print_help()
        return 0
    elif command in ['--help-more', '-hm']:
        print_help_more()
        return 0
    elif command in ['--version', '-v']:
        print_version()
        return 0
    
    # Run module
    module_args = sys.argv[2:] if len(sys.argv) > 2 else []
    return run_module(command, module_args)

if __name__ == "__main__":
    sys.exit(main())