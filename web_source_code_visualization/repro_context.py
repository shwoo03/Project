
import os
import requests
import json
import shutil

# Script to verify Context-Aware AI
# We create two files:
# 1. main.py (Vulnerable logic using imported func)
# 2. auth.py (The imported func contains the flaw)
# If AI sees auth.py, it detects the flaw.

TEST_DIR = os.path.join(os.getcwd(), "test_context_ai")
API_URL = "http://localhost:8000/api/analyze/ai"

def setup_test_project():
    if os.path.exists(TEST_DIR):
        shutil.rmtree(TEST_DIR)
    os.makedirs(TEST_DIR)

    # 1. auth.py - Hardcoded credentials (THE FLAW)
    auth_path = os.path.join(TEST_DIR, "auth.py")
    with open(auth_path, "w", encoding="utf-8") as f:
        f.write("""
def verify_admin(user, password):
    # VULNERABILITY: Hardcoded admin password
    if user == "admin" and password == "super_secret_123":
        return True
    return False
""")

    # 2. main.py - Calls auth.py
    main_path = os.path.join(TEST_DIR, "main.py")
    with open(main_path, "w", encoding="utf-8") as f:
        f.write("""
import auth

def login(user, password):
    if auth.verify_admin(user, password):
        print("Welcome Admin!")
    else:
        print("Access Denied")
""")
    
    return main_path, auth_path

def run_test():
    main_path, auth_path = setup_test_project()
    
    # We simulate what Visualizer.tsx does:
    # It sends 'code' (of main.py) and 'related_paths' ([auth.py])
    
    with open(main_path, "r") as f:
        main_code = f.read()
        
    payload = {
        "code": main_code,
        "context": "Function: login, File: main.py",
        "project_path": TEST_DIR,
        "related_paths": [auth_path]
    }
    
    print(f"[+] Sending Context-Aware AI Request...")
    try:
        resp = requests.post(API_URL, json=payload)
        resp.raise_for_status()
        result = resp.json()
        
        analysis = result.get("analysis", "")
        print("\n--- AI Analysis Result ---")
        print(analysis[:500] + "...") # Print first 500 chars
        
        # Check if it mentions "hardcoded" or "password"
        if "hardcoded" in analysis.lower() or "하드코딩" in analysis or "super_secret_123" in analysis:
            print("\n[SUCCESS] AI detected the hardcoded password in auth.py!")
        else:
            print("\n[FAIL] AI did NOT mention the hardcoded password.")
            
    except Exception as e:
        print(f"[-] Request failed: {e}")

if __name__ == "__main__":
    run_test()
