
from typing import Dict, List, Optional, Any
from enum import Enum
from pydantic import BaseModel, Field

class SymbolType(str, Enum):
    CLASS = "class"
    FUNCTION = "function"
    METHOD = "method"
    VARIABLE = "variable"
    INTERFACE = "interface"
    MODULE = "module"

class Symbol(BaseModel):
    name: str # e.g. "User" or "create_user"
    full_name: str # e.g. "models.User" or "utils.helpers.create_user"
    type: SymbolType
    file_path: str
    line_number: int
    end_line_number: int
    parent_scope: Optional[str] = None # e.g. "models" for User
    
    # For classes
    inherits_from: List[str] = [] # e.g. ["BaseModel", "object"]
    
    # For functions
    params: List[str] = []
    return_type: Optional[str] = None

class SymbolTable:
    def __init__(self):
        # Map full_name -> Symbol
        self.symbols: Dict[str, Symbol] = {}
        # Map file_path -> List[Symbol] (fast lookup for file re-indexing)
        self.file_symbols: Dict[str, List[Symbol]] = {}
        # Map short name -> List[Symbol] (for heuristic resolution)
        self.name_index: Dict[str, List[Symbol]] = {}

    def add(self, symbol: Symbol):
        self.symbols[symbol.full_name] = symbol
        
        if symbol.file_path not in self.file_symbols:
            self.file_symbols[symbol.file_path] = []
        self.file_symbols[symbol.file_path].append(symbol)
        
        if symbol.name not in self.name_index:
            self.name_index[symbol.name] = []
        self.name_index[symbol.name].append(symbol)

    def remove_file(self, file_path: str):
        """Remove all symbols associated with a file (used for re-indexing)"""
        if file_path in self.file_symbols:
            for sym in self.file_symbols[file_path]:
                if sym.full_name in self.symbols:
                    del self.symbols[sym.full_name]
                
                # Setup for name_index cleanup (O(N) for list, but usually small)
                if sym.name in self.name_index:
                    self.name_index[sym.name] = [s for s in self.name_index[sym.name] if s.full_name != sym.full_name]
                    if not self.name_index[sym.name]:
                        del self.name_index[sym.name]
            
            del self.file_symbols[file_path]

    def lookup(self, name: str, current_file: str = None, imports: Dict[str, str] = None) -> Optional[Symbol]:
        """
        Resolve a name to a Symbol.
        Strategy:
        1. Check Exact Match (full_name)
        2. Check Imports (alias -> full_name)
        3. Check Same Module/File
        4. Heuristic: Name Match (if unique)
        """
        # 1. Exact Full Name
        if name in self.symbols:
            return self.symbols[name]
            
        # 2. Imports Mapping (e.g. import utils.helper as h -> h.foo maps to utils.helper.foo)
        if imports:
            # Simple alias check
            if name in imports:
                full = imports[name]
                if full in self.symbols: return self.symbols[full]
        
        # 4. Heuristic (Short Name)
        # If there's only one symbol with this name globally, assume it's that one
        if name in self.name_index:
            candidates = self.name_index[name]
            if len(candidates) == 1:
                return candidates[0]
            # If multiple, we need scoping rules (TODO)
        
        return None

    def get_all(self):
        return list(self.symbols.values())
