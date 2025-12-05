# -*- mode: python ; coding: utf-8 -*-
import sys
import os
import glob

block_cipher = None

# Collect gi binary extensions (needed when using system PyGObject)
gi_binaries = []
try:
    import gi
    gi_path = os.path.dirname(gi.__file__)
    print(f"Found gi at: {gi_path}")
    for ext in glob.glob(os.path.join(gi_path, '*.so')):
        gi_binaries.append((ext, 'gi'))
        print(f"  Adding: {ext}")
    for ext in glob.glob(os.path.join(gi_path, '*.pyd')):
        gi_binaries.append((ext, 'gi'))
        print(f"  Adding: {ext}")
except ImportError as e:
    print(f"Could not import gi during spec: {e}")
    # Try system paths directly
    for sys_path in ['/usr/lib/python3/dist-packages/gi', '/usr/lib64/python3.11/site-packages/gi']:
        if os.path.exists(sys_path):
            print(f"Searching system path: {sys_path}")
            for ext in glob.glob(os.path.join(sys_path, '*.so')):
                gi_binaries.append((ext, 'gi'))
                print(f"  Adding: {ext}")
            break

if gi_binaries:
    print(f"Total gi binaries collected: {len(gi_binaries)}")
else:
    print("WARNING: No gi binaries collected!")

a = Analysis(
    ['walrio_lite.py'],
    pathex=['..'],
    binaries=gi_binaries,
    datas=[('../modules', 'modules'), ('../icons', 'icons')],
    hiddenimports=[
        'gi',
        'gi._gi',
        'gi.repository',
        'gi.overrides',
        'gi.repository.Gst',
        'gi.repository.GstBase',
        'gi.repository.GstAudio',
        'gi.repository.GstVideo',
        'gi.repository.GObject',
        'gi.repository.Gio',
        'gi.repository.GLib',
        'modules',
        'modules.core',
        'modules.core.player',
        'modules.core.queue',
        'modules.core.playlist',
        'modules.core.metadata',
        'modules.core.database'
    ],
    hookspath=['hooks'],
    runtime_hooks=['GUI/pyi_rth_gstreamer.py'],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
)
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='WalrioLite',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='WalrioLite'
)
