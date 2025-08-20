# Walrio
Walrus Audio (Walrio) modular music player.

## Contributing/License/Documentation
This project is licensed under the BSD-3-Clause License, see the [LICENSE](LICENSE) file for details. 

If you're interested in contributing to Walrio check out our [Contributing Guide](CONTRIBUTING.md) for guidelines on how to get started and requirements for contributions. Contributors can be found in the [AUTHORS](AUTHORS) file in the repository. Documentation can be found [here](https://tapsoss.github.io/Walrio/api/).

## Requirements
`requirements.txt` is an up to date list of all Python packages that can simply be installed with `pip install -r requirements.txt` on any system with python installed.

### List of Non-Pip Requirements
- Python 3.6+ (and pip installs using pip with python and requirements.txt)
- GStreamer 1.0 (with gst-launch-1.0 command-line tool)
- FFmpeg (for most audio analysis and conversion)
- rsgain (for ReplayGain LUFS analysis)
- ImageMagick (for image conversion and processing)

### Dependency install commands
I only have the developer environment set up properly for my OS of choice (fedora), feel free to contribute the other required dependecy commands if you know them for other operating systems.

#### Fedora/RHEL/CentOS:
```bash
# Install GStreamer, FFmpeg, ImageMagick, and rsgain system packages
sudo dnf install gstreamer1-plugins-base gstreamer1-plugins-good gstreamer1-plugins-ugly gstreamer1-tools ffmpeg ImageMagick rsgain

# Install Python dependencies
pip install -r requirements.txt
```

## File Overview
The sphinx documentation gives a nice overview of the files and what they do [click here](https://tapsoss.github.io/Walrio/api/index.html#module-overview) to go check that out before asking any questions. The structure below is just the grant overview.

### .github
This is where automated GitHub scritps run to do things like check pull requests, auto-build docs, build and GUIs, and more.

### GUI
This is where you can find the official/mainline GUI versions of Walrio which should always stay up to date and are made to make it possible to just click around to use this music player like you would any other music player. If lots of folks start making their own UIs, I will try to find a way to simply have a webpage linking to all their repos directly which can be submitted to so those GUIs can be easily browsed and users can install the GUI they like most so that this repository doesn't get cluttered or large in size.

### Docs
The Docs folder is where sphinx documentation files go to auto-generate the relevant [documentation](https://tapsoss.github.io/Walrio/) for this project.

### Modules
Modules are the actually music player modules to be used in the backend of any GUI made with Walrio. Their specific features can be viewed in the [API documentation](https://tapsoss.github.io/Walrio/api/index.html). All of the different modules can and should be called directly from 'walrio.py' which is in the root of modules folder itself, but should also work in the CLI (command line interface) on their own.

#### Addons
Addons are modules that greatly assist a standard music player but aren't technically needed to play music (such as converters, album art fetchers, etc.).

#### Core
Essential core libraries are modules that are 100% needed for a standard audio player (play music, analyze, etc.) or are referenced by a large amount of other scripts/files.

#### Niche
The Niche folder is for niche scripts/features for specific devices or workflows (scripts to hook up to lighting system, to be used with NAS, apply gain directly to files, etc.).

### Testing Files
This is where simple audio and playlist files for testing purposes are stored. The files in there were made by [@tapscodes](https://github.com/tapscodes) and aren't super pleasent to listen to but are guaranteed to be legally safe. When testing/writing code, it's best to use your own real music files for testing but these files are there for those who don't have those files.