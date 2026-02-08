#!/usr/bin/env python3
"""
Convert - Convert audio files between formats using FFmpeg
"""

import argparse
from pathlib import Path
import subprocess
import sys
import shutil


class AudioConverter:
    """Converts audio files using FFmpeg"""
    
    # Format configurations
    FORMATS = {
        'mp3': {'codec': 'libmp3lame', 'ext': '.mp3'},
        'flac': {'codec': 'flac', 'ext': '.flac'},
        'ogg': {'codec': 'libvorbis', 'ext': '.ogg'},
        'opus': {'codec': 'libopus', 'ext': '.opus'},
        'm4a': {'codec': 'aac', 'ext': '.m4a'},
        'aac': {'codec': 'aac', 'ext': '.m4a'},
        'alac': {'codec': 'alac', 'ext': '.m4a'},
        'wav': {'codec': 'pcm_s16le', 'ext': '.wav'},
        'wv': {'codec': 'wavpack', 'ext': '.wv'},
    }
    
    def __init__(self, output_format: str, preserve_metadata: bool = True,
                 bitrate: str = None, bit_depth: str = None, sample_rate: str = None,
                 delete_original: bool = False):
        """
        Args:
            output_format: Target format (mp3, flac, etc.)
            preserve_metadata: Preserve metadata tags
            bitrate: Bitrate for lossy formats (e.g., '320k')
            bit_depth: Bit depth for lossless formats ('16', '24', '32')
            sample_rate: Sample rate ('44100', '48000', '96000', '192000')
            delete_original: Delete original file after conversion
        """
        if output_format not in self.FORMATS:
            raise ValueError(f"Unsupported format: {output_format}")
        
        self.output_format = output_format
        self.preserve_metadata = preserve_metadata
        self.bitrate = bitrate
        self.bit_depth = bit_depth
        self.sample_rate = sample_rate
        self.delete_original = delete_original
        self.overwrite_all = False
        self.skip_all = False
        self._check_ffmpeg()
    
    def _check_ffmpeg(self) -> None:
        """Check if FFmpeg is available"""
        try:
            subprocess.run(['ffmpeg', '-version'], capture_output=True, check=True)
        except (subprocess.CalledProcessError, FileNotFoundError):
            raise RuntimeError("FFmpeg not found. Install with: apt install ffmpeg")
    
    def prompt_overwrite(self, filepath: Path) -> bool:
        """Prompt user for overwrite decision"""
        if self.overwrite_all:
            return True
        if self.skip_all:
            return False
        
        print(f"\nFile exists: {filepath.name}")
        while True:
            response = input("Overwrite? (y)es, (n)o, (ya) yes to all, (na) no to all: ").lower().strip()
            if response in ['y', 'yes']:
                return True
            elif response in ['n', 'no']:
                return False
            elif response in ['ya', 'yesall', 'yes to all']:
                self.overwrite_all = True
                return True
            elif response in ['na', 'noall', 'no to all']:
                self.skip_all = True
                return False
            else:
                print("Please enter 'y', 'n', 'ya', or 'na'")
    
    def convert_file(self, input_path: Path, output_path: Path = None,
                    force_overwrite: bool = False) -> Path:
        """
        Convert audio file
        
        Args:
            input_path: Input audio file
            output_path: Output path (auto-generated if None)
            force_overwrite: Force overwrite without prompting
            
        Returns:
            Path to output file
        """
        if not input_path.exists():
            raise FileNotFoundError(f"Input file not found: {input_path}")
        
        # Determine output path
        if output_path is None:
            format_config = self.FORMATS[self.output_format]
            output_path = input_path.with_suffix(format_config['ext'])
        
        # Check if already in target format
        if input_path.suffix.lower() == output_path.suffix.lower():
            if input_path == output_path:
                print(f"Skipping {input_path.name} (already in target format)")
                return input_path
        
        # Check if output exists and prompt if needed
        if output_path.exists() and not force_overwrite:
            if not self.prompt_overwrite(output_path):
                print(f"Skipped: {input_path.name}")
                return None
        
        # Build FFmpeg command
        format_config = self.FORMATS[self.output_format]
        cmd = ['ffmpeg', '-i', str(input_path)]
        
        # Overwrite flag
        if force_overwrite or self.overwrite_all:
            cmd.append('-y')
        
        # Codec
        cmd.extend(['-codec:a', format_config['codec']])
        
        # Sample rate
        if self.sample_rate:
            cmd.extend(['-ar', self.sample_rate])
        
        # Bit depth for lossless formats
        if self.bit_depth and self.output_format in ('flac', 'wav'):
            if self.bit_depth == '16':
                cmd.extend(['-sample_fmt', 's16'])
            elif self.bit_depth == '24':
                cmd.extend(['-sample_fmt', 's32'])
            elif self.bit_depth == '32':
                cmd.extend(['-sample_fmt', 's32'])
        
        # Bitrate for lossy formats
        if self.bitrate and self.output_format in ('mp3', 'aac', 'opus', 'ogg'):
            cmd.extend(['-b:a', self.bitrate])
        else:
            # Default quality settings
            if self.output_format == 'mp3':
                cmd.extend(['-q:a', '2'])  # VBR ~192kbps
            elif self.output_format == 'opus':
                cmd.extend(['-b:a', '128k'])
            elif self.output_format == 'ogg':
                cmd.extend(['-q:a', '6'])
            elif self.output_format == 'flac':
                cmd.extend(['-compression_level', '8'])
        
        # Metadata
        if self.preserve_metadata:
            cmd.extend(['-map_metadata', '0'])
        
        # Output
        cmd.append(str(output_path))
        
        # Execute
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=True
            )
            
            print(f"Converted: {input_path.name} -> {output_path.name}")
            
            # Delete original if requested
            if self.delete_original and output_path.exists() and input_path != output_path:
                try:
                    input_path.unlink()
                    print(f"  Deleted original: {input_path.name}")
                except Exception as e:
                    print(f"  Warning: Could not delete original: {e}")
            
            return output_path
            
        except subprocess.CalledProcessError as e:
            raise RuntimeError(f"Conversion failed: {e.stderr}")
    
    def convert_directory(self, input_dir: Path, output_dir: Path = None,
                         recursive: bool = True, force_overwrite: bool = False, skip_existing: bool = False) -> dict:
        """
        Convert all audio files in directory
        
        Args:
            input_dir: Input directory
            output_dir: Output directory (defaults to input_dir)
            recursive: Process subdirectories
            force_overwrite: Force overwrite without prompting
            skip_existing: Skip files that already exist
            
        Returns:
            Dictionary with conversion stats
        """
        if not input_dir.is_dir():
            raise NotADirectoryError(f"Not a directory: {input_dir}")
        
        output_dir = output_dir or input_dir
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # Find audio files
        audio_exts = {'.mp3', '.flac', '.ogg', '.opus', '.m4a', '.mp4', '.wav', '.wma', '.aac', '.wv', '.ape'}
        
        if recursive:
            pattern = '**/*'
        else:
            pattern = '*'
        
        files = []
        for ext in audio_exts:
            files.extend(input_dir.glob(f'{pattern}{ext}'))
        
        # Convert each file
        stats = {'converted': 0, 'skipped': 0, 'errors': 0}
        
        for file_path in files:
            try:
                # Preserve directory structure
                rel_path = file_path.relative_to(input_dir)
                output_path = output_dir / rel_path.with_suffix(
                    self.FORMATS[self.output_format]['ext']
                )
                output_path.parent.mkdir(parents=True, exist_ok=True)
                
                # Skip if already target format and same location
                if file_path.suffix.lower() == self.FORMATS[self.output_format]['ext']:
                    if output_dir == input_dir:
                        stats['skipped'] += 1
                        continue
                
                # Skip if exists and skip_existing is True
                if skip_existing and output_path.exists():
                    print(f"Skipped (exists): {file_path.name}")
                    stats['skipped'] += 1
                    continue
                
                result = self.convert_file(file_path, output_path, force_overwrite)
                if result:
                    stats['converted'] += 1
                else:
                    stats['skipped'] += 1
                
            except Exception as e:
                print(f"Error converting {file_path.name}: {e}", file=sys.stderr)
                stats['errors'] += 1
        
        return stats


def convert_audio(input_path: Path, output_format: str, output_path: Path = None,
                 recursive: bool = True, force_overwrite: bool = False, 
                 skip_existing: bool = False, quality: Optional[Union[int, str]] = None,
                 preserve_metadata: bool = True, bitrate: Optional[str] = None,
                 bit_depth: Optional[int] = None, sample_rate: Optional[int] = None,
                 delete_original: bool = False) -> dict:
    """
    Convert audio file(s)
    
    Args:
        input_path: Input file or directory
        output_format: Target format
        output_path: Output path
        recursive: Process subdirectories
        force_overwrite: Force overwrite without prompting
        skip_existing: Skip files that already exist
        quality: Quality setting
        preserve_metadata: Copy metadata tags
        bitrate: Target bitrate (e.g., '320k')
        bit_depth: Target bit depth (16/24/32 for FLAC/WAV)
        sample_rate: Target sample rate (e.g., 44100)
        delete_original: Delete original after conversion
        
    Returns:
        Conversion statistics
    """
    converter = AudioConverter(
        output_format, quality, preserve_metadata,
        bitrate=bitrate, bit_depth=bit_depth, 
        sample_rate=sample_rate, delete_original=delete_original
    )
    
    if input_path.is_dir():
        return converter.convert_directory(input_path, output_path, recursive, 
                                           force_overwrite, skip_existing)
    else:
        result = converter.convert_file(input_path, output_path, force_overwrite)
        return {'converted': 1 if result else 0, 'skipped': 0 if result else 1, 'errors': 0}


def main():
    parser = argparse.ArgumentParser(
        description='Convert audio files between formats using FFmpeg'
    )
    parser.add_argument('input', type=Path, help='Input file or directory')
    parser.add_argument('format', choices=['mp3', 'flac', 'ogg', 'opus', 'm4a', 'wav', 'aac', 'alac', 'wv'],
                       help='Target format')
    parser.add_argument('-o', '--output', type=Path, help='Output file or directory')
    parser.add_argument('-r', '--recursive', action='store_true', 
                       help='Process subdirectories')
    parser.add_argument('-f', '--force-overwrite', action='store_true',
                       help='Force overwrite without prompting')
    parser.add_argument('-s', '--skip-existing', action='store_true',
                       help='Skip files that already exist')
    parser.add_argument('-q', '--quality', help='Quality setting (format-specific)')
    parser.add_argument('--no-metadata', action='store_true',
                       help='Do not copy metadata tags')
    parser.add_argument('-b', '--bitrate', help='Target bitrate (e.g., 320k)')
    parser.add_argument('--bit-depth', type=int, choices=[16, 24, 32],
                       help='Target bit depth for FLAC/WAV (16/24/32)')
    parser.add_argument('--sample-rate', type=int,
                       help='Target sample rate (e.g., 44100, 48000)')
    parser.add_argument('-d', '--delete-original', action='store_true',
                       help='Delete original file after successful conversion')
    
    args = parser.parse_args()
    
    try:
        stats = convert_audio(
            args.input,
            args.format,
            args.output,
            args.recursive,
            args.force_overwrite,
            args.skip_existing,
            args.quality,
            not args.no_metadata,
            args.bitrate,
            args.bit_depth,
            args.sample_rate,
            args.delete_original
        )
        
        print(f"\nConversion complete:")
        print(f"  Converted: {stats['converted']}")
        print(f"  Skipped: {stats['skipped']}")
        if stats['errors']:
            print(f"  Errors: {stats['errors']}")
            return 1
        
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    
    return 0


if __name__ == '__main__':
    sys.exit(main())
