#!/usr/bin/env python3
"""
Info view for Walrio GUI
Copyright (c) 2025 TAPS OSS
Project: https://github.com/TAPSOSS/Walrio
Licensed under the BSD-3-Clause License (see LICENSE file for details)

Contains the info tab showing current song details, album art, and lyrics.
"""

import sys
import subprocess
import os
from pathlib import Path

try:
    from PySide6.QtWidgets import (
        QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
        QTextEdit, QFrame, QScrollArea
    )
    from PySide6.QtCore import Qt, Signal
    from PySide6.QtGui import QFont, QPixmap
except ImportError:
    print("PySide6 not found. Installing...")
    subprocess.run([sys.executable, "-m", "pip", "install", "PySide6"])
    from PySide6.QtWidgets import (
        QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
        QTextEdit, QFrame, QScrollArea
    )
    from PySide6.QtCore import Qt, Signal
    from PySide6.QtGui import QFont, QPixmap

# Add the parent directory to the Python path so we can import modules
sys.path.append(os.path.join(os.path.dirname(__file__), '../../../..'))

from .base_view import BaseView


class InfoView(BaseView):
    """Info view widget showing current song details, album art, and lyrics."""
    
    def __init__(self, parent=None):
        """Initialize the info view."""
        super().__init__(parent)
        self.current_song_data = None
        
    def setup_ui(self):
        """Setup the info view UI."""
        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(15)
        
        # Left side - Album art (takes up half the width)
        album_art_container = QWidget()
        album_art_container_layout = QVBoxLayout(album_art_container)
        album_art_container_layout.setContentsMargins(0, 0, 0, 0)
        
        self.album_art_label = QLabel()
        self.album_art_label.setAlignment(Qt.AlignCenter)
        self.album_art_label.setStyleSheet("""
            QLabel {
                border: 2px solid #ccc;
                background-color: #f5f5f5;
                border-radius: 5px;
            }
        """)
        self.album_art_label.setText("No Album Art")
        self.album_art_label.setScaledContents(True)
        self.album_art_label.setMinimumSize(200, 200)
        
        album_art_container_layout.addWidget(self.album_art_label)
        layout.addWidget(album_art_container, 1)  # Takes up half the width
        
        # Right side - Song info and lyrics
        right_side_widget = QWidget()
        right_side_layout = QVBoxLayout(right_side_widget)
        right_side_layout.setContentsMargins(0, 0, 0, 0)
        right_side_layout.setSpacing(10)
        
        # Song info section
        info_widget = QWidget()
        info_layout = QVBoxLayout(info_widget)
        info_layout.setContentsMargins(0, 0, 0, 0)
        info_layout.setSpacing(8)
        
        # Song info labels
        self.title_label = QLabel("No song loaded")
        title_font = QFont()
        title_font.setPointSize(16)
        title_font.setBold(True)
        self.title_label.setFont(title_font)
        info_layout.addWidget(self.title_label)
        
        self.artist_label = QLabel("Artist: -")
        artist_font = QFont()
        artist_font.setPointSize(12)
        self.artist_label.setFont(artist_font)
        info_layout.addWidget(self.artist_label)
        
        self.album_label = QLabel("Album: -")
        album_font = QFont()
        album_font.setPointSize(11)
        self.album_label.setFont(album_font)
        info_layout.addWidget(self.album_label)
        
        self.albumartist_label = QLabel("Album Artist: -")
        albumartist_font = QFont()
        albumartist_font.setPointSize(11)
        self.albumartist_label.setFont(albumartist_font)
        info_layout.addWidget(self.albumartist_label)
        
        self.year_label = QLabel("Year: -")
        year_font = QFont()
        year_font.setPointSize(11)
        self.year_label.setFont(year_font)
        info_layout.addWidget(self.year_label)
        
        self.length_label = QLabel("Length: -")
        length_font = QFont()
        length_font.setPointSize(11)
        self.length_label.setFont(length_font)
        info_layout.addWidget(self.length_label)
        
        right_side_layout.addWidget(info_widget)
        
        # Lyrics section
        lyrics_frame = QFrame()
        lyrics_frame.setFrameStyle(QFrame.Box)
        lyrics_frame.setStyleSheet("QFrame { border: 1px solid #ccc; border-radius: 5px; }")
        lyrics_layout = QVBoxLayout(lyrics_frame)
        
        lyrics_title = QLabel("Lyrics")
        lyrics_title_font = QFont()
        lyrics_title_font.setPointSize(12)
        lyrics_title_font.setBold(True)
        lyrics_title.setFont(lyrics_title_font)
        lyrics_layout.addWidget(lyrics_title)
        
        self.lyrics_text = QTextEdit()
        self.lyrics_text.setReadOnly(True)
        self.lyrics_text.setPlainText("No lyrics available")
        self.lyrics_text.setMinimumHeight(200)
        lyrics_layout.addWidget(self.lyrics_text)
        
        right_side_layout.addWidget(lyrics_frame, 1)  # Give lyrics remaining space
        
        layout.addWidget(right_side_widget, 1)  # Takes up the other half
    
    def update_song_info(self, song_data):
        """Update the displayed song information.
        
        Args:
            song_data (dict): Dictionary containing song metadata
        """
        self.current_song_data = song_data
        
        if not song_data:
            # Clear display
            self.title_label.setText("No song loaded")
            self.artist_label.setText("Artist: -")
            self.album_label.setText("Album: -")
            self.albumartist_label.setText("Album Artist: -")
            self.year_label.setText("Year: -")
            self.length_label.setText("Length: -")
            self.lyrics_text.setPlainText("No lyrics available")
            self.album_art_label.clear()
            self.album_art_label.setText("No Album Art")
            return
        
        # Update basic info
        self.title_label.setText(song_data.get('title', 'Unknown Title'))
        self.artist_label.setText(f"Artist: {song_data.get('artist', 'Unknown Artist')}")
        self.album_label.setText(f"Album: {song_data.get('album', 'Unknown Album')}")
        self.albumartist_label.setText(f"Album Artist: {song_data.get('albumartist', song_data.get('artist', 'Unknown Artist'))}")
        self.year_label.setText(f"Year: {song_data.get('year', 'Unknown')}")
        
        # Format length
        length = song_data.get('length', 0)
        if length and length > 0:
            minutes = int(length // 60)
            seconds = int(length % 60)
            length_text = f"{minutes}:{seconds:02d}"
        else:
            length_text = "Unknown"
        self.length_label.setText(f"Length: {length_text}")
        
        # Load album art and lyrics
        file_path = song_data.get('url') or song_data.get('filepath')
        if file_path:
            self._load_album_art(file_path)
            self._load_lyrics(file_path)
    
    def _load_album_art(self, file_path):
        """Load and display album art from audio file.
        
        Args:
            file_path (str): Path to the audio file
        """
        try:
            # Import mutagen here to avoid loading it if not needed
            from mutagen import File as MutagenFile
            from mutagen.id3 import ID3, APIC
            from mutagen.flac import FLAC
            from mutagen.mp4 import MP4
            from mutagen.oggvorbis import OggVorbis
            from mutagen.oggopus import OggOpus
            import base64
            import io
            
            if not os.path.exists(file_path):
                self.album_art_label.clear()
                self.album_art_label.setText("No Album Art")
                return
            
            audio_file = MutagenFile(file_path)
            if not audio_file:
                self.album_art_label.clear()
                self.album_art_label.setText("No Album Art")
                return
            
            image_data = None
            
            # Extract album art based on file type
            if hasattr(audio_file, 'tags') and audio_file.tags:
                if isinstance(audio_file.tags, ID3):
                    # MP3 files with ID3 tags
                    for key in audio_file.tags.keys():
                        if key.startswith('APIC:'):
                            image_data = audio_file.tags[key].data
                            break
                elif isinstance(audio_file, FLAC):
                    # FLAC files
                    if audio_file.pictures:
                        image_data = audio_file.pictures[0].data
                elif isinstance(audio_file, (OggVorbis, OggOpus)):
                    # OGG files
                    if 'METADATA_BLOCK_PICTURE' in audio_file.tags:
                        picture_data = base64.b64decode(audio_file.tags['METADATA_BLOCK_PICTURE'][0])
                        # Skip the FLAC picture header to get to the actual image data
                        # This is a simplified extraction - may need refinement
                        try:
                            # Look for JPEG or PNG signatures in the data
                            if b'\xff\xd8\xff' in picture_data:
                                jpeg_start = picture_data.find(b'\xff\xd8\xff')
                                image_data = picture_data[jpeg_start:]
                            elif b'\x89PNG\r\n\x1a\n' in picture_data:
                                png_start = picture_data.find(b'\x89PNG\r\n\x1a\n')
                                image_data = picture_data[png_start:]
                        except Exception:
                            pass
                elif isinstance(audio_file, MP4):
                    # MP4/M4A files
                    if 'covr' in audio_file.tags:
                        image_data = bytes(audio_file.tags['covr'][0])
            
            if image_data:
                # Create QPixmap from image data
                pixmap = QPixmap()
                pixmap.loadFromData(image_data)
                
                if not pixmap.isNull():
                    # Get the current size of the album art container and make it square
                    container_size = self.album_art_label.parent().size()
                    square_size = min(container_size.width(), container_size.height()) - 20  # Leave some margin
                    square_size = max(square_size, 200)  # Minimum size
                    
                    # Scale to square size while maintaining aspect ratio
                    scaled_pixmap = pixmap.scaled(
                        square_size, square_size, 
                        Qt.KeepAspectRatio, 
                        Qt.SmoothTransformation
                    )
                    
                    # Update the label size to be square
                    self.album_art_label.setFixedSize(square_size, square_size)
                    self.album_art_label.setPixmap(scaled_pixmap)
                    self.album_art_label.setText("")  # Clear text when showing image
                else:
                    self.album_art_label.clear()
                    self.album_art_label.setText("No Album Art")
            else:
                self.album_art_label.clear()
                self.album_art_label.setText("No Album Art")
                
        except Exception as e:
            print(f"Error loading album art: {e}")
            self.album_art_label.clear()
            self.album_art_label.setText("No Album Art")
    
    def _load_lyrics(self, file_path):
        """Load and display embedded lyrics from audio file.
        
        Args:
            file_path (str): Path to the audio file
        """
        try:
            # Import mutagen here to avoid loading it if not needed
            from mutagen import File as MutagenFile
            from mutagen.id3 import ID3, USLT
            from mutagen.flac import FLAC
            from mutagen.mp4 import MP4
            from mutagen.oggvorbis import OggVorbis
            from mutagen.oggopus import OggOpus
            
            if not os.path.exists(file_path):
                self.lyrics_text.setPlainText("No lyrics available")
                return
            
            audio_file = MutagenFile(file_path)
            if not audio_file:
                self.lyrics_text.setPlainText("No lyrics available")
                return
            
            lyrics = None
            
            # Extract lyrics based on file type
            if hasattr(audio_file, 'tags') and audio_file.tags:
                if isinstance(audio_file.tags, ID3):
                    # MP3 files with ID3 tags - look for USLT (Unsynchronized Lyrics)
                    for key in audio_file.tags.keys():
                        if key.startswith('USLT'):
                            lyrics = str(audio_file.tags[key].text)
                            break
                elif isinstance(audio_file, (FLAC, OggVorbis, OggOpus)):
                    # FLAC/OGG files - look for LYRICS tag
                    if 'LYRICS' in audio_file.tags:
                        lyrics = audio_file.tags['LYRICS'][0]
                    elif 'UNSYNCED LYRICS' in audio_file.tags:
                        lyrics = audio_file.tags['UNSYNCED LYRICS'][0]
                elif isinstance(audio_file, MP4):
                    # MP4/M4A files - look for ©lyr tag
                    if '©lyr' in audio_file.tags:
                        lyrics = audio_file.tags['©lyr'][0]
            
            if lyrics and lyrics.strip():
                self.lyrics_text.setPlainText(lyrics.strip())
            else:
                self.lyrics_text.setPlainText("No lyrics available")
                
        except Exception as e:
            print(f"Error loading lyrics: {e}")
            self.lyrics_text.setPlainText("No lyrics available")
    
    def connect_signals(self):
        """Connect any signals (none needed for info view initially)."""
        pass