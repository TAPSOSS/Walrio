#!/usr/bin/env python3

import os
import re
from pathlib import Path

__version__ = "1.0.0"
__author__ = "Walrio Contributors"

def _discover_modules():
    """
    Automatically discover all modules in the package and extract their descriptions.
    
    Only searches in subdirectories (core/, addons/, niche/) to avoid including
    the global CLI interface (walrio.py) or other non-module files in the root.
    
    Returns:
        dict: Dictionary with module info organized by category
    """
    current_dir = Path(__file__).parent
    modules_by_category = {
        'core': {},
        'addons': {},
        'niche': {}
    }
    
    for category in modules_by_category.keys():
        category_path = current_dir / category
        if category_path.exists():
            for py_file in category_path.glob('*.py'):
                if not py_file.name.startswith('__'):
                    module_name = py_file.stem
                    description = _extract_module_description(str(py_file))
                    modules_by_category[category][module_name] = description
    
    return modules_by_category

def _extract_module_description(file_path: str) -> str:
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
        for line in lines:
            line = line.strip()
            if line.startswith('#') and len(line) > 1:
                comment = line[1:].strip()
                if comment and not comment.startswith('!'):
                    return comment
        
        return "Module description not available"
        
    except Exception:
        return "Module description not available"

# Discover all modules automatically
_discovered_modules = _discover_modules()

# Generate dynamic docstring with current module info
_doc_parts = [__doc__, "\nDiscovered Modules:\n"]

for category, modules in _discovered_modules.items():
    if modules:  # Only include categories that have modules
        _doc_parts.append(f"\n{category.title()} Modules:")
        for name, description in modules.items():
            _doc_parts.append(f"- {name}: {description}")

__doc__ = '\n'.join(_doc_parts)

# Import all discovered modules with error handling
_imported_modules = []

# Import core modules
for module_name in _discovered_modules.get('core', {}):
    try:
        exec(f"from .core import {module_name}")
        _imported_modules.append(module_name)
    except ImportError:
        pass

# Import addon modules  
for module_name in _discovered_modules.get('addons', {}):
    try:
        exec(f"from .addons import {module_name}")
        _imported_modules.append(module_name)
    except ImportError:
        pass

# Import niche modules
for module_name in _discovered_modules.get('niche', {}):
    try:
        exec(f"from .niche import {module_name}")
        _imported_modules.append(module_name)
    except ImportError:
        pass

# Also make submodules available for autodoc
try:
    from . import core
except ImportError:
    pass

try:
    from . import addons
except ImportError:
    pass

try:
    from . import niche
except ImportError:
    pass

# Make all discovered modules available at package level
__all__ = sorted(_imported_modules)
