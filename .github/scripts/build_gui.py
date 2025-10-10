#!/usr/bin/env python3
"""
Walrio Lite GUI - Standalone launcher
Copyright (c) 2025 TAPS OSS  
Project: https://github.com/TAPSOSS/Walrio
Licensed under the BSD-3-Clause License (see LICENSE file for details)

Simplified Walrio GUI Build Script.
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
        
        def build_gui(self, gui_name, debug=False):
            cmd.append("--windowed")  # No console on Windows
        
        # Essential hidden imports for GUI functionality
        hidden_imports = [
            # PySide6 essentials
            "PySide6.QtCore", "PySide6.QtGui", "PySide6.QtWidgets",
            "PySide6.QtNetwork", "shiboken6",
            
            # Audio metadata
            "mutagen", "mutagen.mp3", "mutagen.flac", "mutagen.oggvorbis", 
            "mutagen.mp4", "mutagen.wave", "mutagen.opus",
            
            # GStreamer - ensure GStreamer backend is bundled
            "gi", "gi.repository.Gst",
            
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
            self.bundle_gstreamer_libraries()
            return self.dist_dir / config['name']
        else:
            raise WalrioBuildError(f"PyInstaller failed for {gui_name} (exit code {result.returncode})")

    def bundle_gstreamer_libraries(self):
        """Copy only essential GStreamer audio plugins and libraries into dist/ directory."""
        print("[Walrio Build] Bundling essential GStreamer audio plugins and libraries...")
        import glob
        gst_plugin_dirs = ["/usr/lib64/gstreamer-1.0", "/usr/lib/gstreamer-1.0"]
        gst_lib_dirs = ["/usr/lib64", "/usr/lib"]
        dist_dir = self.dist_dir
        essential_plugins = [
            "libgstcoreelements.so", "libgstplayback.so", "libgstdecodebin.so", "libgstogg.so", "libgstflac.so",
            "libgstmp3.so", "libgstaac.so", "libgstwavparse.so", "libgstvorbis.so", "libgstopus.so",
            "libgstmad.so", "libgstfaad.so", "libgstwavpack.so", "libgsttag.so", "libgstvolume.so",
            "libgstalsa.so", "libgstpulseaudio.so", "libgstapp.so", "libgstresample.so", "libgstsegmentclip.so"
        ]
        copied = False
        for plugin_dir in gst_plugin_dirs:
            if os.path.isdir(plugin_dir):
                dest = dist_dir / "gstreamer-1.0"
                os.makedirs(dest, exist_ok=True)
                for plugin in essential_plugins:
                    src_plugin = os.path.join(plugin_dir, plugin)
                    if os.path.isfile(src_plugin):
                        shutil.copy2(src_plugin, dest)
                        print(f"  Copied {plugin} to {dest}")
                        copied = True
        for lib_dir in gst_lib_dirs:
            if os.path.isdir(lib_dir):
                for sofile in glob.glob(os.path.join(lib_dir, "libgst*so*")):
                    shutil.copy2(sofile, dist_dir)
                    print(f"  Copied {sofile} to {dist_dir}")
                    copied = True
        if not copied:
            print("  WARNING: No essential GStreamer audio plugins/libraries found to bundle.")
        else:
            print("[Walrio Build] Essential GStreamer audio plugins and libraries bundled.")
    
    def create_launcher_scripts(self):
        """Create desktop launcher files."""
        print("Creating launcher scripts...")
        for gui_name, config in self.gui_configs.items():
            # Desktop file for Linux
            desktop_content = f"""[Desktop Entry]
Name={config['name']}
Comment={config['description']}
Exec={config['name']}"""
            # ... rest of launcher script code ...

    def create_readme(self):
        """Create a README for the distribution."""
        readme_content = (
            "# Walrio Music Player - Portable Distribution\n"
            "\n"
            "## System Requirements\n"
            "- GStreamer (shared libraries bundled)\n"
            "- Audio system (PulseAudio, PipeWire, or ALSA)\n"
            "\n"
            "## Installation\n"
            "1. Run the executable directly - no additional installation needed\n"
            "\n"
            "## Usage\n"
            "- WalrioMain: Full-featured music player\n"
            "- WalrioLite: Lightweight version\n"
            "\n"
            "The applications will automatically use the bundled GStreamer libraries.\n"
        )
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