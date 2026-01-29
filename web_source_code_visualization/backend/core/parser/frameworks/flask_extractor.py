"""
Flask framework extractor.

Handles:
- @app.route("/path", methods=["GET", "POST"])
- @blueprint.route("/path")
- request.args.get(), request.form.get(), etc.
"""

from typing import Optional, List
import re
from .base_framework import BaseFrameworkExtractor, RouteInfo, InputInfo


class FlaskExtractor(BaseFrameworkExtractor):
    """Extractor for Flask web framework."""
    
    # Route decorator patterns
    ROUTE_PATTERNS = [
        r"@\w+\.route\s*\(",  # @app.route, @bp.route, @blueprint.route
    ]
    
    # Input patterns for request object
    INPUT_CALL_PATTERNS = {
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
    
    INPUT_SUBSCRIPT_PATTERNS = {
        "request.args": "GET",
        "request.form": "POST",
        "request.cookies": "COOKIE",
        "request.headers": "HEADER",
        "request.files": "FILE",
        "request.view_args": "PATH",
        "request.json": "BODY_JSON",
        "request.data": "BODY_RAW",
    }
    
    INPUT_ATTRIBUTE_PATTERNS = {
        "request.json": "BODY_JSON",
        "request.data": "BODY_RAW",
    }
    
    @property
    def name(self) -> str:
        return "Flask"
    
    def is_route_decorator(self, decorator_text: str) -> bool:
        """Check if this is a Flask route decorator."""
        for pattern in self.ROUTE_PATTERNS:
            if re.search(pattern, decorator_text):
                return True
        return False
    
    def parse_route(self, decorator_text: str) -> RouteInfo:
        """
        Parse Flask route decorator.
        
        Examples:
        - @app.route("/users")
        - @app.route("/users/<int:id>", methods=["GET", "POST"])
        - @bp.route("/api/v1/items")
        """
        path = "/"
        method = "GET"
        
        try:
            # Extract path from first argument
            # Pattern: @xxx.route("path" or 'path'
            path_match = re.search(r'\.route\s*\(\s*["\']([^"\']+)["\']', decorator_text)
            if path_match:
                path = path_match.group(1)
            
            # Extract method from methods= argument
            methods_match = re.search(r'methods\s*=\s*\[([^\]]+)\]', decorator_text)
            if methods_match:
                methods_str = methods_match.group(1)
                # Get all methods
                methods = re.findall(r'["\'](\w+)["\']', methods_str)
                if methods:
                    # Use POST if present, otherwise first method
                    if "POST" in methods:
                        method = "POST"
                    elif "PUT" in methods:
                        method = "PUT"
                    elif "DELETE" in methods:
                        method = "DELETE"
                    elif "PATCH" in methods:
                        method = "PATCH"
                    else:
                        method = methods[0].upper()
        except Exception:
            pass
        
        path_params = self.extract_path_params(path)
        
        return RouteInfo(
            path=path,
            method=method,
            is_route=True,
            path_params=path_params
        )
    
    def extract_path_params(self, path_text: str) -> List[str]:
        """
        Extract Flask path parameters.
        
        Patterns:
        - <id> -> id
        - <int:id> -> id
        - <string:name> -> name
        """
        # Pattern: <optional_converter:param_name>
        params = re.findall(r"<(?:[^:<>]+:)?([^<>]+)>", path_text)
        return params
    
    def extract_input_from_call(self, node, get_text_func) -> Optional[InputInfo]:
        """
        Extract input from Flask request calls.
        
        Examples:
        - request.args.get("param")
        - request.form.get("field")
        - request.get_json()
        """
        if node.type != 'call':
            return None
            
        func_node = node.child_by_field_name('function')
        if not func_node or func_node.type != 'attribute':
            return None
            
        func_text = get_text_func(func_node)
        source_type = None
        
        # Check against patterns
        for pattern, source in self.INPUT_CALL_PATTERNS.items():
            if pattern in func_text:
                source_type = source
                break
        
        if not source_type:
            return None
        
        # Extract parameter name from first argument
        args = node.child_by_field_name('arguments')
        param_name = None
        
        if args:
            first_arg = args.child(1)  # child 0 is (
            if first_arg and first_arg.type in ('string', 'identifier'):
                param_name = get_text_func(first_arg).strip('"\'')
        
        # Default names for certain types
        if not param_name:
            if source_type == "BODY_JSON":
                param_name = "json"
            elif source_type == "BODY_RAW":
                param_name = "data"
            else:
                return None
        
        return InputInfo(
            name=param_name,
            source=source_type,
            type="UserInput",
            line=node.start_point.row + 1
        )
    
    def extract_input_from_subscript(self, node, get_text_func) -> Optional[InputInfo]:
        """
        Extract input from Flask request subscript access.
        
        Examples:
        - request.args["param"]
        - request.form["field"]
        """
        if node.type != 'subscript':
            return None
            
        value_node = node.child_by_field_name('value')
        slice_node = node.child_by_field_name('subscript')
        
        if not value_node or not slice_node:
            return None
            
        value_text = get_text_func(value_node)
        source_type = self.INPUT_SUBSCRIPT_PATTERNS.get(value_text)
        
        if not source_type:
            return None
        
        param_name = get_text_func(slice_node).strip('"\'')
        
        return InputInfo(
            name=param_name,
            source=source_type,
            type="UserInput",
            line=node.start_point.row + 1
        )
    
    def extract_input_from_attribute(self, node, get_text_func) -> Optional[InputInfo]:
        """
        Extract input from Flask request attribute access.
        
        Examples:
        - request.json
        - request.data
        """
        if node.type != 'attribute':
            return None
            
        text = get_text_func(node)
        source_type = self.INPUT_ATTRIBUTE_PATTERNS.get(text)
        
        if not source_type:
            return None
        
        if source_type == "BODY_JSON":
            return InputInfo(name="json", source=source_type, type="UserInput")
        elif source_type == "BODY_RAW":
            return InputInfo(name="data", source=source_type, type="UserInput")
        
        return None
