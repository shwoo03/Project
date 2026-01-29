"""Test Call Graph after UTF-8 fix"""
import sys
sys.path.insert(0, r'c:\Users\dntmd\OneDrive\Desktop\my\Project\web_source_code_visualization\backend')

from core.call_graph_analyzer import CallGraphAnalyzer

# Test with Korean path
test_path = r'C:\Users\dntmd\OneDrive\Desktop\wargame\Dreamhack\웹\새싹\cookie'

cga = CallGraphAnalyzer()
result = cga.analyze_project(test_path)

print("=== Call Graph Analysis Results ===")
print(f"\nTotal nodes: {len(result.get('nodes', []))}")
print(f"Total edges: {len(result.get('edges', []))}")

print("\n=== Functions Found ===")
for node in result.get('nodes', []):
    print(f"  - {node.get('name', 'N/A')} ({node.get('node_type', 'N/A')}) at line {node.get('line_start', 'N/A')}")
    print(f"      Keys: {list(node.keys())}")

print("\n=== Call Edges ===")
for edge in result.get('edges', []):
    print(f"  {edge['source']} -> {edge['target']}")
