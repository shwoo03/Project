from typing import List, Dict, Any
from tree_sitter import Language, Parser
import tree_sitter_javascript
import os
from .base import BaseParser
from models import EndpointNodes, Parameter

class JavascriptParser(BaseParser):
    def __init__(self):
        self.LANGUAGE = Language(tree_sitter_javascript.language())
        self.parser = Parser(self.LANGUAGE)

    def can_parse(self, file_path: str) -> bool:
        return file_path.endswith('.js') or file_path.endswith('.ts')

    def parse(self, file_path: str, content: str, global_symbols: Dict[str, Dict] = None, symbol_table: Any = None) -> List[EndpointNodes]:
        tree = self.parser.parse(bytes(content, "utf8"))
        root_node = tree.root_node
        
        endpoints = []
        filename = os.path.basename(file_path)
        
        # 1. Inputs (req.query, etc)
        global_inputs = self.extract_inputs(root_node, content, file_path)
        
        # If no global symbols provided, use local scan
        if global_symbols is None:
            global_symbols = self.scan_symbols(file_path, content)
        
        # 2. Extract Functions (Local definitions)
        # We merge local defs into global_symbols for this file scope to ensure local precedence if needed (though simple dict overwrite)
        local_defs = self.extract_functions_def(root_node, content)
        for k, v in local_defs.items():
            v['file_path'] = file_path # Ensure current file path
            global_symbols[k] = v

        # 3. Global Calls (pass global_symbols)
        global_calls = self.extract_calls(root_node, content, global_symbols)

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
            params=global_inputs,
            children=global_calls
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
        inputs = []
        # Generic pattern for req.query.param, req.body.param
        # (member_expression object: (member_expression object: (identifier) @req property: (property_identifier) @source) property: (property_identifier) @key)
        query_scm = """
        (member_expression
          object: (member_expression
            object: (identifier) @req
            property: (property_identifier) @source)
          property: (property_identifier) @key
          (#match? @req "^(req|request)$")
          (#match? @source "^(query|body|params|cookies)$")
        )
        """
        try:
            query = self.LANGUAGE.query(query_scm)
            captures = query.captures(node)
            
            # Simple iteration heuristic
            current_source = ""
            
            for n, name in captures:
                if name == 'source':
                    current_source = content[n.start_byte:n.end_byte]
                elif name == 'key':
                    key_text = content[n.start_byte:n.end_byte]
                    
                    method = "UNKNOWN"
                    if current_source == "query": method = "GET"
                    elif current_source == "body": method = "POST"
                    elif current_source == "cookies": method = "COOKIE"
                    elif current_source == "params": method = "PATH"
                    
                    inputs.append(Parameter(
                        name=key_text,
                        type="input",
                        file_path=file_path,
                        line_number=n.start_point[0] + 1,
                        method=method
                    ))
        except Exception:
            pass
            
        return inputs

    def extract_functions_def(self, node, content: str) -> Dict[str, Dict]:
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
                    "file_path": "current"
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
                    "file_path": "current"
                }
        except Exception:
            pass

        # 3. Class Methods: class Foo { bar() {} }
        # Node type: method_definition inside class_body
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
                # Try to find class name? Too complex for now, just index method name
                # or maybe Class.Method if possible.
                # Let's check parent.parent...
                
                defined_funcs[method_name] = {
                    "start_line": parent.start_point[0] + 1,
                    "end_line": parent.end_point[0] + 1,
                    "file_path": "current"
                }
        except Exception:
            pass

        return defined_funcs

    def extract_calls(self, node, content: str, defined_funcs: Dict) -> List[EndpointNodes]:
        calls = []
        # Call expression: foo()
        query_scm = """(call_expression function: (identifier) @name)"""
        try:
            query = self.LANGUAGE.query(query_scm)
            captures = query.captures(node)
            
            for n, _ in captures:
                func_name = content[n.start_byte:n.end_byte]
                
                # Check Global/Local Symbol Table
                def_info = defined_funcs.get(func_name)
                
                # If found, set correct file_path and lines
                target_file = def_info["file_path"] if def_info else ""
                start_line = def_info["start_line"] if def_info else n.start_point[0] + 1
                end_line = def_info["end_line"] if def_info else n.end_point[0] + 1
                
                calls.append(EndpointNodes(
                    id=f"call-{func_name}-{n.start_point[0]}",
                    path=func_name,
                    method="CALL",
                    language="javascript",
                    type="child",
                    file_path=target_file, 
                    line_number=start_line,
                    end_line_number=end_line,
                    params=[],
                    children=[]
                ))
        except Exception:
            pass
            
        return calls
