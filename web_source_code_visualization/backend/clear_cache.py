import sys
import os

# Add backend to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.analysis_cache import AnalysisCache

def main():
    print("Clearing analysis cache...")
    try:
        cache = AnalysisCache()
        cache.clear()
        print("✅ Cache cleared successfully.")
        
        # Verify
        stats = cache.get_stats()
        print(f"Stats after clear: {stats}")
        
    except Exception as e:
        print(f"❌ Failed to clear cache: {e}")

if __name__ == "__main__":
    main()
