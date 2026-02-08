#!/usr/bin/env python3
"""
Walrio Import - Import music from YouTube using yt-dlp
"""

import argparse
from pathlib import Path
import subprocess
import sys
import json


class YouTubeImporter:
    """Imports music from YouTube using yt-dlp"""
    
    def __init__(self, output_dir: Path, audio_format: str = 'mp3',
                 audio_quality: str = '0', embed_metadata: bool = True,
                 embed_thumbnail: bool = True):
        """
        Args:
            output_dir: Output directory for downloads
            audio_format: Audio format (mp3, flac, opus, m4a, etc.)
            audio_quality: Quality (0=best, 9=worst for VBR)
            embed_metadata: Embed metadata tags
            embed_thumbnail: Embed thumbnail as album art
        """
        self.output_dir = output_dir
        self.audio_format = audio_format
        self.audio_quality = audio_quality
        self.embed_metadata = embed_metadata
        self.embed_thumbnail = embed_thumbnail
        self._check_ytdlp()
    
    def _check_ytdlp(self) -> None:
        """Check if yt-dlp is available"""
        try:
            subprocess.run(['yt-dlp', '--version'], capture_output=True, check=True)
        except (subprocess.CalledProcessError, FileNotFoundError):
            raise RuntimeError(
                "yt-dlp not found. Install with: pip install yt-dlp or apt install yt-dlp"
            )
    
    def get_video_info(self, url: str) -> dict:
        """
        Get video information
        
        Args:
            url: YouTube URL
            
        Returns:
            Dictionary with video info
        """
        cmd = [
            'yt-dlp',
            '--dump-json',
            '--no-playlist',
            url
        ]
        
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=True
            )
            return json.loads(result.stdout)
            
        except subprocess.CalledProcessError as e:
            raise RuntimeError(f"Failed to get video info: {e.stderr}")
        except json.JSONDecodeError as e:
            raise RuntimeError(f"Failed to parse video info: {e}")
    
    def download(self, url: str, output_template: str = None) -> Path:
        """
        Download audio from YouTube
        
        Args:
            url: YouTube URL
            output_template: Output filename template
            
        Returns:
            Path to downloaded file
        """
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # Default template
        if output_template is None:
            output_template = '%(artist)s - %(title)s.%(ext)s'
        
        # Build yt-dlp command
        cmd = [
            'yt-dlp',
            '-x',  # Extract audio
            '--audio-format', self.audio_format,
            '--audio-quality', self.audio_quality,
            '-o', str(self.output_dir / output_template)
        ]
        
        # Add metadata options
        if self.embed_metadata:
            cmd.extend([
                '--embed-metadata',
                '--parse-metadata', 'title:%(artist)s - %(title)s'
            ])
        
        if self.embed_thumbnail:
            cmd.append('--embed-thumbnail')
        
        # Add URL
        cmd.append(url)
        
        # Execute
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=True
            )
            
            # Try to find downloaded file
            # yt-dlp outputs the filename in stdout
            for line in result.stdout.split('\n'):
                if 'Destination:' in line or 'has already been downloaded' in line:
                    # Extract filename
                    parts = line.split(':')
                    if len(parts) > 1:
                        filename = parts[1].strip()
                        return Path(filename)
            
            # Fallback: search for recently created files
            audio_files = list(self.output_dir.glob(f'*.{self.audio_format}'))
            if audio_files:
                # Return most recently modified
                return max(audio_files, key=lambda p: p.stat().st_mtime)
            
            raise RuntimeError("Could not find downloaded file")
            
        except subprocess.CalledProcessError as e:
            raise RuntimeError(f"Download failed: {e.stderr}")
    
    def download_playlist(self, url: str, output_template: str = None,
                         max_downloads: int = None, start_index: int = 1) -> list:
        """
        Download playlist from YouTube
        
        Args:
            url: YouTube playlist URL
            output_template: Output filename template
            max_downloads: Maximum number of videos to download
            start_index: Playlist index to start from
            
        Returns:
            List of downloaded file paths
        """
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # Default template for playlists
        if output_template is None:
            output_template = '%(playlist_index)s - %(artist)s - %(title)s.%(ext)s'
        
        # Build yt-dlp command
        cmd = [
            'yt-dlp',
            '-x',  # Extract audio
            '--audio-format', self.audio_format,
            '--audio-quality', self.audio_quality,
            '-o', str(self.output_dir / output_template),
            '--yes-playlist',
            '--playlist-start', str(start_index)
        ]
        
        if max_downloads:
            cmd.extend(['--playlist-end', str(start_index + max_downloads - 1)])
        
        # Add metadata options
        if self.embed_metadata:
            cmd.extend([
                '--embed-metadata',
                '--parse-metadata', 'title:%(artist)s - %(title)s'
            ])
        
        if self.embed_thumbnail:
            cmd.append('--embed-thumbnail')
        
        # Add URL
        cmd.append(url)
        
        # Execute
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=True
            )
            
            # Find all downloaded files
            audio_files = list(self.output_dir.glob(f'*.{self.audio_format}'))
            return sorted(audio_files, key=lambda p: p.stat().st_mtime)
            
        except subprocess.CalledProcessError as e:
            raise RuntimeError(f"Playlist download failed: {e.stderr}")
    
    def search_and_download(self, query: str, max_results: int = 1) -> list:
        """
        Search YouTube and download results
        
        Args:
            query: Search query
            max_results: Maximum number of results to download
            
        Returns:
            List of downloaded file paths
        """
        # Use yt-dlp to search
        search_url = f"ytsearch{max_results}:{query}"
        
        if max_results == 1:
            return [self.download(search_url)]
        else:
            return self.download_playlist(search_url, max_downloads=max_results)


def import_from_youtube(url: str, output_dir: Path, audio_format: str = 'mp3',
                       quality: str = '0', is_playlist: bool = False,
                       max_downloads: int = None) -> list:
    """
    Import music from YouTube
    
    Args:
        url: YouTube URL or search query
        output_dir: Output directory
        audio_format: Audio format
        quality: Audio quality
        is_playlist: URL is a playlist
        max_downloads: Maximum downloads for playlists
        
    Returns:
        List of downloaded file paths
    """
    importer = YouTubeImporter(output_dir, audio_format, quality)
    
    if is_playlist:
        return importer.download_playlist(url, max_downloads=max_downloads)
    else:
        return [importer.download(url)]


def main():
    parser = argparse.ArgumentParser(
        description='Import music from YouTube using yt-dlp'
    )
    parser.add_argument('url', help='YouTube URL or search query')
    parser.add_argument('-o', '--output', type=Path, default=Path.cwd(),
                       help='Output directory (default: current directory)')
    parser.add_argument('-f', '--format', default='mp3',
                       choices=['mp3', 'flac', 'opus', 'm4a', 'wav'],
                       help='Audio format (default: mp3)')
    parser.add_argument('-q', '--quality', default='0',
                       help='Audio quality: 0 (best) to 9 (worst) for VBR (default: 0)')
    parser.add_argument('-p', '--playlist', action='store_true',
                       help='URL is a playlist')
    parser.add_argument('-m', '--max', type=int,
                       help='Maximum number of videos to download from playlist')
    parser.add_argument('-s', '--search', action='store_true',
                       help='Search YouTube instead of direct URL')
    parser.add_argument('-n', '--num-results', type=int, default=1,
                       help='Number of search results to download (default: 1)')
    parser.add_argument('--no-metadata', action='store_true',
                       help='Don\'t embed metadata')
    parser.add_argument('--no-thumbnail', action='store_true',
                       help='Don\'t embed thumbnail')
    
    args = parser.parse_args()
    
    try:
        importer = YouTubeImporter(
            args.output,
            args.format,
            args.quality,
            not args.no_metadata,
            not args.no_thumbnail
        )
        
        if args.search:
            # Search and download
            print(f"Searching for: {args.url}")
            files = importer.search_and_download(args.url, args.num_results)
            print(f"\nDownloaded {len(files)} file(s) to {args.output}")
            for f in files:
                print(f"  {f.name}")
        elif args.playlist:
            # Download playlist
            print(f"Downloading playlist: {args.url}")
            files = importer.download_playlist(args.url, max_downloads=args.max)
            print(f"\nDownloaded {len(files)} file(s) to {args.output}")
        else:
            # Download single video
            print(f"Downloading: {args.url}")
            file_path = importer.download(args.url)
            print(f"\nDownloaded to: {file_path}")
        
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    
    return 0


if __name__ == '__main__':
    sys.exit(main())
