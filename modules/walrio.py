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
import re
from pathlib import Path
from typing import Dict

# Add the current directory to Python path for imports
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, current_dir)

def discover_modules() -> Dict[str, Dict[str, str]]:
    """
    Dynamically discover all modules in the addons, niche, and core directories.
    
    Returns:
        dict: Dictionary with module info organized by category
    """
    modules_by_category = {
        'addons': {},
        'niche': {},
        'core': {}
    }
    
    for category in modules_by_category.keys():
        category_path = Path(current_dir) / category
        if category_path.exists():
            for py_file in category_path.glob('*.py'):
                if not py_file.name.startswith('__'):
                    module_name = py_file.stem
                    relative_path = f"{category}/{py_file.name}"
                    description = extract_module_description(str(py_file))
                    
                    modules_by_category[category][module_name] = {
                        'path': relative_path,
                        'full_path': str(py_file),
                        'description': description
                    }
    
    return modules_by_category

def extract_module_description(file_path: str) -> str:
    """
    Extract description from a Python module's docstring or header comments.
    
    Args:
        file_path (str): Path to the Python file
        
    Returns:
        str: Description of the module
    """
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # First try to extract from docstring
        docstring_match = re.search(r'"""([^"]*?)"""', content, re.DOTALL)
        if docstring_match:
            docstring = docstring_match.group(1).strip()
            # Look for the first line that's not just metadata
            lines = docstring.split('\n')
            for line in lines:
                line = line.strip()
                if line and not line.startswith('Copyright') and not line.startswith('Project:') and not line.startswith('Licensed'):
                    return line
        
        # If no docstring, look for header comments
        lines = content.split('\n')
        description_started = False
        for line in lines:
            line = line.strip()
            if line.startswith('"""') or line.startswith("'''"):
                description_started = True
                continue
            if description_started and line and not line.startswith('#') and not line.startswith('Copyright') and not line.startswith('Project:'):
                return line.replace('"""', '').replace("'''", '').strip()
        
        # Fallback: try to find any descriptive comment
        for line in lines[:20]:  # Check first 20 lines
            if line.strip().startswith('#') and len(line.strip()) > 10:
                comment = line.strip()[1:].strip()
                if not comment.startswith('!') and not comment.lower().startswith('copyright'):
                    return comment
        
        return f"Module: {Path(file_path).stem}"
    except Exception:
        return f"Module: {Path(file_path).stem}"

def get_all_modules() -> Dict[str, str]:
    """
    Get a flattened dictionary of all modules and their paths.
    
    Returns:
        dict: Module name -> relative path mapping
    """
    modules_by_category = discover_modules()
    all_modules = {}
    
    for category, modules in modules_by_category.items():
        for module_name, module_info in modules.items():
            all_modules[module_name] = module_info['path']
    
    return all_modules

def get_module_path(module_name: str) -> str:
    """
    Get the path to a module by its name.
    
    Args:
        module_name (str): Name of the module
        
    Returns:
        str: Path to the module file
    """
    all_modules = get_all_modules()
    
    if module_name in all_modules:
        return all_modules[module_name]
    else:
        raise ValueError(f"Module '{module_name}' not found. Available modules: {', '.join(all_modules.keys())}")

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
    
    # Convert relative path to absolute path
    full_module_path = os.path.join(current_dir, module_path)
    
    if not os.path.exists(full_module_path):
        print(f"Error: Module file not found: {full_module_path}", file=sys.stderr)
        return 1
    
    # Execute the module with the provided arguments
    cmd = [sys.executable, full_module_path] + args
    
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
    """Print basic help information with simple examples."""
    print("Walrio - Unified Music Library Management System")
    print("=" * 50)
    print()
    print("QUICK START - Common Commands:")
    print("  python walrio.py convert /path/to/music --format flac")
    print("  python walrio.py rename /path/to/music")
    print("  python walrio.py replaygain /path/to/music")
    print()
    print("USAGE:")
    print("  python walrio.py <module_name> [arguments...]")
    print()
    print("For module-specific help:")
    print("  python walrio.py <module_name> --help")
    print()
    print("For a list of all modules and descriptions:")
    print("  python walrio.py --help-more")
    print()
    print("For detailed documentation:")
    print("  https://tapsoss.github.io/Walrio/")
    print()

def print_help_more():
    """Print detailed help information about all available modules."""
    print("Walrio - All Available Modules")
    print("=" * 50)
    print()
    
    modules_by_category = discover_modules()
    
    # Print modules organized by category
    for category, modules in modules_by_category.items():
        if modules:  # Only show categories that have modules
            print(f"{category.upper()} MODULES:")
            print("-" * 20)
            for module_name, module_info in sorted(modules.items()):
                print(f"  {module_name:<15} - {module_info['description']}")
            print()
    
    print("USAGE:")
    print("  python walrio.py <module_name> [arguments...]")
    print()
    print("For module-specific help:")
    print("  python walrio.py <module_name> --help")
    print()
    print("For detailed documentation:")
    print("  https://tapsoss.github.io/Walrio/")
    print()
    
    # Show available modules as a list
    all_modules = get_all_modules()
    if all_modules:
        print(f"Available modules: {', '.join(sorted(all_modules.keys()))}")
    print()

def print_version():
    """Print version information."""
    print("Walrio Audio Processing Tool")
    print("Copyright (c) 2025 TAPS OSS")
    print("Project: https://github.com/TAPSOSS/Walrio")
    print("Licensed under the BSD-3-Clause License")

def main():
    """Main entry point for the unified Walrio interface."""
    if len(sys.argv) < 2:
        print_help()
        return
    
    # Handle help commands
    if sys.argv[1] in ['-h', '--help']:
        print_help()
        return
    elif sys.argv[1] == '--help-more':
        print_help_more()
        return
    
    module_name = sys.argv[1]
    module_args = sys.argv[2:]
    
    try:
        run_module(module_name, module_args)
    except ValueError as e:
        print(f"Error: {e}")
        print()
        print_help()
        sys.exit(1)
    except Exception as e:
        print(f"Error running module '{module_name}': {e}")
        sys.exit(1)

if __name__ == "__main__":
    sys.exit(main())
