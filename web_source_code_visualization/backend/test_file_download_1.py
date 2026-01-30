"""Test Path Traversal detection for file-download-1 sample"""
import os
import sys
import json

# Setup
sys.path.insert(0, os.path.dirname(__file__))
os.chdir(os.path.dirname(__file__))
os.environ['PYTHONUTF8'] = '1'

from core.analyzer.semgrep_analyzer import SemgrepAnalyzer

def test_file_download_1():
    """Test Semgrep detection on file-download-1 sample"""
    
    analyzer = SemgrepAnalyzer()
    target = os.path.join(os.path.dirname(__file__), '..', 'plob', '새싹', 'file-download-1')
    
    print(f"=== Testing file-download-1 ===")
    print(f"Target: {target}")
    print()
    
    # Load metadata
    metadata_path = os.path.join(target, 'metadata.json')
    if os.path.exists(metadata_path):
        with open(metadata_path, 'r', encoding='utf-8') as f:
            metadata = json.load(f)
            expected = metadata.get('expected_findings', 0)
            print(f"Expected findings: {expected}")
            for v in metadata.get('vulnerabilities', []):
                print(f"  - [{v['type']}] Line {v['line']}: {v['description']}")
    else:
        print("⚠️ No metadata.json found")
        expected = None
    
    print()
    
    # Run scan
    try:
        results = analyzer.scan_project(target, timeout=60)
        
        print(f"=== Scan Results ({len(results)} findings) ===")
        if results:
            for r in results:
                rule_id = r.get('rule_id', r.get('check_id', '?'))
                line = r.get('line', r.get('start', {}).get('line', '?'))
                severity = r.get('severity', '?')
                msg = r.get('message', '')
                file_path = r.get('file_path', '')
                print(f"  [{severity}] {rule_id} @ line {line}")
                print(f"      {msg}")
                if file_path:
                    print(f"      File: {os.path.basename(file_path)}")
                # Debug: print full result
                print(f"      DEBUG: {r.keys()}")
        else:
            print("  ❌ No findings detected")
        
        # Validation
        print()
        print("=== Validation ===")
        if expected is not None:
            if len(results) == expected:
                print(f"✅ PASS: Found {len(results)} vulnerabilities (expected {expected})")
            else:
                print(f"❌ FAIL: Found {len(results)} vulnerabilities (expected {expected})")
        
        # Check for path-traversal rule
        path_traversal_found = any('path-traversal' in r.get('check_id', r.get('rule_id', '')) for r in results)
        if path_traversal_found:
            print("✅ PASS: Path Traversal rule detected")
        else:
            print("❌ FAIL: Path Traversal rule NOT detected")
        
        return len(results) == expected and path_traversal_found
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_file_download_1()
    sys.exit(0 if success else 1)
