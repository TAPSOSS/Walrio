#!/usr/bin/env python3
"""
Walrio GUI Build Script
Copyright (c) 2025 TAPS OSS
Project: https://github.com/TAPSOSS/Walrio
Licensed under the BSD-3-Clause License (see LICENSE file for details)

Clean implementation using Strawberry Music Player-inspired environment-based GStreamer bundling.
Builds 6 executables total: 2 GUIs (Main/Lite) × 3 platforms (Linux/macOS/Windows).
"""

import os
import sys
import subprocess
import shutil
import platform
import argparse
import json
from pathlib import Path


class WalrioBuildError(Exception):
    """Custom exception for build errors."""
    pass


def run_command(cmd, check=True, capture_output=False):
    """Execute shell command with proper error handling."""
    if isinstance(cmd, list):
        cmd_str = ' '.join(cmd)
    else:
        cmd_str = cmd
        cmd = cmd.split()
    
    print(f"Running: {cmd_str}")
    
    try:
        if capture_output:
            result = subprocess.run(cmd, check=check, capture_output=True, text=True)
            return result
        else:
            subprocess.run(cmd, check=check)
            return None
    except subprocess.CalledProcessError as e:
        if check:
            error_msg = f"Command failed: {cmd_str}"
            if hasattr(e, 'stderr') and e.stderr:
                error_msg += f"\nError: {e.stderr}"
            raise WalrioBuildError(error_msg) from e
        return e


def find_gstreamer_paths():
    """Find GStreamer installation paths using multiple detection methods."""
    system = platform.system().lower()
    
    # Try pkg-config first
    try:
        result = run_command(
            ["pkg-config", "--variable=pluginsdir", "gstreamer-1.0"], 
            capture_output=True, check=False
        )
        if result.returncode == 0 and result.stdout.strip():
            plugins_dir = result.stdout.strip()
            gst_base = Path(plugins_dir).parent
            print(f"Found GStreamer via pkg-config at: {gst_base}")
            
            # Find typelibs directory
            if system == "linux":
                typelib_dir = gst_base / "girepository-1.0"
                if not typelib_dir.exists():
                    # Try alternate locations
                    alt_paths = [
                        Path("/usr/lib/girepository-1.0"),
                        Path("/usr/lib/x86_64-linux-gnu/girepository-1.0"), 
                        Path("/usr/local/lib/girepository-1.0")
                    ]
                    for alt_path in alt_paths:
                        if alt_path.exists():
                            typelib_dir = alt_path
                            break
            else:
                typelib_dir = gst_base / "girepository-1.0"
            
            return {
                "plugins_dir": Path(plugins_dir),
                "typelibs_dir": typelib_dir,
                "system": system
            }
    except:
        pass
    
    # Fallback to common installation paths
    print("pkg-config not available, trying common GStreamer paths...")
    
    if system == "linux":
        # Common Linux paths
        common_paths = [
            ("/usr/lib64/gstreamer-1.0", "/usr/lib64/girepository-1.0"),
            ("/usr/lib/gstreamer-1.0", "/usr/lib/girepository-1.0"),
            ("/usr/lib/x86_64-linux-gnu/gstreamer-1.0", "/usr/lib/x86_64-linux-gnu/girepository-1.0"),
            ("/usr/local/lib/gstreamer-1.0", "/usr/local/lib/girepository-1.0")
        ]
    elif system == "darwin":
        # macOS paths (Homebrew)
        common_paths = [
            ("/opt/homebrew/lib/gstreamer-1.0", "/opt/homebrew/lib/girepository-1.0"),
            ("/usr/local/lib/gstreamer-1.0", "/usr/local/lib/girepository-1.0")
        ]
    elif system == "windows":
        # Windows MSYS2 paths
        common_paths = [
            ("C:/msys64/mingw64/lib/gstreamer-1.0", "C:/msys64/mingw64/lib/girepository-1.0"),
            ("C:/tools/msys64/mingw64/lib/gstreamer-1.0", "C:/tools/msys64/mingw64/lib/girepository-1.0")
        ]
    else:
        raise WalrioBuildError(f"Unsupported platform: {system}")
    
    # Try each path combination
    for plugins_path, typelibs_path in common_paths:
        plugins_dir = Path(plugins_path)
        typelibs_dir = Path(typelibs_path)
        
        if plugins_dir.exists() and typelibs_dir.exists():
            print(f"Found GStreamer at: {plugins_dir.parent}")
            return {
                "plugins_dir": plugins_dir,
                "typelibs_dir": typelibs_dir,
                "system": system
            }
    
    raise WalrioBuildError(f"GStreamer installation not found on {system}. Please install GStreamer development packages.")


def validate_gstreamer_paths(gst_paths):
    """Validate that GStreamer paths exist and contain required files."""
    plugins_dir = gst_paths["plugins_dir"]
    typelibs_dir = gst_paths["typelibs_dir"]
    
    if not plugins_dir.exists():
        raise WalrioBuildError(f"GStreamer plugins directory not found: {plugins_dir}")
        
    if not typelibs_dir.exists():
        raise WalrioBuildError(f"GI typelib directory not found: {typelibs_dir}")
    
    # Count available plugins and typelibs
    plugin_files = list(plugins_dir.glob("*.so" if gst_paths["system"] != "windows" else "*.dll"))
    typelib_files = list(typelibs_dir.glob("*.typelib"))
    
    if len(plugin_files) == 0:
        raise WalrioBuildError(f"No GStreamer plugins found in {plugins_dir}")
        
    if len(typelib_files) == 0:
        raise WalrioBuildError(f"No GI typelib files found in {typelibs_dir}")
    
    print(f"GStreamer validation passed:")
    print(f"  Plugins: {len(plugin_files)} files in {plugins_dir}")
    print(f"  TypeLibs: {len(typelib_files)} files in {typelibs_dir}")


def create_gstreamer_bundle(dist_dir, gst_paths):
    """Create GStreamer bundle structure using Strawberry's approach."""
    system = gst_paths["system"]
    plugins_src = gst_paths["plugins_dir"]
    typelibs_src = gst_paths["typelibs_dir"]
    
    # Create bundle directories based on platform
    bundle_plugins_dir = dist_dir / "plugins" / "gstreamer"
    bundle_typelibs_dir = dist_dir / "plugins" / "girepository-1.0"
    
    # Create directories
    bundle_plugins_dir.mkdir(parents=True, exist_ok=True)
    bundle_typelibs_dir.mkdir(parents=True, exist_ok=True)
    
    # Copy GStreamer plugins
    plugin_count = 0
    for plugin_file in plugins_src.glob("*.so" if system != "windows" else "*.dll"):
        shutil.copy2(plugin_file, bundle_plugins_dir)
        plugin_count += 1
    
    # Copy GI typelib files
    typelib_count = 0
    for typelib_file in typelibs_src.glob("*.typelib"):
        shutil.copy2(typelib_file, bundle_typelibs_dir)
        typelib_count += 1
    
    # Create configuration file for runtime
    config_file = dist_dir / "gstreamer_config.txt"
    config_content = f"""plugins_path=dist/plugins/gstreamer
typelibs_path=dist/plugins/girepository-1.0
system={system}"""
    
    with open(config_file, 'w') as f:
        f.write(config_content)
    
    print(f"Bundling GStreamer plugins: {plugins_src} -> {bundle_plugins_dir}")
    print(f"Bundling GI typelibs: {typelibs_src} -> {bundle_typelibs_dir}")
    print(f"Created {system} bundle structure with {plugin_count} plugins")
    
    return {
        "plugins_path": f"dist/plugins/gstreamer",
        "typelibs_path": f"dist/plugins/girepository-1.0", 
        "config_path": f"dist/gstreamer_config.txt",
        "plugin_count": plugin_count,
        "typelib_count": typelib_count
    }


def build_pyinstaller_command(gui_name, entry_point, debug=False):
    """Build streamlined PyInstaller command without --add-binary."""
    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--onefile" if not debug else "--onedir",
        "--console",  # Use console mode for better debugging
        f"--name={gui_name}",
    ]
    
    # Add data files
    data_dirs = ["modules", "testing_files"]
    for data_dir in data_dirs:
        cmd.extend(["--add-data", f"{data_dir}:{data_dir}"])
    
    # Add runtime hook for GStreamer environment setup
    hook_path = Path(".github/scripts/gst_runtime_hook.py")
    cmd.extend(["--runtime-hook", str(hook_path)])
    
    # Essential hidden imports (streamlined to reduce warnings)
    essential_imports = [
        "gi", "gi.repository.Gtk", "gi.repository.GObject", "gi.repository.Gio",
        "gi.repository.GLib", "gi.repository.Gst", "gi.repository.GstBase", 
        "gi.repository.GstAudio", "gi.repository.GstPbutils", "_gi", "cairo"
    ]
    
    for import_name in essential_imports:
        cmd.extend(["--hidden-import", import_name])
    
    # Exclude unnecessary modules to reduce build size and warnings
    excludes = [
        "tkinter", "matplotlib", "numpy", "scipy", "pandas", 
        "IPython", "jupyter", "sphinx", "pytest"
    ]
    for exclude in excludes:
        cmd.extend(["--exclude-module", exclude])
    
    # Add entry point
    cmd.append(str(entry_point))
    
    return cmd


def cleanup_build_artifacts():
    """Clean up previous build artifacts."""
    artifacts_to_clean = [
        "dist", "build", "*.spec",
        "__pycache__", "*.pyc", "*.pyo"
    ]
    
    for pattern in artifacts_to_clean:
        for path in Path(".").glob(pattern):
            if path.exists():
                if path.is_dir():
                    shutil.rmtree(path)
                else:
                    path.unlink()
    
    print("Build artifacts cleaned up")


class WalrioBuilder:
    """Main build coordinator for Walrio GUIs."""
    
    def __init__(self):
        """Initialize builder with project structure."""
        self.root_dir = Path(".").absolute()
        self.dist_dir = self.root_dir / "dist"
        
        # GUI configurations
        self.gui_configs = {
            "main": {
                "name": "WalrioMain",
                "entry_point": "GUI/walrio_main.py",
                "description": "Full-featured Walrio music player"
            },
            "lite": {
                "name": "WalrioLite", 
                "entry_point": "GUI/walrio_lite.py",
                "description": "Lightweight Walrio music player"
            }
        }
        
        # Platform detection
        self.platform = platform.system().lower()
        self.platform_extension = ".exe" if self.platform == "windows" else ""
        
    def check_dependencies(self):
        """Check that all required dependencies are available."""
        print("Checking dependencies...")
        
        # Check PyInstaller
        try:
            import PyInstaller
            print("  [OK] PyInstaller - installed")
        except ImportError:
            print("  [ERROR] PyInstaller - not installed")
            return False
        
        # Check PySide6
        try:
            import PySide6
            print("  [OK] PySide6 - installed")
        except ImportError:
            print("  [ERROR] PySide6 - not installed")
            return False
            
        # Check mutagen
        try:
            import mutagen
            print("  [OK] mutagen - installed")
        except ImportError:
            print("  [ERROR] mutagen - not installed")
            return False
        
        # Check GStreamer/PyGObject
        try:
            import gi
            gi.require_version('Gst', '1.0')
            from gi.repository import Gst
            result = Gst.init_check(None)
            if result:
                print("  [OK] GStreamer - installed and initialized")
            else:
                print("  [WARNING] GStreamer - installed but failed to initialize")
            return result
        except Exception as e:
            print(f"  [ERROR] GStreamer - {e}")
            return False
    
    def build_gui(self, gui_type, debug=False):
        """Build a specific GUI using the Strawberry approach."""
        if gui_type not in self.gui_configs:
            raise WalrioBuildError(f"Unknown GUI type: {gui_type}")
        
        config = self.gui_configs[gui_type]
        entry_path = self.root_dir / config["entry_point"]
        
        if not entry_path.exists():
            raise WalrioBuildError(f"Entry point not found: {entry_path}")
        
        print(f"\nBuilding {config['name']} ({config['description']})...")
        
        # Build PyInstaller command
        cmd = build_pyinstaller_command(config["name"], entry_path, debug)
        
        print("Built streamlined PyInstaller command with runtime environment setup")
        print("PyInstaller command:")
        print(' '.join(cmd))
        print()
        
        # Execute build
        run_command(cmd)
        
        # Verify executable was created
        exe_name = config["name"] + self.platform_extension
        exe_path = self.dist_dir / exe_name
        
        if not exe_path.exists():
            raise WalrioBuildError(f"Expected executable not found: {exe_path}")
        
        print(f"✅ {config['name']} built successfully")
        return True
    
    def create_build_info(self, built_guis, bundle_info):
        """Create build information file."""
        build_info = {
            "build_timestamp": __import__("datetime").datetime.now().isoformat(),
            "platform": self.platform,
            "guis_built": built_guis,
            "gstreamer_bundle": bundle_info,
            "python_version": sys.version,
            "builder_version": "2.0.0-strawberry"
        }
        
        info_file = self.dist_dir / "build_info.json"
        with open(info_file, 'w') as f:
            json.dump(build_info, f, indent=2)
        
        print(f"Build info saved to {info_file}")
    
    def create_launcher_scripts(self):
        """Create platform-specific launcher scripts."""
        if self.platform == "linux":
            # Create .desktop files for Linux
            for gui_name, config in self.gui_configs.items():
                desktop_content = f"""[Desktop Entry]
Name={config["name"]}
Comment={config["description"]}
Exec={self.dist_dir / config["name"]}
Icon=walrio
Terminal=false
Type=Application
Categories=AudioVideo;Audio;Player;
"""
                desktop_file = self.dist_dir / f"{gui_name}.desktop"
                with open(desktop_file, 'w') as f:
                    f.write(desktop_content)
                print(f"  Created {desktop_file}")
        
        elif self.platform == "windows":
            # Create batch files for Windows
            for gui_name, config in self.gui_configs.items():
                batch_content = f"""@echo off
cd /d "%~dp0"
{config["name"]}.exe %*
"""
                batch_file = self.dist_dir / f"{config['name']}.bat"
                with open(batch_file, 'w') as f:
                    f.write(batch_content)
                print(f"  Created {batch_file}")
    
    def create_readme(self):
        """Create README file for distribution."""
        readme_content = f"""Walrio Music Player - Distribution Package
=========================================

This package contains the Walrio music player executables built for {self.platform}.

Contents:
"""
        
        # List executables
        for config in self.gui_configs.values():
            exe_name = config["name"] + self.platform_extension
            exe_path = self.dist_dir / exe_name
            if exe_path.exists():
                readme_content += f"  - {exe_name}: {config['description']}\n"
        
        readme_content += f"""
GStreamer Configuration:
  - Plugins bundled in: plugins/gstreamer/
  - TypeLibs bundled in: plugins/girepository-1.0/
  - Runtime configuration: gstreamer_config.txt

Platform: {self.platform}
Build Date: {__import__("datetime").datetime.now().strftime("%Y-%m-%d %H:%M:%S")}

For more information, visit: https://github.com/TAPSOSS/Walrio
"""
        
        readme_file = self.dist_dir / "README.txt"
        with open(readme_file, 'w') as f:
            f.write(readme_content)
        
        print(f"Created {readme_file}")


def main():
    """Main build script entry point."""
    parser = argparse.ArgumentParser(
        description="Build Walrio GUIs with Strawberry-inspired GStreamer bundling"
    )
    parser.add_argument(
        "--gui", 
        choices=["main", "lite", "both"], 
        default="both",
        help="Which GUI to build (default: both)"
    )
    parser.add_argument(
        "--clean", 
        action="store_true", 
        help="Clean build directories before building"
    )
    parser.add_argument(
        "--debug", 
        action="store_true",
        help="Build in debug mode (onedir instead of onefile)"
    )
    parser.add_argument(
        "--no-deps-check", 
        action="store_true",
        help="Skip dependency checking"
    )
    
    args = parser.parse_args()
    
    print("Walrio GUI Build Script")
    print("Using Strawberry Music Player-inspired environment-based GStreamer bundling")
    print("=" * 70)
    
    try:
        builder = WalrioBuilder()
        
        # Clean if requested  
        if args.clean:
            print("Cleaning previous build directories...")
            cleanup_build_artifacts()
        
        # Check dependencies
        if not args.no_deps_check:
            if not builder.check_dependencies():
                raise WalrioBuildError("Dependency check failed")
        
        # Detect and validate GStreamer
        print("\nDetecting GStreamer installation...")
        gst_paths = find_gstreamer_paths()
        validate_gstreamer_paths(gst_paths)
        
        # Determine which GUIs to build
        if args.gui == "both":
            guis_to_build = ["main", "lite"]
        else:
            guis_to_build = [args.gui]
        
        # Build GUIs
        built_guis = []
        for gui_type in guis_to_build:
            if builder.build_gui(gui_type, debug=args.debug):
                built_guis.append(gui_type)
        
        # Create GStreamer bundle structure
        print("\nCreating GStreamer bundle structure...")
        bundle_info = create_gstreamer_bundle(builder.dist_dir, gst_paths)
        
        # Create additional files
        if built_guis:
            builder.create_build_info(built_guis, bundle_info)
            print("\nCreating launcher scripts...")
            builder.create_launcher_scripts()
            builder.create_readme()
        
        # Summary
        print("\n" + "=" * 70)
        print(f"✅ Build completed successfully! ({len(built_guis)}/{len(guis_to_build)} GUIs built)")
        print(f"📁 Executable location: {builder.dist_dir}/")
        print(f"🎵 GStreamer plugins: {bundle_info['plugins_path']} ({bundle_info['plugin_count']} plugins)")
        print(f"📚 TypeLib files: {bundle_info['typelibs_path']} ({bundle_info['typelib_count']} files)")
        print(f"⚙️  Configuration: {bundle_info['config_path']}")
        print("\nBuilt applications:")
        for gui_type in built_guis:
            config = builder.gui_configs[gui_type]
            exe_name = config["name"] + builder.platform_extension
            print(f"  - {builder.dist_dir / exe_name}")
        print("\nThe applications will configure GStreamer environment at runtime.")
        
        if len(built_guis) != len(guis_to_build):
            sys.exit(1)
            
    except WalrioBuildError as e:
        print(f"\n❌ Build failed: {e}")
        sys.exit(1)
    except KeyboardInterrupt:
        print("\n⚠️  Build interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n💥 Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
