#!/usr/bin/env python3
"""
Walrio Modules Package
Copyright (c) 2025 TAPS OSS
Project: https://github.com/TAPSOSS/Walrio
Licensed under the BSD-3-Clause License (see LICENSE file for details)

Main modules package containing all Walrio functionality:

Core Modules:
- database: SQLite database management for music metadata and playlists
- player: GStreamer-based audio player with advanced playback features
- playlist: M3U playlist creation and management utilities
- queue: Playback queue management with shuffle and repeat modes
- metadata: Edit audio file metadata and album art using mutagen CLI tools

Addon Modules:
- convert: Audio format conversion using FFmpeg
- file_relocater: Organize audio files based on metadata into folder structures
- rename: Standardize audio file names based on metadata
- replaygain: ReplayGain LUFS analysis and tagging using rsgain
- imageconverter: Convert images between different formats (JPEG, PNG, WebP, etc.) and resize them

Niche Modules:
- applyloudness: Apply gain adjustments directly to audio files using FFmpeg with ReplayGain or manual dB values (WARNING: can damage audio files irreversibly)
- resizealbumart: Extract, resize, and re-embed album art in audio files using imageconverter and metadata tools
"""

__version__ = "1.0.0"
__author__ = "Walrio Contributors"

# Import core modules
try:
    from .core import database, player, playlist, queue, metadata
except ImportError:
    pass

# Import addon modules
try:
    from .addons import convert, file_relocater, rename, replaygain, imageconverter
except ImportError:
    pass

# Import niche modules
try:
    from .niche import applyloudness, resizealbumart
except ImportError:
    pass

# Make all modules available at package level
__all__ = [
    # Core modules
    'database', 'player', 'playlist', 'queue', 'metadata',
    # Addon modules  
    'convert', 'file_relocater', 'rename', 'replaygain', 'imageconverter',
    # Niche modules
    'applyloudness', 'resizealbumart'
]
