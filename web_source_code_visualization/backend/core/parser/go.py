
from typing import List, Dict, Any
from tree_sitter import Language, Parser
import tree_sitter_go
import os
from .base import BaseParser
from models import EndpointNodes, Parameter

class GoParser(BaseParser):
    def __init__(self):
        self.LANGUAGE = Language(tree_sitter_go.language())
        self.parser = Parser(self.LANGUAGE)

    def can_parse(self, file_path: str) -> bool:
        return file_path.endswith('.go')

    def parse(self, file_path: str, content: str, global_symbols: Dict[str, Dict] = None, symbol_table: Any = None) -> List[EndpointNodes]:
        tree = self.parser.parse(bytes(content, "utf8"))
        root_node = tree.root_node
        
        endpoints = []
        filename = os.path.basename(file_path)
        
        funcs = self.extract_functions(root_node, content, file_path)
        
        file_endpoint = EndpointNodes(
            id=f"file-{filename}",
            path=f"/{filename}",
            method="GO",
            language="go",
            type="root",
            file_path=file_path,
            line_number=1,
            end_line_number=len(content.splitlines()),
            params=[],
            children=funcs
        )
        
        endpoints.append(file_endpoint)
        return endpoints

    def scan_symbols(self, file_path: str, content: str) -> Dict[str, Dict]:
        return {}

    def extract_functions(self, node, content: str, file_path: str) -> List[EndpointNodes]:
        nodes = []
        
        stack = [node]
        while stack:
            curr = stack.pop()
            
            if curr.type == 'function_declaration' or curr.type == 'method_declaration':
                # Extract name
                name_node = curr.child_by_field_name('name')
                if name_node:
                    func_name = content[name_node.start_byte:name_node.end_byte]
                    
                    # Extract params (parameter_list)
                    params = []
                    # Logic for params simplified
                    
                    nodes.append(EndpointNodes(
                        id=f"{file_path}:{curr.start_point.row}:{func_name}",
                        path=func_name,
                        method="FUNC",
                        language="go",
                        type="child",
                        file_path=file_path,
                        line_number=curr.start_point.row + 1,
                        end_line_number=curr.end_point.row + 1,
                        params=params,
                        children=[] 
                    ))
            
            for child in curr.children:
                stack.append(child)
                
        return nodes
