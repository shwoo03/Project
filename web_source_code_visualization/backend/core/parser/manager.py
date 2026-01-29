import os
from typing import Optional
from .base import BaseParser
from .python import PythonParser
from .javascript import JavascriptParser
from .typescript import TypeScriptParser
from .php import PHPParser
from .java import JavaParser
from .go import GoParser

class ParserManager:
    def __init__(self):
        self.parsers: list[BaseParser] = [
            PythonParser(),
            TypeScriptParser(),  # TS must come before JS to handle .ts/.tsx
            JavascriptParser(),
            PHPParser(),
            JavaParser(),
            GoParser()
        ]

    def get_parser(self, file_path: str) -> Optional[BaseParser]:
        """Return the appropriate parser for the file."""
        for parser in self.parsers:
            if parser.can_parse(file_path):
                return parser
        return None
