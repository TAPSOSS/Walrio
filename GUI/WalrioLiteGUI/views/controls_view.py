#!/usr/bin/env python3
"""
Control view for Walrio GUI
Copyright (c) 2025 TAPS OSS
Project: https://github.com/TAPSOSS/Walrio
Licensed under the BSD-3-Clause License (see LICENSE file for details)

Contains the playback controls, progress slider, and volume controls.
"""

import sys
import subprocess

try:
    from PySide6.QtWidgets import (
        QWidget, QVBoxLayout, QHBoxLayout, QSlider, QLabel, QPushButton
    )
    from PySide6.QtCore import Qt, Signal, QTimer
    from PySide6.QtGui import QFont
except ImportError:
    print("PySide6 not found. Installing...")
    subprocess.run([sys.executable, "-m", "pip", "install", "PySide6"])
    from PySide6.QtWidgets import (
        QWidget, QVBoxLayout, QHBoxLayout, QSlider, QLabel, QPushButton
    )
    from PySide6.QtCore import Qt, Signal, QTimer
    from PySide6.QtGui import QFont

from .base_view import BaseView


class ControlsView(BaseView):
    """Playback controls widget."""
    
    # Define signals
    play_pause_requested = Signal()
    stop_requested = Signal()
    previous_requested = Signal()
    next_requested = Signal()
    loop_toggle_requested = Signal()
    shuffle_requested = Signal()
    seek_started = Signal()
    seek_ended = Signal(int)  # position
    slider_value_changed = Signal(int)  # value
    volume_changed = Signal(int)  # volume percentage
    
    def __init__(self, parent=None):
        """Initialize the controls view.
        
        Args:
            parent (QWidget, optional): Parent widget for this controls view
        """
        super().__init__(parent)
        self.is_seeking = False
    
    def setup_ui(self):
        """Setup the controls view UI."""
        main_layout = QVBoxLayout(self)
        
        # Time and progress
        time_layout = QHBoxLayout()
        self.time_current = QLabel("00:00")
        self.progress_slider = QSlider(Qt.Horizontal)
        self.progress_slider.setMinimum(0)
        self.progress_slider.setMaximum(100)
        self.progress_slider.setValue(0)
        
        # Enable click-to-position behavior
        self.progress_slider.mousePressEvent = self._slider_mouse_press_event
        
        self.time_total = QLabel("00:00")
        
        time_layout.addWidget(self.time_current)
        time_layout.addWidget(self.progress_slider)
        time_layout.addWidget(self.time_total)
        main_layout.addLayout(time_layout)
        
        # Control buttons
        controls_layout = QHBoxLayout()
        
        self.btn_previous = QPushButton("⏮ Previous")
        self.btn_play_pause = QPushButton("▶ Play")
        self.btn_stop = QPushButton("⏹ Stop")
        self.btn_next = QPushButton("⏭ Next")
        self.btn_shuffle = QPushButton("🔀 Shuffle")
        self.btn_loop = QPushButton("🔁 Repeat: Off")
        
        # Style buttons
        button_style = """
            QPushButton {
                font-size: 12px;
                padding: 6px 8px;
                min-width: 70px;
            }
        """
        for btn in [self.btn_previous, self.btn_play_pause, self.btn_stop, 
                   self.btn_next, self.btn_shuffle, self.btn_loop]:
            btn.setStyleSheet(button_style)
        
        # Volume control
        self.volume_slider = QSlider(Qt.Horizontal)
        self.volume_slider.setMinimum(0)
        self.volume_slider.setMaximum(100)
        self.volume_slider.setValue(70)
        self.volume_slider.setMinimumWidth(200)
        self.volume_slider.setMaximumWidth(300)
        self.volume_label = QLabel("70%")
        self.volume_label.setMinimumWidth(40)

        controls_layout.addStretch()
        controls_layout.addWidget(QLabel("Volume:"))
        controls_layout.addWidget(self.volume_slider)
        controls_layout.addWidget(self.volume_label)
        controls_layout.addSpacing(15)
        controls_layout.addWidget(self.btn_previous)
        controls_layout.addWidget(self.btn_play_pause)
        controls_layout.addWidget(self.btn_stop)
        controls_layout.addWidget(self.btn_next)
        controls_layout.addWidget(self.btn_shuffle)
        controls_layout.addWidget(self.btn_loop)
        controls_layout.addStretch()
        main_layout.addLayout(controls_layout)
        
        # Initially disable some buttons
        self.btn_play_pause.setEnabled(False)
        self.btn_stop.setEnabled(False)
        self.btn_previous.setEnabled(False)
        self.btn_next.setEnabled(False)
        self.btn_shuffle.setEnabled(False)
    
    def connect_signals(self):
        """Connect the UI signals."""
        self.btn_previous.clicked.connect(self._on_previous)
        self.btn_play_pause.clicked.connect(self._on_play_pause)
        self.btn_stop.clicked.connect(self._on_stop)
        self.btn_next.clicked.connect(self._on_next)
        self.btn_shuffle.clicked.connect(self._on_shuffle)
        self.btn_loop.clicked.connect(self._on_loop_toggle)
        
        self.progress_slider.sliderPressed.connect(self._on_seek_start)
        self.progress_slider.sliderReleased.connect(self._on_seek_end)
        self.progress_slider.valueChanged.connect(self._on_slider_value_changed)
        
        self.volume_slider.valueChanged.connect(self._on_volume_changed)
    
    def _on_previous(self):
        """Handle previous button click."""
        self.previous_requested.emit()
    
    def _on_play_pause(self):
        """Handle play/pause button click."""
        self.play_pause_requested.emit()
    
    def _on_stop(self):
        """Handle stop button click."""
        self.stop_requested.emit()
    
    def _on_next(self):
        """Handle next button click."""
        self.next_requested.emit()
    
    def _on_shuffle(self):
        """Handle shuffle button click."""
        self.shuffle_requested.emit()
    
    def _on_loop_toggle(self):
        """Handle loop toggle button click."""
        self.loop_toggle_requested.emit()
    
    def _on_seek_start(self):
        """Handle when user starts seeking."""
        self.is_seeking = True
        self.seek_started.emit()
    
    def _on_seek_end(self):
        """Handle when user finishes seeking."""
        self.is_seeking = False
        seek_position = self.progress_slider.value()
        self.seek_ended.emit(seek_position)
    
    def _on_slider_value_changed(self, value):
        """Handle slider value changes.
        
        Args:
            value (int): New slider value (0-100 for progress)
        """
        self.slider_value_changed.emit(value)
    
    def _on_volume_changed(self, value):
        """Handle volume slider changes.
        
        Args:
            value (int): New volume level (0-100)
        """
        self.volume_label.setText(f"{value}%")
        self.volume_changed.emit(value)
    
    def _slider_mouse_press_event(self, event):
        """Handle mouse press events on the slider for click-to-position.
        
        Args:
            event (QMouseEvent): The mouse press event to handle
        """
        if event.button() == Qt.LeftButton:
            # Calculate the position where the user clicked
            slider_min = self.progress_slider.minimum()
            slider_max = self.progress_slider.maximum()
            slider_range = slider_max - slider_min
            
            # Get the click position relative to the slider
            click_pos = event.position().x()
            slider_width = self.progress_slider.width()
            
            # Calculate the value based on click position
            if slider_width > 0:
                ratio = click_pos / slider_width
                new_value = slider_min + (ratio * slider_range)
                new_value = max(slider_min, min(slider_max, int(new_value)))
                
                # Set the slider to this position
                self.progress_slider.setValue(new_value)
        
        # Call the original mouse press event
        QSlider.mousePressEvent(self.progress_slider, event)
    
    def set_play_pause_text(self, text):
        """Set the play/pause button text.
        
        Args:
            text (str): Text to display on the play/pause button
        """
        self.btn_play_pause.setText(text)
    
    def set_play_pause_enabled(self, enabled):
        """Enable or disable the play/pause button.
        
        Args:
            enabled (bool): True to enable the button, False to disable
        """
        self.btn_play_pause.setEnabled(enabled)
    
    def set_stop_enabled(self, enabled):
        """Enable or disable the stop button.
        
        Args:
            enabled (bool): True to enable the button, False to disable
        """
        self.btn_stop.setEnabled(enabled)
    
    def set_navigation_enabled(self, enabled):
        """Enable or disable the previous/next buttons.
        
        Args:
            enabled (bool): True to enable the buttons, False to disable
        """
        self.btn_previous.setEnabled(enabled)
        self.btn_next.setEnabled(enabled)
    
    def set_shuffle_enabled(self, enabled):
        """Enable or disable the shuffle button.
        
        Args:
            enabled (bool): True to enable the button, False to disable
        """
        self.btn_shuffle.setEnabled(enabled)
    
    def set_loop_text(self, text):
        """Set the loop button text.
        
        Args:
            text (str): Text to display on the loop button
        """
        self.btn_loop.setText(text)
    
    def set_loop_style(self, is_active):
        """Set the loop button style based on active state.
        
        Args:
            is_active (bool): True for active/enabled style, False for inactive style
        """
        if is_active:
            self.btn_loop.setStyleSheet("""
                QPushButton {
                    font-size: 12px;
                    padding: 6px 8px;
                    min-width: 70px;
                    background-color: #4CAF50;
                    color: white;
                }
            """)
        else:
            self.btn_loop.setStyleSheet("""
                QPushButton {
                    font-size: 12px;
                    padding: 6px 8px;
                    min-width: 70px;
                }
            """)
    
    def set_position(self, position):
        """Set the current position on the progress slider.
        
        Args:
            position: The position value to set on the slider.
        """
        if not self.is_seeking:
            self.progress_slider.setValue(int(position))
    
    def set_duration(self, duration):
        """Set the maximum duration on the progress slider.
        
        Args:
            duration: The maximum duration value for the slider.
        """
        if duration > 0:
            self.progress_slider.setMaximum(int(duration))
        else:
            self.progress_slider.setMaximum(100)
    
    def set_time_current(self, time_str):
        """Set the current time display.
        
        Args:
            time_str: The formatted time string to display.
        """
        self.time_current.setText(time_str)
    
    def set_time_total(self, time_str):
        """Set the total time display.
        
        Args:
            time_str: The formatted time string to display.
        """
        self.time_total.setText(time_str)
    
    def get_volume(self):
        """Get the current volume value.
        
        Returns:
            int: The current volume slider value.
        """
        return self.volume_slider.value()
    
    def set_volume(self, volume):
        """Set the volume slider value.
        
        Args:
            volume: The volume value to set (0-100).
        """
        self.volume_slider.setValue(volume)
        self.volume_label.setText(f"{volume}%")
    
    def is_slider_pressed(self):
        """Check if the progress slider is currently being pressed.
        
        Returns:
            bool: True if the progress slider is currently pressed, False otherwise.
        """
        return self.progress_slider.isSliderDown()