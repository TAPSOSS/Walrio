#!/usr/bin/env python3
"""
Image Converter - Convert and resize image files using ImageMagick
"""

import argparse
from pathlib import Path
import subprocess
import sys


class ImageConverter:
    """Converts and resizes images using ImageMagick"""
    
    FORMATS = ['jpg', 'jpeg', 'png', 'webp', 'gif', 'bmp', 'tiff']
    
    def __init__(self, output_format: str, max_size: int = None, quality: int = 90):
        """
        Args:
            output_format: Target format (jpg, png, webp, etc.)
            max_size: Maximum dimension in pixels
            quality: Output quality (1-100)
        """
        if output_format.lower() not in self.FORMATS:
            raise ValueError(f"Unsupported format: {output_format}")
        
        self.output_format = output_format.lower()
        self.max_size = max_size
        self.quality = quality
        self._check_convert()
    
    def _check_convert(self) -> None:
        """Check if ImageMagick is available"""
        try:
            subprocess.run(['convert', '-version'], capture_output=True, check=True)
        except (subprocess.CalledProcessError, FileNotFoundError):
            raise RuntimeError("ImageMagick not found. Install with: apt install imagemagick")
    
    def convert_file(self, input_path: Path, output_path: Path = None,
                    overwrite: bool = False) -> Path:
        """
        Convert image file
        
        Args:
            input_path: Input image
            output_path: Output path (auto-generated if None)
            overwrite: Overwrite existing files
            
        Returns:
            Path to output file
        """
        if not input_path.exists():
            raise FileNotFoundError(f"Input file not found: {input_path}")
        
        # Determine output path
        if output_path is None:
            output_path = input_path.with_suffix(f'.{self.output_format}')
        
        # Check if output exists
        if output_path.exists() and not overwrite:
            raise FileExistsError(f"Output exists: {output_path}")
        
        # Build ImageMagick command
        cmd = ['convert', str(input_path)]
        
        # Resize if requested
        if self.max_size:
            cmd.extend(['-resize', f'{self.max_size}x{self.max_size}>'])
        
        # Quality
        cmd.extend(['-quality', str(self.quality)])
        
        # Output
        cmd.append(str(output_path))
        
        # Execute
        try:
            subprocess.run(cmd, capture_output=True, text=True, check=True)
            return output_path
            
        except subprocess.CalledProcessError as e:
            raise RuntimeError(f"Conversion failed: {e.stderr}")
    
    def convert_directory(self, input_dir: Path, output_dir: Path = None,
                         recursive: bool = True, overwrite: bool = False) -> dict:
        """
        Convert all images in directory
        
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
        
        # Find image files
        image_exts = {'.jpg', '.jpeg', '.png', '.webp', '.gif', '.bmp', '.tiff', '.tif'}
        
        if recursive:
            pattern = '**/*'
        else:
            pattern = '*'
        
        files = []
        for ext in image_exts:
            files.extend(input_dir.glob(f'{pattern}{ext}'))
        
        # Convert each file
        stats = {'converted': 0, 'skipped': 0, 'errors': 0}
        
        for file_path in files:
            try:
                # Preserve directory structure
                rel_path = file_path.relative_to(input_dir)
                output_path = output_dir / rel_path.with_suffix(f'.{self.output_format}')
                output_path.parent.mkdir(parents=True, exist_ok=True)
                
                # Skip if same format and same location
                if (file_path.suffix.lower() == f'.{self.output_format}' and 
                    output_dir == input_dir):
                    stats['skipped'] += 1
                    continue
                
                self.convert_file(file_path, output_path, overwrite)
                print(f"Converted: {file_path} -> {output_path}")
                stats['converted'] += 1
                
            except Exception as e:
                print(f"Error converting {file_path}: {e}", file=sys.stderr)
                stats['errors'] += 1
        
        return stats


def convert_images(input_path: Path, output_format: str, output_path: Path = None,
                  max_size: int = None, quality: int = 90, recursive: bool = True,
                  overwrite: bool = False) -> dict:
    """
    Convert image file(s)
    
    Args:
        input_path: Input file or directory
        output_format: Target format
        output_path: Output path
        max_size: Maximum dimension
        quality: Output quality
        recursive: Process subdirectories
        overwrite: Overwrite existing
        
    Returns:
        Conversion statistics
    """
    converter = ImageConverter(output_format, max_size, quality)
    
    if input_path.is_dir():
        return converter.convert_directory(input_path, output_path, recursive, overwrite)
    else:
        converter.convert_file(input_path, output_path, overwrite)
        return {'converted': 1, 'skipped': 0, 'errors': 0}


def main():
    parser = argparse.ArgumentParser(
        description='Convert and resize images using ImageMagick'
    )
    parser.add_argument('input', type=Path, help='Input file or directory')
    parser.add_argument('format', choices=['jpg', 'jpeg', 'png', 'webp', 'gif', 'bmp', 'tiff'],
                       help='Target format')
    parser.add_argument('-o', '--output', type=Path, help='Output file or directory')
    parser.add_argument('-s', '--size', type=int, help='Maximum dimension in pixels')
    parser.add_argument('-q', '--quality', type=int, default=90,
                       help='Output quality 1-100 (default: 90)')
    parser.add_argument('-r', '--recursive', action='store_true',
                       help='Process subdirectories')
    parser.add_argument('-f', '--force', action='store_true',
                       help='Overwrite existing files')
    
    args = parser.parse_args()
    
    try:
        stats = convert_images(
            args.input,
            args.format,
            args.output,
            args.size,
            args.quality,
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
