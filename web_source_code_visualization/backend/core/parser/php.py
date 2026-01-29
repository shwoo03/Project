from typing import List, Dict
from tree_sitter import Language, Parser
import tree_sitter_php
import os
from .base import BaseParser
from models import EndpointNodes, Parameter

class PHPParser(BaseParser):
    def __init__(self):
        self.LANGUAGE = Language(tree_sitter_php.language_php())
        self.parser = Parser(self.LANGUAGE)

    def can_parse(self, file_path: str) -> bool:
        return file_path.endswith('.php')

    def scan_symbols(self, file_path: str, content: str) -> dict:
        return {}

    def parse(self, file_path: str, content: str) -> List[EndpointNodes]:
        tree = self.parser.parse(bytes(content, "utf8"))
        root_node = tree.root_node
        
        # PHP routing is typically file-based (e.g., login.php)
        # So we create a Root Node for the file itself.
        # But if it's a class file (Model/Controller), we might want to handle it differently.
        # For simple CTF handling, let's treat the file as a "Route".
        
        endpoints = []
        filename = os.path.basename(file_path)
        
        # 1. Global Inputs (Top-level $_GET, etc.)
        global_inputs = self.extract_inputs(root_node, content, file_path)
        
        # 2. Extract Functions
        defined_funcs = self.extract_functions_def(root_node, content)
        
        # 3. Global Calls
        global_calls = self.extract_calls(root_node, content, defined_funcs)

        # Create the main Endpoint for this file
        file_endpoint = EndpointNodes(
            id=f"file-{filename}",
            path=f"/{filename}", # Treat filename as URL path
            method="FILE", # Special method
            type="root",
            file_path=file_path,
            line_number=1,
            end_line_number=len(content.splitlines()),
            params=global_inputs,
            children=global_calls # Global calls are children of the file
        )
        
        # If there are defined functions, we can add them as separate "Routes" or Children?
        # In this visualization, functions are children of the file usually.
        # Let's add them as children nodes of type 'child' (Function Def)
        # Wait, our model strictness: 'child' usually means CALL.
        # But we can reuse the struct.
        
        # Actually, let's stick to the Python model:
        # Route -> [Input, Call, Call...]
        # Defined functions are separate entities unless called.
        # But for viewing source code, we want to start from the File.
        
        endpoints.append(file_endpoint)
        return endpoints

    def extract_inputs(self, node, content: str, file_path: str) -> List[Parameter]:
        inputs = []
        # Query for $_GET, $_POST, $_COOKIE, $_REQUEST
        query_scm = """
        (subscript_expression
            (variable_name) @var
            (string) @key
            (#match? @var "\\$_(GET|POST|COOKIE|REQUEST)")
        )
        """
        query = self.LANGUAGE.query(query_scm)
        captures = query.captures(node)
        
        # Group by pattern: var, key
        # Tree-sitter query returns list of (node, name).
        # We need to iterate carefully.
        
        # Simple iteration for now (assuming pairs)
        # Real robust way is to strictly parse pairs.
        
        processed_nodes = set()
        
        for i in range(0, len(captures), 2):
            if i+1 >= len(captures): break
            
            var_node, var_name = captures[i]
            key_node, key_name = captures[i+1]
            
            if var_name == 'var' and key_name == 'key':
                if var_node.id in processed_nodes: continue
                processed_nodes.add(var_node.id)
                
                var_text = content[var_node.start_byte:var_node.end_byte]
                key_text = content[key_node.start_byte:key_node.end_byte].strip('"\'')
                
                method = "UNKNOWN"
                if "$_GET" in var_text: method = "GET"
                elif "$_POST" in var_text: method = "POST"
                elif "$_COOKIE" in var_text: method = "COOKIE"
                
                inputs.append(Parameter(
                    name=key_text,
                    type="input",
                    file_path=file_path,
                    line_number=var_node.start_point[0] + 1,
                    method=method
                ))
                
        return inputs

    def extract_functions_def(self, node, content: str) -> Dict[str, Dict]:
        defined_funcs = {}
        # PHP function definition
        query_scm = """(function_definition (name) @name)"""
        try:
            query = self.LANGUAGE.query(query_scm)
            captures = query.captures(node)
            for n, _ in captures:
                func_name = content[n.start_byte:n.end_byte]
                parent = n.parent
                defined_funcs[func_name] = {
                    "start_line": parent.start_point[0] + 1,
                    "end_line": parent.end_point[0] + 1,
                    "file_path": "current" # placeholder
                }
        except Exception:
            pass
        return defined_funcs

    def extract_calls(self, node, content: str, defined_funcs: Dict) -> List[EndpointNodes]:
        calls = []
        # PHP function call expression
        query_scm = """(function_call_expression (name) @name)""" # Simplified
        try:
            query = self.LANGUAGE.query(query_scm)
            captures = query.captures(node)
            
            for n, _ in captures:
                func_name = content[n.start_byte:n.end_byte]
                
                # Check definition
                def_info = defined_funcs.get(func_name)
                # If not locally defined, it's external/native
                
                calls.append(EndpointNodes(
                    id=f"call-{func_name}-{n.start_point[0]}",
                    path=func_name,
                    method="CALL",
                    type="child",
                    file_path="current" if def_info else "", # Link if defined
                    line_number=def_info["start_line"] if def_info else n.start_point[0] + 1,
                    end_line_number=def_info["end_line"] if def_info else n.end_point[0] + 1,
                    params=[],
                    children=[]
                ))
        except Exception:
            pass
            
        return calls
