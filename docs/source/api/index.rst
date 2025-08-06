API Reference
=============

.. automodule:: modules
   :members:
   :undoc-members:
   :show-inheritance:

This section contains the complete API reference for Walrio modules, automatically generated from the source code docstrings.

.. toctree::
   :maxdepth: 2
   :caption: Module APIs

   core
   addons

Core Modules
------------

.. autosummary::
   :toctree: _autosummary
   :recursive:

   modules.core.database
   modules.core.player
   modules.core.playlist
   modules.core.queue

Addon Modules
-------------

.. autosummary::
   :toctree: _autosummary
   :recursive:

   modules.addons.convert
   modules.addons.file_relocater
   modules.addons.rename
   modules.addons.organize

Module Overview
---------------

**Core Modules**

**Database Module**
   SQLite database operations for music metadata and library management.

**Player Module** 
   Audio playback functionality.

**Playlist Module**
   M3U playlist creation, parsing, and management from various sources including database queries and file system scanning.

**Queue Module**
   Playback queue management with shuffle, repeat, and queue manipulation features.

**Addon Modules**

**Convert Module**
   Audio format conversion using FFmpeg with support for multiple formats, bitrate adjustment, and metadata preservation.

**File Relocater Module**
   Organize audio files into folder structures based on metadata with customizable folder naming patterns.

**Rename Module**
   Standardize audio file names based on metadata using configurable naming patterns.

**Organize Module**
   Library organization tools and utilities for managing music collections.

Quick Reference
---------------

Common Classes
~~~~~~~~~~~~~~

**Core Classes**

* :class:`database.DatabaseManager` - Main database interface
* :class:`player.GStreamerPlayer` - Core audio player implementation  
* :class:`queue.PlaybackQueue` - Queue management for playback

**Addon Classes**

* :class:`convert.AudioConverter` - Audio format conversion functionality
* :class:`file_relocater.FileRelocater` - Metadata-based file organization
* :class:`rename.AudioRenamer` - Standardized file renaming

Common Functions
~~~~~~~~~~~~~~~~

**Core Functions**

* :func:`database.create_database` - Initialize music library database
* :func:`player.format_time` - Format duration for display
* :func:`playlist.create_m3u_playlist` - Generate M3U playlist files
* :func:`queue.shuffle_queue` - Randomize playback order

**Addon Functions**

* :func:`convert.convert_audio_file` - Convert audio files between formats
* :func:`file_relocater.sanitize_folder_name` - Clean folder names for compatibility
* :func:`rename.sanitize_filename` - Clean file names for compatibility

Constants
~~~~~~~~~

* :data:`database.AUDIO_EXTENSIONS` - Supported audio file formats
* :data:`playlist.DEFAULT_DB_PATH` - Default database location
* :data:`player.SUPPORTED_FORMATS` - Audio formats supported by player
* :data:`convert.SUPPORTED_FORMATS` - Audio formats supported for conversion
* :data:`file_relocater.ALLOWED_FOLDER_CHARS` - Safe characters for folder names
