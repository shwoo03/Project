#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""API 엔드포인트 직접 테스트"""

import requests
import json

def test_ai_endpoint():
    url = "http://localhost:8000/api/analyze/ai"
    
    payload = {
        "code": """
def login(username, password):
    query = f"SELECT * FROM users WHERE username='{username}' AND password='{password}'"
    return execute_query(query)
""",
        "context": "Login function from test",
        "project_path": "",
        "related_paths": []
    }
    
    print("=" * 60)
    print("Testing /api/analyze/ai endpoint")
    print("=" * 60)
    print(f"URL: {url}")
    print(f"Payload code length: {len(payload['code'])}")
    print()
    
    try:
        response = requests.post(url, json=payload, timeout=60)
        
        print(f"Status Code: {response.status_code}")
        print(f"Response Headers: {dict(response.headers)}")
        print()
        
        if response.status_code == 200:
            data = response.json()
            print("Response JSON:")
            print("-" * 60)
            print(json.dumps(data, indent=2, ensure_ascii=False))
            print("-" * 60)
            print()
            print(f"Success: {data.get('success')}")
            print(f"Model: {data.get('model')}")
            print(f"Error: {data.get('error')}")
            print(f"Analysis length: {len(data.get('analysis', ''))}")
            
            if data.get('analysis'):
                print()
                print("Analysis (first 300 chars):")
                print("-" * 60)
                print(data['analysis'][:300])
                print("-" * 60)
                
                if data.get('success') and len(data.get('analysis', '')) > 0:
                    print("\n✅ API TEST PASSED")
                    return True
                else:
                    print("\n❌ API returned empty or failed response")
                    return False
            else:
                print("\n❌ No analysis in response")
                return False
        else:
            print(f"Error response: {response.text}")
            print("\n❌ API TEST FAILED (HTTP error)")
            return False
            
    except requests.exceptions.ConnectionError:
        print("❌ Cannot connect to backend. Is it running?")
        print("   Run: .\\start_dev_manual.ps1")
        return False
    except Exception as e:
        print(f"❌ Exception: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    import sys
    success = test_ai_endpoint()
    sys.exit(0 if success else 1)
