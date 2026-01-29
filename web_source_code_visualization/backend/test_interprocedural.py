"""
Test Inter-Procedural Taint Analysis.

Tests the functionality of tracking taint flow across function calls.
"""

import os
import sys
import tempfile
import shutil

# Add backend to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.interprocedural_taint import (
    InterProceduralTaintAnalyzer,
    TaintSummary,
    analyze_interprocedural_taint
)


def create_test_project():
    """Create a test project with inter-procedural taint flows."""
    temp_dir = tempfile.mkdtemp(prefix="test_interprocedural_")
    
    # File 1: Entry point with source
    with open(os.path.join(temp_dir, "app.py"), "w") as f:
        f.write('''
from flask import Flask, request
from utils import process_input, execute_command

app = Flask(__name__)

@app.route('/vulnerable')
def vulnerable_endpoint():
    """Entry point with user input that flows to sink."""
    user_input = request.args.get('cmd')  # SOURCE
    processed = process_input(user_input)
    result = execute_command(processed)
    return result

@app.route('/safe')
def safe_endpoint():
    """Entry point with sanitized input."""
    user_input = request.args.get('data')
    import html
    safe_data = html.escape(user_input)  # SANITIZER
    return safe_data
''')
    
    # File 2: Utility functions that propagate taint
    with open(os.path.join(temp_dir, "utils.py"), "w") as f:
        f.write('''
import os
import subprocess

def process_input(data):
    """Processes input but doesn't sanitize it - taint propagates."""
    processed = data.strip().upper()
    return processed

def execute_command(cmd):
    """Dangerous sink - executes command."""
    result = os.system(cmd)  # SINK
    return str(result)

def safe_execute(cmd):
    """Uses subprocess with shell=False - safer."""
    import shlex
    args = shlex.split(cmd)  # Sanitizer
    result = subprocess.run(args, capture_output=True)
    return result.stdout
''')
    
    # File 3: More complex call chain
    with open(os.path.join(temp_dir, "handlers.py"), "w") as f:
        f.write('''
from flask import request
from validators import validate_and_process
from db import query_database

@app.route('/search')
def search_handler():
    """3-level call chain to sink."""
    query = request.args.get('q')  # SOURCE
    validated = validate_and_process(query)
    results = query_database(validated)
    return results
''')
    
    with open(os.path.join(temp_dir, "validators.py"), "w") as f:
        f.write('''
def validate_and_process(input_data):
    """Validates but doesn't fully sanitize."""
    if len(input_data) > 100:
        return input_data[:100]
    return input_data
''')
    
    with open(os.path.join(temp_dir, "db.py"), "w") as f:
        f.write('''
def query_database(query):
    """Contains SQL injection sink."""
    import sqlite3
    conn = sqlite3.connect(':memory:')
    cursor = conn.cursor()
    cursor.execute(f"SELECT * FROM users WHERE name = '{query}'")  # SINK
    return cursor.fetchall()
''')
    
    return temp_dir


def test_basic_analysis():
    """Test basic inter-procedural analysis."""
    print("=" * 60)
    print("Test 1: Basic Inter-Procedural Analysis")
    print("=" * 60)
    
    temp_dir = create_test_project()
    
    try:
        analyzer = InterProceduralTaintAnalyzer(max_depth=10)
        result = analyzer.analyze_project(temp_dir)
        
        print(f"\n📊 Analysis Statistics:")
        for key, value in result["statistics"].items():
            print(f"   {key}: {value}")
        
        print(f"\n📝 Function Summaries: {len(result['summaries'])}")
        for name, summary in list(result["summaries"].items())[:5]:
            print(f"   - {summary['function_name']}")
            print(f"     File: {os.path.basename(summary['file_path'])}")
            print(f"     Has sources: {summary['has_sources']}")
            print(f"     Has sinks: {summary['has_sinks']}")
            print(f"     Sanitizes: {summary['sanitizes']}")
        
        print(f"\n🔴 Taint Flows Found: {len(result['flows'])}")
        for flow in result["flows"]:
            status = "🛡️ SANITIZED" if flow["sanitized"] else "⚠️ VULNERABLE"
            print(f"\n   {status}")
            print(f"   Source: {flow['source']['name']} ({flow['source']['type']}) at line {flow['source']['line']}")
            print(f"   Sink: {flow['sink']['name']} ({flow['sink']['category']}) at line {flow['sink']['line']}")
            print(f"   Path: {flow['path_description']}")
            print(f"   Call Chain: {' → '.join(flow['call_chain'][:3])}...")
            print(f"   Confidence: {flow['confidence']:.2f}")
        
        print(f"\n✅ Test passed!")
        return True
        
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        shutil.rmtree(temp_dir)


def test_call_chain_depth():
    """Test that call chains are properly tracked."""
    print("\n" + "=" * 60)
    print("Test 2: Call Chain Depth Tracking")
    print("=" * 60)
    
    temp_dir = create_test_project()
    
    try:
        # Test with different max depths
        for max_depth in [1, 3, 10]:
            analyzer = InterProceduralTaintAnalyzer(max_depth=max_depth)
            result = analyzer.analyze_project(temp_dir)
            
            print(f"\n   Max Depth {max_depth}: {len(result['flows'])} flows found")
            if result["statistics"]["max_depth_reached"] > 0:
                print(f"   ⚠️ Max depth reached {result['statistics']['max_depth_reached']} times")
        
        print(f"\n✅ Test passed!")
        return True
        
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        return False
    finally:
        shutil.rmtree(temp_dir)


def test_sanitizer_detection():
    """Test that sanitizers are properly detected."""
    print("\n" + "=" * 60)
    print("Test 3: Sanitizer Detection")
    print("=" * 60)
    
    temp_dir = create_test_project()
    
    try:
        analyzer = InterProceduralTaintAnalyzer()
        result = analyzer.analyze_project(temp_dir)
        
        sanitized_flows = [f for f in result["flows"] if f["sanitized"]]
        vulnerable_flows = [f for f in result["flows"] if not f["sanitized"]]
        
        print(f"\n   Sanitized flows: {len(sanitized_flows)}")
        print(f"   Vulnerable flows: {len(vulnerable_flows)}")
        
        for summary in result["summaries"].values():
            if summary["sanitizes"]:
                print(f"   🛡️ Function '{summary['function_name']}' sanitizes: {summary['sanitizes']}")
        
        print(f"\n✅ Test passed!")
        return True
        
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        return False
    finally:
        shutil.rmtree(temp_dir)


def test_real_project():
    """Test on the actual plob directory."""
    print("\n" + "=" * 60)
    print("Test 4: Real Project Analysis (plob/)")
    print("=" * 60)
    
    # Get the plob directory
    plob_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "plob")
    
    if not os.path.exists(plob_dir):
        print("   ⚠️ plob directory not found, skipping...")
        return True
    
    try:
        result = analyze_interprocedural_taint(plob_dir, max_depth=5)
        
        print(f"\n📊 Analysis Results:")
        print(f"   Functions analyzed: {result['statistics']['functions_analyzed']}")
        print(f"   Summaries computed: {result['statistics']['summaries_computed']}")
        print(f"   Inter-procedural flows: {result['statistics']['inter_procedural_flows']}")
        
        print(f"\n🔴 Top Vulnerable Flows:")
        for flow in result["flows"][:5]:
            severity = flow["sink"]["severity"]
            icon = "🔴" if severity == "HIGH" else "🟡" if severity == "MEDIUM" else "🟢"
            print(f"   {icon} {flow['sink']['category']}: {flow['path_description'][:60]}...")
        
        print(f"\n✅ Test passed!")
        return True
        
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Run all tests."""
    print("\n" + "=" * 60)
    print("🔬 Inter-Procedural Taint Analysis Tests")
    print("=" * 60)
    
    tests = [
        test_basic_analysis,
        test_call_chain_depth,
        test_sanitizer_detection,
        test_real_project,
    ]
    
    passed = 0
    failed = 0
    
    for test in tests:
        try:
            if test():
                passed += 1
            else:
                failed += 1
        except Exception as e:
            print(f"❌ Test crashed: {e}")
            failed += 1
    
    print("\n" + "=" * 60)
    print(f"📊 Results: {passed} passed, {failed} failed")
    print("=" * 60)
    
    return failed == 0


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
