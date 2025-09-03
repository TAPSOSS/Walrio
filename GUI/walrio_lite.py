#!/usr/bin/env python3
"""
Walrio Lite - Simple Music Player
Copyright (c) 2025 TAPS OSS
Project: https://github.com/TAPSOSS/Walrio
Licensed under the BSD-3-Clause License (see LICENSE file for details)

A lightweight, simple music player GUI built with PySide and music libraries from Walrio that focuses entirely on 
playing music files without any file modification or other extra unneeded capabilities.
"""

import sys
import os
import subprocess
import threading
import time
from pathlib import Path

try:
    from PySide6.QtWidgets import (
        QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
        QPushButton, QSlider, QLabel, QFileDialog, QMessageBox
    )
    from PySide6.QtCore import QTimer, QThread, Signal, Qt
    from PySide6.QtGui import QFont
except ImportError:
    print("PySide6 not found. Installing...")
    subprocess.run([sys.executable, "-m", "pip", "install", "PySide6"])
    from PySide6.QtWidgets import (
        QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
        QPushButton, QSlider, QLabel, QFileDialog, QMessageBox
    )
    from PySide6.QtCore import QTimer, QThread, Signal, Qt
    from PySide6.QtGui import QFont


class SimplePlayerWorker(QThread):
    """Worker thread for running simple audio playback."""
    
    position_updated = Signal(float)
    playback_finished = Signal()
    error = Signal(str)
    
    def __init__(self, filepath):
        """
        Initialize the SimplePlayerWorker thread.
        
        Args:
            filepath (str): Path to the audio file to play.
        """
        super().__init__()
        self.filepath = filepath
        self.should_stop = False
        self.start_time = None
        self.process = None
        self.paused_duration = 0
        self.pause_start = None
    
    def run(self):
        """Run the simple audio player in daemon mode."""
        try:
            # Change to modules directory for walrio.py execution
            modules_dir = Path(__file__).parent.parent / "modules"
            
            # Record start time for position tracking
            self.start_time = time.time()
            
            # Run walrio player in daemon mode for external control
            self.process = subprocess.Popen(
                ["python", "walrio.py", "player", "--daemon", self.filepath],
                cwd=str(modules_dir),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            
            # Monitor process and emit position updates
            while self.process.poll() is None and not self.should_stop:
                if self.start_time and not self.pause_start:
                    # Calculate current position based on elapsed time
                    elapsed = time.time() - self.start_time - self.paused_duration
                    self.position_updated.emit(max(0, elapsed))
                time.sleep(0.1)  # Update position 10 times per second
            
            # Wait for completion
            self.process.wait()
            
            if not self.should_stop:
                self.playback_finished.emit()
                
        except Exception as e:
            error_msg = f"Error in simple player worker: {e}"
            print(error_msg)
            self.error.emit(error_msg)
    
    def pause(self):
        """Pause the playback using daemon command."""
        if self.process and self.process.poll() is None:
            try:
                modules_dir = Path(__file__).parent.parent / "modules"
                subprocess.run(
                    ["python", "walrio.py", "player", "--command", "pause"],
                    cwd=str(modules_dir),
                    timeout=2
                )
                self.pause_start = time.time()
            except Exception as e:
                print(f"Error pausing: {e}")
    
    def resume(self):
        """Resume the playback using daemon command."""
        if self.process and self.process.poll() is None:
            try:
                modules_dir = Path(__file__).parent.parent / "modules"
                subprocess.run(
                    ["python", "walrio.py", "player", "--command", "resume"],
                    cwd=str(modules_dir),
                    timeout=2
                )
                if self.pause_start:
                    self.paused_duration += time.time() - self.pause_start
                    self.pause_start = None
            except Exception as e:
                print(f"Error resuming: {e}")
    
    def stop(self):
        """Stop the playback using daemon command."""
        self.should_stop = True
        if self.process and self.process.poll() is None:
            try:
                modules_dir = Path(__file__).parent.parent / "modules"
                # Send stop command to daemon
                subprocess.run(
                    ["python", "walrio.py", "player", "--command", "stop"],
                    cwd=str(modules_dir),
                    timeout=2
                )
                # Wait a moment for graceful shutdown
                try:
                    self.process.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    self.process.terminate()
                    self.process.wait()
            except Exception as e:
                print(f"Error stopping via command: {e}")
                # Fallback to process termination if command fails
                try:
                    self.process.terminate()
                    self.process.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    self.process.kill()
                    
    def set_volume(self, volume):
        """Set the playback volume using daemon socket command.
        
        Args:
            volume (float): Volume level between 0.0 and 1.0
        """
        if self.process and self.process.poll() is None:
            try:
                import socket
                import tempfile
                import os
                
                # Find the socket file for this daemon
                temp_dir = tempfile.gettempdir()
                socket_files = []
                
                for filename in os.listdir(temp_dir):
                    if filename.startswith("walrio_player_") and filename.endswith(".sock"):
                        socket_path = os.path.join(temp_dir, filename)
                        if os.path.exists(socket_path):
                            socket_files.append((socket_path, os.path.getmtime(socket_path)))
                
                if socket_files:
                    # Use the most recent socket file
                    socket_path = max(socket_files, key=lambda x: x[1])[0]
                    
                    # Connect to socket and send volume command
                    sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
                    try:
                        sock.connect(socket_path)
                        command = f"volume {volume:.2f}"
                        sock.send(command.encode('utf-8'))
                        response = sock.recv(1024).decode('utf-8')
                        print(f"Volume command response: {response}")
                    finally:
                        sock.close()
                        
            except Exception as e:
                print(f"Error setting volume: {e}")


class SimpleMusicPlayer(QMainWindow):
    """Simple music player focused entirely on playback controls."""
    
    def __init__(self):
        """
        Initialize the SimpleMusicPlayer main window.
        
        Sets up the UI, initializes state variables, and configures timers.
        """
        super().__init__()
        self.current_file = None
        self.is_playing = False
        self.player_worker = None
        self.position = 0
        self.duration = 0
        self.is_seeking = False
        
        self.setup_ui()
        self.setup_timer()
    
    def setup_ui(self):
        """Setup the simple music player user interface."""
        self.setWindowTitle("Walrio Lite - Simple Music Player")
        self.setGeometry(300, 300, 600, 200)
        
        # Central widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)
        
        # Track info
        self.track_label = QLabel("No file selected")
        self.track_label.setAlignment(Qt.AlignCenter)
        font = QFont()
        font.setPointSize(12)
        font.setBold(True)
        self.track_label.setFont(font)
        layout.addWidget(self.track_label)
        
        # Time and progress
        time_layout = QHBoxLayout()
        self.time_current = QLabel("00:00")
        self.progress_slider = QSlider(Qt.Horizontal)
        self.progress_slider.setMinimum(0)
        self.progress_slider.setMaximum(100)
        self.progress_slider.setValue(0)
        self.progress_slider.sliderPressed.connect(self.on_seek_start)
        self.progress_slider.sliderReleased.connect(self.on_seek_end)
        self.time_total = QLabel("00:00")
        
        time_layout.addWidget(self.time_current)
        time_layout.addWidget(self.progress_slider)
        time_layout.addWidget(self.time_total)
        layout.addLayout(time_layout)
        
        # Control buttons
        controls_layout = QHBoxLayout()
        
        self.btn_open = QPushButton("Open File")
        self.btn_play_pause = QPushButton("▶ Play")
        self.btn_stop = QPushButton("⏹ Stop")
        
        # Style buttons
        button_style = """
            QPushButton {
                font-size: 14px;
                padding: 10px;
                min-width: 100px;
            }
        """
        self.btn_open.setStyleSheet(button_style)
        self.btn_play_pause.setStyleSheet(button_style)
        self.btn_stop.setStyleSheet(button_style)
        
        # Connect buttons
        self.btn_open.clicked.connect(self.open_file)
        self.btn_play_pause.clicked.connect(self.toggle_play_pause)
        self.btn_stop.clicked.connect(self.stop_playback)
        
        controls_layout.addStretch()
        controls_layout.addWidget(self.btn_open)
        controls_layout.addWidget(self.btn_play_pause)
        controls_layout.addWidget(self.btn_stop)
        controls_layout.addStretch()
        layout.addLayout(controls_layout)
        
        # Volume control
        volume_layout = QHBoxLayout()
        volume_layout.addWidget(QLabel("Volume:"))
        self.volume_slider = QSlider(Qt.Horizontal)
        self.volume_slider.setMinimum(0)
        self.volume_slider.setMaximum(100)
        self.volume_slider.setValue(70)
        self.volume_slider.setMaximumWidth(200)
        self.volume_slider.valueChanged.connect(self.on_volume_change)
        self.volume_label = QLabel("70%")
        self.volume_label.setMinimumWidth(40)
        
        volume_layout.addWidget(self.volume_slider)
        volume_layout.addWidget(self.volume_label)
        volume_layout.addStretch()
        layout.addLayout(volume_layout)
        
        # Initially disable play/stop buttons
        self.btn_play_pause.setEnabled(False)
        self.btn_stop.setEnabled(False)
    
    def setup_timer(self):
        """Setup timer for updating UI (reduced frequency since position comes from worker)."""
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_ui)
        self.timer.start(100)  # Update UI every 100ms for smooth updates
    
    def open_file(self):
        """Open an audio file for simple playback."""
        filepath, _ = QFileDialog.getOpenFileName(
            self, "Open Audio File", "",
            "Audio Files (*.mp3 *.flac *.ogg *.wav *.m4a *.aac *.opus)"
        )
        
        if filepath:
            self.current_file = filepath
            filename = Path(filepath).name
            self.track_label.setText(filename)
            
            # Reset position
            self.position = 0
            self.progress_slider.setValue(0)
            self.time_current.setText("00:00")
            
            # Get actual file duration using Walrio metadata CLI
            try:
                modules_dir = Path(__file__).parent.parent / "modules"
                result = subprocess.run(
                    ["python", "walrio.py", "metadata", "--duration", filepath],
                    cwd=str(modules_dir),
                    capture_output=True,
                    text=True,
                    timeout=10
                )
                if result.returncode == 0 and result.stdout.strip():
                    self.duration = float(result.stdout.strip())
                else:
                    self.duration = 0
            except Exception as e:
                print(f"Error getting duration: {e}")
                self.duration = 0
            
            if self.duration > 0:
                self.time_total.setText(self.format_time(self.duration))
                # Update progress slider maximum to match duration in seconds
                self.progress_slider.setMaximum(int(self.duration))
            else:
                self.time_total.setText("--:--")
                # Fallback to percentage-based progress
                self.progress_slider.setMaximum(100)
                self.show_message("Duration Warning", "Could not determine file duration. Progress bar may not be accurate.")
            
            # Enable controls
            self.btn_play_pause.setEnabled(True)
            self.btn_stop.setEnabled(True)
            
            duration_text = f"{self.format_time(self.duration)}" if self.duration > 0 else "unknown duration"
            self.show_message("File Loaded", f"Ready to play: {filename}\nDuration: {duration_text}")
    
    def toggle_play_pause(self):
        """Toggle between play, pause, and resume for simple playback."""
        if not self.current_file:
            return
        
        if self.is_playing:
            self.pause_playback()
        else:
            # Check if we have a paused player worker to resume
            if self.player_worker and not self.is_playing:
                self.resume_playback()
            else:
                # Start fresh playback
                self.start_playback()
    
    def start_playback(self):
        """Start simple audio playback."""
        if not self.current_file:
            return
        
        self.is_playing = True
        self.btn_play_pause.setText("⏸ Pause")
        self.btn_stop.setEnabled(True)
        
        # Start simple player worker
        self.player_worker = SimplePlayerWorker(self.current_file)
        self.player_worker.finished.connect(self.on_playback_finished)
        self.player_worker.error.connect(self.on_playback_error)
        self.player_worker.position_updated.connect(self.on_position_updated)
        self.player_worker.start()
    
    def pause_playback(self):
        """Pause simple audio playback using CLI command."""
        if not self.is_playing or not self.player_worker:
            return
            
        self.is_playing = False
        self.btn_play_pause.setText("▶ Resume")
        
        # Send pause command to the player
        if self.player_worker:
            self.player_worker.pause()
    
    def resume_playback(self):
        """Resume simple audio playback using CLI command."""
        if self.is_playing or not self.player_worker:
            return
        
        self.is_playing = True
        self.btn_play_pause.setText("⏸ Pause")
        
        # Send resume command to the player
        if self.player_worker:
            self.player_worker.resume()
    
    def stop_playback(self):
        """Stop simple audio playback."""
        # Set state first
        self.is_playing = False
        self.btn_play_pause.setText("▶ Play")
        
        # Immediately disable the stop button to prevent multiple clicks
        self.btn_stop.setEnabled(False)
        
        # Force GUI to update immediately
        QApplication.processEvents()
        
        if self.player_worker:
            # Stop the worker thread
            self.player_worker.stop()
            
            # Wait for the thread to finish, but with a timeout
            if not self.player_worker.wait(3000):  # Wait up to 3 seconds
                # If thread doesn't finish, terminate it forcefully
                self.player_worker.terminate()
                self.player_worker.wait()
            
            self.player_worker = None
        
        # Reset position and UI
        self.position = 0
        self.progress_slider.setValue(0)
        self.time_current.setText("00:00")
        
        # Re-enable play button (stop button already disabled above)
        self.btn_play_pause.setEnabled(True)
    
    def on_volume_change(self, value):
        """
        Handle volume slider changes in simple player.
        
        Args:
            value (int): The new volume slider value (0-100).
        """
        self.volume_label.setText(f"{value}%")
        
        # Convert slider value (0-100) to volume range (0.0-1.0)
        volume = value / 100.0
        
        # Set volume if player worker exists (playing or paused)
        if self.player_worker:
            self.player_worker.set_volume(volume)
    
    def on_seek_start(self):
        """Handle when user starts seeking in simple player."""
        self.is_seeking = True
    
    def on_seek_end(self):
        """Handle when user finishes seeking in simple player."""
        self.is_seeking = False
        # Update position based on slider value (now in seconds)
        if self.duration > 0:
            self.position = self.progress_slider.value()
            self.time_current.setText(self.format_time(self.position))
        # Note: Actual seeking would need to be implemented in the player module
    
    def on_position_updated(self, position):
        """
        Handle position updates from the simple player worker.
        
        Args:
            position (float): Current playback position in seconds.
        """
        if not self.is_seeking:
            self.position = position
            self.progress_slider.setValue(int(position))
            self.time_current.setText(self.format_time(position))
            
            # Auto-stop when reaching end
            if self.duration > 0 and position >= self.duration:
                self.stop_playback()
    
    def update_ui(self):
        """Update UI elements for simple player (called by timer)."""
        # Most updates now come from position_updated signal
        # This is just for any additional UI updates needed
        pass
    
    def format_time(self, seconds):
        """
        Format time in MM:SS format for simple player.
        
        Args:
            seconds (float): Time in seconds to format.
            
        Returns:
            str: Formatted time string in MM:SS format.
        """
        minutes = int(seconds // 60)
        seconds = int(seconds % 60)
        return f"{minutes:02d}:{seconds:02d}"
    
    def on_playback_finished(self):
        """Handle when simple playback finishes naturally."""
        self.stop_playback()
    
    def on_playback_error(self, error):
        """
        Handle simple playback errors.
        
        Args:
            error (str): Error message to display.
        """
        self.show_message("Playback Error", error)
        self.stop_playback()
    
    def show_message(self, title, message):
        """
        Show a message dialog in simple player.
        
        Args:
            title (str): Dialog window title.
            message (str): Message content to display.
        """
        QMessageBox.information(self, title, message)
    
    def closeEvent(self, event):
        """
        Handle simple player application close.
        
        Args:
            event: The close event from Qt.
        """
        if self.player_worker:
            self.player_worker.stop()
            self.player_worker.wait()
        event.accept()


def main():
    """Main entry point for Walrio Lite - Simple Music Player."""
    app = QApplication(sys.argv)
    app.setApplicationName("Walrio Lite")
    
    player = SimpleMusicPlayer()
    player.show()
    
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
