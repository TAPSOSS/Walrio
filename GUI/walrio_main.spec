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
    # Collect all binary extensions (.so for Unix, .pyd/.dll for Windows, .dylib for macOS)
    for pattern in ['*.so', '*.pyd', '*.dll', '*.dylib']:
        for ext in glob.glob(os.path.join(gi_path, pattern)):
            gi_binaries.append((ext, 'gi'))
            print(f"  Adding: {ext}")
except ImportError as e:
    print(f"Could not import gi during spec: {e}")
    # Try platform-specific system paths
    if sys.platform.startswith('linux'):
        sys_paths = [
            '/usr/lib/python3/dist-packages/gi',
            '/usr/lib64/python3.12/site-packages/gi',
            '/usr/lib/python3.12/site-packages/gi'
        ]
    elif sys.platform == 'darwin':
        import subprocess
        brew_prefix = subprocess.run(['brew', '--prefix'], capture_output=True, text=True).stdout.strip()
        sys_paths = [
            f"{brew_prefix}/lib/python3.12/site-packages/gi",
            '/opt/homebrew/lib/python3.12/site-packages/gi'
        ]
    elif sys.platform == 'win32':
        sys_paths = [
            'C:/msys64/mingw64/lib/python3.12/site-packages/gi',
            os.path.join(os.environ.get('MSYSTEM_PREFIX', 'C:/msys64/mingw64'), 'lib/python3.12/site-packages/gi')
        ]
    else:
        sys_paths = []
    
    for sys_path in sys_paths:
        if os.path.exists(sys_path):
            print(f"Searching system path: {sys_path}")
            for pattern in ['*.so', '*.pyd', '*.dll', '*.dylib']:
                for ext in glob.glob(os.path.join(sys_path, pattern)):
                    gi_binaries.append((ext, 'gi'))
                    print(f"  Adding: {ext}")
            if gi_binaries:
                break

if gi_binaries:
    print(f"Total gi binaries collected: {len(gi_binaries)}")
else:
    print("WARNING: No gi binaries collected!")

a = Analysis(
    ['walrio_main.py'],
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
    runtime_hooks=['pyi_rth_gstreamer.py'],
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
    name='WalrioMain',
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
    name='WalrioMain'
)

# macOS .app bundle
app = BUNDLE(
    coll,
    name='WalrioMain.app',
    icon=None,
    bundle_identifier='com.tapsoss.walrio.main',
    info_plist={
        'CFBundleName': 'Walrio Main',
        'CFBundleDisplayName': 'Walrio Main',
        'CFBundleVersion': '1.0.0',
        'CFBundleShortVersionString': '1.0.0',
        'NSHighResolutionCapable': 'True',
        'LSMinimumSystemVersion': '10.13.0',
        'NSPrincipalClass': 'NSApplication',
    },
) if sys.platform == 'darwin' else None
