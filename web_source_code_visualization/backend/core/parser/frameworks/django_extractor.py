"""
Django framework extractor.

Handles:
- Function-based views (FBV)
- Class-based views (CBV) 
- URL patterns from urls.py
- request.GET, request.POST, request.COOKIES, etc.
- Django REST Framework (DRF) viewsets and serializers
"""

from typing import Optional, List, Dict, Tuple
import re
from .base_framework import BaseFrameworkExtractor, RouteInfo, InputInfo


class DjangoExtractor(BaseFrameworkExtractor):
    """Extractor for Django web framework."""
    
    # Class-based view patterns
    CBV_PATTERNS = [
        r"class\s+\w+\s*\([^)]*View[^)]*\)",      # Generic views
        r"class\s+\w+\s*\([^)]*APIView[^)]*\)",   # DRF APIView
        r"class\s+\w+\s*\([^)]*ViewSet[^)]*\)",   # DRF ViewSet
        r"class\s+\w+\s*\([^)]*Mixin[^)]*\)",     # Mixins
    ]
    
    # HTTP method handlers in CBV
    HTTP_METHODS = ['get', 'post', 'put', 'patch', 'delete', 'head', 'options']
    
    # Input patterns for Django request object
    INPUT_CALL_PATTERNS = {
        "request.GET.get": "GET",
        "request.POST.get": "POST",
        "request.COOKIES.get": "COOKIE",
        "request.META.get": "HEADER",
        "request.FILES.get": "FILE",
        "request.session.get": "SESSION",
        "request.body": "BODY_RAW",
        "request.data.get": "BODY_JSON",  # DRF
    }
    
    INPUT_SUBSCRIPT_PATTERNS = {
        "request.GET": "GET",
        "request.POST": "POST",
        "request.COOKIES": "COOKIE",
        "request.META": "HEADER",
        "request.FILES": "FILE",
        "request.session": "SESSION",
        "request.data": "BODY_JSON",  # DRF
    }
    
    # URL pattern matchers
    URL_PATTERNS = [
        r"path\s*\(\s*['\"]([^'\"]+)['\"]",           # path('route/', ...)
        r"re_path\s*\(\s*['\"]([^'\"]+)['\"]",        # re_path(r'^route/$', ...)
        r"url\s*\(\s*r?['\"]([^'\"]+)['\"]",          # legacy url(r'^route/$', ...)
    ]
    
    @property
    def name(self) -> str:
        return "Django"
    
    def is_route_decorator(self, decorator_text: str) -> bool:
        """
        Django doesn't use decorators for routing typically.
        But check for DRF's @api_view and @action decorators.
        """
        drf_patterns = [
            r"@api_view\s*\(",
            r"@action\s*\(",
            r"@permission_classes\s*\(",
            r"@authentication_classes\s*\(",
        ]
        for pattern in drf_patterns:
            if re.search(pattern, decorator_text):
                return True
        return False
    
    def parse_route(self, decorator_text: str) -> RouteInfo:
        """
        Parse DRF decorator for route information.
        
        Examples:
        - @api_view(['GET', 'POST'])
        - @action(detail=True, methods=['post'])
        """
        path = "/"
        method = "GET"
        
        try:
            # @api_view(['GET', 'POST'])
            if "@api_view" in decorator_text:
                methods_match = re.search(r"\[\s*['\"](\w+)['\"]", decorator_text)
                if methods_match:
                    method = methods_match.group(1).upper()
            
            # @action(detail=True, methods=['post'])
            if "@action" in decorator_text:
                methods_match = re.search(r"methods\s*=\s*\[\s*['\"](\w+)['\"]", decorator_text)
                if methods_match:
                    method = methods_match.group(1).upper()
                
                # Try to get action name as path
                detail_match = re.search(r"detail\s*=\s*(True|False)", decorator_text)
                if detail_match:
                    is_detail = detail_match.group(1) == "True"
                    path = "/{pk}/action/" if is_detail else "/action/"
        except Exception:
            pass
        
        return RouteInfo(
            path=path,
            method=method,
            is_route=True,
            path_params=[]
        )
    
    def extract_path_params(self, path_text: str) -> List[str]:
        """
        Extract Django URL path parameters.
        
        Patterns:
        - <int:pk> -> pk
        - <slug:slug> -> slug
        - <str:name> -> name
        - <uuid:id> -> id
        - (?P<name>\d+) -> name (regex)
        """
        params = []
        
        # New-style path converters: <int:pk>, <slug:slug>
        new_style = re.findall(r"<(?:\w+:)?(\w+)>", path_text)
        params.extend(new_style)
        
        # Regex named groups: (?P<name>pattern)
        regex_style = re.findall(r"\(\?P<(\w+)>", path_text)
        params.extend(regex_style)
        
        return params
    
    def extract_input_from_call(self, node, get_text_func) -> Optional[InputInfo]:
        """
        Extract input from Django request calls.
        
        Examples:
        - request.GET.get("param")
        - request.POST.get("field", "default")
        - request.data.get("key")  # DRF
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
        
        if not param_name:
            if source_type == "BODY_JSON":
                param_name = "data"
            elif source_type == "BODY_RAW":
                param_name = "body"
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
        Extract input from Django request subscript access.
        
        Examples:
        - request.GET["param"]
        - request.POST["field"]
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
    
    def is_cbv_method(self, method_name: str) -> bool:
        """Check if a method name is an HTTP handler in a CBV."""
        return method_name.lower() in self.HTTP_METHODS
    
    def parse_urls_py(self, content: str) -> List[Dict]:
        """
        Parse a urls.py file to extract URL patterns.
        
        Returns:
            List of dicts with path, view_name, and name
        """
        patterns = []
        
        for pattern in self.URL_PATTERNS:
            for match in re.finditer(pattern, content):
                path = match.group(1)
                
                # Try to find the view reference after the path
                after_path = content[match.end():match.end() + 200]
                
                view_match = re.search(r",\s*(\w+(?:\.\w+)*)", after_path)
                view_name = view_match.group(1) if view_match else "unknown"
                
                # Try to find the name= argument
                name_match = re.search(r"name\s*=\s*['\"](\w+)['\"]", after_path)
                url_name = name_match.group(1) if name_match else None
                
                patterns.append({
                    "path": path,
                    "view": view_name,
                    "name": url_name,
                    "path_params": self.extract_path_params(path)
                })
        
        return patterns
    
    def extract_view_function(self, func_text: str) -> Dict:
        """
        Analyze a Django view function.
        
        Returns:
            Dict with method, inputs, and other metadata
        """
        info = {
            "methods": ["GET"],  # Default
            "inputs": [],
            "is_fbv": True
        }
        
        # Check for method restrictions
        if "request.method ==" in func_text or "request.method==" in func_text:
            methods_found = re.findall(r"request\.method\s*==\s*['\"](\w+)['\"]", func_text)
            if methods_found:
                info["methods"] = [m.upper() for m in methods_found]
        
        # Check for require_http_methods decorator
        require_match = re.search(r"@require_http_methods\s*\(\s*\[([^\]]+)\]", func_text)
        if require_match:
            methods_str = require_match.group(1)
            info["methods"] = re.findall(r"['\"](\w+)['\"]", methods_str)
        
        # Shortcut decorators
        if "@require_GET" in func_text:
            info["methods"] = ["GET"]
        elif "@require_POST" in func_text:
            info["methods"] = ["POST"]
        elif "@require_safe" in func_text:
            info["methods"] = ["GET", "HEAD"]
        
        return info
    
    def detect_drf_serializer(self, content: str) -> List[Dict]:
        """
        Detect DRF Serializer definitions for input validation analysis.
        
        Returns:
            List of serializer info dicts
        """
        serializers = []
        
        # Match class definitions that inherit from Serializer
        pattern = r"class\s+(\w+)\s*\([^)]*Serializer[^)]*\):\s*\n((?:\s+.+\n)*)"
        
        for match in re.finditer(pattern, content):
            name = match.group(1)
            body = match.group(2)
            
            # Extract fields
            fields = []
            field_pattern = r"(\w+)\s*=\s*serializers\.(\w+)\s*\("
            for field_match in re.finditer(field_pattern, body):
                field_name = field_match.group(1)
                field_type = field_match.group(2)
                fields.append({
                    "name": field_name,
                    "type": field_type
                })
            
            serializers.append({
                "name": name,
                "fields": fields
            })
        
        return serializers
