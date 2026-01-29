"""
Test script for analysis cache functionality.
"""

import time
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.parallel_analyzer import ParallelAnalyzer
from core.analysis_cache import analysis_cache


def test_cache():
    """Test cache functionality with before/after comparison."""
    
    analyzer = ParallelAnalyzer()
    # Use backend directory itself for testing
    test_path = os.path.dirname(os.path.abspath(__file__))
    
    print(f"Testing cache with: {test_path}")
    print(f"Cache DB: {analysis_cache.db_path}")
    print()
    
    # Clear cache first
    print("Clearing cache...")
    analysis_cache.clear()
    
    # First run - cold cache
    print("\n=== First Run (cold cache) ===")
    start = time.time()
    endpoints1, lang_stats1, _ = analyzer.analyze_project(test_path)
    time1 = time.time() - start
    stats1 = analyzer.get_stats()
    
    print(f"Time: {time1*1000:.1f}ms")
    print(f"Parsed: {stats1['parsed_files']}, Cached: {stats1['cached_files']}")
    print(f"Endpoints: {len(endpoints1)}")
    
    # Check cache stats
    cache_stats = analysis_cache.get_stats()
    print(f"\nCache after first run:")
    print(f"  - Files cached: {cache_stats['total_cached_files']}")
    print(f"  - Size: {cache_stats['total_size_bytes']} bytes")
    print(f"  - Saves: {cache_stats['saves']}")
    
    # Second run - warm cache
    print("\n=== Second Run (warm cache) ===")
    start = time.time()
    endpoints2, lang_stats2, _ = analyzer.analyze_project(test_path)
    time2 = time.time() - start
    stats2 = analyzer.get_stats()
    
    print(f"Time: {time2*1000:.1f}ms")
    print(f"Parsed: {stats2['parsed_files']}, Cached: {stats2['cached_files']}")
    print(f"Endpoints: {len(endpoints2)}")
    
    # Check cache stats again
    cache_stats = analysis_cache.get_stats()
    print(f"\nCache after second run:")
    print(f"  - Hits: {cache_stats['hits']}")
    print(f"  - Misses: {cache_stats['misses']}")
    print(f"  - Hit rate: {cache_stats['hit_rate']*100:.1f}%")
    
    # Summary
    print("\n" + "="*50)
    print("SUMMARY")
    print("="*50)
    
    if time2 > 0:
        speedup = time1 / time2
        print(f"Speedup: {speedup:.2f}x")
    
    print(f"Endpoints match: {len(endpoints1) == len(endpoints2)}")
    print(f"Cold cache time: {time1*1000:.1f}ms")
    print(f"Warm cache time: {time2*1000:.1f}ms")
    print(f"Time saved: {(time1-time2)*1000:.1f}ms ({(1-time2/time1)*100:.1f}%)")


if __name__ == "__main__":
    test_cache()
