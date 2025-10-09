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
        self.root_dir = Path(__file__).parent.absolute()
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
                "icon": "assets/walrio_icon.ico" if self.platform == "windows" else "assets/walrio_icon.png",
                "console": False,
                "additional_data": [
                    ("modules", "modules"),
                    ("testing_files", "testing_files"),
                    ("assets", "assets")
                ]
            },
            "walrio_lite": {
                "entry_point": "GUI/walrio_lite.py", 
                "name": "WalrioLite",
                "icon": "assets/walrio_lite_icon.ico" if self.platform == "windows" else "assets/walrio_lite_icon.png",
                "console": False,
                "additional_data": [
                    ("modules", "modules"),
                    ("testing_files", "testing_files"),
                    ("assets", "assets")
                ]
            }
        }
        
        # Platform-specific settings
        self.platform_configs = {
            "linux": {
                "extension": "",
                "separator": ":",
                "hidden_imports": [
                    "gi", "gi.repository", "gi.repository.Gst", "gi.repository.GLib",
                    "PySide6", "PySide6.QtCore", "PySide6.QtWidgets", "PySide6.QtGui",
                    "mutagen", "sqlite3", "pathlib", "json", "PIL", "PIL.Image"
                ]
            },
            "darwin": {  # macOS
                "extension": ".app",
                "separator": ":",
                "hidden_imports": [
                    "gi", "gi.repository", "gi.repository.Gst", "gi.repository.GLib",
                    "PySide6", "PySide6.QtCore", "PySide6.QtWidgets", "PySide6.QtGui",
                    "mutagen", "sqlite3", "pathlib", "json", "Foundation", "AppKit", "PIL", "PIL.Image"
                ]
            },
            "windows": {
                "extension": ".exe",
                "separator": ";",
                "hidden_imports": [
                    "gi", "gi.repository", "gi.repository.Gst", "gi.repository.GLib",
                    "PySide6", "PySide6.QtCore", "PySide6.QtWidgets", "PySide6.QtGui",
                    "mutagen", "sqlite3", "pathlib", "json", "win32api", "win32gui", "PIL", "PIL.Image"
                ]
            }
        }

    def check_dependencies(self):
        """Check if required dependencies are installed."""
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
            print("  [OK] GStreamer - installed")
        except (ImportError, ValueError):
            print("  [WARNING] GStreamer - not found (audio playback may not work)")
            
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

    def build_gui(self, gui_type, debug=False):
        """Build a specific GUI with PyInstaller."""
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
            "--windowed" if not config["console"] else "",
        ]
        
        # Add icon if it exists
        icon_path = self.root_dir / config["icon"]
        if icon_path.exists():
            cmd.append(f"--icon={icon_path}")
        
        # Add hidden imports
        for import_name in platform_config["hidden_imports"]:
            cmd.append(f"--hidden-import={import_name}")
            
        # Add additional data
        for src, dst in config["additional_data"]:
            src_path = self.root_dir / src
            if src_path.exists():
                cmd.append(f"--add-data={src_path}{platform_config['separator']}{dst}")
        
        # Platform-specific options
        if self.platform == "darwin":
            cmd.extend([
                "--osx-bundle-identifier=org.tapsoss.walrio",
                f"--target-arch={self.arch}"
            ])
        elif self.platform == "windows":
            cmd.extend([
                "--version-file=version_info.txt" if (self.root_dir / "version_info.txt").exists() else ""
            ])
        
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
        """Create build information file."""
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