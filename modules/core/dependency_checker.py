#!/usr/bin/env python3
"""Check for required system dependencies (FFmpeg, GStreamer, ImageMagick, rsgain).

This module provides functionality to verify that all required system-level
dependencies are installed and accessible. It checks for FFmpeg, GStreamer,
ImageMagick, and rsgain, which are required by various Walrio modules.
"""

import subprocess
import sys
import argparse
from typing import Dict, List, Tuple

class DependencyChecker:
    """Verify system dependencies for Walrio modules.
    
    This class checks for the availability of required system-level tools
    and provides installation instructions for missing dependencies.
    """
    
    # Define all required dependencies with their check commands and installation hints
    DEPENDENCIES = {
        'ffmpeg': {
            'check_cmd': ['ffmpeg', '-version'],
            'description': 'Audio/video conversion and processing',
            'install': {
                'ubuntu/debian': 'sudo apt install ffmpeg',
                'fedora': 'sudo dnf install ffmpeg',
                'arch': 'sudo pacman -S ffmpeg',
                'macos': 'brew install ffmpeg',
                'windows': 'Download from https://ffmpeg.org/download.html'
            },
            'used_by': ['convert', 'apply_loudness', 'resize_album_art']
        },
        'ffprobe': {
            'check_cmd': ['ffprobe', '-version'],
            'description': 'Media file analysis (part of FFmpeg)',
            'install': {
                'ubuntu/debian': 'sudo apt install ffmpeg',
                'fedora': 'sudo dnf install ffmpeg',
                'arch': 'sudo pacman -S ffmpeg',
                'macos': 'brew install ffmpeg',
                'windows': 'Included with FFmpeg'
            },
            'used_by': ['file_relocater']
        },
        'gstreamer': {
            'check_cmd': ['gst-inspect-1.0', '--version'],
            'description': 'GStreamer multimedia framework',
            'install': {
                'ubuntu/debian': 'sudo apt install gstreamer1.0-tools gstreamer1.0-plugins-base gstreamer1.0-plugins-good gstreamer1.0-plugins-ugly',
                'fedora': 'sudo dnf install gstreamer1-plugins-base gstreamer1-plugins-good gstreamer1-plugins-ugly gstreamer1-tools',
                'arch': 'sudo pacman -S gstreamer gst-plugins-base gst-plugins-good gst-plugins-ugly',
                'macos': 'brew install gstreamer gst-plugins-base gst-plugins-good gst-plugins-ugly',
                'windows': 'Download from https://gstreamer.freedesktop.org/download/'
            },
            'used_by': ['player']
        },
        'imagemagick': {
            'check_cmd': ['convert', '-version'],
            'description': 'ImageMagick image processing',
            'install': {
                'ubuntu/debian': 'sudo apt install imagemagick',
                'fedora': 'sudo dnf install ImageMagick',
                'arch': 'sudo pacman -S imagemagick',
                'macos': 'brew install imagemagick',
                'windows': 'Download from https://imagemagick.org/script/download.php'
            },
            'used_by': ['resize_album_art']
        },
        'rsgain': {
            'check_cmd': ['rsgain', '--version'],
            'description': 'ReplayGain 2.0 loudness scanner',
            'install': {
                'ubuntu/debian': 'See https://github.com/complexlogic/rsgain',
                'fedora': 'sudo dnf install rsgain',
                'arch': 'yay -S rsgain',
                'macos': 'brew install rsgain',
                'windows': 'Download from https://github.com/complexlogic/rsgain/releases'
            },
            'used_by': ['replay_gain']
        }
    }
    
    def check_dependency(self, name: str) -> Tuple[bool, str]:
        """
        Check if a dependency is available.
        
        Args:
            name: Name of the dependency to check
            
        Returns:
            Tuple of (is_available, version_or_error)
        """
        dep_info = self.DEPENDENCIES.get(name)
        if not dep_info:
            return False, f"Unknown dependency: {name}"
        
        try:
            result = subprocess.run(
                dep_info['check_cmd'],
                capture_output=True,
                text=True,
                timeout=5
            )
            
            if result.returncode == 0:
                # Extract version from first line of output
                version_line = result.stdout.split('\n')[0] if result.stdout else "installed"
                return True, version_line
            else:
                return False, "Command failed"
                
        except FileNotFoundError:
            return False, "Not found"
        except subprocess.TimeoutExpired:
            return False, "Timeout"
        except Exception as e:
            return False, str(e)
    
    def check_all(self) -> Dict[str, Tuple[bool, str]]:
        """
        Check all dependencies.
        
        Returns:
            Dictionary mapping dependency names to (is_available, version_or_error)
        """
        results = {}
        for dep_name in self.DEPENDENCIES:
            results[dep_name] = self.check_dependency(dep_name)
        return results
    
    def print_report(self, results: Dict[str, Tuple[bool, str]], verbose: bool = False):
        """
        Print a formatted report of dependency status.
        
        Args:
            results: Dictionary from check_all()
            verbose: If True, show installation instructions for missing deps
        """
        print("Walrio System Dependency Check")
        print("=" * 80)
        print()
        
        missing = []
        available = []
        
        for dep_name, (is_available, info) in sorted(results.items()):
            dep_info = self.DEPENDENCIES[dep_name]
            status = "✓" if is_available else "✗"
            
            if is_available:
                available.append(dep_name)
                print(f"{status} {dep_name:20} - {info[:60]}")
            else:
                missing.append(dep_name)
                print(f"{status} {dep_name:20} - {info}")
        
        print()
        print(f"Available: {len(available)}/{len(results)}")
        
        if missing:
            print()
            print("MISSING DEPENDENCIES:")
            print("-" * 80)
            
            for dep_name in missing:
                dep_info = self.DEPENDENCIES[dep_name]
                print(f"\n{dep_name} - {dep_info['description']}")
                print(f"  Used by: {', '.join(dep_info['used_by'])}")
                
                if verbose:
                    print("  Installation:")
                    for os_name, cmd in dep_info['install'].items():
                        print(f"    {os_name:15} : {cmd}")
            
            print()
            return 1
        else:
            print("\n✓ All dependencies are installed!")
            return 0
    
    def get_install_instructions(self, dep_name: str, platform: str = None) -> str:
        """
        Get installation instructions for a specific dependency.
        
        Args:
            dep_name: Name of the dependency
            platform: Platform name (e.g., 'fedora', 'ubuntu/debian')
            
        Returns:
            Installation command or instructions
        """
        dep_info = self.DEPENDENCIES.get(dep_name)
        if not dep_info:
            return f"Unknown dependency: {dep_name}"
        
        if platform and platform in dep_info['install']:
            return dep_info['install'][platform]
        
        # Return all platforms
        lines = [f"Installation for {dep_name}:"]
        for os_name, cmd in dep_info['install'].items():
            lines.append(f"  {os_name:15} : {cmd}")
        return '\n'.join(lines)


def main():
    """Main entry point for dependency checker.
    
    Returns:
        int: Exit code (0 for success, 1 for missing dependencies or errors).
    """
    parser = argparse.ArgumentParser(
        description="Check for required system dependencies"
    )
    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='Show detailed installation instructions for missing dependencies'
    )
    parser.add_argument(
        '--check',
        metavar='DEPENDENCY',
        help='Check a specific dependency (e.g., ffmpeg, gstreamer)'
    )
    parser.add_argument(
        '--install-help',
        metavar='DEPENDENCY',
        help='Show installation instructions for a specific dependency'
    )
    
    args = parser.parse_args()
    
    checker = DependencyChecker()
    
    # Check specific dependency
    if args.check:
        dep_name = args.check.lower()
        if dep_name not in checker.DEPENDENCIES:
            print(f"Error: Unknown dependency '{dep_name}'")
            print(f"Available: {', '.join(checker.DEPENDENCIES.keys())}")
            return 1
        
        is_available, info = checker.check_dependency(dep_name)
        if is_available:
            print(f"✓ {dep_name} is available: {info}")
            return 0
        else:
            print(f"✗ {dep_name} is not available: {info}")
            if args.verbose:
                print()
                print(checker.get_install_instructions(dep_name))
            return 1
    
    # Show installation help
    if args.install_help:
        dep_name = args.install_help.lower()
        if dep_name not in checker.DEPENDENCIES:
            print(f"Error: Unknown dependency '{dep_name}'")
            print(f"Available: {', '.join(checker.DEPENDENCIES.keys())}")
            return 1
        
        print(checker.get_install_instructions(dep_name))
        return 0
    
    # Check all dependencies
    results = checker.check_all()
    return checker.print_report(results, verbose=args.verbose)


if __name__ == '__main__':
    sys.exit(main())
