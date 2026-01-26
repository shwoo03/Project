import os
import sys
# Add current dir to path to find core/models
sys.path.append(os.getcwd())

from core.parser import ParserManager

def test_full_parse():
    path = os.getcwd() # backend folder
    print(f"Scanning path: {path}")
    
    manager = ParserManager()
    
    count = 0
    for root, _, files in os.walk(path):
        if "venv" in root or "__pycache__" in root:
            continue
            
        for file in files:
            file_path = os.path.join(root, file)
            parser = manager.get_parser(file_path)
            
            if parser:
                print(f"Parsing {file} with {parser.__class__.__name__}")
                try:
                    with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                        content = f.read()
                    endpoints = parser.parse(file_path, content)
                    for ep in endpoints:
                        print(f"  - Found: {ep.method} {ep.path} ({ep.type})")
                        count += 1
                except Exception as e:
                    print(f"Error: {e}")

    print(f"Total endpoints/nodes found: {count}")

if __name__ == "__main__":
    test_full_parse()
