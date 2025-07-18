# Walrio
Walrus Audio (Walrio) modular music player.

## Requirements

```requirements.txt``` is an up to date list of all packages that can simply be installed with ```pip install -r requirements.txt``` on any system with python installed.

### List of Non-Pip Requirements
- Python 3.6+
- GStreamer 1.0 (with gst-launch-1.0 command-line tool)

### List of Pip Requirements 
- None

### Audio Player Requirements
The audio player module (`modules/addons/audio_player.py`) requires:
- Python 3.6+
- GStreamer 1.0


## Dependency install commands
I only have the developer environment set up properly for my OS of choice (fedora), feel free to contribute the other required dependecy commands if you know them for other operating systems.

### Fedora/RHEL/CentOS:
```bash
sudo dnf install gstreamer1-plugins-base gstreamer1-plugins-good gstreamer1-plugins-ugly gstreamer1-tools
pip install -r requirements.txt
```

### Usage Example (will be moved to docs later):
```bash
# Play an audio file using the audio player module
python3 modules/addons/audio_player.py testing_files/test.flac
```

## File Overview

### Modules

#### Addons
- audio_player.py: plays specified song file using gstreamer
- audio_library.py: analyzes given directory to make sqlite file containing useful info such as metadata, url, etc.

#### Libraries
Essential libraries 100% needed for a standard audio player.
- N/A

#### Niche
Niche scripts/features for specific devices or workflows
- N/A 