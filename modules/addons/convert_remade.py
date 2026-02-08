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
        'mp3': {'codec': 'libmp3lame', 'ext': '.mp3', 'quality': ['-q:a', '2']},
        'flac': {'codec': 'flac', 'ext': '.flac', 'quality': ['-compression_level', '8']},
        'ogg': {'codec': 'libvorbis', 'ext': '.ogg', 'quality': ['-q:a', '6']},
        'opus': {'codec': 'libopus', 'ext': '.opus', 'quality': ['-b:a', '128k']},
        'm4a': {'codec': 'aac', 'ext': '.m4a', 'quality': ['-q:a', '2']},
        'wav': {'codec': 'pcm_s16le', 'ext': '.wav', 'quality': []},
    }
    
    def __init__(self, output_format: str, preserve_metadata: bool = True):
        """
        Args:
            output_format: Target format (mp3, flac, etc.)
            preserve_metadata: Preserve metadata tags
        """
        if output_format not in self.FORMATS:
            raise ValueError(f"Unsupported format: {output_format}")
        
        self.output_format = output_format
        self.preserve_metadata = preserve_metadata
        self._check_ffmpeg()
    
    def _check_ffmpeg(self) -> None:
        """Check if FFmpeg is available"""
        try:
            subprocess.run(['ffmpeg', '-version'], capture_output=True, check=True)
        except (subprocess.CalledProcessError, FileNotFoundError):
            raise RuntimeError("FFmpeg not found. Install with: apt install ffmpeg")
    
    def convert_file(self, input_path: Path, output_path: Path = None,
                    overwrite: bool = False) -> Path:
        """
        Convert audio file
        
        Args:
            input_path: Input audio file
            output_path: Output path (auto-generated if None)
            overwrite: Overwrite existing files
            
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
                print(f"Skipping {input_path} (already in target format)")
                return input_path
        
        # Check if output exists
        if output_path.exists() and not overwrite:
            raise FileExistsError(f"Output exists: {output_path}")
        
        # Build FFmpeg command
        format_config = self.FORMATS[self.output_format]
        cmd = ['ffmpeg', '-i', str(input_path)]
        
        # Overwrite flag
        if overwrite:
            cmd.append('-y')
        
        # Codec
        cmd.extend(['-codec:a', format_config['codec']])
        
        # Quality
        cmd.extend(format_config['quality'])
        
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
            return output_path
            
        except subprocess.CalledProcessError as e:
            raise RuntimeError(f"Conversion failed: {e.stderr}")
    
    def convert_directory(self, input_dir: Path, output_dir: Path = None,
                         recursive: bool = True, overwrite: bool = False) -> dict:
        """
        Convert all audio files in directory
        
        Args:
            input_dir: Input directory
            output_dir: Output directory (defaults to input_dir)
            recursive: Process subdirectories
            overwrite: Overwrite existing files
            
        Returns:
            Dictionary with conversion stats
        """
        if not input_dir.is_dir():
            raise NotADirectoryError(f"Not a directory: {input_dir}")
        
        output_dir = output_dir or input_dir
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # Find audio files
        audio_exts = {'.mp3', '.flac', '.ogg', '.opus', '.m4a', '.mp4', '.wav', '.wma', '.aac'}
        
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
                
                # Skip if already target format
                if file_path.suffix.lower() == self.FORMATS[self.output_format]['ext']:
                    if output_dir == input_dir:
                        stats['skipped'] += 1
                        continue
                
                self.convert_file(file_path, output_path, overwrite)
                print(f"Converted: {file_path} -> {output_path}")
                stats['converted'] += 1
                
            except Exception as e:
                print(f"Error converting {file_path}: {e}", file=sys.stderr)
                stats['errors'] += 1
        
        return stats


def convert_audio(input_path: Path, output_format: str, output_path: Path = None,
                 recursive: bool = True, overwrite: bool = False) -> dict:
    """
    Convert audio file(s)
    
    Args:
        input_path: Input file or directory
        output_format: Target format
        output_path: Output path
        recursive: Process subdirectories
        overwrite: Overwrite existing
        
    Returns:
        Conversion statistics
    """
    converter = AudioConverter(output_format)
    
    if input_path.is_dir():
        return converter.convert_directory(input_path, output_path, recursive, overwrite)
    else:
        converter.convert_file(input_path, output_path, overwrite)
        return {'converted': 1, 'skipped': 0, 'errors': 0}


def main():
    parser = argparse.ArgumentParser(
        description='Convert audio files between formats using FFmpeg'
    )
    parser.add_argument('input', type=Path, help='Input file or directory')
    parser.add_argument('format', choices=['mp3', 'flac', 'ogg', 'opus', 'm4a', 'wav'],
                       help='Target format')
    parser.add_argument('-o', '--output', type=Path, help='Output file or directory')
    parser.add_argument('-r', '--recursive', action='store_true', 
                       help='Process subdirectories')
    parser.add_argument('-f', '--force', action='store_true',
                       help='Overwrite existing files')
    
    args = parser.parse_args()
    
    try:
        stats = convert_audio(
            args.input,
            args.format,
            args.output,
            args.recursive,
            args.force
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
