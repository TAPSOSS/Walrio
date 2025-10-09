#!/usr/bin/env python3
"""
Credits view for Walrio GUI
Copyright (c) 2025 TAPS OSS
Project: https://github.com/TAPSOSS/Walrio
Licensed under the BSD-3-Clause License (see LICENSE file for details)

Contains the credits tab showing project information and contributors.
"""

import sys
import subprocess
from pathlib import Path

try:
    from PySide6.QtWidgets import (
        QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
        QTextEdit, QScrollArea, QFrame
    )
    from PySide6.QtCore import Qt, QUrl
    from PySide6.QtGui import QFont, QPixmap, QDesktopServices
except ImportError:
    print("PySide6 not found. Installing...")
    subprocess.run([sys.executable, "-m", "pip", "install", "PySide6"])
    from PySide6.QtWidgets import (
        QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
        QTextEdit, QScrollArea, QFrame
    )
    from PySide6.QtCore import Qt, QUrl
    from PySide6.QtGui import QFont, QPixmap, QDesktopServices

from .base_view import BaseView


class CreditsView(BaseView):
    """Credits view widget showing project information and contributors."""
    
    def __init__(self, parent=None):
        """Initialize the credits view."""
        super().__init__(parent)
    
    def setup_ui(self):
        """Setup the credits view UI."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(20)
        
        # Scroll area for all content
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameStyle(QFrame.NoFrame)
        
        # Main content widget
        content_widget = QWidget()
        content_layout = QVBoxLayout(content_widget)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(15)
        
        # Icon and Title section
        header_layout = QVBoxLayout()
        header_layout.setSpacing(10)
        
        # Walrio Icon
        icon_label = QLabel()
        icon_label.setAlignment(Qt.AlignCenter)
        
        # Try to load SVG first, fallback to PNG
        try:
            # Look for the icon in the icons folder (bundled resources or source directory)
            icon_paths = [
                Path.cwd() / "icons" / "walrio.svg",  # SVG when running from source
                Path(__file__).parent.parent.parent.parent / "icons" / "walrio.svg",  # SVG when bundled
                Path.cwd() / "icons" / "walrio.png",  # PNG fallback when running from source
                Path(__file__).parent.parent.parent.parent / "icons" / "walrio.png",  # PNG fallback when bundled
            ]
            
            icon_loaded = False
            for icon_path in icon_paths:
                if icon_path.exists():
                    pixmap = QPixmap(str(icon_path))
                    if not pixmap.isNull():
                        # Scale the icon to a reasonable size
                        scaled_pixmap = pixmap.scaled(64, 64, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                        icon_label.setPixmap(scaled_pixmap)
                        icon_loaded = True
                        break
            
            if not icon_loaded:
                # If no icon found, show a placeholder
                icon_label.setText("🎵")
                icon_font = QFont()
                icon_font.setPointSize(48)
                icon_label.setFont(icon_font)
                
        except Exception as e:
            # Fallback to emoji if there's any error
            icon_label.setText("🎵")
            icon_font = QFont()
            icon_font.setPointSize(48)
            icon_label.setFont(icon_font)
        
        header_layout.addWidget(icon_label)
        
        # Title
        title_label = QLabel("Walrio Music Player")
        title_font = QFont()
        title_font.setPointSize(24)
        title_font.setBold(True)
        title_label.setFont(title_font)
        title_label.setAlignment(Qt.AlignCenter)
        header_layout.addWidget(title_label)
        
        content_layout.addLayout(header_layout)
        
        # Version/Description section
        desc_text = """
        Walrio Music Player Lite is an open source music player. Built with Python and PySide6, 
        it provides a clean and intuitive interface for managing and playing your music collection.
        """
        
        desc_label = QLabel(desc_text.strip())
        desc_label.setWordWrap(True)
        desc_label.setAlignment(Qt.AlignCenter)
        desc_font = QFont()
        desc_font.setPointSize(11)
        desc_label.setFont(desc_font)
        desc_label.setStyleSheet("color: #666; margin: 10px 0px;")
        content_layout.addWidget(desc_label)
        
        # Project link section
        project_frame = QFrame()
        project_frame.setFrameStyle(QFrame.Box)
        project_frame.setStyleSheet("QFrame { background-color: #f8f9fa; border: 1px solid #dee2e6; border-radius: 5px; padding: 15px; }")
        project_layout = QVBoxLayout(project_frame)
        
        project_title = QLabel("Project Repository")
        project_title_font = QFont()
        project_title_font.setPointSize(14)
        project_title_font.setBold(True)
        project_title.setFont(project_title_font)
        project_layout.addWidget(project_title)
        
        # GitHub link
        github_link = QLabel('<a href="https://github.com/TAPSOSS/Walrio" style="color: #0366d6; text-decoration: none; font-size: 12pt;">https://github.com/TAPSOSS/Walrio</a>')
        github_link.setOpenExternalLinks(True)
        github_link.setTextInteractionFlags(Qt.TextBrowserInteraction)
        project_layout.addWidget(github_link)
        
        content_layout.addWidget(project_frame)
        
        # Contributors section
        contributors_frame = QFrame()
        contributors_frame.setFrameStyle(QFrame.Box)
        contributors_frame.setStyleSheet("QFrame { background-color: #f8f9fa; border: 1px solid #dee2e6; border-radius: 5px; padding: 15px; }")
        contributors_layout = QVBoxLayout(contributors_frame)
        
        contributors_title = QLabel("Contributors")
        contributors_title_font = QFont()
        contributors_title_font.setPointSize(14)
        contributors_title_font.setBold(True)
        contributors_title.setFont(contributors_title_font)
        contributors_layout.addWidget(contributors_title)
        
        # Load and display contributors from AUTHORS file
        authors_text = self._load_authors_file()
        authors_label = QLabel(authors_text)
        authors_label.setWordWrap(True)
        authors_label.setOpenExternalLinks(True)
        authors_label.setTextInteractionFlags(Qt.TextBrowserInteraction)
        authors_font = QFont("monospace")
        authors_font.setPointSize(10)
        authors_label.setFont(authors_font)
        authors_label.setStyleSheet("color: #333; background-color: white; padding: 10px; border-radius: 3px;")
        contributors_layout.addWidget(authors_label)
        
        content_layout.addWidget(contributors_frame)
        
        # Copyright section
        copyright_frame = QFrame()
        copyright_frame.setFrameStyle(QFrame.Box)
        copyright_frame.setStyleSheet("QFrame { background-color: #e9ecef; border: 1px solid #dee2e6; border-radius: 5px; padding: 15px; }")
        copyright_layout = QVBoxLayout(copyright_frame)
        
        copyright_label = QLabel("Copyright © 2025 TAPS OSS")
        copyright_font = QFont()
        copyright_font.setPointSize(12)
        copyright_font.setBold(True)
        copyright_label.setFont(copyright_font)
        copyright_label.setAlignment(Qt.AlignCenter)
        copyright_layout.addWidget(copyright_label)
        
        license_label = QLabel("Licensed under the BSD-3-Clause License")
        license_label.setAlignment(Qt.AlignCenter)
        license_label.setStyleSheet("color: #666;")
        copyright_layout.addWidget(license_label)
        
        content_layout.addWidget(copyright_frame)
        
        # Add stretch to push everything to the top
        content_layout.addStretch()
        
        # Set the content widget to the scroll area
        scroll_area.setWidget(content_widget)
        layout.addWidget(scroll_area)
    
    def _load_authors_file(self):
        """Load and parse the AUTHORS file.
        
        Returns:
            str: Formatted authors text with GitHub links
        """
        try:
            # Find the AUTHORS file in the root of the repository
            current_dir = Path(__file__).parent
            authors_file = current_dir / ".." / ".." / ".." / "AUTHORS"
            
            if authors_file.exists():
                with open(authors_file, 'r', encoding='utf-8') as f:
                    content = f.read().strip()
                
                # Format the content with GitHub links
                lines = content.split('\n')
                formatted_lines = []
                
                for line in lines:
                    line = line.strip()
                    if line:
                        # Make the "Original Author:" and "Contributors" lines bold
                        if line.startswith('Original Author:') or line.startswith('Contributors'):
                            formatted_lines.append(f"<b>{line}</b>")
                        else:
                            # Look for username patterns like "username (Full Name)" or "- username (Full Name)"
                            formatted_line = self._format_author_line(line)
                            formatted_lines.append(formatted_line)
                
                return '<br>'.join(formatted_lines)
            else:
                return "AUTHORS file not found"
                
        except Exception as e:
            return f"Error loading authors: {str(e)}"
    
    def _format_author_line(self, line):
        """Format an author line to include GitHub links for usernames.
        
        Args:
            line (str): The author line to format
            
        Returns:
            str: HTML-formatted line with GitHub links
        """
        import re
        
        # Pattern to match "username (Full Name)" or "- username (Full Name)"
        pattern = r'^(\s*-?\s*)([a-zA-Z0-9_-]+)\s+\(([^)]+)\)'
        match = re.match(pattern, line)
        
        if match:
            prefix = match.group(1)  # Leading spaces and dash if present
            username = match.group(2)
            full_name = match.group(3)
            
            # Create GitHub link for the username
            github_link = f'<a href="https://github.com/{username}" style="color: #0366d6; text-decoration: none;">{username}</a>'
            return f"{prefix}{github_link} ({full_name})"
        else:
            # If no pattern match, return the line as-is
            return line
    
    def connect_signals(self):
        """Connect any signals (none needed for credits view)."""
        pass