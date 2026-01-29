
import requests
import os
import shutil

# Setup test project
BASE_DIR = os.path.join(os.getcwd(), "test_repro_java")
if os.path.exists(BASE_DIR):
    shutil.rmtree(BASE_DIR)
os.makedirs(BASE_DIR)

# Create a sample java file
java_code = """
public class UserManager {
    public void createUser(String name, int age) {
        System.out.println("Creating user " + name);
    }

    public User getUser(int id) {
        return new User(id);
    }
}
"""

with open(os.path.join(BASE_DIR, "UserManager.java"), "w") as f:
    f.write(java_code)

print(f"[+] Created test Java project at: {BASE_DIR}")

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
    
    expected = ['createUser', 'getUser']
    missing = set(expected) - set(endpoints)
    
    if not missing:
        print("[SUCCESS] All Java methods extracted!")
    else:
        print(f"[FAIL] Missing methods. Found: {set(endpoints)}")
        
except Exception as e:
    print(f"[ERROR] Request failed: {e}")
