"""
Enhanced Import Resolution Module.

This module provides comprehensive import resolution for Python, JavaScript/TypeScript,
and other languages, enabling accurate cross-file symbol tracking.

Key features:
- Module dependency graph construction
- Relative and absolute import resolution
- Alias handling (from x import y as z)
- Dynamic import detection (__import__, importlib, require())
- Package __init__.py processing
- Circular import detection
- JavaScript/TypeScript module resolution (ES6, CommonJS)

Example:
    resolver = ImportResolver(project_root="/path/to/project")
    resolver.scan_project()
    
    # Resolve an import
    module = resolver.resolve_import("from utils.helpers import format_date", "app.py")
    
    # Get dependency graph
    graph = resolver.get_dependency_graph()
"""

import os
import re
import ast
from typing import List, Dict, Set, Optional, Any, Tuple
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


class ImportType(Enum):
    """Type of import statement."""
    ABSOLUTE = "absolute"          # import foo.bar
    RELATIVE = "relative"          # from . import foo
    ALIAS = "alias"                # import foo as bar
    STAR = "star"                  # from foo import *
    DYNAMIC = "dynamic"            # __import__, importlib.import_module
    ES6_IMPORT = "es6_import"      # import { foo } from 'bar'
    ES6_DEFAULT = "es6_default"    # import foo from 'bar'
    COMMONJS = "commonjs"          # const foo = require('bar')
    SIDE_EFFECT = "side_effect"    # import 'bar'  (no binding)


@dataclass
class ImportInfo:
    """Represents a single import statement."""
    module_path: str                 # The imported module path (e.g., "utils.helpers")
    imported_names: List[str]        # Names imported (e.g., ["format_date", "parse_date"])
    aliases: Dict[str, str]          # Alias mappings (e.g., {"fd": "format_date"})
    import_type: ImportType          # Type of import
    line_number: int                 # Line number in source file
    source_file: str                 # File containing the import
    is_resolved: bool = False        # Whether resolution succeeded
    resolved_path: Optional[str] = None  # Absolute path to resolved module
    is_external: bool = False        # Is this an external package (not in project)?
    is_dynamic: bool = False         # Is this a dynamic import?


@dataclass
class ModuleInfo:
    """Information about a module/file in the project."""
    file_path: str                   # Absolute file path
    module_name: str                 # Dot-separated module name (e.g., "utils.helpers")
    package_name: Optional[str]      # Package name if in a package
    imports: List[ImportInfo] = field(default_factory=list)
    exports: List[str] = field(default_factory=list)  # Exported names
    is_package: bool = False         # Is this an __init__.py?
    is_entry_point: bool = False     # Is this a main entry point?
    dependencies: Set[str] = field(default_factory=set)  # Module names this depends on
    dependents: Set[str] = field(default_factory=set)    # Modules that depend on this


@dataclass 
class DependencyEdge:
    """An edge in the dependency graph."""
    source: str           # Source module
    target: str           # Target module (dependency)
    import_type: ImportType
    imported_names: List[str]
    line_number: int


class ImportResolver:
    """
    Resolves imports and builds a module dependency graph.
    
    Supports:
    - Python: import, from...import, relative imports, __import__, importlib
    - JavaScript: ES6 import/export, CommonJS require/module.exports
    - TypeScript: Same as JavaScript plus type imports
    """
    
    # Standard library modules (subset - for quick external detection)
    PYTHON_STDLIB = {
        "abc", "asyncio", "collections", "contextlib", "copy", "dataclasses",
        "datetime", "enum", "functools", "hashlib", "html", "http", "io",
        "itertools", "json", "logging", "math", "os", "pathlib", "pickle",
        "queue", "random", "re", "shutil", "socket", "sqlite3", "ssl",
        "string", "struct", "subprocess", "sys", "tempfile", "threading",
        "time", "typing", "unittest", "urllib", "uuid", "warnings", "xml", "zipfile"
    }
    
    # Common external packages
    COMMON_EXTERNAL = {
        "flask", "fastapi", "django", "requests", "numpy", "pandas", "sqlalchemy",
        "pydantic", "pytest", "celery", "redis", "boto3", "aiohttp", "httpx",
        "express", "react", "vue", "angular", "lodash", "axios", "moment"
    }
    
    def __init__(self, project_root: str):
        self.project_root = os.path.abspath(project_root)
        self.modules: Dict[str, ModuleInfo] = {}  # module_name -> ModuleInfo
        self.file_to_module: Dict[str, str] = {}  # file_path -> module_name
        self.dependency_edges: List[DependencyEdge] = []
        self.unresolved_imports: List[ImportInfo] = []
        
        # Package structure cache
        self.packages: Dict[str, str] = {}  # package_name -> __init__.py path
        
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
            "total_imports": 0,
            "resolved_imports": 0,
            "unresolved_imports": 0,
            "external_imports": 0,
            "dynamic_imports": 0,
            "circular_dependencies": 0,
        }
    
    def scan_project(self) -> Dict[str, Any]:
        """
        Scan the entire project and build the dependency graph.
        
        Returns:
            Dict with modules, edges, and statistics
        """
        # Step 1: Discover all modules and packages
        self._discover_modules()
        
        # Step 2: Parse imports from each file
        self._parse_all_imports()
        
        # Step 3: Resolve imports to actual modules
        self._resolve_all_imports()
        
        # Step 4: Build dependency graph
        self._build_dependency_graph()
        
        # Step 5: Detect circular dependencies
        circular = self._detect_circular_dependencies()
        self.stats["circular_dependencies"] = len(circular)
        
        return {
            "modules": {k: self._module_to_dict(v) for k, v in self.modules.items()},
            "edges": [self._edge_to_dict(e) for e in self.dependency_edges],
            "circular_dependencies": circular,
            "statistics": self.stats
        }
    
    def _discover_modules(self):
        """Discover all Python/JS/TS modules in the project."""
        for dirpath, dirnames, filenames in os.walk(self.project_root):
            # Skip common non-source directories
            dirnames[:] = [d for d in dirnames if d not in {
                '__pycache__', 'node_modules', '.git', '.venv', 'venv',
                'dist', 'build', '.next', 'coverage', '.tox', 'egg-info'
            }]
            
            # Check for __init__.py (Python package)
            if '__init__.py' in filenames:
                rel_path = os.path.relpath(dirpath, self.project_root)
                package_name = rel_path.replace(os.sep, '.')
                if package_name == '.':
                    package_name = os.path.basename(self.project_root)
                init_path = os.path.join(dirpath, '__init__.py')
                self.packages[package_name] = init_path
            
            for filename in filenames:
                filepath = os.path.join(dirpath, filename)
                module_name = self._file_to_module_name(filepath)
                
                if module_name:
                    is_package = filename == '__init__.py'
                    
                    self.modules[module_name] = ModuleInfo(
                        file_path=filepath,
                        module_name=module_name,
                        package_name=self._get_package_name(filepath),
                        is_package=is_package,
                        is_entry_point=self._is_entry_point(filepath, filename)
                    )
                    self.file_to_module[filepath] = module_name
                    self.stats["total_files"] += 1
    
    def _file_to_module_name(self, filepath: str) -> Optional[str]:
        """Convert a file path to a module name."""
        rel_path = os.path.relpath(filepath, self.project_root)
        
        # Python files
        if filepath.endswith('.py'):
            module = rel_path[:-3].replace(os.sep, '.')
            if module.endswith('.__init__'):
                module = module[:-9]  # Remove .__init__
            return module
        
        # JavaScript/TypeScript files
        if filepath.endswith(('.js', '.jsx', '.ts', '.tsx', '.mjs')):
            # Remove extension
            for ext in ['.tsx', '.jsx', '.ts', '.js', '.mjs']:
                if rel_path.endswith(ext):
                    module = rel_path[:-len(ext)].replace(os.sep, '/')
                    return module
        
        return None
    
    def _get_package_name(self, filepath: str) -> Optional[str]:
        """Get the package name for a file."""
        dirpath = os.path.dirname(filepath)
        
        while dirpath and dirpath.startswith(self.project_root):
            if os.path.exists(os.path.join(dirpath, '__init__.py')):
                rel_path = os.path.relpath(dirpath, self.project_root)
                return rel_path.replace(os.sep, '.')
            dirpath = os.path.dirname(dirpath)
        
        return None
    
    def _is_entry_point(self, filepath: str, filename: str) -> bool:
        """Check if a file is an entry point."""
        # Common entry point patterns
        entry_patterns = ['main.py', 'app.py', 'wsgi.py', 'asgi.py', 'manage.py',
                         'index.js', 'index.ts', 'server.js', 'server.ts',
                         'main.js', 'main.ts', 'app.js', 'app.ts']
        
        if filename in entry_patterns:
            return True
        
        # Check for if __name__ == "__main__"
        if filepath.endswith('.py'):
            try:
                with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()
                    if '__name__' in content and '__main__' in content:
                        return True
            except Exception:
                pass
        
        return False
    
    def _parse_all_imports(self):
        """Parse imports from all discovered modules."""
        for module_name, module_info in self.modules.items():
            imports = self._parse_file_imports(module_info.file_path)
            module_info.imports = imports
            self.stats["total_imports"] += len(imports)
    
    def _parse_file_imports(self, filepath: str) -> List[ImportInfo]:
        """Parse all imports from a single file."""
        imports = []
        
        try:
            with open(filepath, 'rb') as f:
                content = f.read()
        except Exception:
            return imports
        
        if filepath.endswith('.py'):
            imports = self._parse_python_imports(content, filepath)
        elif filepath.endswith(('.js', '.jsx', '.mjs')):
            imports = self._parse_javascript_imports(content, filepath)
        elif filepath.endswith(('.ts', '.tsx')) and self.ts_parser:
            imports = self._parse_typescript_imports(content, filepath)
        
        return imports
    
    def _parse_python_imports(self, content: bytes, filepath: str) -> List[ImportInfo]:
        """Parse Python import statements using tree-sitter."""
        imports = []
        tree = self.py_parser.parse(content)
        
        def traverse(node):
            if node.type == 'import_statement':
                # import foo, bar
                for child in node.children:
                    if child.type == 'dotted_name':
                        module_path = self._get_node_text(child, content)
                        imports.append(ImportInfo(
                            module_path=module_path,
                            imported_names=[module_path.split('.')[-1]],
                            aliases={},
                            import_type=ImportType.ABSOLUTE,
                            line_number=node.start_point[0] + 1,
                            source_file=filepath
                        ))
                    elif child.type == 'aliased_import':
                        name_node = child.child_by_field_name('name')
                        alias_node = child.child_by_field_name('alias')
                        if name_node:
                            module_path = self._get_node_text(name_node, content)
                            alias = self._get_node_text(alias_node, content) if alias_node else None
                            imports.append(ImportInfo(
                                module_path=module_path,
                                imported_names=[module_path.split('.')[-1]],
                                aliases={alias: module_path} if alias else {},
                                import_type=ImportType.ALIAS if alias else ImportType.ABSOLUTE,
                                line_number=node.start_point[0] + 1,
                                source_file=filepath
                            ))
            
            elif node.type == 'import_from_statement':
                # from foo import bar, baz
                module_node = node.child_by_field_name('module_name')
                module_path = self._get_node_text(module_node, content) if module_node else ""
                
                # Check for relative imports
                relative_level = 0
                for child in node.children:
                    if child.type == 'relative_import':
                        # Count dots for relative level
                        rel_text = self._get_node_text(child, content)
                        relative_level = rel_text.count('.')
                        # Get module after dots
                        dot_child = child.child_by_field_name('module')
                        if dot_child:
                            module_path = self._get_node_text(dot_child, content)
                
                import_type = ImportType.RELATIVE if relative_level > 0 else ImportType.ABSOLUTE
                
                # Get imported names
                imported_names = []
                aliases = {}
                is_star = False
                
                for child in node.children:
                    if child.type == 'wildcard_import':
                        is_star = True
                        import_type = ImportType.STAR
                    elif child.type == 'dotted_name' and child != module_node:
                        imported_names.append(self._get_node_text(child, content))
                    elif child.type == 'aliased_import':
                        name_node = child.child_by_field_name('name')
                        alias_node = child.child_by_field_name('alias')
                        if name_node:
                            name = self._get_node_text(name_node, content)
                            imported_names.append(name)
                            if alias_node:
                                alias = self._get_node_text(alias_node, content)
                                aliases[alias] = name
                                import_type = ImportType.ALIAS
                
                # Handle the prefix dots for module_path in relative imports
                if relative_level > 0:
                    module_path = ('.' * relative_level) + (module_path if module_path else '')
                
                imports.append(ImportInfo(
                    module_path=module_path,
                    imported_names=['*'] if is_star else imported_names,
                    aliases=aliases,
                    import_type=import_type,
                    line_number=node.start_point[0] + 1,
                    source_file=filepath
                ))
            
            # Detect dynamic imports
            elif node.type == 'call':
                func = node.child_by_field_name('function')
                if func:
                    func_text = self._get_node_text(func, content)
                    if func_text in ('__import__', 'importlib.import_module', 'import_module'):
                        args = node.child_by_field_name('arguments')
                        if args:
                            for arg in args.children:
                                if arg.type == 'string':
                                    mod_name = self._get_node_text(arg, content).strip('"\'')
                                    imports.append(ImportInfo(
                                        module_path=mod_name,
                                        imported_names=[],
                                        aliases={},
                                        import_type=ImportType.DYNAMIC,
                                        line_number=node.start_point[0] + 1,
                                        source_file=filepath,
                                        is_dynamic=True
                                    ))
                                    self.stats["dynamic_imports"] += 1
                                    break
            
            for child in node.children:
                traverse(child)
        
        traverse(tree.root_node)
        return imports
    
    def _parse_javascript_imports(self, content: bytes, filepath: str) -> List[ImportInfo]:
        """Parse JavaScript import/require statements."""
        imports = []
        tree = self.js_parser.parse(content)
        
        def traverse(node):
            # ES6 imports
            if node.type == 'import_statement':
                source_node = node.child_by_field_name('source')
                module_path = ""
                if source_node:
                    module_path = self._get_node_text(source_node, content).strip('"\'')
                
                imported_names = []
                aliases = {}
                import_type = ImportType.SIDE_EFFECT  # Default for bare imports
                
                for child in node.children:
                    if child.type == 'import_clause':
                        for imp_child in child.children:
                            if imp_child.type == 'identifier':
                                # Default import
                                imported_names.append(self._get_node_text(imp_child, content))
                                import_type = ImportType.ES6_DEFAULT
                            elif imp_child.type == 'named_imports':
                                # Named imports { a, b as c }
                                import_type = ImportType.ES6_IMPORT
                                for spec in imp_child.children:
                                    if spec.type == 'import_specifier':
                                        name_node = spec.child_by_field_name('name')
                                        alias_node = spec.child_by_field_name('alias')
                                        if name_node:
                                            name = self._get_node_text(name_node, content)
                                            imported_names.append(name)
                                            if alias_node:
                                                alias = self._get_node_text(alias_node, content)
                                                aliases[alias] = name
                            elif imp_child.type == 'namespace_import':
                                # import * as foo
                                import_type = ImportType.STAR
                                alias_node = imp_child.child_by_field_name('alias')
                                if alias_node:
                                    alias = self._get_node_text(alias_node, content)
                                    aliases[alias] = '*'
                                imported_names.append('*')
                
                if module_path:
                    imports.append(ImportInfo(
                        module_path=module_path,
                        imported_names=imported_names,
                        aliases=aliases,
                        import_type=import_type,
                        line_number=node.start_point[0] + 1,
                        source_file=filepath
                    ))
            
            # CommonJS require
            elif node.type == 'call_expression':
                func = node.child_by_field_name('function')
                if func and self._get_node_text(func, content) == 'require':
                    args = node.child_by_field_name('arguments')
                    if args:
                        for arg in args.children:
                            if arg.type == 'string':
                                module_path = self._get_node_text(arg, content).strip('"\'')
                                
                                # Try to find the variable it's assigned to
                                imported_name = None
                                parent = node.parent
                                if parent and parent.type == 'variable_declarator':
                                    name_node = parent.child_by_field_name('name')
                                    if name_node:
                                        imported_name = self._get_node_text(name_node, content)
                                
                                imports.append(ImportInfo(
                                    module_path=module_path,
                                    imported_names=[imported_name] if imported_name else [],
                                    aliases={},
                                    import_type=ImportType.COMMONJS,
                                    line_number=node.start_point[0] + 1,
                                    source_file=filepath
                                ))
                                break
            
            # Dynamic imports: import('module')
            elif node.type == 'call_expression':
                func = node.child_by_field_name('function')
                if func and func.type == 'import':
                    args = node.child_by_field_name('arguments')
                    if args:
                        for arg in args.children:
                            if arg.type == 'string':
                                module_path = self._get_node_text(arg, content).strip('"\'')
                                imports.append(ImportInfo(
                                    module_path=module_path,
                                    imported_names=[],
                                    aliases={},
                                    import_type=ImportType.DYNAMIC,
                                    line_number=node.start_point[0] + 1,
                                    source_file=filepath,
                                    is_dynamic=True
                                ))
                                self.stats["dynamic_imports"] += 1
                                break
            
            for child in node.children:
                traverse(child)
        
        traverse(tree.root_node)
        return imports
    
    def _parse_typescript_imports(self, content: bytes, filepath: str) -> List[ImportInfo]:
        """Parse TypeScript imports (same as JS + type imports)."""
        # TypeScript imports are largely the same as JavaScript
        # Use the appropriate parser
        parser = self.tsx_parser if filepath.endswith('.tsx') else self.ts_parser
        if not parser:
            return self._parse_javascript_imports(content, filepath)
        
        # For now, use the JavaScript parser which handles most TS imports
        # TypeScript-specific type imports (import type { }) could be added
        return self._parse_javascript_imports(content, filepath)
    
    def _get_node_text(self, node, content: bytes) -> str:
        """Get text from a tree-sitter node."""
        if node is None:
            return ""
        try:
            return content[node.start_byte:node.end_byte].decode('utf-8', errors='ignore')
        except Exception:
            return ""
    
    def _resolve_all_imports(self):
        """Resolve all imports to actual module paths."""
        for module_name, module_info in self.modules.items():
            for imp in module_info.imports:
                resolved = self._resolve_import(imp, module_info)
                if resolved:
                    imp.is_resolved = True
                    imp.resolved_path = resolved
                    self.stats["resolved_imports"] += 1
                else:
                    # Check if external
                    if self._is_external_import(imp.module_path):
                        imp.is_external = True
                        imp.is_resolved = True  # External counts as resolved
                        self.stats["external_imports"] += 1
                    else:
                        self.unresolved_imports.append(imp)
                        self.stats["unresolved_imports"] += 1
    
    def _resolve_import(self, imp: ImportInfo, source_module: ModuleInfo) -> Optional[str]:
        """Resolve a single import to an absolute file path."""
        module_path = imp.module_path
        
        # Handle Python relative imports
        if imp.import_type == ImportType.RELATIVE:
            return self._resolve_python_relative_import(module_path, source_module)
        
        # Handle absolute Python imports
        if source_module.file_path.endswith('.py'):
            return self._resolve_python_absolute_import(module_path)
        
        # Handle JavaScript/TypeScript imports
        if source_module.file_path.endswith(('.js', '.jsx', '.ts', '.tsx', '.mjs')):
            return self._resolve_js_import(module_path, source_module)
        
        return None
    
    def _resolve_python_relative_import(self, module_path: str, source_module: ModuleInfo) -> Optional[str]:
        """Resolve a Python relative import."""
        # Count leading dots
        dots = 0
        for char in module_path:
            if char == '.':
                dots += 1
            else:
                break
        
        relative_module = module_path[dots:]
        
        # Start from source file's directory
        source_dir = os.path.dirname(source_module.file_path)
        
        # Go up 'dots - 1' directories (one dot means current package)
        for _ in range(dots - 1):
            source_dir = os.path.dirname(source_dir)
        
        # Build the target path
        if relative_module:
            target_parts = relative_module.split('.')
            target_path = os.path.join(source_dir, *target_parts)
        else:
            target_path = source_dir
        
        # Check for module file or package
        candidates = [
            target_path + '.py',
            os.path.join(target_path, '__init__.py'),
        ]
        
        for candidate in candidates:
            if os.path.exists(candidate):
                return candidate
        
        return None
    
    def _resolve_python_absolute_import(self, module_path: str) -> Optional[str]:
        """Resolve a Python absolute import."""
        parts = module_path.split('.')
        
        # Try to find in project
        candidates = [
            os.path.join(self.project_root, *parts) + '.py',
            os.path.join(self.project_root, *parts, '__init__.py'),
        ]
        
        for candidate in candidates:
            if os.path.exists(candidate):
                return candidate
        
        # Check if it's a known package
        if parts[0] in self.packages:
            # Try to resolve within the package
            package_dir = os.path.dirname(self.packages[parts[0]])
            remaining = parts[1:]
            if remaining:
                candidates = [
                    os.path.join(package_dir, *remaining) + '.py',
                    os.path.join(package_dir, *remaining, '__init__.py'),
                ]
                for candidate in candidates:
                    if os.path.exists(candidate):
                        return candidate
            else:
                return self.packages[parts[0]]
        
        return None
    
    def _resolve_js_import(self, module_path: str, source_module: ModuleInfo) -> Optional[str]:
        """Resolve a JavaScript/TypeScript import."""
        source_dir = os.path.dirname(source_module.file_path)
        
        # Relative import
        if module_path.startswith('.'):
            # Resolve relative to source file
            resolved_base = os.path.normpath(os.path.join(source_dir, module_path))
            
            # Try various extensions
            extensions = ['.ts', '.tsx', '.js', '.jsx', '.mjs', '/index.ts', '/index.tsx', '/index.js']
            
            for ext in extensions:
                candidate = resolved_base + ext
                if os.path.exists(candidate):
                    return candidate
            
            # Check if it's a directory with index file
            if os.path.isdir(resolved_base):
                for ext in ['.ts', '.tsx', '.js', '.jsx']:
                    candidate = os.path.join(resolved_base, 'index' + ext)
                    if os.path.exists(candidate):
                        return candidate
        
        # Alias imports (e.g., @/components) - try common patterns
        if module_path.startswith('@/'):
            alias_path = module_path[2:]  # Remove @/
            
            # Common alias roots
            for root in ['src', 'app', 'lib', '']:
                base = os.path.join(self.project_root, root, alias_path)
                extensions = ['.ts', '.tsx', '.js', '.jsx']
                
                for ext in extensions:
                    candidate = base + ext
                    if os.path.exists(candidate):
                        return candidate
                
                # Try index files
                if os.path.isdir(base):
                    for ext in extensions:
                        candidate = os.path.join(base, 'index' + ext)
                        if os.path.exists(candidate):
                            return candidate
        
        return None
    
    def _is_external_import(self, module_path: str) -> bool:
        """Check if an import is for an external package."""
        # Python stdlib
        first_part = module_path.split('.')[0]
        if first_part in self.PYTHON_STDLIB:
            return True
        
        # Common external packages
        if first_part.lower() in self.COMMON_EXTERNAL:
            return True
        
        # Node built-ins
        if module_path in ('fs', 'path', 'http', 'https', 'crypto', 'url', 'os', 'util'):
            return True
        
        # npm packages (don't start with . or /)
        if not module_path.startswith('.') and not module_path.startswith('/'):
            # If not found in project, assume external
            return not any(
                module_path.startswith(mod.replace('.', '/')) or module_path.startswith(mod)
                for mod in self.modules.keys()
            )
        
        return False
    
    def _build_dependency_graph(self):
        """Build the dependency graph from resolved imports."""
        for module_name, module_info in self.modules.items():
            for imp in module_info.imports:
                if imp.is_resolved and imp.resolved_path:
                    # Find the target module
                    target_module = self.file_to_module.get(imp.resolved_path)
                    
                    if target_module:
                        # Add edge
                        self.dependency_edges.append(DependencyEdge(
                            source=module_name,
                            target=target_module,
                            import_type=imp.import_type,
                            imported_names=imp.imported_names,
                            line_number=imp.line_number
                        ))
                        
                        # Update module dependencies
                        module_info.dependencies.add(target_module)
                        if target_module in self.modules:
                            self.modules[target_module].dependents.add(module_name)
    
    def _detect_circular_dependencies(self) -> List[List[str]]:
        """Detect circular dependencies in the graph."""
        cycles = []
        visited = set()
        rec_stack = set()
        
        def dfs(module: str, path: List[str]):
            visited.add(module)
            rec_stack.add(module)
            path.append(module)
            
            if module in self.modules:
                for dep in self.modules[module].dependencies:
                    if dep not in visited:
                        dfs(dep, path.copy())
                    elif dep in rec_stack:
                        # Found a cycle
                        cycle_start = path.index(dep)
                        cycle = path[cycle_start:] + [dep]
                        # Normalize cycle (start from smallest element)
                        min_idx = cycle.index(min(cycle[:-1]))
                        normalized = cycle[min_idx:-1] + cycle[:min_idx] + [cycle[min_idx]]
                        if normalized not in cycles:
                            cycles.append(normalized)
            
            rec_stack.remove(module)
        
        for module in self.modules:
            if module not in visited:
                dfs(module, [])
        
        return cycles
    
    def resolve_symbol(self, symbol_name: str, source_file: str) -> Optional[Dict[str, Any]]:
        """
        Resolve a symbol name to its definition location.
        
        Args:
            symbol_name: The symbol to resolve (e.g., "format_date" or "utils.format_date")
            source_file: The file where the symbol is used
            
        Returns:
            Dict with file_path, line_number, module_name if found
        """
        source_module = self.file_to_module.get(source_file)
        if not source_module or source_module not in self.modules:
            return None
        
        module_info = self.modules[source_module]
        
        # Check if symbol was imported
        for imp in module_info.imports:
            if symbol_name in imp.imported_names:
                if imp.resolved_path:
                    return {
                        "file_path": imp.resolved_path,
                        "module_name": self.file_to_module.get(imp.resolved_path, imp.module_path),
                        "import_type": imp.import_type.value
                    }
            
            # Check aliases
            if symbol_name in imp.aliases:
                original_name = imp.aliases[symbol_name]
                if imp.resolved_path:
                    return {
                        "file_path": imp.resolved_path,
                        "module_name": self.file_to_module.get(imp.resolved_path, imp.module_path),
                        "original_name": original_name,
                        "import_type": imp.import_type.value
                    }
        
        return None
    
    def get_module_exports(self, module_name: str) -> List[str]:
        """Get the exported symbols from a module."""
        if module_name not in self.modules:
            return []
        
        module_info = self.modules[module_name]
        
        # Parse the file to find exports
        # For now, return function/class names at module level
        exports = []
        
        try:
            with open(module_info.file_path, 'rb') as f:
                content = f.read()
        except Exception:
            return exports
        
        if module_info.file_path.endswith('.py'):
            tree = self.py_parser.parse(content)
            
            def find_exports(node):
                if node.type in ('function_definition', 'class_definition'):
                    name_node = node.child_by_field_name('name')
                    if name_node:
                        name = self._get_node_text(name_node, content)
                        if not name.startswith('_'):  # Skip private
                            exports.append(name)
                
                # Only look at top-level definitions
                if node.type == 'module':
                    for child in node.children:
                        find_exports(child)
            
            find_exports(tree.root_node)
        
        return exports
    
    def _module_to_dict(self, module: ModuleInfo) -> Dict[str, Any]:
        """Convert ModuleInfo to dictionary."""
        return {
            "file_path": module.file_path,
            "module_name": module.module_name,
            "package_name": module.package_name,
            "is_package": module.is_package,
            "is_entry_point": module.is_entry_point,
            "imports_count": len(module.imports),
            "dependencies": list(module.dependencies),
            "dependents": list(module.dependents),
            "imports": [self._import_to_dict(i) for i in module.imports]
        }
    
    def _import_to_dict(self, imp: ImportInfo) -> Dict[str, Any]:
        """Convert ImportInfo to dictionary."""
        return {
            "module_path": imp.module_path,
            "imported_names": imp.imported_names,
            "aliases": imp.aliases,
            "import_type": imp.import_type.value,
            "line_number": imp.line_number,
            "is_resolved": imp.is_resolved,
            "resolved_path": imp.resolved_path,
            "is_external": imp.is_external,
            "is_dynamic": imp.is_dynamic
        }
    
    def _edge_to_dict(self, edge: DependencyEdge) -> Dict[str, Any]:
        """Convert DependencyEdge to dictionary."""
        return {
            "source": edge.source,
            "target": edge.target,
            "import_type": edge.import_type.value,
            "imported_names": edge.imported_names,
            "line_number": edge.line_number
        }


# Convenience function for API usage
def resolve_project_imports(project_path: str) -> Dict[str, Any]:
    """
    Resolve all imports in a project and return the dependency graph.
    
    Args:
        project_path: Path to project root
        
    Returns:
        Dict with modules, edges, circular dependencies, and statistics
    """
    resolver = ImportResolver(project_path)
    return resolver.scan_project()
