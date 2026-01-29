
import sys
import os

# Add backend to path
sys.path.append(os.path.join(os.getcwd(), "backend"))

from core.parser.python import PythonParser

def test_sql_extraction():
    parser = PythonParser()
    
    code = """
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
    """
    
    print("Parsing code...")
    # tree = parser.parser.parse(bytes(code, "utf8"))
    # nodes = parser.extract_sql(tree.root_node, code)
    
    # We can also call parse() directly to see full structure
    endpoints = parser.parse("test_file.py", code)
    
    print(f"Endpoints found: {len(endpoints)}")
    
    found_sql = []
    
    for ep in endpoints:
        print(f"Endpoint: {ep.path} ({ep.type})")
        if ep.children:
            for child in ep.children:
                print(f"  - Child: {child.path} ({child.type})")
                if child.type == 'database':
                    found_sql.append(child.path)
                    
    print(f"Total SQL Nodes found: {len(found_sql)}")
    print(f"SQL Nodes: {found_sql}")

if __name__ == "__main__":
    test_sql_extraction()
