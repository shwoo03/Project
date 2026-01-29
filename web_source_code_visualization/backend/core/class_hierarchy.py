"""
Class Hierarchy Analysis Module.

This module provides comprehensive class hierarchy analysis for object-oriented code,
enabling accurate method resolution, polymorphism tracking, and inheritance analysis.

Key features:
- Inheritance graph construction (single/multiple inheritance)
- Method overriding detection
- Polymorphic call resolution
- Mixin and interface analysis
- Abstract class/method detection
- Method Resolution Order (MRO) computation
- Diamond inheritance handling

Example:
    analyzer = ClassHierarchyAnalyzer(project_root="/path/to/project")
    analyzer.analyze_project()
    
    # Get inheritance hierarchy
    hierarchy = analyzer.get_class_hierarchy("MyClass")
    
    # Find all implementations of an interface
    impls = analyzer.get_implementations("IRepository")
"""

import os
import re
from typing import List, Dict, Set, Optional, Any, Tuple
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from collections import deque

import tree_sitter_python
import tree_sitter_javascript
from tree_sitter import Language, Parser

# Try importing TypeScript support
try:
    import tree_sitter_typescript
    HAS_TYPESCRIPT = True
except ImportError:
    HAS_TYPESCRIPT = False


class ClassKind(Enum):
    """Kind of class-like construct."""
    CLASS = "class"
    ABSTRACT_CLASS = "abstract_class"
    INTERFACE = "interface"
    MIXIN = "mixin"
    PROTOCOL = "protocol"       # Python Protocol
    ENUM = "enum"
    DATACLASS = "dataclass"


class MethodKind(Enum):
    """Kind of method."""
    INSTANCE = "instance"
    STATIC = "static"
    CLASS_METHOD = "class_method"
    ABSTRACT = "abstract"
    PROPERTY = "property"
    CONSTRUCTOR = "constructor"


@dataclass
class MethodInfo:
    """Information about a method."""
    name: str
    qualified_name: str
    file_path: str
    line_start: int
    line_end: int
    kind: MethodKind
    parameters: List[str] = field(default_factory=list)
    return_type: Optional[str] = None
    decorators: List[str] = field(default_factory=list)
    is_override: bool = False
    overrides: Optional[str] = None  # Qualified name of overridden method
    is_public: bool = True
    docstring: Optional[str] = None
    
    def to_dict(self) -> Dict:
        return {
            "name": self.name,
            "qualified_name": self.qualified_name,
            "file_path": self.file_path,
            "line_start": self.line_start,
            "line_end": self.line_end,
            "kind": self.kind.value,
            "parameters": self.parameters,
            "return_type": self.return_type,
            "decorators": self.decorators,
            "is_override": self.is_override,
            "overrides": self.overrides,
            "is_public": self.is_public
        }


@dataclass
class ClassInfo:
    """Comprehensive information about a class."""
    name: str
    qualified_name: str
    file_path: str
    line_start: int
    line_end: int
    kind: ClassKind
    
    # Inheritance
    direct_bases: List[str] = field(default_factory=list)      # Direct parent classes
    all_bases: List[str] = field(default_factory=list)         # All ancestors (computed)
    direct_children: Set[str] = field(default_factory=set)     # Direct subclasses
    all_children: Set[str] = field(default_factory=set)        # All descendants (computed)
    
    # Interfaces/Protocols implemented
    implements: List[str] = field(default_factory=list)
    
    # Members
    methods: Dict[str, MethodInfo] = field(default_factory=dict)
    attributes: Dict[str, str] = field(default_factory=dict)   # name -> type
    class_attributes: Dict[str, str] = field(default_factory=dict)
    
    # Metadata
    decorators: List[str] = field(default_factory=list)
    is_abstract: bool = False
    mro: List[str] = field(default_factory=list)  # Method Resolution Order
    docstring: Optional[str] = None
    type_parameters: List[str] = field(default_factory=list)  # Generic type params
    
    def to_dict(self) -> Dict:
        return {
            "name": self.name,
            "qualified_name": self.qualified_name,
            "file_path": self.file_path,
            "line_start": self.line_start,
            "line_end": self.line_end,
            "kind": self.kind.value,
            "direct_bases": self.direct_bases,
            "all_bases": self.all_bases,
            "direct_children": list(self.direct_children),
            "all_children": list(self.all_children),
            "implements": self.implements,
            "methods": {k: v.to_dict() for k, v in self.methods.items()},
            "attributes": self.attributes,
            "class_attributes": self.class_attributes,
            "decorators": self.decorators,
            "is_abstract": self.is_abstract,
            "mro": self.mro
        }


@dataclass
class InheritanceEdge:
    """An edge in the inheritance graph."""
    child: str           # Child class qualified name
    parent: str          # Parent class qualified name
    edge_type: str       # "extends", "implements", "mixin"
    file_path: str       # Where the relationship is defined
    line_number: int


@dataclass
class PolymorphicCall:
    """Represents a polymorphic method call."""
    call_site_file: str
    call_site_line: int
    method_name: str
    receiver_type: str              # Static type of receiver
    possible_targets: List[str]     # All possible method implementations


class ClassHierarchyAnalyzer:
    """
    Analyzes class hierarchies and method relationships.
    
    Supports:
    - Python: class inheritance, ABCs, Protocols, mixins
    - JavaScript: class extends, prototype chains
    - TypeScript: class extends, interface implements
    """
    
    # Python special base classes
    PYTHON_ABSTRACT_BASES = {'ABC', 'ABCMeta', 'Protocol'}
    
    # Common base classes to ignore
    IGNORED_BASES = {'object', 'Object', 'type', 'type[Self]', 'Generic'}
    
    def __init__(self, project_root: str):
        self.project_root = os.path.abspath(project_root)
        
        # Class storage
        self.classes: Dict[str, ClassInfo] = {}  # qualified_name -> ClassInfo
        self.inheritance_edges: List[InheritanceEdge] = []
        
        # Indexes for quick lookup
        self.name_to_qualified: Dict[str, List[str]] = {}  # short_name -> [qualified_names]
        self.file_classes: Dict[str, List[str]] = {}  # file_path -> [qualified_names]
        
        # Method override tracking
        self.overrides: Dict[str, List[Tuple[str, str]]] = {}  # method_name -> [(class, overriding_class)]
        
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
            "total_classes": 0,
            "total_interfaces": 0,
            "total_methods": 0,
            "inheritance_edges": 0,
            "method_overrides": 0,
            "abstract_classes": 0,
            "diamond_inheritances": 0
        }
    
    def analyze_project(self) -> Dict:
        """
        Analyze the entire project for class hierarchies.
        
        Returns:
            Dict with classes, inheritance graph, and statistics
        """
        self.classes.clear()
        self.inheritance_edges.clear()
        self.name_to_qualified.clear()
        self.file_classes.clear()
        self.overrides.clear()
        
        for key in self.stats:
            self.stats[key] = 0
        
        # First pass: collect all classes
        for dirpath, dirnames, filenames in os.walk(self.project_root):
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
        
        # Second pass: resolve inheritance and compute derived info
        self._resolve_inheritance()
        self._compute_all_ancestors()
        self._compute_all_descendants()
        self._detect_method_overrides()
        self._compute_mro()
        self._detect_diamond_inheritance()
        
        return self._build_result()
    
    def _analyze_python_file(self, filepath: str):
        """Analyze a Python file for class definitions."""
        try:
            with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
            content_bytes = content.encode('utf-8')
        except Exception:
            return
        
        self.stats["total_files"] += 1
        tree = self.py_parser.parse(content_bytes)
        
        rel_path = os.path.relpath(filepath, self.project_root)
        module_name = rel_path.replace(os.sep, ".").replace(".py", "")
        
        self._extract_python_classes(tree.root_node, filepath, content_bytes, module_name)
    
    def _extract_python_classes(self, node, filepath: str, content_bytes: bytes,
                                  module_name: str, outer_class: str = None):
        """Recursively extract Python class definitions."""
        
        if node.type == 'class_definition':
            class_name_node = node.child_by_field_name('name')
            if not class_name_node:
                return
            
            class_name = self._get_node_text(class_name_node, content_bytes)
            if outer_class:
                qualified = f"{module_name}.{outer_class}.{class_name}"
            else:
                qualified = f"{module_name}.{class_name}"
            
            # Get decorators
            decorators = []
            is_dataclass = False
            is_abstract = False
            
            for child in node.children:
                if child.type == 'decorator':
                    dec_text = self._get_node_text(child, content_bytes)
                    decorators.append(dec_text)
                    if '@dataclass' in dec_text:
                        is_dataclass = True
                    if '@abstractmethod' in dec_text:
                        is_abstract = True
            
            # Get base classes
            bases = []
            implements = []
            args_node = node.child_by_field_name('superclasses')
            if args_node:
                for child in args_node.children:
                    if child.type in ('identifier', 'attribute', 'subscript'):
                        base_text = self._get_node_text(child, content_bytes)
                        # Strip generic parameters
                        if '[' in base_text:
                            base_text = base_text[:base_text.index('[')]
                        
                        if base_text and base_text not in self.IGNORED_BASES:
                            # Check if this is a Protocol (interface-like)
                            if base_text == 'Protocol':
                                is_abstract = True
                            elif base_text in self.PYTHON_ABSTRACT_BASES:
                                is_abstract = True
                            else:
                                bases.append(base_text)
            
            # Determine class kind
            if is_dataclass:
                kind = ClassKind.DATACLASS
            elif is_abstract or any(b in self.PYTHON_ABSTRACT_BASES for b in bases):
                kind = ClassKind.ABSTRACT_CLASS
            else:
                kind = ClassKind.CLASS
            
            # Check if it's a Protocol
            if 'Protocol' in bases or any('@runtime_checkable' in d for d in decorators):
                kind = ClassKind.PROTOCOL
            
            class_info = ClassInfo(
                name=class_name,
                qualified_name=qualified,
                file_path=filepath,
                line_start=node.start_point[0] + 1,
                line_end=node.end_point[0] + 1,
                kind=kind,
                direct_bases=bases,
                implements=implements,
                decorators=decorators,
                is_abstract=is_abstract
            )
            
            # Extract methods and attributes
            body = node.child_by_field_name('body')
            if body:
                for child in body.children:
                    # Handle decorated functions
                    if child.type == 'decorated_definition':
                        # Find the actual function_definition inside
                        for subchild in child.children:
                            if subchild.type == 'function_definition':
                                method = self._extract_python_method(subchild, filepath, content_bytes, qualified)
                                if method:
                                    class_info.methods[method.name] = method
                                    self.stats["total_methods"] += 1
                                break
                    elif child.type == 'function_definition':
                        method = self._extract_python_method(child, filepath, content_bytes, qualified)
                        if method:
                            class_info.methods[method.name] = method
                            self.stats["total_methods"] += 1
                    elif child.type in ('assignment', 'annotated_assignment'):
                        attr_name, attr_type = self._extract_python_attribute(child, content_bytes)
                        if attr_name:
                            class_info.class_attributes[attr_name] = attr_type
                    elif child.type == 'class_definition':
                        # Nested class
                        self._extract_python_classes(child, filepath, content_bytes, 
                                                      module_name, class_name)
            
            # Register class
            self.classes[qualified] = class_info
            self._register_class(qualified, class_name, filepath)
            
            # Create inheritance edges
            for base in bases:
                self.inheritance_edges.append(InheritanceEdge(
                    child=qualified,
                    parent=base,
                    edge_type="extends",
                    file_path=filepath,
                    line_number=node.start_point[0] + 1
                ))
                self.stats["inheritance_edges"] += 1
            
            self.stats["total_classes"] += 1
            if is_abstract:
                self.stats["abstract_classes"] += 1
            
            return
        
        # Continue traversing
        for child in node.children:
            self._extract_python_classes(child, filepath, content_bytes, module_name, outer_class)
    
    def _extract_python_method(self, node, filepath: str, content_bytes: bytes,
                                 class_qualified: str) -> Optional[MethodInfo]:
        """Extract a Python method definition."""
        name_node = node.child_by_field_name('name')
        if not name_node:
            return None
        
        name = self._get_node_text(name_node, content_bytes)
        qualified = f"{class_qualified}.{name}"
        
        # Get decorators
        decorators = []
        kind = MethodKind.INSTANCE
        is_abstract = False
        
        for child in node.children:
            if child.type == 'decorator':
                dec_text = self._get_node_text(child, content_bytes)
                decorators.append(dec_text)
                if '@staticmethod' in dec_text:
                    kind = MethodKind.STATIC
                elif '@classmethod' in dec_text:
                    kind = MethodKind.CLASS_METHOD
                elif '@property' in dec_text:
                    kind = MethodKind.PROPERTY
                elif '@abstractmethod' in dec_text:
                    is_abstract = True
                    kind = MethodKind.ABSTRACT
        
        if name in ('__init__', '__new__'):
            kind = MethodKind.CONSTRUCTOR
        
        # Get parameters
        parameters = []
        params_node = node.child_by_field_name('parameters')
        if params_node:
            for param in params_node.children:
                if param.type in ('identifier', 'typed_parameter', 'default_parameter',
                                   'typed_default_parameter'):
                    param_text = self._get_node_text(param, content_bytes)
                    if param_text and param_text not in ('self', 'cls'):
                        # Extract just the parameter name
                        if ':' in param_text:
                            param_text = param_text.split(':')[0].strip()
                        if '=' in param_text:
                            param_text = param_text.split('=')[0].strip()
                        parameters.append(param_text)
        
        # Get return type
        return_type = None
        return_node = node.child_by_field_name('return_type')
        if return_node:
            return_type = self._get_node_text(return_node, content_bytes)
        
        # Check visibility
        is_public = not name.startswith('_') or name.startswith('__') and name.endswith('__')
        
        return MethodInfo(
            name=name,
            qualified_name=qualified,
            file_path=filepath,
            line_start=node.start_point[0] + 1,
            line_end=node.end_point[0] + 1,
            kind=kind,
            parameters=parameters,
            return_type=return_type,
            decorators=decorators,
            is_public=is_public
        )
    
    def _extract_python_attribute(self, node, content_bytes: bytes) -> Tuple[Optional[str], str]:
        """Extract a Python class attribute."""
        if node.type == 'assignment':
            left = node.child_by_field_name('left') or (node.children[0] if node.children else None)
            if left and left.type == 'identifier':
                name = self._get_node_text(left, content_bytes)
                return name, "Any"
        elif node.type == 'annotated_assignment':
            name_node = node.child_by_field_name('name') or (node.children[0] if node.children else None)
            type_node = node.child_by_field_name('type')
            if name_node:
                name = self._get_node_text(name_node, content_bytes)
                type_str = self._get_node_text(type_node, content_bytes) if type_node else "Any"
                return name, type_str
        return None, "Any"
    
    def _analyze_javascript_file(self, filepath: str):
        """Analyze a JavaScript file for class definitions."""
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
        
        self._extract_js_classes(tree.root_node, filepath, content_bytes, module_name)
    
    def _extract_js_classes(self, node, filepath: str, content_bytes: bytes, module_name: str):
        """Extract JavaScript class definitions."""
        
        if node.type == 'class_declaration':
            class_name_node = node.child_by_field_name('name')
            if not class_name_node:
                return
            
            class_name = self._get_node_text(class_name_node, content_bytes)
            qualified = f"{module_name}/{class_name}"
            
            # Get base class (extends)
            bases = []
            heritage = node.child_by_field_name('heritage') or node.child_by_field_name('superclass')
            if heritage:
                base_text = self._get_node_text(heritage, content_bytes)
                if base_text.startswith('extends '):
                    base_text = base_text[8:].strip()
                if base_text and base_text not in self.IGNORED_BASES:
                    bases.append(base_text)
            
            # Also check children for extends clause
            for child in node.children:
                if child.type == 'class_heritage':
                    text = self._get_node_text(child, content_bytes)
                    if 'extends' in text:
                        parts = text.replace('extends', '').strip().split()
                        if parts:
                            bases.append(parts[0])
            
            class_info = ClassInfo(
                name=class_name,
                qualified_name=qualified,
                file_path=filepath,
                line_start=node.start_point[0] + 1,
                line_end=node.end_point[0] + 1,
                kind=ClassKind.CLASS,
                direct_bases=bases
            )
            
            # Extract methods
            body = node.child_by_field_name('body')
            if body:
                for child in body.children:
                    if child.type == 'method_definition':
                        method = self._extract_js_method(child, filepath, content_bytes, qualified)
                        if method:
                            class_info.methods[method.name] = method
                            self.stats["total_methods"] += 1
                    elif child.type == 'field_definition':
                        # Class field (ES2022)
                        name_node = child.child_by_field_name('property')
                        if name_node:
                            attr_name = self._get_node_text(name_node, content_bytes)
                            class_info.class_attributes[attr_name] = "any"
            
            self.classes[qualified] = class_info
            self._register_class(qualified, class_name, filepath)
            
            for base in bases:
                self.inheritance_edges.append(InheritanceEdge(
                    child=qualified,
                    parent=base,
                    edge_type="extends",
                    file_path=filepath,
                    line_number=node.start_point[0] + 1
                ))
                self.stats["inheritance_edges"] += 1
            
            self.stats["total_classes"] += 1
            return
        
        # Continue traversing
        for child in node.children:
            self._extract_js_classes(child, filepath, content_bytes, module_name)
    
    def _extract_js_method(self, node, filepath: str, content_bytes: bytes,
                            class_qualified: str) -> Optional[MethodInfo]:
        """Extract a JavaScript method definition."""
        name_node = node.child_by_field_name('name')
        if not name_node:
            return None
        
        name = self._get_node_text(name_node, content_bytes)
        qualified = f"{class_qualified}.{name}"
        
        # Determine method kind
        kind = MethodKind.INSTANCE
        full_text = self._get_node_text(node, content_bytes)
        if 'static ' in full_text[:20]:
            kind = MethodKind.STATIC
        if 'get ' in full_text[:10]:
            kind = MethodKind.PROPERTY
        if name == 'constructor':
            kind = MethodKind.CONSTRUCTOR
        
        # Get parameters
        parameters = []
        params_node = node.child_by_field_name('parameters')
        if params_node:
            for param in params_node.children:
                if param.type == 'identifier':
                    parameters.append(self._get_node_text(param, content_bytes))
        
        is_public = not name.startswith('_') and not name.startswith('#')
        
        return MethodInfo(
            name=name,
            qualified_name=qualified,
            file_path=filepath,
            line_start=node.start_point[0] + 1,
            line_end=node.end_point[0] + 1,
            kind=kind,
            parameters=parameters,
            is_public=is_public
        )
    
    def _analyze_typescript_file(self, filepath: str):
        """Analyze a TypeScript file for class and interface definitions."""
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
        
        self._extract_ts_classes(tree.root_node, filepath, content_bytes, module_name)
    
    def _extract_ts_classes(self, node, filepath: str, content_bytes: bytes, module_name: str):
        """Extract TypeScript class and interface definitions."""
        
        if node.type == 'class_declaration':
            self._extract_ts_class(node, filepath, content_bytes, module_name)
            return
        
        if node.type == 'interface_declaration':
            self._extract_ts_interface(node, filepath, content_bytes, module_name)
            return
        
        if node.type == 'enum_declaration':
            self._extract_ts_enum(node, filepath, content_bytes, module_name)
            return
        
        # Continue traversing
        for child in node.children:
            self._extract_ts_classes(child, filepath, content_bytes, module_name)
    
    def _extract_ts_class(self, node, filepath: str, content_bytes: bytes, module_name: str):
        """Extract a TypeScript class definition."""
        class_name_node = node.child_by_field_name('name')
        if not class_name_node:
            return
        
        class_name = self._get_node_text(class_name_node, content_bytes)
        qualified = f"{module_name}/{class_name}"
        
        # Get extends/implements
        bases = []
        implements = []
        is_abstract = False
        
        full_text = self._get_node_text(node, content_bytes)
        if 'abstract class' in full_text[:50]:
            is_abstract = True
        
        for child in node.children:
            if child.type == 'class_heritage':
                text = self._get_node_text(child, content_bytes)
                if 'extends' in text:
                    # Parse extends clause
                    parts = text.split('implements')[0]
                    parts = parts.replace('extends', '').strip()
                    if parts:
                        # Handle generics
                        if '<' in parts:
                            parts = parts[:parts.index('<')]
                        bases.append(parts.split()[0] if parts.split() else parts)
                if 'implements' in text:
                    # Parse implements clause
                    impl_part = text.split('implements')[1] if 'implements' in text else ""
                    if impl_part:
                        for impl in impl_part.split(','):
                            impl = impl.strip()
                            if '<' in impl:
                                impl = impl[:impl.index('<')]
                            if impl:
                                implements.append(impl)
        
        kind = ClassKind.ABSTRACT_CLASS if is_abstract else ClassKind.CLASS
        
        class_info = ClassInfo(
            name=class_name,
            qualified_name=qualified,
            file_path=filepath,
            line_start=node.start_point[0] + 1,
            line_end=node.end_point[0] + 1,
            kind=kind,
            direct_bases=bases,
            implements=implements,
            is_abstract=is_abstract
        )
        
        # Extract methods
        body = node.child_by_field_name('body')
        if body:
            for child in body.children:
                if child.type in ('method_definition', 'public_field_definition'):
                    method = self._extract_ts_method(child, filepath, content_bytes, qualified)
                    if method:
                        class_info.methods[method.name] = method
                        self.stats["total_methods"] += 1
                elif child.type == 'property_signature':
                    name_node = child.child_by_field_name('name')
                    if name_node:
                        attr_name = self._get_node_text(name_node, content_bytes)
                        type_node = child.child_by_field_name('type')
                        attr_type = self._get_node_text(type_node, content_bytes) if type_node else "any"
                        class_info.attributes[attr_name] = attr_type
        
        self.classes[qualified] = class_info
        self._register_class(qualified, class_name, filepath)
        
        # Create inheritance edges
        for base in bases:
            self.inheritance_edges.append(InheritanceEdge(
                child=qualified,
                parent=base,
                edge_type="extends",
                file_path=filepath,
                line_number=node.start_point[0] + 1
            ))
            self.stats["inheritance_edges"] += 1
        
        for impl in implements:
            self.inheritance_edges.append(InheritanceEdge(
                child=qualified,
                parent=impl,
                edge_type="implements",
                file_path=filepath,
                line_number=node.start_point[0] + 1
            ))
            self.stats["inheritance_edges"] += 1
        
        self.stats["total_classes"] += 1
        if is_abstract:
            self.stats["abstract_classes"] += 1
    
    def _extract_ts_interface(self, node, filepath: str, content_bytes: bytes, module_name: str):
        """Extract a TypeScript interface definition."""
        name_node = node.child_by_field_name('name')
        if not name_node:
            return
        
        name = self._get_node_text(name_node, content_bytes)
        qualified = f"{module_name}/{name}"
        
        # Get extends
        bases = []
        for child in node.children:
            if child.type == 'extends_type_clause':
                text = self._get_node_text(child, content_bytes)
                for base in text.replace('extends', '').split(','):
                    base = base.strip()
                    if '<' in base:
                        base = base[:base.index('<')]
                    if base:
                        bases.append(base)
        
        class_info = ClassInfo(
            name=name,
            qualified_name=qualified,
            file_path=filepath,
            line_start=node.start_point[0] + 1,
            line_end=node.end_point[0] + 1,
            kind=ClassKind.INTERFACE,
            direct_bases=bases,
            is_abstract=True
        )
        
        # Extract method signatures
        body = node.child_by_field_name('body')
        if body:
            for child in body.children:
                if child.type in ('method_signature', 'property_signature'):
                    name_node = child.child_by_field_name('name')
                    if name_node:
                        method_name = self._get_node_text(name_node, content_bytes)
                        if child.type == 'method_signature':
                            method = MethodInfo(
                                name=method_name,
                                qualified_name=f"{qualified}.{method_name}",
                                file_path=filepath,
                                line_start=child.start_point[0] + 1,
                                line_end=child.end_point[0] + 1,
                                kind=MethodKind.ABSTRACT
                            )
                            class_info.methods[method_name] = method
                        else:
                            type_node = child.child_by_field_name('type')
                            attr_type = self._get_node_text(type_node, content_bytes) if type_node else "any"
                            class_info.attributes[method_name] = attr_type
        
        self.classes[qualified] = class_info
        self._register_class(qualified, name, filepath)
        
        for base in bases:
            self.inheritance_edges.append(InheritanceEdge(
                child=qualified,
                parent=base,
                edge_type="extends",
                file_path=filepath,
                line_number=node.start_point[0] + 1
            ))
            self.stats["inheritance_edges"] += 1
        
        self.stats["total_interfaces"] += 1
    
    def _extract_ts_enum(self, node, filepath: str, content_bytes: bytes, module_name: str):
        """Extract a TypeScript enum definition."""
        name_node = node.child_by_field_name('name')
        if not name_node:
            return
        
        name = self._get_node_text(name_node, content_bytes)
        qualified = f"{module_name}/{name}"
        
        class_info = ClassInfo(
            name=name,
            qualified_name=qualified,
            file_path=filepath,
            line_start=node.start_point[0] + 1,
            line_end=node.end_point[0] + 1,
            kind=ClassKind.ENUM
        )
        
        self.classes[qualified] = class_info
        self._register_class(qualified, name, filepath)
        self.stats["total_classes"] += 1
    
    def _extract_ts_method(self, node, filepath: str, content_bytes: bytes,
                            class_qualified: str) -> Optional[MethodInfo]:
        """Extract a TypeScript method definition."""
        name_node = node.child_by_field_name('name')
        if not name_node:
            return None
        
        name = self._get_node_text(name_node, content_bytes)
        qualified = f"{class_qualified}.{name}"
        
        # Determine method kind
        kind = MethodKind.INSTANCE
        full_text = self._get_node_text(node, content_bytes)
        if 'static ' in full_text[:20]:
            kind = MethodKind.STATIC
        if 'abstract ' in full_text[:20]:
            kind = MethodKind.ABSTRACT
        if name == 'constructor':
            kind = MethodKind.CONSTRUCTOR
        
        # Get parameters with types
        parameters = []
        params_node = node.child_by_field_name('parameters')
        if params_node:
            for param in params_node.children:
                if param.type in ('required_parameter', 'optional_parameter', 'identifier'):
                    param_text = self._get_node_text(param, content_bytes)
                    if ':' in param_text:
                        param_text = param_text.split(':')[0].strip()
                    if param_text:
                        parameters.append(param_text)
        
        # Get return type
        return_type = None
        return_node = node.child_by_field_name('return_type')
        if return_node:
            return_type = self._get_node_text(return_node, content_bytes)
        
        # Check visibility
        is_public = 'private' not in full_text[:20] and 'protected' not in full_text[:20]
        
        return MethodInfo(
            name=name,
            qualified_name=qualified,
            file_path=filepath,
            line_start=node.start_point[0] + 1,
            line_end=node.end_point[0] + 1,
            kind=kind,
            parameters=parameters,
            return_type=return_type,
            is_public=is_public
        )
    
    def _register_class(self, qualified: str, short_name: str, filepath: str):
        """Register class in indexes."""
        if short_name not in self.name_to_qualified:
            self.name_to_qualified[short_name] = []
        self.name_to_qualified[short_name].append(qualified)
        
        if filepath not in self.file_classes:
            self.file_classes[filepath] = []
        self.file_classes[filepath].append(qualified)
    
    def _resolve_inheritance(self):
        """Resolve base class names to qualified names."""
        for edge in self.inheritance_edges:
            # Try to resolve parent to qualified name
            parent_name = edge.parent
            
            # Check if already qualified
            if parent_name in self.classes:
                continue
            
            # Try to find by short name
            if parent_name in self.name_to_qualified:
                candidates = self.name_to_qualified[parent_name]
                if len(candidates) == 1:
                    edge.parent = candidates[0]
                else:
                    # Multiple candidates - try to find one in the same module
                    child_module = edge.child.rsplit('.', 1)[0] if '.' in edge.child else edge.child.rsplit('/', 1)[0]
                    for cand in candidates:
                        cand_module = cand.rsplit('.', 1)[0] if '.' in cand else cand.rsplit('/', 1)[0]
                        if cand_module == child_module:
                            edge.parent = cand
                            break
        
        # Build child->parent links in classes
        for edge in self.inheritance_edges:
            child_class = self.classes.get(edge.child)
            parent_class = self.classes.get(edge.parent)
            
            if parent_class and child_class:
                parent_class.direct_children.add(edge.child)
    
    def _compute_all_ancestors(self):
        """Compute all ancestors for each class."""
        for class_info in self.classes.values():
            visited = set()
            ancestors = []
            
            def collect_ancestors(class_name: str):
                if class_name in visited:
                    return
                visited.add(class_name)
                
                cls = self.classes.get(class_name)
                if cls:
                    for base in cls.direct_bases:
                        # Try to resolve base name
                        resolved = self._resolve_class_name(base)
                        if resolved and resolved not in ancestors:
                            ancestors.append(resolved)
                            collect_ancestors(resolved)
            
            for base in class_info.direct_bases:
                resolved = self._resolve_class_name(base)
                if resolved:
                    ancestors.append(resolved)
                    collect_ancestors(resolved)
            
            class_info.all_bases = ancestors
    
    def _compute_all_descendants(self):
        """Compute all descendants for each class."""
        for class_info in self.classes.values():
            visited = set()
            descendants = set()
            
            def collect_descendants(class_name: str):
                if class_name in visited:
                    return
                visited.add(class_name)
                
                cls = self.classes.get(class_name)
                if cls:
                    for child in cls.direct_children:
                        descendants.add(child)
                        collect_descendants(child)
            
            collect_descendants(class_info.qualified_name)
            class_info.all_children = descendants
    
    def _detect_method_overrides(self):
        """Detect which methods override parent methods."""
        for class_info in self.classes.values():
            for method_name, method in class_info.methods.items():
                # Skip constructors
                if method.kind == MethodKind.CONSTRUCTOR:
                    continue
                
                # Check if any ancestor has this method
                for ancestor_name in class_info.all_bases:
                    ancestor = self.classes.get(ancestor_name)
                    if ancestor and method_name in ancestor.methods:
                        method.is_override = True
                        method.overrides = f"{ancestor_name}.{method_name}"
                        self.stats["method_overrides"] += 1
                        
                        # Track override
                        if method_name not in self.overrides:
                            self.overrides[method_name] = []
                        self.overrides[method_name].append(
                            (ancestor_name, class_info.qualified_name)
                        )
                        break
    
    def _compute_mro(self):
        """Compute Method Resolution Order for each class (Python C3 linearization)."""
        for class_info in self.classes.values():
            mro = self._c3_linearization(class_info.qualified_name)
            class_info.mro = mro
    
    def _c3_linearization(self, class_name: str) -> List[str]:
        """Compute C3 linearization (Python MRO algorithm)."""
        cls = self.classes.get(class_name)
        if not cls:
            return [class_name]
        
        if not cls.direct_bases:
            return [class_name]
        
        # Get parent MROs
        parent_mros = []
        for base in cls.direct_bases:
            resolved = self._resolve_class_name(base)
            if resolved:
                parent_mros.append(self._c3_linearization(resolved))
        
        if not parent_mros:
            return [class_name]
        
        # Add list of direct parents
        parent_mros.append([self._resolve_class_name(b) for b in cls.direct_bases if self._resolve_class_name(b)])
        
        # Merge
        result = [class_name]
        while parent_mros:
            # Find good head
            head = None
            for mro in parent_mros:
                if not mro:
                    continue
                candidate = mro[0]
                # Check if candidate appears in tail of any other MRO
                in_tail = False
                for other_mro in parent_mros:
                    if candidate in other_mro[1:]:
                        in_tail = True
                        break
                if not in_tail:
                    head = candidate
                    break
            
            if head is None:
                # No good head found - just take first available
                for mro in parent_mros:
                    if mro:
                        head = mro[0]
                        break
                if head is None:
                    break
            
            result.append(head)
            
            # Remove head from all MROs
            parent_mros = [[c for c in mro if c != head] for mro in parent_mros]
            parent_mros = [mro for mro in parent_mros if mro]
        
        return result
    
    def _detect_diamond_inheritance(self):
        """Detect diamond inheritance patterns."""
        for class_info in self.classes.values():
            if len(class_info.direct_bases) < 2:
                continue
            
            # Check if any two bases share a common ancestor
            ancestor_sets = []
            for base in class_info.direct_bases:
                resolved = self._resolve_class_name(base)
                if resolved and resolved in self.classes:
                    ancestors = set(self.classes[resolved].all_bases)
                    ancestors.add(resolved)
                    ancestor_sets.append(ancestors)
            
            if len(ancestor_sets) < 2:
                continue
            
            # Check for intersection
            for i, set1 in enumerate(ancestor_sets):
                for j, set2 in enumerate(ancestor_sets[i+1:], i+1):
                    common = set1 & set2
                    if common - self.IGNORED_BASES:
                        self.stats["diamond_inheritances"] += 1
                        break
    
    def _resolve_class_name(self, name: str) -> Optional[str]:
        """Resolve a class short name to qualified name."""
        if name in self.classes:
            return name
        
        if name in self.name_to_qualified:
            candidates = self.name_to_qualified[name]
            if candidates:
                return candidates[0]
        
        return None
    
    def _get_node_text(self, node, content_bytes: bytes) -> str:
        """Get the text content of a node."""
        if node is None:
            return ""
        try:
            return content_bytes[node.start_byte:node.end_byte].decode('utf-8')
        except:
            return ""
    
    # Public API Methods
    
    def get_class_hierarchy(self, class_name: str) -> Optional[Dict]:
        """Get the full hierarchy for a class."""
        resolved = self._resolve_class_name(class_name)
        if not resolved:
            return None
        
        cls = self.classes.get(resolved)
        if not cls:
            return None
        
        return {
            "class": cls.to_dict(),
            "ancestors": [self.classes[a].to_dict() for a in cls.all_bases if a in self.classes],
            "descendants": [self.classes[d].to_dict() for d in cls.all_children if d in self.classes]
        }
    
    def get_implementations(self, interface_name: str) -> List[Dict]:
        """Get all classes that implement an interface/protocol."""
        resolved = self._resolve_class_name(interface_name)
        implementations = []
        
        for class_info in self.classes.values():
            if class_info.kind in (ClassKind.INTERFACE, ClassKind.PROTOCOL):
                continue
            
            # Check direct implementation
            if interface_name in class_info.implements or resolved in class_info.implements:
                implementations.append(class_info.to_dict())
                continue
            
            # Check if it extends something that implements
            if resolved in class_info.all_bases:
                implementations.append(class_info.to_dict())
        
        return implementations
    
    def get_method_implementations(self, method_name: str) -> List[Dict]:
        """Get all implementations of a method across the hierarchy."""
        implementations = []
        
        for class_info in self.classes.values():
            if method_name in class_info.methods:
                method = class_info.methods[method_name]
                implementations.append({
                    "class": class_info.qualified_name,
                    "method": method.to_dict(),
                    "is_override": method.is_override,
                    "overrides": method.overrides
                })
        
        return implementations
    
    def resolve_polymorphic_call(self, receiver_type: str, method_name: str) -> List[str]:
        """
        Resolve possible targets for a polymorphic method call.
        
        Returns list of qualified method names that could be called.
        """
        resolved = self._resolve_class_name(receiver_type)
        if not resolved:
            return []
        
        cls = self.classes.get(resolved)
        if not cls:
            return []
        
        targets = []
        
        # Check the class itself
        if method_name in cls.methods:
            targets.append(f"{resolved}.{method_name}")
        
        # Check all descendants (for polymorphic dispatch)
        for descendant_name in cls.all_children:
            descendant = self.classes.get(descendant_name)
            if descendant and method_name in descendant.methods:
                targets.append(f"{descendant_name}.{method_name}")
        
        return targets
    
    def get_inheritance_graph(self) -> Dict:
        """Get the full inheritance graph for visualization."""
        nodes = []
        edges = []
        
        for class_info in self.classes.values():
            nodes.append({
                "id": class_info.qualified_name,
                "label": class_info.name,
                "kind": class_info.kind.value,
                "file_path": class_info.file_path,
                "line": class_info.line_start,
                "is_abstract": class_info.is_abstract,
                "method_count": len(class_info.methods)
            })
        
        for edge in self.inheritance_edges:
            edges.append({
                "source": edge.child,
                "target": edge.parent,
                "type": edge.edge_type
            })
        
        return {
            "nodes": nodes,
            "edges": edges,
            "statistics": self.stats
        }
    
    def _build_result(self) -> Dict:
        """Build the analysis result dictionary."""
        return {
            "classes": {k: v.to_dict() for k, v in self.classes.items()},
            "inheritance_graph": self.get_inheritance_graph(),
            "method_overrides": self.overrides,
            "statistics": self.stats
        }


def analyze_class_hierarchy(project_path: str) -> Dict:
    """Convenience function to analyze a project's class hierarchy."""
    analyzer = ClassHierarchyAnalyzer(project_path)
    return analyzer.analyze_project()
