"""
Enhanced PHP Parser with Laravel and Symfony Support.

Features:
- Laravel routes, controllers, middleware
- Symfony annotations and attributes
- PHP dangerous sinks detection
- Request input extraction
"""

from typing import List, Dict, Any
from tree_sitter import Language, Parser
import tree_sitter_php
import os
import re
from .base import BaseParser
from .frameworks.php_extractor import PHPFrameworkDetector, PHP_DANGEROUS_SINKS
from models import EndpointNodes, Parameter


class PHPParser(BaseParser):
    """
    Enhanced PHP parser with framework support.
    
    Supports:
    - Plain PHP files
    - Laravel (routes, controllers, Eloquent)
    - Symfony (annotations, controllers)
    """
    
    def __init__(self):
        self.LANGUAGE = Language(tree_sitter_php.language_php())
        self.parser = Parser(self.LANGUAGE)
        self.framework_detector = PHPFrameworkDetector()

    def can_parse(self, file_path: str) -> bool:
        return file_path.endswith('.php')

    def scan_symbols(self, file_path: str, content: str) -> Dict[str, Dict]:
        """Scan for function and class definitions."""
        tree = self.parser.parse(bytes(content, "utf8"))
        root_node = tree.root_node
        
        symbols = {}
        
        # Function definitions
        symbols.update(self._extract_functions(root_node, content))
        
        # Class definitions
        symbols.update(self._extract_classes(root_node, content))
        
        for k, v in symbols.items():
            v['file_path'] = file_path
        
        return symbols

    def parse(self, file_path: str, content: str, 
              global_symbols: Dict[str, Dict] = None,
              symbol_table: Any = None) -> List[EndpointNodes]:
        tree = self.parser.parse(bytes(content, "utf8"))
        root_node = tree.root_node
        
        endpoints = []
        filename = os.path.basename(file_path)
        
        # Detect framework
        framework_data = self.framework_detector.extract_all(content, file_path)
        framework = framework_data.get("framework")
        
        if framework == "laravel":
            endpoints.extend(self._parse_laravel(content, file_path, framework_data))
        elif framework == "symfony":
            endpoints.extend(self._parse_symfony(content, file_path, framework_data))
        else:
            endpoints.extend(self._parse_plain_php(root_node, content, file_path))
        
        return endpoints

    def _parse_laravel(self, content: str, file_path: str, 
                       framework_data: Dict) -> List[EndpointNodes]:
        """Parse Laravel-specific patterns."""
        endpoints = []
        filename = os.path.basename(file_path)
        
        # Check if this is a routes file
        is_routes_file = 'routes' in file_path.lower() or 'web.php' in filename or 'api.php' in filename
        
        if is_routes_file:
            # Create endpoints for each route
            for route in framework_data.get("routes", []):
                route_id = f"route-{route['method']}-{route['path'].replace('/', '-')}"
                
                endpoint = EndpointNodes(
                    id=route_id,
                    path=route['path'],
                    method=route['method'],
                    language="php",
                    type="root",
                    file_path=file_path,
                    line_number=route['line'],
                    end_line_number=route['line'] + 1,
                    params=[],
                    children=[],
                    metadata={
                        "framework": "laravel",
                        "controller": route.get('controller'),
                        "action": route.get('action'),
                        "middleware": route.get('middleware', [])
                    }
                )
                endpoints.append(endpoint)
        else:
            # Controller or other Laravel file
            inputs = [
                Parameter(
                    name=inp['name'],
                    type="string",
                    source=inp['source'] if inp['source'] in ['query', 'body', 'path', 'header', 'cookie', 'file'] else 'unknown'
                )
                for inp in framework_data.get("inputs", [])
            ]
            
            # Create sink children
            children = []
            for sink in framework_data.get("sinks", []):
                children.append(EndpointNodes(
                    id=f"sink-{sink['name']}-{sink['line']}",
                    path=f"⚠️ {sink['name']}",
                    method=sink['vulnerability_type'],
                    language="php",
                    type="sink",
                    file_path=file_path,
                    line_number=sink['line'],
                    end_line_number=sink['line'],
                    metadata={
                        "sink_type": sink['vulnerability_type'].lower(),
                        "sink_name": sink['name'],
                        "severity": sink['severity'],
                        "dangerous": sink['severity'] == "HIGH"
                    }
                ))
            
            # Create endpoint for controller methods
            for method in framework_data.get("methods", []):
                endpoint = EndpointNodes(
                    id=f"controller-{method['name']}",
                    path=f"{filename}::{method['name']}",
                    method="CONTROLLER",
                    language="php",
                    type="root",
                    file_path=file_path,
                    line_number=method['line'],
                    end_line_number=method['line'] + 50,
                    params=inputs,
                    children=children,
                    metadata={
                        "framework": "laravel",
                        "type": "controller_action"
                    }
                )
                endpoints.append(endpoint)
            
            # If no methods found, create file-level endpoint
            if not endpoints:
                endpoints.append(EndpointNodes(
                    id=f"file-{filename}",
                    path=f"/{filename}",
                    method="FILE",
                    language="php",
                    type="root",
                    file_path=file_path,
                    line_number=1,
                    end_line_number=len(content.splitlines()),
                    params=inputs,
                    children=children,
                    metadata={"framework": "laravel"}
                ))
        
        return endpoints

    def _parse_symfony(self, content: str, file_path: str, 
                       framework_data: Dict) -> List[EndpointNodes]:
        """Parse Symfony-specific patterns."""
        endpoints = []
        filename = os.path.basename(file_path)
        
        # Process each route/controller action
        for route in framework_data.get("routes", []):
            inputs = [
                Parameter(
                    name=inp['name'],
                    type="string",
                    source=inp['source'] if inp['source'] in ['query', 'body', 'path', 'header', 'cookie', 'file'] else 'unknown'
                )
                for inp in framework_data.get("inputs", [])
            ]
            
            # Create sink children
            children = []
            for sink in framework_data.get("sinks", []):
                children.append(EndpointNodes(
                    id=f"sink-{sink['name']}-{sink['line']}",
                    path=f"⚠️ {sink['name']}",
                    method=sink['vulnerability_type'],
                    language="php",
                    type="sink",
                    file_path=file_path,
                    line_number=sink['line'],
                    end_line_number=sink['line'],
                    metadata={
                        "sink_type": sink['vulnerability_type'].lower(),
                        "sink_name": sink['name'],
                        "severity": sink['severity'],
                        "dangerous": sink['severity'] == "HIGH"
                    }
                ))
            
            method_str = route['methods'][0] if route['methods'] else "GET"
            
            endpoint = EndpointNodes(
                id=f"route-{route['controller']}-{route['line']}",
                path=route['path'],
                method=method_str,
                language="php",
                type="root",
                file_path=file_path,
                line_number=route['line'],
                end_line_number=route['line'] + 50,
                params=inputs,
                children=children,
                metadata={
                    "framework": "symfony",
                    "route_name": route.get('name'),
                    "controller": route.get('controller')
                }
            )
            endpoints.append(endpoint)
        
        # If no routes found, create file-level endpoint
        if not endpoints:
            inputs = [
                Parameter(
                    name=inp['name'],
                    type="string",
                    source=inp['source'] if inp['source'] in ['query', 'body', 'path', 'header', 'cookie', 'file'] else 'unknown'
                )
                for inp in framework_data.get("inputs", [])
            ]
            
            children = []
            for sink in framework_data.get("sinks", []):
                children.append(EndpointNodes(
                    id=f"sink-{sink['name']}-{sink['line']}",
                    path=f"⚠️ {sink['name']}",
                    method=sink['vulnerability_type'],
                    language="php",
                    type="sink",
                    file_path=file_path,
                    line_number=sink['line'],
                    end_line_number=sink['line'],
                    metadata={
                        "sink_type": sink['vulnerability_type'].lower(),
                        "sink_name": sink['name'],
                        "severity": sink['severity'],
                        "dangerous": sink['severity'] == "HIGH"
                    }
                ))
            
            endpoints.append(EndpointNodes(
                id=f"file-{filename}",
                path=f"/{filename}",
                method="FILE",
                language="php",
                type="root",
                file_path=file_path,
                line_number=1,
                end_line_number=len(content.splitlines()),
                params=inputs,
                children=children,
                metadata={"framework": "symfony"}
            ))
        
        return endpoints

    def _parse_plain_php(self, node, content: str, file_path: str) -> List[EndpointNodes]:
        """Parse plain PHP file without framework."""
        endpoints = []
        filename = os.path.basename(file_path)
        
        # Extract inputs
        inputs = self._extract_inputs(node, content, file_path)
        
        # Extract function definitions
        defined_funcs = self._extract_functions(node, content)
        
        # Extract calls
        calls = self._extract_calls(node, content, defined_funcs)
        
        # Extract sinks
        sinks = self._extract_sinks(content, file_path)
        
        # Combine children
        children = calls + sinks
        
        endpoint = EndpointNodes(
            id=f"file-{filename}",
            path=f"/{filename}",
            method="FILE",
            language="php",
            type="root",
            file_path=file_path,
            line_number=1,
            end_line_number=len(content.splitlines()),
            params=inputs,
            children=children,
            metadata={"framework": None}
        )
        
        endpoints.append(endpoint)
        return endpoints

    def _extract_inputs(self, node, content: str, file_path: str) -> List[Parameter]:
        """Extract PHP superglobal inputs."""
        inputs = []
        seen = set()
        
        # $_GET, $_POST, $_COOKIE, $_REQUEST patterns
        patterns = [
            (r"\$_GET\s*\[\s*['\"](\w+)['\"]", "query"),
            (r"\$_POST\s*\[\s*['\"](\w+)['\"]", "body"),
            (r"\$_COOKIE\s*\[\s*['\"](\w+)['\"]", "cookie"),
            (r"\$_REQUEST\s*\[\s*['\"](\w+)['\"]", "unknown"),
            (r"\$_FILES\s*\[\s*['\"](\w+)['\"]", "file"),
            (r"\$_SERVER\s*\[\s*['\"](\w+)['\"]", "header"),
        ]
        
        for pattern, source in patterns:
            for match in re.finditer(pattern, content):
                name = match.group(1)
                if name not in seen:
                    seen.add(name)
                    inputs.append(Parameter(
                        name=name,
                        type="string",
                        source=source
                    ))
        
        return inputs

    def _extract_functions(self, node, content: str) -> Dict[str, Dict]:
        """Extract function definitions."""
        defined_funcs = {}
        
        try:
            query = self.LANGUAGE.query("(function_definition (name) @name)")
            captures = query.captures(node)
            
            for n, _ in captures:
                func_name = content[n.start_byte:n.end_byte]
                parent = n.parent
                defined_funcs[func_name] = {
                    "start_line": parent.start_point[0] + 1,
                    "end_line": parent.end_point[0] + 1,
                    "type": "function"
                }
        except Exception:
            pass
        
        return defined_funcs

    def _extract_classes(self, node, content: str) -> Dict[str, Dict]:
        """Extract class definitions."""
        classes = {}
        
        try:
            query = self.LANGUAGE.query("(class_declaration (name) @name)")
            captures = query.captures(node)
            
            for n, _ in captures:
                class_name = content[n.start_byte:n.end_byte]
                parent = n.parent
                classes[class_name] = {
                    "start_line": parent.start_point[0] + 1,
                    "end_line": parent.end_point[0] + 1,
                    "type": "class"
                }
        except Exception:
            pass
        
        return classes

    def _extract_calls(self, node, content: str, defined_funcs: Dict) -> List[EndpointNodes]:
        """Extract function calls."""
        calls = []
        seen = set()
        
        try:
            query = self.LANGUAGE.query("(function_call_expression (name) @name)")
            captures = query.captures(node)
            
            for n, _ in captures:
                func_name = content[n.start_byte:n.end_byte]
                
                # Skip if it's a known sink (handled separately)
                if func_name in PHP_DANGEROUS_SINKS:
                    continue
                
                key = (func_name, n.start_point[0])
                if key in seen:
                    continue
                seen.add(key)
                
                def_info = defined_funcs.get(func_name, {})
                
                calls.append(EndpointNodes(
                    id=f"call-{func_name}-{n.start_point[0]}",
                    path=func_name,
                    method="CALL",
                    language="php",
                    type="call",
                    file_path=def_info.get("file_path", ""),
                    line_number=def_info.get("start_line", n.start_point[0] + 1),
                    end_line_number=def_info.get("end_line", n.end_point[0] + 1),
                    metadata={"resolved": bool(def_info)}
                ))
        except Exception:
            pass
        
        return calls

    def _extract_sinks(self, content: str, file_path: str) -> List[EndpointNodes]:
        """Extract dangerous function calls (sinks)."""
        sinks = []
        seen = set()
        
        for sink_name, (vuln_type, severity) in PHP_DANGEROUS_SINKS.items():
            if "::" in sink_name:
                continue
            
            pattern = rf"\b{re.escape(sink_name)}\s*\("
            for match in re.finditer(pattern, content):
                line = content[:match.start()].count('\n') + 1
                key = (sink_name, line)
                
                if key not in seen:
                    seen.add(key)
                    sinks.append(EndpointNodes(
                        id=f"sink-{sink_name}-{line}",
                        path=f"⚠️ {sink_name}",
                        method=vuln_type,
                        language="php",
                        type="sink",
                        file_path=file_path,
                        line_number=line,
                        end_line_number=line,
                        metadata={
                            "sink_type": vuln_type.lower(),
                            "sink_name": sink_name,
                            "severity": severity,
                            "dangerous": severity == "HIGH"
                        }
                    ))
        
        return sinks
