#!/usr/bin/env python3
"""
Data models for Walrio GUI
Copyright (c) 2025 TAPS OSS
Project: https://github.com/TAPSOSS/Walrio
Licensed under the BSD-3-Clause License (see LICENSE file for details)

Contains data structure classes for managing songs, playlists, and application state.
"""

from pathlib import Path
import sys
import os

# Add the parent directory to the Python path so we can import modules
sys.path.append(os.path.join(os.path.dirname(__file__), '../../..'))

from modules.core.queue import QueueManager, RepeatMode


class Song:
    """Data model for a single song."""
    
    def __init__(self, url, title=None, artist=None, album=None, albumartist=None, year=None, duration=0):
        """
        Initialize a Song instance.
        
        Args:
            url (str): File path or URL to the audio file
            title (str): Song title
            artist (str): Artist name
            album (str): Album name
            albumartist (str): Album artist name
            year (str): Release year
            duration (float): Duration in seconds
        """
        self.url = url
        self.title = title or Path(url).stem
        self.artist = artist or 'Unknown Artist'
        self.album = album or 'Unknown Album'
        self.albumartist = albumartist or self.artist
        self.year = year or 'Unknown'
        self.duration = duration or 0
    
    def to_dict(self):
        """Convert song to dictionary format."""
        return {
            'url': self.url,
            'title': self.title,
            'artist': self.artist,
            'album': self.album,
            'albumartist': self.albumartist,
            'year': self.year,
            'duration': self.duration
        }
    
    @classmethod
    def from_dict(cls, data):
        """Create Song instance from dictionary."""
        return cls(
            url=data.get('url', ''),
            title=data.get('title'),
            artist=data.get('artist'),
            album=data.get('album'),
            albumartist=data.get('albumartist'),
            year=data.get('year'),
            duration=data.get('duration', 0)
        )
    
    def __str__(self):
        return f"{self.artist} - {self.title}"
    
    def __repr__(self):
        return f"Song(url='{self.url}', title='{self.title}', artist='{self.artist}')"


class Playlist:
    """Data model for a playlist."""
    
    def __init__(self, name, songs=None, filepath=None):
        """
        Initialize a Playlist instance.
        
        Args:
            name (str): Playlist name
            songs (list): List of Song instances
            filepath (str): Path to the playlist file
        """
        self.name = name
        self.songs = songs or []
        self.filepath = filepath
    
    def add_song(self, song):
        """Add a song to the playlist."""
        if isinstance(song, dict):
            song = Song.from_dict(song)
        self.songs.append(song)
    
    def remove_song(self, index):
        """Remove a song by index."""
        if 0 <= index < len(self.songs):
            return self.songs.pop(index)
        return None
    
    def get_song(self, index):
        """Get a song by index."""
        if 0 <= index < len(self.songs):
            return self.songs[index]
        return None
    
    def __len__(self):
        return len(self.songs)
    
    def __iter__(self):
        return iter(self.songs)
    
    def __str__(self):
        return f"{self.name} ({len(self.songs)} tracks)"


class ApplicationState:
    """Data model for application state."""
    
    def __init__(self):
        """Initialize application state."""
        self.current_file = None
        self.is_playing = False
        self.position = 0
        self.duration = 0
        self.is_seeking = False
        self.loop_mode = "off"  # Can be "off" or "track"
        self.volume = 70  # Volume percentage (0-100)
        self.pending_position = 0
        
        # Queue state
        self.queue_songs = []
        self.current_queue_index = 0
        self.queue_manager = None
        
        # Playlist state
        self.loaded_playlists = {}  # Dictionary {name: Playlist}
        self.selected_playlist_name = None
        self.selected_playlist_songs = []
        
        # UI state
        self.is_processing_finish = False
    
    def reset_playback_state(self):
        """Reset playback-related state."""
        self.is_playing = False
        self.position = 0
        self.is_seeking = False
        self.pending_position = 0
    
    def set_current_file(self, filepath):
        """Set the current file and reset related state."""
        self.current_file = filepath
        self.reset_playback_state()
    
    def update_queue_manager(self):
        """Create or update the queue manager with current queue state."""
        current_songs = self.queue_songs if self.queue_songs else []
        
        # If no queue songs, create single-song queue for current file
        if not current_songs and self.current_file:
            current_songs = [{
                'url': self.current_file,
                'title': Path(self.current_file).stem,
                'artist': 'Unknown Artist',
                'album': 'Unknown Album'
            }]
        
        # Create QueueManager only if it doesn't exist
        if not self.queue_manager:
            print(f"Creating initial QueueManager with {len(current_songs)} songs")
            self.queue_manager = QueueManager(current_songs)
            self.queue_manager.set_current_index(self.current_queue_index)
        else:
            # Update the current index
            self.queue_manager.set_current_index(self.current_queue_index)
    
    def add_playlist(self, name, playlist):
        """Add a playlist to the loaded playlists."""
        if isinstance(playlist, list):
            # Convert list of dicts to Playlist object
            playlist_obj = Playlist(name)
            for song_data in playlist:
                playlist_obj.add_song(song_data)
            playlist = playlist_obj
        
        self.loaded_playlists[name] = playlist
    
    def get_playlist(self, name):
        """Get a playlist by name."""
        return self.loaded_playlists.get(name)
    
    def remove_playlist(self, name):
        """Remove a playlist by name."""
        if name in self.loaded_playlists:
            del self.loaded_playlists[name]
            return True
        return False