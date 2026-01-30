#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""AI Analyzer 실제 테스트"""

import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from core.ai_analyzer import AIAnalyzer

def test_ai():
    print("=" * 60)
    print("AI Analyzer Test")
    print("=" * 60)
    
    ai = AIAnalyzer()
    
    print(f"API Key exists: {bool(ai.api_key)}")
    print(f"Client initialized: {ai.client is not None}")
    print(f"Models available: {ai.models}")
    print()
    
    # Test code
    test_code = """
def login(username, password):
    query = f"SELECT * FROM users WHERE username='{username}' AND password='{password}'"
    return execute_query(query)
"""
    
    test_context = "Login function with SQL query"
    
    print("Analyzing code...")
    print("-" * 60)
    
    result = ai.analyze_code(test_code, test_context)
    
    print("=" * 60)
    print("RESULT:")
    print("=" * 60)
    print(f"Keys: {result.keys()}")
    print(f"Success: {result.get('success')}")
    print(f"Model: {result.get('model')}")
    print(f"Error: {result.get('error')}")
    print(f"Analysis length: {len(result.get('analysis', ''))}")
    print()
    
    if result.get('analysis'):
        print("Analysis content (first 500 chars):")
        print("-" * 60)
        print(result['analysis'][:500])
        print("-" * 60)
    
    return result

if __name__ == "__main__":
    result = test_ai()
    
    # Exit code
    if result.get('success') and result.get('analysis'):
        print("\n✅ TEST PASSED")
        sys.exit(0)
    else:
        print("\n❌ TEST FAILED")
        sys.exit(1)
