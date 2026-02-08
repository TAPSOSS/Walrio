#!/usr/bin/env python3
"""
Apply Loudness - Apply loudness normalization to audio files using FFmpeg
"""

import argparse
from pathlib import Path
import subprocess
import sys
import json
import tempfile


class LoudnessNormalizer:
    """Applies loudness normalization using FFmpeg"""
    
    def __init__(self, target_loudness: float = -14.0, dual_pass: bool = True):
        """
        Args:
            target_loudness: Target loudness in LUFS (default: -14.0)
            dual_pass: Use dual-pass normalization for better quality
        """
        self.target_loudness = target_loudness
        self.dual_pass = dual_pass
        self._check_ffmpeg()
    
    def _check_ffmpeg(self) -> None:
        """Check if FFmpeg is available"""
        try:
            result = subprocess.run(
                ['ffmpeg', '-version'],
                capture_output=True,
                check=True
            )
        except (subprocess.CalledProcessError, FileNotFoundError):
            raise RuntimeError("FFmpeg not found. Install with: apt install ffmpeg")
    
    def measure_loudness(self, file_path: Path) -> dict:
        """
        Measure loudness of audio file
        
        Args:
            file_path: Audio file path
            
        Returns:
            Dictionary with loudness measurements
        """
        cmd = [
            'ffmpeg', '-i', str(file_path),
            '-af', 'loudnorm=print_format=json',
            '-f', 'null', '-'
        ]
        
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=False  # Don't check return code, FFmpeg returns error but we just need stderr
            )
            
            # Parse JSON from stderr
            output = result.stderr
            
            # Extract JSON (it's at the end of stderr)
            json_start = output.rfind('[Parsed_loudnorm')
            if json_start == -1:
                raise RuntimeError("Could not parse loudness data")
            
            json_start = output.find('{', json_start)
            json_end = output.rfind('}') + 1
            
            if json_start == -1 or json_end == 0:
                raise RuntimeError("Could not parse loudness data")
            
            json_str = output[json_start:json_end]
            data = json.loads(json_str)
            
            return {
                'input_i': float(data.get('input_i', 0)),
                'input_tp': float(data.get('input_tp', 0)),
                'input_lra': float(data.get('input_lra', 0)),
                'input_thresh': float(data.get('input_thresh', 0)),
                'target_offset': float(data.get('target_offset', 0))
            }
            
        except Exception as e:
            raise RuntimeError(f"Failed to measure loudness: {e}")
    
    def normalize_file(self, input_path: Path, output_path: Path = None,
                      overwrite: bool = False) -> Path:
        """
        Normalize audio file loudness
        
        Args:
            input_path: Input audio file
            output_path: Output path (defaults to input with _normalized suffix)
            overwrite: Overwrite existing files
            
        Returns:
            Path to output file
        """
        if not input_path.exists():
            raise FileNotFoundError(f"Input file not found: {input_path}")
        
        # Determine output path
        if output_path is None:
            stem = input_path.stem
            output_path = input_path.with_stem(f"{stem}_normalized")
        
        # Check if output exists
        if output_path.exists() and not overwrite:
            raise FileExistsError(f"Output exists: {output_path}")
        
        if self.dual_pass:
            # First pass: measure
            measurements = self.measure_loudness(input_path)
            
            # Second pass: normalize with measurements
            filter_str = (
                f"loudnorm=linear=true:i={self.target_loudness}:"
                f"lra=7:tp=-2:"
                f"measured_I={measurements['input_i']}:"
                f"measured_LRA={measurements['input_lra']}:"
                f"measured_tp={measurements['input_tp']}:"
                f"measured_thresh={measurements['input_thresh']}"
            )
        else:
            # Single pass
            filter_str = f"loudnorm=i={self.target_loudness}:lra=7:tp=-2"
        
        # Build FFmpeg command
        cmd = [
            'ffmpeg', '-i', str(input_path),
            '-af', filter_str,
            '-ar', '48000'  # Standard sample rate
        ]
        
        if overwrite:
            cmd.append('-y')
        
        cmd.append(str(output_path))
        
        # Execute
        try:
            subprocess.run(cmd, capture_output=True, text=True, check=True)
            return output_path
            
        except subprocess.CalledProcessError as e:
            raise RuntimeError(f"Normalization failed: {e.stderr}")
    
    def normalize_directory(self, input_dir: Path, output_dir: Path = None,
                           recursive: bool = True, overwrite: bool = False,
                           in_place: bool = False) -> dict:
        """
        Normalize all audio files in directory
        
        Args:
            input_dir: Input directory
            output_dir: Output directory (defaults to input_dir)
            recursive: Process subdirectories
            overwrite: Overwrite existing files
            in_place: Normalize in place (replace originals)
            
        Returns:
            Dictionary with normalization stats
        """
        if not input_dir.is_dir():
            raise NotADirectoryError(f"Not a directory: {input_dir}")
        
        output_dir = output_dir or input_dir
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # Find audio files
        audio_exts = {'.mp3', '.flac', '.ogg', '.opus', '.m4a', '.mp4', '.wav'}
        
        if recursive:
            pattern = '**/*'
        else:
            pattern = '*'
        
        files = []
        for ext in audio_exts:
            files.extend(input_dir.glob(f'{pattern}{ext}'))
        
        # Normalize each file
        stats = {'normalized': 0, 'errors': 0}
        
        for file_path in files:
            try:
                # Preserve directory structure
                rel_path = file_path.relative_to(input_dir)
                
                if in_place:
                    # Use temp file then replace
                    with tempfile.NamedTemporaryFile(
                        suffix=file_path.suffix,
                        delete=False
                    ) as tmp:
                        temp_path = Path(tmp.name)
                    
                    self.normalize_file(file_path, temp_path, True)
                    temp_path.replace(file_path)
                    output_path = file_path
                else:
                    stem = file_path.stem
                    output_path = output_dir / rel_path.with_stem(f"{stem}_normalized")
                    output_path.parent.mkdir(parents=True, exist_ok=True)
                    self.normalize_file(file_path, output_path, overwrite)
                
                print(f"Normalized: {file_path} -> {output_path}")
                stats['normalized'] += 1
                
            except Exception as e:
                print(f"Error normalizing {file_path}: {e}", file=sys.stderr)
                stats['errors'] += 1
        
        return stats


def apply_loudness(input_path: Path, target_loudness: float = -14.0,
                  output_path: Path = None, dual_pass: bool = True,
                  recursive: bool = True, overwrite: bool = False,
                  in_place: bool = False) -> dict:
    """
    Apply loudness normalization
    
    Args:
        input_path: Input file or directory
        target_loudness: Target loudness in LUFS
        output_path: Output path
        dual_pass: Use dual-pass normalization
        recursive: Process subdirectories
        overwrite: Overwrite existing
        in_place: Replace originals
        
    Returns:
        Normalization statistics
    """
    normalizer = LoudnessNormalizer(target_loudness, dual_pass)
    
    if input_path.is_dir():
        return normalizer.normalize_directory(
            input_path, output_path, recursive, overwrite, in_place
        )
    else:
        normalizer.normalize_file(input_path, output_path, overwrite)
        return {'normalized': 1, 'errors': 0}


def main():
    parser = argparse.ArgumentParser(
        description='Apply loudness normalization to audio files'
    )
    parser.add_argument('input', type=Path, help='Input file or directory')
    parser.add_argument('-o', '--output', type=Path, help='Output file or directory')
    parser.add_argument('-t', '--target', type=float, default=-14.0,
                       help='Target loudness in LUFS (default: -14.0)')
    parser.add_argument('-s', '--single-pass', action='store_true',
                       help='Use single-pass (faster but lower quality)')
    parser.add_argument('-r', '--recursive', action='store_true',
                       help='Process subdirectories')
    parser.add_argument('-f', '--force', action='store_true',
                       help='Overwrite existing files')
    parser.add_argument('-i', '--in-place', action='store_true',
                       help='Normalize in place (replace originals)')
    
    args = parser.parse_args()
    
    try:
        stats = apply_loudness(
            args.input,
            args.target,
            args.output,
            not args.single_pass,
            args.recursive,
            args.force,
            args.in_place
        )
        
        print(f"\nNormalization complete:")
        print(f"  Normalized: {stats['normalized']}")
        if stats['errors']:
            print(f"  Errors: {stats['errors']}")
            return 1
        
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    
    return 0


if __name__ == '__main__':
    sys.exit(main())
