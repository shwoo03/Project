
from core.parser.python import PythonParser
import os

file_path = r"C:\Users\dntmd\OneDrive\Desktop\my\프로젝트\Project\web_source_code_visualization\plob\xss-1\deploy\app.py"

try:
    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()

    parser = PythonParser()
    nodes = parser.parse(file_path, content)
    
    print(f"Found {len(nodes)} endpoints")
    for n in nodes:
        print(f"- {n.path} ({n.method})")
        for c in n.children:
            print(f"  -> {c.path} ({c.type})")

except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()
