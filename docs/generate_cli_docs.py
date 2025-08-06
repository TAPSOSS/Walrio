#!/usr/bin/env python3
"""
CLI Documentation Generator
Copyright (c) 2025 TAPS OSS
Project: https://github.com/TAPSOSS/Walrio
Licensed under the BSD-3-Clause License (see LICENSE file for details)

Automatically generates CLI documentation from --help output of command-line tools
in the modules directory (core, addons, niche folders).
"""

import os
import sys
import importlib.util
import subprocess
import re
from pathlib import Path
from typing import List, Dict, Optional

def find_cli_tools(modules_dir: str) -> List[str]:
    """
    Find all Python files in modules subdirectories that could be CLI tools.
    
    Args:
        modules_dir (str): Path to the modules directory
        
    Returns:
        list: List of Python file paths
    """
    cli_tools = []
    modules_path = Path(modules_dir)
    
    # Look in core, addons, niche, and any other subdirectories
    for subdir in modules_path.iterdir():
        if subdir.is_dir() and not subdir.name.startswith('__'):
            for py_file in subdir.glob('*.py'):
                if not py_file.name.startswith('__'):
                    cli_tools.append(str(py_file))
    
    return cli_tools

def has_cli_interface(file_path: str) -> bool:
    """
    Check if a Python file has a CLI interface (argparse usage).
    
    Args:
        file_path (str): Path to the Python file
        
    Returns:
        bool: True if file appears to have CLI interface
    """
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
            
        # Look for argparse usage indicators
        cli_indicators = [
            'argparse.ArgumentParser',
            'parse_arguments',
            'if __name__ == "__main__"',
            'def main(',
            'sys.argv'
        ]
        
        return any(indicator in content for indicator in cli_indicators)
    except Exception:
        return False

def get_help_output(file_path: str) -> Optional[str]:
    """
    Get the --help output from a CLI tool.
    
    Args:
        file_path (str): Path to the Python file
        
    Returns:
        str or None: Help output if successful, None otherwise
    """
    try:
        # Run the script with --help
        result = subprocess.run(
            [sys.executable, file_path, '--help'],
            capture_output=True,
            text=True,
            timeout=10,
            cwd=os.path.dirname(file_path)
        )
        
        if result.returncode == 0:
            return result.stdout
        else:
            return None
    except Exception:
        return None

def extract_tool_info(file_path: str, help_output: str) -> Dict[str, str]:
    """
    Extract tool information from help output.
    
    Args:
        file_path (str): Path to the Python file
        help_output (str): Help output from the tool
        
    Returns:
        dict: Dictionary with tool information
    """
    lines = help_output.split('\n')
    
    # Extract description (usually after "usage:" line)
    description = ""
    usage = ""
    examples = ""
    
    in_examples = False
    for i, line in enumerate(lines):
        if line.lower().startswith('usage:'):
            usage = line
            # Description is usually the next non-empty line
            for j in range(i + 1, len(lines)):
                if lines[j].strip() and not lines[j].startswith(' '):
                    description = lines[j].strip()
                    break
        
        # Look for examples section
        if 'examples:' in line.lower() or 'example:' in line.lower():
            in_examples = True
            continue
        
        if in_examples:
            if line.strip() and not line.startswith(' '):
                in_examples = False
            else:
                examples += line + '\n'
    
    return {
        'name': Path(file_path).stem,
        'path': file_path,
        'usage': usage.strip(),
        'description': description.strip(),
        'examples': examples.strip(),
        'full_help': help_output
    }

def generate_rst_section(tool_info: Dict[str, str]) -> str:
    """
    Generate RST documentation section for a CLI tool.
    
    Args:
        tool_info (dict): Tool information dictionary
        
    Returns:
        str: RST formatted documentation section
    """
    name = tool_info['name']
    description = tool_info['description']
    full_help = tool_info['full_help']
    
    # Create a clean title
    title = name.replace('_', ' ').title()
    
    rst = f"\n{title}\n"
    rst += "~" * len(title) + "\n\n"
    
    # Add location
    relative_path = tool_info['path'].replace('/mnt/Xtra/GitHub/Walrio/', '')
    rst += f"**Location**: ``{relative_path}``\n\n"
    
    # Add description if available
    if description:
        rst += f"{description}\n\n"
    
    # Add complete help output
    rst += "**Complete Help Output**:\n\n"
    rst += ".. code-block:: text\n\n"
    for line in full_help.split('\n'):
        rst += f"    {line}\n"
    rst += "\n"
    # Add link to full help
    rst += f"For complete options, run: ``python {relative_path} --help``\n\n"
    return rst

def generate_cli_documentation(modules_dir: str, output_file: str):
    """
    Generate complete CLI documentation.
    
    Args:
        modules_dir (str): Path to modules directory
        output_file (str): Path to output RST file
    """
    print("🔍 Scanning for CLI tools...")
    
    # Find all potential CLI tools
    python_files = find_cli_tools(modules_dir)
    cli_tools = []
    
    for file_path in python_files:
        if has_cli_interface(file_path):
            print(f"  📋 Found CLI tool: {Path(file_path).name}")
            help_output = get_help_output(file_path)
            
            if help_output:
                tool_info = extract_tool_info(file_path, help_output)
                cli_tools.append(tool_info)
                print(f"    ✅ Extracted help documentation")
            else:
                print(f"    ⚠️  Could not get help output")
        else:
            print(f"  ⏭️  Skipping {Path(file_path).name} (no CLI interface)")
    
    # Generate RST documentation
    print(f"\n📝 Generating documentation for {len(cli_tools)} CLI tools...")
    
    rst_content = """Command Line Usage
==================

Walrio provides several command-line tools for audio file management and processing. These tools are located throughout the ``modules/`` directory and can be run directly as Python scripts.

Available Tools
---------------
"""
    
    # Group tools by directory
    tools_by_dir = {}
    for tool in cli_tools:
        dir_name = Path(tool['path']).parent.name
        if dir_name not in tools_by_dir:
            tools_by_dir[dir_name] = []
        tools_by_dir[dir_name].append(tool)
    
    # Generate documentation for each directory
    for dir_name in sorted(tools_by_dir.keys()):
        rst_content += f"\n{dir_name.title()} Tools\n"
        rst_content += "^" * (len(dir_name) + 6) + "\n"
        
        for tool in sorted(tools_by_dir[dir_name], key=lambda x: x['name']):
            rst_content += generate_rst_section(tool)
    
    # Add getting help section
    rst_content += """Getting Help
------------

Each tool provides comprehensive help with examples::

"""
    
    for tool in sorted(cli_tools, key=lambda x: x['name']):
        relative_path = tool['path'].replace('/mnt/Xtra/GitHub/Walrio/', '')
        rst_content += f"    python {relative_path} --help\n"
    
    rst_content += """
For detailed API documentation of these tools, see :doc:`api/index`.

Dependencies
------------

These command-line tools may require:

* **FFmpeg/FFprobe** - For audio conversion and metadata extraction
* **Python 3.8+** - Required Python version
* **Additional libraries** - See requirements.txt for specific tools

Installation of FFmpeg:

.. code-block:: bash

    # Ubuntu/Debian
    sudo apt install ffmpeg
    
    # macOS (with Homebrew)
    brew install ffmpeg
    
    # Windows (with Chocolatey)  
    choco install ffmpeg
"""
    
    # Write the documentation
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(rst_content)
    
    print(f"✅ Documentation generated: {output_file}")

def main():
    """
    Main function to generate CLI documentation.
    """
    # Get paths
    script_dir = Path(__file__).parent
    modules_dir = script_dir.parent / 'modules'
    output_file = script_dir / 'source' / 'cli_usage.rst'
    
    print("🚀 Generating CLI Documentation...")
    print(f"📁 Modules directory: {modules_dir}")
    print(f"📄 Output file: {output_file}")
    
    try:
        generate_cli_documentation(str(modules_dir), str(output_file))
        print("\n🎉 CLI documentation generation complete!")
    except Exception as e:
        print(f"\n❌ Error generating documentation: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
