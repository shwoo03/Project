"""
Type Inference Module.

This module provides type inference for dynamically-typed languages (Python, JavaScript, TypeScript),
enabling more accurate data flow analysis and security vulnerability detection.

Key features:
- Variable type inference from assignments, literals, and expressions
- Function return type inference
- Class instance tracking
- Type hint parsing (Python type annotations, TypeScript types)
- Type narrowing through control flow analysis
- Method resolution with inferred receiver types

Example:
    inferencer = TypeInferencer(project_root="/path/to/project")
    inferencer.analyze_project()
    
    # Get inferred type for a variable
    var_type = inferencer.get_variable_type("user_input", "app.py", line=10)
    
    # Get function return type
    return_type = inferencer.get_return_type("parse_json", "utils.py")
"""

import os
import re
import ast
from typing import List, Dict, Set, Optional, Any, Tuple, Union
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path

import tree_sitter_python
import tree_sitter_javascript
from tree_sitter import Language, Parser

# Try importing TypeScript support
try:
    import tree_sitter_typescript
    HAS_TYPESCRIPT = True
except ImportError:
    HAS_TYPESCRIPT = False


class TypeCategory(Enum):
    """Category of inferred types."""
    PRIMITIVE = "primitive"      # str, int, bool, etc.
    COLLECTION = "collection"    # list, dict, set, etc.
    CLASS = "class"              # User-defined classes
    FUNCTION = "function"        # Callable
    UNION = "union"              # Multiple possible types
    UNKNOWN = "unknown"          # Could not infer
    ANY = "any"                  # Explicitly typed as Any
    NONE = "none"                # None/null/undefined


@dataclass
class TypeInfo:
    """Represents an inferred type."""
    name: str                              # Type name (e.g., "str", "List[int]", "User")
    category: TypeCategory                 # Category of the type
    generic_args: List['TypeInfo'] = field(default_factory=list)  # Generic parameters
    source: str = "inferred"               # How type was determined: "inferred", "annotation", "literal"
    confidence: float = 1.0                # Confidence score (0.0 - 1.0)
    line_number: int = 0                   # Where type was inferred
    is_optional: bool = False              # Optional[T] or T | None
    is_nullable: bool = False              # Can be None/null
    union_types: List['TypeInfo'] = field(default_factory=list)  # For union types
    
    def __str__(self) -> str:
        if self.category == TypeCategory.UNION and self.union_types:
            return " | ".join(str(t) for t in self.union_types)
        if self.generic_args:
            args = ", ".join(str(a) for a in self.generic_args)
            return f"{self.name}[{args}]"
        return self.name
    
    def to_dict(self) -> Dict:
        return {
            "name": self.name,
            "category": self.category.value,
            "generic_args": [a.to_dict() for a in self.generic_args],
            "source": self.source,
            "confidence": self.confidence,
            "is_optional": self.is_optional,
            "is_nullable": self.is_nullable,
            "union_types": [t.to_dict() for t in self.union_types]
        }


@dataclass
class VariableType:
    """Type information for a variable at a specific scope."""
    name: str                          # Variable name
    type_info: TypeInfo                # Inferred type
    scope: str                         # Scope (function name, class, or "global")
    file_path: str                     # File where defined
    line_defined: int                  # Line where first assigned
    line_last_assigned: int            # Line of most recent assignment
    is_parameter: bool = False         # Is this a function parameter?
    is_class_attribute: bool = False   # Is this a class attribute?
    is_constant: bool = False          # Is this a constant (ALL_CAPS)?
    type_history: List[Tuple[int, TypeInfo]] = field(default_factory=list)  # Type changes


@dataclass
class FunctionSignature:
    """Type signature of a function."""
    name: str
    qualified_name: str
    file_path: str
    parameters: List[Tuple[str, TypeInfo]]  # (param_name, type)
    return_type: TypeInfo
    is_method: bool = False
    is_static: bool = False
    is_classmethod: bool = False
    is_async: bool = False
    decorators: List[str] = field(default_factory=list)
    docstring: Optional[str] = None


@dataclass
class ClassType:
    """Type information for a class."""
    name: str
    qualified_name: str
    file_path: str
    line_number: int
    base_classes: List[str] = field(default_factory=list)
    attributes: Dict[str, TypeInfo] = field(default_factory=dict)  # Instance attributes
    class_attributes: Dict[str, TypeInfo] = field(default_factory=dict)
    methods: Dict[str, FunctionSignature] = field(default_factory=dict)
    is_dataclass: bool = False
    is_abstract: bool = False
    type_parameters: List[str] = field(default_factory=list)  # Generic type params


class TypeInferencer:
    """
    Infers types for variables and functions in dynamically-typed languages.
    
    Supports:
    - Python: Type annotations, docstrings, literal inference
    - JavaScript: JSDoc, literal inference, TypeScript definitions
    - TypeScript: Full type annotations
    """
    
    # Python built-in types
    PYTHON_PRIMITIVES = {
        "str", "int", "float", "bool", "bytes", "complex",
        "None", "NoneType", "type", "object"
    }
    
    PYTHON_COLLECTIONS = {
        "list": "List", "dict": "Dict", "set": "Set", "tuple": "Tuple",
        "frozenset": "FrozenSet", "deque": "Deque"
    }
    
    # JavaScript primitive types
    JS_PRIMITIVES = {
        "string", "number", "boolean", "null", "undefined",
        "symbol", "bigint"
    }
    
    def __init__(self, project_root: str):
        self.project_root = os.path.abspath(project_root)
        
        # Type storage
        self.variables: Dict[str, VariableType] = {}  # scope::name -> VariableType
        self.functions: Dict[str, FunctionSignature] = {}  # qualified_name -> signature
        self.classes: Dict[str, ClassType] = {}  # qualified_name -> ClassType
        
        # File to symbols mapping
        self.file_symbols: Dict[str, List[str]] = {}  # file_path -> [symbol_keys]
        
        # Initialize parsers
        self.py_parser = Parser(Language(tree_sitter_python.language()))
        self.js_parser = Parser(Language(tree_sitter_javascript.language()))
        
        if HAS_TYPESCRIPT:
            self.ts_parser = Parser(Language(tree_sitter_typescript.language_typescript()))
            self.tsx_parser = Parser(Language(tree_sitter_typescript.language_tsx()))
        else:
            self.ts_parser = None
            self.tsx_parser = None
        
        # Statistics
        self.stats = {
            "total_files": 0,
            "variables_inferred": 0,
            "functions_analyzed": 0,
            "classes_analyzed": 0,
            "type_annotations_found": 0,
            "types_from_literals": 0,
            "types_from_inference": 0
        }
    
    def analyze_project(self) -> Dict:
        """
        Analyze the entire project for type information.
        
        Returns:
            Dict with variables, functions, classes, and statistics
        """
        self.variables.clear()
        self.functions.clear()
        self.classes.clear()
        self.file_symbols.clear()
        
        for key in self.stats:
            self.stats[key] = 0
        
        # Walk through all source files
        for dirpath, dirnames, filenames in os.walk(self.project_root):
            # Skip common non-source directories
            dirnames[:] = [d for d in dirnames if d not in {
                '__pycache__', 'node_modules', '.git', '.venv', 'venv',
                'dist', 'build', '.next', 'coverage', '.pytest_cache'
            }]
            
            for filename in filenames:
                filepath = os.path.join(dirpath, filename)
                
                if filename.endswith('.py'):
                    self._analyze_python_file(filepath)
                elif filename.endswith(('.js', '.jsx')):
                    self._analyze_javascript_file(filepath)
                elif filename.endswith(('.ts', '.tsx')) and self.ts_parser:
                    self._analyze_typescript_file(filepath)
        
        return self._build_result()
    
    def _analyze_python_file(self, filepath: str):
        """Analyze a Python file for type information."""
        try:
            with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
            content_bytes = content.encode('utf-8')
        except Exception:
            return
        
        self.stats["total_files"] += 1
        tree = self.py_parser.parse(content_bytes)
        
        # Track current scope
        rel_path = os.path.relpath(filepath, self.project_root)
        module_name = rel_path.replace(os.sep, ".").replace(".py", "")
        
        self._extract_python_types(tree.root_node, filepath, content_bytes, module_name, "global")
    
    def _extract_python_types(self, node, filepath: str, content_bytes: bytes, 
                               module_name: str, scope: str, current_class: str = None):
        """Recursively extract type information from Python AST."""
        
        if node.type == 'class_definition':
            class_name = self._get_node_text(node.child_by_field_name('name'), content_bytes)
            if class_name:
                qualified = f"{module_name}.{class_name}"
                
                # Get base classes
                bases = []
                args_node = node.child_by_field_name('superclasses')
                if args_node:
                    for child in args_node.children:
                        if child.type in ('identifier', 'attribute'):
                            bases.append(self._get_node_text(child, content_bytes))
                
                # Check for dataclass decorator
                is_dataclass = False
                is_abstract = False
                for child in node.children:
                    if child.type == 'decorator':
                        dec_text = self._get_node_text(child, content_bytes)
                        if 'dataclass' in dec_text:
                            is_dataclass = True
                        if 'abstractmethod' in dec_text or 'ABC' in dec_text:
                            is_abstract = True
                
                class_type = ClassType(
                    name=class_name,
                    qualified_name=qualified,
                    file_path=filepath,
                    line_number=node.start_point[0] + 1,
                    base_classes=bases,
                    is_dataclass=is_dataclass,
                    is_abstract=is_abstract
                )
                self.classes[qualified] = class_type
                self.stats["classes_analyzed"] += 1
                
                # Process class body
                body = node.child_by_field_name('body')
                if body:
                    for child in body.children:
                        self._extract_python_types(child, filepath, content_bytes, 
                                                    module_name, class_name, class_name)
                return
        
        elif node.type == 'function_definition':
            self._analyze_python_function(node, filepath, content_bytes, 
                                           module_name, scope, current_class)
            return
        
        elif node.type == 'assignment':
            self._analyze_python_assignment(node, filepath, content_bytes, 
                                             module_name, scope, current_class)
        
        elif node.type == 'annotated_assignment':
            self._analyze_python_annotated_assignment(node, filepath, content_bytes,
                                                       module_name, scope, current_class)
        
        # Continue traversing
        for child in node.children:
            self._extract_python_types(child, filepath, content_bytes, 
                                        module_name, scope, current_class)
    
    def _analyze_python_function(self, node, filepath: str, content_bytes: bytes,
                                   module_name: str, scope: str, current_class: str = None):
        """Analyze a Python function for type information."""
        func_name = self._get_node_text(node.child_by_field_name('name'), content_bytes)
        if not func_name:
            return
        
        if current_class:
            qualified = f"{module_name}.{current_class}.{func_name}"
            is_method = True
        else:
            qualified = f"{module_name}.{func_name}"
            is_method = False
        
        # Get decorators
        decorators = []
        is_static = False
        is_classmethod = False
        is_async = node.type == 'async_function_definition'
        
        for child in node.children:
            if child.type == 'decorator':
                dec_text = self._get_node_text(child, content_bytes)
                decorators.append(dec_text)
                if '@staticmethod' in dec_text:
                    is_static = True
                if '@classmethod' in dec_text:
                    is_classmethod = True
        
        # Parse parameters with type annotations
        parameters = []
        params_node = node.child_by_field_name('parameters')
        if params_node:
            for param in params_node.children:
                if param.type in ('identifier', 'typed_parameter', 'default_parameter', 
                                   'typed_default_parameter'):
                    param_name, param_type = self._parse_python_parameter(param, content_bytes)
                    if param_name and param_name not in ('self', 'cls'):
                        parameters.append((param_name, param_type))
        
        # Parse return type annotation
        return_annotation = node.child_by_field_name('return_type')
        if return_annotation:
            return_type = self._parse_python_type_annotation(return_annotation, content_bytes)
            self.stats["type_annotations_found"] += 1
        else:
            # Try to infer from return statements
            return_type = self._infer_python_return_type(node, content_bytes)
        
        signature = FunctionSignature(
            name=func_name,
            qualified_name=qualified,
            file_path=filepath,
            parameters=parameters,
            return_type=return_type,
            is_method=is_method,
            is_static=is_static,
            is_classmethod=is_classmethod,
            is_async=is_async,
            decorators=decorators
        )
        self.functions[qualified] = signature
        self.stats["functions_analyzed"] += 1
        
        # Analyze function body for local variables
        body = node.child_by_field_name('body')
        if body:
            func_scope = f"{current_class}.{func_name}" if current_class else func_name
            for child in body.children:
                self._extract_python_types(child, filepath, content_bytes,
                                            module_name, func_scope, current_class)
    
    def _parse_python_parameter(self, param_node, content_bytes: bytes) -> Tuple[str, TypeInfo]:
        """Parse a Python function parameter with optional type annotation."""
        if param_node.type == 'identifier':
            name = self._get_node_text(param_node, content_bytes)
            return name, TypeInfo("Any", TypeCategory.ANY, source="no_annotation")
        
        elif param_node.type == 'typed_parameter':
            name_node = param_node.child_by_field_name('name') or param_node.children[0]
            name = self._get_node_text(name_node, content_bytes)
            
            type_node = param_node.child_by_field_name('type')
            if type_node:
                type_info = self._parse_python_type_annotation(type_node, content_bytes)
                self.stats["type_annotations_found"] += 1
            else:
                type_info = TypeInfo("Any", TypeCategory.ANY, source="no_annotation")
            
            return name, type_info
        
        elif param_node.type in ('default_parameter', 'typed_default_parameter'):
            # Has default value - can infer type from it
            name_node = param_node.child_by_field_name('name') or param_node.children[0]
            name = self._get_node_text(name_node, content_bytes)
            
            type_node = param_node.child_by_field_name('type')
            if type_node:
                type_info = self._parse_python_type_annotation(type_node, content_bytes)
                self.stats["type_annotations_found"] += 1
            else:
                # Infer from default value
                value_node = param_node.child_by_field_name('value')
                if value_node:
                    type_info = self._infer_type_from_expression(value_node, content_bytes)
                else:
                    type_info = TypeInfo("Any", TypeCategory.ANY, source="no_annotation")
            
            return name, type_info
        
        return None, TypeInfo("Any", TypeCategory.ANY)
    
    def _parse_python_type_annotation(self, type_node, content_bytes: bytes) -> TypeInfo:
        """Parse a Python type annotation into TypeInfo."""
        type_text = self._get_node_text(type_node, content_bytes)
        if not type_text:
            return TypeInfo("Any", TypeCategory.ANY)
        
        # Handle Optional
        if type_text.startswith("Optional["):
            inner = type_text[9:-1]
            inner_type = self._parse_type_string(inner)
            inner_type.is_optional = True
            inner_type.is_nullable = True
            return inner_type
        
        # Handle Union
        if type_text.startswith("Union["):
            inner = type_text[6:-1]
            types = self._split_type_args(inner)
            union_types = [self._parse_type_string(t.strip()) for t in types]
            return TypeInfo(
                name=type_text,
                category=TypeCategory.UNION,
                union_types=union_types,
                source="annotation"
            )
        
        # Handle | union syntax (Python 3.10+)
        if ' | ' in type_text:
            types = type_text.split(' | ')
            union_types = [self._parse_type_string(t.strip()) for t in types]
            is_optional = any(t.name in ('None', 'NoneType') for t in union_types)
            return TypeInfo(
                name=type_text,
                category=TypeCategory.UNION,
                union_types=union_types,
                is_optional=is_optional,
                source="annotation"
            )
        
        return self._parse_type_string(type_text)
    
    def _parse_type_string(self, type_str: str) -> TypeInfo:
        """Parse a type string into TypeInfo."""
        type_str = type_str.strip()
        
        # Check for generics
        if '[' in type_str and type_str.endswith(']'):
            bracket_pos = type_str.index('[')
            base_type = type_str[:bracket_pos]
            args_str = type_str[bracket_pos + 1:-1]
            args = self._split_type_args(args_str)
            generic_args = [self._parse_type_string(a.strip()) for a in args]
            
            category = TypeCategory.COLLECTION if base_type in ('List', 'Dict', 'Set', 'Tuple') else TypeCategory.CLASS
            return TypeInfo(
                name=base_type,
                category=category,
                generic_args=generic_args,
                source="annotation"
            )
        
        # Primitives
        if type_str in self.PYTHON_PRIMITIVES:
            return TypeInfo(type_str, TypeCategory.PRIMITIVE, source="annotation")
        
        # Collections without generics
        if type_str in self.PYTHON_COLLECTIONS:
            return TypeInfo(type_str, TypeCategory.COLLECTION, source="annotation")
        
        # Special types
        if type_str in ('Any', 'any'):
            return TypeInfo("Any", TypeCategory.ANY, source="annotation")
        if type_str in ('None', 'NoneType'):
            return TypeInfo("None", TypeCategory.NONE, source="annotation")
        if type_str == 'Callable':
            return TypeInfo("Callable", TypeCategory.FUNCTION, source="annotation")
        
        # Assume class type
        return TypeInfo(type_str, TypeCategory.CLASS, source="annotation")
    
    def _split_type_args(self, args_str: str) -> List[str]:
        """Split generic type arguments, respecting nested brackets."""
        args = []
        current = ""
        depth = 0
        
        for char in args_str:
            if char == '[':
                depth += 1
                current += char
            elif char == ']':
                depth -= 1
                current += char
            elif char == ',' and depth == 0:
                args.append(current.strip())
                current = ""
            else:
                current += char
        
        if current.strip():
            args.append(current.strip())
        
        return args
    
    def _infer_python_return_type(self, func_node, content_bytes: bytes) -> TypeInfo:
        """Infer function return type from return statements."""
        return_types = []
        
        def find_returns(node):
            if node.type == 'return_statement':
                value = node.child_by_field_name('value') or (
                    node.children[1] if len(node.children) > 1 else None
                )
                if value:
                    inferred = self._infer_type_from_expression(value, content_bytes)
                    return_types.append(inferred)
                else:
                    return_types.append(TypeInfo("None", TypeCategory.NONE, source="inferred"))
            
            for child in node.children:
                # Don't recurse into nested functions
                if child.type not in ('function_definition', 'async_function_definition'):
                    find_returns(child)
        
        find_returns(func_node)
        
        if not return_types:
            return TypeInfo("None", TypeCategory.NONE, source="inferred", confidence=0.5)
        
        if len(return_types) == 1:
            return return_types[0]
        
        # Multiple return types - create union
        unique_types = []
        seen = set()
        for t in return_types:
            key = str(t)
            if key not in seen:
                seen.add(key)
                unique_types.append(t)
        
        if len(unique_types) == 1:
            return unique_types[0]
        
        self.stats["types_from_inference"] += 1
        return TypeInfo(
            name="Union",
            category=TypeCategory.UNION,
            union_types=unique_types,
            source="inferred",
            confidence=0.7
        )
    
    def _infer_type_from_expression(self, expr_node, content_bytes: bytes) -> TypeInfo:
        """Infer type from an expression."""
        node_type = expr_node.type
        
        # Literals
        if node_type == 'string':
            self.stats["types_from_literals"] += 1
            return TypeInfo("str", TypeCategory.PRIMITIVE, source="literal")
        
        if node_type == 'integer':
            self.stats["types_from_literals"] += 1
            return TypeInfo("int", TypeCategory.PRIMITIVE, source="literal")
        
        if node_type == 'float':
            self.stats["types_from_literals"] += 1
            return TypeInfo("float", TypeCategory.PRIMITIVE, source="literal")
        
        if node_type in ('true', 'false'):
            self.stats["types_from_literals"] += 1
            return TypeInfo("bool", TypeCategory.PRIMITIVE, source="literal")
        
        if node_type == 'none':
            self.stats["types_from_literals"] += 1
            return TypeInfo("None", TypeCategory.NONE, source="literal")
        
        if node_type == 'list':
            self.stats["types_from_literals"] += 1
            # Try to infer element type
            element_type = self._infer_collection_element_type(expr_node, content_bytes)
            return TypeInfo("list", TypeCategory.COLLECTION, 
                          generic_args=[element_type] if element_type.name != "Any" else [],
                          source="literal")
        
        if node_type == 'dictionary':
            self.stats["types_from_literals"] += 1
            return TypeInfo("dict", TypeCategory.COLLECTION, source="literal")
        
        if node_type == 'set':
            self.stats["types_from_literals"] += 1
            return TypeInfo("set", TypeCategory.COLLECTION, source="literal")
        
        if node_type == 'tuple':
            self.stats["types_from_literals"] += 1
            return TypeInfo("tuple", TypeCategory.COLLECTION, source="literal")
        
        # Call expression - try to resolve return type
        if node_type == 'call':
            return self._infer_call_return_type(expr_node, content_bytes)
        
        # Attribute access
        if node_type == 'attribute':
            return TypeInfo("Any", TypeCategory.ANY, source="inferred", confidence=0.3)
        
        # Binary operations
        if node_type == 'binary_operator':
            return self._infer_binary_op_type(expr_node, content_bytes)
        
        # Identifier - look up in variables
        if node_type == 'identifier':
            name = self._get_node_text(expr_node, content_bytes)
            # Check if it's a known class constructor
            for class_name, class_info in self.classes.items():
                if class_info.name == name:
                    return TypeInfo(name, TypeCategory.CLASS, source="inferred")
            return TypeInfo("Any", TypeCategory.ANY, source="inferred", confidence=0.3)
        
        return TypeInfo("Any", TypeCategory.ANY, source="inferred", confidence=0.2)
    
    def _infer_collection_element_type(self, collection_node, content_bytes: bytes) -> TypeInfo:
        """Infer the element type of a collection literal."""
        element_types = []
        
        for child in collection_node.children:
            if child.type not in ('[', ']', '{', '}', '(', ')', ','):
                elem_type = self._infer_type_from_expression(child, content_bytes)
                if elem_type.category != TypeCategory.ANY:
                    element_types.append(elem_type)
        
        if not element_types:
            return TypeInfo("Any", TypeCategory.ANY)
        
        # If all elements have the same type, use that
        first_type = str(element_types[0])
        if all(str(t) == first_type for t in element_types):
            return element_types[0]
        
        # Mixed types - return Any
        return TypeInfo("Any", TypeCategory.ANY)
    
    def _infer_call_return_type(self, call_node, content_bytes: bytes) -> TypeInfo:
        """Infer return type from a function call."""
        func_node = call_node.child_by_field_name('function')
        if not func_node:
            return TypeInfo("Any", TypeCategory.ANY, source="inferred")
        
        func_name = self._get_node_text(func_node, content_bytes)
        
        # Built-in constructors
        builtin_returns = {
            "str": TypeInfo("str", TypeCategory.PRIMITIVE, source="builtin"),
            "int": TypeInfo("int", TypeCategory.PRIMITIVE, source="builtin"),
            "float": TypeInfo("float", TypeCategory.PRIMITIVE, source="builtin"),
            "bool": TypeInfo("bool", TypeCategory.PRIMITIVE, source="builtin"),
            "list": TypeInfo("list", TypeCategory.COLLECTION, source="builtin"),
            "dict": TypeInfo("dict", TypeCategory.COLLECTION, source="builtin"),
            "set": TypeInfo("set", TypeCategory.COLLECTION, source="builtin"),
            "tuple": TypeInfo("tuple", TypeCategory.COLLECTION, source="builtin"),
            "len": TypeInfo("int", TypeCategory.PRIMITIVE, source="builtin"),
            "range": TypeInfo("range", TypeCategory.COLLECTION, source="builtin"),
            "open": TypeInfo("TextIO", TypeCategory.CLASS, source="builtin"),
        }
        
        if func_name in builtin_returns:
            return builtin_returns[func_name]
        
        # Check if it's a known class constructor
        for class_name, class_info in self.classes.items():
            if class_info.name == func_name:
                self.stats["types_from_inference"] += 1
                return TypeInfo(func_name, TypeCategory.CLASS, source="inferred")
        
        # Check if it's a known function
        for qual_name, func_sig in self.functions.items():
            if func_sig.name == func_name:
                return func_sig.return_type
        
        return TypeInfo("Any", TypeCategory.ANY, source="inferred", confidence=0.3)
    
    def _infer_binary_op_type(self, bin_op_node, content_bytes: bytes) -> TypeInfo:
        """Infer type from binary operation."""
        operator_node = bin_op_node.child_by_field_name('operator')
        if not operator_node:
            # Try to find operator in children
            for child in bin_op_node.children:
                text = self._get_node_text(child, content_bytes)
                if text in ('+', '-', '*', '/', '//', '%', '**', '&', '|', '^', 
                           '==', '!=', '<', '>', '<=', '>=', 'and', 'or', 'in', 'not in'):
                    operator = text
                    break
            else:
                return TypeInfo("Any", TypeCategory.ANY)
        else:
            operator = self._get_node_text(operator_node, content_bytes)
        
        # Comparison operators return bool
        if operator in ('==', '!=', '<', '>', '<=', '>=', 'in', 'not in', 'is', 'is not'):
            return TypeInfo("bool", TypeCategory.PRIMITIVE, source="inferred")
        
        # Logical operators return bool
        if operator in ('and', 'or'):
            return TypeInfo("bool", TypeCategory.PRIMITIVE, source="inferred")
        
        # Arithmetic operators - infer from operands
        left = bin_op_node.child_by_field_name('left') or (bin_op_node.children[0] if bin_op_node.children else None)
        if left:
            left_type = self._infer_type_from_expression(left, content_bytes)
            if left_type.name in ('int', 'float'):
                return left_type
            if left_type.name == 'str' and operator == '+':
                return TypeInfo("str", TypeCategory.PRIMITIVE, source="inferred")
        
        return TypeInfo("Any", TypeCategory.ANY, source="inferred", confidence=0.5)
    
    def _analyze_python_assignment(self, node, filepath: str, content_bytes: bytes,
                                     module_name: str, scope: str, current_class: str = None):
        """Analyze a Python assignment for variable types."""
        left = node.child_by_field_name('left') or (node.children[0] if node.children else None)
        right = node.child_by_field_name('right') or (node.children[2] if len(node.children) > 2 else None)
        
        if not left or not right:
            return
        
        var_name = self._get_node_text(left, content_bytes)
        if not var_name or '.' in var_name:  # Skip attribute assignments for now
            return
        
        type_info = self._infer_type_from_expression(right, content_bytes)
        type_info.line_number = node.start_point[0] + 1
        
        key = f"{scope}::{var_name}"
        is_constant = var_name.isupper()
        is_class_attr = current_class is not None and scope == current_class
        
        var_type = VariableType(
            name=var_name,
            type_info=type_info,
            scope=scope,
            file_path=filepath,
            line_defined=node.start_point[0] + 1,
            line_last_assigned=node.start_point[0] + 1,
            is_class_attribute=is_class_attr,
            is_constant=is_constant
        )
        
        self.variables[key] = var_type
        self.stats["variables_inferred"] += 1
        
        # Add to class attributes if applicable
        if is_class_attr and current_class:
            for qual_name, class_info in self.classes.items():
                if class_info.name == current_class:
                    class_info.class_attributes[var_name] = type_info
                    break
    
    def _analyze_python_annotated_assignment(self, node, filepath: str, content_bytes: bytes,
                                               module_name: str, scope: str, current_class: str = None):
        """Analyze a Python annotated assignment (x: int = 5)."""
        name_node = node.child_by_field_name('name') or (node.children[0] if node.children else None)
        type_node = node.child_by_field_name('type')
        value_node = node.child_by_field_name('value')
        
        if not name_node:
            return
        
        var_name = self._get_node_text(name_node, content_bytes)
        if not var_name:
            return
        
        if type_node:
            type_info = self._parse_python_type_annotation(type_node, content_bytes)
            type_info.source = "annotation"
            self.stats["type_annotations_found"] += 1
        elif value_node:
            type_info = self._infer_type_from_expression(value_node, content_bytes)
        else:
            type_info = TypeInfo("Any", TypeCategory.ANY)
        
        type_info.line_number = node.start_point[0] + 1
        
        key = f"{scope}::{var_name}"
        is_class_attr = current_class is not None and scope == current_class
        
        var_type = VariableType(
            name=var_name,
            type_info=type_info,
            scope=scope,
            file_path=filepath,
            line_defined=node.start_point[0] + 1,
            line_last_assigned=node.start_point[0] + 1,
            is_class_attribute=is_class_attr
        )
        
        self.variables[key] = var_type
        self.stats["variables_inferred"] += 1
        
        # Add to class attributes
        if is_class_attr and current_class:
            for qual_name, class_info in self.classes.items():
                if class_info.name == current_class:
                    class_info.attributes[var_name] = type_info
                    break
    
    def _analyze_javascript_file(self, filepath: str):
        """Analyze a JavaScript file for type information."""
        try:
            with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
            content_bytes = content.encode('utf-8')
        except Exception:
            return
        
        self.stats["total_files"] += 1
        tree = self.js_parser.parse(content_bytes)
        
        rel_path = os.path.relpath(filepath, self.project_root)
        module_name = rel_path.replace(os.sep, "/").replace(".js", "").replace(".jsx", "")
        
        self._extract_js_types(tree.root_node, filepath, content_bytes, module_name, "global")
    
    def _analyze_typescript_file(self, filepath: str):
        """Analyze a TypeScript file for type information."""
        try:
            with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
            content_bytes = content.encode('utf-8')
        except Exception:
            return
        
        self.stats["total_files"] += 1
        
        parser = self.tsx_parser if filepath.endswith('.tsx') else self.ts_parser
        if not parser:
            return
        
        tree = parser.parse(content_bytes)
        
        rel_path = os.path.relpath(filepath, self.project_root)
        module_name = rel_path.replace(os.sep, "/").replace(".ts", "").replace(".tsx", "")
        
        self._extract_ts_types(tree.root_node, filepath, content_bytes, module_name, "global")
    
    def _extract_js_types(self, node, filepath: str, content_bytes: bytes,
                           module_name: str, scope: str, current_class: str = None):
        """Extract type information from JavaScript AST."""
        
        if node.type == 'class_declaration':
            class_name_node = node.child_by_field_name('name')
            if class_name_node:
                class_name = self._get_node_text(class_name_node, content_bytes)
                qualified = f"{module_name}/{class_name}"
                
                # Get extends
                bases = []
                heritage = node.child_by_field_name('heritage')
                if heritage:
                    bases.append(self._get_node_text(heritage, content_bytes))
                
                class_type = ClassType(
                    name=class_name,
                    qualified_name=qualified,
                    file_path=filepath,
                    line_number=node.start_point[0] + 1,
                    base_classes=bases
                )
                self.classes[qualified] = class_type
                self.stats["classes_analyzed"] += 1
                
                # Process class body
                body = node.child_by_field_name('body')
                if body:
                    for child in body.children:
                        self._extract_js_types(child, filepath, content_bytes,
                                               module_name, class_name, class_name)
                return
        
        elif node.type in ('function_declaration', 'arrow_function', 'method_definition'):
            self._analyze_js_function(node, filepath, content_bytes, 
                                       module_name, scope, current_class)
        
        elif node.type == 'variable_declaration':
            self._analyze_js_variable(node, filepath, content_bytes,
                                       module_name, scope)
        
        # Continue traversing
        for child in node.children:
            self._extract_js_types(child, filepath, content_bytes,
                                    module_name, scope, current_class)
    
    def _analyze_js_function(self, node, filepath: str, content_bytes: bytes,
                              module_name: str, scope: str, current_class: str = None):
        """Analyze a JavaScript function."""
        func_name = None
        
        if node.type == 'function_declaration':
            name_node = node.child_by_field_name('name')
            if name_node:
                func_name = self._get_node_text(name_node, content_bytes)
        elif node.type == 'method_definition':
            name_node = node.child_by_field_name('name')
            if name_node:
                func_name = self._get_node_text(name_node, content_bytes)
        
        if not func_name:
            return
        
        if current_class:
            qualified = f"{module_name}/{current_class}.{func_name}"
            is_method = True
        else:
            qualified = f"{module_name}/{func_name}"
            is_method = False
        
        # Parse parameters (no types in plain JS)
        parameters = []
        params_node = node.child_by_field_name('parameters')
        if params_node:
            for param in params_node.children:
                if param.type == 'identifier':
                    param_name = self._get_node_text(param, content_bytes)
                    parameters.append((param_name, TypeInfo("any", TypeCategory.ANY, source="no_annotation")))
        
        signature = FunctionSignature(
            name=func_name,
            qualified_name=qualified,
            file_path=filepath,
            parameters=parameters,
            return_type=TypeInfo("any", TypeCategory.ANY, source="inferred"),
            is_method=is_method,
            is_async='async' in self._get_node_text(node, content_bytes)[:20]
        )
        self.functions[qualified] = signature
        self.stats["functions_analyzed"] += 1
    
    def _analyze_js_variable(self, node, filepath: str, content_bytes: bytes,
                              module_name: str, scope: str):
        """Analyze a JavaScript variable declaration."""
        for child in node.children:
            if child.type == 'variable_declarator':
                name_node = child.child_by_field_name('name')
                value_node = child.child_by_field_name('value')
                
                if name_node:
                    var_name = self._get_node_text(name_node, content_bytes)
                    if value_node:
                        type_info = self._infer_js_type_from_expression(value_node, content_bytes)
                    else:
                        type_info = TypeInfo("undefined", TypeCategory.NONE, source="inferred")
                    
                    type_info.line_number = node.start_point[0] + 1
                    key = f"{scope}::{var_name}"
                    
                    # Check if const
                    is_const = 'const' in self._get_node_text(node, content_bytes)[:10]
                    
                    var_type = VariableType(
                        name=var_name,
                        type_info=type_info,
                        scope=scope,
                        file_path=filepath,
                        line_defined=node.start_point[0] + 1,
                        line_last_assigned=node.start_point[0] + 1,
                        is_constant=is_const
                    )
                    self.variables[key] = var_type
                    self.stats["variables_inferred"] += 1
    
    def _infer_js_type_from_expression(self, expr_node, content_bytes: bytes) -> TypeInfo:
        """Infer type from a JavaScript expression."""
        node_type = expr_node.type
        
        if node_type == 'string':
            return TypeInfo("string", TypeCategory.PRIMITIVE, source="literal")
        if node_type == 'number':
            return TypeInfo("number", TypeCategory.PRIMITIVE, source="literal")
        if node_type in ('true', 'false'):
            return TypeInfo("boolean", TypeCategory.PRIMITIVE, source="literal")
        if node_type == 'null':
            return TypeInfo("null", TypeCategory.NONE, source="literal")
        if node_type == 'undefined':
            return TypeInfo("undefined", TypeCategory.NONE, source="literal")
        if node_type == 'array':
            return TypeInfo("Array", TypeCategory.COLLECTION, source="literal")
        if node_type == 'object':
            return TypeInfo("object", TypeCategory.CLASS, source="literal")
        if node_type in ('arrow_function', 'function'):
            return TypeInfo("Function", TypeCategory.FUNCTION, source="literal")
        
        if node_type == 'new_expression':
            constructor = expr_node.child_by_field_name('constructor')
            if constructor:
                class_name = self._get_node_text(constructor, content_bytes)
                return TypeInfo(class_name, TypeCategory.CLASS, source="inferred")
        
        return TypeInfo("any", TypeCategory.ANY, source="inferred")
    
    def _extract_ts_types(self, node, filepath: str, content_bytes: bytes,
                           module_name: str, scope: str, current_class: str = None):
        """Extract type information from TypeScript AST."""
        
        if node.type == 'class_declaration':
            class_name_node = node.child_by_field_name('name')
            if class_name_node:
                class_name = self._get_node_text(class_name_node, content_bytes)
                qualified = f"{module_name}/{class_name}"
                
                # Get extends/implements
                bases = []
                for child in node.children:
                    if child.type == 'class_heritage':
                        heritage_text = self._get_node_text(child, content_bytes)
                        # Extract class names from extends/implements
                        if 'extends' in heritage_text or 'implements' in heritage_text:
                            # Simple extraction
                            parts = heritage_text.replace('extends', '').replace('implements', '').split(',')
                            bases.extend([p.strip() for p in parts if p.strip()])
                
                class_type = ClassType(
                    name=class_name,
                    qualified_name=qualified,
                    file_path=filepath,
                    line_number=node.start_point[0] + 1,
                    base_classes=bases
                )
                self.classes[qualified] = class_type
                self.stats["classes_analyzed"] += 1
                
                # Process class body
                body = node.child_by_field_name('body')
                if body:
                    for child in body.children:
                        self._extract_ts_types(child, filepath, content_bytes,
                                                module_name, class_name, class_name)
                return
        
        elif node.type == 'interface_declaration':
            self._analyze_ts_interface(node, filepath, content_bytes, module_name)
        
        elif node.type in ('function_declaration', 'arrow_function', 'method_definition'):
            self._analyze_ts_function(node, filepath, content_bytes,
                                       module_name, scope, current_class)
        
        elif node.type in ('variable_declaration', 'lexical_declaration'):
            self._analyze_ts_variable(node, filepath, content_bytes,
                                       module_name, scope)
        
        # Continue traversing
        for child in node.children:
            self._extract_ts_types(child, filepath, content_bytes,
                                    module_name, scope, current_class)
    
    def _analyze_ts_interface(self, node, filepath: str, content_bytes: bytes, module_name: str):
        """Analyze a TypeScript interface."""
        name_node = node.child_by_field_name('name')
        if not name_node:
            return
        
        interface_name = self._get_node_text(name_node, content_bytes)
        qualified = f"{module_name}/{interface_name}"
        
        # Get extends
        bases = []
        for child in node.children:
            if child.type == 'extends_type_clause':
                extends_text = self._get_node_text(child, content_bytes)
                bases.extend([b.strip() for b in extends_text.replace('extends', '').split(',')])
        
        class_type = ClassType(
            name=interface_name,
            qualified_name=qualified,
            file_path=filepath,
            line_number=node.start_point[0] + 1,
            base_classes=bases,
            is_abstract=True  # Interfaces are abstract by nature
        )
        self.classes[qualified] = class_type
        self.stats["classes_analyzed"] += 1
    
    def _analyze_ts_function(self, node, filepath: str, content_bytes: bytes,
                              module_name: str, scope: str, current_class: str = None):
        """Analyze a TypeScript function with type annotations."""
        func_name = None
        
        if node.type in ('function_declaration', 'method_definition'):
            name_node = node.child_by_field_name('name')
            if name_node:
                func_name = self._get_node_text(name_node, content_bytes)
        
        if not func_name:
            return
        
        if current_class:
            qualified = f"{module_name}/{current_class}.{func_name}"
            is_method = True
        else:
            qualified = f"{module_name}/{func_name}"
            is_method = False
        
        # Parse parameters with types
        parameters = []
        params_node = node.child_by_field_name('parameters')
        if params_node:
            for param in params_node.children:
                if param.type in ('required_parameter', 'optional_parameter'):
                    name_node = param.child_by_field_name('pattern') or param.children[0]
                    param_name = self._get_node_text(name_node, content_bytes)
                    
                    type_node = param.child_by_field_name('type')
                    if type_node:
                        type_info = self._parse_ts_type(type_node, content_bytes)
                        self.stats["type_annotations_found"] += 1
                    else:
                        type_info = TypeInfo("any", TypeCategory.ANY, source="no_annotation")
                    
                    if param_name:
                        parameters.append((param_name, type_info))
        
        # Parse return type
        return_type_node = node.child_by_field_name('return_type')
        if return_type_node:
            return_type = self._parse_ts_type(return_type_node, content_bytes)
            self.stats["type_annotations_found"] += 1
        else:
            return_type = TypeInfo("any", TypeCategory.ANY, source="inferred")
        
        signature = FunctionSignature(
            name=func_name,
            qualified_name=qualified,
            file_path=filepath,
            parameters=parameters,
            return_type=return_type,
            is_method=is_method,
            is_async='async' in self._get_node_text(node, content_bytes)[:20]
        )
        self.functions[qualified] = signature
        self.stats["functions_analyzed"] += 1
    
    def _analyze_ts_variable(self, node, filepath: str, content_bytes: bytes,
                              module_name: str, scope: str):
        """Analyze a TypeScript variable declaration."""
        for child in node.children:
            if child.type == 'variable_declarator':
                name_node = child.child_by_field_name('name')
                type_node = child.child_by_field_name('type')
                value_node = child.child_by_field_name('value')
                
                if name_node:
                    var_name = self._get_node_text(name_node, content_bytes)
                    
                    if type_node:
                        type_info = self._parse_ts_type(type_node, content_bytes)
                        self.stats["type_annotations_found"] += 1
                    elif value_node:
                        type_info = self._infer_js_type_from_expression(value_node, content_bytes)
                    else:
                        type_info = TypeInfo("any", TypeCategory.ANY, source="no_annotation")
                    
                    type_info.line_number = node.start_point[0] + 1
                    key = f"{scope}::{var_name}"
                    
                    is_const = 'const' in self._get_node_text(node, content_bytes)[:10]
                    
                    var_type = VariableType(
                        name=var_name,
                        type_info=type_info,
                        scope=scope,
                        file_path=filepath,
                        line_defined=node.start_point[0] + 1,
                        line_last_assigned=node.start_point[0] + 1,
                        is_constant=is_const
                    )
                    self.variables[key] = var_type
                    self.stats["variables_inferred"] += 1
    
    def _parse_ts_type(self, type_node, content_bytes: bytes) -> TypeInfo:
        """Parse a TypeScript type annotation."""
        type_text = self._get_node_text(type_node, content_bytes)
        if not type_text:
            return TypeInfo("any", TypeCategory.ANY)
        
        # Remove leading colon if present
        type_text = type_text.lstrip(': ')
        
        # Handle union types
        if ' | ' in type_text:
            types = type_text.split(' | ')
            union_types = [self._parse_ts_type_string(t.strip()) for t in types]
            return TypeInfo(
                name=type_text,
                category=TypeCategory.UNION,
                union_types=union_types,
                source="annotation"
            )
        
        return self._parse_ts_type_string(type_text)
    
    def _parse_ts_type_string(self, type_str: str) -> TypeInfo:
        """Parse a TypeScript type string."""
        type_str = type_str.strip()
        
        # Array types
        if type_str.endswith('[]'):
            element_type = self._parse_ts_type_string(type_str[:-2])
            return TypeInfo("Array", TypeCategory.COLLECTION, 
                          generic_args=[element_type], source="annotation")
        
        # Generic types
        if '<' in type_str and type_str.endswith('>'):
            bracket_pos = type_str.index('<')
            base_type = type_str[:bracket_pos]
            args_str = type_str[bracket_pos + 1:-1]
            args = self._split_type_args(args_str)
            generic_args = [self._parse_ts_type_string(a.strip()) for a in args]
            
            return TypeInfo(base_type, TypeCategory.CLASS, 
                          generic_args=generic_args, source="annotation")
        
        # Primitives
        if type_str in self.JS_PRIMITIVES:
            return TypeInfo(type_str, TypeCategory.PRIMITIVE, source="annotation")
        
        if type_str == 'any':
            return TypeInfo("any", TypeCategory.ANY, source="annotation")
        if type_str in ('void', 'never'):
            return TypeInfo(type_str, TypeCategory.NONE, source="annotation")
        
        # Assume class/interface type
        return TypeInfo(type_str, TypeCategory.CLASS, source="annotation")
    
    def _get_node_text(self, node, content_bytes: bytes) -> str:
        """Get the text content of a node."""
        if node is None:
            return ""
        try:
            return content_bytes[node.start_byte:node.end_byte].decode('utf-8')
        except:
            return ""
    
    # Public API Methods
    
    def get_variable_type(self, var_name: str, file_path: str = None, 
                          scope: str = None, line: int = None) -> Optional[TypeInfo]:
        """Get the inferred type for a variable."""
        if scope:
            key = f"{scope}::{var_name}"
            if key in self.variables:
                return self.variables[key].type_info
        
        # Search all scopes
        candidates = []
        for key, var_type in self.variables.items():
            if var_type.name == var_name:
                if file_path and var_type.file_path != file_path:
                    continue
                if line and var_type.line_defined > line:
                    continue
                candidates.append(var_type)
        
        if candidates:
            # Return the most recently defined before the line
            candidates.sort(key=lambda v: v.line_defined, reverse=True)
            return candidates[0].type_info
        
        return None
    
    def get_function_signature(self, func_name: str, file_path: str = None) -> Optional[FunctionSignature]:
        """Get the type signature for a function."""
        # Try exact match first
        if func_name in self.functions:
            return self.functions[func_name]
        
        # Search by short name
        for qual_name, signature in self.functions.items():
            if signature.name == func_name:
                if file_path and signature.file_path != file_path:
                    continue
                return signature
        
        return None
    
    def get_return_type(self, func_name: str, file_path: str = None) -> Optional[TypeInfo]:
        """Get the return type for a function."""
        signature = self.get_function_signature(func_name, file_path)
        if signature:
            return signature.return_type
        return None
    
    def get_class_info(self, class_name: str, file_path: str = None) -> Optional[ClassType]:
        """Get type information for a class."""
        # Try exact match
        if class_name in self.classes:
            return self.classes[class_name]
        
        # Search by short name
        for qual_name, class_info in self.classes.items():
            if class_info.name == class_name:
                if file_path and class_info.file_path != file_path:
                    continue
                return class_info
        
        return None
    
    def _build_result(self) -> Dict:
        """Build the analysis result dictionary."""
        return {
            "variables": {k: {
                "name": v.name,
                "type": v.type_info.to_dict(),
                "scope": v.scope,
                "file_path": v.file_path,
                "line_defined": v.line_defined,
                "is_parameter": v.is_parameter,
                "is_class_attribute": v.is_class_attribute,
                "is_constant": v.is_constant
            } for k, v in self.variables.items()},
            "functions": {k: {
                "name": v.name,
                "qualified_name": v.qualified_name,
                "file_path": v.file_path,
                "parameters": [(p[0], p[1].to_dict()) for p in v.parameters],
                "return_type": v.return_type.to_dict(),
                "is_method": v.is_method,
                "is_static": v.is_static,
                "is_async": v.is_async,
                "decorators": v.decorators
            } for k, v in self.functions.items()},
            "classes": {k: {
                "name": v.name,
                "qualified_name": v.qualified_name,
                "file_path": v.file_path,
                "line_number": v.line_number,
                "base_classes": v.base_classes,
                "attributes": {ak: av.to_dict() for ak, av in v.attributes.items()},
                "class_attributes": {ak: av.to_dict() for ak, av in v.class_attributes.items()},
                "methods": list(v.methods.keys()),
                "is_dataclass": v.is_dataclass,
                "is_abstract": v.is_abstract
            } for k, v in self.classes.items()},
            "statistics": self.stats
        }


def analyze_project_types(project_path: str) -> Dict:
    """Convenience function to analyze a project for types."""
    inferencer = TypeInferencer(project_path)
    return inferencer.analyze_project()
