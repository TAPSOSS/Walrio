# Walrio
Walrus Audio (Walrio) modular music player.

## Contributing
If you're interested in contributing to Walrio? Check out our [Contributing Guide](CONTRIBUTING.md) for guidelines on how to get started and requirements for contributions.

## License
This project is licensed under the BSD-3-Clause License, see the [LICENSE](LICENSE) file for details. 

## Requirements
```requirements.txt``` is an up to date list of all packages that can simply be installed with ```pip install -r requirements.txt``` on any system with python installed.

### List of Requirements
- Python 3.6+ (and pip installs using pip with python and requirements.txt)
- GStreamer 1.0 (with gst-launch-1.0 command-line tool)

### Dependency install commands
I only have the developer environment set up properly for my OS of choice (fedora), feel free to contribute the other required dependecy commands if you know them for other operating systems.

#### Fedora/RHEL/CentOS:
```bash
sudo dnf install gstreamer1-plugins-base gstreamer1-plugins-good gstreamer1-plugins-ugly gstreamer1-tools
pip install -r requirements.txt
```

## File Overview

### GUI
GUI versions of Walrio to make it easier to use the modules without needing the command line or to standardize the command line commands.

### Modules
Modules to be used in the backend of any GUI made with Walrio.

#### Addons
Addons that greatly assist a standard music player but aren't technically needed to play music (such as converters, album art fetchers, etc.).
- N/A

#### Libraries
Essential libraries 100% needed for a standard audio player (play music, analyze, etc.).
- audio_player.py: plays specified song file using gstreamer
- audio_library.py: analyzes given directory to make sqlite file containing useful info such as metadata, url, etc.
- audio_queue.py: stores a list of songs in order to be played by audio_player.py and queues them up when the previous song finishes.

#### Niche
Niche scripts/features for specific devices or workflows (scripts to hook up to lighting system, NAS, etc.).
- N/A