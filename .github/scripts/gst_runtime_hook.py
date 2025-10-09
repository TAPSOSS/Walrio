
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
