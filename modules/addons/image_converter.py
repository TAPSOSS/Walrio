#!/usr/bin/env python3
"""
Image Converter
Copyright (c) 2025 TAPS OSS
Project: https://github.com/TAPSOSS/Walrio
Licensed under the BSD-3-Clause License (see LICENSE file for details)

A utility for converting images between different formats and resizing them using ImageMagick.
Supports common image formats like JPEG, PNG, WebP, BMP, TIFF, and GIF.
Provides options for quality control, size adjustment, and batch processing.
"""

import os
import sys
import argparse
import logging
import subprocess
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple


def setup_logging(level: str = "INFO") -> logging.Logger:
    """
    Set up logging configuration.
    
    Args:
        level (str): Logging level ('DEBUG', 'INFO', 'WARNING', 'ERROR')
        
    Returns:
        logging.Logger: Configured logger instance
    """
    log_level = getattr(logging, level.upper(), logging.INFO)
    logging.basicConfig(
        level=log_level,
        format='%(asctime)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    return logging.getLogger(__name__)


def check_imagemagick() -> bool:
    """
    Check if ImageMagick is available on the system.
    
    Returns:
        bool: True if ImageMagick is available, False otherwise
    """
    try:
        result = subprocess.run(['convert', '-version'], 
                              capture_output=True, text=True, timeout=10)
        return result.returncode == 0
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return False


def get_supported_formats() -> Dict[str, str]:
    """
    Get supported image formats with descriptions.
    
    Returns:
        dict: Dictionary of format extensions and their descriptions
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
    Validate and normalize image format.
    
    Args:
        format_name (str): Image format name
        
    Returns:
        str: Normalized format name
        
    Raises:
        ValueError: If format is not supported
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
    Parse size string into ImageMagick geometry format.
    
    Args:
        size_str (str): Size string in format 'WIDTHxHEIGHT', 'WIDTH', or 'xHEIGHT'
        force_stretch (bool): Force exact dimensions, ignoring aspect ratio
        
    Returns:
        tuple: (geometry_string, maintain_aspect_ratio)
        
    Raises:
        ValueError: If size string is invalid
    """
    if not size_str:
        return None, True
    
    # Check for percentage
    if size_str.endswith('%'):
        return size_str, True
    
    # Parse dimensions
    if 'x' in size_str:
        parts = size_str.split('x', 1)
        width_str, height_str = parts[0], parts[1]
        
        if not width_str and not height_str:
            raise ValueError("Invalid size format. Use 'WIDTHxHEIGHT', 'WIDTH', or 'xHEIGHT'")
        
        # ImageMagick geometry: WIDTHxHEIGHT! forces exact size (ignores aspect ratio)
        if force_stretch and width_str and height_str:
            geometry = f"{width_str}x{height_str}!"
            maintain_aspect = False
        else:
            geometry = f"{width_str}x{height_str}"
            maintain_aspect = True
        
        return geometry, maintain_aspect
    else:
        # Single dimension - assume it's width, maintain aspect ratio
        return f"{size_str}x", True


def get_image_info(image_path: str) -> Optional[Dict[str, Any]]:
    """
    Get information about an image using ImageMagick identify command.
    
    Args:
        image_path (str): Path to the image file
        
    Returns:
        dict or None: Image information or None if error
    """
    logger = logging.getLogger(__name__)
    
    try:
        cmd = [
            'identify',
            '-format', '%w %h %m %Q %[colorspace] %[orientation]',
            image_path
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        
        if result.returncode != 0:
            logger.error(f"Error getting image info: {result.stderr}")
            return None
        
        parts = result.stdout.strip().split()
        if len(parts) >= 4:
            return {
                'width': int(parts[0]),
                'height': int(parts[1]),
                'format': parts[2],
                'quality': parts[3] if parts[3] != '0' else 'N/A',
                'colorspace': parts[4] if len(parts) > 4 else 'Unknown',
                'orientation': parts[5] if len(parts) > 5 else 'Unknown'
            }
        
        return None
        
    except (subprocess.TimeoutExpired, ValueError, IndexError) as e:
        logger.error(f"Error getting image info for {image_path}: {e}")
        return None


def convert_image(input_path: str, 
                 output_path: str = None,
                 output_format: str = None,
                 geometry: str = None,
                 quality: int = 100,
                 auto_orient: bool = True,
                 strip_metadata: bool = False,
                 background_color: str = "white") -> bool:
    """
    Convert a single image file using ImageMagick.
    
    Args:
        input_path (str): Path to input image file
        output_path (str, optional): Path for output file (auto-generated if None)
        output_format (str, optional): Output format (detected from extension if None)
        geometry (str, optional): ImageMagick geometry string for resizing
        quality (int): JPEG/WebP quality (1-100, only for lossy formats)
        auto_orient (bool): Auto-rotate based on EXIF orientation
        strip_metadata (bool): Remove EXIF metadata
        background_color (str): Background color for transparency removal
        
    Returns:
        bool: True if conversion successful, False otherwise
    """
    logger = logging.getLogger(__name__)
    
    try:
        # Validate input file
        if not os.path.isfile(input_path):
            logger.error(f"Input file does not exist: {input_path}")
            return False
        
        # Determine output path and format
        if output_path is None:
            input_stem = Path(input_path).stem
            output_format = output_format or 'png'
            output_path = f"{input_stem}_converted.{output_format}"
        
        if output_format is None:
            output_format = Path(output_path).suffix.lstrip('.').lower()
        
        output_format = validate_format(output_format)
        
        # Build ImageMagick command
        cmd = ['convert', input_path]
        
        # Auto-orient based on EXIF
        if auto_orient:
            cmd.append('-auto-orient')
        
        # Strip metadata if requested
        if strip_metadata:
            cmd.append('-strip')
        
        # Resize if geometry specified
        if geometry:
            cmd.extend(['-resize', geometry])
        
        # Handle transparency for formats that don't support it
        if output_format in ('jpeg', 'bmp'):
            cmd.extend(['-background', background_color, '-flatten'])
        
        # Set quality for lossy formats
        if output_format in ('jpeg', 'webp', 'jxl'):
            cmd.extend(['-quality', str(quality)])
        
        # Set output format and path
        cmd.append(f"{output_format.upper()}:{output_path}")
        
        # Execute conversion
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        
        if result.returncode != 0:
            logger.error(f"ImageMagick conversion failed: {result.stderr}")
            return False
        
        logger.info(f"Converted: {input_path} -> {output_path}")
        return True
        
    except subprocess.TimeoutExpired:
        logger.error(f"Conversion timeout for {input_path}")
        return False
    except Exception as e:
        logger.error(f"Error converting {input_path}: {e}")
        return False


def convert_batch(input_paths: List[str],
                 output_dir: str = None,
                 output_format: str = 'png',
                 geometry: str = None,
                 quality: int = 100,
                 auto_orient: bool = True,
                 strip_metadata: bool = False,
                 background_color: str = "white",
                 overwrite: bool = False) -> Tuple[int, int]:
    """
    Convert multiple images in batch using ImageMagick.
    
    Args:
        input_paths (list): List of input image file paths
        output_dir (str, optional): Output directory (same as input if None)
        output_format (str): Output format for all images
        geometry (str, optional): ImageMagick geometry string for resizing
        quality (int): JPEG/WebP quality (1-100, only for lossy formats)
        auto_orient (bool): Auto-rotate based on EXIF orientation
        strip_metadata (bool): Remove EXIF metadata
        background_color (str): Background color for transparency removal
        overwrite (bool): Overwrite existing output files
        
    Returns:
        tuple: (successful_count, total_count)
    """
    logger = logging.getLogger(__name__)
    
    successful = 0
    total = len(input_paths)
    
    # Validate output format
    try:
        output_format = validate_format(output_format)
    except ValueError as e:
        logger.error(str(e))
        return 0, total
    
    # Create output directory if specified
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)
    
    for input_path in input_paths:
        try:
            # Generate output path
            input_file = Path(input_path)
            
            if output_dir:
                output_path = os.path.join(output_dir, f"{input_file.stem}.{output_format}")
            else:
                output_path = str(input_file.with_suffix(f".{output_format}"))
            
            # Check if output exists
            if os.path.exists(output_path) and not overwrite:
                logger.warning(f"Output file exists, skipping: {output_path}")
                continue
            
            # Convert image
            if convert_image(
                input_path=input_path,
                output_path=output_path,
                output_format=output_format,
                geometry=geometry,
                quality=quality,
                auto_orient=auto_orient,
                strip_metadata=strip_metadata,
                background_color=background_color
            ):
                successful += 1
                
        except Exception as e:
            logger.error(f"Error processing {input_path}: {e}")
    
    logger.info(f"Batch conversion complete: {successful}/{total} successful")
    return successful, total


def scan_directory(directory: str, recursive: bool = False) -> List[str]:
    """
    Scan directory for image files.
    
    Args:
        directory (str): Directory path to scan
        recursive (bool): Scan subdirectories recursively
        
    Returns:
        list: List of image file paths
    """
    logger = logging.getLogger(__name__)
    
    image_extensions = {'.jpg', '.jpeg', '.png', '.webp', '.bmp', '.tiff', '.tif', 
                       '.gif', '.ico', '.svg', '.pdf', '.eps', '.psd'}
    image_files = []
    
    try:
        if recursive:
            for root, _, files in os.walk(directory):
                for file in files:
                    if Path(file).suffix.lower() in image_extensions:
                        image_files.append(os.path.join(root, file))
        else:
            for file in os.listdir(directory):
                file_path = os.path.join(directory, file)
                if os.path.isfile(file_path) and Path(file).suffix.lower() in image_extensions:
                    image_files.append(file_path)
        
        logger.info(f"Found {len(image_files)} image files in {directory}")
        return sorted(image_files)
        
    except Exception as e:
        logger.error(f"Error scanning directory {directory}: {e}")
        return []


def parse_arguments():
    """
    Parse command line arguments.
    
    Returns:
        argparse.Namespace: Parsed arguments
    """
    parser = argparse.ArgumentParser(
        description="Image Converter - Convert images between different formats and sizes using ImageMagick",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Convert single image to 1000x1000 PNG lossless (default behavior)
  python imageconverter.py image.png

  # Convert to JXL with lossy compression for smaller file size
  python imageconverter.py image.png --format jxl --quality 90

  # Convert to different format, keeping default 1000x1000 size
  python imageconverter.py image.png --format webp

  # Convert with custom dimensions (maintains aspect ratio by default)
  python imageconverter.py image.png --size 800x600

  # Convert with forced stretching to exact dimensions
  python imageconverter.py image.png --size 800x600 --stretch true

  # Convert and resize by percentage
  python imageconverter.py image.png --size 50%

  # Batch convert all images in directory to default 1000x1000 PNG lossless
  python imageconverter.py /path/to/images --recursive

  # Convert with custom quality and strip metadata
  python imageconverter.py image.jpg --quality 80 --strip-exif-metadata true

  # Get image information
  python imageconverter.py image.jpg --info

Supported formats: {}

Note: By default, images maintain their aspect ratio when resized (e.g., 800x600 fits within those dimensions).
Use --stretch true to force exact dimensions and stretch the image instead.

JXL Quality Modes:
  Quality 100 (default) - Lossless compression, perfect quality, larger files
  Quality 90-99        - Near-lossless, visually identical, smaller than lossless
  Quality 70-89        - High quality lossy, good balance of size/quality
  Quality < 70         - Lower quality lossy, smallest file sizes

ImageMagick geometry examples:
  800x600   - Fit within 800x600 maintaining aspect ratio (default behavior)
  800x600   - With --stretch true: resize to exactly 800x600 (stretches image)
  800x600!  - Force exact size (stretches - same as --stretch true)
  800x600>  - Only shrink if larger than 800x600
  800x600<  - Only enlarge if smaller than 800x600
  50%       - Resize to 50% of original size
        """.format(', '.join(get_supported_formats().keys()))
    )
    
    parser.add_argument(
        'input',
        nargs='*',
        help='Input image file(s) or directory'
    )
    
    parser.add_argument(
        '-f', '--format',
        default='png',
        help='Output format (default: png)'
    )
    
    parser.add_argument(
        '-o', '--output',
        help='Output file or directory (auto-generated if not specified)'
    )
    
    parser.add_argument(
        '-s', '--size',
        default='1000x1000',
        help='Target size using ImageMagick geometry (default: 1000x1000)'
    )
    
    parser.add_argument(
        '--stretch', '--st',
        choices=['true', 'false'],
        default='true',
        help='Stretch images to exact dimensions instead of maintaining aspect ratio (default: true)'
    )
    
    parser.add_argument(
        '-q', '--quality',
        type=int,
        default=100,
        help='Quality setting (1-100, default: 100). For JXL: 100=lossless, <100=lossy. For JPEG/WebP: higher=better quality'
    )
    
    parser.add_argument(
        '--no-auto-orient',
        action='store_true',
        help='Disable auto-orientation based on EXIF'
    )
    
    parser.add_argument(
        '--strip-exif-metadata', '--sem',
        choices=['true', 'false'],
        default='false',
        help='Remove EXIF metadata from images (default: false)'
    )
    
    parser.add_argument(
        '--background',
        default='white',
        help='Background color for transparency removal (default: white)'
    )
    
    parser.add_argument(
        '--overwrite',
        action='store_true',
        default=False,
        help='Overwrite existing output files (default: False)'
    )
    
    parser.add_argument(
        '-r', '--recursive',
        action='store_true',
        default=False,
        help='Process directories recursively (default: False)'
    )
    
    parser.add_argument(
        '--info',
        action='store_true',
        help='Show image information and exit'
    )
    
    parser.add_argument(
        '--list-formats',
        action='store_true',
        help='List supported formats and exit'
    )
    
    parser.add_argument(
        '--logging',
        choices=['DEBUG', 'INFO', 'WARNING', 'ERROR'],
        default='INFO',
        help='Logging level (default: INFO)'
    )
    
    return parser.parse_args()


def main():
    """
    Main function for the image converter.
    """
    args = parse_arguments()
    
    # Set up logging
    logger = setup_logging(args.logging)
    
    # Check if ImageMagick is available
    if not check_imagemagick():
        logger.error("ImageMagick is not installed or not in PATH")
        logger.error("Please install ImageMagick: https://imagemagick.org/script/download.php")
        sys.exit(1)
    
    # List formats and exit
    if args.list_formats:
        print("Supported image formats:")
        for fmt, desc in get_supported_formats().items():
            print(f"  {fmt:<6} - {desc}")
        return
    
    # Check for input files (required for non-info operations)
    if not args.input and not args.info:
        logger.error("Input files or directories are required")
        sys.exit(1)
    
    # Validate quality
    if not 1 <= args.quality <= 100:
        logger.error("Quality must be between 1 and 100")
        sys.exit(1)
    
    # Parse size/geometry (always has a default value now)
    try:
        # Stretch only if explicitly enabled with --stretch true
        force_stretch = args.stretch == 'true'
        geometry, _ = parse_size(args.size, force_stretch)
    except ValueError as e:
        logger.error(f"Invalid size format: {e}")
        sys.exit(1)
    
    # Validate format
    try:
        output_format = validate_format(args.format)
    except ValueError as e:
        logger.error(str(e))
        sys.exit(1)
    
    # Collect input files
    input_files = []
    for input_path in args.input:
        if os.path.isfile(input_path):
            input_files.append(input_path)
        elif os.path.isdir(input_path):
            dir_files = scan_directory(input_path, args.recursive)
            input_files.extend(dir_files)
        else:
            logger.warning(f"Input path does not exist: {input_path}")
    
    if not input_files:
        logger.error("No valid input files found")
        sys.exit(1)
    
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
            else:
                print(f"\n{input_path}: Unable to get image information")
        return
    
    # Single file conversion
    if len(input_files) == 1 and args.output and not os.path.isdir(args.output):
        success = convert_image(
            input_path=input_files[0],
            output_path=args.output,
            output_format=output_format,
            geometry=geometry,
            quality=args.quality,
            auto_orient=not args.no_auto_orient,
            strip_metadata=args.strip_exif_metadata == 'true',
            background_color=args.background
        )
        sys.exit(0 if success else 1)
    
    # Batch conversion
    else:
        output_dir = args.output if args.output and os.path.isdir(args.output) else None
        
        successful, total = convert_batch(
            input_paths=input_files,
            output_dir=output_dir,
            output_format=output_format,
            geometry=geometry,
            quality=args.quality,
            auto_orient=not args.no_auto_orient,
            strip_metadata=args.strip_exif_metadata == 'true',
            background_color=args.background,
            overwrite=args.overwrite
        )
        
        sys.exit(0 if successful == total else 1)


if __name__ == "__main__":
    main()
