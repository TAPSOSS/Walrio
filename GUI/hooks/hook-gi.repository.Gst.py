"""
GStreamer PyInstaller Hook
Copyright (c) 2025 TAPS OSS
Project: https://github.com/TAPSOSS/Walrio
Licensed under the BSD-3-Clause License (see LICENSE file for details)

PyInstaller hook for GStreamer that collects all necessary GStreamer files 
(plugins, libraries, and typelibs) for bundling on Linux, Windows, and macOS.
"""
from PyInstaller.utils.hooks import collect_dynamic_libs, collect_data_files
import os
import sys
import glob

# Collect GStreamer typelibs
datas = []
binaries = []

if sys.platform.startswith('linux'):
    # LINUX - Prioritize 64-bit paths for 64-bit Python
    import platform
    is_64bit = platform.machine() == 'x86_64' or sys.maxsize > 2**32
    
    if is_64bit:
        typelib_paths = [
            '/usr/lib64/girepository-1.0',
            '/usr/lib/x86_64-linux-gnu/girepository-1.0',
            '/usr/lib/girepository-1.0'
        ]
    else:
        typelib_paths = [
            '/usr/lib/girepository-1.0',
            '/usr/lib/x86_64-linux-gnu/girepository-1.0',
            '/usr/lib64/girepository-1.0'
        ]
    
    for typelib_path in typelib_paths:
        if os.path.exists(typelib_path):
            for pattern in ['Gst*.typelib', 'GLib*.typelib', 'GObject*.typelib', 'Gio*.typelib']:
                for typelib in glob.glob(os.path.join(typelib_path, pattern)):
                    datas.append((typelib, 'gi_typelibs'))
            break
    
    if is_64bit:
        plugin_paths = [
            '/usr/lib64/gstreamer-1.0',
            '/usr/lib/x86_64-linux-gnu/gstreamer-1.0',
            '/usr/lib/gstreamer-1.0'
        ]
    else:
        plugin_paths = [
            '/usr/lib/gstreamer-1.0',
            '/usr/lib/x86_64-linux-gnu/gstreamer-1.0',
            '/usr/lib64/gstreamer-1.0'
        ]
    
    for plugin_path in plugin_paths:
        if os.path.exists(plugin_path):
            for plugin in glob.glob(os.path.join(plugin_path, '*.so')):
                binaries.append((plugin, 'gst_plugins'))
            break
    
    # Collect gst-plugin-scanner helper binary
    scanner_paths = [
        '/usr/libexec/gstreamer-1.0/gst-plugin-scanner',
        '/usr/lib/x86_64-linux-gnu/gstreamer1.0/gstreamer-1.0/gst-plugin-scanner',
        '/usr/lib/gstreamer-1.0/gst-plugin-scanner'
    ]
    for scanner_path in scanner_paths:
        if os.path.exists(scanner_path):
            binaries.append((scanner_path, 'gst_helpers'))
            break
    
    lib_paths = ['/usr/lib64', '/usr/lib/x86_64-linux-gnu', '/usr/lib'] if is_64bit else ['/usr/lib', '/usr/lib/x86_64-linux-gnu', '/usr/lib64']
    gst_libs = [
        'libgstreamer-1.0.so.*', 'libgstbase-1.0.so.*', 'libgstaudio-1.0.so.*',
        'libgstvideo-1.0.so.*', 'libgstpbutils-1.0.so.*', 'libgsttag-1.0.so.*',
        'libgstapp-1.0.so.*', 'libgstcontroller-1.0.so.*', 'libgstnet-1.0.so.*',
        'libgstriff-1.0.so.*', 'libgstrtp-1.0.so.*', 'libgstrtsp-1.0.so.*', 'libgstsdp-1.0.so.*',
    ]
    
    for lib_path in lib_paths:
        if os.path.exists(lib_path):
            for lib_pattern in gst_libs:
                for lib in glob.glob(os.path.join(lib_path, lib_pattern)):
                    if lib.endswith('.so.0') or '.so.0.' in lib:
                        binaries.append((lib, '.'))
            if any(lib for lib, _ in binaries if 'gstreamer' in lib):
                break

elif sys.platform == 'darwin':
    # macOS (Homebrew)
    brew_prefix = os.popen('brew --prefix 2>/dev/null').read().strip()
    if brew_prefix:
        typelib_path = os.path.join(brew_prefix, 'lib/girepository-1.0')
        if os.path.exists(typelib_path):
            for pattern in ['Gst*.typelib', 'GLib*.typelib', 'GObject*.typelib', 'Gio*.typelib']:
                for typelib in glob.glob(os.path.join(typelib_path, pattern)):
                    datas.append((typelib, 'gi_typelibs'))
        
        plugin_path = os.path.join(brew_prefix, 'lib/gstreamer-1.0')
        if os.path.exists(plugin_path):
            for plugin in glob.glob(os.path.join(plugin_path, '*.dylib')):
                binaries.append((plugin, 'gst_plugins'))
        
        lib_path = os.path.join(brew_prefix, 'lib')
        if os.path.exists(lib_path):
            for pattern in ['libgstreamer-1.0*.dylib', 'libgst*.1.dylib']:
                for lib in glob.glob(os.path.join(lib_path, pattern)):
                    binaries.append((lib, '.'))

elif sys.platform == 'win32':
    # Windows (MSYS2/MinGW)
    msys_paths = [
        'C:/msys64/mingw64',
        os.path.join(os.environ.get('MSYS2_ROOT', 'C:/msys64'), 'mingw64')
    ]
    
    for msys_prefix in msys_paths:
        if os.path.exists(msys_prefix):
            typelib_path = os.path.join(msys_prefix, 'lib/girepository-1.0')
            if os.path.exists(typelib_path):
                for pattern in ['Gst*.typelib', 'GLib*.typelib', 'GObject*.typelib', 'Gio*.typelib']:
                    for typelib in glob.glob(os.path.join(typelib_path, pattern)):
                        datas.append((typelib, 'gi_typelibs'))
            
            plugin_path = os.path.join(msys_prefix, 'lib/gstreamer-1.0')
            if os.path.exists(plugin_path):
                for plugin in glob.glob(os.path.join(plugin_path, '*.dll')):
                    binaries.append((plugin, 'gst_plugins'))
            
            bin_path = os.path.join(msys_prefix, 'bin')
            if os.path.exists(bin_path):
                for pattern in ['gstreamer-1.0-0.dll', 'gst*.dll']:
                    for lib in glob.glob(os.path.join(bin_path, pattern)):
                        binaries.append((lib, '.'))
            
            if datas or binaries:
                break

print(f"GStreamer hook ({sys.platform}): Found {len(datas)} typelibs and {len([b for b in binaries if 'gst' in b[0].lower()])} GStreamer files")
