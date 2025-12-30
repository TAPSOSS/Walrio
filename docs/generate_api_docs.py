#!/usr/bin/env python3
"""
API Documentation Generator
Copyright (c) 2025 TAPS OSS
Project: https://github.com/TAPSOSS/Walrio
Licensed under the BSD-3-Clause License (see LICENSE file for details)

Automatically generates the API reference documentation (index.rst) by discovering
all modules in the Walrio project and creating appropriate Sphinx autodoc directives.
"""

import os
import sys
from pathlib import Path
import re

def get_module_title(module_name: str) -> str:
    """
    Convert a module filename to a human-readable title.
    
    Args:
        module_name: The module filename (without .py extension)
        
    Returns:
        str: Human-readable title for the module
    """
    # Handle special cases
    special_cases = {
        'file_relocater': 'File Relocater',
        'image_converter': 'Image Converter',
        'replay_gain': 'ReplayGain',
        'apply_loudness': 'Apply Loudness',
        'resize_album_art': 'Resize Album Art',
        'playlist_case_conflicts': 'Playlist Case Conflicts',
        'playlist_cleaner': 'Playlist Cleaner',
        'playlist_cloner': 'Playlist Cloner',
        'playlist_deleter': 'Playlist Deleter',
        'playlist_fixer': 'Playlist Fixer',
        'playlist_overlap': 'Playlist Overlap',
        'playlist_updater': 'Playlist Updater',
        'walrio_import': 'Walrio Import'
    }
    
    if module_name in special_cases:
        return special_cases[module_name]
    
    # Default: capitalize first letter and replace underscores with spaces
    return module_name.replace('_', ' ').title()

def get_rst_underline(title: str, level: int = 1) -> str:
    """
    Generate appropriate RST underline for a title.
    
    Args:
        title: The title text
        level: Header level (1=~, 2=--, 3=^^, etc.)
        
    Returns:
        str: RST underline characters
    """
    underline_chars = ['~', '-', '^', '"', "'", '.', '`', ':', '#', '*', '+', '_']
    if level > len(underline_chars):
        level = len(underline_chars)
    
    char = underline_chars[level - 1]
    return char * len(title)

def extract_module_description(file_path: str) -> str:
    """
    Extract description from a Python module's docstring or header comments.
    
    Args:
        file_path: Path to the Python file
        
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
        for line in lines:
            line = line.strip()
            if line.startswith('#') and len(line) > 1:
                comment = line[1:].strip()
                if comment and not comment.startswith('!'):
                    return comment
        
        return "Module description not available"
        
    except Exception:
        return "Module description not available"

def has_api_content(file_path: str) -> bool:
    """
    Check if a module has typical API content (classes, functions, etc.).
    
    Args:
        file_path: Path to the Python file
        
    Returns:
        bool: True if module has API content, False otherwise
    """
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Look for class definitions
        class_pattern = r'^\s*class\s+[A-Z]\w*\s*[:\(]'
        has_classes = bool(re.search(class_pattern, content, re.MULTILINE))
        
        if has_classes:
            return True
        
        # Look for public function definitions (excluding private ones starting with _)
        function_pattern = r'^\s*def\s+([a-zA-Z]\w*)\s*\('
        functions = re.findall(function_pattern, content, re.MULTILINE)
        
        # If there are any public functions, consider it an API module
        return len(functions) > 0
        
    except Exception:
        return False

def discover_modules():
    """
    Discover all modules in the Walrio project.
    
    Returns:
        dict: Dictionary with module info organized by category
    """
    # Get the project root (parent of docs directory)
    docs_dir = Path(__file__).parent
    project_root = docs_dir.parent
    modules_dir = project_root / 'modules'
    
    modules_by_category = {
        'core': {},
        'addons': {},
        'niche': {}
    }
    
    for category in modules_by_category.keys():
        category_path = modules_dir / category
        if category_path.exists():
            for py_file in category_path.glob('*.py'):
                if not py_file.name.startswith('__'):
                    module_name = py_file.stem
                    description = extract_module_description(str(py_file))
                    has_api = has_api_content(str(py_file))
                    
                    modules_by_category[category][module_name] = {
                        'description': description,
                        'has_api': has_api,
                        'title': get_module_title(module_name)
                    }
    
    return modules_by_category

def generate_api_documentation():
    """
    Generate the API reference documentation file.
    """
    print("🔍 Discovering modules...")
    modules = discover_modules()
    
    # Count total modules
    total_modules = sum(len(category_modules) for category_modules in modules.values())
    print(f"📦 Found {total_modules} modules across {len(modules)} categories")
    
    # Generate RST content
    rst_content = []
    rst_content.append("API Reference")
    rst_content.append("=============")
    rst_content.append("")
    rst_content.append("This section contains the complete API reference for Walrio modules, automatically generated from the source code docstrings.")
    rst_content.append("")
    
    # Generate sections for each category
    for category, category_modules in modules.items():
        if not category_modules:
            continue
            
        # Category header
        category_title = f"{category.title()} Modules"
        rst_content.append(category_title)
        rst_content.append(get_rst_underline(category_title, level=2))
        rst_content.append("")
        
        # Sort modules alphabetically
        sorted_modules = sorted(category_modules.items())
        
        for module_name, module_info in sorted_modules:
            # Module header
            module_title = module_info['title']
            rst_content.append(module_title)
            rst_content.append(get_rst_underline(module_title, level=3))
            rst_content.append("")
            
            # Add note for modules without API content
            if not module_info['has_api']:
                rst_content.append(".. note::")
                rst_content.append("   This module contains no API calls to document. It may contain only")
                rst_content.append("   constants, configuration, or utility code without public functions or classes.")
                rst_content.append("")
            
            # Autodoc directive
            rst_content.append(f".. automodule:: modules.{category}.{module_name}")
            rst_content.append("   :members:")
            rst_content.append("   :undoc-members:")
            rst_content.append("   :show-inheritance:")
            rst_content.append("")
    
    # Write to file
    docs_dir = Path(__file__).parent
    api_index_path = docs_dir / 'source' / 'api' / 'index.rst'
    
    try:
        with open(api_index_path, 'w', encoding='utf-8') as f:
            f.write('\n'.join(rst_content))
        
        print(f"✅ Generated API documentation: {api_index_path}")
        print(f"📄 Created documentation for {total_modules} modules")
        
        # Show breakdown by category
        for category, category_modules in modules.items():
            if category_modules:
                api_count = sum(1 for m in category_modules.values() if m['has_api'])
                script_count = len(category_modules) - api_count
                print(f"   {category.title()}: {len(category_modules)} modules ({api_count} API, {script_count} script/pipeline)")
        
    except Exception as e:
        print(f"❌ Error writing API documentation: {e}")
        sys.exit(1)

def main():
    """Main entry point."""
    print("🚀 Walrio API Documentation Generator")
    print("=" * 50)
    
    generate_api_documentation()
    
    print("")
    print("✅ API documentation generation complete!")

if __name__ == "__main__":
    main()
