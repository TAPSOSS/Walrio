#!/usr/bin/env python3
"""
Simplified Walrio GUI Build Script
Let PyInstaller handle GStreamer, we only manage essential dependencies.
"""

import argparse
import sys
import shutil
import subprocess
import os
from pathlib import Path


class WalrioBuildError(Exception):
    """Custom exception for build errors."""
    pass


def run_command(cmd, check=True):
    """Execute shell command with proper error handling."""
    if isinstance(cmd, list):
        cmd_str = ' '.join(cmd)
    else:
        cmd_str = cmd
        cmd = cmd.split()
    
    print(f"Running: {cmd_str}")
    
    try:
        result = subprocess.run(cmd, check=check, capture_output=True, text=True)
        if result.stdout.strip():
            print(result.stdout)
        return result
    except subprocess.CalledProcessError as e:
        print(f"Command failed: {e}")
        if e.stderr:
            print(f"Error output: {e.stderr}")
        if check:
            raise WalrioBuildError(f"Command failed: {e}")
        return e


class SimpleWalrioBuilder:
    """Simplified builder that lets PyInstaller handle everything properly."""
    
    def __init__(self, clean=False):
        self.root_dir = Path.cwd()
        self.dist_dir = self.root_dir / "dist"
        self.build_dir = self.root_dir / "build"
        
        # GUI configurations
        self.gui_configs = {
            "main": {
                "name": "WalrioMain",
                "entry": "GUI/walrio_main.py",
                "description": "Full-featured music player"
            },
            "lite": {
                "name": "WalrioLite", 
                "entry": "GUI/walrio_lite.py",
                "description": "Lightweight music player"
            }
        }
        
        if clean:
            self.cleanup_build_artifacts()
    
    def cleanup_build_artifacts(self):
        """Clean previous build artifacts."""
        print("Cleaning previous build artifacts...")
        
        for path in [self.dist_dir, self.build_dir]:
            if path.exists():
                shutil.rmtree(path)
                print(f"Removed {path}")
        
        # Remove spec files
        for spec_file in self.root_dir.glob("*.spec"):
            spec_file.unlink()
            print(f"Removed {spec_file}")
    
    def build_gui(self, gui_name, debug=False):
        """Build a GUI application using PyInstaller."""
        if gui_name not in self.gui_configs:
            raise WalrioBuildError(f"Unknown GUI: {gui_name}")
        
        config = self.gui_configs[gui_name]
        entry_point = self.root_dir / config["entry"]
        
        if not entry_point.exists():
            raise WalrioBuildError(f"Entry point not found: {entry_point}")
        
        print(f"\n[Walrio Build] Building {config['name']} ({config['description']})...")
        print(f"[Walrio Build] Entry point: {entry_point}")
        print(f"[Walrio Build] Dist dir: {self.dist_dir}")
        print(f"[Walrio Build] Build dir: {self.build_dir}")
        
        # Build PyInstaller command - let it handle everything
        cmd = [
            "pyinstaller",
            "--onefile",
            f"--name={config['name']}",
            f"--distpath={self.dist_dir}",
            f"--workpath={self.build_dir}",
        ]
        
        if not debug:
            cmd.append("--windowed")  # No console on Windows
        
        # Essential hidden imports for GUI functionality
        hidden_imports = [
            # PySide6 essentials
            "PySide6.QtCore", "PySide6.QtGui", "PySide6.QtWidgets",
            "PySide6.QtNetwork", "shiboken6",
            
            # Audio metadata
            "mutagen", "mutagen.mp3", "mutagen.flac", "mutagen.oggvorbis", 
            "mutagen.mp4", "mutagen.wave", "mutagen.opus",
            
            # GStreamer - let PyInstaller handle the rest
            "gi", "gi.repository.Gst", "gi.repository.GstBase", 
            "gi.repository.GstAudio", "gi.repository.GObject",
            
            # Walrio modules (ensure package hierarchy is bundled)
            "modules", "modules.core",
            "modules.core.metadata", "modules.core.playlist", 
            "modules.core.player", "modules.core.queue",
            
            # Standard library essentials  
            "sqlite3", "json", "threading", "pathlib", "tempfile",
            "PIL", "PIL.Image"
        ]
        
        print("[Walrio Build] Adding hidden imports:")
        for import_name in hidden_imports:
            print(f"  [hidden-import] {import_name}")
            cmd.extend(["--hidden-import", import_name])
        
        # Exclude unnecessary modules to reduce size
        excludes = [
            "tkinter", "matplotlib", "numpy", "scipy", "pandas",
            "IPython", "jupyter", "sphinx", "pytest", "test"
        ]
        print("[Walrio Build] Excluding modules:")
        for exclude in excludes:
            print(f"  [exclude-module] {exclude}")
            cmd.extend(["--exclude-module", exclude])
        
        # Add module paths
        gui_path = str(self.root_dir / "GUI")
        modules_path = str(self.root_dir / "modules")
        print(f"[Walrio Build] Adding paths: GUI={gui_path}, modules={modules_path}")
        cmd.extend([
            "--paths", gui_path,
            "--paths", modules_path
        ])

        # Bundle the entire modules directory as data
        modules_dir = str(self.root_dir / "modules")
        sep = ';' if sys.platform.startswith('win') else ':'
        add_data_arg = f"{modules_dir}{sep}modules"
        print(f"[Walrio Build] Adding data: {add_data_arg}")
        cmd.extend(["--add-data", add_data_arg])
        
        # Entry point
        cmd.append(str(entry_point))
        print(f"[Walrio Build] Final PyInstaller command:")
        print('  ' + ' '.join(cmd))
        print("[Walrio Build] Running PyInstaller...")
        result = run_command(cmd, check=False)
        print(f"[Walrio Build] PyInstaller exited with code: {result.returncode}")
        if result.stdout:
            print(f"[Walrio Build] PyInstaller stdout:\n{result.stdout}")
        if result.stderr:
            print(f"[Walrio Build] PyInstaller stderr:\n{result.stderr}")
        if result.returncode == 0:
            print(f"[Walrio Build] {config['name']} built successfully")
            return self.dist_dir / config['name']
        else:
            raise WalrioBuildError(f"PyInstaller failed for {gui_name} (exit code {result.returncode})")
    
    def create_launcher_scripts(self):
        """Create desktop launcher files."""
        print("Creating launcher scripts...")
        
        for gui_name, config in self.gui_configs.items():
            # Desktop file for Linux
            desktop_content = f"""[Desktop Entry]
Name={config['name']}
Comment={config['description']}
Exec={config['name']}
Icon=audio-player
Terminal=false
Type=Application
Categories=AudioVideo;Audio;Player;
"""
            desktop_file = self.dist_dir / f"{gui_name}.desktop"
            desktop_file.write_text(desktop_content)
            print(f"  Created {desktop_file}")
    
    def create_readme(self):
        """Create a README for the distribution."""
        readme_content = """# Walrio Music Player - Portable Distribution

## System Requirements
- GStreamer 1.0 with plugins (gstreamer1.0-plugins-base, gstreamer1.0-plugins-good)
- Audio system (PulseAudio, PipeWire, or ALSA)

## Installation
1. Install GStreamer on your system:
   - Ubuntu/Debian: `sudo apt install gstreamer1.0-plugins-base gstreamer1.0-plugins-good`
   - Fedora: `sudo dnf install gstreamer1-plugins-base gstreamer1-plugins-good`
   - Arch: `sudo pacman -S gstreamer gst-plugins-base gst-plugins-good`

2. Run the executable directly - no additional installation needed

## Usage
- WalrioMain: Full-featured music player
- WalrioLite: Lightweight version

The applications will automatically use your system's GStreamer installation.
"""
        readme_file = self.dist_dir / "README.txt"
        readme_file.write_text(readme_content)
        print(f"Created {readme_file}")


def main():
    parser = argparse.ArgumentParser(description="Build Walrio GUI applications")
    parser.add_argument("--gui", choices=["main", "lite", "all"], default="all",
                        help="Which GUI to build")
    parser.add_argument("--clean", action="store_true", 
                        help="Clean build artifacts first")
    parser.add_argument("--debug", action="store_true",
                        help="Build with debug console")
    parser.add_argument("--no-deps-check", action="store_true",
                        help="Skip dependency checks")
    
    args = parser.parse_args()
    
    try:
        # Create builder
        builder = SimpleWalrioBuilder(clean=args.clean)
        
        # Determine what to build
        if args.gui == "all":
            guis_to_build = ["main", "lite"]
        else:
            guis_to_build = [args.gui]
        
        print(f"Building {len(guis_to_build)} GUI(s): {', '.join(guis_to_build)}")
        
        # Build each GUI
        built_executables = []
        for gui_name in guis_to_build:
            exe_path = builder.build_gui(gui_name, debug=args.debug)
            built_executables.append(exe_path)
        
        # Create additional files
        if len(built_executables) > 0:
            builder.create_launcher_scripts()
            builder.create_readme()
        
        # Summary
        print("\n" + "=" * 70)
        print(f"Build completed successfully! ({len(built_executables)}/{len(guis_to_build)} GUIs built)")
        print(f"Executable location: {builder.dist_dir}/")
        print("\nBuilt applications:")
        for exe_path in built_executables:
            print(f"  - {exe_path}")
        print("\nGStreamer will be handled by PyInstaller and your system installation.")
        
    except WalrioBuildError as e:
        print(f"\nBuild failed: {e}")
        sys.exit(1)
    except KeyboardInterrupt:
        print("\nBuild interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\nUnexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()