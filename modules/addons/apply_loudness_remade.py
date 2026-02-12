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
import logging
from pathlib import Path
from typing import Optional, Dict, Any, Tuple, List

# Add parent directory for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
from modules.addons.replay_gain import ReplayGainAnalyzer
from modules.core import metadata

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger('ApplyLoudness')

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
                logger.debug(f"{tool} is available")
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
            logger.error(f"Error getting ReplayGain for {os.path.basename(filepath)}: {e}")
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
    
    def print_settings(self, gain_db: Optional[float], use_replaygain: bool, target_lufs: int, 
                      output_dir: Optional[str], create_backup: bool):
        """Print loudness application settings"""
        print("\n" + "=" * 60)
        print(f"Loudness Application Settings:")
        if use_replaygain:
            print(f"  Mode: ReplayGain")
            print(f"  Target LUFS: {target_lufs}")
        else:
            print(f"  Mode: Fixed Gain")
            print(f"  Gain: {gain_db:+.2f} dB")
        print(f"  Output: {'New directory' if output_dir else 'In-place modification'}")
        if output_dir:
            print(f"  Output Directory: {output_dir}")
        else:
            print(f"  Create Backups: {'Yes' if create_backup else 'No'}")
        print("=" * 60 + "\n")
    
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
    
    def apply_gain_to_file(self, filepath: str, gain_db: float, output_dir: Optional[str] = None,
                           current_file: int = None, total_files: int = None) -> bool:
        """
        Apply gain to file using FFmpeg
        
        Args:
            filepath: Audio file path
            gain_db: Gain in dB to apply
            output_dir: Output directory (None for in-place)
            current_file: Current file number (for progress display)
            total_files: Total number of files (for progress display)
            
        Returns:
            True if successful
        """
        if not self.is_supported_file(filepath):
            logger.warning(f"Unsupported file type: {os.path.basename(filepath)}")
            return False
        
        if abs(gain_db) < 0.01:
            logger.info(f"Skipping {os.path.basename(filepath)} - no significant gain change ({gain_db:.2f} dB)")
            return True
        
        # Display progress
        if current_file and total_files:
            print(f"\nFile {current_file}/{total_files}: Processing {os.path.basename(filepath)}")
        else:
            print(f"\nProcessing {os.path.basename(filepath)}")
        
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
                print(f"  → Analyzing audio properties...")
                audio_props = self.get_audio_properties(filepath)
                
                print(f"  → Applying {gain_db:+.2f} dB gain...")
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
                    try:
                        stderr = result.stderr.decode('utf-8', errors='replace') if result.stderr else ""
                    except:
                        stderr = str(result.stderr) if result.stderr else ""
                    logger.error(f"FFmpeg failed: {stderr}")
                    return False
                
                print(f"  ✓ Gain applied successfully")
                
                # Handle Opus album art
                if ext == ".opus":
                    print(f"  → Handling album art...")
                    self._handle_opus_album_art(filepath, temp_path)
                
                # Move to final location
                print(f"  → Finalizing...")
                shutil.move(temp_path, str(out_file))
                
                self.processed_count += 1
                print(f"  ✓ Complete: Applied {gain_db:+.2f} dB to {os.path.basename(filepath)}\n")
                logger.debug(f"Successfully processed {os.path.basename(filepath)}")
                
                return True
                
            finally:
                if os.path.exists(temp_path):
                    try:
                        os.remove(temp_path)
                    except:
                        pass
                        
        except Exception as e:
            self.error_count += 1
            logger.error(f"Error processing {os.path.basename(filepath)}: {e}")
            return False
    
    def process_files(self, file_paths: List[str], gain_db: Optional[float] = None,
                     use_replaygain: bool = False, target_lufs: int = -18,
                     output_dir: Optional[str] = None, show_settings: bool = True) -> Tuple[int, int]:
        """
        Process multiple files
        
        Args:
            file_paths: List of file paths
            gain_db: Fixed gain in dB
            use_replaygain: Use ReplayGain values
            target_lufs: Target LUFS for ReplayGain
            output_dir: Output directory
            show_settings: Show settings display
            
        Returns:
            (successful_count, total_count)
        """
        supported_files = [f for f in file_paths if self.is_supported_file(f)]
        unsupported_count = len(file_paths) - len(supported_files)
        
        if unsupported_count > 0:
            logger.warning(f"Skipping {unsupported_count} unsupported files")
        
        if not supported_files:
            logger.error("No supported audio files to process")
            return (0, 0)
        
        # Print settings
        if show_settings:
            self.print_settings(gain_db, use_replaygain, target_lufs, output_dir, self.create_backup)
            print(f"Found {len(supported_files)} audio file(s) to process\n")
        
        successful_count = 0
        
        for i, filepath in enumerate(supported_files, 1):
            logger.debug(f"Processing file {i}/{len(supported_files)}: {os.path.basename(filepath)}")
            
            # Determine gain
            if use_replaygain:
                file_gain = self.get_replaygain_value(filepath, target_lufs)
                if file_gain is None:
                    logger.error(f"Could not get ReplayGain value, skipping")
                    continue
            else:
                file_gain = gain_db
            
            # Apply gain
            if self.apply_gain_to_file(filepath, file_gain, output_dir, current_file=i, total_files=len(supported_files)):
                successful_count += 1
        
        return (successful_count, len(supported_files))
    
    def process_directory(self, directory: str, recursive: bool = True,
                         gain_db: Optional[float] = None, use_replaygain: bool = False,
                         target_lufs: int = -18, output_dir: Optional[str] = None) -> Tuple[int, int]:
        """Process all files in directory"""
        if not os.path.isdir(directory):
            logger.error(f"Directory does not exist: {directory}")
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
        
        return self.process_files(file_paths, gain_db, use_replaygain, target_lufs, output_dir, show_settings=True)


def main():
    parser = argparse.ArgumentParser(
        description='Apply Loudness Tool - Apply gain adjustments to audio files using FFmpeg',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""Examples:
  # Apply fixed +3 dB gain to all files in a directory
  %(prog)s music/ --gain +3

  # Apply -2 dB gain to specific files
  %(prog)s song1.mp3 song2.flac --gain -2

  # Use ReplayGain values with default -18 LUFS target
  %(prog)s music/ --replaygain

  # Use ReplayGain with custom LUFS target (Apple Music standard)
  %(prog)s music/ --replaygain --target-lufs -16

  # Process files and save to output directory (preserve originals)
  %(prog)s music/ --gain +1.5 --output output/

  # Apply gain without creating backup files
  %(prog)s music/ --gain -1 --backup false

  # Dry run to see what would be processed
  %(prog)s music/ --gain +2 --dry-run

Supported file formats:
  - FLAC (.flac)
  - MP3 (.mp3)
  - M4A (.m4a)
  - WAV (.wav)
  - OGG (.ogg)
  - Opus (.opus)

LUFS Target Values (for --replaygain mode):
  -18 LUFS: ReplayGain 2.0 standard (default)
  -16 LUFS: Apple Music standard
  -14 LUFS: Spotify, Amazon Music, YouTube standard
  -20 LUFS: TV broadcast standard

Requirements:
  - FFmpeg (for audio processing)
  - rsgain (for ReplayGain mode)
"""
    )
    
    parser.add_argument("input", nargs="+", help="Audio files or directories to process")
    
    # Gain mode (mutually exclusive)
    gain_group = parser.add_mutually_exclusive_group(required=True)
    gain_group.add_argument("--gain", type=float, help="Fixed gain to apply in dB (e.g., +3, -2.5)")
    gain_group.add_argument("--replaygain", action="store_true", 
                           help="Use ReplayGain values calculated from file analysis")
    
    # ReplayGain options
    parser.add_argument("--target-lufs", "--lufs", type=int, default=-18,
                       help="Target LUFS value for ReplayGain calculation (default: -18)")
    
    # Processing options
    parser.add_argument("--output", "-o", metavar="DIR",
                       help="Output directory for processed files (default: modify files in-place)")
    parser.add_argument("--recursive", "-r", action="store_true", default=False,
                       help="Process directories recursively (default: False)")
    parser.add_argument("--backup", choices=['true', 'false'], default='true',
                       help="Create backup files when modifying in-place (default: true)")
    parser.add_argument("--dry-run", action="store_true",
                       help="Show what would be processed without actually modifying files")
    parser.add_argument("--force", "-f", action="store_true",
                       help="Skip confirmation prompt for destructive operations")
    
    args = parser.parse_args()
    
    # Validate arguments
    if args.replaygain and not (-30 <= args.target_lufs <= -5):
        logger.warning(f"Target LUFS {args.target_lufs} is outside typical range (-30 to -5)")
    
    if args.gain is not None and abs(args.gain) > 20:
        logger.warning(f"Large gain adjustment ({args.gain} dB) may cause severe distortion or clipping")
    
    # Determine if creating backups
    create_backup = args.backup == 'true' and not args.output
    
    try:
        applicator = LoudnessApplicator(create_backup=create_backup)
        
        # Dry run check
        if args.dry_run:
            logger.info("DRY RUN MODE - No files will be modified")
        else:
            # Warning for destructive operations
            if not args.force:
                print("\n" + "="*60)
                print("WARNING: DESTRUCTIVE OPERATION")
                print("="*60)
                print("Applying gain directly to audio files can permanently damage them")
                print("and may cause irreversible audio quality loss or clipping.")
                print("")
                print("This operation will modify your audio files directly.")
                if not create_backup:
                    print("Backup creation is DISABLED - original files will be lost!")
                else:
                    print("Backup files will be created (.backup extension)")
                print("")
                print("Are you absolutely sure you want to continue?")
                print("="*60)
                
                while True:
                    response = input("Type 'y' to confirm or 'n' to cancel: ").strip().lower()
                    if response == 'y':
                        print("Proceeding with gain application...")
                        break
                    elif response == 'n':
                        print("Operation cancelled by user.")
                        return 0
                    else:
                        print("Please enter 'y' to confirm or 'n' to cancel.")
            else:
                logger.info("Skipping confirmation prompt (--force enabled)")
        
        total_successful = 0
        total_files = 0
        
        # Process inputs
        for input_path in args.input:
            if not os.path.exists(input_path):
                logger.error(f"Input does not exist: {input_path}")
                continue
            
            if os.path.isfile(input_path):
                # Single file
                if not applicator.is_supported_file(input_path):
                    logger.warning(f"Unsupported file: {input_path}")
                    continue
                
                logger.info(f"Processing file: {os.path.basename(input_path)}")
                
                if args.dry_run:
                    if args.replaygain:
                        gain_value = applicator.get_replaygain_value(input_path, args.target_lufs)
                        if gain_value is not None:
                            logger.info(f"Would apply {gain_value:+.2f} dB gain (ReplayGain) to {os.path.basename(input_path)}")
                        else:
                            logger.warning(f"Could not determine ReplayGain for {os.path.basename(input_path)}")
                    else:
                        logger.info(f"Would apply {args.gain:+.2f} dB gain to {os.path.basename(input_path)}")
                    total_successful += 1
                    total_files += 1
                else:
                    # Show settings for single file
                    applicator.print_settings(args.gain, args.replaygain, args.target_lufs, args.output, create_backup)
                    print(f"Found 1 audio file to process\n")
                    
                    if args.replaygain:
                        gain = applicator.get_replaygain_value(input_path, args.target_lufs)
                        if gain is None:
                            logger.error(f"Could not get ReplayGain for {input_path}")
                            continue
                    else:
                        gain = args.gain
                    
                    success = 1 if applicator.apply_gain_to_file(input_path, gain, args.output) else 0
                    total_successful += success
                    total_files += 1
            
            elif os.path.isdir(input_path):
                # Directory
                logger.info(f"Processing directory: {input_path}")
                
                if args.dry_run:
                    # For dry run, just count files
                    file_count = 0
                    if args.recursive:
                        for root, _, files in os.walk(input_path):
                            for file in files:
                                filepath = os.path.join(root, file)
                                if applicator.is_supported_file(filepath):
                                    file_count += 1
                    else:
                        for file in os.listdir(input_path):
                            filepath = os.path.join(input_path, file)
                            if applicator.is_supported_file(filepath):
                                file_count += 1
                    
                    if args.replaygain:
                        logger.info(f"Would analyze and apply ReplayGain to {file_count} files")
                    else:
                        logger.info(f"Would apply {args.gain:+.2f} dB gain to {file_count} files")
                    total_successful += file_count
                    total_files += file_count
                else:
                    success, total = applicator.process_directory(
                        input_path,
                        args.recursive,
                        args.gain,
                        args.replaygain,
                        args.target_lufs,
                        args.output
                    )
                    total_successful += success
                    total_files += total
            
            else:
                logger.error(f"Input is neither file nor directory: {input_path}")
        
        # Print summary
        if args.dry_run:
            logger.info(f"Dry run completed: {total_successful}/{total_files} files would be processed")
        else:
            print(f"\nProcessing completed:")
            print(f"  Successful: {total_successful}")
            print(f"  Total: {total_files}")
            if total_successful < total_files:
                print(f"  Failed: {total_files - total_successful}")
            
            if create_backup and applicator.backup_count > 0:
                print(f"  Backups created: {applicator.backup_count}")
            
            if applicator.error_count > 0:
                logger.error(f"Encountered {applicator.error_count} errors during processing")
                return 1
        
        return 0 if total_successful == total_files else 1
        
    except Exception as e:
        logger.error(f"Error: {e}")
        return 1


if __name__ == '__main__':
    sys.exit(main())
