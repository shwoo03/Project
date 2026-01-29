
import requests
import os
import shutil

# Setup test project
BASE_DIR = os.path.join(os.getcwd(), "test_repro_go")
if os.path.exists(BASE_DIR):
    shutil.rmtree(BASE_DIR)
os.makedirs(BASE_DIR)

# Create a sample go file
go_code = """
package main

import "fmt"

func main() {
    fmt.Println("Hello")
}

func GetUser(id int) string {
    return "User"
}

func (s *Service) CreatePost(title string) {
    // method
}
"""

with open(os.path.join(BASE_DIR, "main.go"), "w") as f:
    f.write(go_code)

print(f"[+] Created test Go project at: {BASE_DIR}")

# Send request
url = "http://localhost:8000/api/analyze"
print(f"[+] Sending analysis request to {url}...")
try:
    response = requests.post(url, json={"path": BASE_DIR})
    response.raise_for_status()
    data = response.json()
    
    endpoints = []
    
    # helper to find endpoints
    def find_endpoints(nodes):
        for node in nodes:
            if node['type'] == 'child': 
                endpoints.append(node['path'])
            if 'children' in node:
                find_endpoints(node['children'])

    find_endpoints(data['endpoints'])
    
    print(f"[DEBUG] Endpoints found: {endpoints}")
    
    # Note: 'main' might skip if logic excludes main? Or checked.
    expected = ['main', 'GetUser', 'CreatePost'] 
    # CreatePost depends on receiver logic extraction
    
    missing = set(expected) - set(endpoints)
    
    if not missing:
        print("[SUCCESS] All Go functions extracted!")
    else:
        print(f"[FAIL] Missing functions. Found: {set(endpoints)}")
        
except Exception as e:
    print(f"[ERROR] Request failed: {e}")
