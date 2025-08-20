Walrio Developer Documentation
================================

Walrio is a modular Python application framework designed for extensibility and dynamic module loading. This documentation is intended for developers who want to understand the codebase, contribute to the project, or build modules and extensions.

.. toctree::
   :maxdepth: 2
   :caption: API Reference

   api/index

.. toctree::
   :maxdepth: 2
   :caption: Command Line Tools

   cli_usage

Overview
--------

Walrio follows a modular architecture where functionality is provided through dynamically loaded modules. The core framework handles module discovery, loading, dependency management, and provides a plugin system for extending functionality.

**Unified Interface**: All modules can be accessed through the unified ``walrio.py`` interface:

.. code-block:: bash

    python modules/walrio.py <module> [args...]
    python modules/walrio.py --help  # Show all available modules
    python modules/walrio.py list    # List modules by category

Key Components
--------------

* **Core Framework**: The main application framework that handles module lifecycle
* **Module System**: Dynamic module loading and dependency resolution  
* **Addon System**: Plugin architecture for extending functionality
* **GUI Components**: Optional graphical user interface modules
* **Unified CLI**: Single entry point (``walrio.py``) for all command-line tools

Architecture
------------

The Walrio framework is built around several core concepts:

**Modular Design**
   The application is structured as a collection of loosely coupled modules that can be dynamically loaded and unloaded at runtime.

**Plugin System**
   Addons provide a way to extend core functionality without modifying the base framework.

**Library Modules**
   Core functionality is provided through library modules including:
   
   * **Playlist Management** - Handles audio playlist creation and manipulation
   * **Audio Player** - Provides audio playback capabilities
   * **Database Operations** - Manages persistent data storage
   * **Queue Management** - Handles playback queues and ordering

Getting Started
---------------

To explore the codebase:

1. **Use the Unified Interface** - Run ``python modules/walrio.py --help`` to see all available tools
2. **Browse the API Reference** - See :doc:`api/index` for detailed module documentation
3. **Review Core Modules** - Check the modules/ directory for the main application logic
4. **Examine Addons** - Look at modules/addons/ for extension examples
5. **Try Command Line Tools** - See :doc:`cli_usage` for practical examples

**Quick Start with Command Line Tools:**

.. code-block:: bash

    # See all available modules
    python modules/walrio.py list
    
    # Get help for any module
    python modules/walrio.py <module> --help
    
    # Example: Convert audio files
    python modules/walrio.py convert input.wav --format mp3

Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`