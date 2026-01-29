#!/usr/bin/env python3
"""Test analyzing the cookie directory with improved error handling"""
import sys
import os
import requests
import json

# Test directory path
test_path = r"c:\Users\dntmd\OneDrive\Desktop\my\Project\web_source_code_visualization\plob\새싹\cookie"

print("=" * 60)
print("Testing Cookie Directory Analysis")
print("=" * 60)
print(f"Path: {test_path}")
print(f"Path exists: {os.path.exists(test_path)}")
print(f"Path is directory: {os.path.isdir(test_path)}")
print()

# Check files
files = []
for root, dirs, filelist in os.walk(test_path):
    for f in filelist:
        file_path = os.path.join(root, f)
        files.append(file_path)
        print(f"Found file: {file_path}")
        print(f"  - Size: {os.path.getsize(file_path)} bytes")
        print(f"  - Readable: {os.access(file_path, os.R_OK)}")

print(f"\nTotal files: {len(files)}")
print()

# Test API call
API_BASE = "http://localhost:8000"

print("=" * 60)
print("Testing Non-Streaming Analysis API")
print("=" * 60)

try:
    response = requests.post(
        f"{API_BASE}/api/analyze",
        json={
            "path": test_path,
            "cluster": False,
            "use_parallel": False
        },
        timeout=30
    )
    
    print(f"Status Code: {response.status_code}")
    
    if response.status_code == 200:
        data = response.json()
        print("\n✅ Analysis Successful!")
        print(f"Endpoints found: {len(data.get('endpoints', []))}")
        print(f"Taint flows: {len(data.get('taint_flows', []))}")
        print(f"Language stats: {data.get('language_stats', {})}")
        
        if data.get('endpoints'):
            print("\nFirst endpoint:")
            ep = data['endpoints'][0]
            print(f"  Path: {ep.get('path')}")
            print(f"  Type: {ep.get('type')}")
            print(f"  Children: {len(ep.get('children', []))}")
    else:
        print(f"\n❌ Analysis Failed")
        print(f"Response: {response.text}")
        
except requests.exceptions.Timeout:
    print("❌ Request timed out after 30 seconds")
except requests.exceptions.ConnectionError:
    print("❌ Cannot connect to API server. Is it running?")
    print("   Start server with: cd backend && python main.py")
except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()

print()
print("=" * 60)
print("Testing Streaming Analysis API")
print("=" * 60)

try:
    response = requests.post(
        f"{API_BASE}/api/analyze/stream",
        json={
            "path": test_path,
            "cluster": False,
            "use_cache": False,
            "format": "sse"
        },
        stream=True,
        timeout=30
    )
    
    print(f"Status Code: {response.status_code}")
    
    if response.status_code == 200:
        print("\n📡 Streaming events:")
        event_count = 0
        for line in response.iter_lines():
            if line:
                line = line.decode('utf-8')
                if line.startswith('data: '):
                    event_count += 1
                    event_data = json.loads(line[6:])
                    event_type = event_data.get('type')
                    print(f"  Event {event_count}: {event_type}")
                    
                    if event_type == 'error':
                        print(f"    ❌ Error: {event_data.get('data')}")
                    elif event_type == 'complete':
                        print(f"    ✅ Complete: {event_data.get('data')}")
                    
                    # Stop after 20 events to prevent infinite loop
                    if event_count >= 20:
                        print("  ... (stopping after 20 events)")
                        break
        
        print(f"\nTotal events received: {event_count}")
    else:
        print(f"\n❌ Streaming Failed")
        print(f"Response: {response.text}")
        
except requests.exceptions.Timeout:
    print("❌ Request timed out after 30 seconds")
except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()
