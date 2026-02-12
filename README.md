# Walrio GUI

Walrio is a modular library/set of files that let you play, manage, and edit music and music-related files. Every file should be usable via the terminal except documentation.

## Contributing

For those interested in contributing code/documentation, please check the [contribution guidelines](https://github.com/TAPSOSS/.github/blob/main/CONTRIBUTING.md). On top of these guidelines, this specific project requires a single comment at the top of each file explaining what it does so that help commands properlyload dynmically. TODO: add this to a CONTRIBUTING.md later.

All current contributors are listed both in the sidebar and (optionally) in the [AUTHORS](AUTHORS) file.

## Star History

[![Star History Chart](https://api.star-history.com/svg?repos=TAPSOSS/Walrio&type=date&legend=top-left)](https://www.star-history.com/#TAPSOSS/Walrio&type=date&legend=top-left)

## Licensing (USE IN OTHER PROJECTS)

Check out the [LICENSE file](LICENSE) to see what LICENSE this project uses and how you're allowed to use it. General rule of thumb is attribution (crediting) is required at a minimum.

## Built Instructions (For Devs)

1. Install [Python](https://python.org).
2. Install non-python libraries (listed in third-party credits below).
   On fedora this can be done with the following command:

   ```bash
   sudo dnf install gstreamer1-plugins-base gstreamer1-plugins-good gstreamer1-plugins-ugly gstreamer1-tools ffmpeg ImageMagick rsgain
   ```

3. Install Python dependencies

   ```bash
   pip install -r requirements.txt
   ```

4. Use any command through walrio.py by running it as a python script/file.
   Try either `python walrio.py --help` or `python3 walrio.py --help` depending on your operating system to see what modules you can use and then further flag and whatnot from there to see what each individual module can do (`python walrio.py player --help` for example).

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

#### Niche

Very specific workflow related files or extremely niche functionality. Generally files combining multiple different core and addon modules together into a singular unified workflow or something to connect your music to external programs/hardware.
