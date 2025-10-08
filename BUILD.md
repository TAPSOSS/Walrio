# Walrio GUI Build System

This directory contains the complete build system for creating distributable Walrio GUI applications using PyInstaller across Linux, macOS, and Windows platforms.

## Quick Start

### Prerequisites

**All Platforms:**
- Python 3.9+ 
- pip package manager

**Linux (Ubuntu/Debian):**
```bash
sudo apt-get install gstreamer1.0-tools gstreamer1.0-plugins-base gstreamer1.0-plugins-good
sudo apt-get install libgirepository1.0-dev libcairo2-dev libgtk-3-dev
```

**macOS:**
```bash
brew install gstreamer gst-plugins-base gst-plugins-good gobject-introspection gtk+3
```

**Windows:**
- Install GStreamer from https://gstreamer.freedesktop.org/download/
- Add GStreamer to your PATH environment variable

### Installation

1. **Install Python dependencies:**
   ```bash
   pip install -r requirements-build.txt
   ```

2. **Build both GUIs:**
   ```bash
   # Using the Python script (recommended)
   python build_gui.py --gui both --clean
   
   # Using Make (Linux/macOS)
   make build
   
   # Using batch file (Windows)
   build_gui.bat --both --clean
   ```

## Build Scripts

### `build_gui.py` - Main Build Script

The primary build automation script with cross-platform support.

**Usage:**
```bash
python build_gui.py [options]
```

**Options:**
- `--gui {main,lite,both}` - Which GUI to build (default: both)
- `--clean` - Clean build directories before building
- `--debug` - Build in debug mode (onedir instead of onefile)
- `--no-deps-check` - Skip dependency checking

**Examples:**
```bash
# Build both applications (recommended)
python build_gui.py --gui both --clean

# Build only WalrioMain
python build_gui.py --gui main

# Debug build with detailed output
python build_gui.py --gui both --debug --clean

# Quick rebuild without cleaning
python build_gui.py --gui lite
```

### Platform-Specific Scripts

**Linux/macOS - Makefile:**
```bash
make build          # Build both GUIs
make build-main     # Build only WalrioMain
make build-lite     # Build only WalrioLite
make clean          # Clean build directories
make deps-check     # Check dependencies
make install-deps   # Install Python dependencies
make test           # Run basic tests
```

**Windows - Batch File:**
```cmd
build_gui.bat --both --clean     # Build both (clean)
build_gui.bat --main             # Build WalrioMain only  
build_gui.bat --debug            # Debug build
build_gui.bat --help             # Show help
```

## Output Structure

After building, the `dist/` directory contains:

```
dist/
├── WalrioMain[.exe]           # Main GUI executable
├── WalrioLite[.exe]           # Lite GUI executable  
├── build_info.json            # Build metadata
├── README.txt                 # End-user documentation
├── Launch_WalrioMain.bat      # Windows launcher (Windows only)
├── Launch_WalrioLite.bat      # Windows launcher (Windows only)
├── walriomain.desktop         # Linux desktop file (Linux only)
└── walriolite.desktop         # Linux desktop file (Linux only)
```

## GitHub Actions Integration

The repository includes automated builds via GitHub Actions (`.github/workflows/build-gui.yml`):

- **Triggers:** Push to main/develop, tags, PRs, manual dispatch
- **Platforms:** Ubuntu, macOS, Windows
- **Python Versions:** 3.9, 3.10, 3.11
- **Artifacts:** Uploaded for each platform/Python combination
- **Releases:** Automatic release creation for version tags

### Using GitHub Actions

1. **Push code** to trigger builds
2. **Download artifacts** from the Actions tab
3. **Create releases** by pushing tags (e.g., `git tag v1.0.0 && git push origin v1.0.0`)

## Configuration

### Build Configuration

Edit `build_gui.py` to customize:

- **Entry points:** Modify `configs` dictionary
- **Icons:** Update icon paths in `configs`
- **Hidden imports:** Adjust `platform_configs` for additional modules
- **Additional data:** Add files/directories to bundle

### Platform-Specific Options

**Linux:**
- Creates `.desktop` files for system integration
- Includes GTK+ themes and icons
- Optimizes for distribution packaging

**macOS:**
- Generates `.app` bundles
- Code signing preparation (add certificates separately)
- Universal binary support (Intel/Apple Silicon)

**Windows:**
- Creates `.exe` executables
- Includes batch launchers
- Version information embedding
- Optional UPX compression

## Troubleshooting

### Common Issues

**Import Errors:**
```bash
# Check dependencies
python build_gui.py --no-deps-check --gui both
pip list | grep -E "(pyinstaller|PySide6|mutagen)"
```

**GStreamer Not Found:**
- Ensure GStreamer is installed system-wide
- Check PATH environment variable  
- Test with: `python -c "import gi; gi.require_version('Gst', '1.0')"`

**Large Executable Size:**
- Use `--debug` mode to identify included files
- Add exclusions in `build_gui.py` 
- Enable UPX compression (Linux)

**Permission Issues (Linux/macOS):**
```bash
chmod +x build_gui.py
chmod +x dist/WalrioMain dist/WalrioLite
```

### Debug Mode

Use debug mode to investigate build issues:

```bash
python build_gui.py --gui both --debug --clean
```

Debug mode creates `onedir` builds in `dist/` showing all included files and dependencies.

### Dependency Debugging

```bash
# Check what Python sees
python -c "import sys; print('\n'.join(sys.path))"

# Test imports manually
python -c "from GUI.WalrioMainGUI.walrio_main_app import WalrioMainApp"
python -c "from GUI.WalrioLiteGUI.walrio_lite_app import WalrioLiteApp"

# Check PyInstaller analysis
pyinstaller --log-level DEBUG GUI/walrio_main.py
```

## Performance Optimization

### Build Time
- Use `--no-deps-check` for faster rebuilds
- Keep `build/` directory between builds
- Use parallel builds in CI/CD

### Runtime Performance  
- Use `--onefile` for single executable (default)
- Use `--onedir` for faster startup (debug mode)
- Enable UPX compression where available
- Strip debug symbols in production

### File Size
- Exclude unnecessary modules in `hidden_imports`
- Use virtual environments to minimize dependencies
- Enable compression and optimization flags

## Advanced Usage

### Custom Build Hooks

Create `hooks/` directory and add PyInstaller hooks:

```python
# hooks/hook-mymodule.py  
from PyInstaller.utils.hooks import collect_data_files

datas = collect_data_files('mymodule')
```

### Code Signing

**macOS:**
```bash
codesign --force --verify --verbose --sign "Developer ID" dist/WalrioMain.app
```

**Windows:**
```cmd
signtool sign /f certificate.p12 /p password dist/WalrioMain.exe
```

### Distribution Packaging

**Linux (AppImage):**
```bash
# Use appimage-builder or similar tools
make package
```

**macOS (DMG):**
```bash
hdiutil create -volname "Walrio" -srcfolder dist/ -ov -format UDZO Walrio.dmg
```

**Windows (Installer):**
- Use NSIS, Inno Setup, or WiX Toolset
- Include Visual C++ redistributables

## Contributing

When modifying the build system:

1. **Test on all platforms** before committing
2. **Update documentation** for new options
3. **Maintain backward compatibility** where possible
4. **Follow the existing code style** and patterns
5. **Test with GitHub Actions** to verify CI/CD

## Support

- **Documentation:** See `docs/` directory  
- **Issues:** Report on GitHub repository
- **Discussions:** Use GitHub Discussions for build help
- **Wiki:** Check GitHub Wiki for additional guides

---

© 2025 TAPS OSS - Licensed under BSD-3-Clause License