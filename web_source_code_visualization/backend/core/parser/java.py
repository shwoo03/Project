from typing import List
from tree_sitter import Language, Parser
import tree_sitter_java
from .base import BaseParser
from models import EndpointNodes

class JavaParser(BaseParser):
    def __init__(self):
        self.LANGUAGE = Language(tree_sitter_java.language())
        self.parser = Parser(self.LANGUAGE)

    def can_parse(self, file_path: str) -> bool:
        return file_path.endswith(".java")

    def scan_symbols(self, file_path: str, content: str) -> dict:
        return {}

    def parse(self, file_path: str, content: str) -> List[EndpointNodes]:
        tree = self.parser.parse(bytes(content, "utf8"))
        root_node = tree.root_node
        endpoints = []
        
        # Placeholder for Java methods
        query = self.LANGUAGE.query("""
        (method_declaration
          name: (identifier) @method_name)
        """)
        
        captures = query.captures(root_node)
        
        for node, _ in captures:
            name_text = node.text.decode('utf-8')
            endpoints.append(EndpointNodes(
                id=f"{file_path}:{node.start_point.row}",
                path=name_text,
                method="FUNC",
                language="java",
                file_path=file_path,
                line_number=node.start_point.row + 1,
                type="child"
            ))
            
        return endpoints
