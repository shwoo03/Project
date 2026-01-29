
import os
import requests
import json
import shutil

# Script to verify SQL Code Visualization
# We create a python file with SQL queries
# Verify if backend extracts them as 'database' nodes.

TEST_DIR = os.path.join(os.getcwd(), "test_repro_sql")
API_URL = "http://localhost:8000/api/analyze"

def setup_test_project():
    if os.path.exists(TEST_DIR):
        shutil.rmtree(TEST_DIR)
    os.makedirs(TEST_DIR)

    # app.py
    with open(os.path.join(TEST_DIR, "app.py"), "w", encoding="utf-8") as f:
        f.write("""
import sqlite3

def get_users():
    cursor.execute("SELECT * FROM users WHERE active=1")
    return cursor.fetchall()

def create_post(title, body):
    # SQL Injection potential?
    query = f"INSERT INTO posts (title, body) VALUES ('{title}', '{body}')"
    cursor.execute(query)

@app.route("/admin")
def admin_panel():
    cursor.execute("UPDATE config SET value=1 WHERE key='maint_mode'")
""")
    
    print(f"[+] Created test SQL project at: {TEST_DIR}")

def run_test():
    print(f"[+] Sending analysis request to {API_URL}...")
    try:
        resp = requests.post(API_URL, json={"path": TEST_DIR})
        resp.raise_for_status()
        data = resp.json()
        
        endpoints = data.get("endpoints", [])
        print(f"[DEBUG] Endpoints found: {[e['path'] for e in endpoints]}")
        
        sql_nodes_count = 0
        tables_found = set()
        
        for ep in endpoints:
            # Check children of endpoints (Functions/Routes)
            for child in ep.get("children", []):
                if child.get("type") == "database":
                    sql_nodes_count += 1
                    tables_found.add(child.get("path"))
                    print(f"[FOUND] SQL Node: {child.get('path')} in {ep.get('path')}")

        if "Table: users" in tables_found and "Table: posts" in tables_found and "Table: config" in tables_found:
             print("[SUCCESS] All tables (users, posts, config) extracted!")
        else:
             print(f"[FAIL] Missing tables. Found: {tables_found}")

    except Exception as e:
        print(f"[-] API Request failed: {e}")

if __name__ == "__main__":
    setup_test_project()
    run_test()
