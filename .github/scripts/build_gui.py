#!/usr/bin/env python3
"""
Walrio GUI Build Script
Copyright (c) 2025 TAPS OSS
Project: https://github.com/TAPSOSS/Walrio
Licensed under the BSD-3-Clause License (see LICENSE file for details)

Automated PyInstaller build script for Walrio Main and Lite GUIs.
Supports building for Linux, macOS, and Windows with proper dependency handling.
"""

import os
import sys
import platform
import subprocess
import shutil
import argparse
from pathlib import Path
import json

class WalrioBuildScript:
    """PyInstaller build automation for Walrio GUIs."""
    
    def __init__(self):
        """Initialize the build script with paths and platform detection."""
        # Since script is now in .github/scripts/, go up two levels to reach project root
        self.root_dir = Path(__file__).parent.parent.parent.absolute()
        self.dist_dir = self.root_dir / "dist"
        self.build_dir = self.root_dir / "build"
        self.gui_dir = self.root_dir / "GUI"
        
        # Platform detection
        self.platform = platform.system().lower()
        self.arch = platform.machine().lower()
        
        # Build configurations
        self.configs = {
            "walrio_main": {
                "entry_point": "GUI/walrio_main.py",
                "name": "WalrioMain",
                "console": False,
                "additional_data": [
                    ("modules", "modules"),
                    ("testing_files", "testing_files"),
                    ("assets", "assets"),
                    ("icons", "icons")  # Add entire icons folder to bundle
                ]
            },
            "walrio_lite": {
                "entry_point": "GUI/walrio_lite.py", 
                "name": "WalrioLite",
                "console": False,
                "additional_data": [
                    ("modules", "modules"),
                    ("testing_files", "testing_files"),
                    ("assets", "assets"),
                    ("icons", "icons")  # Add entire icons folder to bundle
                ]
            }
        }
        
        # Platform-specific settings
        self.platform_configs = {
            "linux": {
                "extension": "",
                "separator": ":",
                "hidden_imports": [
                    "gi.repository.Gst", "gi.repository.GLib", "gi.repository.GObject",
                    "PySide6.QtCore", "PySide6.QtWidgets", "PySide6.QtGui",
                    "mutagen", "sqlite3", "PIL.Image"
                ]
            },
            "darwin": {  # macOS
                "extension": ".app",
                "separator": ":",
                "hidden_imports": [
                    "gi.repository.Gst", "gi.repository.GLib", "gi.repository.GObject", 
                    "PySide6.QtCore", "PySide6.QtWidgets", "PySide6.QtGui",
                    "mutagen", "sqlite3", "Foundation", "AppKit", "PIL.Image"
                ]
            },
            "windows": {
                "extension": ".exe",
                "separator": ";",
                "hidden_imports": [
                    "gi.repository.Gst", "gi.repository.GLib", "gi.repository.GObject",
                    "PySide6.QtCore", "PySide6.QtWidgets", "PySide6.QtGui", 
                    "mutagen", "sqlite3", "PIL.Image"
                ]
            }
        }

    def check_dependencies(self):
        """Check if required dependencies are installed.
        
        Returns:
            bool: True if all required dependencies are available, False otherwise.
        """
        print("Checking dependencies...")
        
        required_packages = [
            "PyInstaller", "PySide6", "mutagen"
        ]
        
        missing_packages = []
        
        for package in required_packages:
            try:
                __import__(package)
                print(f"  [OK] {package} - installed")
            except ImportError:
                print(f"  [MISSING] {package} - missing")
                missing_packages.append(package)
        
        # Check for GStreamer (platform-specific)
        try:
            import gi
            gi.require_version('Gst', '1.0')
            from gi.repository import Gst
            
            # Initialize GStreamer to verify it's properly set up
            if Gst.init_check(None):
                print("  [OK] GStreamer - installed and initialized")
            else:
                print("  [WARNING] GStreamer - installed but initialization failed")
        except ImportError as e:
            print(f"  [WARNING] PyGObject/GStreamer - not found ({e})")
            print(f"            Audio playback may not work in the built executable")
            # Print environment info for debugging
            import os
            gst_path = os.environ.get('GST_PLUGIN_PATH', 'Not set')
            gi_path = os.environ.get('GI_TYPELIB_PATH', 'Not set')
            print(f"            GST_PLUGIN_PATH: {gst_path}")
            print(f"            GI_TYPELIB_PATH: {gi_path}")
        except ValueError as e:
            print(f"  [WARNING] GStreamer version issue - {e}")
            
        if missing_packages:
            print(f"\n[ERROR] Missing required packages: {', '.join(missing_packages)}")
            print("Install them with: pip install " + " ".join(missing_packages))
            return False
            
        return True

    def clean_build_dirs(self):
        """Clean previous build directories."""
        print("Cleaning previous build directories...")
        
        dirs_to_clean = [self.dist_dir, self.build_dir]
        
        for dir_path in dirs_to_clean:
            if dir_path.exists():
                shutil.rmtree(dir_path)
                print(f"  Removed {dir_path}")
            
        # Create fresh directories
        self.dist_dir.mkdir(exist_ok=True)
        self.build_dir.mkdir(exist_ok=True)

    def create_gstreamer_hook(self, hook_path):
        """Create GStreamer runtime hook for PyInstaller."""
        hook_content = '''
import os
import sys
import platform

def pyi_rth_gstreamer():
    """Runtime hook to properly initialize GStreamer in PyInstaller bundle."""
    try:
        # Set up GStreamer plugin paths relative to executable
        if hasattr(sys, '_MEIPASS'):
            # Running from PyInstaller bundle
            base_path = sys._MEIPASS
            
            if platform.system() == 'Linux':
                gst_plugin_path = os.path.join(base_path, 'gstreamer-1.0')
                gi_typelib_path = os.path.join(base_path, 'girepository-1.0')
                
                if os.path.exists(gst_plugin_path):
                    os.environ['GST_PLUGIN_PATH'] = gst_plugin_path
                if os.path.exists(gi_typelib_path):
                    os.environ['GI_TYPELIB_PATH'] = gi_typelib_path
                    
            elif platform.system() == 'Darwin':
                gst_plugin_path = os.path.join(base_path, 'gstreamer-1.0')
                gi_typelib_path = os.path.join(base_path, 'girepository-1.0')
                
                if os.path.exists(gst_plugin_path):
                    os.environ['GST_PLUGIN_PATH'] = gst_plugin_path
                if os.path.exists(gi_typelib_path):
                    os.environ['GI_TYPELIB_PATH'] = gi_typelib_path
                    
            elif platform.system() == 'Windows':
                gst_plugin_path = os.path.join(base_path, 'gstreamer-1.0')
                gi_typelib_path = os.path.join(base_path, 'girepository-1.0')
                
                if os.path.exists(gst_plugin_path):
                    os.environ['GST_PLUGIN_PATH'] = gst_plugin_path
                if os.path.exists(gi_typelib_path):
                    os.environ['GI_TYPELIB_PATH'] = gi_typelib_path
    except Exception as e:
        print(f"Warning: Failed to set up GStreamer environment: {e}")

# Execute hook
pyi_rth_gstreamer()
'''
        
        with open(hook_path, 'w') as f:
            f.write(hook_content)
        print(f"Created GStreamer runtime hook: {hook_path}")

    def create_fallback_gi_module(self):
        """Create a fallback gi module stub in case bundling fails."""
        gi_stub = self.root_dir / "gi_stub.py"
        stub_content = '''
"""
Fallback gi module stub for when PyGObject bundling fails.
This provides a helpful error message instead of a cryptic import error.
"""

class GiStub:
    def __init__(self):
        self.available = False
    
    def require_version(self, *args, **kwargs):
        raise ImportError(
            "GStreamer/PyGObject is not available in this build. "
            "This may indicate a packaging issue. "
            "Audio playback will not work. "
            "Please use a system installation or report this issue."
        )

# Create stub repository module
class RepositoryStub:
    def __getattr__(self, name):
        raise ImportError(
            f"GStreamer module '{name}' is not available. "
            "PyGObject/GStreamer was not properly bundled with this executable."
        )

# Replace the gi module functionality
import sys
sys.modules[__name__] = GiStub()
sys.modules[__name__ + '.repository'] = RepositoryStub()
'''
        
        with open(gi_stub, 'w') as f:
            f.write(stub_content)
        print(f"Created gi fallback stub: {gi_stub}")
        
        return gi_stub

    def build_gui(self, gui_type, debug=False):
        """Build a specific GUI with PyInstaller.
        
        Args:
            gui_type (str): Type of GUI to build ('main' or 'lite').
            debug (bool): Whether to build in debug mode (onedir vs onefile).
            
        Returns:
            bool: True if build succeeded, False otherwise.
        """
        if gui_type not in self.configs:
            raise ValueError(f"Unknown GUI type: {gui_type}")
            
        config = self.configs[gui_type]
        platform_config = self.platform_configs[self.platform]
        
        print(f"Building {config['name']} for {self.platform}...")
        
        # Build PyInstaller command
        cmd = [
            "pyinstaller",
            "--onefile" if not debug else "--onedir",
            f"--name={config['name']}",
            "--windowed" if not config["console"] else ""
        ]
        
        # Add platform-specific icon if it exists
        if self.platform == "windows":
            # Windows requires ICO format
            icon_path = self.root_dir / "icons" / "walrio.ico"
        else:
            # Linux and macOS can use PNG
            icon_path = self.root_dir / "icons" / "walrio.png"
            
        if icon_path.exists():
            cmd.append(f"--icon={icon_path}")
            print(f"  Using icon: {icon_path}")
        else:
            print(f"  Warning: Icon not found at {icon_path}")
        
        # Add hidden imports
        for import_name in platform_config["hidden_imports"]:
            cmd.append(f"--hidden-import={import_name}")
        
        # Use minimal PyInstaller collection to reduce warnings
        # Only collect what we absolutely need
        cmd.extend([
            "--collect-binaries=gi"
        ])
        
        # Add runtime hook for GStreamer initialization
        hook_file = self.root_dir / ".github" / "scripts" / "gst_runtime_hook.py"
        if not hook_file.exists():
            self.create_gstreamer_hook(hook_file)
        cmd.append(f"--runtime-hook={hook_file}")
            
        # Add additional data
        for src, dst in config["additional_data"]:
            src_path = self.root_dir / src
            if src_path.exists():
                cmd.append(f"--add-data={src_path}{platform_config['separator']}{dst}")
        
        # Platform-specific options and library collection
        if self.platform == "linux":
            # Try to find GStreamer plugin directories
            gst_paths = [
                "/usr/lib/x86_64-linux-gnu/gstreamer-1.0",
                "/usr/lib/gstreamer-1.0", 
                "/usr/local/lib/gstreamer-1.0"
            ]
            gi_paths = [
                "/usr/lib/x86_64-linux-gnu/girepository-1.0",
                "/usr/lib/girepository-1.0",
                "/usr/local/lib/girepository-1.0"
            ]
            
            for gst_path in gst_paths:
                if Path(gst_path).exists():
                    cmd.append(f"--add-binary={gst_path}/*:gstreamer-1.0/")
                    break
                    
            for gi_path in gi_paths:
                if Path(gi_path).exists():
                    cmd.append(f"--add-binary={gi_path}/*:girepository-1.0/")
                    break
                    
        elif self.platform == "darwin":
            cmd.extend([
                "--osx-bundle-identifier=org.tapsoss.walrio",
                f"--target-arch={self.arch}"
            ])
            
            # Check for GStreamer framework (setup-gstreamer action)
            framework_path = "/Library/Frameworks/GStreamer.framework"
            if Path(framework_path).exists():
                gst_lib_path = f"{framework_path}/Libraries"
                if Path(gst_lib_path).exists():
                    cmd.append(f"--add-binary={gst_lib_path}/*:.")
                    print(f"    Added GStreamer framework libraries from: {gst_lib_path}")
            
            # Try to find Homebrew GStreamer paths (fallback)
            homebrew_paths = ["/opt/homebrew", "/usr/local"]
            for homebrew in homebrew_paths:
                gst_path = f"{homebrew}/lib/gstreamer-1.0"
                gi_path = f"{homebrew}/lib/girepository-1.0"
                
                if Path(gst_path).exists():
                    cmd.append(f"--add-binary={gst_path}/*:gstreamer-1.0/")
                    print(f"    Added GStreamer plugins from: {gst_path}")
                if Path(gi_path).exists():
                    cmd.append(f"--add-binary={gi_path}/*:girepository-1.0/")
                    print(f"    Added GI typelibs from: {gi_path}")
                    
        elif self.platform == "windows":
            version_file_option = "--version-file=version_info.txt" if (self.root_dir / "version_info.txt").exists() else ""
            if version_file_option:
                cmd.append(version_file_option)
                
            # Try to find GStreamer paths (setup-gstreamer action and MSYS2)
            gst_root = os.environ.get('GSTREAMER_1_0_ROOT_MSVC_X86_64')
            potential_paths = []
            
            # Add setup-gstreamer action path if available
            if gst_root and Path(gst_root).exists():
                potential_paths.append(gst_root)
            
            # Add common GStreamer installation paths (only if they exist)
            common_paths = [
                "C:/gstreamer/1.0/msvc_x86_64",
                "C:/gstreamer"
            ]
            
            for path in common_paths:
                if Path(path).exists():
                    potential_paths.append(path)
            
            # Add MSYS2 paths for PyGObject integration (only if they exist)
            msys2_paths = [
                "C:/msys64/mingw64", 
                "C:/tools/msys64/mingw64"
            ]
            
            for msys2_path in msys2_paths:
                if Path(msys2_path).exists():
                    potential_paths.append(msys2_path)
                    print(f"    Found MSYS2 installation: {msys2_path}")
                else:
                    print(f"    MSYS2 path not found: {msys2_path}")
            
            # Track which paths we've already added to avoid duplicates
            added_gst_paths = set()
            added_gi_paths = set()
            added_bin_paths = set()
            
            for base_path in potential_paths:
                # Normalize path for Windows
                base_path_normalized = str(Path(base_path))
                base_path_obj = Path(base_path_normalized)
                
                print(f"    Checking base path: {base_path_normalized} - {'exists' if base_path_obj.exists() else 'not found'}")
                
                if not base_path_obj.exists():
                    continue
                    
                gst_path = base_path_obj / "lib" / "gstreamer-1.0"
                gi_path = base_path_obj / "lib" / "girepository-1.0"
                bin_path = base_path_obj / "bin"
                
                # Convert back to string and normalize for PyInstaller
                gst_path_str = str(gst_path).replace('\\', '/')
                gi_path_str = str(gi_path).replace('\\', '/')
                bin_path_str = str(bin_path).replace('\\', '/')
                
                if gst_path.exists() and gst_path_str not in added_gst_paths:
                    cmd.append(f"--add-binary={gst_path_str}/*:gstreamer-1.0/")
                    print(f"    Added GStreamer plugins from: {gst_path_str}")
                    added_gst_paths.add(gst_path_str)
                    
                if gi_path.exists() and gi_path_str not in added_gi_paths:
                    cmd.append(f"--add-binary={gi_path_str}/*:girepository-1.0/")
                    print(f"    Added GI typelibs from: {gi_path_str}")
                    added_gi_paths.add(gi_path_str)
                    
                if bin_path.exists() and bin_path_str not in added_bin_paths:
                    # Double-check path exists and verify DLL files actually exist before adding
                    if not Path(bin_path_str).exists():
                        print(f"    ERROR: Path existence check failed for {bin_path_str}")
                        continue
                        
                    dll_files = list(bin_path.glob("*.dll"))
                    if dll_files:
                        # Final safety check - verify the exact path PyInstaller will use
                        final_check_path = Path(bin_path_str)
                        if final_check_path.exists() and any(final_check_path.glob("*.dll")):
                            cmd.append(f"--add-binary={bin_path_str}/*.dll:.")
                            print(f"    Added GStreamer binaries from: {bin_path_str} ({len(dll_files)} DLL files)")
                            added_bin_paths.add(bin_path_str)
                        else:
                            print(f"    SAFETY CHECK FAILED: Path or DLLs not found at {bin_path_str}")
                    else:
                        print(f"    Skipped {bin_path_str} - no DLL files found")
        
        # Add entry point
        cmd.append(str(self.root_dir / config["entry_point"]))
        
        # Remove empty strings
        cmd = [arg for arg in cmd if arg]
        
        print(f"  Command: {' '.join(cmd)}")
        
        # Execute PyInstaller
        try:
            result = subprocess.run(cmd, cwd=self.root_dir, check=True, 
                                  capture_output=True, text=True)
            print(f"  [SUCCESS] {config['name']} built successfully")
            return True
        except subprocess.CalledProcessError as e:
            print(f"  [FAILED] Failed to build {config['name']}")
            print(f"  Error: {e.stderr}")
            return False

    def create_build_info(self, built_guis):
        """Create build information file.
        
        Args:
            built_guis (list): List of successfully built GUI applications.
        """
        build_info = {
            "timestamp": str(subprocess.check_output(["date"], text=True).strip()),
            "platform": self.platform,
            "architecture": self.arch,
            "python_version": platform.python_version(),
            "built_applications": built_guis
        }
        
        info_file = self.dist_dir / "build_info.json"
        with open(info_file, 'w') as f:
            json.dump(build_info, f, indent=2)
        
        print(f"Build info saved to {info_file}")

    def create_launcher_scripts(self):
        """Create platform-specific launcher scripts."""
        print("Creating launcher scripts...")
        
        if self.platform == "linux":
            # Create .desktop files for Linux
            desktop_template = """[Desktop Entry]
Version=1.0
Type=Application
Name={name}
Comment=Walrio Audio Player - {variant}
Exec={executable}
Icon={icon}
Categories=AudioVideo;Audio;Player;
StartupNotify=true
"""
            
            for gui_type, config in self.configs.items():
                executable = self.dist_dir / config["name"]
                if executable.exists():
                    desktop_content = desktop_template.format(
                        name=config["name"],
                        variant="Main Interface" if "main" in gui_type else "Lite Interface",
                        executable=str(executable),
                        icon="walrio"
                    )
                    
                    desktop_file = self.dist_dir / f"{config['name'].lower()}.desktop"
                    with open(desktop_file, 'w') as f:
                        f.write(desktop_content)
                    
                    # Make desktop file executable
                    os.chmod(desktop_file, 0o755)
                    print(f"  Created {desktop_file}")
        
        elif self.platform == "windows":
            # Create batch files for Windows
            batch_template = """@echo off
cd /d "%~dp0"
"{executable}" %*
"""
            
            for gui_type, config in self.configs.items():
                executable = self.dist_dir / f"{config['name']}.exe"
                if executable.exists():
                    batch_content = batch_template.format(executable=executable.name)
                    
                    batch_file = self.dist_dir / f"Launch_{config['name']}.bat"
                    with open(batch_file, 'w') as f:
                        f.write(batch_content)
                    
                    print(f"  Created {batch_file}")

    def create_readme(self):
        """Create README for distribution."""
        readme_content = f"""# Walrio Audio Player - Distribution Package

Built on: {platform.system()} {platform.release()}
Architecture: {self.arch}
Python Version: {platform.python_version()}

## Applications Included

### WalrioMain
Full-featured audio player with complete library management, playlist support, 
and advanced audio controls.

### WalrioLite  
Lightweight audio player with essential playback controls and simplified interface.

## System Requirements

### Linux
- GStreamer 1.0+ (for audio playback)
- GTK 3.0+ (for UI components)

### macOS
- macOS 10.14+ (Mojave or later)
- Audio Unit framework (built-in)

### Windows
- Windows 10+ (64-bit recommended)
- DirectShow codecs (usually pre-installed)

## Installation

1. Extract all files to your desired location
2. Run the appropriate executable:
   - Linux: `./WalrioMain` or `./WalrioLite`
   - macOS: Double-click `WalrioMain.app` or `WalrioLite.app`
   - Windows: Double-click `WalrioMain.exe` or `WalrioLite.exe`

## Audio Format Support

- MP3, FLAC, OGG, WAV, M4A, OPUS
- Playlist formats: M3U, M3U8

## Troubleshooting

### No Audio Output
- Ensure GStreamer is properly installed (Linux)
- Check system audio settings
- Verify audio file formats are supported

### Performance Issues  
- Try WalrioLite for better performance on older systems
- Close unnecessary applications
- Check available system memory

## Support

- Project: https://github.com/TAPSOSS/Walrio
- Documentation: See included docs/ folder
- Issues: Report on GitHub repository

---
© 2025 TAPS OSS - Licensed under BSD-3-Clause License
"""
        
        readme_file = self.dist_dir / "README.txt"
        with open(readme_file, 'w') as f:
            f.write(readme_content)
        
        print(f"Created {readme_file}")

def main():
    """Main build script entry point."""
    parser = argparse.ArgumentParser(description="Build Walrio GUIs with PyInstaller")
    parser.add_argument("--gui", choices=["main", "lite", "both"], default="both",
                       help="Which GUI to build (default: both)")
    parser.add_argument("--clean", action="store_true", 
                       help="Clean build directories before building")
    parser.add_argument("--debug", action="store_true",
                       help="Build in debug mode (onedir instead of onefile)")
    parser.add_argument("--no-deps-check", action="store_true",
                       help="Skip dependency checking")
    
    args = parser.parse_args()
    
    print("Walrio GUI Build Script")
    print("=" * 50)
    
    builder = WalrioBuildScript()
    
    # Check dependencies
    if not args.no_deps_check:
        if not builder.check_dependencies():
            sys.exit(1)
    
    # Clean if requested
    if args.clean:
        builder.clean_build_dirs()
    
    # Determine which GUIs to build
    guis_to_build = []
    if args.gui in ["main", "both"]:
        guis_to_build.append("walrio_main")
    if args.gui in ["lite", "both"]:
        guis_to_build.append("walrio_lite")
    
    # Build GUIs
    built_guis = []
    success_count = 0
    
    for gui_type in guis_to_build:
        if builder.build_gui(gui_type, debug=args.debug):
            built_guis.append(gui_type)
            success_count += 1
    
    # Create additional files
    if built_guis:
        builder.create_build_info(built_guis)
        builder.create_launcher_scripts()
        builder.create_readme()
    
    # Summary
    print("\n" + "=" * 50)
    print(f"Build Complete! ({success_count}/{len(guis_to_build)} successful)")
    
    if built_guis:
        print(f"Output directory: {builder.dist_dir}")
        print("Built applications:")
        for gui in built_guis:
            config = builder.configs[gui]
            extension = builder.platform_configs[builder.platform]["extension"]
            executable = builder.dist_dir / f"{config['name']}{extension}"
            print(f"  - {executable}")
    
    if success_count != len(guis_to_build):
        sys.exit(1)

if __name__ == "__main__":
    main()