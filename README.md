# Walrio GUI
Walrio is a modular library/set of files that let you play, manage, and edit music and music-related files. Every file should be usable via the terminal except documentation.

## Contributing
For those interested in contributing code/documentation, please check the [contribution guidelines](https://github.com/TAPSOSS/.github/blob/main/CONTRIBUTING.md).

All current contributors are listed both in the sidebar and (optionally) in the [AUTHORS](AUTHORS) file.

## Star History

[![Star History Chart](https://api.star-history.com/svg?repos=TAPSOSS/Walrio&type=date&legend=top-left)](https://www.star-history.com/#TAPSOSS/Walrio&type=date&legend=top-left)

## Licensing (USE IN OTHER PROJECTS)
Check out the [LICENSE file](LICENSE) to see what LICENSE this project uses and how you're allowed to use it. General rule of thumb is attribution (crediting) is required at a minimum.

## Built Instructions (For Devs)
1. Install [Python](https://python.org).
2. Install non-python libraries (listed in third-party credits below).
On fedora this can be done with the following command:
```sudo dnf install gstreamer1-plugins-base gstreamer1-plugins-good gstreamer1-plugins-ugly gstreamer1-tools ffmpeg ImageMagick rsgain```
3. Install Python dependencies
```pip install -r requirements.txt```
4. Use any command through walrio.py by running it as a python script/file.
Try either `python walrio.py --help` or `python3 walrio.py --help` depending on your operating system to see what modules you can use and then further flag and whatnot from there to see what each individual module can do (`python walrio.py player --help` for example).

## Third-Party Credits
Walrio uses/requires/bundles the following projects (and [python](https://www.python.org/)):

### Non-Python
- **GStreamer** : https://github.com/GStreamer/gstreamer
- **FFmpeg** : https://github.com/FFmpeg/FFmpeg
- **rsgain** : https://github.com/complexlogic/rsgain
- **ImageMagick**: https://github.com/ImageMagick/ImageMagick
### Python/Pip-Installable
Check the [requirements.txt](requirements.txt) file to see what to install with pip/python in order to use this library.