#!/usr/bin/env python3
"""Test parsing of cookie app.py"""
import os
import sys
import json
import time

# Add parent directory to path
sys.path.insert(0, os.path.dirname(__file__))

from core.parser import ParserManager

def test_parse():
    file_path = r"c:\Users\dntmd\OneDrive\Desktop\my\Project\web_source_code_visualization\plob\새싹\cookie\app.py"
    
    print(f"Testing file: {file_path}")
    print(f"File exists: {os.path.exists(file_path)}")
    print(f"File size: {os.path.getsize(file_path)} bytes")
    print()
    
    # Read content
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    print(f"Content length: {len(content)} characters")
    print(f"First 200 chars: {content[:200]}")
    print()
    
    # Initialize parser
    parser_manager = ParserManager()
    parser = parser_manager.get_parser(file_path)
    
    print(f"Parser type: {type(parser).__name__}")
    print()
    
    # Test symbol scanning
    print("=" * 60)
    print("Phase 1: Symbol Scanning")
    print("=" * 60)
    start = time.time()
    try:
        symbols = parser.scan_symbols(file_path, content)
        scan_time = time.time() - start
        print(f"✓ Symbol scanning completed in {scan_time:.3f}s")
        print(f"Found {len(symbols)} symbols:")
        for name, info in symbols.items():
            print(f"  - {name}: {info}")
    except Exception as e:
        print(f"✗ Symbol scanning failed: {e}")
        import traceback
        traceback.print_exc()
    
    print()
    
    # Test full parsing
    print("=" * 60)
    print("Phase 2: Full Parsing")
    print("=" * 60)
    start = time.time()
    try:
        endpoints = parser.parse(file_path, content, global_symbols={}, symbol_table=None)
        parse_time = time.time() - start
        print(f"✓ Full parsing completed in {parse_time:.3f}s")
        print(f"Found {len(endpoints)} endpoints:")
        
        for i, ep in enumerate(endpoints):
            print(f"\nEndpoint {i+1}:")
            print(f"  ID: {ep.id}")
            print(f"  Path: {ep.path}")
            print(f"  Type: {ep.type}")
            print(f"  Children: {len(ep.children)}")
            print(f"  Line: {ep.line_number}")
            
            # Show first few children
            if ep.children:
                print(f"  First children:")
                for child in ep.children[:3]:
                    print(f"    - {child.path} ({child.type})")
                    
    except Exception as e:
        print(f"✗ Full parsing failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_parse()
