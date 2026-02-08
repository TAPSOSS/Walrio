#!/usr/bin/env python3
"""
Playlist Overlap - Find overlapping and unique songs between M3U playlists
"""

import argparse
from pathlib import Path
import sys


class PlaylistOverlap:
    """Analyzes overlap between M3U playlists"""
    
    def __init__(self):
        self.playlists = {}  # name -> set of normalized paths
    
    def load_playlist(self, playlist_path: Path, name: str = None) -> None:
        """
        Load a playlist into the analyzer
        
        Args:
            playlist_path: Path to M3U playlist
            name: Name for this playlist (defaults to filename)
        """
        if not playlist_path.exists():
            raise FileNotFoundError(f"Playlist not found: {playlist_path}")
        
        name = name or playlist_path.stem
        paths = set()
        
        with open(playlist_path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.rstrip('\n\r')
                if line and not line.startswith('#'):
                    entry_path = Path(line)
                    
                    # Make absolute for comparison
                    if not entry_path.is_absolute():
                        entry_path = (playlist_path.parent / entry_path).resolve()
                    else:
                        entry_path = entry_path.resolve()
                    
                    paths.add(str(entry_path))
        
        self.playlists[name] = paths
    
    def get_overlap(self, playlist_a: str, playlist_b: str) -> set:
        """Get songs in both playlists"""
        return self.playlists[playlist_a] & self.playlists[playlist_b]
    
    def get_unique(self, playlist_name: str) -> set:
        """Get songs unique to this playlist"""
        all_others = set()
        for name, paths in self.playlists.items():
            if name != playlist_name:
                all_others |= paths
        
        return self.playlists[playlist_name] - all_others
    
    def get_difference(self, playlist_a: str, playlist_b: str) -> set:
        """Get songs in playlist_a but not in playlist_b"""
        return self.playlists[playlist_a] - self.playlists[playlist_b]
    
    def get_all_overlap(self) -> set:
        """Get songs present in ALL loaded playlists"""
        if not self.playlists:
            return set()
        
        result = set(next(iter(self.playlists.values())))
        for paths in self.playlists.values():
            result &= paths
        
        return result
    
    def save_to_playlist(self, paths: set, output_path: Path, 
                        relative_to: Path = None) -> None:
        """
        Save a set of paths to M3U playlist
        
        Args:
            paths: Set of file paths
            output_path: Output playlist path
            relative_to: Make paths relative to this directory
        """
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        entries = []
        for path_str in sorted(paths):
            path = Path(path_str)
            
            if relative_to:
                try:
                    path = path.relative_to(relative_to)
                except ValueError:
                    pass  # Keep absolute if can't make relative
            
            entries.append(str(path))
        
        with open(output_path, 'w', encoding='utf-8') as f:
            for entry in entries:
                f.write(f"{entry}\n")


def analyze_overlap(playlist_paths: list, output_dir: Path = None, 
                    save_results: bool = False) -> dict:
    """
    Analyze overlap between playlists
    
    Args:
        playlist_paths: List of playlist Path objects
        output_dir: Directory to save result playlists
        save_results: Save overlap/unique playlists
        
    Returns:
        Dictionary with analysis results
    """
    analyzer = PlaylistOverlap()
    
    # Load all playlists
    for path in playlist_paths:
        analyzer.load_playlist(path)
    
    results = {
        'playlists': {},
        'all_overlap': analyzer.get_all_overlap()
    }
    
    # Analyze each playlist
    for name, paths in analyzer.playlists.items():
        unique = analyzer.get_unique(name)
        results['playlists'][name] = {
            'total': len(paths),
            'unique': len(unique)
        }
        
        if save_results and output_dir:
            # Save unique songs
            unique_file = output_dir / f"{name}_unique.m3u"
            analyzer.save_to_playlist(unique, unique_file, output_dir)
    
    # Save all overlap if requested
    if save_results and output_dir and results['all_overlap']:
        overlap_file = output_dir / "all_overlap.m3u"
        analyzer.save_to_playlist(results['all_overlap'], overlap_file, output_dir)
    
    # Pairwise overlaps
    names = list(analyzer.playlists.keys())
    results['pairwise'] = {}
    
    for i, name_a in enumerate(names):
        for name_b in names[i+1:]:
            overlap = analyzer.get_overlap(name_a, name_b)
            key = f"{name_a} ∩ {name_b}"
            results['pairwise'][key] = len(overlap)
            
            if save_results and output_dir and overlap:
                overlap_file = output_dir / f"{name_a}_and_{name_b}.m3u"
                analyzer.save_to_playlist(overlap, overlap_file, output_dir)
    
    return results


def main():
    parser = argparse.ArgumentParser(
        description='Analyze overlap between M3U playlists'
    )
    parser.add_argument('playlists', type=Path, nargs='+', help='M3U playlists to compare')
    parser.add_argument('-o', '--output', type=Path, help='Output directory for result playlists')
    parser.add_argument('-s', '--save', action='store_true', help='Save overlap/unique playlists')
    
    args = parser.parse_args()
    
    try:
        results = analyze_overlap(args.playlists, args.output, args.save)
        
        # Display results
        print("=== Playlist Analysis ===\n")
        
        for name, data in results['playlists'].items():
            print(f"{name}:")
            print(f"  Total songs: {data['total']}")
            print(f"  Unique songs: {data['unique']}")
            print()
        
        if len(results['playlists']) > 1:
            print(f"Songs in ALL playlists: {len(results['all_overlap'])}\n")
            
            print("Pairwise overlaps:")
            for pair, count in results['pairwise'].items():
                print(f"  {pair}: {count}")
        
        if args.save and args.output:
            print(f"\nResult playlists saved to: {args.output}")
        
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    
    return 0


if __name__ == '__main__':
    sys.exit(main())
