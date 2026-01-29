"""
Monorepo Analyzer Module

Provides comprehensive analysis of monorepo structures:
- Multi-project structure detection
- Build configuration parsing (package.json, pom.xml, go.mod, etc.)
- Shared library dependency tracking
- Service-level isolated analysis

Supports:
- JavaScript/TypeScript: npm workspaces, yarn workspaces, lerna, turborepo, nx
- Python: poetry workspaces, pip requirements
- Java: Maven multi-module, Gradle multi-project
- Go: Go modules, Go workspaces
"""

import os
import re
import json
import logging
from pathlib import Path
from typing import Dict, List, Optional, Set, Any, Tuple
from dataclasses import dataclass, field
from enum import Enum
import xml.etree.ElementTree as ET

logger = logging.getLogger(__name__)


# =============================================================================
# Enums and Data Classes
# =============================================================================

class ProjectType(str, Enum):
    """Type of project/package."""
    APPLICATION = "application"
    LIBRARY = "library"
    SERVICE = "service"
    PACKAGE = "package"
    MODULE = "module"
    UNKNOWN = "unknown"


class BuildSystem(str, Enum):
    """Build system/package manager."""
    # JavaScript/TypeScript
    NPM = "npm"
    YARN = "yarn"
    PNPM = "pnpm"
    LERNA = "lerna"
    TURBOREPO = "turborepo"
    NX = "nx"
    
    # Python
    PIP = "pip"
    POETRY = "poetry"
    SETUPTOOLS = "setuptools"
    PDM = "pdm"
    UV = "uv"
    
    # Java
    MAVEN = "maven"
    GRADLE = "gradle"
    
    # Go
    GO_MOD = "go_mod"
    GO_WORK = "go_work"
    
    # Rust
    CARGO = "cargo"
    
    # .NET
    DOTNET = "dotnet"
    
    UNKNOWN = "unknown"


class MonorepoTool(str, Enum):
    """Monorepo management tool."""
    LERNA = "lerna"
    TURBOREPO = "turborepo"
    NX = "nx"
    RUSH = "rush"
    BAZEL = "bazel"
    PANTS = "pants"
    YARN_WORKSPACES = "yarn_workspaces"
    NPM_WORKSPACES = "npm_workspaces"
    PNPM_WORKSPACES = "pnpm_workspaces"
    MAVEN_MULTIMODULE = "maven_multimodule"
    GRADLE_MULTIPROJECT = "gradle_multiproject"
    GO_WORKSPACE = "go_workspace"
    CARGO_WORKSPACE = "cargo_workspace"
    POETRY_MONOREPO = "poetry_monorepo"
    NONE = "none"


@dataclass
class Dependency:
    """Represents a project dependency."""
    name: str
    version: str = ""
    version_constraint: str = ""
    is_dev: bool = False
    is_local: bool = False
    local_path: Optional[str] = None
    is_optional: bool = False
    scope: str = "compile"  # compile, runtime, test, provided


@dataclass
class Script:
    """Represents a build/run script."""
    name: str
    command: str
    description: str = ""


@dataclass
class ProjectConfig:
    """Configuration for a single project/package."""
    name: str
    path: str
    project_type: ProjectType
    build_system: BuildSystem
    language: str
    version: str = ""
    description: str = ""
    
    # Dependencies
    dependencies: List[Dependency] = field(default_factory=list)
    dev_dependencies: List[Dependency] = field(default_factory=list)
    
    # Internal dependencies (other projects in monorepo)
    internal_dependencies: List[str] = field(default_factory=list)
    
    # Scripts
    scripts: List[Script] = field(default_factory=list)
    
    # Entry points
    main_file: Optional[str] = None
    entry_points: List[str] = field(default_factory=list)
    
    # Build configuration
    build_config: Dict[str, Any] = field(default_factory=dict)
    
    # Metadata
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class MonorepoStructure:
    """Complete monorepo structure."""
    root_path: str
    name: str
    monorepo_tool: MonorepoTool
    
    # All projects
    projects: List[ProjectConfig] = field(default_factory=list)
    
    # Dependency graph (project_name -> [dependent_project_names])
    dependency_graph: Dict[str, List[str]] = field(default_factory=dict)
    
    # Shared packages
    shared_packages: List[str] = field(default_factory=list)
    
    # Build order (topologically sorted)
    build_order: List[str] = field(default_factory=list)
    
    # Workspace configuration
    workspace_config: Dict[str, Any] = field(default_factory=dict)
    
    # Statistics
    stats: Dict[str, Any] = field(default_factory=dict)


@dataclass 
class DependencyEdge:
    """Edge in dependency graph for visualization."""
    source: str
    target: str
    dependency_type: str  # internal, external, dev
    version: str = ""


@dataclass
class DependencyGraph:
    """Visualization-ready dependency graph."""
    nodes: List[Dict[str, Any]] = field(default_factory=list)
    edges: List[Dict[str, Any]] = field(default_factory=list)


# =============================================================================
# Build Configuration Parsers
# =============================================================================

class PackageJsonParser:
    """Parser for package.json (npm/yarn/pnpm)."""
    
    def parse(self, file_path: str) -> Optional[ProjectConfig]:
        """Parse package.json file."""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            project_dir = os.path.dirname(file_path)
            
            config = ProjectConfig(
                name=data.get('name', os.path.basename(project_dir)),
                path=project_dir,
                project_type=self._detect_project_type(data),
                build_system=self._detect_build_system(project_dir),
                language=self._detect_language(project_dir, data),
                version=data.get('version', '0.0.0'),
                description=data.get('description', ''),
                main_file=data.get('main'),
                metadata={
                    'license': data.get('license'),
                    'author': data.get('author'),
                    'repository': data.get('repository'),
                    'private': data.get('private', False),
                }
            )
            
            # Parse dependencies
            config.dependencies = self._parse_dependencies(
                data.get('dependencies', {}), 
                is_dev=False
            )
            config.dev_dependencies = self._parse_dependencies(
                data.get('devDependencies', {}),
                is_dev=True
            )
            
            # Parse scripts
            config.scripts = [
                Script(name=name, command=cmd)
                for name, cmd in data.get('scripts', {}).items()
            ]
            
            # Entry points
            if data.get('main'):
                config.entry_points.append(data['main'])
            if data.get('module'):
                config.entry_points.append(data['module'])
            if data.get('bin'):
                bins = data['bin']
                if isinstance(bins, str):
                    config.entry_points.append(bins)
                elif isinstance(bins, dict):
                    config.entry_points.extend(bins.values())
            
            # Build config
            config.build_config = {
                'workspaces': data.get('workspaces'),
                'engines': data.get('engines'),
                'type': data.get('type'),  # module or commonjs
            }
            
            return config
            
        except Exception as e:
            logger.error(f"Error parsing {file_path}: {e}")
            return None
    
    def _detect_project_type(self, data: Dict) -> ProjectType:
        """Detect project type from package.json."""
        name = data.get('name', '')
        
        # Check for common patterns
        if data.get('private') and data.get('workspaces'):
            return ProjectType.MODULE  # Monorepo root
        
        if 'bin' in data:
            return ProjectType.APPLICATION
        
        if name.startswith('@') and '/' in name:
            # Scoped package, likely a library
            return ProjectType.LIBRARY
        
        if 'main' in data or 'module' in data or 'exports' in data:
            return ProjectType.LIBRARY
        
        return ProjectType.APPLICATION
    
    def _detect_build_system(self, project_dir: str) -> BuildSystem:
        """Detect build system from files."""
        if os.path.exists(os.path.join(project_dir, 'yarn.lock')):
            return BuildSystem.YARN
        if os.path.exists(os.path.join(project_dir, 'pnpm-lock.yaml')):
            return BuildSystem.PNPM
        if os.path.exists(os.path.join(project_dir, 'package-lock.json')):
            return BuildSystem.NPM
        return BuildSystem.NPM
    
    def _detect_language(self, project_dir: str, data: Dict) -> str:
        """Detect primary language."""
        deps = {**data.get('dependencies', {}), **data.get('devDependencies', {})}
        
        if 'typescript' in deps or os.path.exists(os.path.join(project_dir, 'tsconfig.json')):
            return 'typescript'
        return 'javascript'
    
    def _parse_dependencies(self, deps: Dict[str, str], is_dev: bool) -> List[Dependency]:
        """Parse dependencies dict."""
        result = []
        for name, version in deps.items():
            is_local = version.startswith('file:') or version.startswith('link:') or version.startswith('workspace:')
            local_path = None
            
            if is_local:
                # Extract local path
                if version.startswith('file:'):
                    local_path = version[5:]
                elif version.startswith('link:'):
                    local_path = version[5:]
                elif version.startswith('workspace:'):
                    local_path = version[10:] if version != 'workspace:*' else None
            
            result.append(Dependency(
                name=name,
                version_constraint=version,
                is_dev=is_dev,
                is_local=is_local,
                local_path=local_path
            ))
        
        return result


class PomXmlParser:
    """Parser for Maven pom.xml files."""
    
    def parse(self, file_path: str) -> Optional[ProjectConfig]:
        """Parse pom.xml file."""
        try:
            tree = ET.parse(file_path)
            root = tree.getroot()
            
            # Handle namespace
            ns = {'m': 'http://maven.apache.org/POM/4.0.0'}
            
            # Try with namespace first, then without
            def find(elem, path):
                result = elem.find(f'm:{path}', ns)
                if result is None:
                    result = elem.find(path)
                return result
            
            def findall(elem, path):
                result = elem.findall(f'm:{path}', ns)
                if not result:
                    result = elem.findall(path)
                return result
            
            project_dir = os.path.dirname(file_path)
            
            # Get basic info
            group_id = find(root, 'groupId')
            artifact_id = find(root, 'artifactId')
            version = find(root, 'version')
            packaging = find(root, 'packaging')
            name_elem = find(root, 'name')
            desc_elem = find(root, 'description')
            
            name = artifact_id.text if artifact_id is not None else os.path.basename(project_dir)
            
            config = ProjectConfig(
                name=name,
                path=project_dir,
                project_type=self._detect_project_type(packaging),
                build_system=BuildSystem.MAVEN,
                language='java',
                version=version.text if version is not None else '0.0.0',
                description=desc_elem.text if desc_elem is not None else '',
                metadata={
                    'groupId': group_id.text if group_id is not None else '',
                    'artifactId': artifact_id.text if artifact_id is not None else '',
                    'packaging': packaging.text if packaging is not None else 'jar',
                }
            )
            
            # Parse dependencies
            deps_elem = find(root, 'dependencies')
            if deps_elem is not None:
                for dep in findall(deps_elem, 'dependency'):
                    config.dependencies.append(self._parse_dependency(dep, ns))
            
            # Parse modules (for multi-module projects)
            modules_elem = find(root, 'modules')
            if modules_elem is not None:
                modules = findall(modules_elem, 'module')
                config.build_config['modules'] = [m.text for m in modules if m.text]
            
            # Check for parent
            parent = find(root, 'parent')
            if parent is not None:
                parent_artifact = find(parent, 'artifactId')
                if parent_artifact is not None:
                    config.metadata['parent'] = parent_artifact.text
            
            return config
            
        except Exception as e:
            logger.error(f"Error parsing {file_path}: {e}")
            return None
    
    def _detect_project_type(self, packaging_elem) -> ProjectType:
        """Detect project type from packaging."""
        if packaging_elem is None:
            return ProjectType.LIBRARY
        
        packaging = packaging_elem.text
        if packaging == 'pom':
            return ProjectType.MODULE
        elif packaging in ('war', 'ear'):
            return ProjectType.APPLICATION
        elif packaging == 'jar':
            return ProjectType.LIBRARY
        return ProjectType.UNKNOWN
    
    def _parse_dependency(self, dep_elem, ns: Dict) -> Dependency:
        """Parse a single dependency element."""
        def find(path):
            result = dep_elem.find(f'm:{path}', ns)
            if result is None:
                result = dep_elem.find(path)
            return result
        
        group_id = find('groupId')
        artifact_id = find('artifactId')
        version = find('version')
        scope = find('scope')
        optional = find('optional')
        
        name = f"{group_id.text}:{artifact_id.text}" if group_id is not None and artifact_id is not None else ""
        
        return Dependency(
            name=name,
            version=version.text if version is not None else '',
            scope=scope.text if scope is not None else 'compile',
            is_optional=optional is not None and optional.text == 'true',
            is_dev=scope is not None and scope.text in ('test', 'provided')
        )


class GoModParser:
    """Parser for go.mod files."""
    
    def parse(self, file_path: str) -> Optional[ProjectConfig]:
        """Parse go.mod file."""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            project_dir = os.path.dirname(file_path)
            
            # Parse module name
            module_match = re.search(r'^module\s+(\S+)', content, re.MULTILINE)
            module_name = module_match.group(1) if module_match else os.path.basename(project_dir)
            
            # Parse Go version
            go_match = re.search(r'^go\s+(\S+)', content, re.MULTILINE)
            go_version = go_match.group(1) if go_match else ''
            
            config = ProjectConfig(
                name=module_name,
                path=project_dir,
                project_type=self._detect_project_type(project_dir, module_name),
                build_system=BuildSystem.GO_MOD,
                language='go',
                version='',
                metadata={
                    'go_version': go_version,
                    'module': module_name,
                }
            )
            
            # Parse require block
            require_pattern = r'require\s*\((.*?)\)|require\s+(\S+)\s+(\S+)'
            
            # Multi-line require block
            block_match = re.search(r'require\s*\((.*?)\)', content, re.DOTALL)
            if block_match:
                block = block_match.group(1)
                for line in block.strip().split('\n'):
                    line = line.strip()
                    if line and not line.startswith('//'):
                        parts = line.split()
                        if len(parts) >= 2:
                            name = parts[0]
                            version = parts[1]
                            is_indirect = '// indirect' in line
                            config.dependencies.append(Dependency(
                                name=name,
                                version=version,
                                is_optional=is_indirect,
                            ))
            
            # Single-line requires
            for match in re.finditer(r'^require\s+(\S+)\s+(\S+)', content, re.MULTILINE):
                config.dependencies.append(Dependency(
                    name=match.group(1),
                    version=match.group(2),
                ))
            
            # Parse replace directives for local modules
            for match in re.finditer(r'^replace\s+(\S+)\s+=>\s+(\S+)', content, re.MULTILINE):
                original = match.group(1)
                replacement = match.group(2)
                if replacement.startswith('./') or replacement.startswith('../'):
                    # Local replacement
                    for dep in config.dependencies:
                        if dep.name == original:
                            dep.is_local = True
                            dep.local_path = replacement
            
            return config
            
        except Exception as e:
            logger.error(f"Error parsing {file_path}: {e}")
            return None
    
    def _detect_project_type(self, project_dir: str, module_name: str) -> ProjectType:
        """Detect project type from structure."""
        # Check for cmd directory (Go convention for applications)
        if os.path.exists(os.path.join(project_dir, 'cmd')):
            return ProjectType.APPLICATION
        
        # Check for main.go
        if os.path.exists(os.path.join(project_dir, 'main.go')):
            return ProjectType.APPLICATION
        
        # Check for internal/pkg directories (library patterns)
        if os.path.exists(os.path.join(project_dir, 'pkg')) or \
           os.path.exists(os.path.join(project_dir, 'internal')):
            return ProjectType.LIBRARY
        
        return ProjectType.PACKAGE


class PyProjectParser:
    """Parser for pyproject.toml files."""
    
    def parse(self, file_path: str) -> Optional[ProjectConfig]:
        """Parse pyproject.toml file."""
        try:
            # Simple TOML parsing without external library
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            project_dir = os.path.dirname(file_path)
            
            # Extract project name
            name_match = re.search(r'^\s*name\s*=\s*["\']([^"\']+)["\']', content, re.MULTILINE)
            name = name_match.group(1) if name_match else os.path.basename(project_dir)
            
            # Extract version
            version_match = re.search(r'^\s*version\s*=\s*["\']([^"\']+)["\']', content, re.MULTILINE)
            version = version_match.group(1) if version_match else '0.0.0'
            
            # Extract description
            desc_match = re.search(r'^\s*description\s*=\s*["\']([^"\']+)["\']', content, re.MULTILINE)
            description = desc_match.group(1) if desc_match else ''
            
            # Detect build system
            build_system = BuildSystem.SETUPTOOLS
            if '[tool.poetry]' in content:
                build_system = BuildSystem.POETRY
            elif '[tool.pdm]' in content:
                build_system = BuildSystem.PDM
            
            config = ProjectConfig(
                name=name,
                path=project_dir,
                project_type=ProjectType.PACKAGE,
                build_system=build_system,
                language='python',
                version=version,
                description=description,
            )
            
            # Parse dependencies (simplified)
            deps_match = re.search(r'\[project\]\s*.*?dependencies\s*=\s*\[(.*?)\]', content, re.DOTALL)
            if deps_match:
                deps_block = deps_match.group(1)
                for dep in re.findall(r'["\']([^"\']+)["\']', deps_block):
                    config.dependencies.append(Dependency(
                        name=dep.split('[')[0].split('<')[0].split('>')[0].split('=')[0].split('~')[0].strip(),
                        version_constraint=dep,
                    ))
            
            # Poetry dependencies
            poetry_deps = re.findall(r'^\s*(\w[\w-]*)\s*=', content, re.MULTILINE)
            if '[tool.poetry.dependencies]' in content:
                for dep in poetry_deps:
                    if dep not in ('python', 'name', 'version', 'description'):
                        config.dependencies.append(Dependency(name=dep))
            
            return config
            
        except Exception as e:
            logger.error(f"Error parsing {file_path}: {e}")
            return None


class GradleParser:
    """Parser for build.gradle and build.gradle.kts files."""
    
    def parse(self, file_path: str) -> Optional[ProjectConfig]:
        """Parse Gradle build file."""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            project_dir = os.path.dirname(file_path)
            is_kotlin_dsl = file_path.endswith('.kts')
            
            # Extract project name from settings.gradle if exists
            settings_file = os.path.join(project_dir, 'settings.gradle.kts' if is_kotlin_dsl else 'settings.gradle')
            name = os.path.basename(project_dir)
            
            if os.path.exists(settings_file):
                with open(settings_file, 'r', encoding='utf-8') as f:
                    settings = f.read()
                name_match = re.search(r'rootProject\.name\s*=\s*["\']([^"\']+)["\']', settings)
                if name_match:
                    name = name_match.group(1)
            
            # Detect project type
            project_type = ProjectType.LIBRARY
            if "application" in content or "mainClass" in content:
                project_type = ProjectType.APPLICATION
            elif "java-library" in content:
                project_type = ProjectType.LIBRARY
            
            config = ProjectConfig(
                name=name,
                path=project_dir,
                project_type=project_type,
                build_system=BuildSystem.GRADLE,
                language=self._detect_language(content, project_dir),
                metadata={
                    'kotlin_dsl': is_kotlin_dsl,
                }
            )
            
            # Parse dependencies
            dep_pattern = r'(implementation|api|compileOnly|runtimeOnly|testImplementation)\s*[\(\s]["\']([^"\']+)["\']'
            for match in re.finditer(dep_pattern, content):
                scope = match.group(1)
                dep_str = match.group(2)
                
                config.dependencies.append(Dependency(
                    name=dep_str,
                    scope=scope,
                    is_dev=scope.startswith('test'),
                ))
            
            # Parse subprojects
            subprojects = []
            include_pattern = r'include\s*[\(\s]["\']([^"\']+)["\']'
            if os.path.exists(settings_file):
                with open(settings_file, 'r', encoding='utf-8') as f:
                    settings = f.read()
                for match in re.finditer(include_pattern, settings):
                    subprojects.append(match.group(1))
            
            if subprojects:
                config.build_config['subprojects'] = subprojects
            
            return config
            
        except Exception as e:
            logger.error(f"Error parsing {file_path}: {e}")
            return None
    
    def _detect_language(self, content: str, project_dir: str) -> str:
        """Detect primary language from Gradle file."""
        if "kotlin(" in content or "org.jetbrains.kotlin" in content:
            return 'kotlin'
        if os.path.exists(os.path.join(project_dir, 'src', 'main', 'kotlin')):
            return 'kotlin'
        return 'java'


class CargoTomlParser:
    """Parser for Cargo.toml (Rust)."""
    
    def parse(self, file_path: str) -> Optional[ProjectConfig]:
        """Parse Cargo.toml file."""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            project_dir = os.path.dirname(file_path)
            
            # Extract package info
            name_match = re.search(r'^\s*name\s*=\s*["\']([^"\']+)["\']', content, re.MULTILINE)
            name = name_match.group(1) if name_match else os.path.basename(project_dir)
            
            version_match = re.search(r'^\s*version\s*=\s*["\']([^"\']+)["\']', content, re.MULTILINE)
            version = version_match.group(1) if version_match else '0.0.0'
            
            # Check if workspace
            is_workspace = '[workspace]' in content
            
            config = ProjectConfig(
                name=name,
                path=project_dir,
                project_type=ProjectType.MODULE if is_workspace else self._detect_project_type(project_dir),
                build_system=BuildSystem.CARGO,
                language='rust',
                version=version,
            )
            
            # Parse dependencies
            in_deps = False
            for line in content.split('\n'):
                line = line.strip()
                if line == '[dependencies]':
                    in_deps = True
                    continue
                elif line.startswith('['):
                    in_deps = False
                    continue
                
                if in_deps and '=' in line:
                    parts = line.split('=', 1)
                    dep_name = parts[0].strip()
                    dep_value = parts[1].strip()
                    
                    # Check for path dependency
                    is_local = 'path' in dep_value
                    local_path = None
                    if is_local:
                        path_match = re.search(r'path\s*=\s*["\']([^"\']+)["\']', dep_value)
                        if path_match:
                            local_path = path_match.group(1)
                    
                    config.dependencies.append(Dependency(
                        name=dep_name,
                        version_constraint=dep_value,
                        is_local=is_local,
                        local_path=local_path,
                    ))
            
            # Parse workspace members
            if is_workspace:
                members_match = re.search(r'members\s*=\s*\[(.*?)\]', content, re.DOTALL)
                if members_match:
                    members = re.findall(r'["\']([^"\']+)["\']', members_match.group(1))
                    config.build_config['members'] = members
            
            return config
            
        except Exception as e:
            logger.error(f"Error parsing {file_path}: {e}")
            return None
    
    def _detect_project_type(self, project_dir: str) -> ProjectType:
        """Detect project type from structure."""
        if os.path.exists(os.path.join(project_dir, 'src', 'main.rs')):
            return ProjectType.APPLICATION
        if os.path.exists(os.path.join(project_dir, 'src', 'lib.rs')):
            return ProjectType.LIBRARY
        return ProjectType.PACKAGE


# =============================================================================
# Monorepo Detector
# =============================================================================

class MonorepoDetector:
    """Detects monorepo structure and tool."""
    
    def __init__(self, root_path: str):
        self.root_path = root_path
    
    def detect(self) -> Tuple[MonorepoTool, Dict[str, Any]]:
        """Detect monorepo tool and configuration."""
        # Check for various monorepo tools
        
        # Lerna
        lerna_json = os.path.join(self.root_path, 'lerna.json')
        if os.path.exists(lerna_json):
            return MonorepoTool.LERNA, self._parse_lerna(lerna_json)
        
        # Turborepo
        turbo_json = os.path.join(self.root_path, 'turbo.json')
        if os.path.exists(turbo_json):
            return MonorepoTool.TURBOREPO, self._parse_turbo(turbo_json)
        
        # Nx
        nx_json = os.path.join(self.root_path, 'nx.json')
        if os.path.exists(nx_json):
            return MonorepoTool.NX, self._parse_nx(nx_json)
        
        # Rush
        rush_json = os.path.join(self.root_path, 'rush.json')
        if os.path.exists(rush_json):
            return MonorepoTool.RUSH, {}
        
        # Bazel
        if os.path.exists(os.path.join(self.root_path, 'WORKSPACE')) or \
           os.path.exists(os.path.join(self.root_path, 'WORKSPACE.bazel')):
            return MonorepoTool.BAZEL, {}
        
        # Pants
        if os.path.exists(os.path.join(self.root_path, 'pants.toml')) or \
           os.path.exists(os.path.join(self.root_path, 'pants.ini')):
            return MonorepoTool.PANTS, {}
        
        # Go workspace
        go_work = os.path.join(self.root_path, 'go.work')
        if os.path.exists(go_work):
            return MonorepoTool.GO_WORKSPACE, self._parse_go_work(go_work)
        
        # Cargo workspace
        cargo_toml = os.path.join(self.root_path, 'Cargo.toml')
        if os.path.exists(cargo_toml):
            with open(cargo_toml, 'r') as f:
                if '[workspace]' in f.read():
                    return MonorepoTool.CARGO_WORKSPACE, {}
        
        # Maven multi-module
        pom_xml = os.path.join(self.root_path, 'pom.xml')
        if os.path.exists(pom_xml):
            if self._is_maven_multimodule(pom_xml):
                return MonorepoTool.MAVEN_MULTIMODULE, {}
        
        # Gradle multi-project
        settings_gradle = os.path.join(self.root_path, 'settings.gradle')
        settings_gradle_kts = os.path.join(self.root_path, 'settings.gradle.kts')
        if os.path.exists(settings_gradle) or os.path.exists(settings_gradle_kts):
            if self._is_gradle_multiproject(settings_gradle if os.path.exists(settings_gradle) else settings_gradle_kts):
                return MonorepoTool.GRADLE_MULTIPROJECT, {}
        
        # Check package.json workspaces
        package_json = os.path.join(self.root_path, 'package.json')
        if os.path.exists(package_json):
            with open(package_json, 'r') as f:
                try:
                    data = json.load(f)
                    workspaces = data.get('workspaces', [])
                    if workspaces:
                        # Determine workspace manager
                        if os.path.exists(os.path.join(self.root_path, 'pnpm-workspace.yaml')):
                            return MonorepoTool.PNPM_WORKSPACES, {'workspaces': workspaces}
                        if os.path.exists(os.path.join(self.root_path, 'yarn.lock')):
                            return MonorepoTool.YARN_WORKSPACES, {'workspaces': workspaces}
                        return MonorepoTool.NPM_WORKSPACES, {'workspaces': workspaces}
                except:
                    pass
        
        return MonorepoTool.NONE, {}
    
    def _parse_lerna(self, file_path: str) -> Dict:
        """Parse lerna.json."""
        try:
            with open(file_path, 'r') as f:
                return json.load(f)
        except:
            return {}
    
    def _parse_turbo(self, file_path: str) -> Dict:
        """Parse turbo.json."""
        try:
            with open(file_path, 'r') as f:
                return json.load(f)
        except:
            return {}
    
    def _parse_nx(self, file_path: str) -> Dict:
        """Parse nx.json."""
        try:
            with open(file_path, 'r') as f:
                return json.load(f)
        except:
            return {}
    
    def _parse_go_work(self, file_path: str) -> Dict:
        """Parse go.work file."""
        try:
            with open(file_path, 'r') as f:
                content = f.read()
            
            # Extract use directives
            uses = re.findall(r'use\s+(\S+)', content)
            return {'uses': uses}
        except:
            return {}
    
    def _is_maven_multimodule(self, pom_path: str) -> bool:
        """Check if Maven project has modules."""
        try:
            tree = ET.parse(pom_path)
            root = tree.getroot()
            ns = {'m': 'http://maven.apache.org/POM/4.0.0'}
            
            modules = root.find('m:modules', ns) or root.find('modules')
            return modules is not None and len(list(modules)) > 0
        except:
            return False
    
    def _is_gradle_multiproject(self, settings_path: str) -> bool:
        """Check if Gradle project has subprojects."""
        try:
            with open(settings_path, 'r') as f:
                content = f.read()
            return 'include' in content
        except:
            return False


# =============================================================================
# Main Monorepo Analyzer
# =============================================================================

class MonorepoAnalyzer:
    """
    Comprehensive Monorepo Analyzer.
    
    Detects and analyzes monorepo structures:
    - Identifies monorepo tool (Lerna, Turborepo, Nx, etc.)
    - Discovers all projects/packages
    - Maps internal dependencies
    - Calculates build order
    - Generates dependency graph
    """
    
    # Build file patterns
    BUILD_FILES = {
        'package.json': PackageJsonParser,
        'pom.xml': PomXmlParser,
        'go.mod': GoModParser,
        'pyproject.toml': PyProjectParser,
        'build.gradle': GradleParser,
        'build.gradle.kts': GradleParser,
        'Cargo.toml': CargoTomlParser,
    }
    
    def __init__(self, root_path: str = None):
        self.root_path = root_path or os.getcwd()
        self.projects: Dict[str, ProjectConfig] = {}
        self.monorepo_tool = MonorepoTool.NONE
        self.workspace_config: Dict = {}
    
    def analyze(self) -> MonorepoStructure:
        """Analyze the monorepo structure."""
        # Detect monorepo tool
        detector = MonorepoDetector(self.root_path)
        self.monorepo_tool, self.workspace_config = detector.detect()
        
        # Discover all projects
        self._discover_projects()
        
        # Resolve internal dependencies
        self._resolve_internal_dependencies()
        
        # Build dependency graph
        dependency_graph = self._build_dependency_graph()
        
        # Calculate build order
        build_order = self._calculate_build_order(dependency_graph)
        
        # Identify shared packages
        shared_packages = self._identify_shared_packages(dependency_graph)
        
        # Get root name
        root_name = os.path.basename(self.root_path)
        if self.monorepo_tool in (MonorepoTool.NPM_WORKSPACES, MonorepoTool.YARN_WORKSPACES, MonorepoTool.PNPM_WORKSPACES):
            pkg_json = os.path.join(self.root_path, 'package.json')
            if os.path.exists(pkg_json):
                with open(pkg_json, 'r') as f:
                    data = json.load(f)
                    root_name = data.get('name', root_name)
        
        # Compile stats
        stats = {
            'total_projects': len(self.projects),
            'project_types': {},
            'languages': {},
            'total_dependencies': 0,
            'internal_dependencies': 0,
            'shared_packages': len(shared_packages),
        }
        
        for project in self.projects.values():
            # Count project types
            pt = project.project_type.value
            stats['project_types'][pt] = stats['project_types'].get(pt, 0) + 1
            
            # Count languages
            lang = project.language
            stats['languages'][lang] = stats['languages'].get(lang, 0) + 1
            
            # Count dependencies
            stats['total_dependencies'] += len(project.dependencies) + len(project.dev_dependencies)
            stats['internal_dependencies'] += len(project.internal_dependencies)
        
        return MonorepoStructure(
            root_path=self.root_path,
            name=root_name,
            monorepo_tool=self.monorepo_tool,
            projects=list(self.projects.values()),
            dependency_graph=dependency_graph,
            shared_packages=shared_packages,
            build_order=build_order,
            workspace_config=self.workspace_config,
            stats=stats
        )
    
    def _discover_projects(self):
        """Discover all projects in the monorepo."""
        # Get workspace patterns
        patterns = self._get_workspace_patterns()
        
        if patterns:
            # Use workspace patterns to find projects
            for pattern in patterns:
                self._find_projects_by_pattern(pattern)
        else:
            # Scan entire directory
            self._scan_for_projects(self.root_path)
    
    def _get_workspace_patterns(self) -> List[str]:
        """Get workspace patterns from configuration."""
        patterns = []
        
        # From workspace_config
        if 'workspaces' in self.workspace_config:
            ws = self.workspace_config['workspaces']
            if isinstance(ws, list):
                patterns.extend(ws)
            elif isinstance(ws, dict) and 'packages' in ws:
                patterns.extend(ws['packages'])
        
        # Lerna packages
        if 'packages' in self.workspace_config:
            patterns.extend(self.workspace_config['packages'])
        
        # Go workspace
        if 'uses' in self.workspace_config:
            patterns.extend(self.workspace_config['uses'])
        
        return patterns
    
    def _find_projects_by_pattern(self, pattern: str):
        """Find projects matching a glob pattern."""
        import glob
        
        # Convert workspace pattern to glob
        if pattern.endswith('/*'):
            pattern = pattern[:-2] + '/**'
        
        # Find matching directories
        full_pattern = os.path.join(self.root_path, pattern)
        
        for path in glob.glob(full_pattern, recursive=True):
            if os.path.isdir(path):
                self._try_parse_project(path)
    
    def _scan_for_projects(self, directory: str, max_depth: int = 5, current_depth: int = 0):
        """Recursively scan for projects."""
        if current_depth > max_depth:
            return
        
        # Skip common non-project directories
        skip_dirs = {'node_modules', '.git', '__pycache__', 'venv', 'env', 
                     'dist', 'build', 'target', '.next', '.nuxt', 'vendor'}
        
        try:
            entries = os.listdir(directory)
        except PermissionError:
            return
        
        # Check if this directory is a project
        self._try_parse_project(directory)
        
        # Recurse into subdirectories
        for entry in entries:
            if entry in skip_dirs or entry.startswith('.'):
                continue
            
            path = os.path.join(directory, entry)
            if os.path.isdir(path):
                self._scan_for_projects(path, max_depth, current_depth + 1)
    
    def _try_parse_project(self, directory: str):
        """Try to parse a project from a directory."""
        for build_file, parser_class in self.BUILD_FILES.items():
            file_path = os.path.join(directory, build_file)
            if os.path.exists(file_path):
                parser = parser_class()
                config = parser.parse(file_path)
                if config:
                    self.projects[config.name] = config
                    break  # Only parse first matching build file
    
    def _resolve_internal_dependencies(self):
        """Resolve which dependencies are internal (other monorepo projects)."""
        project_names = set(self.projects.keys())
        
        for project in self.projects.values():
            internal_deps = []
            
            for dep in project.dependencies + project.dev_dependencies:
                # Check if dependency is another project
                if dep.name in project_names:
                    internal_deps.append(dep.name)
                elif dep.is_local and dep.local_path:
                    # Resolve local path to project
                    local_abs = os.path.normpath(
                        os.path.join(project.path, dep.local_path)
                    )
                    for p_name, p_config in self.projects.items():
                        if os.path.normpath(p_config.path) == local_abs:
                            internal_deps.append(p_name)
                            break
            
            project.internal_dependencies = internal_deps
    
    def _build_dependency_graph(self) -> Dict[str, List[str]]:
        """Build dependency graph from internal dependencies."""
        graph = {}
        
        for name, project in self.projects.items():
            graph[name] = project.internal_dependencies.copy()
        
        return graph
    
    def _calculate_build_order(self, graph: Dict[str, List[str]]) -> List[str]:
        """Calculate topological build order."""
        # Kahn's algorithm for topological sort
        in_degree = {node: 0 for node in graph}
        
        for node in graph:
            for dep in graph[node]:
                if dep in in_degree:
                    in_degree[dep] = in_degree.get(dep, 0) + 1
        
        # Start with nodes that have no dependencies
        queue = [node for node in in_degree if in_degree[node] == 0]
        result = []
        
        while queue:
            node = queue.pop(0)
            result.append(node)
            
            for other in graph:
                if node in graph[other]:
                    in_degree[node] -= 1
                    if in_degree.get(node, 0) == 0:
                        queue.append(node)
        
        # Reverse for build order (dependencies first)
        return list(reversed(result))
    
    def _identify_shared_packages(self, graph: Dict[str, List[str]]) -> List[str]:
        """Identify packages that are dependencies of multiple projects."""
        dep_count = {}
        
        for deps in graph.values():
            for dep in deps:
                dep_count[dep] = dep_count.get(dep, 0) + 1
        
        # Shared if used by more than one project
        return [name for name, count in dep_count.items() if count > 1]
    
    def get_project(self, name: str) -> Optional[ProjectConfig]:
        """Get a specific project configuration."""
        return self.projects.get(name)
    
    def get_dependents(self, project_name: str) -> List[str]:
        """Get projects that depend on the given project."""
        dependents = []
        
        for name, project in self.projects.items():
            if project_name in project.internal_dependencies:
                dependents.append(name)
        
        return dependents
    
    def get_dependencies(self, project_name: str, include_transitive: bool = False) -> List[str]:
        """Get dependencies of a project."""
        project = self.projects.get(project_name)
        if not project:
            return []
        
        if not include_transitive:
            return project.internal_dependencies.copy()
        
        # BFS for transitive dependencies
        visited = set()
        queue = project.internal_dependencies.copy()
        result = []
        
        while queue:
            dep = queue.pop(0)
            if dep in visited:
                continue
            
            visited.add(dep)
            result.append(dep)
            
            dep_project = self.projects.get(dep)
            if dep_project:
                queue.extend(dep_project.internal_dependencies)
        
        return result
    
    def build_visualization_graph(self) -> DependencyGraph:
        """Build visualization-ready dependency graph."""
        nodes = []
        edges = []
        
        # Create nodes
        for name, project in self.projects.items():
            nodes.append({
                'id': name,
                'label': name,
                'type': project.project_type.value,
                'language': project.language,
                'path': project.path,
                'version': project.version,
                'build_system': project.build_system.value,
            })
        
        # Create edges
        for name, project in self.projects.items():
            for dep in project.internal_dependencies:
                edges.append({
                    'source': name,
                    'target': dep,
                    'type': 'internal',
                })
        
        return DependencyGraph(nodes=nodes, edges=edges)


# =============================================================================
# Helper Functions
# =============================================================================

def analyze_monorepo(root_path: str) -> Dict[str, Any]:
    """Analyze a monorepo and return results as dict."""
    analyzer = MonorepoAnalyzer(root_path)
    structure = analyzer.analyze()
    
    return {
        'root_path': structure.root_path,
        'name': structure.name,
        'monorepo_tool': structure.monorepo_tool.value,
        'projects': [
            {
                'name': p.name,
                'path': p.path,
                'project_type': p.project_type.value,
                'build_system': p.build_system.value,
                'language': p.language,
                'version': p.version,
                'description': p.description,
                'internal_dependencies': p.internal_dependencies,
                'dependency_count': len(p.dependencies) + len(p.dev_dependencies),
                'scripts': [{'name': s.name, 'command': s.command} for s in p.scripts],
            }
            for p in structure.projects
        ],
        'dependency_graph': structure.dependency_graph,
        'shared_packages': structure.shared_packages,
        'build_order': structure.build_order,
        'stats': structure.stats,
    }


def get_project_details(root_path: str, project_name: str) -> Optional[Dict[str, Any]]:
    """Get detailed information about a specific project."""
    analyzer = MonorepoAnalyzer(root_path)
    analyzer.analyze()
    
    project = analyzer.get_project(project_name)
    if not project:
        return None
    
    return {
        'name': project.name,
        'path': project.path,
        'project_type': project.project_type.value,
        'build_system': project.build_system.value,
        'language': project.language,
        'version': project.version,
        'description': project.description,
        'main_file': project.main_file,
        'entry_points': project.entry_points,
        'dependencies': [
            {
                'name': d.name,
                'version': d.version_constraint or d.version,
                'is_dev': d.is_dev,
                'is_local': d.is_local,
                'local_path': d.local_path,
            }
            for d in project.dependencies
        ],
        'dev_dependencies': [
            {
                'name': d.name,
                'version': d.version_constraint or d.version,
                'is_local': d.is_local,
            }
            for d in project.dev_dependencies
        ],
        'internal_dependencies': project.internal_dependencies,
        'dependents': analyzer.get_dependents(project_name),
        'transitive_dependencies': analyzer.get_dependencies(project_name, include_transitive=True),
        'scripts': [{'name': s.name, 'command': s.command} for s in project.scripts],
        'build_config': project.build_config,
        'metadata': project.metadata,
    }


def get_dependency_graph(root_path: str) -> Dict[str, Any]:
    """Get visualization-ready dependency graph."""
    analyzer = MonorepoAnalyzer(root_path)
    analyzer.analyze()
    graph = analyzer.build_visualization_graph()
    
    return {
        'nodes': graph.nodes,
        'edges': graph.edges,
    }


def get_affected_projects(root_path: str, changed_projects: List[str]) -> Dict[str, Any]:
    """Get projects affected by changes in the given projects."""
    analyzer = MonorepoAnalyzer(root_path)
    analyzer.analyze()
    
    affected = set(changed_projects)
    queue = list(changed_projects)
    
    while queue:
        project = queue.pop(0)
        dependents = analyzer.get_dependents(project)
        
        for dep in dependents:
            if dep not in affected:
                affected.add(dep)
                queue.append(dep)
    
    # Calculate build order for affected projects
    all_deps = {}
    for name in affected:
        project = analyzer.get_project(name)
        if project:
            all_deps[name] = [d for d in project.internal_dependencies if d in affected]
    
    build_order = analyzer._calculate_build_order(all_deps)
    
    return {
        'changed': changed_projects,
        'affected': list(affected),
        'build_order': build_order,
    }
