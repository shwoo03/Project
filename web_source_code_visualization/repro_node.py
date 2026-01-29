
import os
import requests
import json
import shutil
from typing import Dict, Any

# Script to verify Node.js cross-file support.

TEST_DIR = os.path.join(os.getcwd(), "test_repro_node")
API_URL = "http://localhost:8000/api/analyze"

def setup_test_project():
    if os.path.exists(TEST_DIR):
        shutil.rmtree(TEST_DIR)
    os.makedirs(TEST_DIR)

    # utils.js
    with open(os.path.join(TEST_DIR, "utils.js"), "w", encoding="utf-8") as f:
        f.write("""
function helper() {
    console.log("I am helper");
}

const arrowHelper = () => {
    return "arrow";
}

class Service {
    doWork() {
        return true;
    }
}

module.exports = { helper, arrowHelper, Service };
""")

    # app.js
    with open(os.path.join(TEST_DIR, "app.js"), "w", encoding="utf-8") as f:
        f.write("""
const { helper, arrowHelper, Service } = require('./utils');

function main() {
    helper();
    arrowHelper();
    
    const s = new Service();
    s.doWork();
}
""")
    
    print(f"[+] Created test Node.js project at: {TEST_DIR}")

def run_analysis():
    print(f"[+] Sending analysis request to {API_URL}...")
    try:
        resp = requests.post(API_URL, json={"path": TEST_DIR})
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        print(f"[-] API Request failed: {e}")
        return None

def verify_results(data: Dict[str, Any]):
    endpoints = data.get("endpoints", [])
    print(f"[DEBUG] Endpoints found: {[e['path'] for e in endpoints]}")
    
    # Check 1: app.js root
    app_root = next((e for e in endpoints if e["path"] == "/app.js"), None)
    if not app_root:
        print("[FAIL] app.js root node not found")
        return

    print("[SUCCESS] Found app.js root")
    
    # Check 2: calls inside main() (which is inside app.js)
    # The structure might be: app.js -> main (call? or function def?)
    # Wait, my parser extracts functions and puts them in 'global_calls'?
    # No, extract_calls finds top-level calls.
    # main() is a definition.
    # My parser currently doesn't create nodes for Function Definitions themselves as children of File.
    # It creates 'root' node for FILE.
    # And 'children' are Global Calls.
    # But wait, python parser extracts functions and calls inside them?
    # JS parser `parse` method:
    # 3. Global Calls -> global_calls = self.extract_calls(root_node...)
    # endpoints.append(file_endpoint with children=global_calls)
    
    # It seems JS parser currently only captures TOP LEVEL calls?
    # Let's check `extract_calls` implementation.
    # It queries `(call_expression ...)` on `node` (root_node).
    # `captures` returns ALL matches in the tree (recursive by default in tree-sitter query?).
    # Yes, tree-sitter query runs on whole tree usually.
    # So `helper()` inside `main()` inside `app.js` SHOULD be captured.
    
    children = app_root.get("children", [])
    call_paths = [c["path"] for c in children if c["type"] == "child"]
    print(f"    -> Calls found in app.js: {call_paths}")
    
    # Check linking
    helper_call = next((c for c in children if c["path"] == "helper"), None)
    if helper_call:
        print(f"[CHECK] helper() call detected. File path: {helper_call.get('file_path')}")
        if "utils.js" in helper_call.get("file_path", ""):
            print("[SUCCESS] helper() linked to utils.js")
        else:
            print(f"[FAIL] helper() linked to {helper_call.get('file_path')} (Expected utils.js)")
    else:
        print("[FAIL] helper() call not found")

    arrow_call = next((c for c in children if c["path"] == "arrowHelper"), None)
    if arrow_call and "utils.js" in arrow_call.get("file_path", ""):
        print("[SUCCESS] arrowHelper() linked to utils.js")
    
    work_call = next((c for c in children if c["path"] == "doWork"), None)
    if work_call:
         # Class method detection
         # My parser for class methods extracts 'doWork'.
         # So global map has 'doWork' -> utils.js
         # Call is 's.doWork()'. tree-sitter call_expression function field is member_expression?
         # Query `(call_expression function: (identifier) @name)` only matches simple calls `foo()`.
         # `s.doWork()` is `(call_expression function: (member_expression ... property: (property_identifier) @name ?))`
         # My current query: `(call_expression function: (identifier) @name)`
         # This WONT match `s.doWork()`.
         # So 'doWork' call might be missed.
         print(f"[INFO] doWork call found? {work_call}")
    else:
         print("[INFO] doWork() call NOT found (Expected if method calls not supported yet)")

def main():
    setup_test_project()
    data = run_analysis()
    if data:
        verify_results(data)
    
    # Cleanup
    # shutil.rmtree(TEST_DIR)

if __name__ == "__main__":
    main()
