#!/usr/bin/env python3
"""
GUI Documentation Generator
Copyright (c) 2025 TAPS OSS
Project: https://github.com/TAPSOSS/Walrio
Licensed under the BSD-3-Clause License (see LICENSE file for details)

Automatically generates GUI documentation from the GUI directory, extracting
class information, method docstrings, and usage instructions.
"""

import os
import sys
import re
from pathlib import Path
from typing import List, Dict, Optional

def find_gui_applications(gui_dir: str) -> List[str]:
    """
    Find all GUI applications in the GUI directory.
    
    Args:
        gui_dir (str): Path to the GUI directory
        
    Returns:
        list: List of GUI application file paths
    """
    gui_apps = []
    gui_path = Path(gui_dir)
    
    if gui_path.exists():
        for py_file in gui_path.glob('*.py'):
            if not py_file.name.startswith('__'):
                gui_apps.append(str(py_file))
    
    return gui_apps

def extract_gui_module_info(file_path: str) -> Dict:
    """
    Extract detailed information from a GUI module including classes and methods.
    
    Args:
        file_path (str): Path to the GUI Python file
        
    Returns:
        dict: Detailed information about the GUI module
    """
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        info = {
            'name': Path(file_path).stem,
            'path': file_path,
            'classes': [],
            'main_description': '',
            'dependencies': [],
            'imports': []
        }
        
        # Extract module docstring
        docstring_match = re.search(r'"""([^"]*?)"""', content, re.DOTALL)
        if docstring_match:
            docstring = docstring_match.group(1).strip()
            # Look for the first descriptive line
            lines = docstring.split('\n')
            for line in lines:
                line = line.strip()
                if line and not line.startswith('Copyright') and not line.startswith('Project:') and not line.startswith('Licensed'):
                    info['main_description'] = line
                    break
        
        # Extract dependencies
        if 'PySide6' in content:
            info['dependencies'].append('PySide6')
        if 'PyQt' in content:
            info['dependencies'].append('PyQt')
        if 'tkinter' in content:
            info['dependencies'].append('tkinter')
        
        # Extract imports
        import_pattern = r'from\s+([\w.]+)\s+import|import\s+([\w.]+)'
        import_matches = re.findall(import_pattern, content)
        for match in import_matches:
            module = match[0] if match[0] else match[1]
            if module and not module.startswith('.') and module not in ['sys', 'os', 'subprocess', 'threading', 'time']:
                info['imports'].append(module)
        
        # Find all class definitions with their docstrings and methods
        class_pattern = r'class\s+(\w+)\s*\([^)]*\):\s*\n\s*"""([^"]*?)"""'
        class_matches = re.findall(class_pattern, content, re.DOTALL)
        
        for class_name, class_docstring in class_matches:
            class_info = {
                'name': class_name,
                'docstring': class_docstring.strip(),
                'methods': [],
                'signals': []
            }
            
            # Find the class definition and extract methods until next class or end
            class_start = content.find(f'class {class_name}')
            if class_start != -1:
                # Find the next class or end of file
                next_class = content.find('\nclass ', class_start + 1)
                if next_class == -1:
                    class_content = content[class_start:]
                else:
                    class_content = content[class_start:next_class]
                
                # Find methods with docstrings
                method_pattern = r'def\s+(\w+)\s*\([^)]*\):\s*\n\s*"""([^"]*?)"""'
                method_matches = re.findall(method_pattern, class_content, re.DOTALL)
                
                for method_name, method_docstring in method_matches:
                    if not method_name.startswith('__'):  # Skip magic methods for cleanliness
                        # Extract first line of docstring for summary
                        summary = method_docstring.split('\n')[0].strip()
                        
                        class_info['methods'].append({
                            'name': method_name,
                            'docstring': method_docstring.strip(),
                            'summary': summary
                        })
                
                # Find signals (Qt specific)
                signal_pattern = r'(\w+)\s*=\s*Signal\([^)]*\)'
                signal_matches = re.findall(signal_pattern, class_content)
                class_info['signals'] = signal_matches
            
            info['classes'].append(class_info)
        
        return info
        
    except Exception as e:
        return {
            'name': Path(file_path).stem,
            'path': file_path,
            'classes': [],
            'main_description': f"Error reading GUI module: {e}",
            'dependencies': [],
            'imports': []
        }

def get_gui_title(module_name: str) -> str:
    """
    Convert a GUI module filename to a human-readable title.
    
    Args:
        module_name (str): The module filename (without .py extension)
        
    Returns:
        str: Human-readable title for the GUI module
    """
    special_cases = {
        'walrio_main': 'Walrio Main GUI',
        'walrio_lite': 'Walrio Lite - Simple Music Player'
    }
    
    if module_name in special_cases:
        return special_cases[module_name]
    
    # Default: capitalize first letter and replace underscores with spaces
    return module_name.replace('_', ' ').title()

def generate_gui_rst_section(gui_info: Dict) -> str:
    """
    Generate RST documentation section for a GUI application.
    
    Args:
        gui_info (dict): GUI application information dictionary
        
    Returns:
        str: RST formatted documentation section
    """
    name = gui_info['name']
    description = gui_info['main_description']
    dependencies = gui_info['dependencies']
    classes = gui_info['classes']
    
    # Create a clean title
    title = get_gui_title(name)
    
    rst = f"\n{title}\n"
    rst += "~" * len(title) + "\n\n"
    
    # Add location
    relative_path = gui_info['path'].replace('/mnt/Xtra/GitHub/Walrio/', '')
    rst += f"**Location**: ``{relative_path}``\n\n"
    
    # Add description
    if description:
        rst += f"{description}\n\n"
    
    # Add dependencies
    if dependencies:
        rst += "**Dependencies**:\n\n"
        for dep in dependencies:
            rst += f"* ``{dep}``\n"
        rst += "\n"
    
    # Add classes and their methods
    if classes:
        rst += "**Classes and Methods**:\n\n"
        
        for class_info in classes:
            rst += f"**{class_info['name']}**\n\n"
            
            if class_info['docstring']:
                # Clean up the docstring and add proper indentation
                docstring_lines = class_info['docstring'].split('\n')
                for line in docstring_lines:
                    if line.strip():
                        rst += f"   {line.strip()}\n"
                rst += "\n"
            
            # Add signals if any (Qt specific)
            if class_info['signals']:
                rst += "   **Signals**:\n\n"
                for signal in class_info['signals']:
                    rst += f"   * ``{signal}``\n"
                rst += "\n"
            
            # Add methods
            if class_info['methods']:
                rst += "   **Key Methods**:\n\n"
                
                for method in class_info['methods']:
                    rst += f"   * ``{method['name']}()``\n"
                    if method['summary']:
                        rst += f"     {method['summary']}\n"
                    rst += "\n"
            
            rst += "\n"
    
    # Add usage instructions
    rst += "**Usage**:\n\n"
    rst += ".. code-block:: bash\n\n"
    rst += f"    python {relative_path}\n\n"
    
    # Add note about GUI
    rst += ".. note::\n"
    rst += "   This is a graphical application. Ensure you have a display environment available and the required GUI dependencies installed.\n\n"
    
    return rst

def generate_gui_documentation(gui_dir: str, output_file: str):
    """
    Generate complete GUI documentation.
    
    Args:
        gui_dir (str): Path to GUI directory
        output_file (str): Path to output RST file
    """
    print("🖥️  Scanning for GUI applications...")
    
    # Find all GUI applications
    gui_files = find_gui_applications(gui_dir)
    gui_apps = []
    
    for file_path in gui_files:
        print(f"  🖼️  Found GUI app: {Path(file_path).name}")
        gui_info = extract_gui_module_info(file_path)
        gui_apps.append(gui_info)
        print(f"    ✅ Extracted GUI information")
        
        # Show classes found
        if gui_info['classes']:
            for class_info in gui_info['classes']:
                print(f"      📋 Class: {class_info['name']} ({len(class_info['methods'])} methods)")
    
    # Generate RST documentation
    print(f"\n📝 Generating documentation for {len(gui_apps)} GUI applications...")
    
    rst_content = """GUI Applications
================

Walrio includes several graphical user interface applications that provide easy-to-use interfaces for music playback and management. These applications are built using modern GUI frameworks and provide intuitive controls for various Walrio features.

Overview
--------

The GUI applications are designed to be:

* **User-friendly**: Intuitive interfaces suitable for all user levels
* **Modular**: Each GUI serves a specific purpose or workflow  
* **Integrated**: Built on top of Walrio's core modules and CLI tools
* **Cross-platform**: Compatible with Windows, macOS, and Linux

**Available GUI Applications:**

"""
    
    # Add summary list
    for gui_app in sorted(gui_apps, key=lambda x: x['name']):
        title = get_gui_title(gui_app['name'])
        description = gui_app['main_description'] or "GUI Application"
        rst_content += f"* **{title}**: {description}\n"
    
    rst_content += "\nDetailed Documentation\n"
    rst_content += "---------------------\n"
    
    # Add detailed documentation for each GUI app
    for gui_app in sorted(gui_apps, key=lambda x: x['name']):
        rst_content += generate_gui_rst_section(gui_app)
    
    # Add installation and requirements section
    rst_content += """
Installation Requirements
-------------------------

To run the GUI applications, you need:

**Core Dependencies:**

.. code-block:: bash

    pip install PySide6

**System Requirements:**

* **Python 3.8+** - Required Python version
* **Display Environment** - GUI applications require:
  
  * **Linux**: X11 or Wayland display server
  * **macOS**: Native Cocoa support (built-in)
  * **Windows**: Native Windows desktop (built-in)

**Audio Dependencies:**

The GUI applications use Walrio's audio modules, which may require:

* **FFmpeg** - For audio format support and metadata extraction
* **GStreamer** - For advanced audio playback features

**Installation on Different Platforms:**

.. code-block:: bash

    # Ubuntu/Debian
    sudo apt install python3-pyside6 ffmpeg gstreamer1.0-plugins-base
    
    # macOS (with Homebrew)
    brew install python-tk ffmpeg
    pip install PySide6
    
    # Windows
    pip install PySide6
    # Download FFmpeg from https://ffmpeg.org/download.html

Troubleshooting
--------------

**Common Issues:**

* **"No module named 'PySide6'"**: Install PySide6 with ``pip install PySide6``
* **"Cannot connect to display"**: Ensure you have a GUI environment running
* **Audio playback issues**: Verify FFmpeg is installed and accessible

**Getting Help:**

For more information about the underlying modules used by these GUI applications, see:

* :doc:`api/index` - API documentation for core modules
* :doc:`cli_usage` - Command-line tools used by GUI applications

Development
-----------

These GUI applications are built using:

* **PySide6/Qt6** - Cross-platform GUI framework
* **Threading** - For responsive user interfaces during audio operations
* **Walrio Modules** - Integration with core audio processing capabilities

For extending or modifying the GUI applications, refer to the source code and the detailed class documentation above.
"""
    
    # Write the documentation
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(rst_content)
    
    print(f"✅ Documentation generated: {output_file}")

def main():
    """
    Main function to generate GUI documentation.
    """
    # Get paths
    script_dir = Path(__file__).parent
    project_root = script_dir.parent
    gui_dir = project_root / 'GUI'
    output_file = script_dir / 'source' / 'gui_usage.rst'
    
    print("🚀 Generating GUI Documentation...")
    print(f"📁 GUI directory: {gui_dir}")
    print(f"📄 Output file: {output_file}")
    
    try:
        generate_gui_documentation(str(gui_dir), str(output_file))
        print("\n🎉 GUI documentation generation complete!")
    except Exception as e:
        print(f"\n❌ Error generating documentation: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
