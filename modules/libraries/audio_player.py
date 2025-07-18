#!/usr/bin/env python3
"""
Audio Player using GStreamer

Copyright (c) 2025 TAPSOSS
Project: https://github.com/TAPSOSS/Walrio
Licensed under the BSD-3-Clause License (see LICENSE file for details)

A simple audio player that uses gst-launch-1.0 to play audio files.
Sample Usage: python audioplayer.py <filepath>
"""

import sys
import os
import subprocess
import argparse
from pathlib import Path

# plays audio file using GStreamer's gst-launch 1.0 command with the filepath provided as a string
def play_audio(filepath):
    #use absolute path of file
    absolute_path = os.path.abspath(filepath)
    
    # check if file exists
    if not os.path.exists(absolute_path):
        print(f"Error: File '{filepath}' not found.")
        return False
    
    # check that it's a file and not directory
    if not os.path.isfile(absolute_path):
        print(f"Error: '{filepath}' is not a file.")
        return False

    # construct the GStreamer command (use playbin for compatibility and simplicity)
    uri = f"file://{absolute_path}"
    command = ["gst-launch-1.0", "playbin", f"uri={uri}"]
    
    print(f"Playing: {filepath}")
    print(f"Command: {' '.join(command)}")
    
    try:
        # run the GStreamer command
        result = subprocess.run(command, check=True)
        return True
    except subprocess.CalledProcessError as e:
        print(f"Error playing audio: {e}")
        return False
    except FileNotFoundError:
        print("Error: gst-launch-1.0 not found. Please install GStreamer.")
        return False
    except KeyboardInterrupt:
        print("\nPlayback interrupted by user.")
        return True

# main function to handle command line arguments and play audio
def main():
    parser = argparse.ArgumentParser(
        description="Audio Player using GStreamer",
        epilog="Example: python audioplayer.py /path/to/song.mp3"
    )
    parser.add_argument(
        "filepath",
        help="Path to the audio file to play"
    )

    # parse argument and play file
    args = parser.parse_args()
    success = play_audio(args.filepath)
    
    # exit with appropriate code for success or failure
    sys.exit(0 if success else 1)

# run file
if __name__ == "__main__":
    main()