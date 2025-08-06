API Reference
=============

This section contains the complete API reference for Walrio modules, automatically generated from the source code docstrings.

.. toctree::
   :maxdepth: 2
   :caption: Module APIs

   core
   addons

Core Libraries
--------------
The core libraries provide the fundamental functionality for Walrio:

.. autosummary::
   :toctree: _autosummary
   :recursive:

   modules.core.database
   modules.core.player
   modules.core.playlist
   modules.core.queue

Module Overview
---------------

**Database Module**
   SQLite database operations for music metadata and library management.

**Player Module** 
   Audio playback functionality.

**Playlist Module**
   M3U playlist creation, parsing, and management from various sources including database queries and file system scanning.

**Queue Module**
   Playback queue management with shuffle, repeat, and queue manipulation features.

Quick Reference
---------------

Common Classes
~~~~~~~~~~~~~~

* :class:`database.DatabaseManager` - Main database interface
* :class:`player.GStreamerPlayer` - Core audio player implementation  
* :class:`queue.PlaybackQueue` - Queue management for playback

Common Functions
~~~~~~~~~~~~~~~~

* :func:`database.create_database` - Initialize music library database
* :func:`player.format_time` - Format duration for display
* :func:`playlist.create_m3u_playlist` - Generate M3U playlist files
* :func:`queue.shuffle_queue` - Randomize playback order

Constants
~~~~~~~~~

* :data:`database.AUDIO_EXTENSIONS` - Supported audio file formats
* :data:`playlist.DEFAULT_DB_PATH` - Default database location
* :data:`player.SUPPORTED_FORMATS` - Audio formats supported by player
