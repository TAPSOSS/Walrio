# -*- mode: python ; coding: utf-8 -*-
import sys
import os
import site

block_cipher = None

# Find gi module location dynamically
gi_path = None
for path in site.getsitepackages() + [site.getusersitepackages()]:
    potential_gi = os.path.join(path, 'gi')
    if os.path.exists(potential_gi):
        gi_path = potential_gi
        break

# Build datas list
datas_list = [('../modules', 'modules'), ('../icons', 'icons')]
if gi_path:
    # Add gi Python source files
    datas_list.append((os.path.join(gi_path, '*.py'), 'gi'))
    gi_repo = os.path.join(gi_path, 'repository')
    if os.path.exists(gi_repo):
        datas_list.append((os.path.join(gi_repo, '*.py'), 'gi/repository'))
    gi_overrides = os.path.join(gi_path, 'overrides')
    if os.path.exists(gi_overrides):
        datas_list.append((os.path.join(gi_overrides, '*.py'), 'gi/overrides'))

a = Analysis(
    ['walrio_lite.py'],
    pathex=['..'],
    binaries=[],
    datas=datas_list,
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
