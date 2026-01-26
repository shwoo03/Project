from typing import List, Dict
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

    def parse(self, file_path: str, content: str) -> List[EndpointNodes]:
        tree = self.parser.parse(bytes(content, "utf8"))
        root_node = tree.root_node
        
        endpoints = []
        filename = os.path.basename(file_path)
        
        # 1. Inputs (req.query, etc)
        global_inputs = self.extract_inputs(root_node, content, file_path)
        
        # 2. Extract Functions
        defined_funcs = self.extract_functions_def(root_node, content)
        
        # 3. Global Calls
        global_calls = self.extract_calls(root_node, content, defined_funcs)

        # Create Root Node for this file
        file_endpoint = EndpointNodes(
            id=f"file-{filename}",
            path=f"/{filename}",
            method="JS",
            type="root",
            file_path=file_path,
            line_number=1,
            end_line_number=len(content.splitlines()),
            params=global_inputs,
            children=global_calls
        )
        
        endpoints.append(file_endpoint)
        return endpoints

    def extract_inputs(self, node, content: str, file_path: str) -> List[Parameter]:
        inputs = []
        # Generic pattern for req.query.param, req.body.param
        # (member_expression object: (identifier) @obj property: (property_identifier) @prop)
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
            
            # Pattern: req, source, key (tripets)
            # Need to process carefully.
            # Tree-sitter py bindings return individual captures. 
            # We assume order req -> source -> key.
            
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
        # Function declaration
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
            
        # Arrow function assignment: const foo = () => {}
        # (variable_declarator name: (identifier) @name value: (arrow_function))
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
                
                def_info = defined_funcs.get(func_name)
                
                calls.append(EndpointNodes(
                    id=f"call-{func_name}-{n.start_point[0]}",
                    path=func_name,
                    method="CALL",
                    type="child",
                    file_path="current" if def_info else "",
                    line_number=def_info["start_line"] if def_info else n.start_point[0] + 1,
                    end_line_number=def_info["end_line"] if def_info else n.end_point[0] + 1,
                    params=[],
                    children=[]
                ))
        except Exception:
            pass
            
        return calls
