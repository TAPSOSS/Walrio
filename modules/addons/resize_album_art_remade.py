#!/usr/bin/env python3
"""
Resize Album Art - Resizes embedded album art in audio files to reduce file size
"""

import argparse
from pathlib import Path
import sys
from io import BytesIO
from PIL import Image

try:
    from mutagen import File as MutagenFile
    from mutagen.id3 import APIC, ID3
    from mutagen.flac import Picture, FLAC
    from mutagen.mp4 import MP4, MP4Cover
except ImportError:
    print("Error: mutagen library required. Install with: pip install mutagen", file=sys.stderr)
    sys.exit(1)


class AlbumArtResizer:
    """Resizes embedded album art in audio files"""
    
    def __init__(self, max_size: int = 500):
        """
        Args:
            max_size: Maximum width/height in pixels
        """
        self.max_size = max_size
    
    def resize_image(self, image_data: bytes) -> bytes:
        """
        Resize image data
        
        Args:
            image_data: Original image bytes
            
        Returns:
            Resized image bytes
        """
        try:
            img = Image.open(BytesIO(image_data))
            
            # Check if resize needed
            if max(img.size) <= self.max_size:
                return image_data
            
            # Calculate new size maintaining aspect ratio
            ratio = self.max_size / max(img.size)
            new_size = tuple(int(dim * ratio) for dim in img.size)
            
            # Resize with high quality
            img = img.resize(new_size, Image.Resampling.LANCZOS)
            
            # Save to bytes
            output = BytesIO()
            img_format = img.format or 'JPEG'
            img.save(output, format=img_format, quality=95)
            return output.getvalue()
            
        except Exception as e:
            raise RuntimeError(f"Failed to resize image: {e}")
    
    def resize_mp3(self, file_path: Path) -> bool:
        """Resize album art in MP3 file"""
        try:
            audio = ID3(file_path)
            modified = False
            
            for key in list(audio.keys()):
                if key.startswith('APIC:'):
                    apic = audio[key]
                    original_size = len(apic.data)
                    resized_data = self.resize_image(apic.data)
                    
                    if len(resized_data) < original_size:
                        apic.data = resized_data
                        modified = True
            
            if modified:
                audio.save(file_path)
            
            return modified
            
        except Exception as e:
            raise RuntimeError(f"Failed to process MP3: {e}")
    
    def resize_flac(self, file_path: Path) -> bool:
        """Resize album art in FLAC file"""
        try:
            audio = FLAC(file_path)
            modified = False
            
            if audio.pictures:
                new_pictures = []
                for pic in audio.pictures:
                    original_size = len(pic.data)
                    resized_data = self.resize_image(pic.data)
                    
                    if len(resized_data) < original_size:
                        new_pic = Picture()
                        new_pic.type = pic.type
                        new_pic.mime = pic.mime
                        new_pic.desc = pic.desc
                        new_pic.data = resized_data
                        new_pictures.append(new_pic)
                        modified = True
                    else:
                        new_pictures.append(pic)
                
                if modified:
                    audio.clear_pictures()
                    for pic in new_pictures:
                        audio.add_picture(pic)
                    audio.save()
            
            return modified
            
        except Exception as e:
            raise RuntimeError(f"Failed to process FLAC: {e}")
    
    def resize_mp4(self, file_path: Path) -> bool:
        """Resize album art in MP4/M4A file"""
        try:
            audio = MP4(file_path)
            modified = False
            
            if 'covr' in audio:
                covers = audio['covr']
                new_covers = []
                
                for cover in covers:
                    original_size = len(cover)
                    resized_data = self.resize_image(bytes(cover))
                    
                    if len(resized_data) < original_size:
                        # Preserve format
                        fmt = cover.imageformat
                        new_covers.append(MP4Cover(resized_data, imageformat=fmt))
                        modified = True
                    else:
                        new_covers.append(cover)
                
                if modified:
                    audio['covr'] = new_covers
                    audio.save()
            
            return modified
            
        except Exception as e:
            raise RuntimeError(f"Failed to process MP4: {e}")
    
    def resize_file(self, file_path: Path) -> bool:
        """
        Resize album art in audio file
        
        Args:
            file_path: Path to audio file
            
        Returns:
            True if album art was resized
        """
        ext = file_path.suffix.lower()
        
        if ext == '.mp3':
            return self.resize_mp3(file_path)
        elif ext in {'.flac', '.ogg', '.opus'}:
            return self.resize_flac(file_path)
        elif ext in {'.m4a', '.mp4'}:
            return self.resize_mp4(file_path)
        else:
            raise ValueError(f"Unsupported format: {ext}")


def resize_album_art(file_path: Path, max_size: int = 500) -> bool:
    """
    Resize embedded album art
    
    Args:
        file_path: Audio file path
        max_size: Maximum dimension in pixels
        
    Returns:
        True if resized
    """
    resizer = AlbumArtResizer(max_size)
    return resizer.resize_file(file_path)


def main():
    parser = argparse.ArgumentParser(
        description='Resize embedded album art in audio files'
    )
    parser.add_argument('files', type=Path, nargs='+', help='Audio files to process')
    parser.add_argument('-s', '--size', type=int, default=500, help='Maximum size in pixels (default: 500)')
    parser.add_argument('-r', '--recursive', action='store_true', help='Process directories recursively')
    
    args = parser.parse_args()
    
    resizer = AlbumArtResizer(args.size)
    processed = 0
    resized = 0
    errors = 0
    
    # Collect files to process
    files_to_process = []
    for file_arg in args.files:
        if file_arg.is_dir():
            if args.recursive:
                pattern = '**/*'
            else:
                pattern = '*'
            
            for ext in ['.mp3', '.flac', '.ogg', '.opus', '.m4a', '.mp4']:
                files_to_process.extend(file_arg.glob(f'{pattern}{ext}'))
        else:
            files_to_process.append(file_arg)
    
    # Process files
    for file_path in files_to_process:
        try:
            if resizer.resize_file(file_path):
                print(f"Resized: {file_path}")
                resized += 1
            processed += 1
            
        except Exception as e:
            print(f"Error processing {file_path}: {e}", file=sys.stderr)
            errors += 1
    
    print(f"\nProcessed: {processed}")
    print(f"Resized: {resized}")
    print(f"Errors: {errors}")
    
    return 0 if errors == 0 else 1


if __name__ == '__main__':
    sys.exit(main())
