GUI Applications
================

Walrio includes several graphical user interface applications that provide easy-to-use interfaces for music playback and management. These applications are built using modern GUI frameworks and provide intuitive controls for various Walrio features.

Overview
--------

The GUI system follows a clear organizational pattern:

* **GUI Runners**: Any ``.py`` file in the ``GUI/`` directory is a launcher for a specific user interface
* **Structured Architecture**: Complex GUIs use organized component architecture in subdirectories
* **Purpose-Built**: Each GUI serves a specific use case (simple playback, full management, etc.)
* **Extensible**: New GUIs can be added by creating new runner files

The GUI applications are designed to be:

* **User-friendly**: Intuitive interfaces suitable for all user levels
* **Modular**: Each GUI serves a specific purpose or workflow  
* **Integrated**: Built on top of Walrio's core modules and CLI tools
* **Cross-platform**: Compatible with Windows, macOS, and Linux
* **Architecturally Sound**: Following established patterns for maintainability

**Available GUI Applications:**

* **Walrio Lite GUI - Standalone launcher**: Lightweight GUI interface for basic operations
* **Walrio GUI - Standalone launcher**: Primary GUI interface with full feature set
* **WalrioLiteGUI (Structured Architecture)**: Lightweight music player with organized component architecture
* **WalrioMainGUI (Structured Architecture)**: Full-featured music player with organized component architecture

Detailed Documentation
---------------------

WalrioMainGUI - Full-Featured GUI Architecture
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

**Location**: ``GUI/WalrioMainGUI/``

The WalrioMainGUI application follows a structured component architecture, providing a clean separation of concerns for this full-featured music player GUI.

**Component Structure**:

.. code-block:: text

    WalrioMainGUI/
    ├── main.py                  # Main application entry point
    ├── __main__.py              # Module entry point
    ├── models/                  # Data models and business logic
    │   ├── data_models.py
    │   ├── workers.py
    ├── views/                   # UI components
    │   ├── base_view.py
    │   ├── controls_view.py
    │   ├── main_window.py
    │   ├── playlist_content_view.py
    │   ├── playlist_sidebar.py
    │   ├── queue_view.py
    └── controllers/             # Business logic coordinators
        ├── main_controller.py
        ├── playback_controller.py
        ├── playlist_controller.py
        ├── queue_controller.py

**Models**:

Data models and business logic components:

* **data_models.py**: Data models for Walrio GUI

* **workers.py**: Worker classes for background tasks in Walrio GUI
  
  * ``QueueWorker`` - Worker thread for queue operations like metadata extraction.
    (2 public methods, 3 signals)
  
  * ``PlayerWorker`` - Worker thread for handling audio playback operations with event-based communication.
    (9 public methods, 4 signals)

**Views**:

User interface components:

* **base_view.py**: Base view class for Walrio GUI components
  
  * ``BaseView`` - Base class for all view components.
    (3 public methods)

* **controls_view.py**: Control view for Walrio GUI
  
  * ``ControlsView`` - Playback controls widget.
    (15 public methods, 9 signals)

* **main_window.py**: Main window view for Walrio GUI
  
  * ``MainWindow`` - Main window for the Walrio music player.
    (7 public methods, 1 signals)

* **playlist_content_view.py**: Playlist content view for Walrio GUI
  
  * ``PlaylistContentView`` - Playlist content tab widget for viewing selected playlist contents.
    (5 public methods, 2 signals)

* **playlist_sidebar.py**: Playlist sidebar view for Walrio GUI
  
  * ``PlaylistSidebarView`` - Playlist sidebar widget for managing playlists.
    (6 public methods, 4 signals)

* **queue_view.py**: Queue view for Walrio GUI
  
  * ``QueueView`` - Queue tab widget for managing the playback queue.
    (7 public methods, 6 signals)

**Controllers**:

Business logic coordinators:

* **main_controller.py**: Main controller for Walrio GUI
  
  * ``MainController`` - Main controller that coordinates all components of the Walrio GUI.
    (2 public methods)

* **playback_controller.py**: Playback controller for Walrio GUI
  
  * ``PlaybackController`` - Controller for playback management.
    (3 public methods, 3 signals)

* **playlist_controller.py**: Playlist controller for Walrio GUI
  
  * ``PlaylistController`` - Controller for playlist management.

* **queue_controller.py**: Queue controller for Walrio GUI
  
  * ``QueueController`` - Controller for queue management.
    (2 public methods, 3 signals)

**Usage**:

.. code-block:: bash

    # Run the WalrioMainGUI application
    python GUI/walrio_main.py
    
    # Or as a module
    python -m GUI.WalrioMainGUI

**Structured Architecture Benefits**:

* **Separation of Concerns**: UI, business logic, and data are clearly separated
* **Maintainability**: Each component has a single responsibility
* **Testability**: Controllers can be tested independently of UI
* **Reusability**: Views and models can be reused in different contexts
* **Scalability**: New features can be added without affecting existing code


WalrioLiteGUI - Lightweight GUI Architecture
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

**Location**: ``GUI/WalrioLiteGUI/``

The WalrioLiteGUI application follows a structured component architecture, providing a clean separation of concerns for this lightweight, simple music player GUI.

**Component Structure**:

.. code-block:: text

    WalrioLiteGUI/
    ├── main.py                  # Main application entry point
    ├── __main__.py              # Module entry point
    ├── models/                  # Data models and business logic
    │   ├── data_models.py
    │   ├── workers.py
    ├── views/                   # UI components
    │   ├── base_view.py
    │   ├── controls_view.py
    │   ├── main_window.py
    │   ├── playlist_content_view.py
    │   ├── playlist_sidebar.py
    │   ├── queue_view.py
    └── controllers/             # Business logic coordinators
        ├── main_controller.py
        ├── playback_controller.py
        ├── playlist_controller.py
        ├── queue_controller.py

**Models**:

Data models and business logic components:

* **data_models.py**: Data models for Walrio GUI

* **workers.py**: Worker classes for background tasks in Walrio GUI
  
  * ``QueueWorker`` - Worker thread for queue operations like metadata extraction.
    (2 public methods, 3 signals)
  
  * ``PlayerWorker`` - Worker thread for handling audio playback operations with event-based communication.
    (9 public methods, 4 signals)

**Views**:

User interface components:

* **base_view.py**: Base view class for Walrio GUI components
  
  * ``BaseView`` - Base class for all view components.
    (3 public methods)

* **controls_view.py**: Control view for Walrio GUI
  
  * ``ControlsView`` - Playback controls widget.
    (15 public methods, 9 signals)

* **main_window.py**: Main window view for Walrio GUI
  
  * ``MainWindow`` - Main window for the Walrio music player.
    (7 public methods, 1 signals)

* **playlist_content_view.py**: Playlist content view for Walrio GUI
  
  * ``PlaylistContentView`` - Playlist content tab widget for viewing selected playlist contents.
    (5 public methods, 2 signals)

* **playlist_sidebar.py**: Playlist sidebar view for Walrio GUI
  
  * ``PlaylistSidebarView`` - Playlist sidebar widget for managing playlists.
    (6 public methods, 4 signals)

* **queue_view.py**: Queue view for Walrio GUI
  
  * ``QueueView`` - Queue tab widget for managing the playback queue.
    (7 public methods, 6 signals)

**Controllers**:

Business logic coordinators:

* **main_controller.py**: Main controller for Walrio GUI
  
  * ``MainController`` - Main controller that coordinates all components of the Walrio GUI.
    (2 public methods)

* **playback_controller.py**: Playback controller for Walrio GUI
  
  * ``PlaybackController`` - Controller for playback management.
    (3 public methods, 3 signals)

* **playlist_controller.py**: Playlist controller for Walrio GUI
  
  * ``PlaylistController`` - Controller for playlist management.

* **queue_controller.py**: Queue controller for Walrio GUI
  
  * ``QueueController`` - Controller for queue management.
    (2 public methods, 3 signals)

**Usage**:

.. code-block:: bash

    # Run the WalrioLiteGUI application
    python GUI/walrio_lite.py
    
    # Or as a module
    python -m GUI.WalrioLiteGUI

**Structured Architecture Benefits**:

* **Separation of Concerns**: UI, business logic, and data are clearly separated
* **Maintainability**: Each component has a single responsibility
* **Testability**: Controllers can be tested independently of UI
* **Reusability**: Views and models can be reused in different contexts
* **Scalability**: New features can be added without affecting existing code


Walrio Lite GUI - Standalone launcher
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

**Location**: ``GUI/walrio_lite.py``

**Purpose**: Lightweight GUI interface for basic operations

.. note::
   This is a GUI runner file. All ``.py`` files in the GUI directory are launchers for specific user interfaces.

**Dependencies**:

* ``PySide6``

**Usage**:

.. code-block:: bash

    python GUI/walrio_lite.py

.. note::
   This is a graphical application. Ensure you have a display environment available and the required GUI dependencies installed.


Walrio GUI - Standalone launcher
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

**Location**: ``GUI/walrio_main.py``

**Purpose**: Primary GUI interface with full feature set

.. note::
   This is a GUI runner file. All ``.py`` files in the GUI directory are launchers for specific user interfaces.

**Dependencies**:

* ``PySide6``

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
