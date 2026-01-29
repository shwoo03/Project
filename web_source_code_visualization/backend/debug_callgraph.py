"""Debug Call Graph parsing"""
import sys
sys.path.insert(0, r'c:\Users\dntmd\OneDrive\Desktop\my\Project\web_source_code_visualization\backend')

import tree_sitter_python
from tree_sitter import Language, Parser

# Read test file as BYTES (not string!)
with open(r'C:\Users\dntmd\OneDrive\Desktop\wargame\Dreamhack\웹\새싹\cookie\app.py', 'rb') as f:
    content_bytes = f.read()

# Also read as string for display
content_str = content_bytes.decode('utf-8', errors='ignore')

print("=== File Content (first 500 chars) ===")
print(content_str[:500])
print("\n" + "="*50)

# Parse with BYTES
parser = Parser(Language(tree_sitter_python.language()))
tree = parser.parse(content_bytes)

def get_node_text(node, content_bytes):
    """Properly extract text using byte offsets"""
    return content_bytes[node.start_byte:node.end_byte].decode('utf-8', errors='ignore')

def print_tree(node, content_bytes, indent=0):
    text = get_node_text(node, content_bytes)
    if len(text) > 50:
        text = text[:50] + "..."
    text = text.replace('\n', '\\n')
    print("  " * indent + f"{node.type}: '{text}'")
    
    for child in node.children:
        print_tree(child, content_bytes, indent + 1)

# Find function definitions
def find_functions(node, content_bytes, results=None):
    if results is None:
        results = []
    
    if node.type == 'function_definition':
        # Get name field
        name_node = node.child_by_field_name('name')
        if name_node:
            name = get_node_text(name_node, content_bytes)
            print(f"\nFound function_definition:")
            print(f"  name node type: {name_node.type}")
            print(f"  name text: '{name}'")
            print(f"  line: {node.start_point[0]+1}-{node.end_point[0]+1}")
        else:
            print(f"\nfunction_definition without name field at line {node.start_point[0]+1}")
            # Print all children
            print("  Children:")
            for i, child in enumerate(node.children):
                child_text = get_node_text(child, content_bytes)[:30].replace('\n', '\\n')
                field = child.field_name if hasattr(child, 'field_name') else None
                print(f"    [{i}] type={child.type}, field={field}, text='{child_text}'")
        
        results.append(node)
    
    for child in node.children:
        find_functions(child, content_bytes, results)
    
    return results

print("\n=== Searching for function definitions ===")
functions = find_functions(tree.root_node, content_bytes)
print(f"\nTotal functions found: {len(functions)}")
