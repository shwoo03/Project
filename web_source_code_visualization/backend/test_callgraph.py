"""Test Call Graph Analyzer"""
import sys
sys.path.insert(0, r'c:\Users\dntmd\OneDrive\Desktop\my\Project\web_source_code_visualization\backend')

from core.call_graph_analyzer import CallGraphAnalyzer

cg = CallGraphAnalyzer()
result = cg.analyze_project(r'C:\Users\dntmd\OneDrive\Desktop\wargame\Dreamhack\웹\새싹\cookie')

print(f"Total Nodes: {len(result['nodes'])}")
print(f"Total Edges: {len(result['edges'])}")
print(f"Entry Points: {result['entry_points']}")
print(f"Sinks: {result['sinks']}")

print("\n=== Nodes ===")
for node in result['nodes']:
    print(f"  {node['name']} | type={node['node_type']} | entry={node['is_entry_point']} | sink={node['is_sink']}")
    print(f"    file: {node['file_path']}")
    print(f"    line: {node['line_number']}-{node['end_line']}")

print("\n=== Edges ===")
for edge in result['edges'][:10]:
    print(f"  {edge['source_id']} -> {edge['target_id']}")
