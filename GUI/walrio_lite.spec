# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_data_files, collect_submodules
import sys
import os

block_cipher = None

# Collect all gi module files
gi_datas = collect_data_files('gi', include_py_files=True)
gi_submodules = collect_submodules('gi')

a = Analysis(
    ['walrio_lite.py'],
    pathex=['..'],
    binaries=[],
    datas=[('../modules', 'modules'), ('../icons', 'icons')] + gi_datas,
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
    ] + gi_submodules,
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
