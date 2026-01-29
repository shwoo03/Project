"""
FastAPI framework extractor.

Handles:
- @app.get("/path"), @app.post("/path"), etc.
- @router.get("/path"), @router.post("/path"), etc.
- Path parameters {id}
- Query/Body parameter injection via function arguments
"""

from typing import Optional, List
import re
from .base_framework import BaseFrameworkExtractor, RouteInfo, InputInfo


class FastAPIExtractor(BaseFrameworkExtractor):
    """Extractor for FastAPI web framework."""
    
    # HTTP method decorators
    HTTP_METHODS = ['get', 'post', 'put', 'delete', 'patch', 'options', 'head']
    
    # Route decorator patterns
    ROUTE_PATTERNS = [
        r"@\w+\.(get|post|put|delete|patch|options|head)\s*\(",  # @app.get, @router.post
    ]
    
    @property
    def name(self) -> str:
        return "FastAPI"
    
    def is_route_decorator(self, decorator_text: str) -> bool:
        """Check if this is a FastAPI route decorator."""
        for pattern in self.ROUTE_PATTERNS:
            if re.search(pattern, decorator_text, re.IGNORECASE):
                return True
        return False
    
    def parse_route(self, decorator_text: str) -> RouteInfo:
        """
        Parse FastAPI route decorator.
        
        Examples:
        - @app.get("/users")
        - @router.post("/users/{user_id}")
        - @app.put("/items/{item_id}", response_model=Item)
        """
        path = "/"
        method = "GET"
        
        try:
            # Extract method from decorator name
            method_match = re.search(r'\.(\w+)\s*\(', decorator_text)
            if method_match:
                detected_method = method_match.group(1).lower()
                if detected_method in self.HTTP_METHODS:
                    method = detected_method.upper()
            
            # Extract path from first argument
            path_match = re.search(r'\.\w+\s*\(\s*["\']([^"\']+)["\']', decorator_text)
            if path_match:
                path = path_match.group(1)
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
        Extract FastAPI path parameters.
        
        Pattern: {param_name} or {param_name:type}
        Examples:
        - /users/{user_id} -> user_id
        - /items/{item_id:int} -> item_id
        """
        # Simple pattern: {param_name}
        params = re.findall(r"\{([^}:]+)(?::[^}]+)?\}", path_text)
        return params
    
    def extract_input_from_call(self, node, get_text_func) -> Optional[InputInfo]:
        """
        FastAPI uses function parameters for input, not explicit calls like Flask.
        This method handles special cases like Request.body() etc.
        """
        if node.type != 'call':
            return None
        
        func_node = node.child_by_field_name('function')
        if not func_node:
            return None
        
        func_text = get_text_func(func_node)
        
        # FastAPI Request object patterns
        if "request.body" in func_text.lower():
            return InputInfo(name="body", source="BODY_RAW", type="UserInput")
        elif "request.json" in func_text.lower():
            return InputInfo(name="json", source="BODY_JSON", type="UserInput")
        elif "request.form" in func_text.lower():
            return InputInfo(name="form", source="POST", type="UserInput")
        elif "request.query_params" in func_text.lower():
            return InputInfo(name="query_params", source="GET", type="UserInput")
        
        return None
    
    def extract_input_from_subscript(self, node, get_text_func) -> Optional[InputInfo]:
        """
        Extract input from FastAPI request subscript access.
        """
        if node.type != 'subscript':
            return None
        
        value_node = node.child_by_field_name('value')
        slice_node = node.child_by_field_name('subscript')
        
        if not value_node or not slice_node:
            return None
        
        value_text = get_text_func(value_node)
        
        # FastAPI Query/Form/Header patterns
        subscript_patterns = {
            "request.query_params": "GET",
            "request.headers": "HEADER",
            "request.cookies": "COOKIE",
        }
        
        source_type = subscript_patterns.get(value_text)
        if source_type:
            param_name = get_text_func(slice_node).strip('"\'')
            return InputInfo(
                name=param_name,
                source=source_type,
                type="UserInput",
                line=node.start_point.row + 1
            )
        
        return None
    
    def extract_params_from_function(self, func_node, get_text_func, method: str) -> List[InputInfo]:
        """
        Extract FastAPI inputs from function parameters.
        
        FastAPI uses dependency injection:
        - def endpoint(id: int, name: str = Query(...), body: Item = Body(...))
        
        Args:
            func_node: Function definition node
            get_text_func: Text extraction function
            method: HTTP method (affects default source type)
            
        Returns:
            List of InputInfo for each detected input parameter
        """
        inputs = []
        params_node = func_node.child_by_field_name('parameters')
        
        if not params_node:
            return inputs
        
        # Skip common non-input parameters
        skip_params = {'self', 'cls', 'request', 'req', 'db', 'session'}
        
        for child in params_node.children:
            param_name = None
            param_source = "query" if method == "GET" else "body"
            
            if child.type == 'identifier':
                param_name = get_text_func(child)
            elif child.type in ('typed_parameter', 'default_parameter', 'typed_default_parameter'):
                name_node = child.child_by_field_name('name')
                if not name_node:
                    name_node = child.child(0)
                if name_node:
                    param_name = get_text_func(name_node)
                
                # Check for FastAPI dependency hints
                full_text = get_text_func(child)
                if 'Query(' in full_text:
                    param_source = "query"
                elif 'Body(' in full_text:
                    param_source = "body"
                elif 'Header(' in full_text:
                    param_source = "header"
                elif 'Cookie(' in full_text:
                    param_source = "cookie"
                elif 'Form(' in full_text:
                    param_source = "form"
                elif 'Path(' in full_text:
                    param_source = "path"
                elif 'File(' in full_text:
                    param_source = "file"
            
            if param_name and param_name not in skip_params:
                inputs.append(InputInfo(
                    name=param_name,
                    source=param_source.upper() if param_source != "query" else "GET",
                    type="UserInput"
                ))
        
        return inputs
