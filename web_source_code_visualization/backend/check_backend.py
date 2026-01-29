#!/usr/bin/env python3
"""
Backend server health check utility
"""
import requests
import sys
import time

API_BASE = "http://localhost:8000"

def check_backend():
    """Check if backend server is running and healthy"""
    
    print("=" * 60)
    print(" Backend Server Health Check")
    print("=" * 60)
    print()
    
    # 1. Basic connectivity
    print("[1] Checking server connectivity...")
    try:
        response = requests.get(f"{API_BASE}/", timeout=5)
        print(f"✅ Server is running (Status: {response.status_code})")
    except requests.exceptions.ConnectionError:
        print("❌ Cannot connect to server!")
        print("   Please start the server:")
        print("   cd backend && python main.py")
        return False
    except requests.exceptions.Timeout:
        print("❌ Server connection timed out")
        return False
    except Exception as e:
        print(f"❌ Connection error: {e}")
        return False
    
    print()
    
    # 2. Health endpoint
    print("[2] Checking health endpoint...")
    try:
        response = requests.get(f"{API_BASE}/health", timeout=5)
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Server healthy: {data}")
        else:
            print(f"⚠️ Health check returned status {response.status_code}")
    except Exception as e:
        print(f"⚠️ Health endpoint not available: {e}")
    
    print()
    
    # 3. Cache stats
    print("[3] Checking cache...")
    try:
        response = requests.get(f"{API_BASE}/api/cache/stats", timeout=5)
        if response.status_code == 200:
            stats = response.json()
            print(f"✅ Cache operational:")
            print(f"   - Hit rate: {stats.get('hit_rate', 0):.1%}")
            print(f"   - Total queries: {stats.get('total_queries', 0)}")
            print(f"   - DB size: {stats.get('db_size_mb', 0):.2f} MB")
        else:
            print(f"⚠️ Cache stats unavailable")
    except Exception as e:
        print(f"⚠️ Cannot fetch cache stats: {e}")
    
    print()
    
    # 4. Quick analysis test
    print("[4] Testing analysis endpoint...")
    test_path = r"c:\Users\dntmd\OneDrive\Desktop\my\Project\web_source_code_visualization\plob\새싹\cookie"
    
    try:
        print(f"   Testing with: {test_path}")
        start_time = time.time()
        
        response = requests.post(
            f"{API_BASE}/api/analyze",
            json={
                "path": test_path,
                "cluster": False,
                "use_parallel": False
            },
            timeout=30
        )
        
        elapsed = time.time() - start_time
        
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Analysis successful ({elapsed:.2f}s)")
            print(f"   - Endpoints: {len(data.get('endpoints', []))}")
            print(f"   - Taint flows: {len(data.get('taint_flows', []))}")
            print(f"   - Languages: {data.get('language_stats', {})}")
        elif response.status_code == 404:
            print(f"⚠️ Test path not found (this is OK if path doesn't exist)")
        else:
            print(f"❌ Analysis failed (Status: {response.status_code})")
            print(f"   Response: {response.text[:200]}")
    except requests.exceptions.Timeout:
        print(f"❌ Analysis timed out after 30 seconds")
        print(f"   This might indicate a stuck analysis issue")
    except Exception as e:
        print(f"❌ Analysis test failed: {e}")
    
    print()
    print("=" * 60)
    print("✅ Health check complete!")
    print("=" * 60)
    
    return True

if __name__ == "__main__":
    success = check_backend()
    sys.exit(0 if success else 1)
