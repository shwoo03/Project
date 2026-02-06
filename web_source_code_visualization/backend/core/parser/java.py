
from typing import List, Dict, Any
from tree_sitter import Language, Parser
import tree_sitter_java
import os
from .base import BaseParser
from models import EndpointNodes, Parameter

class JavaParser(BaseParser):
    def __init__(self):
        self.LANGUAGE = Language(tree_sitter_java.language())
        self.parser = Parser(self.LANGUAGE)

    def can_parse(self, file_path: str) -> bool:
        return file_path.endswith('.java')

    def parse(self, file_path: str, content: str, global_symbols: Dict[str, Dict] = None, symbol_table: Any = None) -> List[EndpointNodes]:
        tree = self.parser.parse(bytes(content, "utf8"))
        root_node = tree.root_node
        
        endpoints = []
        filename = os.path.basename(file_path)
        
        # Java usually has class -> method structure
        # We'll treat public methods as endpoints for now or just map the structure
        
        methods = self.extract_methods(root_node, content, file_path)
        
        # Create Root Node for this file (Class container)
        # Find class name
        class_name = filename.replace(".java", "")
        # Try to find class node for better name
        
        file_endpoint = EndpointNodes(
            id=f"file-{filename}",
            path=f"/{class_name}",
            method="JAVA",
            language="java",
            type="root",
            file_path=file_path,
            line_number=1,
            end_line_number=len(content.splitlines()),
            params=[],
            children=methods
        )
        
        endpoints.append(file_endpoint)
        return endpoints

    def scan_symbols(self, file_path: str, content: str) -> Dict[str, Dict]:
        # Minimal symbol scan
        return {}

    def extract_methods(self, node, content: str, file_path: str) -> List[EndpointNodes]:
        nodes = []
        
        # Traverse for method_declaration
        # We'll use manual traversal or query if captures worked (but captures is flaky in this env)
        # Let's use manual traversal for stability based on recent issues
        
        stack = [node]
        while stack:
            curr = stack.pop()
            
            if curr.type == 'method_declaration':
                # Extract name
                name_node = curr.child_by_field_name('name')
                if name_node:
                    method_name = content[name_node.start_byte:name_node.end_byte]
                    
                    # Extract params
                    params = []
                    params_node = curr.child_by_field_name('parameters')
                    if params_node:
                        for child in params_node.children:
                            if child.type == 'formal_parameter':
                                name_child = child.child_by_field_name('name')
                                if name_child:
                                    p_name = content[name_child.start_byte:name_child.end_byte]
                                    params.append(Parameter(name=p_name, source="arg", type="unknown"))

                    nodes.append(EndpointNodes(
                        id=f"{file_path}:{curr.start_point.row}:{method_name}",
                        path=method_name,
                        method="METHOD",
                        language="java",
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
