#!/usr/bin/env python3

import os
import sys
import argparse
import subprocess
import logging
import shutil
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
import tempfile

# Add parent directory to path for module imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
from modules.addons.replay_gain import ReplayGainAnalyzer
from modules.core import metadata

# Configure logging format
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger('ApplyLoudness')

# Supported audio file extensions
SUPPORTED_EXTENSIONS = {'.flac', '.mp3', '.m4a', '.wav', '.ogg', '.opus'}

class LoudnessApplicator:
    """
    Audio loudness applicator using FFmpeg for gain adjustment
    """
    
    def __init__(self, create_backup: bool = True):
        """
        Initialize the loudness applicator.
        
        Args:
            create_backup (bool): Whether to create backup files before modification
        """
        self.create_backup = create_backup
        self.processed_count = 0
        self.error_count = 0
        self.backup_count = 0
        
        # Validate FFmpeg/FFprobe availability
        self._check_ffmpeg()
    
    def _check_ffmpeg(self):
        """
        Check if FFmpeg and FFprobe are available.
        
        Raises:
            RuntimeError: If FFmpeg or FFprobe is not found.
        """
        for tool in ['ffmpeg', 'ffprobe']:
            try:
                result = subprocess.run(
                    [tool, '-version'],
                    capture_output=True,
                    text=True,
                    check=True
                )
                logger.debug(f"{tool} is available")
            except (subprocess.CalledProcessError, FileNotFoundError):
                raise RuntimeError(
                    f"{tool} not found. Please install FFmpeg and make sure it's in your PATH."
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
    
    def get_replaygain_value(self, filepath: str, target_lufs: int = -18) -> Optional[float]:
        """
        Get ReplayGain value for a file using the ReplayGain analyzer.
        
        Args:
            filepath (str): Path to the audio file
            target_lufs (int): Target LUFS value for ReplayGain calculation
            
        Returns:
            float or None: ReplayGain value in dB, or None if analysis failed
        """
        try:
            # Create analyzer instance with the target LUFS
            analyzer = ReplayGainAnalyzer(target_lufs=target_lufs)
            
            # Analyze the file
            result = analyzer.analyze_file(filepath)
            
            if result is None:
                logger.error(f"ReplayGain analysis failed for {os.path.basename(filepath)}")
                return None
            
            # Extract the gain value
            gain_db = result.get('gain_db')
            if gain_db is None:
                logger.error(f"No gain value found in ReplayGain analysis for {os.path.basename(filepath)}")
                return None
            
            if isinstance(gain_db, str):
                try:
                    gain_db = float(gain_db)
                except ValueError:
                    logger.error(f"Invalid gain value in ReplayGain analysis for {os.path.basename(filepath)}: {gain_db}")
                    return None
            
            logger.debug(f"ReplayGain analysis for {os.path.basename(filepath)}: {result.get('loudness_lufs')} LUFS, {gain_db} dB gain")
            return gain_db
            
        except Exception as e:
            logger.error(f"Error getting ReplayGain value for {os.path.basename(filepath)}: {str(e)}")
            return None
    
    def get_audio_properties(self, filepath: str) -> Dict[str, Any]:
        """
        Get audio properties from a file using FFprobe.
        
        Args:
            filepath (str): Path to the audio file
            
        Returns:
            dict: Audio properties including bit depth, sample rate, etc.
        """
        try:
            cmd = [
                "ffprobe", "-v", "error", 
                "-select_streams", "a:0", 
                "-show_entries", "stream=bits_per_raw_sample,bits_per_sample,sample_rate,channels", 
                "-of", "default=noprint_wrappers=1:nokey=1", 
                str(filepath)
            ]
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=False
            )
            
            if result.returncode != 0:
                logger.warning(f"Could not get audio properties for {os.path.basename(filepath)}")
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
            
        except Exception as e:
            logger.warning(f"Error getting audio properties for {os.path.basename(filepath)}: {str(e)}")
            return {}
    
    def _has_album_art(self, filepath: str) -> bool:
        """
        Check if a file has album art using FFprobe.
        
        Args:
            filepath (str): Path to the audio file
            
        Returns:
            bool: True if the file has album art, False otherwise
        """
        try:
            cmd = [
                "ffprobe", "-v", "error",
                "-select_streams", "v:0",
                "-show_entries", "stream=codec_type",
                "-of", "csv=p=0",
                str(filepath)
            ]
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=False
            )
            
            return result.returncode == 0 and "video" in result.stdout.lower()
            
        except Exception:
            return False
    
    def _handle_opus_album_art(self, original_filepath: str, opus_filepath: str):
        """
        Handle album art embedding for Opus files using the centralized metadata module.
        
        Args:
            original_filepath (str): Path to the original file with album art
            opus_filepath (str): Path to the converted Opus file
        """
        if not self._has_album_art(original_filepath):
            logger.debug(f"No album art detected in {os.path.basename(original_filepath)}")
            return
        
        logger.info("Extracting and embedding album art for Opus file using metadata module")
        
        # Extract album art using FFmpeg first
        temp_art_file = f"{opus_filepath}.albumart.jpg"
        
        try:
            # Extract album art using FFmpeg
            art_cmd = [
                'ffmpeg', '-y', '-i', str(original_filepath),
                '-an', '-vcodec', 'copy', 
                '-map', '0:v:0',  # Map first video stream (album art)
                temp_art_file
            ]
            
            logger.debug(f"Extracting album art to {temp_art_file}")
            
            art_process = subprocess.run(
                art_cmd,
                capture_output=True,
                text=True,
                check=False,
                timeout=60  # Set a 1-minute timeout for art extraction
            )
            
            if art_process.returncode == 0 and os.path.exists(temp_art_file):
                logger.debug("Album art extracted successfully")
                
                # Use the centralized metadata module to embed album art
                if metadata.set_album_art(opus_filepath, temp_art_file):
                    logger.debug("Successfully embedded album art in Opus file using metadata module")
                else:
                    logger.warning("Failed to embed album art using metadata module")
            else:
                logger.warning(f"Failed to extract album art: {art_process.stderr}")
                
        except subprocess.TimeoutExpired:
            logger.error("Album art processing timed out")
        except Exception as e:
            logger.warning(f"Error during album art processing: {str(e)}")
        finally:
            # Clean up temporary art file
            if os.path.exists(temp_art_file):
                try:
                    os.remove(temp_art_file)
                except:
                    pass
    
    def apply_gain_to_file(self, filepath: str, gain_db: float, output_dir: Optional[str] = None) -> bool:
        """
        Apply gain to a single audio file using FFmpeg while preserving metadata and album art.
        
        Args:
            filepath (str): Path to the audio file
            gain_db (float): Gain to apply in dB
            output_dir (str, optional): Output directory for modified files (None for in-place)
            
        Returns:
            bool: True if successful, False otherwise
        """
        if not self.is_supported_file(filepath):
            logger.warning(f"Unsupported file type: {os.path.basename(filepath)}")
            return False
        
        if abs(gain_db) < 0.01:  # Effectively no change
            logger.info(f"Skipping {os.path.basename(filepath)} - no significant gain change needed ({gain_db:.2f} dB)")
            return True
        
        try:
            file_path = Path(filepath)
            ext = file_path.suffix.lower()
            
            # Determine output file path
            if output_dir:
                output_path = Path(output_dir)
                output_path.mkdir(parents=True, exist_ok=True)
                out_file = output_path / file_path.name
            else:
                out_file = file_path
            
            # Create backup if requested and modifying in-place
            if self.create_backup and not output_dir:
                backup_file = file_path.with_suffix(f"{ext}.backup")
                if not backup_file.exists():
                    shutil.copy2(filepath, backup_file)
                    self.backup_count += 1
                    logger.debug(f"Created backup: {backup_file}")
            
            # Create temporary file for processing
            with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as temp_file:
                temp_path = temp_file.name
            
            try:
                # Get audio properties for format-specific encoding
                audio_props = self.get_audio_properties(filepath)
                
                # Build FFmpeg command
                ffmpeg_cmd = [
                    "ffmpeg", "-y", "-i", str(filepath),
                    "-map_metadata", "0",  # Preserve all metadata
                    "-af", f"volume={gain_db}dB",  # Apply gain
                ]
                
                # Special handling for Opus format which needs specific treatment for album art
                if ext == ".opus":
                    # For Opus, we only map audio stream in the initial command
                    # Album art will be handled separately after audio conversion
                    ffmpeg_cmd.extend(["-map", "0:a:0"])  # Only map first audio stream
                else:
                    # For other formats with album art support
                    ffmpeg_cmd.extend(["-map", "0"])  # Map all streams (audio + video/images)
                    ffmpeg_cmd.extend(["-c:v", "copy"])  # Copy video/image streams (album art) without re-encoding
                
                # Format-specific audio encoding settings
                if ext == ".mp3":
                    ffmpeg_cmd += ["-c:a", "libmp3lame"]
                elif ext == ".flac":
                    ffmpeg_cmd += ["-c:a", "flac"]
                    # Preserve bit depth for FLAC
                    if 'bits_per_raw_sample' in audio_props or 'bits_per_sample' in audio_props:
                        bit_depth = audio_props.get('bits_per_raw_sample', audio_props.get('bits_per_sample', 16))
                        if bit_depth == 16:
                            ffmpeg_cmd += ["-sample_fmt", "s16"]
                        elif bit_depth == 24:
                            ffmpeg_cmd += ["-sample_fmt", "s32"]
                        elif bit_depth == 32:
                            ffmpeg_cmd += ["-sample_fmt", "s32"]
                elif ext == ".m4a":
                    ffmpeg_cmd += ["-c:a", "aac"]
                elif ext == ".ogg":
                    ffmpeg_cmd += ["-c:a", "libvorbis"]
                elif ext == ".opus":
                    ffmpeg_cmd += ["-c:a", "libopus"]
                elif ext == ".wav":
                    # For WAV, preserve the original sample format
                    if 'bits_per_sample' in audio_props:
                        bit_depth = audio_props['bits_per_sample']
                        if bit_depth == 16:
                            ffmpeg_cmd += ["-c:a", "pcm_s16le"]
                        elif bit_depth == 24:
                            ffmpeg_cmd += ["-c:a", "pcm_s24le"]
                        elif bit_depth == 32:
                            ffmpeg_cmd += ["-c:a", "pcm_s32le"]
                        else:
                            ffmpeg_cmd += ["-c:a", "pcm_s16le"]  # Default fallback
                    else:
                        ffmpeg_cmd += ["-c:a", "pcm_s16le"]  # Default fallback
                
                ffmpeg_cmd.append(temp_path)
                
                # Execute FFmpeg command
                logger.debug(f"Running FFmpeg command: {' '.join(ffmpeg_cmd)}")
                
                result = subprocess.run(
                    ffmpeg_cmd,
                    capture_output=True,
                    text=False,  # Use binary mode to avoid encoding issues
                    check=False
                )
                
                if result.returncode != 0:
                    # Decode error output safely
                    try:
                        stderr = result.stderr.decode('utf-8', errors='replace') if result.stderr else ""
                        stdout = result.stdout.decode('utf-8', errors='replace') if result.stdout else ""
                    except:
                        stderr = str(result.stderr) if result.stderr else ""
                        stdout = str(result.stdout) if result.stdout else ""
                    
                    logger.error(f"FFmpeg failed for {os.path.basename(filepath)}: {stderr or stdout}")
                    return False
                
                # Special handling for Opus files with album art
                if ext == ".opus":
                    self._handle_opus_album_art(filepath, temp_path)
                
                # Move temporary file to final location
                shutil.move(temp_path, str(out_file))
                
                self.processed_count += 1
                logger.info(f"Applied {gain_db:+.2f} dB gain to {os.path.basename(filepath)}")
                
                return True
                
            finally:
                # Clean up temporary file if it still exists
                if os.path.exists(temp_path):
                    try:
                        os.unlink(temp_path)
                    except:
                        pass
        
        except Exception as e:
            logger.error(f"Error applying gain to {os.path.basename(filepath)}: {str(e)}")
            self.error_count += 1
            return False
    
    def process_files(self, file_paths: List[str], gain_db: Optional[float] = None, 
                     use_replaygain: bool = False, target_lufs: int = -18, 
                     output_dir: Optional[str] = None) -> Tuple[int, int]:
        """
        Process multiple audio files to apply gain.
        
        Args:
            file_paths (list): List of file paths to process
            gain_db (float, optional): Fixed gain to apply in dB
            use_replaygain (bool): Whether to use ReplayGain values instead of fixed gain
            target_lufs (int): Target LUFS for ReplayGain calculation
            output_dir (str, optional): Output directory for modified files
            
        Returns:
            tuple: (successful_count, total_count)
        """
        if not file_paths:
            logger.warning("No files to process")
            return (0, 0)
        
        if not use_replaygain and gain_db is None:
            logger.error("Either gain_db must be specified or use_replaygain must be True")
            return (0, 0)
        
        # Filter supported files
        supported_files = [f for f in file_paths if self.is_supported_file(f)]
        unsupported_count = len(file_paths) - len(supported_files)
        
        if unsupported_count > 0:
            logger.warning(f"Skipping {unsupported_count} unsupported files")
        
        if not supported_files:
            logger.error("No supported audio files to process")
            return (0, 0)
        
        logger.info(f"Processing {len(supported_files)} audio files")
        
        successful_count = 0
        
        for i, filepath in enumerate(supported_files, 1):
            logger.debug(f"Processing file {i}/{len(supported_files)}: {os.path.basename(filepath)}")
            
            # Determine gain to apply
            if use_replaygain:
                file_gain = self.get_replaygain_value(filepath, target_lufs)
                if file_gain is None:
                    logger.error(f"Could not get ReplayGain value for {os.path.basename(filepath)}, skipping")
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
        """
        Process all supported audio files in a directory.
        
        Args:
            directory (str): Directory to process
            recursive (bool): Whether to process subdirectories recursively
            gain_db (float, optional): Fixed gain to apply in dB
            use_replaygain (bool): Whether to use ReplayGain values instead of fixed gain
            target_lufs (int): Target LUFS for ReplayGain calculation
            output_dir (str, optional): Output directory for modified files
            
        Returns:
            tuple: (successful_count, total_count)
        """
        if not os.path.isdir(directory):
            logger.error(f"Directory does not exist: {directory}")
            return (0, 0)
        
        # Find all supported audio files
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


def parse_arguments():
    """
    Parse command line arguments.
    
    Returns:
        argparse.Namespace: Parsed arguments
    """
    parser = argparse.ArgumentParser(
        description="Apply Loudness Tool - Apply gain adjustments to audio files using FFmpeg",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""Examples:
  # Apply fixed +3 dB gain to all files in a directory
  python applyloudness.py /path/to/music --gain +3

  # Apply -2 dB gain to specific files
  python applyloudness.py song1.mp3 song2.flac --gain -2

  # Use ReplayGain values with default -18 LUFS target
  python applyloudness.py /path/to/music --replaygain

  # Use ReplayGain with custom LUFS target (Apple Music standard)
  python applyloudness.py /path/to/music --replaygain --target-lufs -16

  # Process files and save to output directory (preserve originals)
  python applyloudness.py /path/to/music --gain +1.5 --output /path/to/output

  # Apply gain without creating backup files
  python applyloudness.py /path/to/music --gain -1 --backup false

  # Dry run to see what would be processed
  python applyloudness.py /path/to/music --gain +2 --dry-run

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
""")
    
    # Input options
    parser.add_argument(
        "input",
        nargs="+",
        help="Audio files or directories to process"
    )
    
    # Gain mode options (mutually exclusive)
    gain_group = parser.add_mutually_exclusive_group(required=True)
    gain_group.add_argument(
        "--gain",
        type=float,
        help="Fixed gain to apply in dB (e.g., +3, -2.5)"
    )
    gain_group.add_argument(
        "--replaygain",
        action="store_true",
        help="Use ReplayGain values calculated from file analysis"
    )
    
    # ReplayGain options
    parser.add_argument(
        "--target-lufs", "--lufs",
        type=int,
        default=-18,
        help="Target LUFS value for ReplayGain calculation (default: -18)"
    )
    
    # Processing options
    parser.add_argument(
        "--output", "-o",
        metavar="DIR",
        help="Output directory for processed files (default: modify files in-place)"
    )
    parser.add_argument(
        "--recursive", "-r",
        action="store_true",
        default=False,
        help="Process directories recursively (default: False)"
    )
    parser.add_argument(
        "--backup",
        choices=['true', 'false'],
        default='true',
        help="Create backup files when modifying in-place (default: true)"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be processed without actually modifying files"
    )
    parser.add_argument(
        "--force", "-f",
        action="store_true",
        help="Skip confirmation prompt for destructive operations"
    )
    
    # Output options
    parser.add_argument(
        "--quiet", "-q",
        action="store_true",
        help="Suppress progress messages, only show summary"
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Show detailed processing information"
    )
    
    # Utility options
    parser.add_argument(
        "--check-deps",
        action="store_true",
        help="Check if required dependencies are available and exit"
    )
    
    return parser.parse_args()


def main():
    """
    Main function for the apply loudness tool.
    """
    args = parse_arguments()
    
    # Set logging level
    if args.quiet:
        logger.setLevel(logging.WARNING)
    elif args.verbose:
        logger.setLevel(logging.DEBUG)
    
    # Handle dependency check
    if args.check_deps:
        try:
            applicator = LoudnessApplicator()
            print("FFmpeg and FFprobe are available.")
            if args.replaygain:
                try:
                    subprocess.run(['rsgain', '--version'], capture_output=True, check=True)
                    print("rsgain is available.")
                except:
                    print("Warning: rsgain is not available (required for --replaygain mode)")
                    sys.exit(1)
            sys.exit(0)
        except RuntimeError as e:
            print(f"Error: {e}")
            sys.exit(1)
    
    # Validate arguments
    if args.replaygain and not (-30 <= args.target_lufs <= -5):
        logger.warning(f"Target LUFS {args.target_lufs} is outside typical range (-30 to -5)")
    
    if args.gain is not None and abs(args.gain) > 20:
        logger.warning(f"Large gain adjustment ({args.gain} dB) may cause severe distortion or clipping")
    
    # Resolve settings
    recursive = args.recursive
    create_backup = args.backup == 'true' and not args.output  # No backup needed if using output dir
    
    try:
        # Create applicator
        applicator = LoudnessApplicator(create_backup=create_backup)
        
        if args.dry_run:
            logger.info("DRY RUN MODE - No files will be modified")
        else:
            # Warning for destructive operations (skip if --force)
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
                
                # Get user confirmation
                while True:
                    response = input("Type 'y' to confirm or 'n' to cancel: ").strip().lower()
                    if response == 'y':
                        print("Proceeding with gain application...")
                        break
                    elif response == 'n':
                        print("Operation cancelled by user.")
                        sys.exit(0)
                    else:
                        print("Please enter 'y' to confirm or 'n' to cancel.")
            else:
                logger.info("Skipping confirmation prompt (--force enabled)")
        
        # Process all inputs
        total_successful = 0
        total_processed = 0
        
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
                    total_processed += 1
                else:
                    successful, processed = applicator.process_files(
                        [input_path], args.gain, args.replaygain, args.target_lufs, args.output
                    )
                    total_successful += successful
                    total_processed += processed
            
            elif os.path.isdir(input_path):
                # Directory
                logger.info(f"Processing directory: {input_path}")
                
                if args.dry_run:
                    # For dry run, just count files
                    file_count = 0
                    if recursive:
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
                    total_processed += file_count
                else:
                    successful, processed = applicator.process_directory(
                        input_path, recursive, args.gain, args.replaygain, args.target_lufs, args.output
                    )
                    total_successful += successful
                    total_processed += processed
            
            else:
                logger.error(f"Input is neither file nor directory: {input_path}")
        
        # Print summary
        if args.dry_run:
            logger.info(f"Dry run completed: {total_successful}/{total_processed} files would be processed")
        else:
            logger.info(f"Processing completed: {total_successful}/{total_processed} files processed successfully")
            
            if applicator.backup_count > 0:
                logger.info(f"Created {applicator.backup_count} backup files")
            
            if applicator.error_count > 0:
                logger.error(f"Encountered {applicator.error_count} errors during processing")
        
        # Exit with error code if there were failures
        if total_processed > 0 and total_successful < total_processed:
            sys.exit(1)
    
    except Exception as e:
        logger.error(f"Error: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    main()
