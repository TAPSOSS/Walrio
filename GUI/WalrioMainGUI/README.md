# WalrioMainGUI - MVC Architecture

This directory contains the refactored Walrio GUI using Model-View-Controller (MVC) architecture, following the pattern used in [MuseAmp](https://github.com/tapscodes/MuseAmp).

## Structure

```
WalrioMainGUI/
├── __init__.py              # Package initialization
├── __main__.py              # Module entry point (python -m WalrioMainGUI)
├── main.py                  # Main application entry point
├── models/                  # Data models and business logic
│   ├── __init__.py
│   ├── data_models.py       # Song, Playlist, ApplicationState classes
│   └── workers.py           # QueueWorker, PlayerWorker background threads
├── views/                   # UI components
│   ├── __init__.py
│   ├── base_view.py         # Base view class with common functionality
│   ├── main_window.py       # Main window layout
│   ├── playlist_sidebar.py  # Playlist sidebar widget
│   ├── queue_view.py        # Queue table and controls
│   ├── playlist_content_view.py # Playlist content display
│   └── controls_view.py     # Playback controls and progress
└── controllers/             # Business logic coordinators
    ├── __init__.py
    ├── main_controller.py   # Main application controller
    ├── playlist_controller.py # Playlist management
    ├── queue_controller.py  # Queue management
    └── playback_controller.py # Playback control
```

## Running the MVC Version

### Option 1: Standalone Script (Recommended)
```bash
cd GUI
python walrio_main_mvc.py
```

### Option 2: As a Module
```bash
cd GUI
python -m WalrioMainGUI
```

### Option 3: Direct Import
```python
from WalrioMainGUI.main import main
main()
```

## Architecture Overview

### Models (`models/`)
- **`data_models.py`**: Contains data structures (Song, Playlist, ApplicationState)
- **`workers.py`**: Background thread classes (QueueWorker for metadata, PlayerWorker for audio)

### Views (`views/`)
- **`base_view.py`**: Common UI functionality and message dialogs
- **`main_window.py`**: Main window layout with splitter and tabs
- **`playlist_sidebar.py`**: Playlist management sidebar
- **`queue_view.py`**: Queue table with drag-and-drop reordering
- **`playlist_content_view.py`**: Selected playlist content display
- **`controls_view.py`**: Playback controls, progress slider, volume

### Controllers (`controllers/`)
- **`main_controller.py`**: Coordinates all other controllers and manages app lifecycle
- **`playlist_controller.py`**: Handles playlist loading, display, and queue integration
- **`queue_controller.py`**: Manages queue operations and metadata processing
- **`playback_controller.py`**: Controls audio playback and player state

## Key Benefits of MVC Architecture

1. **Separation of Concerns**: UI, business logic, and data are clearly separated
2. **Maintainability**: Each component has a single responsibility
3. **Testability**: Controllers can be tested independently of UI
4. **Reusability**: Views and models can be reused in different contexts
5. **Scalability**: New features can be added without affecting existing code

## Signal Flow

The application uses Qt signals and slots for communication between components:

```
View → Controller → Model → Controller → View
```

Example: Adding files to queue
1. `QueueView` emits `files_add_requested` signal
2. `QueueController` receives signal and starts `QueueWorker`
3. `QueueWorker` processes files and emits `file_processed` signals
4. `QueueController` updates `ApplicationState` and emits `queue_updated`
5. Views update their display based on the new state

## Migration from Original

The original `walrio_main.py` (2393 lines) has been split into:
- 8 view files (~200-300 lines each)
- 4 controller files (~200-400 lines each) 
- 2 model files (~150-500 lines each)
- Supporting files and documentation

This makes the codebase much more manageable and follows software engineering best practices.