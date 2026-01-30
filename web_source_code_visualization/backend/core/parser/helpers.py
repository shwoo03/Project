"""
Helper functions for Python AST traversal and extraction.

These are shared utilities used by the PythonParser class.
Extracted from python.py to reduce file size and improve maintainability.
"""

from typing import List, Dict, Any, Optional, Set, Callable
import re
import os
from models import Parameter

# Import shared constants and functions from extractors
from .extractors import (
    SANITIZER_FUNCTIONS,
    SANITIZER_BASE_NAMES,
    get_node_text,
    is_sanitizer,
    extract_path_params,
    extract_template_usage,
    find_template_path,
)


def extract_render_template_context(args_node, get_text_func: Callable) -> List[Dict]:
    """
    Extract context variables passed to render_template().
    
    Args:
        args_node: Tree-sitter arguments node
        get_text_func: Function to extract text from nodes
        
    Returns:
        List of context variable dicts with 'name' key
    """
    context_vars = []
    if not args_node:
        return context_vars
        
    named_children = [child for child in args_node.children if child.is_named]
    start_index = 0
    
    # Skip first argument if it's a string (template name)
    if named_children and named_children[0].type == "string":
        start_index = 1

    for child in named_children[start_index:]:
        if child.type == "keyword_argument":
            name_node = child.child_by_field_name('name')
            if name_node:
                context_vars.append({"name": get_text_func(name_node)})
        elif child.type == "dictionary":
            for pair in child.children:
                if pair.type != "pair":
                    continue
                key_node = pair.child_by_field_name('key')
                if key_node:
                    key_text = get_text_func(key_node).strip('"\'')
                    context_vars.append({"name": key_text})
        elif child.type == "dictionary_splat":
            context_vars.append({"name": get_text_func(child)})
        else:
            text = get_text_func(child)
            if "=" in text:
                key = text.split("=", 1)[0].strip()
                if key:
                    context_vars.append({"name": key})

    # Deduplicate
    seen = set()
    unique_vars = []
    for item in context_vars:
        name = item.get("name")
        if not name or name in seen:
            continue
        seen.add(name)
        unique_vars.append(item)
    return unique_vars


def extract_params(func_node, get_text_func: Callable) -> List[Parameter]:
    """
    Extract function parameters from a function definition node.
    
    Args:
        func_node: Tree-sitter function_definition node
        get_text_func: Function to extract text from nodes
        
    Returns:
        List of Parameter objects
    """
    params = []
    params_node = func_node.child_by_field_name('parameters')
    if not params_node:
        return params
        
    for child in params_node.children:
        if child.type == 'identifier':
            params.append(Parameter(name=get_text_func(child), type="Any", source="unknown"))
            
        elif child.type == 'typed_parameter':
            name_node = child.child_by_field_name('name')
            if not name_node:
                name_node = child.child(0)
            type_node = child.child_by_field_name('type')
            p_name = get_text_func(name_node) if name_node else "unknown"
            p_type = get_text_func(type_node) if type_node else "Any"
            params.append(Parameter(name=p_name, type=p_type, source="unknown"))
            
        elif child.type == 'default_parameter':
            name_node = child.child_by_field_name('name')
            type_node = child.child_by_field_name('type')
            first_child = child.child(0)
            
            if first_child.type == 'typed_parameter':
                name_node = first_child.child_by_field_name('name')
                if not name_node:
                    name_node = first_child.child(0)
                type_node = first_child.child_by_field_name('type')
            elif not name_node:
                name_node = first_child
                
            p_name = get_text_func(name_node) if name_node else "unknown"
            p_type = get_text_func(type_node) if type_node else "Any"
            params.append(Parameter(name=p_name, type=p_type, source="unknown"))
            
        elif child.type == 'typed_default_parameter':
            name_node = child.child_by_field_name('name')
            if not name_node:
                name_node = child.child(0)
            type_node = child.child_by_field_name('type')
            if not type_node and child.child_count > 2:
                type_node = child.child(2)
            p_name = get_text_func(name_node) if name_node else "unknown"
            p_type = get_text_func(type_node) if type_node else "Any"
            params.append(Parameter(name=p_name, type=p_type, source="unknown"))
            
    return params


def extract_sanitizers(node, get_text_func: Callable) -> List[Dict]:
    """
    Extract sanitizer function calls from an AST node.
    
    Args:
        node: Tree-sitter node to search
        get_text_func: Function to extract text from nodes
        
    Returns:
        List of sanitizer info dicts
    """
    sanitizers = []
    
    if node.type == 'call':
        func_node = node.child_by_field_name('function')
        if func_node:
            func_name = get_text_func(func_node)
            if is_sanitizer(func_name):
                args_list = []
                args_node = node.child_by_field_name('arguments')
                if args_node:
                    for child in args_node.children:
                        if child.is_named:
                            args_list.append(get_text_func(child))
                sanitizers.append({
                    "name": func_name,
                    "args": args_list,
                    "line": node.start_point.row + 1
                })

    for child in node.children:
        sanitizers.extend(extract_sanitizers(child, get_text_func))
    return sanitizers


def extract_identifiers(node, get_text_func: Callable) -> List[str]:
    """
    Recursively extract all identifier names from a node.
    """
    identifiers = []
    if node.type == 'identifier':
        identifiers.append(get_text_func(node))
    for child in node.children:
        identifiers.extend(extract_identifiers(child, get_text_func))
    return identifiers


class InputExtractor:
    """
    Helper class for extracting user inputs from Python code.
    
    Handles various input patterns:
    - request.args.get("param")  -> GET
    - request.form.get("param")  -> POST
    - request.cookies.get("param") -> COOKIE
    - request.headers.get("param") -> HEADER
    - request.files.get("param") -> FILE
    - request.json / request.get_json() -> BODY_JSON
    - request.data / request.get_data() -> BODY_RAW
    - Subscript access: request.args["param"]
    """
    
    def __init__(self, get_text_func: Callable):
        self.get_text = get_text_func
    
    def get_input_from_call(self, node) -> Optional[Dict]:
        """Extract input from a function call node."""
        if node.type != 'call':
            return None
            
        func_node = node.child_by_field_name('function')
        if not func_node or func_node.type != 'attribute':
            return None
            
        text = self.get_text(func_node)
        source_type = self._detect_call_source(text)
        
        if not source_type:
            return None
            
        args = node.child_by_field_name('arguments')
        param_name = self._extract_first_arg_name(args)
        
        if not param_name:
            if source_type == "BODY_JSON":
                param_name = "json"
            elif source_type == "BODY_RAW":
                param_name = "data"
            else:
                return None
        
        return {
            "name": param_name,
            "source": source_type,
            "type": "UserInput"
        }
    
    def get_input_from_subscript(self, node) -> Optional[Dict]:
        """Extract input from a subscript access node."""
        if node.type != 'subscript':
            return None
            
        value_node = node.child_by_field_name('value')
        slice_node = node.child_by_field_name('subscript')
        
        if not value_node or not slice_node:
            return None
            
        value_text = self.get_text(value_node)
        source_type = self._detect_subscript_source(value_text)
        
        if not source_type:
            return None
            
        param_name = self.get_text(slice_node).strip('"\'')
        return {
            "name": param_name,
            "source": source_type,
            "type": "UserInput"
        }
    
    def get_input_from_attribute(self, node) -> Optional[Dict]:
        """Extract input from an attribute access node."""
        if node.type != 'attribute':
            return None
            
        text = self.get_text(node)
        if text == "request.json":
            return {"name": "json", "source": "BODY_JSON", "type": "UserInput"}
        if text == "request.data":
            return {"name": "data", "source": "BODY_RAW", "type": "UserInput"}
        return None
    
    def find_inputs_in_node(self, node) -> List[Dict]:
        """Recursively find all inputs in a node."""
        inputs = []
        
        if node.type == 'call':
            input_info = self.get_input_from_call(node)
            if input_info:
                inputs.append(input_info)
        elif node.type == 'subscript':
            input_info = self.get_input_from_subscript(node)
            if input_info:
                inputs.append(input_info)
        elif node.type == 'attribute':
            input_info = self.get_input_from_attribute(node)
            if input_info:
                inputs.append(input_info)
        
        for child in node.children:
            inputs.extend(self.find_inputs_in_node(child))
        return inputs
    
    def _detect_call_source(self, text: str) -> Optional[str]:
        """Detect source type from function call text.
        
        Fixed: Exact match at end of text to prevent false positives
        from chained method calls like request.form.get('x').encode('utf-8')
        """
        patterns = {
            "request.args.get": "GET",
            "request.form.get": "POST",
            "request.cookies.get": "COOKIE",
            "request.headers.get": "HEADER",
            "request.files.get": "FILE",
            "request.view_args.get": "PATH",
            "request.json.get": "BODY_JSON",
            "request.get_json": "BODY_JSON",
            "request.get_data": "BODY_RAW",
        }
        for pattern, source in patterns.items():
            # Must end with the pattern (not be part of a chain)
            if text == pattern or text.endswith('.' + pattern.split('.')[-1]):
                # Additional check: text should match pattern exactly 
                # or start with known request prefixes
                if text == pattern:
                    return source
        return None
    
    def _detect_subscript_source(self, value_text: str) -> Optional[str]:
        """Detect source type from subscript value."""
        patterns = {
            "request.args": "GET",
            "request.form": "POST",
            "request.cookies": "COOKIE",
            "request.headers": "HEADER",
            "request.files": "FILE",
            "request.view_args": "PATH",
            "request.json": "BODY_JSON",
            "request.data": "BODY_RAW",
        }
        return patterns.get(value_text)
    
    def _extract_first_arg_name(self, args_node) -> Optional[str]:
        """Extract the name from the first argument of a call."""
        if not args_node:
            return None
        first_arg = args_node.child(1)  # child 0 is (
        if first_arg and first_arg.type in ('string', 'identifier'):
            return self.get_text(first_arg).strip('"\'')
        return None


class SanitizationAnalyzer:
    """
    Analyzer for detecting sanitization of user inputs.
    
    Tracks variable bindings to detect when inputs flow through sanitizers.
    """
    
    def __init__(self, get_text_func: Callable, input_extractor: InputExtractor):
        self.get_text = get_text_func
        self.input_extractor = input_extractor
    
    def collect_param_bindings(self, func_node) -> Dict[str, Dict]:
        """Collect bindings for function parameters."""
        bindings = {}
        for param in extract_params(func_node, self.get_text):
            if param.name and param.name not in bindings:
                bindings[param.name] = {
                    "name": param.name,
                    "source": "PARAM",
                    "type": "FunctionParam"
                }
        return bindings
    
    def collect_input_bindings(self, node) -> Dict[str, Dict]:
        """Collect bindings from assignment statements that capture inputs."""
        bindings = {}
        
        def visit(n):
            if n.type == 'assignment':
                left_node = n.child_by_field_name('left')
                right_node = n.child_by_field_name('right')
                if left_node and right_node and left_node.type == 'identifier':
                    inputs = self.input_extractor.find_inputs_in_node(right_node)
                    if inputs:
                        bindings[self.get_text(left_node)] = inputs[0]
            for child in n.children:
                visit(child)
        
        visit(node)
        return bindings
    
    def extract_sanitization_details(self, func_node) -> List[Dict]:
        """
        Extract detailed sanitization information.
        
        Returns list of dicts with:
        - input: Input parameter name
        - source: Input source type
        - sanitizer: Sanitizer function name
        - args: Arguments passed to sanitizer
        - line: Line number
        - via: How the input reached the sanitizer ('direct' or variable name)
        """
        details = []
        seen = set()
        
        # Build binding maps
        bindings = self.collect_input_bindings(func_node)
        param_bindings = self.collect_param_bindings(func_node)
        for key, value in param_bindings.items():
            if key not in bindings:
                bindings[key] = value
        
        def visit(n):
            if n.type == 'call':
                func_node_inner = n.child_by_field_name('function')
                if func_node_inner:
                    func_name = self.get_text(func_node_inner)
                    if is_sanitizer(func_name):
                        args_node = n.child_by_field_name('arguments')
                        arg_texts = []
                        arg_nodes = []
                        
                        if args_node:
                            for child in args_node.children:
                                if child.is_named:
                                    arg_nodes.append(child)
                                    arg_texts.append(self.get_text(child))
                        
                        line_no = n.start_point.row + 1
                        
                        for arg in arg_nodes:
                            # Check for direct input usage
                            direct_inputs = self.input_extractor.find_inputs_in_node(arg)
                            if direct_inputs:
                                for inp in direct_inputs:
                                    key = (inp["name"], inp["source"], func_name, line_no)
                                    if key in seen:
                                        continue
                                    seen.add(key)
                                    details.append({
                                        "input": inp["name"],
                                        "source": inp["source"],
                                        "sanitizer": func_name,
                                        "args": arg_texts,
                                        "line": line_no,
                                        "via": "direct"
                                    })
                            else:
                                # Check for indirect usage via variables
                                identifiers = extract_identifiers(arg, self.get_text)
                                for ident in identifiers:
                                    if ident in bindings:
                                        inp = bindings[ident]
                                        key = (inp["name"], inp["source"], func_name, line_no, ident)
                                        if key in seen:
                                            continue
                                        seen.add(key)
                                        details.append({
                                            "input": inp["name"],
                                            "source": inp["source"],
                                            "sanitizer": func_name,
                                            "args": arg_texts,
                                            "line": line_no,
                                            "via": ident
                                        })
            
            for child in n.children:
                visit(child)
        
        visit(func_node)
        return details
