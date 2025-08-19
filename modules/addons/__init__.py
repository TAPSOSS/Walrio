#!/usr/bin/env python3
"""
Walrio Addon Modules
Copyright (c) 2025 TAPS OSS
Project: https://github.com/TAPSOSS/Walrio
Licensed under the BSD-3-Clause License (see LICENSE file for details)

Addon modules for the Walrio audio library management system.
These modules provide extended functionality for audio processing,
file management, and metadata manipulation.
"""

# Import addon modules for easier access
from . import convert
from . import file_relocater 
from . import rename
from . import replaygain

__all__ = ['convert', 'file_relocater', 'rename', 'replaygain']
