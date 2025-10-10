
"""
GStreamer Runtime Hook
Copyright (c) 2025 TAPS OSS
Project: https://github.com/TAPSOSS/Walrio
Licensed under the BSD-3-Clause License (see LICENSE file for details)

PyInstaller runtime hook to properly initialize GStreamer in bundled executables.
Sets up environment variables for GStreamer plugins and type libraries.
"""

import os
import sys
from pathlib import Path


def set_environment_variable(name, value, append=False):
    """Set environment variable with optional append mode."""
    if append and name in os.environ:
        separator = ";" if os.name == "nt" else ":"
        os.environ[name] = f"{value}{separator}{os.environ[name]}"
    else:
        os.environ[name] = str(value)
    print(f"Set {name}={os.environ[name]}")


def find_bundle_root():
    """Find the root directory of the bundled application."""
    if getattr(sys, 'frozen', False):
        # Running in PyInstaller bundle
        exe_path = Path(sys.executable)
        
        # Check if we're in a macOS .app bundle
        if "Contents/MacOS" in str(exe_path):
            return exe_path.parents[2]  # Go up to .app directory
        else:
            return exe_path.parent
    else:
        # Development mode
        return Path(__file__).parent.parent.parent


def setup_gstreamer_environment():
    """
    Configure GStreamer environment using Strawberry Music Player's approach.
    Sets up plugin paths, typelib paths, and registry location.
    """
    bundle_root = find_bundle_root()
    system = sys.platform
    
    print(f"Setting up GStreamer environment for {system}")
    print(f"Bundle root: {bundle_root}")
    
    # Platform-specific path configuration (following Strawberry's structure)
    if system.startswith("win"):
        # Windows: plugins in application directory
        plugins_path = bundle_root / "gstreamer-plugins"
        typelibs_path = bundle_root / "girepository-1.0"
        
    elif system == "darwin":
        # macOS: PlugIns directory in app bundle  
        if bundle_root.suffix == ".app":
            plugins_path = bundle_root / "Contents" / "PlugIns" / "gstreamer"
            typelibs_path = bundle_root / "Contents" / "PlugIns" / "girepository-1.0"
        else:
            plugins_path = bundle_root / "gstreamer"
            typelibs_path = bundle_root / "girepository-1.0"
            
    else:
        # Linux: ../plugins directory relative to executable
        plugins_path = bundle_root / "plugins" / "gstreamer"
        typelibs_path = bundle_root / "plugins" / "girepository-1.0"
    
    # Set GStreamer plugin paths
    if plugins_path.exists():
        # Set both plugin path and system path (Strawberry approach)
        set_environment_variable("GST_PLUGIN_PATH", plugins_path)
        set_environment_variable("GST_PLUGIN_SYSTEM_PATH", plugins_path)
        
        # Scan plugin directory 
        plugin_count = len(list(plugins_path.glob("*gst*")))
        print(f"Found {plugin_count} GStreamer plugins in {plugins_path}")
    else:
        print(f"Warning: GStreamer plugins not found at {plugins_path}")
    
    # Set GObject Introspection typelib path  
    if typelibs_path.exists():
        set_environment_variable("GI_TYPELIB_PATH", typelibs_path, append=True)
        
        # Count typelib files
        typelib_count = len(list(typelibs_path.glob("*.typelib")))
        print(f"Found {typelib_count} typelib files in {typelibs_path}")
    else:
        print(f"Warning: GI typelibs not found at {typelibs_path}")
    
    # Set custom GStreamer registry (following Strawberry's approach)
    if getattr(sys, 'frozen', False):
        # Create user-specific registry for bundled app
        import tempfile
        registry_dir = Path(tempfile.gettempdir()) / "walrio-gstreamer"
        registry_dir.mkdir(exist_ok=True)
        registry_file = registry_dir / "gst-registry.bin"
        
        set_environment_variable("GST_REGISTRY", registry_file)
        print(f"Using custom GStreamer registry: {registry_file}")
    
    # Additional GStreamer configuration
    # Disable external plugin scanning for security
    set_environment_variable("GST_PLUGIN_SCANNER_1_0", "")
    
    # Enable debug output for troubleshooting (can be disabled in production)
    if os.environ.get("WALRIO_DEBUG"):
        set_environment_variable("GST_DEBUG", "3")
        print("GStreamer debug output enabled")
    
    print("GStreamer environment configuration complete")


def verify_gstreamer_setup():
    """Verify that GStreamer can be imported and initialized."""
    try:
        import gi
        gi.require_version('Gst', '1.0')
        from gi.repository import Gst
        
        # Initialize GStreamer
        success = Gst.init_check(None)
        if success:
            print("✅ GStreamer initialized successfully")
            
            # Check plugin registry
            registry = Gst.Registry.get()
            plugin_count = len(registry.get_plugin_list())
            print(f"✅ GStreamer registry loaded with {plugin_count} plugins")
            
            return True
        else:
            print("❌ GStreamer initialization failed")
            return False
            
    except ImportError as e:
        print(f"❌ Failed to import GStreamer: {e}")
        return False
    except Exception as e:
        print(f"❌ GStreamer verification error: {e}")
        return False


# Execute setup when hook is loaded by PyInstaller
print("Initializing Walrio GStreamer environment...")
setup_gstreamer_environment()

# Verify setup in debug mode
if os.environ.get("WALRIO_DEBUG"):
    verify_gstreamer_setup()
