"""
Call Graph Analyzer.

Builds a call graph showing function-to-function call relationships.
This enables:
- Understanding code flow
- Finding paths from entry points to sinks
- Identifying dead code
- Tracing data flow through function calls
"""

import os
import re
from typing import List, Dict, Set, Optional, Tuple
from dataclasses import dataclass, field
import tree_sitter_python
import tree_sitter_javascript
from tree_sitter import Language, Parser

# Try importing TypeScript support
try:
    import tree_sitter_typescript
    HAS_TYPESCRIPT = True
except ImportError:
    HAS_TYPESCRIPT = False


@dataclass
class FunctionInfo:
    """Information about a function/method definition."""
    name: str
    qualified_name: str
    file_path: str
    line_start: int
    line_end: int
    node_type: str  # function, method, class
    class_name: Optional[str] = None
    decorators: List[str] = field(default_factory=list)
    calls: List[Tuple[str, int]] = field(default_factory=list)  # (called_name, line)
    is_entry_point: bool = False
    is_sink: bool = False


class CallGraphAnalyzer:
    """
    Analyzes source code to build a call graph.
    
    Supports:
    - Python (functions, methods, classes)
    - JavaScript/TypeScript (functions, arrow functions, methods)
    """
    
    # Dangerous sink functions
    PYTHON_SINKS = {
        "eval", "exec", "compile", "open",
        "os.system", "os.popen", "os.exec", "os.spawn",
        "subprocess.call", "subprocess.run", "subprocess.Popen",
        "pickle.loads", "yaml.load",
        "cursor.execute", "db.execute", "execute",
        "render_template_string", "Markup",
        "__import__", "importlib.import_module",
    }
    
    JS_SINKS = {
        "eval", "Function", "setTimeout", "setInterval",
        "document.write", "innerHTML", "outerHTML",
        "insertAdjacentHTML", "document.writeln",
        "exec", "execSync", "spawn", "spawnSync",
        "child_process.exec", "child_process.spawn",
        "fs.readFile", "fs.writeFile",
    }
    
    def __init__(self):
        self.functions: Dict[str, FunctionInfo] = {}
        self.call_edges: List[Tuple[str, str, int]] = []  # (caller, callee, line)
        
        # Initialize parsers
        self.py_parser = Parser(Language(tree_sitter_python.language()))
        self.js_parser = Parser(Language(tree_sitter_javascript.language()))
        
        if HAS_TYPESCRIPT:
            self.ts_parser = Parser(Language(tree_sitter_typescript.language_typescript()))
            self.tsx_parser = Parser(Language(tree_sitter_typescript.language_tsx()))
        else:
            self.ts_parser = None
            self.tsx_parser = None
    
    def analyze_project(self, root_path: str) -> Dict:
        """
        Analyze an entire project and build the call graph.
        
        Returns:
            Dict with nodes, edges, entry_points, sinks
        """
        self.functions.clear()
        self.call_edges.clear()
        
        # Walk through all source files
        for dirpath, dirnames, filenames in os.walk(root_path):
            # Skip common non-source directories
            dirnames[:] = [d for d in dirnames if d not in {
                '__pycache__', 'node_modules', '.git', '.venv', 'venv',
                'dist', 'build', '.next', 'coverage'
            }]
            
            for filename in filenames:
                filepath = os.path.join(dirpath, filename)
                
                if filename.endswith('.py'):
                    self._analyze_python_file(filepath)
                elif filename.endswith('.js') or filename.endswith('.jsx'):
                    self._analyze_javascript_file(filepath)
                elif (filename.endswith('.ts') or filename.endswith('.tsx')) and self.ts_parser:
                    self._analyze_typescript_file(filepath)
        
        # Resolve call edges
        self._resolve_calls()
        
        return self._build_graph_data()
    
    def _analyze_python_file(self, filepath: str):
        """Analyze a Python file for functions and calls."""
        try:
            with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
        except Exception:
            return
        
        tree = self.py_parser.parse(content.encode())
        self._extract_python_definitions(tree.root_node, filepath, content, None)
    
    def _extract_python_definitions(self, node, filepath: str, content: str, 
                                     current_class: Optional[str], depth: int = 0):
        """Recursively extract Python function/class definitions."""
        
        if node.type == 'class_definition':
            class_name = self._get_child_text(node, 'name', content)
            if class_name:
                # Register class
                qualified = f"{os.path.basename(filepath)}::{class_name}"
                self.functions[qualified] = FunctionInfo(
                    name=class_name,
                    qualified_name=qualified,
                    file_path=filepath,
                    line_start=node.start_point[0] + 1,
                    line_end=node.end_point[0] + 1,
                    node_type="class"
                )
                
                # Process class body
                body = node.child_by_field_name('body')
                if body:
                    for child in body.children:
                        self._extract_python_definitions(child, filepath, content, class_name, depth + 1)
                return
        
        elif node.type == 'function_definition':
            func_name = self._get_child_text(node, 'name', content)
            if func_name:
                # Build qualified name
                if current_class:
                    qualified = f"{os.path.basename(filepath)}::{current_class}.{func_name}"
                    node_type = "method"
                else:
                    qualified = f"{os.path.basename(filepath)}::{func_name}"
                    node_type = "function"
                
                # Check decorators
                decorators = []
                is_entry_point = False
                for child in node.children:
                    if child.type == 'decorator':
                        dec_text = content[child.start_byte:child.end_byte]
                        decorators.append(dec_text)
                        if any(p in dec_text for p in ['@app.route', '@router.', '@api_view', '@action']):
                            is_entry_point = True
                
                # Extract calls within this function
                calls = self._extract_python_calls(node, content)
                
                # Check if any call is a sink
                is_sink = any(call[0] in self.PYTHON_SINKS for call in calls)
                
                self.functions[qualified] = FunctionInfo(
                    name=func_name,
                    qualified_name=qualified,
                    file_path=filepath,
                    line_start=node.start_point[0] + 1,
                    line_end=node.end_point[0] + 1,
                    node_type=node_type,
                    class_name=current_class,
                    decorators=decorators,
                    calls=calls,
                    is_entry_point=is_entry_point,
                    is_sink=is_sink
                )
                return
        
        # Continue traversing
        for child in node.children:
            self._extract_python_definitions(child, filepath, content, current_class, depth)
    
    def _extract_python_calls(self, node, content: str) -> List[Tuple[str, int]]:
        """Extract all function calls within a node."""
        calls = []
        
        def traverse(n):
            if n.type == 'call':
                func = n.child_by_field_name('function')
                if func:
                    call_text = content[func.start_byte:func.end_byte]
                    # Simplify to base function name
                    call_name = call_text.split('.')[-1].split('(')[0]
                    calls.append((call_name, n.start_point[0] + 1))
            
            for child in n.children:
                traverse(child)
        
        # Traverse function body only
        body = node.child_by_field_name('body')
        if body:
            traverse(body)
        
        return calls
    
    def _analyze_javascript_file(self, filepath: str):
        """Analyze a JavaScript file for functions and calls."""
        try:
            with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
        except Exception:
            return
        
        tree = self.js_parser.parse(content.encode())
        self._extract_js_definitions(tree.root_node, filepath, content)
    
    def _analyze_typescript_file(self, filepath: str):
        """Analyze a TypeScript file for functions and calls."""
        try:
            with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
        except Exception:
            return
        
        parser = self.tsx_parser if filepath.endswith('.tsx') else self.ts_parser
        if not parser:
            return
        
        tree = parser.parse(content.encode())
        self._extract_js_definitions(tree.root_node, filepath, content)
    
    def _extract_js_definitions(self, node, filepath: str, content: str, 
                                 current_class: Optional[str] = None):
        """Extract JavaScript/TypeScript function definitions."""
        
        if node.type in ('function_declaration', 'generator_function_declaration'):
            name_node = node.child_by_field_name('name')
            if name_node:
                func_name = content[name_node.start_byte:name_node.end_byte]
                qualified = f"{os.path.basename(filepath)}::{func_name}"
                
                calls = self._extract_js_calls(node, content)
                is_sink = any(call[0] in self.JS_SINKS for call in calls)
                
                self.functions[qualified] = FunctionInfo(
                    name=func_name,
                    qualified_name=qualified,
                    file_path=filepath,
                    line_start=node.start_point[0] + 1,
                    line_end=node.end_point[0] + 1,
                    node_type="function",
                    calls=calls,
                    is_sink=is_sink
                )
        
        elif node.type == 'class_declaration':
            name_node = node.child_by_field_name('name')
            class_name = content[name_node.start_byte:name_node.end_byte] if name_node else None
            
            if class_name:
                qualified = f"{os.path.basename(filepath)}::{class_name}"
                self.functions[qualified] = FunctionInfo(
                    name=class_name,
                    qualified_name=qualified,
                    file_path=filepath,
                    line_start=node.start_point[0] + 1,
                    line_end=node.end_point[0] + 1,
                    node_type="class"
                )
            
            # Process class body
            body = node.child_by_field_name('body')
            if body:
                for child in body.children:
                    if child.type == 'method_definition':
                        self._extract_js_method(child, filepath, content, class_name)
                    else:
                        self._extract_js_definitions(child, filepath, content, class_name)
            return
        
        elif node.type == 'variable_declaration':
            # Check for arrow functions assigned to variables
            for child in node.children:
                if child.type == 'variable_declarator':
                    name_node = child.child_by_field_name('name')
                    value_node = child.child_by_field_name('value')
                    
                    if name_node and value_node and value_node.type == 'arrow_function':
                        func_name = content[name_node.start_byte:name_node.end_byte]
                        qualified = f"{os.path.basename(filepath)}::{func_name}"
                        
                        calls = self._extract_js_calls(value_node, content)
                        is_sink = any(call[0] in self.JS_SINKS for call in calls)
                        
                        # Check if it's a route handler (export default, app.get, etc.)
                        is_entry_point = 'export default' in content[max(0, node.start_byte-20):node.start_byte]
                        
                        self.functions[qualified] = FunctionInfo(
                            name=func_name,
                            qualified_name=qualified,
                            file_path=filepath,
                            line_start=node.start_point[0] + 1,
                            line_end=node.end_point[0] + 1,
                            node_type="function",
                            calls=calls,
                            is_entry_point=is_entry_point,
                            is_sink=is_sink
                        )
        
        # Continue traversing
        for child in node.children:
            self._extract_js_definitions(child, filepath, content, current_class)
    
    def _extract_js_method(self, node, filepath: str, content: str, class_name: str):
        """Extract a JavaScript class method."""
        name_node = node.child_by_field_name('name')
        if name_node:
            method_name = content[name_node.start_byte:name_node.end_byte]
            qualified = f"{os.path.basename(filepath)}::{class_name}.{method_name}"
            
            calls = self._extract_js_calls(node, content)
            is_sink = any(call[0] in self.JS_SINKS for call in calls)
            
            self.functions[qualified] = FunctionInfo(
                name=method_name,
                qualified_name=qualified,
                file_path=filepath,
                line_start=node.start_point[0] + 1,
                line_end=node.end_point[0] + 1,
                node_type="method",
                class_name=class_name,
                calls=calls,
                is_sink=is_sink
            )
    
    def _extract_js_calls(self, node, content: str) -> List[Tuple[str, int]]:
        """Extract all function calls within a JavaScript node."""
        calls = []
        
        def traverse(n):
            if n.type == 'call_expression':
                func = n.child_by_field_name('function')
                if func:
                    call_text = content[func.start_byte:func.end_byte]
                    # Simplify to base function name
                    call_name = call_text.split('.')[-1].split('(')[0]
                    calls.append((call_name, n.start_point[0] + 1))
            
            for child in n.children:
                traverse(child)
        
        traverse(node)
        return calls
    
    def _get_child_text(self, node, field_name: str, content: str) -> Optional[str]:
        """Get text of a named child."""
        child = node.child_by_field_name(field_name)
        if child:
            return content[child.start_byte:child.end_byte]
        return None
    
    def _resolve_calls(self):
        """Resolve function calls to actual function definitions."""
        # Build a map of simple names to qualified names
        name_to_qualified: Dict[str, List[str]] = {}
        
        for qualified, info in self.functions.items():
            if info.name not in name_to_qualified:
                name_to_qualified[info.name] = []
            name_to_qualified[info.name].append(qualified)
        
        # Resolve each call
        for caller_qualified, info in self.functions.items():
            for call_name, line in info.calls:
                # Find possible callees
                possible = name_to_qualified.get(call_name, [])
                
                # For now, take the first match (could be improved with scope analysis)
                if possible:
                    callee_qualified = possible[0]
                    self.call_edges.append((caller_qualified, callee_qualified, line))
    
    def _build_graph_data(self) -> Dict:
        """Build the final call graph data structure."""
        nodes = []
        edges = []
        entry_points = []
        sinks = []
        
        for qualified, info in self.functions.items():
            # Find callers and callees
            callers = [e[0] for e in self.call_edges if e[1] == qualified]
            callees = [e[1] for e in self.call_edges if e[0] == qualified]
            
            node = {
                "id": qualified,
                "name": info.name,
                "qualified_name": qualified,
                "file_path": info.file_path,
                "line_number": info.line_start,
                "end_line": info.line_end,
                "node_type": info.node_type,
                "is_entry_point": info.is_entry_point,
                "is_sink": info.is_sink,
                "callers": callers,
                "callees": callees
            }
            nodes.append(node)
            
            if info.is_entry_point:
                entry_points.append(qualified)
            if info.is_sink:
                sinks.append(qualified)
        
        # Build edges
        for i, (source, target, line) in enumerate(self.call_edges):
            edges.append({
                "id": f"edge-{i}",
                "source_id": source,
                "target_id": target,
                "call_site_line": line,
                "call_type": "direct"
            })
        
        return {
            "nodes": nodes,
            "edges": edges,
            "entry_points": entry_points,
            "sinks": sinks
        }
    
    def find_paths_to_sink(self, entry_point: str, sink: str, max_depth: int = 10) -> List[List[str]]:
        """
        Find all paths from an entry point to a sink.
        
        Returns:
            List of paths, where each path is a list of function qualified names
        """
        paths = []
        visited = set()
        
        def dfs(current: str, path: List[str]):
            if len(path) > max_depth:
                return
            
            if current == sink:
                paths.append(path.copy())
                return
            
            if current in visited:
                return
            
            visited.add(current)
            
            # Find callees of current
            for source, target, _ in self.call_edges:
                if source == current:
                    dfs(target, path + [target])
            
            visited.remove(current)
        
        dfs(entry_point, [entry_point])
        return paths
    
    def get_function_metrics(self) -> Dict:
        """
        Calculate metrics for each function.
        
        Returns:
            Dict with function metrics (fan_in, fan_out, complexity_hint)
        """
        metrics = {}
        
        for qualified, info in self.functions.items():
            fan_in = sum(1 for e in self.call_edges if e[1] == qualified)
            fan_out = sum(1 for e in self.call_edges if e[0] == qualified)
            
            metrics[qualified] = {
                "fan_in": fan_in,
                "fan_out": fan_out,
                "is_hub": fan_in > 5 or fan_out > 5,
                "is_orphan": fan_in == 0 and fan_out == 0 and not info.is_entry_point
            }
        
        return metrics
