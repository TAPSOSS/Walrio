#!/usr/bin/env python3
"""
Apply Loudness - Apply gain adjustments to audio files using ReplayGain or fixed values
"""

import os
import sys
import argparse
import subprocess
import shutil
import tempfile
from pathlib import Path
from typing import Optional, Dict, Any, Tuple, List

# Add parent directory for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
from modules.addons.replay_gain import ReplayGainAnalyzer
from modules.core import metadata

SUPPORTED_EXTENSIONS = {'.flac', '.mp3', '.m4a', '.wav', '.ogg', '.opus'}


class LoudnessApplicator:
    """Applies loudness adjustments using FFmpeg volume filter"""
    
    def __init__(self, create_backup: bool = True):
        """
        Args:
            create_backup: Create backup files before modification
        """
        self.create_backup = create_backup
        self.processed_count = 0
        self.error_count = 0
        self.backup_count = 0
        self._check_ffmpeg()
    
    def _check_ffmpeg(self):
        """Check FFmpeg availability"""
        for tool in ['ffmpeg', 'ffprobe']:
            try:
                subprocess.run([tool, '-version'], capture_output=True, check=True)
            except (subprocess.CalledProcessError, FileNotFoundError):
                raise RuntimeError(f"{tool} not found. Install FFmpeg.")
    
    def is_supported_file(self, filepath: str) -> bool:
        """Check if file is supported"""
        return Path(filepath).suffix.lower() in SUPPORTED_EXTENSIONS
    
    def get_replaygain_value(self, filepath: str, target_lufs: int = -18) -> Optional[float]:
        """
        Get ReplayGain value using analyzer
        
        Args:
            filepath: Audio file path
            target_lufs: Target LUFS for calculation
            
        Returns:
            Gain in dB or None if failed
        """
        try:
            analyzer = ReplayGainAnalyzer(target_lufs=target_lufs)
            result = analyzer.analyze_file(filepath)
            
            if result is None:
                return None
            
            gain_db = result.get('gain_db')
            if gain_db is None:
                return None
            
            if isinstance(gain_db, str):
                gain_db = float(gain_db)
            
            return gain_db
            
        except Exception as e:
            print(f"Error getting ReplayGain for {os.path.basename(filepath)}: {e}", file=sys.stderr)
            return None
    
    def get_audio_properties(self, filepath: str) -> Dict[str, Any]:
        """Get audio properties using FFprobe"""
        try:
            cmd = [
                "ffprobe", "-v", "error",
                "-select_streams", "a:0",
                "-show_entries", "stream=bits_per_raw_sample,bits_per_sample,sample_rate,channels",
                "-of", "default=noprint_wrappers=1:nokey=1",
                str(filepath)
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True, check=False)
            
            if result.returncode != 0:
                return {}
            
            lines = result.stdout.strip().splitlines()
            properties = {}
            
            if len(lines) >= 1 and lines[0].isdigit():
                properties['bits_per_raw_sample'] = int(lines[0])
            if len(lines) >= 2 and lines[1].isdigit():
                properties['bits_per_sample'] = int(lines[1])
            if len(lines) >= 3 and lines[2].isdigit():
                properties['sample_rate'] = int(lines[2])
            if len(lines) >= 4 and lines[3].isdigit():
                properties['channels'] = int(lines[3])
            
            return properties
            
        except Exception:
            return {}
    
    def _has_album_art(self, filepath: str) -> bool:
        """Check if file has album art"""
        try:
            cmd = [
                "ffprobe", "-v", "error",
                "-select_streams", "v:0",
                "-show_entries", "stream=codec_type",
                "-of", "csv=p=0",
                str(filepath)
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True, check=False)
            return result.returncode == 0 and "video" in result.stdout.lower()
            
        except Exception:
            return False
    
    def _handle_opus_album_art(self, original_filepath: str, opus_filepath: str):
        """Handle album art for Opus files"""
        if not self._has_album_art(original_filepath):
            return
        
        temp_art_file = f"{opus_filepath}.albumart.jpg"
        
        try:
            # Extract album art
            art_cmd = [
                'ffmpeg', '-y', '-i', str(original_filepath),
                '-an', '-vcodec', 'copy',
                '-map', '0:v:0',
                temp_art_file
            ]
            
            art_process = subprocess.run(
                art_cmd,
                capture_output=True,
                text=True,
                check=False,
                timeout=60
            )
            
            if art_process.returncode == 0 and os.path.exists(temp_art_file):
                # Embed using metadata module
                if hasattr(metadata, 'set_album_art'):
                    metadata.set_album_art(opus_filepath, temp_art_file)
                
        except subprocess.TimeoutExpired:
            pass
        except Exception:
            pass
        finally:
            if os.path.exists(temp_art_file):
                try:
                    os.remove(temp_art_file)
                except:
                    pass
    
    def apply_gain_to_file(self, filepath: str, gain_db: float, output_dir: Optional[str] = None) -> bool:
        """
        Apply gain to file using FFmpeg
        
        Args:
            filepath: Audio file path
            gain_db: Gain in dB to apply
            output_dir: Output directory (None for in-place)
            
        Returns:
            True if successful
        """
        if not self.is_supported_file(filepath):
            return False
        
        if abs(gain_db) < 0.01:
            print(f"Skipping {os.path.basename(filepath)} - no significant gain change ({gain_db:.2f} dB)")
            return True
        
        try:
            file_path = Path(filepath)
            ext = file_path.suffix.lower()
            
            # Determine output path
            if output_dir:
                output_path = Path(output_dir)
                output_path.mkdir(parents=True, exist_ok=True)
                out_file = output_path / file_path.name
            else:
                out_file = file_path
            
            # Create backup if in-place and requested
            if self.create_backup and not output_dir:
                backup_file = file_path.with_suffix(f"{ext}.backup")
                if not backup_file.exists():
                    shutil.copy2(filepath, backup_file)
                    self.backup_count += 1
            
            # Create temporary file
            with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as temp_file:
                temp_path = temp_file.name
            
            try:
                audio_props = self.get_audio_properties(filepath)
                
                # Build FFmpeg command
                ffmpeg_cmd = [
                    "ffmpeg", "-y", "-i", str(filepath),
                    "-map_metadata", "0",
                    "-af", f"volume={gain_db}dB",
                ]
                
                # Handle Opus separately (album art issues)
                if ext == ".opus":
                    ffmpeg_cmd.extend(["-map", "0:a:0"])
                else:
                    ffmpeg_cmd.extend(["-map", "0"])
                    ffmpeg_cmd.extend(["-c:v", "copy"])
                
                # Format-specific encoding
                if ext == ".mp3":
                    ffmpeg_cmd += ["-c:a", "libmp3lame"]
                elif ext == ".flac":
                    ffmpeg_cmd += ["-c:a", "flac"]
                    # Preserve bit depth
                    if 'bits_per_raw_sample' in audio_props or 'bits_per_sample' in audio_props:
                        bit_depth = audio_props.get('bits_per_raw_sample', audio_props.get('bits_per_sample', 16))
                        if bit_depth == 16:
                            ffmpeg_cmd += ["-sample_fmt", "s16"]
                        elif bit_depth >= 24:
                            ffmpeg_cmd += ["-sample_fmt", "s32"]
                elif ext == ".m4a":
                    ffmpeg_cmd += ["-c:a", "aac"]
                elif ext == ".ogg":
                    ffmpeg_cmd += ["-c:a", "libvorbis"]
                elif ext == ".opus":
                    ffmpeg_cmd += ["-c:a", "libopus"]
                elif ext == ".wav":
                    if 'bits_per_sample' in audio_props:
                        bit_depth = audio_props['bits_per_sample']
                        if bit_depth == 16:
                            ffmpeg_cmd += ["-c:a", "pcm_s16le"]
                        elif bit_depth == 24:
                            ffmpeg_cmd += ["-c:a", "pcm_s24le"]
                        elif bit_depth == 32:
                            ffmpeg_cmd += ["-c:a", "pcm_s32le"]
                        else:
                            ffmpeg_cmd += ["-c:a", "pcm_s16le"]
                    else:
                        ffmpeg_cmd += ["-c:a", "pcm_s16le"]
                
                ffmpeg_cmd.append(temp_path)
                
                result = subprocess.run(
                    ffmpeg_cmd,
                    capture_output=True,
                    text=False,
                    check=False
                )
                
                if result.returncode != 0:
                    return False
                
                # Handle Opus album art
                if ext == ".opus":
                    self._handle_opus_album_art(filepath, temp_path)
                
                # Move to final location
                shutil.move(temp_path, str(out_file))
                
                self.processed_count += 1
                print(f"Applied {gain_db:+.2f} dB to {os.path.basename(filepath)}")
                
                return True
                
            finally:
                if os.path.exists(temp_path):
                    try:
                        os.remove(temp_path)
                    except:
                        pass
                        
        except Exception as e:
            self.error_count += 1
            print(f"Error processing {os.path.basename(filepath)}: {e}", file=sys.stderr)
            return False
    
    def process_files(self, file_paths: List[str], gain_db: Optional[float] = None,
                     use_replaygain: bool = False, target_lufs: int = -18,
                     output_dir: Optional[str] = None) -> Tuple[int, int]:
        """
        Process multiple files
        
        Args:
            file_paths: List of file paths
            gain_db: Fixed gain in dB
            use_replaygain: Use ReplayGain values
            target_lufs: Target LUFS for ReplayGain
            output_dir: Output directory
            
        Returns:
            (successful_count, total_count)
        """
        supported_files = [f for f in file_paths if self.is_supported_file(f)]
        
        if not supported_files:
            print("No supported audio files to process", file=sys.stderr)
            return (0, 0)
        
        print(f"Processing {len(supported_files)} files")
        
        successful_count = 0
        
        for i, filepath in enumerate(supported_files, 1):
            print(f"[{i}/{len(supported_files)}] {os.path.basename(filepath)}")
            
            # Determine gain
            if use_replaygain:
                file_gain = self.get_replaygain_value(filepath, target_lufs)
                if file_gain is None:
                    print(f"  Could not get ReplayGain value, skipping")
                    continue
            else:
                file_gain = gain_db
            
            # Apply gain
            if self.apply_gain_to_file(filepath, file_gain, output_dir):
                successful_count += 1
        
        return (successful_count, len(supported_files))
    
    def process_directory(self, directory: str, recursive: bool = True,
                         gain_db: Optional[float] = None, use_replaygain: bool = False,
                         target_lufs: int = -18, output_dir: Optional[str] = None) -> Tuple[int, int]:
        """Process all files in directory"""
        if not os.path.isdir(directory):
            print(f"Directory does not exist: {directory}", file=sys.stderr)
            return (0, 0)
        
        file_paths = []
        
        if recursive:
            for root, _, files in os.walk(directory):
                for file in files:
                    filepath = os.path.join(root, file)
                    if self.is_supported_file(filepath):
                        file_paths.append(filepath)
        else:
            for file in os.listdir(directory):
                filepath = os.path.join(directory, file)
                if self.is_supported_file(filepath):
                    file_paths.append(filepath)
        
        return self.process_files(file_paths, gain_db, use_replaygain, target_lufs, output_dir)


def main():
    parser = argparse.ArgumentParser(
        description='Apply gain adjustments to audio files',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""Examples:
  # Apply fixed +3 dB gain
  %(prog)s music/ --gain 3

  # Use ReplayGain values
  %(prog)s music/ --replaygain

  # Use ReplayGain with custom target
  %(prog)s music/ --replaygain --target-lufs -16

  # Save to output directory
  %(prog)s music/ --gain 2 --output output/

Supported: FLAC, MP3, M4A, WAV, OGG, Opus
"""
    )
    
    parser.add_argument("input", nargs="+", help="Files or directories to process")
    
    # Gain mode (mutually exclusive)
    gain_group = parser.add_mutually_exclusive_group(required=True)
    gain_group.add_argument("--gain", type=float, help="Fixed gain in dB (e.g., +3, -2.5)")
    gain_group.add_argument("--replaygain", action="store_true", help="Use ReplayGain values")
    
    # Options
    parser.add_argument("--target-lufs", "--lufs", type=int, default=-18,
                       help="Target LUFS for ReplayGain (default: -18)")
    parser.add_argument("--output", "-o", metavar="DIR",
                       help="Output directory (default: modify in-place)")
    parser.add_argument("--recursive", "-r", action="store_true", default=False,
                       help="Process directories recursively")
    parser.add_argument("--backup", choices=['true', 'false'], default='true',
                       help="Create backup files (default: true)")
    parser.add_argument("--dry-run", action="store_true",
                       help="Show what would be processed")
    parser.add_argument("--force", "-f", action="store_true",
                       help="Skip confirmation prompts")
    parser.add_argument("--quiet", "-q", action="store_true",
                       help="Suppress progress messages")
    parser.add_argument("--verbose", "-v", action="store_true",
                       help="Show detailed information")
    
    args = parser.parse_args()
    
    # Determine if creating backups
    create_backup = args.backup == 'true'
    
    try:
        applicator = LoudnessApplicator(create_backup=create_backup)
        
        # Dry run check
        if args.dry_run:
            print("DRY RUN MODE - No files will be modified")
            return 0
        
        # Confirmation for destructive operations
        if not args.output and not args.force and not create_backup:
            response = input("Modify files in-place without backups? (yes/no): ")
            if response.lower() not in ['yes', 'y']:
                print("Aborted")
                return 0
        
        total_successful = 0
        total_files = 0
        
        # Process inputs
        for input_path in args.input:
            if os.path.isdir(input_path):
                success, total = applicator.process_directory(
                    input_path,
                    args.recursive,
                    args.gain,
                    args.replaygain,
                    args.target_lufs,
                    args.output
                )
            elif os.path.isfile(input_path):
                # Determine gain
                if args.replaygain:
                    gain = applicator.get_replaygain_value(input_path, args.target_lufs)
                    if gain is None:
                        print(f"Could not get ReplayGain for {input_path}", file=sys.stderr)
                        continue
                else:
                    gain = args.gain
                
                success = 1 if applicator.apply_gain_to_file(input_path, gain, args.output) else 0
                total = 1
            else:
                print(f"Not found: {input_path}", file=sys.stderr)
                continue
            
            total_successful += success
            total_files += total
        
        # Summary
        print(f"\nProcessed: {total_successful}/{total_files} files")
        if create_backup and applicator.backup_count > 0:
            print(f"Backups created: {applicator.backup_count}")
        if applicator.error_count > 0:
            print(f"Errors: {applicator.error_count}")
            return 1
        
        return 0
        
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
