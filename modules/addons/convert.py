#!/usr/bin/env python3
"""
Audio File Converter using FFmpeg
Copyright (c) 2025 TAPS OSS
Project: https://github.com/TAPSOSS/Walrio
Licensed under the BSD-3-Clause License (see LICENSE file for details)

A flexible audio conversion tool that supports multiple input formats and provides
various conversion options including output format selection, metadata preservation,
bitrate adjustment, and bit depth selection.
"""

import os
import sys
import argparse
import subprocess
import logging
import json
import tempfile
from pathlib import Path
from typing import List, Dict, Any, Tuple, Optional, Union

# Configure logging format
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger('AudioConverter')

# Supported formats for conversion
SUPPORTED_OUTPUT_FORMATS = {
    'mp3': {'ext': 'mp3', 'desc': 'MP3 (MPEG Layer III)', 'codec': 'libmp3lame'},
    'aac': {'ext': 'm4a', 'desc': 'AAC (Advanced Audio Coding)', 'codec': 'aac'},
    'opus': {'ext': 'opus', 'desc': 'Opus (Opus Interactive Audio Codec)', 'codec': 'libopus'},
    'ogg': {'ext': 'ogg', 'desc': 'Ogg Vorbis', 'codec': 'libvorbis'},
    'flac': {'ext': 'flac', 'desc': 'FLAC (Free Lossless Audio Codec)', 'codec': 'flac'},
    'alac': {'ext': 'm4a', 'desc': 'ALAC (Apple Lossless Audio Codec)', 'codec': 'alac'},
    'wav': {'ext': 'wav', 'desc': 'WAV (Waveform Audio File Format)', 'codec': 'pcm_s16le'},
    'wv': {'ext': 'wv', 'desc': 'WavPack', 'codec': 'wavpack'},
}

# Default conversion settings
DEFAULT_SETTINGS = {
    'output_format': 'flac',
    'metadata': 'y',  # y = yes, n = no
    'bitrate': '320k',
    'bit_depth': '16',
    'sample_rate': '48000',
    'channels': '2',
    'quality': 'maximum',  # standard, high, maximum
    'skip_existing': False,
    'recursive': False,
    'force_overwrite': False,  # Don't force overwrite by default
}

# Bitrate presets for various formats (in kbps)
BITRATE_PRESETS = {
    'mp3': {'low': '96k', 'medium': '192k', 'high': '320k'},
    'aac': {'low': '96k', 'medium': '192k', 'high': '256k'},
    'opus': {'low': '64k', 'medium': '128k', 'high': '256k'},
    'ogg': {'low': '96k', 'medium': '192k', 'high': '256k'},
}

# Bit depth options
BIT_DEPTH_OPTIONS = {
    '16': {'desc': '16-bit (CD Quality)', 'pcm_codec': 'pcm_s16le'},
    '24': {'desc': '24-bit (Studio Quality)', 'pcm_codec': 'pcm_s24le'},
    '32': {'desc': '32-bit (Float)', 'pcm_codec': 'pcm_f32le'},
}

# Quality presets mapping
QUALITY_PRESETS = {
    'low': {'desc': 'Lower quality, smaller files'},
    'standard': {'desc': 'Standard quality, balanced file size'},
    'high': {'desc': 'High quality, larger files'},
    'maximum': {'desc': 'Maximum quality'},
}

class AudioConverter:
    """
    Audio file converter using FFmpeg to convert between various audio formats
    with options for metadata preservation, bitrate, bit depth, and other settings.
    """
    
    def __init__(self, options: Dict[str, Any]):
        """
        Initialize the AudioConverter with the specified options.
        
        Args:
            options (dict): Dictionary of conversion options
        """
        self.options = DEFAULT_SETTINGS.copy()
        self.options.update(options)
        
        # Validate FFmpeg availability
        self._check_ffmpeg()
    
    def _check_ffmpeg(self):
        """
        Check if FFmpeg is available and get version information.
        
        Raises:
            RuntimeError: If FFmpeg is not found.
        """
        try:
            result = subprocess.run(
                ['ffmpeg', '-version'],
                capture_output=True,
                text=True,
                check=True
            )
            ffmpeg_version = result.stdout.split('\\n')[0]
            logger.debug(f"Using {ffmpeg_version}")
        except (subprocess.CalledProcessError, FileNotFoundError):
            raise RuntimeError(
                "FFmpeg not found. Please install FFmpeg and make sure it's in your PATH."
            )
    
    def get_file_info(self, filepath: str) -> Dict[str, Any]:
        """
        Get detailed information about an audio file using FFprobe.
        
        Args:
            filepath (str): Path to the audio file
            
        Returns:
            dict: Dictionary containing file information
        """
        try:
            cmd = [
                'ffprobe', 
                '-v', 'quiet', 
                '-print_format', 'json', 
                '-show_format', 
                '-show_streams', 
                filepath
            ]
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=True
            )
            
            file_info = json.loads(result.stdout)
            return file_info
        except (subprocess.CalledProcessError, json.JSONDecodeError) as e:
            logger.warning(f"Could not get file info for {filepath}: {str(e)}")
            return {}
    
    def display_file_info(self, filepath: str):
        """
        Display detailed information about an audio file.
        
        Args:
            filepath (str): Path to the audio file
        """
        file_info = self.get_file_info(filepath)
        
        if not file_info:
            print(f"Could not get information for {filepath}")
            return
            
        print(f"\nFile Information: {os.path.basename(filepath)}")
        print("-" * 50)
        
        # Format information
        if 'format' in file_info:
            fmt = file_info['format']
            duration = float(fmt.get('duration', '0'))
            minutes = int(duration / 60)
            seconds = int(duration % 60)
            
            print(f"Format: {fmt.get('format_long_name', 'Unknown')}")
            print(f"Duration: {minutes}:{seconds:02d}")
            print(f"Size: {int(fmt.get('size', 0)) / (1024*1024):.2f} MB")
            print(f"Bitrate: {int(fmt.get('bit_rate', 0)) / 1000:.0f} kbps")
            
        # Stream information
        if 'streams' in file_info:
            audio_streams = [s for s in file_info['streams'] if s.get('codec_type') == 'audio']
            
            for i, stream in enumerate(audio_streams):
                print(f"\nAudio Stream #{i+1}:")
                print(f"  Codec: {stream.get('codec_name', 'Unknown')} ({stream.get('codec_long_name', 'Unknown')})")
                print(f"  Sample Rate: {stream.get('sample_rate', 'Unknown')} Hz")
                print(f"  Channels: {stream.get('channels', 'Unknown')}")
                print(f"  Channel Layout: {stream.get('channel_layout', 'Unknown')}")
                print(f"  Bit Depth: {stream.get('bits_per_sample', 'N/A')}-bit")
        
        # Metadata
        if 'format' in file_info and 'tags' in file_info['format']:
            tags = file_info['format']['tags']
            print("\nMetadata:")
            for key, value in tags.items():
                print(f"  {key}: {value}")
    
    def build_ffmpeg_command(self, input_file: str, output_file: str) -> List[str]:
        """
        Build the FFmpeg command for audio conversion based on the options.
        
        Args:
            input_file (str): Path to the input file
            output_file (str): Path to the output file
            
        Returns:
            list: FFmpeg command as a list of arguments
        """
        output_format = self.options['output_format']
        codec = SUPPORTED_OUTPUT_FORMATS[output_format]['codec']
        
        # Start with basic command
        cmd = ['ffmpeg']
        
        # Add force overwrite flag if specified
        if self.options.get('force_overwrite', False):
            cmd.append('-y')
            
        cmd.extend(['-i', input_file])
        
        # Add codec
        cmd.extend(['-c:a', codec])
        
        # Handle bitrate for lossy formats
        if output_format in ('mp3', 'aac', 'opus', 'ogg'):
            cmd.extend(['-b:a', self.options['bitrate']])
            
        # Handle bit depth for lossless formats
        if output_format in ('flac', 'wav', 'alac'):
            if output_format == 'wav':
                # For WAV, we need to select the appropriate PCM codec based on bit depth
                bit_depth = self.options['bit_depth']
                if bit_depth in BIT_DEPTH_OPTIONS:
                    pcm_codec = BIT_DEPTH_OPTIONS[bit_depth]['pcm_codec']
                    cmd[cmd.index('-c:a') + 1] = pcm_codec
            else:
                # For other lossless formats, set the bit depth parameter
                cmd.extend(['-sample_fmt', f's{self.options["bit_depth"]}'])
        
        # Set sample rate if specified
        if self.options.get('sample_rate'):
            cmd.extend(['-ar', self.options['sample_rate']])
            
        # Set channels if specified
        if self.options.get('channels'):
            cmd.extend(['-ac', self.options['channels']])
        
        # Quality settings for specific formats
        if output_format == 'mp3' and codec == 'libmp3lame':
            # MP3 quality setting (0-9, where 0 is best)
            quality = {'low': '5', 'standard': '2', 'high': '0', 'maximum': '0'}
            cmd.extend(['-q:a', quality.get(self.options['quality'], '2')])
        elif output_format == 'opus':
            # Opus has excellent quality even at low bitrates
            if self.options['quality'] == 'maximum':
                cmd.extend(['-compression_level', '10'])
        elif output_format == 'flac':
            # FLAC compression level (0-12, where 12 is highest compression)
            flac_compression = {'low': '5', 'standard': '8', 'high': '10', 'maximum': '12'}
            cmd.extend(['-compression_level', flac_compression.get(self.options['quality'], '8')])
                
        # Handle metadata preservation
        if self.options['metadata'] == 'n':
            cmd.extend(['-map_metadata', '-1'])
        else:
            # Always map metadata from input to output
            cmd.extend(['-map_metadata', '0'])
            
            # Special handling for Opus format which needs specific treatment for album art
            if output_format == 'opus':
                # For Opus, we only map audio stream in the initial command
                # Album art will be handled separately after audio conversion
                cmd = [x for x in cmd if x != '-map' or x == '-map_metadata']  # Remove any map options except metadata
                cmd.extend(['-map', '0:a:0'])  # Only map first audio stream
            else:
                # For other formats with album art support
                cmd.extend(['-map', '0'])  # Map all streams
                cmd.extend(['-c:v', 'copy'])  # Copy album art as-is
                
                if output_format == 'mp3':
                    # For MP3, ensure album art is properly tagged
                    cmd.extend(['-id3v2_version', '3', '-write_id3v1', '1'])
        
        # Set the output file
        cmd.append(output_file)
        
        return cmd
    
    def convert_file(self, input_file: str, output_dir: Optional[str] = None) -> bool:
        """
        Convert a single audio file to the specified format.
        
        Args:
            input_file (str): Path to the input file
            output_dir (str, optional): Output directory. If None, use the input directory.
            
        Returns:
            bool: True if conversion was successful, False otherwise
        """
        if not os.path.isfile(input_file):
            logger.error(f"Input file does not exist: {input_file}")
            return False
        
        # Get output directory
        if output_dir is None:
            output_dir = os.path.dirname(input_file)
        
        # Create output directory if it doesn't exist
        os.makedirs(output_dir, exist_ok=True)
        
        # Determine output filename
        output_format = self.options['output_format']
        output_ext = SUPPORTED_OUTPUT_FORMATS[output_format]['ext']
        
        base_name = os.path.splitext(os.path.basename(input_file))[0]
        output_file = os.path.join(output_dir, f"{base_name}.{output_ext}")
        
        # Check if output file already exists and skip_existing is True
        if os.path.exists(output_file) and self.options['skip_existing']:
            logger.info(f"Skipping existing file: {output_file}")
            return True
            
        # Get file information for logging
        file_info = self.get_file_info(input_file)
        input_format = file_info.get('format', {}).get('format_name', 'unknown')
        
        # Check if file has album art
        has_album_art = False
        album_art_streams = []
        if 'streams' in file_info:
            for i, stream in enumerate(file_info['streams']):
                if stream.get('codec_type') == 'video' and 'attached_pic' in stream.get('disposition', {}):
                    has_album_art = True
                    album_art_streams.append(i)
        
        logger.info(f"Converting {input_file} ({input_format}) to {output_format}")
        
        if has_album_art:
            if self.options['metadata'] == 'y':
                if output_format == 'opus':
                    logger.info(f"Album art detected - will be properly embedded in Opus file using mutagen")
                else:
                    logger.info(f"Album art detected - will be preserved in output file")
            else:
                logger.info(f"Album art detected but will be removed (--metadata n specified)")
        
        # Build FFmpeg command
        cmd = self.build_ffmpeg_command(input_file, output_file)
        logger.debug(f"FFmpeg command: {' '.join(cmd)}")
        
        try:
            # Run FFmpeg with a timeout
            logger.info(f"Starting FFmpeg process for audio conversion")
            try:
                process = subprocess.run(
                    cmd, 
                    capture_output=True, 
                    text=True,
                    check=False,
                    timeout=300  # Set a 5-minute timeout for the conversion process
                )
                
                # Log command output for debugging
                if process.stdout:
                    logger.debug(f"FFmpeg stdout: {process.stdout}")
                
                # Check if user declined to overwrite the file
                if process.returncode != 0:
                    # Look for the specific "not overwriting" message in stderr
                    if "not overwriting" in process.stderr.lower() or "file exists" in process.stderr.lower():
                        logger.info(f"User declined to overwrite {output_file}")
                    else:
                        logger.error(f"FFmpeg error: {process.stderr}")
                    return False
                
                logger.info(f"Initial audio conversion completed successfully")
            except subprocess.TimeoutExpired:
                logger.error(f"FFmpeg process timed out after 5 minutes")
                return False
            
            # Special handling for Opus files with album art
            if output_format == 'opus' and has_album_art and self.options['metadata'] == 'y':
                # Extract album art to temporary file
                logger.info("Extracting album art for Opus embedding")
                temp_art_file = f"{output_file}.albumart.jpg"
                
                # Get the first album art stream
                art_stream_index = album_art_streams[0] if album_art_streams else 0
                
                # Extract album art using FFmpeg (force overwrite for temp files)
                art_cmd = [
                    'ffmpeg', '-y', '-i', input_file,  # -y is ok here since it's a temp file
                    '-an', '-vcodec', 'copy', 
                    '-map', f'0:{art_stream_index}',
                    temp_art_file
                ]
                
                try:
                    logger.info(f"Extracting album art to {temp_art_file}")
                    logger.debug(f"Album art extraction command: {' '.join(art_cmd)}")
                    
                    art_process = subprocess.run(
                        art_cmd,
                        capture_output=True,
                        text=True,
                        check=False,
                        timeout=60  # Set a 1-minute timeout for art extraction
                    )
                    
                    if art_process.returncode == 0 and os.path.exists(temp_art_file):
                        # Now embed the extracted art into the Opus file using mutagen via python script
                        logger.info(f"Album art extracted successfully to {temp_art_file}")
                        logger.info("Embedding album art in Opus file using mutagen")
                        
                        # Create a small Python script to embed the cover using mutagen
                        temp_script = f"{output_file}.embed_art.py"
                        with open(temp_script, 'w') as f:
                            f.write(f'''
import base64
from mutagen.oggopus import OggOpus
from mutagen.flac import Picture
from PIL import Image
import io

# Load the image and resize if necessary
img = Image.open("{temp_art_file}")
img = img.convert("RGB")
img = img.resize((1000, 1000), Image.LANCZOS)  # Resize to reasonable size
buf = io.BytesIO()
img.save(buf, format="JPEG")
img_data = buf.getvalue()

# Create FLAC Picture object
pic = Picture()
pic.mime = "image/jpeg"
pic.type = 3  # Front cover
pic.data = img_data
pic.desc = "Cover"

# Embed in Opus file
opus = OggOpus("{output_file}")
opus["METADATA_BLOCK_PICTURE"] = [base64.b64encode(pic.write()).decode("ascii")]
opus.save()

print("Album art embedded successfully!")
''')
                        
                        # Execute the Python script
                        python_cmd = [sys.executable, temp_script]
                        logger.debug(f"Running Python script to embed album art: {' '.join(python_cmd)}")
                        
                        python_process = subprocess.run(
                            python_cmd,
                            capture_output=True,
                            text=True,
                            check=False,
                            timeout=60  # Set a 1-minute timeout for embedding
                        )
                        
                        if python_process.returncode == 0:
                            logger.info("Successfully embedded album art in Opus file")
                        else:
                            logger.warning(f"Failed to embed album art: {python_process.stderr}")
                        
                        # Clean up temporary files
                        for temp_file in [temp_art_file, temp_script]:
                            if os.path.exists(temp_file):
                                os.remove(temp_file)
                    else:
                        logger.warning(f"Failed to extract album art: {art_process.stderr}")
                except subprocess.TimeoutExpired:
                    logger.error("Album art processing timed out")
                except Exception as e:
                    logger.warning(f"Error during album art processing: {str(e)}")
            
            logger.info(f"Successfully converted {input_file} to {output_file}")
            return True
        except Exception as e:
            logger.error(f"Error converting {input_file}: {str(e)}")
            # Clean up any temporary files that might have been created
            temp_files = [
                f"{output_file}.albumart.jpg",
                f"{output_file}.embed_art.py"
            ]
            for tmp_file in temp_files:
                if os.path.exists(tmp_file):
                    try:
                        os.remove(tmp_file)
                    except:
                        pass
            return False
    
    def convert_directory(self, input_dir: str, output_dir: Optional[str] = None) -> Tuple[int, int]:
        """
        Convert all audio files in a directory to the specified format.
        
        Args:
            input_dir (str): Input directory containing audio files
            output_dir (str, optional): Output directory. If None, use the input directory.
            
        Returns:
            tuple: (number of successful conversions, total number of files attempted)
        """
        if not os.path.isdir(input_dir):
            logger.error(f"Input directory does not exist: {input_dir}")
            return (0, 0)
        
        # Create output directory if it doesn't exist
        if output_dir is not None:
            os.makedirs(output_dir, exist_ok=True)
        
        # Get list of audio files
        audio_extensions = ['.mp3', '.flac', '.wav', '.ogg', '.m4a', '.aac', '.opus', '.wma', '.ape', '.wv']
        
        files_to_convert = []
        
        if self.options['recursive']:
            # Walk through directory tree recursively
            for root, _, files in os.walk(input_dir):
                for file in files:
                    if any(file.lower().endswith(ext) for ext in audio_extensions):
                        files_to_convert.append(os.path.join(root, file))
        else:
            # Non-recursive: just get files in the top directory
            files_to_convert = [
                os.path.join(input_dir, file) 
                for file in os.listdir(input_dir) 
                if os.path.isfile(os.path.join(input_dir, file)) and
                any(file.lower().endswith(ext) for ext in audio_extensions)
            ]
        
        total_files = len(files_to_convert)
        logger.info(f"Found {total_files} audio files to convert")
        
        # Convert each file
        success_count = 0
        for i, file in enumerate(files_to_convert, 1):
            logger.info(f"Processing file {i}/{total_files}: {os.path.basename(file)}")
            
            # Determine output path preserving directory structure if recursive
            if output_dir is not None and self.options['recursive']:
                rel_path = os.path.relpath(os.path.dirname(file), input_dir)
                file_output_dir = os.path.join(output_dir, rel_path)
                os.makedirs(file_output_dir, exist_ok=True)
            else:
                file_output_dir = output_dir
                
            if self.convert_file(file, file_output_dir):
                success_count += 1
        
        return (success_count, total_files)


def parse_arguments():
    """
    Parse command line arguments.
    
    Returns:
        argparse.Namespace: Parsed arguments
    """
    parser = argparse.ArgumentParser(
        description="Audio File Converter using FFmpeg",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="Examples:\n"
               "  # Convert a single file to MP3\n"
               "  python convert.py input.wav --format mp3\n\n"
               "  # Convert multiple files at once\n"
               "  python convert.py file1.wav file2.mp3 file3.flac --format ogg\n\n"
               "  # Convert a directory of files to FLAC (default format)\n"
               "  python convert.py /music/input\n\n"
               "  # Convert files from multiple directories\n"
               "  python convert.py /music/input1 /music/input2 -o /music/output\n\n"
               "  # Explicitly specify that inputs are files\n"
               "  python convert.py file1 file2 --type file\n\n"
               "  # Convert files recursively without metadata, high logging level\n"
               "  python convert.py /music/input -o /music/output -r --metadata n --logging high\n\n"
               "  # Force overwrite existing files without prompting\n"
               "  python convert.py input.flac -f opus -y\n"
    )
    
    # Input/output options
    parser.add_argument(
        "input",
        nargs='+',  # Accept one or more input files/directories
        help="Input file(s) or directory to convert"
    )
    parser.add_argument(
        "--type",
        choices=["file", "directory", "auto"],
        default="auto",
        help="Explicitly specify if inputs are files or a directory (default: auto-detect)"
    )
    parser.add_argument(
        "-o", "--output",
        help="Output directory (default: same as input)"
    )
    parser.add_argument(
        "-r", "--recursive",
        action="store_true",
        help="Recursively process directories"
    )
    parser.add_argument(
        "--skip-existing",
        action="store_true",
        help="Skip existing files"
    )
    parser.add_argument(
        "-y", "--force-overwrite",
        action="store_true",
        help="Force overwrite of existing files without prompting"
    )
    
    # Format options
    parser.add_argument(
        "-f", "--format",
        choices=list(SUPPORTED_OUTPUT_FORMATS.keys()),
        help="Output format (default: flac)"
    )
    parser.add_argument(
        "--metadata",
        choices=["y", "n"],
        default="y",
        help="Preserve metadata: y=yes (default), n=no"
    )
    
    # Audio quality options
    parser.add_argument(
        "-b", "--bitrate",
        help="Audio bitrate for lossy formats (e.g., 128k, 256k, 320k)"
    )
    parser.add_argument(
        "-d", "--bit-depth",
        choices=list(BIT_DEPTH_OPTIONS.keys()),
        help="Bit depth for lossless formats"
    )
    parser.add_argument(
        "--sample-rate",
        choices=["44100", "48000", "96000", "192000", "320000"],
        help="Sample rate in Hz"
    )
    parser.add_argument(
        "--channels",
        choices=["1", "2"],
        help="Number of audio channels (1=mono, 2=stereo)"
    )
    parser.add_argument(
        "-q", "--quality",
        choices=list(QUALITY_PRESETS.keys()),
        help="Encoding quality preset"
    )
    
    # Utility options
    parser.add_argument(
        "-i", "--info",
        action="store_true",
        help="Display information about the input file and exit"
    )
    parser.add_argument(
        "--logging",
        choices=["low", "high"],
        default="low",
        help="Logging level: low (default) or high (verbose)"
    )
    parser.add_argument(
        "--list-formats",
        action="store_true",
        help="List supported output formats and exit"
    )
    
    return parser.parse_args()


def main():
    """
    Main function for the audio converter.
    """
    args = parse_arguments()
    
    # Set logging level
    if args.logging == "high":
        logger.setLevel(logging.DEBUG)
    
    # List supported formats and exit
    if args.list_formats:
        print("Supported output formats:")
        for fmt, info in SUPPORTED_OUTPUT_FORMATS.items():
            print(f"  {fmt}: {info['desc']} (.{info['ext']})")
        return
    
    # Prepare conversion options
    options = DEFAULT_SETTINGS.copy()
    
    if args.format:
        options['output_format'] = args.format
    if args.metadata:
        options['metadata'] = args.metadata
    if args.bitrate:
        options['bitrate'] = args.bitrate
    if args.bit_depth:
        options['bit_depth'] = args.bit_depth
    if args.sample_rate:
        options['sample_rate'] = args.sample_rate
    if args.channels:
        options['channels'] = args.channels
    if args.quality:
        options['quality'] = args.quality
    if args.recursive:
        options['recursive'] = True
    if args.skip_existing:
        options['skip_existing'] = True
    if args.force_overwrite:
        options['force_overwrite'] = True
    
    # Create converter
    try:
        converter = AudioConverter(options)
        
        # Just display file info and exit
        if args.info:
            if len(args.input) > 1:
                logger.warning("Multiple inputs provided with --info, showing info for the first file only")
                
            input_path = args.input[0]  # Get first input
            
            # Handle --type parameter with --info
            if args.type == "file" or (args.type == "auto" and os.path.isfile(input_path)):
                converter.display_file_info(input_path)
            else:
                logger.error(f"--info option requires a file input, not a directory")
            return
        
        # Process multiple inputs based on type parameter
        input_files = []
        input_dirs = []
        
        # When a single input is provided, args.input is still a list with one item
        for input_path in args.input:
            if args.type == "file":
                if not os.path.isfile(input_path):
                    logger.error(f"Input was specified as a file, but '{input_path}' is not a file")
                    sys.exit(1)
                input_files.append(input_path)
            elif args.type == "directory":
                if not os.path.isdir(input_path):
                    logger.error(f"Input was specified as a directory, but '{input_path}' is not a directory")
                    sys.exit(1)
                input_dirs.append(input_path)
            else:  # auto-detect
                if os.path.isfile(input_path):
                    input_files.append(input_path)
                elif os.path.isdir(input_path):
                    input_dirs.append(input_path)
                else:
                    logger.error(f"Input path '{input_path}' doesn't exist")
                    sys.exit(1)
            
        # Prepare output directory
        output_dir = args.output if args.output else None
        
        # Process all files first
        if input_files:
            logger.info(f"Converting {len(input_files)} individual file(s)")
            success_count = 0
            
            for file_path in input_files:
                if converter.convert_file(file_path, output_dir):
                    success_count += 1
                    
            logger.info(f"File conversion completed: {success_count}/{len(input_files)} files converted successfully")
            if success_count < len(input_files):
                sys.exit(1)
        
        # Then process all directories
        total_dir_files = 0
        total_dir_success = 0
        
        for dir_path in input_dirs:
            logger.info(f"Converting files in directory: {dir_path}")
            dir_success, dir_total = converter.convert_directory(dir_path, output_dir)
            total_dir_files += dir_total
            total_dir_success += dir_success
            
        if input_dirs:
            logger.info(f"Directory conversion completed: {total_dir_success}/{total_dir_files} files converted successfully")
            if total_dir_success < total_dir_files:
                sys.exit(1)
        
    except Exception as e:
        logger.error(f"Error: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    main()
