"""
Python Parser for Web Application Analysis.

This parser uses tree-sitter to analyze Python web applications (Flask, FastAPI, Django)
and extract routes, inputs, function calls, templates, and security-related information.

Refactored from a single 1400-line file into modular components:
- frameworks/: Framework-specific extractors (Flask, FastAPI, Django)
- helpers.py: Shared helper functions
- extractors.py: Basic extraction utilities
- taint_analyzer.py: Taint flow analysis
"""

from typing import List, Dict, Any, Optional
from tree_sitter import Language, Parser
import tree_sitter_python
import os
import re

from .base import BaseParser
from .extractors import (
    SANITIZER_FUNCTIONS,
    SANITIZER_BASE_NAMES,
    get_node_text,
    is_sanitizer,
    extract_path_params,
    extract_template_usage,
    find_template_path,
)
from .helpers import (
    extract_render_template_context,
    extract_params,
    extract_sanitizers,
    extract_identifiers,
    InputExtractor,
    SanitizationAnalyzer,
)
from .frameworks import FlaskExtractor, FastAPIExtractor, DjangoExtractor, FrameworkRegistry
from .frameworks.base_framework import RouteInfo
from models import EndpointNodes, Parameter

# Import taint analysis
from ..taint_analyzer import (
    TaintAnalyzer, TaintSource, TaintSink, TaintFlow,
    DANGEROUS_SINKS, detect_sink, TaintType
)


class PythonParser(BaseParser):
    """
    Python source code parser for web application analysis.
    
    Supports:
    - Flask: @app.route decorators, request.args/form/cookies/etc.
    - FastAPI: @app.get/post/etc. decorators, Path/Query/Body parameters
    - Django: views.py, urls.py, DRF viewsets/serializers
    
    Features:
    - Route detection and path parameter extraction
    - User input detection and tracking
    - Function call analysis with cross-file resolution
    - Template rendering analysis (render_template)
    - Sanitizer detection and flow analysis
    - Taint analysis (source → sink tracking)
    - SQL query extraction
    - Dangerous sink detection
    """
    
    def __init__(self):
        self.LANGUAGE = Language(tree_sitter_python.language())
        self.parser = Parser(self.LANGUAGE)
        
        # Register framework extractors
        self._flask = FlaskExtractor()
        self._fastapi = FastAPIExtractor()
        self._django = DjangoExtractor()
        FrameworkRegistry.register(self._flask)
        FrameworkRegistry.register(self._fastapi)
        FrameworkRegistry.register(self._django)

    def can_parse(self, file_path: str) -> bool:
        return file_path.endswith(".py")

    def parse(self, file_path: str, content: str, 
              global_symbols: Dict[str, Dict] = None, 
              symbol_table: Any = None) -> List[EndpointNodes]:
        """
        Parse a Python file and extract security-relevant information.
        
        Args:
            file_path: Path to the file being parsed
            content: Source code content
            global_symbols: Pre-scanned function/class definitions
            symbol_table: Global symbol table for cross-file resolution
            
        Returns:
            List of EndpointNodes representing routes and functions
        """
        tree = self.parser.parse(bytes(content, "utf8"))
        root_node = tree.root_node
        endpoints = []
        
        # Use local scan if no global symbols provided
        if global_symbols is None:
            global_symbols = self.scan_symbols(file_path, content)

        # Extract imports for cross-file resolution
        file_imports = self.extract_imports(root_node, content)
        
        # Helper function for text extraction (closure over content)
        def get_text(node) -> str:
            return node.text.decode('utf-8')
        
        # Initialize extractors
        input_extractor = InputExtractor(get_text)
        sanitization_analyzer = SanitizationAnalyzer(get_text, input_extractor)
        
        def find_framework_and_route(decorator_text: str) -> Optional[RouteInfo]:
            """Detect framework and parse route information."""
            # Try Flask
            if self._flask.is_route_decorator(decorator_text):
                return self._flask.parse_route(decorator_text)
            # Try FastAPI
            if self._fastapi.is_route_decorator(decorator_text):
                return self._fastapi.parse_route(decorator_text)
            # Try Django/DRF
            if self._django.is_route_decorator(decorator_text):
                return self._django.parse_route(decorator_text)
            return None

        def extract_calls(node, defined_funcs: Dict[str, Dict], 
                         file_imports: Dict[str, str] = None,
                         symbol_table: Any = None) -> List[Dict]:
            """Extract function calls from an AST node."""
            calls = []
            
            if node.type == 'call':
                func_node = node.child_by_field_name('function')
                if func_node:
                    func_name = get_text(func_node)
                    
                    # Handle render_template specially
                    if func_name == "render_template":
                        template_call = self._extract_template_call(
                            node, file_path, get_text
                        )
                        if template_call:
                            calls.append(template_call)
                    else:
                        # General function call resolution
                        def_info = self._resolve_function(
                            func_name, defined_funcs, file_imports, symbol_table
                        )
                        if def_info:
                            calls.append({
                                "name": func_name,
                                "def_info": def_info
                            })
            
            for child in node.children:
                calls.extend(extract_calls(child, defined_funcs, file_imports, symbol_table))
            return calls

        def traverse_clean(node, defined_funcs: Dict[str, Dict]):
            """Traverse AST and extract endpoints."""
            should_recurse = True
            
            if node.type == 'decorated_definition':
                decorator = self._find_decorator(node)
                definition = self._find_definition(node)
                
                if decorator and definition:
                    decorator_text = get_text(decorator)
                    route_info = find_framework_and_route(decorator_text)
                    
                    if route_info and route_info.is_route:
                        endpoint = self._build_route_endpoint(
                            node, definition, route_info, 
                            file_path, content, get_text,
                            defined_funcs, file_imports, symbol_table,
                            input_extractor, sanitization_analyzer,
                            extract_calls
                        )
                        endpoints.append(endpoint)
                        should_recurse = False

            elif node.type == 'function_definition':
                endpoint = self._build_function_endpoint(
                    node, file_path, content, get_text,
                    defined_funcs, file_imports, symbol_table,
                    input_extractor, sanitization_analyzer,
                    extract_calls
                )
                endpoints.append(endpoint)
            
            if should_recurse:
                for child in node.children:
                    traverse_clean(child, defined_funcs)

        traverse_clean(root_node, global_symbols)
        
        # Post-process: Hide helper functions if routes exist
        has_routes = any(ep.type == 'root' for ep in endpoints)
        if has_routes:
            endpoints = [ep for ep in endpoints if ep.type == 'root']
            
        return endpoints

    def _find_decorator(self, node):
        """Find decorator in a decorated_definition node."""
        decorator = node.child_by_field_name('decorator')
        if not decorator:
            for child in node.children:
                if child.type == 'decorator':
                    return child
        return decorator
    
    def _find_definition(self, node):
        """Find function/class definition in a decorated_definition node."""
        definition = node.child_by_field_name('definition')
        if not definition:
            for child in node.children:
                if child.type in ('function_definition', 'class_definition'):
                    return child
        return definition

    def _extract_template_call(self, call_node, file_path: str, 
                               get_text) -> Optional[Dict]:
        """Extract template call information from render_template()."""
        args = call_node.child_by_field_name('arguments')
        if not args:
            return None
            
        first_arg = args.child(1)
        if not first_arg or first_arg.type != "string":
            return None
            
        template_name = get_text(first_arg).strip('"\'')
        base_dir = os.path.dirname(file_path)
        
        found_path = find_template_path(base_dir, template_name)
        if not found_path:
            return None
            
        context_vars = extract_render_template_context(args, get_text)
        template_usage = extract_template_usage(found_path)
        
        try:
            with open(found_path, "r", encoding="utf-8") as f:
                lines = f.readlines()
                end_line = len(lines)
        except:
            end_line = 0

        return {
            "name": f"Template: {template_name}",
            "def_info": {
                "file_path": found_path,
                "start_line": 1,
                "end_line": end_line,
                "template_context": context_vars,
                "template_usage": template_usage
            }
        }

    def _resolve_function(self, func_name: str, 
                         defined_funcs: Dict[str, Dict],
                         file_imports: Dict[str, str],
                         symbol_table: Any) -> Optional[Dict]:
        """Resolve function definition location."""
        def_info = None
        
        # Symbol Table Resolution
        if symbol_table:
            resolved = symbol_table.lookup(func_name, imports=file_imports)
            if resolved:
                def_info = {
                    "file_path": resolved.file_path,
                    "start_line": resolved.line_number,
                    "end_line": resolved.end_line_number,
                    "filters": [],
                    "sanitization": []
                }
        
        # Local Definition
        if not def_info and func_name in defined_funcs:
            def_info = defined_funcs[func_name]
        
        return def_info

    def _build_route_endpoint(self, decorated_node, func_node, route_info: RouteInfo,
                              file_path: str, content: str, get_text,
                              defined_funcs: Dict, file_imports: Dict,
                              symbol_table: Any, input_extractor: InputExtractor,
                              sanitization_analyzer: SanitizationAnalyzer,
                              extract_calls_fn) -> EndpointNodes:
        """Build an EndpointNodes object for a route."""
        
        params = extract_params(func_node, get_text)
        
        # Mark path params
        for p in params:
            if p.name in route_info.path_params:
                p.source = "path"
        
        inputs = input_extractor.find_inputs_in_node(func_node)
        
        # FastAPI: Treat function params as inputs
        if self._fastapi.is_route_decorator(get_text(self._find_decorator(decorated_node))):
            for p in params:
                if p.source == "unknown" and p.name not in ["self", "cls", "request", "req"]:
                    p_source = "query" if route_info.method == "GET" else "body"
                    if not any(i['name'] == p.name for i in inputs):
                        inputs.append({
                            "name": p.name,
                            "source": p_source.upper() if p_source != "query" else "GET",
                            "type": "UserInput"
                        })
        
        calls = extract_calls_fn(func_node, defined_funcs, file_imports, symbol_table)
        filters = extract_sanitizers(func_node, get_text)
        sanitization = sanitization_analyzer.extract_sanitization_details(func_node)
        sql_nodes = self.extract_sql(func_node, content)
        
        # Extract dangerous sinks and perform taint analysis
        sink_nodes = self.extract_sinks(func_node, content, file_path, get_text)
        taint_flows = self._perform_taint_analysis(
            inputs, sink_nodes, sanitization, func_node, get_text, file_path
        )
        
        # Build children
        children_nodes = []
        children_nodes.extend(sql_nodes)
        children_nodes.extend(sink_nodes)  # Add sink nodes
        
        for inp in inputs:
            children_nodes.append(EndpointNodes(
                id=f"{file_path}:{decorated_node.start_point.row}:input:{inp['name']}",
                path=inp['name'],
                method=inp['source'],
                language="python",
                file_path=file_path,
                line_number=decorated_node.start_point.row + 1,
                type="input"
            ))
        
        for call_info in calls:
            def_info = call_info['def_info']
            children_nodes.append(EndpointNodes(
                id=f"{file_path}:{decorated_node.start_point.row}:call:{call_info['name']}",
                path=call_info['name'],
                method="CALL",
                language="python",
                file_path=def_info['file_path'],
                line_number=def_info['start_line'],
                end_line_number=def_info['end_line'],
                filters=def_info.get("filters", []),
                sanitization=def_info.get("sanitization", []),
                template_context=def_info.get("template_context", []),
                template_usage=def_info.get("template_usage", []),
                type="child"
            ))
        
        return EndpointNodes(
            id=f"{file_path}:{decorated_node.start_point.row}",
            path=route_info.path,
            method=route_info.method,
            language="python",
            file_path=file_path,
            line_number=decorated_node.start_point.row + 1,
            params=params,
            children=children_nodes,
            type="root",
            filters=filters,
            sanitization=sanitization,
            end_line_number=decorated_node.end_point.row + 1
        )

    def _build_function_endpoint(self, func_node, file_path: str, content: str,
                                 get_text, defined_funcs: Dict, file_imports: Dict,
                                 symbol_table: Any, input_extractor: InputExtractor,
                                 sanitization_analyzer: SanitizationAnalyzer,
                                 extract_calls_fn) -> EndpointNodes:
        """Build an EndpointNodes object for a standalone function."""
        
        name_node = func_node.child_by_field_name('name')
        func_name = get_text(name_node)
        
        params = extract_params(func_node, get_text)
        inputs = input_extractor.find_inputs_in_node(func_node)
        calls = extract_calls_fn(func_node, defined_funcs, file_imports, symbol_table)
        filters = extract_sanitizers(func_node, get_text)
        sanitization = sanitization_analyzer.extract_sanitization_details(func_node)
        sql_nodes = self.extract_sql(func_node, content)
        
        # Extract dangerous sinks and perform taint analysis
        sink_nodes = self.extract_sinks(func_node, content, file_path, get_text)
        taint_flows = self._perform_taint_analysis(
            inputs, sink_nodes, sanitization, func_node, get_text, file_path
        )
        
        children_nodes = []
        children_nodes.extend(sql_nodes)
        children_nodes.extend(sink_nodes)  # Add sink nodes
        
        for inp in inputs:
            children_nodes.append(EndpointNodes(
                id=f"{file_path}:{func_node.start_point.row}:input:{inp['name']}",
                path=inp['name'],
                method=inp['source'],
                language="python",
                file_path=file_path,
                line_number=func_node.start_point.row + 1,
                type="input"
            ))
        
        for call_info in calls:
            def_info = call_info['def_info']
            children_nodes.append(EndpointNodes(
                id=f"{file_path}:{func_node.start_point.row}:call:{call_info['name']}",
                path=call_info['name'],
                method="CALL",
                language="python",
                file_path=file_path,
                line_number=func_node.start_point.row + 1,
                metadata={"definition": def_info},
                filters=def_info.get("filters", []),
                sanitization=def_info.get("sanitization", []),
                template_context=def_info.get("template_context", []),
                template_usage=def_info.get("template_usage", []),
                type="call"
            ))
        
        return EndpointNodes(
            id=f"{file_path}:{func_node.start_point.row}",
            path=func_name,
            method="FUNC",
            language="python",
            file_path=file_path,
            line_number=func_node.start_point.row + 1,
            params=params,
            children=children_nodes,
            type="child",
            filters=filters,
            sanitization=sanitization,
            end_line_number=func_node.end_point.row + 1
        )

    def scan_symbols(self, file_path: str, content: str) -> Dict[str, Dict]:
        """
        Pre-scan a file to build a symbol table of defined functions and classes.
        
        This is used for resolving function calls to their definitions.
        """
        tree = self.parser.parse(bytes(content, "utf8"))
        root_node = tree.root_node
        
        def get_text(node):
            return node.text.decode('utf-8')

        defined_funcs = {}
        
        def scan_funcs(n):
            if n.type == 'function_definition':
                name_node = n.child_by_field_name('name')
                if name_node:
                    fn_name = get_text(name_node)
                    filters = extract_sanitizers(n, get_text)
                    
                    defined_funcs[fn_name] = {
                        "type": "function",
                        "file_path": file_path,
                        "start_line": n.start_point.row + 1,
                        "end_line": n.end_point.row + 1,
                        "filters": filters,
                        "sanitization": [],
                        "template_context": [],
                        "template_usage": []
                    }
                    
            elif n.type == 'class_definition':
                name_node = n.child_by_field_name('name')
                if name_node:
                    class_name = get_text(name_node)
                    
                    inherits = []
                    args_node = n.child_by_field_name('superclasses')
                    if args_node:
                        for child in args_node.children:
                            if child.is_named:
                                inherits.append(get_text(child))

                    defined_funcs[class_name] = {
                        "type": "class",
                        "file_path": file_path,
                        "start_line": n.start_point.row + 1,
                        "end_line": n.end_point.row + 1,
                        "inherits": inherits,
                        "filters": [],
                        "sanitization": [],
                        "template_context": [],
                        "template_usage": []
                    }
                    
            for c in n.children:
                scan_funcs(c)
            
        scan_funcs(root_node)
        return defined_funcs

    def extract_sql(self, node, content: str) -> List[EndpointNodes]:
        """Extract SQL queries from string literals in the code."""
        sql_nodes = []
        nodes_to_visit = [node]
        seen_tables = set()

        while nodes_to_visit:
            curr = nodes_to_visit.pop()
            
            if curr.type in ('string', 'string_content'):
                text = content[curr.start_byte:curr.end_byte]
                clean_text = text.strip("'\"")
                
                if re.match(r"^\s*(SELECT|INSERT|UPDATE|DELETE)\s", clean_text, re.IGNORECASE):
                    table_match = re.search(
                        r"(?:FROM|INTO|UPDATE)\s+([a-zA-Z0-9_]+)", 
                        clean_text, re.IGNORECASE
                    )
                    if table_match:
                        table_name = table_match.group(1)
                        if table_name not in seen_tables:
                            seen_tables.add(table_name)
                            sql_nodes.append(EndpointNodes(
                                id=f"sql-{table_name}-{curr.start_point[0]}",
                                path=f"Table: {table_name}",
                                method="SQL",
                                language="sql",
                                type="database",
                                file_path="database",
                                line_number=curr.start_point[0] + 1,
                                end_line_number=curr.end_point[0] + 1,
                                params=[],
                                children=[]
                            ))
            
            for child in curr.children:
                nodes_to_visit.append(child)
                
        return sql_nodes

    def extract_imports(self, node, content: str) -> Dict[str, str]:
        """
        Extract import statements and build an alias -> full_name mapping.
        
        Examples:
        - from models import User -> {'User': 'models.User'}
        - import utils -> {'utils': 'utils'}
        - import utils as u -> {'u': 'utils'}
        """
        imports = {}
        stack = [node]
        
        while stack:
            curr = stack.pop()
            
            if curr.type == 'import_from_statement':
                module_node = curr.child_by_field_name('module_name')
                if module_node:
                    module_name = content[module_node.start_byte:module_node.end_byte]
                    
                    for child in curr.children:
                        if child.type == 'aliased_import':
                            name_node = child.child_by_field_name('name')
                            alias_node = child.child_by_field_name('alias')
                            if name_node and alias_node:
                                real_name = content[name_node.start_byte:name_node.end_byte]
                                alias = content[alias_node.start_byte:alias_node.end_byte]
                                imports[alias] = f"{module_name}.{real_name}"
                        elif child.type == 'dotted_name' and child != module_node:
                            name = content[child.start_byte:child.end_byte]
                            imports[name] = f"{module_name}.{name}"
                        elif child.type == 'identifier' and child != module_node:
                            name = content[child.start_byte:child.end_byte]
                            imports[name] = f"{module_name}.{name}"
                            
            elif curr.type == 'import_statement':
                for child in curr.children:
                    if child.type == 'dotted_name':
                        name = content[child.start_byte:child.end_byte]
                        imports[name] = name
                    elif child.type == 'aliased_import':
                        name_node = child.child_by_field_name('name')
                        alias_node = child.child_by_field_name('alias')
                        if name_node and alias_node:
                            real_name = content[name_node.start_byte:name_node.end_byte]
                            alias = content[alias_node.start_byte:alias_node.end_byte]
                            imports[alias] = real_name
            
            if curr.type not in ('function_definition', 'class_definition'):
                for c in curr.children:
                    stack.append(c)
                    
        return imports

    def extract_sinks(self, node, content: str, file_path: str, get_text) -> List[EndpointNodes]:
        """
        Extract dangerous sink function calls from the code.
        
        Sinks are functions that can cause security vulnerabilities when
        receiving untrusted user input (e.g., os.system, eval, cursor.execute).
        """
        sink_nodes = []
        nodes_to_visit = [node]
        seen_sinks = set()

        while nodes_to_visit:
            curr = nodes_to_visit.pop()
            
            if curr.type == 'call':
                func_node = curr.child_by_field_name('function')
                if func_node:
                    func_name = get_text(func_node)
                    sink_info = detect_sink(func_name)
                    
                    if sink_info:
                        taint_type, severity = sink_info
                        line = curr.start_point[0] + 1
                        sink_key = (func_name, line)
                        
                        if sink_key not in seen_sinks:
                            seen_sinks.add(sink_key)
                            
                            # Extract arguments
                            args_text = []
                            args_node = curr.child_by_field_name('arguments')
                            if args_node:
                                for child in args_node.children:
                                    if child.is_named:
                                        args_text.append(get_text(child))
                            
                            sink_nodes.append(EndpointNodes(
                                id=f"sink-{func_name}-{line}",
                                path=f"⚠️ {func_name}",
                                method=taint_type.value.upper(),
                                language="python",
                                type="sink",
                                file_path=file_path,
                                line_number=line,
                                end_line_number=curr.end_point[0] + 1,
                                params=[],
                                children=[],
                                metadata={
                                    "sink_type": taint_type.value,
                                    "severity": severity,
                                    "args": args_text,
                                    "dangerous": True
                                }
                            ))
            
            for child in curr.children:
                nodes_to_visit.append(child)
                
        return sink_nodes

    def _perform_taint_analysis(self, inputs: List[Dict], sink_nodes: List[EndpointNodes],
                                sanitization: List[Dict], func_node, get_text,
                                file_path: str) -> List[Dict]:
        """
        Perform taint analysis to track data flow from inputs to sinks.
        
        Returns:
            List of taint flow information dicts
        """
        if not inputs or not sink_nodes:
            return []
        
        taint_analyzer = TaintAnalyzer()
        
        # Register sources (inputs)
        for inp in inputs:
            source = TaintSource(
                name=inp['name'],
                source_type=inp.get('source', 'unknown'),
                line=0,  # TODO: Get actual line
                file_path=file_path
            )
            taint_analyzer.add_source(source)
        
        # Register sinks
        for sink_node in sink_nodes:
            sink = TaintSink(
                name=sink_node.path.replace("⚠️ ", ""),
                category=TaintType(sink_node.metadata.get("sink_type", "general")),
                line=sink_node.line_number,
                file_path=file_path,
                args=sink_node.metadata.get("args", []),
                severity=sink_node.metadata.get("severity", "HIGH")
            )
            taint_analyzer.add_sink(sink)
        
        # Register sanitizers
        for san in sanitization:
            taint_analyzer.add_sanitizer(san)
        
        # Track variable assignments
        self._track_assignments(func_node, get_text, taint_analyzer)
        
        # Analyze flows
        flows = taint_analyzer.analyze()
        
        # Convert to serializable format
        flow_data = []
        for flow in flows:
            flow_data.append({
                "source": {
                    "name": flow.source.name,
                    "type": flow.source.source_type,
                    "line": flow.source.line
                },
                "sink": {
                    "name": flow.sink.name,
                    "category": flow.sink.category.value,
                    "severity": flow.sink.severity,
                    "line": flow.sink.line
                },
                "path": flow.path,
                "sanitized": flow.sanitized,
                "sanitizer": flow.sanitizer_name,
                "vulnerable": not flow.sanitized
            })
        
        return flow_data

    def _track_assignments(self, node, get_text, taint_analyzer: TaintAnalyzer):
        """Track variable assignments for taint propagation."""
        nodes_to_visit = [node]
        
        while nodes_to_visit:
            curr = nodes_to_visit.pop()
            
            if curr.type == 'assignment':
                left = curr.child_by_field_name('left')
                right = curr.child_by_field_name('right')
                
                if left and right:
                    target = get_text(left)
                    source_expr = get_text(right)
                    line = curr.start_point[0] + 1
                    
                    taint_analyzer.track_assignment(target, source_expr, line)
            
            for child in curr.children:
                nodes_to_visit.append(child)
