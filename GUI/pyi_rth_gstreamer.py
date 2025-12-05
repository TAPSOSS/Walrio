"""
GStreamer Runtime Hook
Copyright (c) 2025 TAPS OSS
Project: https://github.com/TAPSOSS/Walrio
Licensed under the BSD-3-Clause License (see LICENSE file for details)

PyInstaller runtime hook for GStreamer that sets up environment variables
so GStreamer can find bundled plugins and typelibs on Linux, Windows, and macOS.
"""
import os
import sys

# Set GStreamer plugin path to bundled plugins
if hasattr(sys, '_MEIPASS'):
    # Running as PyInstaller bundle
    bundle_dir = sys._MEIPASS
    
    # Check for _internal directory (onedir mode)
    internal_dir = os.path.join(os.path.dirname(sys.executable), '_internal')
    if os.path.exists(internal_dir):
        bundle_dir = internal_dir
    
    # Set plugin path
    gst_plugin_path = os.path.join(bundle_dir, 'gst_plugins')
    if os.path.exists(gst_plugin_path):
        os.environ['GST_PLUGIN_PATH'] = gst_plugin_path
        print(f"[Walrio] GStreamer plugin path: {gst_plugin_path}")
        if '--debug-gst' in sys.argv:
            print(f"GStreamer: Debug - Plugin path set to {gst_plugin_path}")
    
    # Set plugin scanner to bundled version
    gst_scanner_path = os.path.join(bundle_dir, 'gst_helpers', 'gst-plugin-scanner')
    if os.path.exists(gst_scanner_path):
        os.environ['GST_PLUGIN_SCANNER'] = gst_scanner_path
        print(f"[Walrio] GStreamer plugin scanner: {gst_scanner_path}")
    else:
        # Disable system plugin scanner if we don't have our own
        os.environ['GST_PLUGIN_SCANNER'] = ''
        print("[Walrio] GStreamer plugin scanner: disabled (not found)")
    
    # Set typelib path for GObject introspection
    gi_typelib_path = os.path.join(bundle_dir, 'gi_typelibs')
    if os.path.exists(gi_typelib_path):
        os.environ['GI_TYPELIB_PATH'] = gi_typelib_path
        print(f"[Walrio] GI typelib path: {gi_typelib_path}")
        if '--debug-gst' in sys.argv:
            print(f"GStreamer: Debug - Typelib path set to {gi_typelib_path}")
    
    # Disable system plugins completely to avoid conflicts
    os.environ['GST_PLUGIN_SYSTEM_PATH_1_0'] = ''
    print("[Walrio] GStreamer: System plugins disabled")
    
    # Set registry to a writable location
    if sys.platform == 'win32':
        cache_dir = os.path.join(os.environ.get('LOCALAPPDATA', os.path.expanduser('~')), 'Walrio', 'cache')
    elif sys.platform == 'darwin':
        cache_dir = os.path.expanduser('~/Library/Caches/Walrio')
    else:  # Linux
        cache_dir = os.path.expanduser('~/.cache/walrio')
    
    os.makedirs(cache_dir, exist_ok=True)
    registry_path = os.path.join(cache_dir, 'gstreamer-registry.bin')
    os.environ['GST_REGISTRY'] = registry_path
    
    # Force registry fork to ensure child processes can update registry
    os.environ['GST_REGISTRY_FORK'] = 'yes'
    
    # Don't disable registry updates - let GStreamer update if needed
    # This ensures plugins are properly registered on first run or after updates
    
    if '--debug-gst' in sys.argv:
        print(f"GStreamer: Registry set to {registry_path}")
        print(f"GStreamer: Debug mode enabled")
        os.environ['GST_DEBUG'] = '2'
