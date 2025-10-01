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

def find_gui_applications(gui_dir: str) -> Dict:
    """
    Find all GUI applications and MVC structure in the GUI directory.
    
    Args:
        gui_dir (str): Path to the GUI directory
        
    Returns:
        dict: Dictionary with 'standalone' apps and 'mvc' structure
    """
    result = {
        'standalone': [],
        'mvc': None
    }
    
    gui_path = Path(gui_dir)
    
    if gui_path.exists():
        # Find standalone GUI applications
        for py_file in gui_path.glob('*.py'):
            if not py_file.name.startswith('__'):
                result['standalone'].append(str(py_file))
        
        # Check for GUI application directories with MVC structure
        result['mvc'] = []
        for subdir in gui_path.iterdir():
            if (subdir.is_dir() and 
                subdir.name.endswith('GUI') and 
                not subdir.name.startswith('__')):
                mvc_structure = discover_mvc_structure(str(subdir))
                if mvc_structure:
                    result['mvc'].append(mvc_structure)
    
    return result

def discover_mvc_structure(mvc_root_dir: str) -> Dict:
    """
    Discover the MVC architecture structure automatically.
    
    Args:
        mvc_root_dir (str): Path to the MVC root directory
        
    Returns:
        dict: MVC structure with models, views, controllers, or None if not MVC
    """
    mvc_root = Path(mvc_root_dir)
    
    # Check if this directory has MVC structure
    has_mvc = (
        (mvc_root / 'models').exists() or
        (mvc_root / 'views').exists() or
        (mvc_root / 'controllers').exists()
    )
    
    if not has_mvc:
        return None
    
    structure = {
        'name': mvc_root.name,
        'root_dir': mvc_root_dir,
        'models': [],
        'views': [],
        'controllers': [],
        'main_files': []
    }
    
    # Find main entry point files
    for main_file in ['main.py', '__main__.py', '__init__.py']:
        main_path = mvc_root / main_file
        if main_path.exists():
            structure['main_files'].append(str(main_path))
    
    # Discover models
    models_dir = mvc_root / 'models'
    if models_dir.exists():
        for py_file in models_dir.glob('*.py'):
            if not py_file.name.startswith('__'):
                structure['models'].append(str(py_file))
    
    # Discover views
    views_dir = mvc_root / 'views'
    if views_dir.exists():
        for py_file in views_dir.glob('*.py'):
            if not py_file.name.startswith('__'):
                structure['views'].append(str(py_file))
    
    # Discover controllers
    controllers_dir = mvc_root / 'controllers'
    if controllers_dir.exists():
        for py_file in controllers_dir.glob('*.py'):
            if not py_file.name.startswith('__'):
                structure['controllers'].append(str(py_file))
    
    return structure

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

def get_gui_title(module_name: str, module_info: Dict = None) -> str:
    """
    Convert a GUI module filename to a human-readable title.
    
    Args:
        module_name (str): The module filename (without .py extension)
        module_info (dict): Optional module info for better title detection
        
    Returns:
        str: Human-readable title for the GUI module
    """
    # Try to extract title from module docstring first
    if module_info and module_info.get('main_description'):
        desc = module_info['main_description']
        # If it looks like a title, use it
        if len(desc) < 100 and not desc.startswith('Copyright'):
            return desc
    
    # Fallback patterns for common GUI naming conventions
    gui_patterns = {
        'walrio_main': 'Walrio Main GUI',
        'walrio_lite': 'Walrio Lite GUI', 
        'walrio_minimal': 'Walrio Minimal GUI',
        'walrio_advanced': 'Walrio Advanced GUI',
        'walrio_studio': 'Walrio Studio GUI'
    }
    
    if module_name in gui_patterns:
        return gui_patterns[module_name]
    
    # General pattern: Any .py file in GUI/ is a runner for a specific interface
    # Convert snake_case to Title Case and add "GUI" suffix
    title = module_name.replace('_', ' ').title()
    if not title.endswith('GUI') and not title.endswith('gui'):
        title += ' GUI'
    
    return title

def get_gui_description(module_name: str, module_info: Dict) -> str:
    """
    Generate a description for a GUI runner file.
    
    Args:
        module_name (str): The module filename
        module_info (dict): Module information
        
    Returns:
        str: Description of what this GUI provides
    """
    # Try to extract a better description from the full docstring
    if module_info.get('module_docstring'):
        docstring = module_info['module_docstring']
        lines = docstring.split('\n')
        
        # Look for descriptive content after the title line
        for i, line in enumerate(lines):
            line = line.strip()
            if (line and 
                not line.startswith('Copyright') and 
                not line.startswith('Project:') and
                not line.startswith('Licensed') and
                not line.startswith('#!/') and
                not line.endswith('launcher')):  # Skip generic "launcher" lines
                
                # Check if this looks like a substantial description
                if len(line) > 20 and len(line) < 200:
                    # Also check the next line to get complete sentences
                    if i + 1 < len(lines):
                        next_line = lines[i + 1].strip()
                        if next_line and len(next_line) > 10 and not next_line.startswith('Copyright'):
                            return f"{line} {next_line}"
                    return line
    
    # Fallback to main_description if no better description found
    if module_info.get('main_description'):
        desc = module_info['main_description']
        if (not desc.startswith('Copyright') and 
            len(desc) < 200 and 
            not desc.endswith('launcher')):
            return desc
    
    # Generate description based on classes found
    if module_info.get('classes'):
        class_names = [cls['name'] for cls in module_info['classes']]
        
        # Detect common GUI patterns
        if any('Player' in name for name in class_names):
            return f"Music player interface with {len(class_names)} component(s)"
        elif any('Manager' in name for name in class_names):
            return f"Management interface with {len(class_names)} component(s)"
        elif any('Editor' in name for name in class_names):
            return f"Editing interface with {len(class_names)} component(s)"
        else:
            return f"GUI application with {len(class_names)} component(s)"
    
    # Special cases for known patterns
    if 'main' in module_name:
        return "Primary GUI interface with full feature set"
    elif 'lite' in module_name:
        return "Lightweight GUI interface for basic operations"
    elif 'minimal' in module_name:
        return "Minimal GUI interface for essential functions"
    
    # Default fallback
    return "Walrio GUI application launcher"

def generate_gui_rst_section(gui_info: Dict) -> str:
    """
    Generate RST documentation section for a GUI application.
    
    Args:
        gui_info (dict): GUI application information dictionary
        
    Returns:
        str: RST formatted documentation section
    """
    name = gui_info['name']
    dependencies = gui_info['dependencies']
    classes = gui_info['classes']
    
    # Create a clean title and description using the enhanced functions
    title = get_gui_title(name, gui_info)
    description = get_gui_description(name, gui_info)
    
    rst = f"\n{title}\n"
    rst += "~" * len(title) + "\n\n"
    
    # Add location
    relative_path = gui_info['path'].replace('/mnt/Xtra/GitHub/Walrio/', '')
    rst += f"**Location**: ``{relative_path}``\n\n"
    
    # Add description and purpose
    rst += f"**Purpose**: {description}\n\n"
    
    # Add note about GUI runner files
    rst += f".. note::\n"
    rst += f"   This is a GUI runner file. All ``.py`` files in the GUI directory are launchers for specific user interfaces.\n\n"
    
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

def generate_mvc_documentation(mvc_structure: Dict) -> str:
    """
    Generate comprehensive MVC architecture documentation.
    
    Args:
        mvc_structure (dict): MVC structure with models, views, controllers
        
    Returns:
        str: RST formatted MVC documentation
    """
    mvc_root = Path(mvc_structure['root_dir'])
    app_name = mvc_structure['name']
    project_root = mvc_root.parent.parent
    
    # Generate appropriate title based on app name
    if 'Lite' in app_name:
        title = f"{app_name} - Lightweight GUI Architecture"
        description = "lightweight, simple music player GUI"
    elif 'Main' in app_name:
        title = f"{app_name} - Full-Featured GUI Architecture"
        description = "full-featured music player GUI"
    else:
        title = f"{app_name} - Structured GUI Architecture"
        description = "structured GUI application"
    
    rst = f"\n{title}\n"
    rst += "~" * len(title) + "\n\n"
    
    rst += f"**Location**: ``GUI/{app_name}/``\n\n"
    rst += f"The {app_name} application follows a structured component architecture, "
    rst += f"providing a clean separation of concerns for this {description}.\n\n"
    
    # Add structure overview
    rst += "**Component Structure**:\n\n"
    rst += ".. code-block:: text\n\n"
    rst += f"    {app_name}/\n"
    rst += "    ├── main.py                  # Main application entry point\n"
    rst += "    ├── __main__.py              # Module entry point\n"
    rst += "    ├── models/                  # Data models and business logic\n"
    
    for model_file in sorted(mvc_structure['models']):
        model_name = Path(model_file).stem
        rst += f"    │   ├── {model_name}.py\n"
    
    rst += "    ├── views/                   # UI components\n"
    for view_file in sorted(mvc_structure['views']):
        view_name = Path(view_file).stem
        rst += f"    │   ├── {view_name}.py\n"
    
    rst += "    └── controllers/             # Business logic coordinators\n"
    for controller_file in sorted(mvc_structure['controllers']):
        controller_name = Path(controller_file).stem
        rst += f"        ├── {controller_name}.py\n"
    rst += "\n"
    
    # Document each MVC component type
    rst += generate_mvc_component_docs("Models", mvc_structure['models'], "Data models and business logic components")
    rst += generate_mvc_component_docs("Views", mvc_structure['views'], "User interface components")
    rst += generate_mvc_component_docs("Controllers", mvc_structure['controllers'], "Business logic coordinators")
    
    # Add usage section
    # Generate usage instructions based on app name
    launcher_name = "walrio_main.py" if "Main" in app_name else "walrio_lite.py"
    
    rst += "**Usage**:\n\n"
    rst += ".. code-block:: bash\n\n"
    rst += f"    # Run the {app_name} application\n"
    rst += f"    python GUI/{launcher_name}\n"
    rst += "    \n"
    rst += "    # Or as a module\n"
    rst += f"    python -m GUI.{app_name}\n\n"
    
    # Add structured architecture benefits
    rst += "**Structured Architecture Benefits**:\n\n"
    rst += "* **Separation of Concerns**: UI, business logic, and data are clearly separated\n"
    rst += "* **Maintainability**: Each component has a single responsibility\n"
    rst += "* **Testability**: Controllers can be tested independently of UI\n"
    rst += "* **Reusability**: Views and models can be reused in different contexts\n"
    rst += "* **Scalability**: New features can be added without affecting existing code\n\n"
    
    return rst

def generate_mvc_component_docs(component_type: str, files: List[str], description: str) -> str:
    """
    Generate documentation for MVC component type (Models, Views, or Controllers).
    
    Args:
        component_type (str): Type of component (Models, Views, Controllers)
        files (list): List of file paths for this component type
        description (str): Description of this component type
        
    Returns:
        str: RST formatted documentation for the component type
    """
    if not files:
        return f"**{component_type}**: No {component_type.lower()} found.\n\n"
    
    rst = f"**{component_type}**:\n\n"
    rst += f"{description}:\n\n"
    
    for file_path in sorted(files):
        file_info = extract_gui_module_info(file_path)
        component_name = Path(file_path).stem
        
        rst += f"* **{component_name}.py**"
        if file_info['main_description']:
            rst += f": {file_info['main_description']}"
        rst += "\n"
        
        # Add classes found in this file
        if file_info['classes']:
            for class_info in file_info['classes']:
                rst += f"  \n"
                rst += f"  * ``{class_info['name']}``"
                if class_info['docstring']:
                    # Get first meaningful line from docstring
                    docstring_lines = class_info['docstring'].split('\n')
                    for line in docstring_lines:
                        line = line.strip()
                        if line and not line.startswith('Copyright'):
                            rst += f" - {line}"
                            break
                rst += "\n"
                
                # Add key methods count
                method_count = len([m for m in class_info['methods'] if not m['name'].startswith('_')])
                if method_count > 0:
                    rst += f"    ({method_count} public methods"
                    if class_info['signals']:
                        rst += f", {len(class_info['signals'])} signals"
                    rst += ")\n"
        
        rst += "\n"
    
    return rst

def generate_gui_documentation(gui_dir: str, output_file: str):
    """
    Generate complete GUI documentation including MVC architecture.
    
    Args:
        gui_dir (str): Path to GUI directory
        output_file (str): Path to output RST file
    """
    print("🖥️  Scanning for GUI applications...")
    
    # Find all GUI applications and MVC structure
    gui_structure = find_gui_applications(gui_dir)
    standalone_apps = []
    
    # Process standalone applications
    for file_path in gui_structure['standalone']:
        print(f"  🖼️  Found standalone GUI app: {Path(file_path).name}")
        gui_info = extract_gui_module_info(file_path)
        standalone_apps.append(gui_info)
        print(f"    ✅ Extracted GUI information")
        
        # Show classes found
        if gui_info['classes']:
            for class_info in gui_info['classes']:
                print(f"      📋 Class: {class_info['name']} ({len(class_info['methods'])} methods)")
    
    # Process MVC structures
    mvc_structures = gui_structure['mvc']
    if mvc_structures:
        for mvc_structure in mvc_structures:
            total_mvc_files = len(mvc_structure['models']) + len(mvc_structure['views']) + len(mvc_structure['controllers'])
            print(f"  🏗️  Found {mvc_structure['name']} architecture: {total_mvc_files} components")
            print(f"    📊 Models: {len(mvc_structure['models'])}")
            print(f"    🖼️  Views: {len(mvc_structure['views'])}")
            print(f"    🎮 Controllers: {len(mvc_structure['controllers'])}")
    
    # Generate RST documentation
    total_apps = len(standalone_apps) + len(mvc_structures)
    print(f"\n📝 Generating documentation for {total_apps} GUI applications...")
    
    rst_content = """GUI Applications
================

Walrio includes several graphical user interface applications that provide easy-to-use interfaces for music playback and management. These applications are built using modern GUI frameworks and provide intuitive controls for various Walrio features.

Overview
--------

The GUI system follows a clear organizational pattern:

* **GUI Runners**: Any ``.py`` file in the ``GUI/`` directory is a launcher for a specific user interface
* **Structured Architecture**: Complex GUIs use organized component architecture in subdirectories
* **Purpose-Built**: Each GUI serves a specific use case (simple playback, full management, etc.)
* **Extensible**: New GUIs can be added by creating new runner files

The GUI applications are designed to be:

* **User-friendly**: Intuitive interfaces suitable for all user levels
* **Modular**: Each GUI serves a specific purpose or workflow  
* **Integrated**: Built on top of Walrio's core modules and CLI tools
* **Cross-platform**: Compatible with Windows, macOS, and Linux
* **Architecturally Sound**: Following established patterns for maintainability

**Available GUI Applications:**

"""
    
    # Add summary list for standalone apps
    for gui_app in sorted(standalone_apps, key=lambda x: x['name']):
        title = get_gui_title(gui_app['name'], gui_app)
        description = get_gui_description(gui_app['name'], gui_app)
        rst_content += f"* **{title}**: {description}\n"
    
    # Add structured GUI applications to summary
    for mvc_structure in mvc_structures:
        app_name = mvc_structure['name']
        if 'Lite' in app_name:
            description = "Lightweight music player with organized component architecture"
        elif 'Main' in app_name:
            description = "Full-featured music player with organized component architecture"
        else:
            description = "Structured music player with organized component architecture"
        rst_content += f"* **{app_name} (Structured Architecture)**: {description}\n"
    
    rst_content += "\nDetailed Documentation\n"
    rst_content += "---------------------\n"
    
    # Add MVC documentation for structured applications (main apps first)
    for mvc_structure in sorted(mvc_structures, key=lambda x: 'Main' not in x['name']):
        rst_content += generate_mvc_documentation(mvc_structure)
    
    # Add detailed documentation for each standalone GUI app
    for gui_app in sorted(standalone_apps, key=lambda x: x['name']):
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
    
    print("🚀 Generating Comprehensive GUI Documentation...")
    print(f"📁 GUI directory: {gui_dir}")
    print(f"📄 Output file: {output_file}")
    
    try:
        generate_gui_documentation(str(gui_dir), str(output_file))
        print("\n🎉 GUI documentation generation complete!")
        print("   📖 Documentation includes:")
        print("      • Standalone GUI applications")
        print("      • GUI architecture components")  
        print("      • Automatic component discovery")
        print("      • Class and method documentation")
    except Exception as e:
        print(f"\n❌ Error generating documentation: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()
