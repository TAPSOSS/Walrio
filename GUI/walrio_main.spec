# -*- mode: python ; coding: utf-8 -*-

block_cipher = None

a = Analysis(
    ['walrio_main.py'],
    pathex=['..'],
    binaries=[],
    datas=[('../modules', 'modules'), ('../icons', 'icons')],
    hiddenimports=[
        'gi',
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
