"""
Enhanced JavaScript/TypeScript Parser for Web Application Analysis.

This parser analyzes JavaScript and TypeScript code for:
- DOM manipulation (potential XSS sinks)
- Fetch/AJAX API calls
- Event handlers
- User input sources (URL params, form inputs)
- Dangerous sinks (innerHTML, eval, etc.)
"""

from typing import List, Dict, Any, Optional, Set
from tree_sitter import Language, Parser
import tree_sitter_javascript
import os
import re
from .base import BaseParser
from models import EndpointNodes, Parameter


# ============================================
# JavaScript Security Patterns
# ============================================

# DOM XSS Sinks - properties/methods that can execute JS or inject HTML
DOM_XSS_SINKS: Dict[str, str] = {
    # High Risk - Direct HTML/Script injection
    "innerHTML": "HIGH",
    "outerHTML": "HIGH",
    "insertAdjacentHTML": "HIGH",
    "document.write": "HIGH",
    "document.writeln": "HIGH",
    
    # High Risk - Script execution
    "eval": "HIGH",
    "Function": "HIGH",
    "setTimeout": "MEDIUM",  # When string argument
    "setInterval": "MEDIUM",  # When string argument
    
    # Medium Risk - URL manipulation
    "location.href": "MEDIUM",
    "location.assign": "MEDIUM",
    "location.replace": "MEDIUM",
    "window.open": "MEDIUM",
    
    # Medium Risk - Event handlers
    "onclick": "MEDIUM",
    "onerror": "MEDIUM",
    "onload": "MEDIUM",
    "onmouseover": "MEDIUM",
    
    # Lower Risk - May need context
    "src": "LOW",
    "href": "LOW",
    "action": "LOW",
    "formAction": "LOW",
}

# JavaScript input sources
JS_INPUT_SOURCES: Dict[str, str] = {
    "location.search": "URL_QUERY",
    "location.hash": "URL_HASH",
    "location.pathname": "URL_PATH",
    "location.href": "URL",
    "document.URL": "URL",
    "document.documentURI": "URL",
    "document.referrer": "REFERRER",
    "document.cookie": "COOKIE",
    "window.name": "WINDOW_NAME",
    "localStorage.getItem": "LOCAL_STORAGE",
    "sessionStorage.getItem": "SESSION_STORAGE",
    "URLSearchParams": "URL_QUERY",
}

# API call patterns
API_PATTERNS = [
    "fetch",
    "axios",
    "$.ajax",
    "$.get",
    "$.post",
    "XMLHttpRequest",
    "http.get",
    "http.post",
]


class JavaScriptParser(BaseParser):
    """
    Enhanced JavaScript/TypeScript parser for security analysis.
    
    Features:
    - DOM XSS sink detection
    - Fetch/AJAX API call tracking
    - URL parameter extraction
    - Event handler analysis
    - Taint source detection
    """
    
    def __init__(self):
        self.LANGUAGE = Language(tree_sitter_javascript.language())
        self.parser = Parser(self.LANGUAGE)

    def can_parse(self, file_path: str) -> bool:
        return file_path.endswith('.js') or file_path.endswith('.jsx') or \
               file_path.endswith('.ts') or file_path.endswith('.tsx')

    def parse(self, file_path: str, content: str, 
              global_symbols: Dict[str, Dict] = None,
              symbol_table: Any = None) -> List[EndpointNodes]:
        tree = self.parser.parse(bytes(content, "utf8"))
        root_node = tree.root_node
        
        endpoints = []
        filename = os.path.basename(file_path)
        
        # If no global symbols provided, use local scan
        if global_symbols is None:
            global_symbols = self.scan_symbols(file_path, content)
        
        # Merge local definitions
        local_defs = self.extract_functions_def(root_node, content)
        for k, v in local_defs.items():
            v['file_path'] = file_path
            global_symbols[k] = v

        # 1. Extract inputs (user-controlled data sources)
        inputs = self.extract_inputs(root_node, content, file_path)
        
        # 2. Extract API calls (fetch, axios, etc.)
        api_calls = self.extract_api_calls(root_node, content, file_path)
        
        # 3. Extract DOM sinks (XSS vulnerabilities)
        dom_sinks = self.extract_dom_sinks(root_node, content, file_path)
        
        # 4. Extract general function calls
        func_calls = self.extract_calls(root_node, content, global_symbols, file_path)
        
        # 5. Extract event handlers
        event_handlers = self.extract_event_handlers(root_node, content, file_path)
        
        # Build children list
        children = []
        children.extend(api_calls)
        children.extend(dom_sinks)
        children.extend(func_calls)
        children.extend(event_handlers)

        # Create Root Node for this file
        file_endpoint = EndpointNodes(
            id=f"file-{filename}",
            path=f"/{filename}",
            method="JS",
            language="javascript",
            type="root",
            file_path=file_path,
            line_number=1,
            end_line_number=len(content.splitlines()),
            params=inputs,
            children=children,
            metadata={
                "inputs_count": len(inputs),
                "api_calls_count": len(api_calls),
                "dom_sinks_count": len(dom_sinks),
                "has_dangerous_sinks": any(s.type == "sink" for s in dom_sinks)
            }
        )
        
        endpoints.append(file_endpoint)
        return endpoints

    def scan_symbols(self, file_path: str, content: str) -> Dict[str, Dict]:
        tree = self.parser.parse(bytes(content, "utf8"))
        root_node = tree.root_node
        
        defined = self.extract_functions_def(root_node, content)
        for k, v in defined.items():
            v['file_path'] = file_path
        return defined

    def extract_inputs(self, node, content: str, file_path: str) -> List[Parameter]:
        """Extract user-controlled input sources."""
        inputs = []
        seen = set()
        
        # Pattern 1: req.query.param, req.body.param (Express.js)
        query_scm = """
        (member_expression
          object: (member_expression
            object: (identifier) @req
            property: (property_identifier) @source)
          property: (property_identifier) @key
          (#match? @req "^(req|request)$")
          (#match? @source "^(query|body|params|cookies|headers)$")
        )
        """
        try:
            query = self.LANGUAGE.query(query_scm)
            captures = query.captures(node)
            
            current_source = ""
            for n, name in captures:
                if name == 'source':
                    current_source = content[n.start_byte:n.end_byte]
                elif name == 'key':
                    key_text = content[n.start_byte:n.end_byte]
                    key = (key_text, current_source)
                    
                    if key not in seen:
                        seen.add(key)
                        method = self._source_to_method(current_source)
                        inputs.append(Parameter(
                            name=key_text,
                            type="UserInput",
                            source=method.lower()
                        ))
        except Exception:
            pass
        
        # Pattern 2: URL/Location sources
        for source_pattern, source_type in JS_INPUT_SOURCES.items():
            if source_pattern in content:
                key = (source_pattern, source_type)
                if key not in seen:
                    seen.add(key)
                    inputs.append(Parameter(
                        name=source_pattern,
                        type="URLSource",
                        source=source_type.lower()
                    ))
        
        # Pattern 3: URLSearchParams
        if "URLSearchParams" in content:
            # Find .get() calls on URLSearchParams
            params_pattern = r"\.get\s*\(\s*['\"](\w+)['\"]\s*\)"
            for match in re.finditer(params_pattern, content):
                param_name = match.group(1)
                key = (param_name, "URL_QUERY")
                if key not in seen:
                    seen.add(key)
                    inputs.append(Parameter(
                        name=param_name,
                        type="URLParam",
                        source="query"
                    ))
        
        return inputs

    def extract_api_calls(self, node, content: str, file_path: str) -> List[EndpointNodes]:
        """Extract fetch/axios/AJAX API calls."""
        api_calls = []
        seen = set()
        
        # Pattern: fetch("url") or fetch(url, options)
        fetch_pattern = r"fetch\s*\(\s*([^,\)]+)"
        for match in re.finditer(fetch_pattern, content):
            url_arg = match.group(1).strip()
            line = content[:match.start()].count('\n') + 1
            
            key = (url_arg, line)
            if key not in seen:
                seen.add(key)
                api_calls.append(EndpointNodes(
                    id=f"api-fetch-{line}",
                    path=f"fetch({url_arg[:30]}...)" if len(url_arg) > 30 else f"fetch({url_arg})",
                    method="API",
                    language="javascript",
                    type="api_call",
                    file_path=file_path,
                    line_number=line,
                    end_line_number=line,
                    metadata={
                        "api_type": "fetch",
                        "url": url_arg
                    }
                ))
        
        # Pattern: axios.get/post/etc
        axios_pattern = r"axios\.(get|post|put|delete|patch)\s*\(\s*([^,\)]+)"
        for match in re.finditer(axios_pattern, content):
            method = match.group(1).upper()
            url_arg = match.group(2).strip()
            line = content[:match.start()].count('\n') + 1
            
            key = (url_arg, line)
            if key not in seen:
                seen.add(key)
                api_calls.append(EndpointNodes(
                    id=f"api-axios-{line}",
                    path=f"axios.{method.lower()}({url_arg[:25]}...)" if len(url_arg) > 25 else f"axios.{method.lower()}({url_arg})",
                    method=method,
                    language="javascript",
                    type="api_call",
                    file_path=file_path,
                    line_number=line,
                    end_line_number=line,
                    metadata={
                        "api_type": "axios",
                        "http_method": method,
                        "url": url_arg
                    }
                ))
        
        # Pattern: $.ajax, $.get, $.post (jQuery)
        jquery_pattern = r"\$\.(ajax|get|post|getJSON)\s*\(\s*([^,\)]+)"
        for match in re.finditer(jquery_pattern, content):
            method_name = match.group(1)
            url_arg = match.group(2).strip()
            line = content[:match.start()].count('\n') + 1
            
            method = "GET" if method_name in ["get", "getJSON"] else "POST" if method_name == "post" else "AJAX"
            
            key = (url_arg, line)
            if key not in seen:
                seen.add(key)
                api_calls.append(EndpointNodes(
                    id=f"api-jquery-{line}",
                    path=f"$.{method_name}({url_arg[:25]}...)" if len(url_arg) > 25 else f"$.{method_name}({url_arg})",
                    method=method,
                    language="javascript",
                    type="api_call",
                    file_path=file_path,
                    line_number=line,
                    end_line_number=line,
                    metadata={
                        "api_type": "jquery",
                        "http_method": method,
                        "url": url_arg
                    }
                ))
        
        return api_calls

    def extract_dom_sinks(self, node, content: str, file_path: str) -> List[EndpointNodes]:
        """Extract DOM XSS sinks and dangerous operations."""
        sinks = []
        seen = set()
        
        for sink_name, severity in DOM_XSS_SINKS.items():
            # Pattern: element.innerHTML = something
            if "." in sink_name:
                # Global objects like document.write
                pattern = rf"{re.escape(sink_name)}\s*[=(]"
            else:
                # Properties like innerHTML
                pattern = rf"\.{re.escape(sink_name)}\s*="
            
            for match in re.finditer(pattern, content):
                line = content[:match.start()].count('\n') + 1
                
                # Get the value being assigned
                after_match = content[match.end():match.end() + 100]
                value_match = re.match(r"\s*([^;]+)", after_match)
                value = value_match.group(1).strip() if value_match else "unknown"
                
                key = (sink_name, line)
                if key not in seen:
                    seen.add(key)
                    sinks.append(EndpointNodes(
                        id=f"sink-{sink_name.replace('.', '_')}-{line}",
                        path=f"⚠️ {sink_name}",
                        method="DOM_XSS" if "HTML" in sink_name or sink_name in ["eval", "Function"] else "DOM",
                        language="javascript",
                        type="sink",
                        file_path=file_path,
                        line_number=line,
                        end_line_number=line,
                        metadata={
                            "sink_type": "dom_xss",
                            "sink_name": sink_name,
                            "severity": severity,
                            "dangerous": severity == "HIGH",
                            "value": value[:50] if len(value) > 50 else value
                        }
                    ))
        
        # Special case: eval() function call
        eval_pattern = r"\beval\s*\("
        for match in re.finditer(eval_pattern, content):
            line = content[:match.start()].count('\n') + 1
            key = ("eval", line)
            if key not in seen:
                seen.add(key)
                sinks.append(EndpointNodes(
                    id=f"sink-eval-{line}",
                    path="⚠️ eval()",
                    method="CODE_INJECTION",
                    language="javascript",
                    type="sink",
                    file_path=file_path,
                    line_number=line,
                    end_line_number=line,
                    metadata={
                        "sink_type": "code_injection",
                        "sink_name": "eval",
                        "severity": "HIGH",
                        "dangerous": True
                    }
                ))
        
        return sinks

    def extract_event_handlers(self, node, content: str, file_path: str) -> List[EndpointNodes]:
        """Extract DOM event handlers."""
        handlers = []
        seen = set()
        
        # Pattern: addEventListener("click", handler)
        pattern = r'addEventListener\s*\(\s*[\'"](\w+)[\'"]'
        for match in re.finditer(pattern, content):
            event_type = match.group(1)
            line = content[:match.start()].count('\n') + 1
            
            key = (event_type, line)
            if key not in seen:
                seen.add(key)
                handlers.append(EndpointNodes(
                    id=f"event-{event_type}-{line}",
                    path=f"on{event_type}",
                    method="EVENT",
                    language="javascript",
                    type="event_handler",
                    file_path=file_path,
                    line_number=line,
                    end_line_number=line,
                    metadata={
                        "event_type": event_type
                    }
                ))
        
        # Pattern: onClick, onSubmit (React/JSX)
        jsx_pattern = r'on([A-Z]\w+)\s*=\s*\{'
        for match in re.finditer(jsx_pattern, content):
            event_type = match.group(1)
            line = content[:match.start()].count('\n') + 1
            
            key = (event_type, line)
            if key not in seen:
                seen.add(key)
                handlers.append(EndpointNodes(
                    id=f"event-{event_type}-{line}",
                    path=f"on{event_type}",
                    method="EVENT",
                    language="javascript",
                    type="event_handler",
                    file_path=file_path,
                    line_number=line,
                    end_line_number=line,
                    metadata={
                        "event_type": event_type,
                        "framework": "react"
                    }
                ))
        
        return handlers

    def extract_functions_def(self, node, content: str) -> Dict[str, Dict]:
        """Extract function definitions."""
        defined_funcs = {}
        
        # 1. Function declaration: function foo() {}
        query_scm = """(function_declaration (identifier) @name)"""
        try:
            query = self.LANGUAGE.query(query_scm)
            captures = query.captures(node)
            for n, _ in captures:
                func_name = content[n.start_byte:n.end_byte]
                parent = n.parent
                defined_funcs[func_name] = {
                    "start_line": parent.start_point[0] + 1,
                    "end_line": parent.end_point[0] + 1,
                    "file_path": "current",
                    "type": "function"
                }
        except Exception:
            pass
            
        # 2. Arrow function assignment: const foo = () => {}
        query_scm_arrow = """
        (variable_declarator
          name: (identifier) @name
          value: (arrow_function)
        )
        """
        try:
            query = self.LANGUAGE.query(query_scm_arrow)
            captures = query.captures(node)
            for n, _ in captures:
                func_name = content[n.start_byte:n.end_byte]
                parent = n.parent
                defined_funcs[func_name] = {
                    "start_line": parent.start_point[0] + 1,
                    "end_line": parent.end_point[0] + 1,
                    "file_path": "current",
                    "type": "arrow_function"
                }
        except Exception:
            pass

        # 3. Class Methods
        query_scm_method = """
        (method_definition
            name: (property_identifier) @name
        )
        """
        try:
            query = self.LANGUAGE.query(query_scm_method)
            captures = query.captures(node)
            for n, _ in captures:
                method_name = content[n.start_byte:n.end_byte]
                parent = n.parent
                defined_funcs[method_name] = {
                    "start_line": parent.start_point[0] + 1,
                    "end_line": parent.end_point[0] + 1,
                    "file_path": "current",
                    "type": "method"
                }
        except Exception:
            pass

        # 4. React Component: const Component = () => { ... }
        # or function Component() { ... }
        # Already covered by #1 and #2

        return defined_funcs

    def extract_calls(self, node, content: str, defined_funcs: Dict, file_path: str) -> List[EndpointNodes]:
        """Extract function calls."""
        calls = []
        seen = set()
        
        query_scm = """(call_expression function: (identifier) @name)"""
        try:
            query = self.LANGUAGE.query(query_scm)
            captures = query.captures(node)
            
            for n, _ in captures:
                func_name = content[n.start_byte:n.end_byte]
                
                # Skip common built-ins and already processed patterns
                if func_name in ['fetch', 'eval', 'setTimeout', 'setInterval', 'console', 'require', 'import']:
                    continue
                
                key = (func_name, n.start_point[0])
                if key in seen:
                    continue
                seen.add(key)
                
                def_info = defined_funcs.get(func_name, {})
                target_file = def_info.get("file_path", file_path)
                start_line = def_info.get("start_line", n.start_point[0] + 1)
                end_line = def_info.get("end_line", n.end_point[0] + 1)
                
                calls.append(EndpointNodes(
                    id=f"call-{func_name}-{n.start_point[0]}",
                    path=func_name,
                    method="CALL",
                    language="javascript",
                    type="call",
                    file_path=target_file if target_file != "current" else file_path,
                    line_number=start_line,
                    end_line_number=end_line,
                    metadata={
                        "resolved": bool(def_info)
                    }
                ))
        except Exception:
            pass
        
        return calls

    def _source_to_method(self, source: str) -> str:
        """Convert source name to HTTP method."""
        mapping = {
            "query": "GET",
            "body": "POST",
            "params": "PATH",
            "cookies": "COOKIE",
            "headers": "HEADER",
        }
        return mapping.get(source, "UNKNOWN")


# Keep backward compatibility with old class name
JavascriptParser = JavaScriptParser
