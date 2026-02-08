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
        cmd = ['identify', '-format', '%w %h %m %b', str(image_path)]
        result = subprocess.run(cmd, capture_output=True, text=True, check=True, timeout=10)
        
        parts = result.stdout.strip().split()
        if len(parts) >= 4:
            return {
                'width': int(parts[0]),
                'height': int(parts[1]),
                'format': parts[2],
                'size': parts[3]
            }
        return None
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, ValueError):
        return None


def convert_image(input_path: Path, output_path: Path,
                 output_format: Optional[str] = None,
                 geometry: Optional[str] = None,
                 quality: int = 90,
                 auto_orient: bool = False,
                 strip_metadata: bool = False,
                 background_color: Optional[str] = None) -> bool:
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
        
    Returns:
        True if successful
    """
    if not input_path.exists():
        logger.error(f"Input file not found: {input_path}")
        return False
    
    # Build command
    cmd = ['convert', str(input_path)]
    
    # Auto-orient
    if auto_orient:
        cmd.append('-auto-orient')
    
    # Resize
    if geometry:
        cmd.extend(['-resize', geometry])
    
    # Background color (for transparent images)
    if background_color:
        cmd.extend(['-background', background_color])
        cmd.append('-flatten')
    
    # Quality
    cmd.extend(['-quality', str(quality)])
    
    # Strip metadata
    if strip_metadata:
        cmd.append('-strip')
    
    # Output format
    if output_format:
        cmd.append(f"{validate_format(output_format)}:{output_path}")
    else:
        cmd.append(str(output_path))
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True, timeout=60)
        logger.debug(f"Converted {input_path.name} to {output_path.name}")
        return True
    except subprocess.CalledProcessError as e:
        logger.error(f"Conversion failed: {e.stderr}")
        return False
    except subprocess.TimeoutExpired:
        logger.error(f"Conversion timed out for {input_path}")
        return False


class ImageConverter:
    """
    Image converter with advanced size parsing and format support
    """
    
    def __init__(self, output_format: str = 'png', 
                 size: Optional[str] = None,
                 quality: int = 90,
                 force_stretch: bool = False,
                 auto_orient: bool = True,
                 strip_metadata: bool = False):
        """
        Args:
            output_format: Target format
            size: Size specification (e.g., '800x800', '800x800!', '50%')
            quality: Output quality (1-100)
            force_stretch: Force exact dimensions
            auto_orient: Auto-orient based on EXIF
            strip_metadata: Remove metadata
        """
        self.output_format = validate_format(output_format)
        self.quality = quality
        self.force_stretch = force_stretch
        self.auto_orient = auto_orient
        self.strip_metadata = strip_metadata
        
        # Parse size
        if size:
            self.geometry, self.maintain_aspect = parse_size(size, force_stretch)
        else:
            self.geometry = None
            self.maintain_aspect = True
        
        if not check_imagemagick():
            raise RuntimeError("ImageMagick not found. Install with: apt install imagemagick")
    
    def convert_file(self, input_path: Path, output_path: Optional[Path] = None,
                    overwrite: bool = False) -> Optional[Path]:
        """
        Convert single image file
        
        Args:
            input_path: Input image
            output_path: Output path (auto-generated if None)
            overwrite: Overwrite existing files
            
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
            logger.warning(f"Output exists: {output_path} (use --force to overwrite)")
            return None
        
        # Convert
        success = convert_image(
            input_path, output_path,
            output_format=self.output_format,
            geometry=self.geometry,
            quality=self.quality,
            auto_orient=self.auto_orient,
            strip_metadata=self.strip_metadata
        )
        
        return output_path if success else None
    
    def convert_directory(self, input_dir: Path, output_dir: Optional[Path] = None,
                         recursive: bool = True, overwrite: bool = False) -> Dict[str, int]:
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
        
        # Convert each file
        stats = {'converted': 0, 'skipped': 0, 'errors': 0}
        
        for file_path in files:
            try:
                # Preserve directory structure
                rel_path = file_path.relative_to(input_dir)
                output_path = output_dir / rel_path.with_suffix(f'.{self.output_format}')
                output_path.parent.mkdir(parents=True, exist_ok=True)
                
                result = self.convert_file(file_path, output_path, overwrite)
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
        description='Convert and resize images using ImageMagick',
        epilog="""
Size format examples:
  800x600    - Fit within 800x600, maintaining aspect ratio
  800x600!   - Force exact 800x600, ignore aspect ratio
  800x600>   - Only shrink larger images
  800        - Set width to 800, maintain aspect ratio
  x600       - Set height to 600, maintain aspect ratio
  50%%       - Scale to 50%% of original size

Supported formats: png, jpeg, jpg, jxl, webp, bmp, tiff, gif, ico, svg, pdf, eps, psd
        """
    )
    parser.add_argument('input', type=Path, help='Input file or directory')
    parser.add_argument('format', help='Target format')
    parser.add_argument('-o', '--output', type=Path, help='Output file or directory')
    parser.add_argument('-s', '--size', help='Size specification (e.g., 800x600, 800x600!)')
    parser.add_argument('-q', '--quality', type=int, default=90, help='Quality (1-100, default: 90)')
    parser.add_argument('-r', '--recursive', action='store_true', help='Process subdirectories')
    parser.add_argument('-f', '--force', action='store_true', help='Overwrite existing files')
    parser.add_argument('--force-stretch', action='store_true', help='Force exact dimensions')
    parser.add_argument('--no-auto-orient', action='store_true', help='Disable auto-orientation')
    parser.add_argument('--strip-metadata', action='store_true', help='Remove metadata')
    parser.add_argument('--list-formats', action='store_true', help='List supported formats')
    parser.add_argument('--info', action='store_true', help='Show input file information')
    
    args = parser.parse_args()
    
    # List formats
    if args.list_formats:
        print("Supported image formats:")
        for fmt, desc in get_supported_formats().items():
            print(f"  {fmt:6} - {desc}")
        return 0
    
    # Show info
    if args.info:
        info = get_image_info(args.input)
        if info:
            print(f"Image Information:")
            print(f"  Format: {info['format']}")
            print(f"  Dimensions: {info['width']}x{info['height']}")
            print(f"  File size: {info['size']}")
        else:
            print("Could not read image information")
            return 1
        return 0
    
    try:
        converter = ImageConverter(
            output_format=args.format,
            size=args.size,
            quality=args.quality,
            force_stretch=args.force_stretch,
            auto_orient=not args.no_auto_orient,
            strip_metadata=args.strip_metadata
        )
        
        if args.input.is_dir():
            stats = converter.convert_directory(args.input, args.output, args.recursive, args.force)
            print(f"\nConversion complete:")
            print(f"  Converted: {stats['converted']}")
            print(f"  Skipped: {stats['skipped']}")
            if stats['errors']:
                print(f"  Errors: {stats['errors']}")
                return 1
        else:
            result = converter.convert_file(args.input, args.output, args.force)
            if result:
                print(f"Converted: {result}")
            else:
                print("Conversion failed")
                return 1
        
        return 0
        
    except Exception as e:
        logger.error(f"Error: {e}")
        return 1


if __name__ == '__main__':
    sys.exit(main())
