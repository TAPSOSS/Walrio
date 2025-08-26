#!/usr/bin/env python3
"""
ReplayGain LUFS Analyzer
Copyright (c) 2025 TAPS OSS
Project: https://github.com/TAPSOSS/Walrio
Licensed under the BSD-3-Clause License (see LICENSE file for details)

A tool to analyze audio files for ReplayGain values using LUFS (Loudness Units relative to Full Scale).
Uses rsgain tool for analysis and can optionally apply ReplayGain tags to files.

This implementation is inspired by the MuseAmp project by tapscodes.
"""

import os
import sys
import argparse
import subprocess
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
import json

# Configure logging format
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger('ReplayGainAnalyzer')

# Supported audio file extensions
SUPPORTED_EXTENSIONS = {'.flac', '.mp3', '.m4a'}

# Default LUFS target (ReplayGain 2.0 standard)
DEFAULT_TARGET_LUFS = -18

class ReplayGainAnalyzer:
    """
    Audio ReplayGain analyzer using rsgain for LUFS analysis
    """
    
    def __init__(self, target_lufs: int = DEFAULT_TARGET_LUFS):
        """
        Initialize the ReplayGain analyzer.
        
        Args:
            target_lufs (int): Target LUFS value for analysis (default: -18)
        """
        self.target_lufs = target_lufs
        self.analyzed_count = 0
        self.error_count = 0
        self.tagged_count = 0
        
        # Validate rsgain availability
        self._check_rsgain()
    
    def _check_rsgain(self):
        """
        Check if rsgain is available for analysis.
        
        Raises:
            RuntimeError: If rsgain is not found.
        """
        try:
            result = subprocess.run(
                ['rsgain', '--version'],
                capture_output=True,
                text=True,
                check=True
            )
            logger.debug("rsgain is available for ReplayGain analysis")
        except (subprocess.CalledProcessError, FileNotFoundError):
            raise RuntimeError(
                "rsgain not found. Please install rsgain from https://github.com/complexlogic/rsgain and make sure it's in your PATH."
            )
    
    def is_supported_file(self, filepath: str) -> bool:
        """
        Check if a file is a supported audio file.
        
        Args:
            filepath (str): Path to the file
            
        Returns:
            bool: True if the file is supported, False otherwise
        """
        if not os.path.isfile(filepath):
            return False
        
        ext = Path(filepath).suffix.lower()
        return ext in SUPPORTED_EXTENSIONS
    
    def analyze_file(self, filepath: str) -> Optional[Dict[str, Any]]:
        """
        Analyze a single audio file for ReplayGain values using rsgain.
        
        Args:
            filepath (str): Path to the audio file
            
        Returns:
            dict or None: Analysis results containing loudness, gain, and clipping info, or None if analysis failed
        """
        if not self.is_supported_file(filepath):
            logger.warning(f"Unsupported file type: {os.path.basename(filepath)}")
            return None
        
        try:
            # Use rsgain custom command for analysis without writing tags
            cmd = [
                "rsgain", "custom",
                "-O",  # Output format: tab-separated values
                str(filepath)
            ]
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=False
            )
            
            if result.returncode != 0:
                logger.error(f"rsgain analysis failed for {os.path.basename(filepath)}: {result.stderr or result.stdout}")
                self.error_count += 1
                return None
            
            # Parse the output
            lines = result.stdout.strip().splitlines()
            if len(lines) < 2:
                logger.error(f"Unexpected rsgain output format for {os.path.basename(filepath)}")
                self.error_count += 1
                return None
            
            # Parse header and values
            header = lines[0].split('\t')
            values = lines[1].split('\t')
            
            if len(header) != len(values):
                logger.error(f"Header/value mismatch in rsgain output for {os.path.basename(filepath)}")
                self.error_count += 1
                return None
            
            # Create column mapping
            colmap = {k: i for i, k in enumerate(header)}
            
            # Extract values
            analysis_result = {
                'filepath': filepath,
                'filename': os.path.basename(filepath),
                'loudness_lufs': None,
                'gain_db': None,
                'clipping': None,
                'raw_output': result.stdout.strip()
            }
            
            # Get loudness value
            lufs_col = colmap.get("Loudness (LUFS)", -1)
            if lufs_col != -1 and lufs_col < len(values):
                try:
                    analysis_result['loudness_lufs'] = float(values[lufs_col])
                except ValueError:
                    analysis_result['loudness_lufs'] = values[lufs_col]  # Keep as string if not numeric
            
            # Get gain value
            gain_col = colmap.get("Gain (dB)", -1)
            if gain_col != -1 and gain_col < len(values):
                try:
                    analysis_result['gain_db'] = float(values[gain_col])
                except ValueError:
                    analysis_result['gain_db'] = values[gain_col]  # Keep as string if not numeric
            
            # Get clipping information
            clip_col = colmap.get("Clipping", colmap.get("Clipping Adjustment?", -1))
            if clip_col != -1 and clip_col < len(values):
                clip_val = values[clip_col].strip().upper()
                if clip_val in ("Y", "YES"):
                    analysis_result['clipping'] = True
                elif clip_val in ("N", "NO"):
                    analysis_result['clipping'] = False
                else:
                    analysis_result['clipping'] = values[clip_col]  # Keep original value
            
            self.analyzed_count += 1
            logger.debug(f"Analyzed {os.path.basename(filepath)}: {analysis_result['loudness_lufs']} LUFS, {analysis_result['gain_db']} dB gain")
            
            return analysis_result
            
        except Exception as e:
            logger.error(f"Error analyzing {os.path.basename(filepath)}: {str(e)}")
            self.error_count += 1
            return None
    
    def analyze_and_tag_file(self, filepath: str, skip_tagged: bool = True) -> Optional[Dict[str, Any]]:
        """
        Analyze a file and optionally apply ReplayGain tags.
        
        Args:
            filepath (str): Path to the audio file
            skip_tagged (bool): If True, skip files that already have ReplayGain tags
            
        Returns:
            dict or None: Analysis results, or None if analysis failed
        """
        if not self.is_supported_file(filepath):
            logger.warning(f"Unsupported file type: {os.path.basename(filepath)}")
            return None
        
        try:
            # Build rsgain command for analysis and tagging (following MuseAmp pattern)
            lufs_str = f"-{abs(self.target_lufs)}"  # MuseAmp pattern: always negative
            cmd = [
                "rsgain", "custom",
                "-s", "i",  # Apply tags (single file mode, integrated mode)
                "-l", lufs_str,  # Target LUFS
                "-O",  # Output format: tab-separated values
                str(filepath)
            ]
            
            # Add skip option if requested
            if skip_tagged:
                cmd.insert(2, "-S")  # Skip files with existing ReplayGain tags

            logger.debug(f"Running command: {' '.join(cmd)}")  # Debug the exact command
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=False
            )

            if result.returncode != 0:
                logger.error(f"rsgain tagging failed for {os.path.basename(filepath)}: {result.stderr or result.stdout}")
                self.error_count += 1
                return None

            # Parse the output (same format as analyze_file)
            lines = result.stdout.strip().splitlines()
            if len(lines) < 2:
                logger.error(f"Unexpected rsgain output format for {os.path.basename(filepath)}")
                self.error_count += 1
                return None

            # Parse header and values
            header = lines[0].split('\t')
            values = lines[1].split('\t')
            logger.debug(f"Header: {header}")  # Debug output
            logger.debug(f"Values: {values}")  # Debug output
            
            if len(header) != len(values):
                logger.error(f"Header/value mismatch in rsgain output for {os.path.basename(filepath)}")
                self.error_count += 1
                return None
            
            # Create column mapping
            colmap = {k: i for i, k in enumerate(header)}
            
            # Extract values
            analysis_result = {
                'filepath': filepath,
                'filename': os.path.basename(filepath),
                'loudness_lufs': None,
                'gain_db': None,
                'clipping': None,
                'tagged': True,
                'target_lufs': self.target_lufs,
                'raw_output': result.stdout.strip()
            }
            
            # Get loudness value
            lufs_col = colmap.get("Loudness (LUFS)", -1)
            if lufs_col != -1 and lufs_col < len(values):
                try:
                    analysis_result['loudness_lufs'] = float(values[lufs_col])
                except ValueError:
                    analysis_result['loudness_lufs'] = values[lufs_col]
            
            # Get gain value
            gain_col = colmap.get("Gain (dB)", -1)
            if gain_col != -1 and gain_col < len(values):
                try:
                    analysis_result['gain_db'] = float(values[gain_col])
                except ValueError:
                    analysis_result['gain_db'] = values[gain_col]
            
            # Get clipping information
            clip_col = colmap.get("Clipping", colmap.get("Clipping Adjustment?", -1))
            if clip_col != -1 and clip_col < len(values):
                clip_val = values[clip_col].strip().upper()
                if clip_val in ("Y", "YES"):
                    analysis_result['clipping'] = True
                elif clip_val in ("N", "NO"):
                    analysis_result['clipping'] = False
                else:
                    analysis_result['clipping'] = values[clip_col]
            
            self.analyzed_count += 1
            self.tagged_count += 1
            logger.info(f"Tagged {os.path.basename(filepath)}: {analysis_result['loudness_lufs']} LUFS, {analysis_result['gain_db']} dB gain")
            
            return analysis_result
            
        except Exception as e:
            logger.error(f"Error analyzing and tagging {os.path.basename(filepath)}: {str(e)}")
            self.error_count += 1
            return None
    
    def analyze_directory(self, directory: str, recursive: bool = True, analyze_only: bool = True) -> List[Dict[str, Any]]:
        """
        Analyze all supported audio files in a directory.
        
        Args:
            directory (str): Directory to analyze
            recursive (bool): If True, process subdirectories recursively
            analyze_only (bool): If True, only analyze without tagging
            
        Returns:
            list: List of analysis results for all processed files
        """
        if not os.path.isdir(directory):
            logger.error(f"Directory does not exist: {directory}")
            return []
        
        # Find all supported audio files
        files_to_process = []
        
        if recursive:
            for root, _, files in os.walk(directory):
                for file in files:
                    filepath = os.path.join(root, file)
                    if self.is_supported_file(filepath):
                        files_to_process.append(filepath)
        else:
            for file in os.listdir(directory):
                filepath = os.path.join(directory, file)
                if self.is_supported_file(filepath):
                    files_to_process.append(filepath)
        
        if not files_to_process:
            logger.warning(f"No supported audio files found in {directory}")
            return []
        
        logger.info(f"Found {len(files_to_process)} supported audio files")
        
        # Process all files
        results = []
        for i, filepath in enumerate(files_to_process, 1):
            logger.debug(f"Processing file {i}/{len(files_to_process)}: {os.path.basename(filepath)}")
            
            if analyze_only:
                result = self.analyze_file(filepath)
            else:
                result = self.analyze_and_tag_file(filepath)
            
            if result:
                results.append(result)
        
        return results
    
    def print_analysis_summary(self, results: List[Dict[str, Any]], detailed: bool = False):
        """
        Print a summary of analysis results.
        
        Args:
            results (list): List of analysis results
            detailed (bool): If True, print detailed per-file results
        """
        if not results:
            print("No analysis results to display.")
            return
        
        print(f"\nReplayGain Analysis Summary")
        print("=" * 60)
        print(f"Target LUFS: {self.target_lufs}")
        print(f"Files analyzed: {len(results)}")
        print(f"Files with errors: {self.error_count}")
        
        # Calculate statistics
        valid_loudness = [r['loudness_lufs'] for r in results if isinstance(r['loudness_lufs'], (int, float))]
        valid_gain = [r['gain_db'] for r in results if isinstance(r['gain_db'], (int, float))]
        clipping_files = [r for r in results if r['clipping'] is True]
        
        if valid_loudness:
            avg_loudness = sum(valid_loudness) / len(valid_loudness)
            min_loudness = min(valid_loudness)
            max_loudness = max(valid_loudness)
            print(f"Average loudness: {avg_loudness:.2f} LUFS")
            print(f"Loudness range: {min_loudness:.2f} to {max_loudness:.2f} LUFS")
        
        if valid_gain:
            avg_gain = sum(valid_gain) / len(valid_gain)
            min_gain = min(valid_gain)
            max_gain = max(valid_gain)
            print(f"Average gain: {avg_gain:.2f} dB")
            print(f"Gain range: {min_gain:.2f} to {max_gain:.2f} dB")
        
        if clipping_files:
            print(f"Files with clipping: {len(clipping_files)}")
        
        # Detailed per-file results
        if detailed:
            print(f"\nDetailed Results:")
            print("-" * 60)
            for result in results:
                filename = result['filename']
                loudness = result.get('loudness_lufs', 'N/A')
                gain = result.get('gain_db', 'N/A')
                clipping = result.get('clipping', 'N/A')
                
                # Format values
                if isinstance(loudness, (int, float)):
                    loudness_str = f"{loudness:.2f} LUFS"
                else:
                    loudness_str = str(loudness)
                
                if isinstance(gain, (int, float)):
                    gain_str = f"{gain:.2f} dB"
                else:
                    gain_str = str(gain)
                
                if isinstance(clipping, bool):
                    clipping_str = "Yes" if clipping else "No"
                else:
                    clipping_str = str(clipping)
                
                tagged_str = " [TAGGED]" if result.get('tagged', False) else ""
                
                print(f"{filename:<40} {loudness_str:<12} {gain_str:<10} Clipping: {clipping_str}{tagged_str}")


def parse_arguments():
    """
    Parse command line arguments.
    
    Returns:
        argparse.Namespace: Parsed arguments
    """
    parser = argparse.ArgumentParser(
        description="ReplayGain LUFS Analyzer - Analyze and tag audio files with ReplayGain values",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""Examples:
  # Analyze files without tagging (dry run)
  python replaygain.py /path/to/music --analyze-only

  # Analyze and tag files with default -18 LUFS target
  python replaygain.py /path/to/music --tag

  # Use custom LUFS target
  python replaygain.py /path/to/music --tag --target-lufs -16

  # Analyze specific files
  python replaygain.py song1.flac song2.mp3 --analyze-only

  # Show detailed per-file results
  python replaygain.py /path/to/music --analyze-only --detailed

  # Tag files but skip those already tagged
  python replaygain.py /path/to/music --tag --skip-tagged

  # Force retag all files (overwrite existing tags)
  python replaygain.py /path/to/music --tag --no-skip-tagged

Supported file formats:
  - FLAC (.flac)
  - MP3 (.mp3)
  - M4A (.m4a)

LUFS Target Values:
  -18 LUFS: ReplayGain 2.0 standard (default)
  -16 LUFS: Apple Music standard
  -14 LUFS: Spotify, Amazon Music, YouTube standard
  -20 LUFS: TV broadcast standard

Requirements:
  - rsgain tool (https://github.com/complexlogic/rsgain)
""")
    
    # Input options
    parser.add_argument(
        "input",
        nargs="+",
        help="Audio files or directories to analyze"
    )
    
    # Operation mode
    mode_group = parser.add_mutually_exclusive_group(required=True)
    mode_group.add_argument(
        "--analyze-only", "--analyze",
        action="store_true",
        help="Only analyze files without applying ReplayGain tags"
    )
    mode_group.add_argument(
        "--tag",
        action="store_true",
        help="Analyze files and apply ReplayGain tags"
    )
    
    # Analysis options
    parser.add_argument(
        "--target-lufs", "--lufs",
        type=int,
        default=DEFAULT_TARGET_LUFS,
        help=f"Target LUFS value for ReplayGain calculation (default: {DEFAULT_TARGET_LUFS})"
    )
    parser.add_argument(
        "--skip-tagged",
        action="store_true",
        default=False,
        help="Skip files that already have ReplayGain tags (default: False - process all files)"
    )
    parser.add_argument(
        "--no-skip-tagged",
        action="store_true",
        help="Process all files, overwriting existing ReplayGain tags"
    )
    
    # Directory processing options
    parser.add_argument(
        "--recursive", "-r",
        action="store_true",
        default=False,
        help="Process directories recursively (default: False)"
    )
    parser.add_argument(
        "--non-recursive",
        action="store_true",
        help="Only process files in the top level of directories"
    )
    
    # Output options
    parser.add_argument(
        "--detailed", "--verbose",
        action="store_true",
        help="Show detailed per-file analysis results"
    )
    parser.add_argument(
        "--quiet", "-q",
        action="store_true",
        help="Suppress progress messages, only show summary"
    )
    parser.add_argument(
        "--json",
        metavar="FILE",
        help="Save analysis results to JSON file"
    )
    
    # Utility options
    parser.add_argument(
        "--check-rsgain",
        action="store_true",
        help="Check if rsgain is available and exit"
    )
    
    return parser.parse_args()


def main():
    """
    Main function for the ReplayGain analyzer.
    """
    args = parse_arguments()
    
    # Set logging level
    if args.quiet:
        logger.setLevel(logging.WARNING)
    
    # Handle rsgain check
    if args.check_rsgain:
        try:
            analyzer = ReplayGainAnalyzer()
            print("rsgain is available and ready for use.")
            sys.exit(0)
        except RuntimeError as e:
            print(f"Error: {e}")
            sys.exit(1)
    
    # Resolve skip-tagged setting
    skip_tagged = args.skip_tagged and not args.no_skip_tagged
    
    # Resolve recursive setting
    recursive = args.recursive and not args.non_recursive
    
    # Validate target LUFS range
    if not (-30 <= args.target_lufs <= -5):
        logger.warning(f"Target LUFS {args.target_lufs} is outside typical range (-30 to -5). This may not be optimal.")
    
    try:
        # Create analyzer
        analyzer = ReplayGainAnalyzer(target_lufs=args.target_lufs)
        
        # Process all inputs
        all_results = []
        
        for input_path in args.input:
            if not os.path.exists(input_path):
                logger.error(f"Input does not exist: {input_path}")
                continue
            
            if os.path.isfile(input_path):
                # Single file
                if not analyzer.is_supported_file(input_path):
                    logger.warning(f"Unsupported file: {input_path}")
                    continue
                
                logger.info(f"Processing file: {os.path.basename(input_path)}")
                
                if args.analyze_only:
                    result = analyzer.analyze_file(input_path)
                else:
                    result = analyzer.analyze_and_tag_file(input_path, skip_tagged)
                
                if result:
                    all_results.append(result)
            
            elif os.path.isdir(input_path):
                # Directory
                logger.info(f"Processing directory: {input_path}")
                
                if args.analyze_only:
                    # Use the analyze_directory method for analysis-only mode
                    results = analyzer.analyze_directory(input_path, recursive, args.analyze_only)
                else:
                    # For tagging mode, process each file individually with proper settings
                    results = []
                    for root, _, files in os.walk(input_path) if recursive else [(input_path, [], os.listdir(input_path))]:
                        for file in files:
                            filepath = os.path.join(root, file)
                            if analyzer.is_supported_file(filepath):
                                result = analyzer.analyze_and_tag_file(filepath, skip_tagged)
                                if result:
                                    results.append(result)
                
                all_results.extend(results)
            
            else:
                logger.error(f"Input is neither file nor directory: {input_path}")
        
        # Print summary
        if not args.quiet:
            analyzer.print_analysis_summary(all_results, args.detailed)
        
        # Save JSON results if requested
        if args.json:
            try:
                with open(args.json, 'w') as f:
                    json.dump(all_results, f, indent=2, default=str)
                logger.info(f"Analysis results saved to: {args.json}")
            except Exception as e:
                logger.error(f"Failed to save JSON results: {e}")
        
        # Exit with error code if there were errors
        if analyzer.error_count > 0:
            logger.error(f"Analysis completed with {analyzer.error_count} errors")
            sys.exit(1)
        
        # Success summary
        operation = "analyzed" if args.analyze_only else "analyzed and tagged"
        logger.info(f"Successfully {operation} {analyzer.analyzed_count} files")
        
        if not args.analyze_only:
            logger.info(f"Applied ReplayGain tags to {analyzer.tagged_count} files")
    
    except Exception as e:
        logger.error(f"Error: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    main()
