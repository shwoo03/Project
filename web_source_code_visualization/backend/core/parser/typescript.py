"""
TypeScript/TSX Parser for Web Application Analysis.

Enhanced TypeScript parser with support for:
- Type annotations and interfaces
- React component detection (FC, Component)
- Next.js API routes and pages
- Express.js type-safe handlers
- Generic type parameters
"""

from typing import List, Dict, Any, Optional, Set
from tree_sitter import Language, Parser
import tree_sitter_typescript
import os
import re
from .base import BaseParser
from models import EndpointNodes, Parameter


# TypeScript-specific patterns
TS_DANGEROUS_TYPES = {
    "any",      # Can bypass type checking
    "unknown",  # Needs type assertion
}

# React/Next.js patterns
REACT_COMPONENT_PATTERNS = [
    r"React\.FC",
    r"React\.Component",
    r"React\.PureComponent",
    r"NextPage",
    r"GetServerSideProps",
    r"GetStaticProps",
]

# Next.js API handler pattern
NEXTJS_API_PATTERNS = [
    r"NextApiRequest",
    r"NextApiResponse",
]


class TypeScriptParser(BaseParser):
    """
    TypeScript/TSX parser with enhanced type-aware analysis.
    
    Features:
    - Interface and type alias extraction
    - React component detection
    - Next.js API route analysis
    - Type annotation tracking
    - Generic parameter resolution
    """
    
    def __init__(self):
        # Use TypeScript language
        self.LANGUAGE = Language(tree_sitter_typescript.language_typescript())
        self.TSX_LANGUAGE = Language(tree_sitter_typescript.language_tsx())
        self.parser = Parser(self.LANGUAGE)
        self.tsx_parser = Parser(self.TSX_LANGUAGE)

    def can_parse(self, file_path: str) -> bool:
        return file_path.endswith('.ts') or file_path.endswith('.tsx')

    def _get_parser(self, file_path: str) -> Parser:
        """Get appropriate parser based on file extension."""
        if file_path.endswith('.tsx'):
            return self.tsx_parser
        return self.parser

    def _get_language(self, file_path: str) -> Language:
        """Get appropriate language based on file extension."""
        if file_path.endswith('.tsx'):
            return self.TSX_LANGUAGE
        return self.LANGUAGE

    def parse(self, file_path: str, content: str, 
              global_symbols: Dict[str, Dict] = None,
              symbol_table: Any = None) -> List[EndpointNodes]:
        parser = self._get_parser(file_path)
        language = self._get_language(file_path)
        
        tree = parser.parse(bytes(content, "utf8"))
        root_node = tree.root_node
        
        endpoints = []
        filename = os.path.basename(file_path)
        
        if global_symbols is None:
            global_symbols = self.scan_symbols(file_path, content)
        
        # Merge local definitions
        local_defs = self.extract_functions_def(root_node, content, language)
        for k, v in local_defs.items():
            v['file_path'] = file_path
            global_symbols[k] = v

        # 1. Detect framework and extract appropriate patterns
        framework = self._detect_framework(content)
        
        # 2. Extract based on framework
        if framework == 'nextjs_api':
            endpoints.extend(self._parse_nextjs_api(root_node, content, file_path, language))
        elif framework == 'nextjs_page':
            endpoints.extend(self._parse_nextjs_page(root_node, content, file_path, language))
        elif framework == 'react':
            endpoints.extend(self._parse_react_component(root_node, content, file_path, language, global_symbols))
        else:
            # Default: treat as general TypeScript
            endpoints.extend(self._parse_general_ts(root_node, content, file_path, language, global_symbols))

        return endpoints

    def scan_symbols(self, file_path: str, content: str) -> Dict[str, Dict]:
        parser = self._get_parser(file_path)
        language = self._get_language(file_path)
        
        tree = parser.parse(bytes(content, "utf8"))
        root_node = tree.root_node
        
        defined = self.extract_functions_def(root_node, content, language)
        
        # Also extract interfaces and types
        interfaces = self._extract_interfaces(root_node, content, language)
        defined.update(interfaces)
        
        for k, v in defined.items():
            v['file_path'] = file_path
        
        return defined

    def _detect_framework(self, content: str) -> str:
        """Detect the framework being used."""
        # Next.js API route
        if any(re.search(p, content) for p in NEXTJS_API_PATTERNS):
            return 'nextjs_api'
        
        # Next.js page with GetServerSideProps/GetStaticProps
        if 'GetServerSideProps' in content or 'GetStaticProps' in content:
            return 'nextjs_page'
        
        # React component
        if any(re.search(p, content) for p in REACT_COMPONENT_PATTERNS):
            return 'react'
        
        # Check for React imports
        if 'from "react"' in content or "from 'react'" in content:
            return 'react'
        
        return 'general'

    def _parse_nextjs_api(self, node, content: str, file_path: str, language: Language) -> List[EndpointNodes]:
        """Parse Next.js API route handler."""
        endpoints = []
        filename = os.path.basename(file_path)
        
        # Extract the default export function
        # Pattern: export default function handler(req, res)
        # or: export default async function handler(req, res)
        
        # Derive route from file path (pages/api/users.ts -> /api/users)
        route_path = self._derive_nextjs_route(file_path)
        
        # Find handler function
        handler_pattern = r"export\s+default\s+(async\s+)?function\s+(\w+)?"
        match = re.search(handler_pattern, content)
        
        if match:
            func_name = match.group(2) or "handler"
            line = content[:match.start()].count('\n') + 1
            
            # Extract request parameters
            inputs = self._extract_nextjs_inputs(content)
            
            # Extract sinks (dangerous operations)
            sinks = self._extract_ts_sinks(node, content, file_path, language)
            
            endpoint = EndpointNodes(
                id=f"api-{filename}",
                path=route_path,
                method="API",
                language="typescript",
                type="root",
                file_path=file_path,
                line_number=line,
                end_line_number=len(content.splitlines()),
                params=inputs,
                children=sinks,
                metadata={
                    "framework": "nextjs",
                    "type": "api_route",
                    "handler": func_name
                }
            )
            endpoints.append(endpoint)
        
        return endpoints

    def _parse_nextjs_page(self, node, content: str, file_path: str, language: Language) -> List[EndpointNodes]:
        """Parse Next.js page with data fetching."""
        endpoints = []
        filename = os.path.basename(file_path)
        route_path = self._derive_nextjs_route(file_path)
        
        # Check for getServerSideProps or getStaticProps
        data_fetching = []
        
        if 'getServerSideProps' in content:
            data_fetching.append('SSR')
        if 'getStaticProps' in content:
            data_fetching.append('SSG')
        
        inputs = []
        children = []
        
        # Extract context.query, context.params from getServerSideProps
        query_pattern = r"context\.(query|params)\.(\w+)"
        for match in re.finditer(query_pattern, content):
            source_type = match.group(1)
            param_name = match.group(2)
            inputs.append(Parameter(
                name=param_name,
                type="string",
                source="query" if source_type == "query" else "path"
            ))
        
        # Extract fetch/API calls
        children.extend(self._extract_api_calls(node, content, file_path, language))
        
        endpoint = EndpointNodes(
            id=f"page-{filename}",
            path=route_path,
            method="PAGE",
            language="typescript",
            type="root",
            file_path=file_path,
            line_number=1,
            end_line_number=len(content.splitlines()),
            params=inputs,
            children=children,
            metadata={
                "framework": "nextjs",
                "type": "page",
                "data_fetching": data_fetching
            }
        )
        endpoints.append(endpoint)
        
        return endpoints

    def _parse_react_component(self, node, content: str, file_path: str, 
                               language: Language, global_symbols: Dict) -> List[EndpointNodes]:
        """Parse React component."""
        endpoints = []
        filename = os.path.basename(file_path)
        
        # Find component name
        component_pattern = r"(?:export\s+(?:default\s+)?)?(?:function|const)\s+(\w+)\s*(?::\s*(?:React\.)?FC|=)"
        match = re.search(component_pattern, content)
        
        component_name = match.group(1) if match else filename.replace('.tsx', '').replace('.ts', '')
        
        # Extract props interface
        props = self._extract_component_props(content, component_name)
        
        # Extract hooks and state
        hooks = self._extract_hooks(content)
        
        # Extract API calls and event handlers
        children = []
        children.extend(self._extract_api_calls(node, content, file_path, language))
        children.extend(self._extract_event_handlers(content, file_path))
        children.extend(self._extract_ts_sinks(node, content, file_path, language))
        
        endpoint = EndpointNodes(
            id=f"component-{component_name}",
            path=f"<{component_name} />",
            method="COMPONENT",
            language="typescript",
            type="root",
            file_path=file_path,
            line_number=1,
            end_line_number=len(content.splitlines()),
            params=props,
            children=children,
            metadata={
                "framework": "react",
                "type": "component",
                "hooks": hooks
            }
        )
        endpoints.append(endpoint)
        
        return endpoints

    def _parse_general_ts(self, node, content: str, file_path: str, 
                          language: Language, global_symbols: Dict) -> List[EndpointNodes]:
        """Parse general TypeScript file."""
        endpoints = []
        filename = os.path.basename(file_path)
        
        # Extract all exported functions
        funcs = self.extract_functions_def(node, content, language)
        
        # Extract inputs (Express-style req.query, etc.)
        inputs = self._extract_express_inputs(node, content, language)
        
        # Extract calls and sinks
        children = []
        children.extend(self._extract_ts_sinks(node, content, file_path, language))
        children.extend(self._extract_api_calls(node, content, file_path, language))
        
        endpoint = EndpointNodes(
            id=f"file-{filename}",
            path=f"/{filename}",
            method="TS",
            language="typescript",
            type="root",
            file_path=file_path,
            line_number=1,
            end_line_number=len(content.splitlines()),
            params=inputs,
            children=children,
            metadata={
                "exports": list(funcs.keys())
            }
        )
        endpoints.append(endpoint)
        
        return endpoints

    def extract_functions_def(self, node, content: str, language: Language) -> Dict[str, Dict]:
        """Extract function definitions with type annotations."""
        defined_funcs = {}
        
        # Function declarations
        try:
            query = language.query("(function_declaration name: (identifier) @name)")
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
        
        # Arrow functions
        try:
            query = language.query("""
                (variable_declarator
                    name: (identifier) @name
                    value: (arrow_function)
                )
            """)
            captures = query.captures(node)
            for n, _ in captures:
                func_name = content[n.start_byte:n.end_byte]
                parent = n.parent
                defined_funcs[func_name] = {
                    "start_line": parent.start_point[0] + 1,
                    "end_line": parent.end_point[0] + 1,
                    "type": "arrow_function"
                }
        except Exception:
            pass
        
        # Class methods
        try:
            query = language.query("(method_definition name: (property_identifier) @name)")
            captures = query.captures(node)
            for n, _ in captures:
                method_name = content[n.start_byte:n.end_byte]
                parent = n.parent
                defined_funcs[method_name] = {
                    "start_line": parent.start_point[0] + 1,
                    "end_line": parent.end_point[0] + 1,
                    "type": "method"
                }
        except Exception:
            pass
        
        return defined_funcs

    def _extract_interfaces(self, node, content: str, language: Language) -> Dict[str, Dict]:
        """Extract TypeScript interfaces and type aliases."""
        interfaces = {}
        
        # Interface declarations
        try:
            query = language.query("(interface_declaration name: (type_identifier) @name)")
            captures = query.captures(node)
            for n, _ in captures:
                name = content[n.start_byte:n.end_byte]
                parent = n.parent
                interfaces[name] = {
                    "start_line": parent.start_point[0] + 1,
                    "end_line": parent.end_point[0] + 1,
                    "type": "interface"
                }
        except Exception:
            pass
        
        # Type aliases
        try:
            query = language.query("(type_alias_declaration name: (type_identifier) @name)")
            captures = query.captures(node)
            for n, _ in captures:
                name = content[n.start_byte:n.end_byte]
                parent = n.parent
                interfaces[name] = {
                    "start_line": parent.start_point[0] + 1,
                    "end_line": parent.end_point[0] + 1,
                    "type": "type_alias"
                }
        except Exception:
            pass
        
        return interfaces

    def _derive_nextjs_route(self, file_path: str) -> str:
        """Derive Next.js route from file path."""
        # pages/api/users/[id].ts -> /api/users/[id]
        # app/api/users/route.ts -> /api/users
        
        path = file_path.replace('\\', '/')
        
        # Handle pages directory
        if '/pages/' in path:
            route = path.split('/pages/')[-1]
            route = route.rsplit('.', 1)[0]  # Remove extension
            if route.endswith('/index'):
                route = route[:-6]
            return f"/{route}"
        
        # Handle app directory (Next.js 13+)
        if '/app/' in path:
            route = path.split('/app/')[-1]
            route = route.rsplit('.', 1)[0]
            route = route.replace('/route', '').replace('/page', '')
            return f"/{route}"
        
        return f"/{os.path.basename(file_path)}"

    def _extract_nextjs_inputs(self, content: str) -> List[Parameter]:
        """Extract inputs from Next.js API handler."""
        inputs = []
        seen = set()
        
        patterns = [
            (r"req\.query\.(\w+)", "query"),
            (r"req\.body\.(\w+)", "body"),
            (r"req\.cookies\.(\w+)", "cookie"),
            (r"req\.headers\[?['\"]?([\w-]+)", "header"),
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

    def _extract_express_inputs(self, node, content: str, language: Language) -> List[Parameter]:
        """Extract Express.js style inputs."""
        inputs = []
        seen = set()
        
        patterns = [
            (r"req\.query\.(\w+)", "query"),
            (r"req\.body\.(\w+)", "body"),
            (r"req\.params\.(\w+)", "path"),
            (r"req\.cookies\.(\w+)", "cookie"),
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

    def _extract_component_props(self, content: str, component_name: str) -> List[Parameter]:
        """Extract React component props from interface."""
        props = []
        
        # Look for Props interface
        props_pattern = rf"interface\s+{component_name}Props\s*\{{\s*([^}}]+)\}}"
        match = re.search(props_pattern, content)
        
        if not match:
            # Try generic Props
            match = re.search(r"interface\s+Props\s*\{\s*([^}]+)\}", content)
        
        if match:
            props_content = match.group(1)
            # Parse props: name: type
            for prop_match in re.finditer(r"(\w+)\s*[?]?\s*:\s*([^;,\n]+)", props_content):
                props.append(Parameter(
                    name=prop_match.group(1),
                    type=prop_match.group(2).strip(),
                    source="arg"
                ))
        
        return props

    def _extract_hooks(self, content: str) -> List[str]:
        """Extract React hooks used in component."""
        hooks = []
        hook_pattern = r"\b(use[A-Z]\w+)\s*\("
        for match in re.finditer(hook_pattern, content):
            hook = match.group(1)
            if hook not in hooks:
                hooks.append(hook)
        return hooks

    def _extract_api_calls(self, node, content: str, file_path: str, language: Language) -> List[EndpointNodes]:
        """Extract fetch/axios API calls."""
        api_calls = []
        seen = set()
        
        # fetch calls
        fetch_pattern = r"fetch\s*\(\s*([^,\)]+)"
        for match in re.finditer(fetch_pattern, content):
            url = match.group(1).strip()
            line = content[:match.start()].count('\n') + 1
            
            key = (url, line)
            if key not in seen:
                seen.add(key)
                api_calls.append(EndpointNodes(
                    id=f"api-fetch-{line}",
                    path=f"fetch({url[:30]})" if len(url) > 30 else f"fetch({url})",
                    method="API",
                    language="typescript",
                    type="api_call",
                    file_path=file_path,
                    line_number=line,
                    end_line_number=line,
                    metadata={"api_type": "fetch", "url": url}
                ))
        
        # axios calls
        axios_pattern = r"axios\.(get|post|put|delete|patch)\s*[<(]"
        for match in re.finditer(axios_pattern, content):
            method = match.group(1).upper()
            line = content[:match.start()].count('\n') + 1
            
            key = (method, line)
            if key not in seen:
                seen.add(key)
                api_calls.append(EndpointNodes(
                    id=f"api-axios-{line}",
                    path=f"axios.{method.lower()}()",
                    method=method,
                    language="typescript",
                    type="api_call",
                    file_path=file_path,
                    line_number=line,
                    end_line_number=line,
                    metadata={"api_type": "axios", "http_method": method}
                ))
        
        return api_calls

    def _extract_event_handlers(self, content: str, file_path: str) -> List[EndpointNodes]:
        """Extract React event handlers."""
        handlers = []
        seen = set()
        
        # onClick, onSubmit, onChange, etc.
        pattern = r'on([A-Z]\w+)\s*=\s*\{'
        for match in re.finditer(pattern, content):
            event = match.group(1)
            line = content[:match.start()].count('\n') + 1
            
            key = (event, line)
            if key not in seen:
                seen.add(key)
                handlers.append(EndpointNodes(
                    id=f"event-{event}-{line}",
                    path=f"on{event}",
                    method="EVENT",
                    language="typescript",
                    type="event_handler",
                    file_path=file_path,
                    line_number=line,
                    end_line_number=line,
                    metadata={"event_type": event, "framework": "react"}
                ))
        
        return handlers

    def _extract_ts_sinks(self, node, content: str, file_path: str, language: Language) -> List[EndpointNodes]:
        """Extract dangerous operations (sinks)."""
        sinks = []
        seen = set()
        
        # TypeScript/React specific sinks
        ts_sinks = {
            "dangerouslySetInnerHTML": ("XSS", "HIGH"),
            "innerHTML": ("XSS", "HIGH"),
            "eval": ("CODE", "HIGH"),
            "Function": ("CODE", "HIGH"),
            "document.write": ("XSS", "HIGH"),
            "exec": ("CMDI", "HIGH"),
            "spawn": ("CMDI", "HIGH"),
        }
        
        for sink_name, (vuln_type, severity) in ts_sinks.items():
            if sink_name in content:
                pattern = rf"\b{re.escape(sink_name)}\b"
                for match in re.finditer(pattern, content):
                    line = content[:match.start()].count('\n') + 1
                    
                    key = (sink_name, line)
                    if key not in seen:
                        seen.add(key)
                        sinks.append(EndpointNodes(
                            id=f"sink-{sink_name.replace('.', '_')}-{line}",
                            path=f"⚠️ {sink_name}",
                            method=vuln_type,
                            language="typescript",
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


# Backward compatibility
TypescriptParser = TypeScriptParser
