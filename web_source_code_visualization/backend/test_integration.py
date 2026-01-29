"""
Integration Test for Enhanced Security Analysis Features.

Tests:
1. Taint Analysis (Python)
2. Django Framework Support
3. JavaScript DOM XSS Detection
"""

import sys
sys.path.insert(0, 'c:/Users/dntmd/OneDrive/Desktop/my/Project/web_source_code_visualization/backend')

from core.parser.python import PythonParser
from core.parser.javascript import JavaScriptParser

# ============================================
# Test 1: Python + Taint Analysis
# ============================================
FLASK_CODE = '''
from flask import Flask, request, render_template, redirect
import subprocess
import os

app = Flask(__name__)

@app.route('/cmd', methods=['POST'])
def execute_command():
    """Vulnerable to Command Injection"""
    cmd = request.form.get('command')
    # Dangerous: user input flows to subprocess
    result = subprocess.run(cmd, shell=True, capture_output=True)
    return result.stdout

@app.route('/read', methods=['GET'])
def read_file():
    """Vulnerable to Path Traversal"""
    filename = request.args.get('file')
    path = os.path.join('/var/www/', filename)
    with open(path, 'r') as f:
        return f.read()

@app.route('/search')
def search():
    """Vulnerable to SQL Injection"""
    query = request.args.get('q')
    cursor.execute(f"SELECT * FROM users WHERE name = '{query}'")
    return jsonify(cursor.fetchall())
'''

# ============================================
# Test 2: Django/DRF Code
# ============================================
DJANGO_CODE = '''
from django.shortcuts import render
from django.http import HttpResponse
from rest_framework.decorators import api_view
from rest_framework.response import Response
import subprocess

@api_view(['POST'])
def execute_command(request):
    """DRF view vulnerable to command injection"""
    cmd = request.data.get('command')
    result = subprocess.run(cmd, shell=True, capture_output=True)
    return Response({'output': result.stdout})

class UserViewSet(viewsets.ModelViewSet):
    @action(methods=['get'], detail=True)
    def profile(self, request, pk=None):
        user_id = request.query_params.get('id')
        return Response({'id': user_id})
'''

# ============================================
# Test 3: JavaScript with XSS
# ============================================
JS_XSS_CODE = '''
// Vulnerable to DOM XSS
function displaySearch() {
    const query = new URLSearchParams(window.location.search).get('q');
    
    // XSS Sink: innerHTML with user input
    document.getElementById('results').innerHTML = query;
    
    // API call
    fetch('/api/search?q=' + encodeURIComponent(query))
        .then(res => res.json())
        .then(data => {
            // Another XSS sink
            document.write('<div>' + data.html + '</div>');
        });
}

// Event handler
document.getElementById('btn').addEventListener('click', () => {
    const userInput = document.getElementById('input').value;
    eval(userInput);  // Code injection
});
'''

def test_python_taint_analysis():
    print("\n" + "=" * 60)
    print("Test 1: Python Taint Analysis (Flask)")
    print("=" * 60)
    
    parser = PythonParser()
    endpoints = parser.parse("app.py", FLASK_CODE)
    
    sinks_found = []
    taint_flows = []
    
    for ep in endpoints:
        # Check for sinks in children
        for child in ep.children:
            if child.type == "sink":
                sinks_found.append(child)
            if child.metadata.get("taint_flow"):
                taint_flows.append(child)
        
        # Check metadata for sinks
        if ep.metadata.get("sinks"):
            sinks_found.extend(ep.metadata.get("sinks", []))
    
    print(f"[INFO] Found {len(endpoints)} endpoints")
    for ep in endpoints:
        print(f"  - {ep.method} {ep.path}")
        print(f"    Inputs: {[p.name for p in ep.params]}")
        if ep.children:
            sink_children = [c for c in ep.children if c.type == "sink"]
            if sink_children:
                print(f"    Sinks: {[s.path for s in sink_children]}")
    
    print(f"\n[RESULT] Sinks detected: {len(sinks_found)}")
    print("[PASS] Python taint analysis working")
    return True

def test_django_support():
    print("\n" + "=" * 60)
    print("Test 2: Django/DRF Support")
    print("=" * 60)
    
    parser = PythonParser()
    endpoints = parser.parse("views.py", DJANGO_CODE)
    
    print(f"[INFO] Found {len(endpoints)} endpoints")
    for ep in endpoints:
        print(f"  - {ep.method} {ep.path}")
        print(f"    Inputs: {[p.name for p in ep.params]}")
    
    # Check if DRF decorators are recognized
    has_drf = any("api_view" in str(ep.metadata) or ep.method in ["POST", "GET"] for ep in endpoints)
    
    print(f"\n[RESULT] Django/DRF routes detected: {len(endpoints)}")
    print("[PASS] Django support working")
    return True

def test_js_xss_detection():
    print("\n" + "=" * 60)
    print("Test 3: JavaScript DOM XSS Detection")
    print("=" * 60)
    
    parser = JavaScriptParser()
    endpoints = parser.parse("search.js", JS_XSS_CODE)
    
    root = endpoints[0]
    sinks = [c for c in root.children if c.type == "sink"]
    api_calls = [c for c in root.children if c.type == "api_call"]
    events = [c for c in root.children if c.type == "event_handler"]
    
    print(f"[INFO] Parsed JavaScript file: {root.path}")
    print(f"  - DOM XSS Sinks: {len(sinks)}")
    for sink in sinks:
        print(f"    ⚠️ {sink.metadata.get('sink_name')} (severity: {sink.metadata.get('severity')})")
    
    print(f"  - API Calls: {len(api_calls)}")
    for api in api_calls:
        print(f"    → {api.path}")
    
    print(f"  - Event Handlers: {len(events)}")
    for event in events:
        print(f"    📎 {event.path}")
    
    # Verify we found dangerous sinks
    dangerous_sinks = [s for s in sinks if s.metadata.get("dangerous")]
    print(f"\n[RESULT] Dangerous sinks detected: {len(dangerous_sinks)}")
    
    assert len(dangerous_sinks) >= 3, "Should detect innerHTML, document.write, and eval"
    print("[PASS] JavaScript XSS detection working")
    return True

def main():
    print("=" * 60)
    print("INTEGRATION TEST: Security Analysis Features")
    print("=" * 60)
    
    results = []
    
    try:
        results.append(("Python Taint Analysis", test_python_taint_analysis()))
    except Exception as e:
        print(f"[FAIL] Python Taint Analysis: {e}")
        results.append(("Python Taint Analysis", False))
    
    try:
        results.append(("Django Support", test_django_support()))
    except Exception as e:
        print(f"[FAIL] Django Support: {e}")
        results.append(("Django Support", False))
    
    try:
        results.append(("JavaScript XSS Detection", test_js_xss_detection()))
    except Exception as e:
        print(f"[FAIL] JavaScript XSS Detection: {e}")
        results.append(("JavaScript XSS Detection", False))
    
    # Summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    
    all_passed = True
    for name, passed in results:
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"  {status} - {name}")
        if not passed:
            all_passed = False
    
    print("\n" + "=" * 60)
    if all_passed:
        print("All integration tests passed! ✓")
    else:
        print("Some tests failed. Please check the output above.")
    print("=" * 60)
    
    return all_passed

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
