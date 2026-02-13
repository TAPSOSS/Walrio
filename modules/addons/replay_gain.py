#!/usr/bin/env python3
"""
analyze and tag files with standard replay gain values for volume normalizaiton
"""

import argparse
import json
import logging
import os
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Optional, Any

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger('ReplayGainAnalyzer')

# Supported formats
SUPPORTED_EXTENSIONS = {'.flac', '.mp3', '.m4a', '.ogg', '.opus', '.wv'}

# Default LUFS target (ReplayGain 2.0 standard)
DEFAULT_TARGET_LUFS = -18


class ReplayGainAnalyzer:
    """
    ReplayGain analyzer using rsgain for LUFS analysis and tagging
    """
    
    def __init__(self, target_lufs: int = DEFAULT_TARGET_LUFS, 
                 preserve_mtimes: bool = True):
        """
        Args:
            target_lufs: Target LUFS value for analysis (default: -18)
            preserve_mtimes: Preserve file modification times
        """
        # Validate LUFS range
        if target_lufs > -5 or target_lufs < -30:
            raise ValueError(f"Target LUFS must be between -30 and -5 (got {target_lufs})")
        
        self.target_lufs = target_lufs
        self.preserve_mtimes = preserve_mtimes
        self.analyzed_count = 0
        self.error_count = 0
        self.tagged_count = 0
        
        self._check_rsgain()
    
    def _check_rsgain(self):
        """Check if rsgain is available"""
        try:
            subprocess.run(['rsgain', '--version'], 
                          capture_output=True, check=True)
            logger.debug("rsgain available for ReplayGain analysis")
        except (subprocess.CalledProcessError, FileNotFoundError):
            raise RuntimeError(
                "rsgain not found. Install from https://github.com/complexlogic/rsgain"
            )
    
    def print_analysis_settings(self, tag: bool = False, skip_tagged: bool = False):
        """Print analysis parameters being used"""
        print("\n" + "=" * 60)
        print(f"ReplayGain Analysis Settings:")
        print(f"  Target LUFS: {self.target_lufs}")
        print(f"  Mode: {'Tag files' if tag else 'Analysis only'}")
        if tag and skip_tagged:
            print(f"  Skip Tagged: Yes")
        print(f"  Preserve Modification Times: {'Yes' if self.preserve_mtimes else 'No'}")
        print("=" * 60 + "\n")
    
    def is_supported_file(self, filepath: Path) -> bool:
        """
        Check if file is supported
        
        Args:
            filepath: File path
            
        Returns:
            True if supported
        """
        return filepath.is_file() and filepath.suffix.lower() in SUPPORTED_EXTENSIONS
    
    def analyze_file(self, filepath: Path, current_file: int = None, 
                     total_files: int = None) -> Optional[Dict[str, Any]]:
        """
        Analyze single audio file for ReplayGain values (no tagging)
        
        Args:
            filepath: Audio file path
            current_file: Current file number (for progress display)
            total_files: Total number of files (for progress display)
            
        Returns:
            Analysis results with loudness, gain, clipping info, or None on failure
        """
        if not self.is_supported_file(filepath):
            logger.warning(f"Unsupported file type: {filepath.name}")
            return None
        
        # Display progress
        if current_file and total_files:
            print(f"\nFile {current_file}/{total_files}: Analyzing {filepath.name}")
        else:
            print(f"\nAnalyzing {filepath.name}")
        
        try:
            # Use rsgain custom command for analysis without writing tags
            lufs_str = f"-{abs(self.target_lufs)}"
            cmd = [
                "rsgain", "custom",
                "-s", "s",  # Scan mode (no writing)
                "-l", lufs_str,  # Target LUFS
                "-O",  # Output format: tab-separated values
            ]
            
            # Add preserve mtimes if requested
            if self.preserve_mtimes:
                cmd.insert(2, "-p")
            
            cmd.append(str(filepath))
            
            result = subprocess.run(cmd, capture_output=True, text=True, check=False)
            
            if result.returncode != 0:
                logger.error(f"rsgain analysis failed for {filepath.name}: {result.stderr or result.stdout}")
                self.error_count += 1
                return None
            
            # Parse output
            lines = result.stdout.strip().splitlines()
            if len(lines) < 2:
                logger.error(f"Unexpected rsgain output format for {filepath.name}")
                self.error_count += 1
                return None
            
            # Parse header and values
            header = lines[0].split('\t')
            values = lines[1].split('\t')
            
            if len(header) != len(values):
                logger.error(f"Header/value mismatch in rsgain output for {filepath.name}")
                self.error_count += 1
                return None
            
            # Create column mapping
            colmap = {k: i for i, k in enumerate(header)}
            
            # Extract values
            analysis_result = {
                'filepath': str(filepath),
                'filename': filepath.name,
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
            logger.debug(f"Analyzed {filepath.name}: {analysis_result['loudness_lufs']} LUFS, {analysis_result['gain_db']} dB gain")
            
            # Display results
            print(f"  ✓ Analysis complete: Volume level: {analysis_result['loudness_lufs']} LUFS | Replay Gain: {analysis_result['gain_db']} dB")
            
            return analysis_result
            
        except Exception as e:
            logger.error(f"Error analyzing {filepath.name}: {e}")
            self.error_count += 1
            return None
    
    def analyze_and_tag_file(self, filepath: Path, skip_tagged: bool = True,
                            current_file: int = None, total_files: int = None) -> Optional[Dict[str, Any]]:
        """
        Analyze file and write ReplayGain tags
        
        Args:
            filepath: Audio file path
            skip_tagged: Skip files that already have ReplayGain tags
            current_file: Current file number (for progress display)
            total_files: Total number of files (for progress display)
            
        Returns:
            Analysis results, or None on failure
        """
        if not self.is_supported_file(filepath):
            logger.warning(f"Unsupported file type: {filepath.name}")
            return None
        
        # Display progress
        if current_file and total_files:
            print(f"\nFile {current_file}/{total_files}: Analyzing {filepath.name}")
        else:
            print(f"\nAnalyzing {filepath.name}")
        
        try:
            # Build rsgain command for analysis and tagging
            lufs_str = f"-{abs(self.target_lufs)}"
            cmd = [
                "rsgain", "custom",
                "-s", "i",  # Apply tags (single file mode, integrated mode)
                "-l", lufs_str,  # Target LUFS
                "-O",  # Output format: tab-separated values
            ]
            
            # Add skip option if requested
            if skip_tagged:
                cmd.insert(2, "-S")  # Skip files with existing tags
            
            # Add preserve mtimes if requested
            if self.preserve_mtimes:
                cmd.insert(2, "-p")
            
            cmd.append(str(filepath))
            
            logger.debug(f"Running: {' '.join(cmd)}")
            
            result = subprocess.run(cmd, capture_output=True, text=True, check=False)
            
            if result.returncode != 0:
                logger.error(f"rsgain tagging failed for {filepath.name}: {result.stderr or result.stdout}")
                self.error_count += 1
                return None
            
            # Parse output (same format as analyze_file)
            lines = result.stdout.strip().splitlines()
            if len(lines) < 2:
                logger.error(f"Unexpected rsgain output format for {filepath.name}")
                self.error_count += 1
                return None
            
            header = lines[0].split('\t')
            values = lines[1].split('\t')
            
            if len(header) != len(values):
                logger.error(f"Header/value mismatch in rsgain output for {filepath.name}")
                self.error_count += 1
                return None
            
            colmap = {k: i for i, k in enumerate(header)}
            
            analysis_result = {
                'filepath': str(filepath),
                'filename': filepath.name,
                'loudness_lufs': None,
                'gain_db': None,
                'clipping': None,
                'tagged': True,
                'target_lufs': self.target_lufs,
                'raw_output': result.stdout.strip()
            }
            
            # Get loudness
            lufs_col = colmap.get("Loudness (LUFS)", -1)
            if lufs_col != -1 and lufs_col < len(values):
                try:
                    analysis_result['loudness_lufs'] = float(values[lufs_col])
                except ValueError:
                    analysis_result['loudness_lufs'] = values[lufs_col]
            
            # Get gain
            gain_col = colmap.get("Gain (dB)", -1)
            if gain_col != -1 and gain_col < len(values):
                try:
                    analysis_result['gain_db'] = float(values[gain_col])
                except ValueError:
                    analysis_result['gain_db'] = values[gain_col]
            
            # Get clipping
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
            logger.info(f"Tagged {filepath.name}: {analysis_result['loudness_lufs']} LUFS, {analysis_result['gain_db']} dB gain")
            
            # Display results
            print(f"  ✓ Analysis complete: Volume level: {analysis_result['loudness_lufs']} LUFS | Replay Gain: {analysis_result['gain_db']} dB")
            print(f"  ✓ ReplayGain tags written")
            
            return analysis_result
            
        except Exception as e:
            logger.error(f"Error analyzing and tagging {filepath.name}: {e}")
            self.error_count += 1
            return None
    
    def delete_tags_file(self, filepath: Path, current_file: int = None, 
                        total_files: int = None) -> bool:
        """
        Delete ReplayGain tags from file
        
        Args:
            filepath: Audio file path
            current_file: Current file number (for progress display)
            total_files: Total number of files (for progress display)
            
        Returns:
            True if successful, False otherwise
        """
        if not self.is_supported_file(filepath):
            logger.warning(f"Unsupported file type: {filepath.name}")
            return False
        
        # Display progress
        if current_file and total_files:
            print(f"\nFile {current_file}/{total_files}: Deleting ReplayGain tags from {filepath.name}")
        else:
            print(f"\nDeleting ReplayGain tags from {filepath.name}")
        
        try:
            # Build rsgain command for deleting tags
            cmd = [
                "rsgain", "custom",
                "-s", "d",  # Delete mode
            ]
            
            # Add preserve mtimes if requested
            if self.preserve_mtimes:
                cmd.insert(2, "-p")
            
            cmd.append(str(filepath))
            
            result = subprocess.run(cmd, capture_output=True, text=True, check=False)
            
            if result.returncode != 0:
                logger.error(f"Failed to delete tags from {filepath.name}: {result.stderr or result.stdout}")
                self.error_count += 1
                return False
            
            print(f"  ✓ ReplayGain tags deleted")
            return True
            
        except Exception as e:
            logger.error(f"Error deleting tags from {filepath.name}: {e}")
            self.error_count += 1
            return False
    
    def analyze_directory(self, directory: Path, recursive: bool = True, 
                         tag: bool = False, skip_tagged: bool = True,
                         delete_tags: bool = False) -> List[Dict[str, Any]]:
        """
        Analyze all supported audio files in directory
        
        Args:
            directory: Directory to scan
            recursive: Process subdirectories
            tag: Write ReplayGain tags
            skip_tagged: Skip files that already have tags
            delete_tags: Delete ReplayGain tags from files
            
        Returns:
            List of analysis results
        """
        if not directory.is_dir():
            raise NotADirectoryError(f"Not a directory: {directory}")
        
        # Find audio files
        if recursive:
            files = []
            for ext in SUPPORTED_EXTENSIONS:
                files.extend(directory.rglob(f'*{ext}'))
        else:
            files = []
            for ext in SUPPORTED_EXTENSIONS:
                files.extend(directory.glob(f'*{ext}'))
        
        # Print settings and file count
        if files:
            if delete_tags:
                print("\n" + "=" * 60)
                print(f"ReplayGain Tag Deletion:")
                print(f"  Preserve Modification Times: {'Yes' if self.preserve_mtimes else 'No'}")
                print("=" * 60 + "\n")
                print(f"Found {len(files)} audio file(s) to process\n")
            else:
                self.print_analysis_settings(tag, skip_tagged)
                print(f"Found {len(files)} audio file(s) to analyze\n")
        
        results = []
        deleted_count = 0
        for idx, file_path in enumerate(files, 1):
            if delete_tags:
                if self.delete_tags_file(file_path, current_file=idx, total_files=len(files)):
                    deleted_count += 1
            elif tag:
                result = self.analyze_and_tag_file(file_path, skip_tagged, 
                                                   current_file=idx, total_files=len(files))
                if result:
                    results.append(result)
            else:
                result = self.analyze_file(file_path, 
                                          current_file=idx, total_files=len(files))
                if result:
                    results.append(result)
        
        if delete_tags:
            # Return summary for delete mode
            return {'deleted': deleted_count, 'errors': self.error_count}
        
        return results


def main():
    """Main entry point for ReplayGain analyzer - analyze and tag audio files."""
    parser = argparse.ArgumentParser(
        description='Analyze and apply ReplayGain tags to audio files'
    )
    parser.add_argument('input', type=Path, help='File or directory to process')
    parser.add_argument('-r', '--recursive', action='store_true',
                       help='Process subdirectories')
    parser.add_argument('-t', '--tag', action='store_true',
                       help='Write ReplayGain tags (default: analyze only)')
    parser.add_argument('-s', '--skip-tagged', action='store_true',
                       help='Skip files that already have ReplayGain tags')
    parser.add_argument('--delete-tags', action='store_true',
                       help='Delete ReplayGain tags from files')
    parser.add_argument('-l', '--target-lufs', type=int, default=DEFAULT_TARGET_LUFS,
                       help=f'Target LUFS value from -30 to -5 (default: {DEFAULT_TARGET_LUFS})')
    parser.add_argument('--no-preserve-mtimes', action='store_true',
                       help='Do not preserve file modification times')
    
    args = parser.parse_args()
    
    try:
        analyzer = ReplayGainAnalyzer(
            target_lufs=args.target_lufs,
            preserve_mtimes=not args.no_preserve_mtimes
        )
        
        if args.delete_tags:
            # Delete mode
            if args.input.is_dir():
                result = analyzer.analyze_directory(
                    args.input, args.recursive, delete_tags=True
                )
                print(f"\nTag deletion complete:")
                print(f"  Deleted: {result['deleted']}")
                if result['errors']:
                    print(f"  Errors: {result['errors']}")
                    return 1
            else:
                # Single file
                success = analyzer.delete_tags_file(args.input)
                if not success:
                    return 1
        
        elif args.input.is_dir():
            # Directory analysis
            results = analyzer.analyze_directory(
                args.input, args.recursive, args.tag, args.skip_tagged
            )
            
            print(f"\nAnalysis complete:")
            print(f"  Analyzed: {analyzer.analyzed_count}")
            if args.tag:
                print(f"  Tagged: {analyzer.tagged_count}")
            if analyzer.error_count:
                print(f"  Errors: {analyzer.error_count}")
        
        else:
            # Single file analysis
            if args.tag:
                result = analyzer.analyze_and_tag_file(args.input, args.skip_tagged)
            else:
                result = analyzer.analyze_file(args.input)
            
            if result:
                print(f"\nResults for {result['filename']}:")
                print(f"  Loudness: {result['loudness_lufs']} LUFS")
                print(f"  Gain: {result['gain_db']} dB")
                print(f"  Clipping: {result['clipping']}")
                if args.tag:
                    print(f"  Tagged: Yes")
            else:
                print("Analysis failed")
                return 1
        
        return 0
        
    except Exception as e:
        logger.error(f"Error: {e}")
        return 1


if __name__ == '__main__':
    sys.exit(main())