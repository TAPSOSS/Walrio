#!/usr/bin/env python3
"""
Image Converter - Convert and resize image files using ImageMagick
"""

import argparse
import logging
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)


def check_imagemagick() -> bool:
    """
    Check if ImageMagick is available
    
    Returns:
        True if available
    """
    try:
        result = subprocess.run(['convert', '-version'], 
                              capture_output=True, text=True, timeout=10)
        return result.returncode == 0
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return False


def get_supported_formats() -> Dict[str, str]:
    """
    Get supported image formats with descriptions
    
    Returns:
        Dictionary of format extensions and descriptions
    """
    return {
        'png': 'PNG - Portable Network Graphics (lossless)',
        'jpeg': 'JPEG - Joint Photographic Experts Group (lossy)',
        'jpg': 'JPG - JPEG alias (lossy)',
        'jxl': 'JXL - JPEG XL (lossy/lossless)',
        'webp': 'WebP - Google WebP format (lossy/lossless)',
        'bmp': 'BMP - Windows Bitmap (lossless)',
        'tiff': 'TIFF - Tagged Image File Format (lossless)',
        'tif': 'TIF - TIFF alias (lossless)',
        'gif': 'GIF - Graphics Interchange Format (lossless)',
        'ico': 'ICO - Windows Icon format',
        'svg': 'SVG - Scalable Vector Graphics',
        'pdf': 'PDF - Portable Document Format',
        'eps': 'EPS - Encapsulated PostScript',
        'psd': 'PSD - Adobe Photoshop Document'
    }


def validate_format(format_name: str) -> str:
    """
    Validate and normalize image format
    
    Args:
        format_name: Image format name
        
    Returns:
        Normalized format name
        
    Raises:
        ValueError: If format not supported
    """
    format_name = format_name.lower().lstrip('.')
    supported = get_supported_formats()
    
    if format_name not in supported:
        raise ValueError(f"Unsupported format: {format_name}. Supported: {', '.join(supported.keys())}")
    
    # Normalize format names
    if format_name == 'jpg':
        format_name = 'jpeg'
    elif format_name == 'tif':
        format_name = 'tiff'
    
    return format_name


def parse_size(size_str: str, force_stretch: bool = False) -> Tuple[Optional[str], bool]:
    """
    Parse size string into ImageMagick geometry format
    
    Supports:
    - 'WIDTHxHEIGHT' - Resize to fit within dimensions, maintaining aspect ratio
    - 'WIDTHxHEIGHT!' - Force exact dimensions, ignoring aspect ratio
    - 'WIDTHxHEIGHT>' - Only shrink larger images
    - 'WIDTHxHEIGHT<' - Only enlarge smaller images
    - 'WIDTH' - Set width, maintain aspect ratio
    - 'xHEIGHT' - Set height, maintain aspect ratio
    - 'N%' - Percentage scaling
    
    Args:
        size_str: Size string
        force_stretch: Force exact dimensions, ignoring aspect ratio
        
    Returns:
        Tuple of (geometry_string, maintain_aspect_ratio)
        
    Raises:
        ValueError: If size string invalid
    """
    if not size_str:
        return None, True
    
    # Check for percentage
    if size_str.endswith('%'):
        return size_str, True
    
    # Check for special suffixes
    suffix = ''
    if size_str.endswith(('>', '<', '!', '^', '#')):
        suffix = size_str[-1]
        size_str = size_str[:-1]
    
    # Parse dimensions
    if 'x' in size_str:
        parts = size_str.split('x', 1)
        width_str, height_str = parts[0], parts[1]
        
        if not width_str and not height_str:
            raise ValueError("Invalid size format. Use 'WIDTHxHEIGHT', 'WIDTH', or 'xHEIGHT'")
        
        # Build geometry string
        if force_stretch and width_str and height_str:
            geometry = f"{width_str}x{height_str}!"
            maintain_aspect = False
        else:
            geometry = f"{width_str}x{height_str}{suffix}"
            maintain_aspect = suffix != '!'
        
        return geometry, maintain_aspect
    else:
        # Single dimension - assume it's width, maintain aspect ratio
        return f"{size_str}x{suffix}", True


def get_image_info(image_path: Path) -> Optional[Dict[str, Any]]:
    """
    Get image information using ImageMagick identify
    
    Args:
        image_path: Path to image file
        
    Returns:
        Dictionary with image info or None on error
    """
    try:
        cmd = ['identify', '-format', '%w %h %m %Q %[colorspace] %[orientation] %b', str(image_path)]
        result = subprocess.run(cmd, capture_output=True, text=True, check=True, timeout=10)
        
        parts = result.stdout.strip().split()
        if len(parts) >= 4:
            return {
                'width': int(parts[0]),
                'height': int(parts[1]),
                'format': parts[2],
                'quality': parts[3] if len(parts) > 3 and parts[3] != '0' else 'N/A',
                'colorspace': parts[4] if len(parts) > 4 else 'Unknown',
                'orientation': parts[5] if len(parts) > 5 else 'Unknown',
                'size': parts[6] if len(parts) > 6 else 'Unknown'
            }
        return None
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, ValueError, IndexError):
        return None


def convert_image(input_path: Path, output_path: Path,
                 output_format: Optional[str] = None,
                 geometry: Optional[str] = None,
                 quality: int = 100,
                 auto_orient: bool = True,
                 strip_metadata: bool = False,
                 background_color: str = 'white',
                 current_file: Optional[int] = None,
                 total_files: Optional[int] = None) -> bool:
    """
    Convert and/or resize image using ImageMagick
    
    Args:
        input_path: Input image path
        output_path: Output image path
        output_format: Target format (inferred from output_path if None)
        geometry: ImageMagick geometry string (e.g., '800x800', '800x800!')
        quality: Output quality (1-100)
        auto_orient: Auto-orient based on EXIF orientation
        strip_metadata: Remove metadata from output
        background_color: Background color for transparent images
        current_file: Current file number for progress display
        total_files: Total number of files for progress display
        
    Returns:
        True if successful
    """
    if not input_path.exists():
        logger.error(f"Input file not found: {input_path}")
        return False
    
    # Display progress
    if current_file and total_files:
        print(f"\nFile {current_file}/{total_files}: Processing {input_path.name}")
    else:
        print(f"\nProcessing {input_path.name}")
    
    # Build command
    cmd = ['convert', str(input_path)]
    
    # Auto-orient
    if auto_orient:
        cmd.append('-auto-orient')
        print(f"  → Auto-orienting based on EXIF...")
    
    # Resize
    if geometry:
        cmd.extend(['-resize', geometry])
        print(f"  → Resizing to {geometry}...")
    
    # Background color (for transparent images)
    if background_color and output_format in ('jpeg', 'jpg', 'bmp'):
        cmd.extend(['-background', background_color])
        cmd.append('-flatten')
        print(f"  → Flattening transparency with {background_color} background...")
    
    # Quality
    cmd.extend(['-quality', str(quality)])
    
    # Strip metadata
    if strip_metadata:
        cmd.append('-strip')
        print(f"  → Stripping metadata...")
    
    # Output format
    if output_format:
        cmd.append(f"{validate_format(output_format).upper()}:{output_path}")
    else:
        cmd.append(str(output_path))
    
    try:
        print(f"  → Converting to {output_format or output_path.suffix.lstrip('.')}...")
        result = subprocess.run(cmd, capture_output=True, text=True, check=True, timeout=60)
        print(f"  ✓ Complete: Saved to {output_path.name}\n")
        logger.debug(f"Converted {input_path.name} to {output_path.name}")
        return True
    except subprocess.CalledProcessError as e:
        logger.error(f"ImageMagick conversion failed: {e.stderr}")
        return False
    except subprocess.TimeoutExpired:
        logger.error(f"Conversion timed out for {input_path}")
        return False


class ImageConverter:
    """
    Image converter with advanced size parsing and format support
    """
    
    def __init__(self, output_format: str = 'png', 
                 size: str = '1000x1000',
                 quality: int = 100,
                 force_stretch: bool = True,
                 auto_orient: bool = True,
                 strip_metadata: bool = False,
                 background_color: str = 'white'):
        """
        Args:
            output_format: Target format
            size: Size specification (e.g., '800x800', '800x800!', '50%')
            quality: Output quality (1-100)
            force_stretch: Force exact dimensions
            auto_orient: Auto-orient based on EXIF
            strip_metadata: Remove metadata
            background_color: Background color for transparency removal
        """
        self.output_format = validate_format(output_format)
        self.quality = quality
        self.force_stretch = force_stretch
        self.auto_orient = auto_orient
        self.strip_metadata = strip_metadata
        self.background_color = background_color
        self.size_str = size
        
        # Parse size
        self.geometry, self.maintain_aspect = parse_size(size, force_stretch)
        
        # Statistics
        self.processed_count = 0
        self.error_count = 0
        
        if not check_imagemagick():
            raise RuntimeError("ImageMagick not found. Install with: apt install imagemagick")
    
    def print_settings(self, output_dir: Optional[Path] = None):
        """Print conversion settings"""
        print("\n" + "=" * 60)
        print(f"Image Conversion Settings:")
        print(f"  Output Format: {self.output_format.upper()}")
        print(f"  Target Size: {self.size_str}")
        aspect_mode = "Force exact dimensions" if self.force_stretch else "Maintain aspect ratio"
        print(f"  Resize Mode: {aspect_mode}")
        print(f"  Quality: {self.quality}")
        print(f"  Auto-orient: {'Yes' if self.auto_orient else 'No'}")
        print(f"  Strip Metadata: {'Yes' if self.strip_metadata else 'No'}")
        print(f"  Background Color: {self.background_color}")
        if output_dir:
            print(f"  Output Directory: {output_dir}")
        print("=" * 60 + "\n")
    
    def convert_file(self, input_path: Path, output_path: Optional[Path] = None,
                    overwrite: bool = False, current_file: Optional[int] = None,
                    total_files: Optional[int] = None) -> Optional[Path]:
        """
        Convert single image file
        
        Args:
            input_path: Input image
            output_path: Output path (auto-generated if None)
            overwrite: Overwrite existing files
            current_file: Current file number for progress
            total_files: Total file count for progress
            
        Returns:
            Path to output file or None on failure
        """
        if not input_path.exists():
            logger.error(f"Input file not found: {input_path}")
            return None
        
        # Determine output path
        if output_path is None:
            output_path = input_path.with_suffix(f'.{self.output_format}')
        
        # Check if output exists
        if output_path.exists() and not overwrite:
            logger.warning(f"Output exists: {output_path} (use --overwrite to overwrite)")
            return None
        
        # Convert
        success = convert_image(
            input_path, output_path,
            output_format=self.output_format,
            geometry=self.geometry,
            quality=self.quality,
            auto_orient=self.auto_orient,
            strip_metadata=self.strip_metadata,
            background_color=self.background_color,
            current_file=current_file,
            total_files=total_files
        )
        
        if success:
            self.processed_count += 1
        else:
            self.error_count += 1
        
        return output_path if success else None
    
    def convert_directory(self, input_dir: Path, output_dir: Optional[Path] = None,
                         recursive: bool = False, overwrite: bool = False) -> Dict[str, int]:
        """
        Convert all images in directory
        
        Args:
            input_dir: Input directory
            output_dir: Output directory (defaults to input_dir)
            recursive: Process subdirectories
            overwrite: Overwrite existing files
            
        Returns:
            Statistics dictionary
        """
        if not input_dir.is_dir():
            raise NotADirectoryError(f"Not a directory: {input_dir}")
        
        output_dir = output_dir or input_dir
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # Find image files
        image_exts = {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.tiff', '.tif', 
                     '.webp', '.jxl', '.svg', '.ico', '.pdf', '.eps', '.psd'}
        
        if recursive:
            files = []
            for ext in image_exts:
                files.extend(input_dir.rglob(f'*{ext}'))
        else:
            files = []
            for ext in image_exts:
                files.extend(input_dir.glob(f'*{ext}'))
        
        if not files:
            logger.warning(f"No image files found in {input_dir}")
            return {'converted': 0, 'skipped': 0, 'errors': 0}
        
        # Print settings
        self.print_settings(output_dir)
        print(f"Found {len(files)} image file(s) to process\n")
        
        # Convert each file
        stats = {'converted': 0, 'skipped': 0, 'errors': 0}
        
        for i, file_path in enumerate(files, 1):
            try:
                # Preserve directory structure
                rel_path = file_path.relative_to(input_dir)
                output_path = output_dir / rel_path.with_suffix(f'.{self.output_format}')
                output_path.parent.mkdir(parents=True, exist_ok=True)
                
                result = self.convert_file(file_path, output_path, overwrite, 
                                          current_file=i, total_files=len(files))
                if result:
                    stats['converted'] += 1
                else:
                    stats['skipped'] += 1
                
            except Exception as e:
                logger.error(f"Error converting {file_path.name}: {e}")
                stats['errors'] += 1
        
        return stats


def main():
    parser = argparse.ArgumentParser(
        description='Image Converter - Convert images between different formats and sizes using ImageMagick',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Convert single image to 1000x1000 PNG with quality 100 (defaults)
  %(prog)s image.png

  # Convert to JXL with lossy compression for smaller file size
  %(prog)s image.png --format jxl --quality 90

  # Convert to different format, keeping default 1000x1000 size
  %(prog)s image.png --format webp

  # Convert with custom dimensions (forced exact size by default)
  %(prog)s image.png --size 800x600

  # Convert maintaining aspect ratio instead of stretching
  %(prog)s image.png --size 800x600 --no-force-stretch

  # Convert and resize by percentage
  %(prog)s image.png --size 50%%

  # Batch convert all images in directory to default 1000x1000 PNG
  %(prog)s /path/to/images --recursive

  # Convert with custom quality and strip metadata
  %(prog)s image.jpg --quality 80 --strip-metadata

  # Get image information
  %(prog)s image.jpg --info

Supported formats: {}

Note: By default, images are forced to exact dimensions (e.g., 800x600 stretches if needed).
Use --no-force-stretch to maintain aspect ratio and fit within dimensions instead.

Quality Modes:
  Quality 100 (default) - Best quality, lossless for formats that support it
  Quality 90-99        - High quality, good balance for most uses
  Quality 70-89        - Good quality, smaller file sizes
  Quality < 70         - Lower quality, smallest file sizes

ImageMagick geometry examples:
  800x600   - Exact 800x600 (with --force-stretch, default)
  800x600   - Fit within 800x600 (with --no-force-stretch)
  800x600!  - Force exact size regardless of --force-stretch flag
  800x600>  - Only shrink if larger than 800x600
  800x600<  - Only enlarge if smaller than 800x600
  50%%      - Resize to 50%% of original size
        """.format(', '.join(get_supported_formats().keys()))
    )
    
    parser.add_argument('input', nargs='*', help='Input image file(s) or directory')
    parser.add_argument('-f', '--format', default='png', help='Output format (default: png)')
    parser.add_argument('-o', '--output', help='Output file or directory (auto-generated if not specified)')
    parser.add_argument('-s', '--size', default='1000x1000', help='Target size using ImageMagick geometry (default: 1000x1000)')
    parser.add_argument('-q', '--quality', type=int, default=100, help='Quality (1-100, default: 100)')
    parser.add_argument('--force-stretch', action='store_true', default=True, help='Force exact dimensions (default: True)')
    parser.add_argument('--no-force-stretch', action='store_true', help='Maintain aspect ratio instead of forcing exact dimensions')
    parser.add_argument('--no-auto-orient', action='store_true', help='Disable auto-orientation based on EXIF')
    parser.add_argument('--strip-metadata', action='store_true', help='Remove EXIF metadata from images')
    parser.add_argument('--background', default='white', help='Background color for transparency removal (default: white)')
    parser.add_argument('--overwrite', action='store_true', default=False, help='Overwrite existing output files (default: False)')
    parser.add_argument('-r', '--recursive', action='store_true', default=False, help='Process directories recursively (default: False)')
    parser.add_argument('--info', action='store_true', help='Show image information and exit')
    parser.add_argument('--list-formats', action='store_true', help='List supported formats and exit')
    
    args = parser.parse_args()
    
    # List formats and exit
    if args.list_formats:
        print("Supported image formats:")
        for fmt, desc in get_supported_formats().items():
            print(f"  {fmt:<6} - {desc}")
        return 0
    
    # Check for input files
    if not args.input and not args.info:
        logger.error("Input files or directories are required")
        return 1
    
    # Validate quality
    if not 1 <= args.quality <= 100:
        logger.error("Quality must be between 1 and 100")
        return 1
    
    # Determine stretch mode
    force_stretch = args.force_stretch and not args.no_force_stretch
    
    # Validate format
    try:
        output_format = validate_format(args.format)
    except ValueError as e:
        logger.error(str(e))
        return 1
    
    # Collect input files
    input_files = []
    input_dirs = []
    
    for input_path_str in args.input:
        input_path = Path(input_path_str)
        if input_path.is_file():
            input_files.append(input_path)
        elif input_path.is_dir():
            input_dirs.append(input_path)
        else:
            logger.warning(f"Input path does not exist: {input_path}")
    
    # Show image info and exit
    if args.info:
        for input_path in input_files:
            info = get_image_info(input_path)
            if info:
                print(f"\n{input_path}:")
                print(f"  Format: {info['format']}")
                print(f"  Dimensions: {info['width']}x{info['height']}")
                print(f"  Quality: {info['quality']}")
                print(f"  Colorspace: {info['colorspace']}")
                print(f"  Orientation: {info['orientation']}")
                print(f"  File size: {info['size']}")
            else:
                print(f"\n{input_path}: Unable to get image information")
        return 0
    
    if not input_files and not input_dirs:
        logger.error("No valid input files or directories found")
        return 1
    
    try:
        converter = ImageConverter(
            output_format=output_format,
            size=args.size,
            quality=args.quality,
            force_stretch=force_stretch,
            auto_orient=not args.no_auto_orient,
            strip_metadata=args.strip_metadata,
            background_color=args.background
        )
        
        total_converted = 0
        total_skipped = 0
        total_errors = 0
        
        # Process directories
        for input_dir in input_dirs:
            output_dir = Path(args.output) if args.output else input_dir
            stats = converter.convert_directory(input_dir, output_dir, args.recursive, args.overwrite)
            total_converted += stats['converted']
            total_skipped += stats['skipped']
            total_errors += stats['errors']
        
        # Process individual files
        if input_files:
            # Determine output handling
            if args.output:
                output_path = Path(args.output)
                if len(input_files) == 1 and not output_path.is_dir():
                    # Single file to specific output
                    converter.print_settings()
                    print(f"Found 1 image file to process\n")
                    result = converter.convert_file(input_files[0], output_path, args.overwrite)
                    if result:
                        total_converted += 1
                    else:
                        total_errors += 1
                else:
                    # Multiple files or directory output
                    output_path.mkdir(parents=True, exist_ok=True)
                    converter.print_settings(output_path)
                    print(f"Found {len(input_files)} image file(s) to process\n")
                    
                    for i, input_file in enumerate(input_files, 1):
                        out_file = output_path / f"{input_file.stem}.{output_format}"
                        result = converter.convert_file(input_file, out_file, args.overwrite,
                                                       current_file=i, total_files=len(input_files))
                        if result:
                            total_converted += 1
                        else:
                            total_errors += 1
            else:
                # In-place conversion
                converter.print_settings()
                print(f"Found {len(input_files)} image file(s) to process\n")
                
                for i, input_file in enumerate(input_files, 1):
                    output_path = input_file.with_suffix(f'.{output_format}')
                    result = converter.convert_file(input_file, output_path, args.overwrite,
                                                   current_file=i, total_files=len(input_files))
                    if result:
                        total_converted += 1
                    else:
                        total_errors += 1
        
        # Print summary
        print(f"\nConversion completed:")
        print(f"  Successful: {total_converted}")
        if total_skipped > 0:
            print(f"  Skipped: {total_skipped}")
        if total_errors > 0:
            print(f"  Errors: {total_errors}")
            return 1
        
        return 0
        
    except Exception as e:
        logger.error(f"Error: {e}")
        return 1


if __name__ == '__main__':
    sys.exit(main())
