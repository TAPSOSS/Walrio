# Walrio GUI

Walrio is a modular library/set of files that let you play, manage, and edit music and music-related files. Every file should be usable via the terminal except documentation.

## Contributing

For those interested in contributing code/documentation, please check the [contribution guidelines](https://github.com/TAPSOSS/.github/blob/main/CONTRIBUTING.md). On top of these guidelines, this specific project requires a single comment at the top of each file explaining what it does so that help commands properlyload dynmically. TODO: add this to a CONTRIBUTING.md later.

All current contributors are listed both in the sidebar and (optionally) in the [AUTHORS](AUTHORS) file.

## Star History

[![Star History Chart](https://api.star-history.com/svg?repos=TAPSOSS/Walrio&type=date&legend=top-left)](https://www.star-history.com/#TAPSOSS/Walrio&type=date&legend=top-left)

## Licensing (USE IN OTHER PROJECTS)

Check out the [LICENSE file](LICENSE) to see what LICENSE this project uses and how you're allowed to use it. General rule of thumb is attribution (crediting) is required at a minimum.

## Installation

### Quick Install (pip)

```bash
pip install walrio
```

**⚠️ Important:** Walrio requires system dependencies that pip cannot install:
- FFmpeg
- GStreamer
- ImageMagick
- rsgain

After installing via pip, check for missing dependencies:

```bash
walrio dependency_checker --verbose
```

Then install any missing system packages (see [System Requirements](#system-requirements) below).

If you have all the needed dependencies, you can get started using walrio with the help command (`walrio --help`).

### System Requirements

Walrio requires the following non-Python tools to be installed on your system:

- **FFmpeg** - Audio/video conversion and processing
- **GStreamer** - Audio playback engine
- **ImageMagick** - Image processing for album art
- **rsgain** - ReplayGain 2.0 loudness scanner

**Installation by platform:**

**Fedora:**
```bash
sudo dnf install gstreamer1-plugins-base gstreamer1-plugins-good gstreamer1-plugins-ugly gstreamer1-tools ffmpeg ImageMagick rsgain
```

**Ubuntu/Debian:**
```bash
sudo apt install gstreamer1.0-tools gstreamer1.0-plugins-base gstreamer1.0-plugins-good gstreamer1.0-plugins-ugly ffmpeg imagemagick
# rsgain: See https://github.com/complexlogic/rsgain
```

**Arch Linux:**
```bash
sudo pacman -S gstreamer gst-plugins-base gst-plugins-good gst-plugins-ugly ffmpeg imagemagick
yay -S rsgain  # or use another AUR helper
```

**macOS:**
```bash
brew install gstreamer gst-plugins-base gst-plugins-good gst-plugins-ugly ffmpeg imagemagick rsgain
```

## Development Setup

1. Clone the repository
   ```bash
   git clone https://github.com/TAPSOSS/Walrio.git
   cd Walrio
   ```

2. Install system dependencies (see [System Requirements](#system-requirements) above)

3. Install in editable mode with dev dependencies
   ```bash
   pip install -e .[dev]
   ```

4. Verify dependencies
   ```bash
   walrio dependency_checker --verbose
   ```

5. Run Walrio
   ```bash
   walrio --help
   walrio player song.mp3
   ```

## Third-Party Credits

Walrio uses/requires/bundles the following projects (and [python](https://www.python.org/)):

### Non-Python

- **GStreamer** : <https://github.com/GStreamer/gstreamer>
- **FFmpeg** : <https://github.com/FFmpeg/FFmpeg>
- **rsgain** : <https://github.com/complexlogic/rsgain>
- **ImageMagick**: <https://github.com/ImageMagick/ImageMagick>

### Python/Pip-Installable

Check the [requirements.txt](requirements.txt) file to see what to install with pip/python in order to use this library.

## File Structure

### Modules

The main folder with all the seperate walrio music modules you can use and walrio.py,
the global file that lets you easily run any file without having the CD into each folder.

#### Addons

Files that are non-essential for playing music but are still very nice to have/relevant for maintaining a music library (converter files, replay gain, move files, etc.). Can require modules from the addons folder itself or the core modules.

#### Core

The core set of modules that are absolutely essential to playing your music files from your media library. Often required for addons/niche modules to function.

#### Database

Modules that require a SQLite database (walrio_library.db/database.py from the core section) to function. These provide advanced library management features like playback statistics, smart playlists, and database-powered queues. The database must be created first using the database module.

#### Niche

Very specific workflow related files or extremely niche functionality. Generally files combining multiple different core and addon modules together into a singular unified workflow or something to connect your music to external programs/hardware.
