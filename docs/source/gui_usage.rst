GUI Applications
================

Walrio includes several graphical user interface applications that provide easy-to-use interfaces for music playback and management. These applications are built using modern GUI frameworks and provide intuitive controls for various Walrio features.

Overview
--------

The GUI applications are designed to be:

* **User-friendly**: Intuitive interfaces suitable for all user levels
* **Modular**: Each GUI serves a specific purpose or workflow  
* **Integrated**: Built on top of Walrio's core modules and CLI tools
* **Cross-platform**: Compatible with Windows, macOS, and Linux

**Available GUI Applications:**

* **Walrio Lite - Simple Music Player**: Walrio Lite - Simple Music Player
* **Walrio Main GUI**: Walrio Music Player GUI

Detailed Documentation
---------------------

Walrio Lite - Simple Music Player
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

**Location**: ``GUI/walrio_lite.py``

Walrio Lite - Simple Music Player

**Dependencies**:

* ``PySide6``

**Classes and Methods**:

**SimplePlayerWorker**

   Worker thread for running simple audio playback.

   **Signals**:

   * ``position_updated``
   * ``playback_finished``
   * ``error``

   **Key Methods**:

   * ``run()``
     Run the simple audio player in daemon mode.

   * ``pause()``
     Pause the playback using daemon command.

   * ``resume()``
     Resume the playback using daemon command.

   * ``stop()``
     Stop the playback using daemon command.

   * ``set_volume()``
     Set the playback volume using daemon socket command.


**SimpleMusicPlayer**

   Simple music player focused entirely on playback controls.

   **Key Methods**:

   * ``setup_ui()``
     Setup the simple music player user interface.

   * ``setup_timer()``
     Setup timer for updating UI (reduced frequency since position comes from worker).

   * ``open_file()``
     Open an audio file for simple playback.

   * ``toggle_play_pause()``
     Toggle between play, pause, and resume for simple playback.

   * ``start_playback()``
     Start simple audio playback.

   * ``pause_playback()``
     Pause simple audio playback using CLI command.

   * ``resume_playback()``
     Resume simple audio playback using CLI command.

   * ``stop_playback()``
     Stop simple audio playback.

   * ``on_volume_change()``

   * ``on_seek_start()``
     Handle when user starts seeking in simple player.

   * ``on_seek_end()``
     Handle when user finishes seeking in simple player.

   * ``on_position_updated()``

   * ``update_ui()``
     Update UI elements for simple player (called by timer).

   * ``format_time()``

   * ``on_playback_finished()``
     Handle when simple playback finishes naturally.

   * ``on_playback_error()``

   * ``show_message()``

   * ``closeEvent()``

   * ``main()``
     Main entry point for Walrio Lite - Simple Music Player.


**Usage**:

.. code-block:: bash

    python GUI/walrio_lite.py

.. note::
   This is a graphical application. Ensure you have a display environment available and the required GUI dependencies installed.


Walrio Main GUI
~~~~~~~~~~~~~~~

**Location**: ``GUI/walrio_main.py``

Walrio Music Player GUI

**Dependencies**:

* ``PySide6``

**Classes and Methods**:

**PlayerWorker**

   Worker thread for running audio playback.

   **Signals**:

   * ``position_updated``
   * ``playback_finished``
   * ``error``

   **Key Methods**:

   * ``run()``
     Run the audio player in daemon mode.

   * ``pause()``
     Pause the playback using daemon command.

   * ``resume()``
     Resume the playback using daemon command.

   * ``stop()``
     Stop the playback using daemon command.

   * ``set_volume()``
     Set the playback volume using daemon socket command.


**WalrioMusicPlayer**

   Walrio music player with full playback controls.

   **Key Methods**:

   * ``setup_ui()``
     Setup the user interface.

   * ``setup_timer()``
     Setup timer for updating UI (reduced frequency since position comes from worker).

   * ``open_file()``
     Open an audio file.

   * ``toggle_play_pause()``
     Toggle between play, pause, and resume.

   * ``start_playback()``
     Start audio playback.

   * ``pause_playback()``
     Pause audio playback using CLI command.

   * ``resume_playback()``
     Resume audio playback using CLI command.

   * ``stop_playback()``
     Stop audio playback.

   * ``on_volume_change()``

   * ``on_seek_start()``
     Handle when user starts seeking.

   * ``on_seek_end()``
     Handle when user finishes seeking.

   * ``on_position_updated()``

   * ``update_ui()``
     Update UI elements (called by timer).

   * ``format_time()``

   * ``on_playback_finished()``
     Handle when playback finishes naturally.

   * ``on_playback_error()``

   * ``show_message()``

   * ``closeEvent()``

   * ``main()``
     Main entry point for Walrio.


**Usage**:

.. code-block:: bash

    python GUI/walrio_main.py

.. note::
   This is a graphical application. Ensure you have a display environment available and the required GUI dependencies installed.


Installation Requirements
-------------------------

To run the GUI applications, you need:

**Core Dependencies:**

.. code-block:: bash

    pip install PySide6

**System Requirements:**

* **Python 3.8+** - Required Python version
* **Display Environment** - GUI applications require:
  
  * **Linux**: X11 or Wayland display server
  * **macOS**: Native Cocoa support (built-in)
  * **Windows**: Native Windows desktop (built-in)

**Audio Dependencies:**

The GUI applications use Walrio's audio modules, which may require:

* **FFmpeg** - For audio format support and metadata extraction
* **GStreamer** - For advanced audio playback features

**Installation on Different Platforms:**

.. code-block:: bash

    # Ubuntu/Debian
    sudo apt install python3-pyside6 ffmpeg gstreamer1.0-plugins-base
    
    # macOS (with Homebrew)
    brew install python-tk ffmpeg
    pip install PySide6
    
    # Windows
    pip install PySide6
    # Download FFmpeg from https://ffmpeg.org/download.html

Troubleshooting
--------------

**Common Issues:**

* **"No module named 'PySide6'"**: Install PySide6 with ``pip install PySide6``
* **"Cannot connect to display"**: Ensure you have a GUI environment running
* **Audio playback issues**: Verify FFmpeg is installed and accessible

**Getting Help:**

For more information about the underlying modules used by these GUI applications, see:

* :doc:`api/index` - API documentation for core modules
* :doc:`cli_usage` - Command-line tools used by GUI applications

Development
-----------

These GUI applications are built using:

* **PySide6/Qt6** - Cross-platform GUI framework
* **Threading** - For responsive user interfaces during audio operations
* **Walrio Modules** - Integration with core audio processing capabilities

For extending or modifying the GUI applications, refer to the source code and the detailed class documentation above.
