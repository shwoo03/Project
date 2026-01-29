"""
PHP Framework Extractors for Laravel and Symfony.

Supports:
- Laravel routes, controllers, middleware
- Symfony routes, controllers, annotations
- Common PHP input sources ($_GET, $_POST, Request object)
- PHP security sinks
"""

from typing import List, Dict, Optional, Tuple, Any
from dataclasses import dataclass
import re


# ============================================
# PHP Dangerous Sinks
# ============================================

PHP_DANGEROUS_SINKS: Dict[str, Tuple[str, str]] = {
    # Command Injection
    "exec": ("CMDI", "HIGH"),
    "shell_exec": ("CMDI", "HIGH"),
    "system": ("CMDI", "HIGH"),
    "passthru": ("CMDI", "HIGH"),
    "popen": ("CMDI", "HIGH"),
    "proc_open": ("CMDI", "HIGH"),
    "pcntl_exec": ("CMDI", "HIGH"),
    "backtick": ("CMDI", "HIGH"),  # `` operator
    
    # Code Injection
    "eval": ("CODE", "HIGH"),
    "assert": ("CODE", "HIGH"),
    "create_function": ("CODE", "HIGH"),
    "preg_replace": ("CODE", "MEDIUM"),  # with /e modifier
    
    # SQL Injection
    "mysql_query": ("SQLI", "HIGH"),
    "mysqli_query": ("SQLI", "HIGH"),
    "pg_query": ("SQLI", "HIGH"),
    "sqlite_query": ("SQLI", "HIGH"),
    "query": ("SQLI", "MEDIUM"),  # PDO/Eloquent
    "raw": ("SQLI", "HIGH"),  # DB::raw()
    "whereRaw": ("SQLI", "HIGH"),
    "selectRaw": ("SQLI", "HIGH"),
    
    # File Inclusion
    "include": ("LFI", "HIGH"),
    "include_once": ("LFI", "HIGH"),
    "require": ("LFI", "HIGH"),
    "require_once": ("LFI", "HIGH"),
    
    # Path Traversal
    "file_get_contents": ("PATH", "MEDIUM"),
    "file_put_contents": ("PATH", "MEDIUM"),
    "fopen": ("PATH", "MEDIUM"),
    "readfile": ("PATH", "MEDIUM"),
    "unlink": ("PATH", "HIGH"),
    "rmdir": ("PATH", "HIGH"),
    "copy": ("PATH", "MEDIUM"),
    "rename": ("PATH", "MEDIUM"),
    
    # XSS (when output without escaping)
    "echo": ("XSS", "LOW"),
    "print": ("XSS", "LOW"),
    "printf": ("XSS", "LOW"),
    
    # SSRF
    "curl_exec": ("SSRF", "MEDIUM"),
    "file_get_contents": ("SSRF", "MEDIUM"),
    "fopen": ("SSRF", "MEDIUM"),
    
    # Deserialization
    "unserialize": ("DESER", "HIGH"),
    
    # XML External Entity
    "simplexml_load_string": ("XXE", "MEDIUM"),
    "simplexml_load_file": ("XXE", "MEDIUM"),
    "DOMDocument::loadXML": ("XXE", "MEDIUM"),
}


@dataclass
class LaravelRoute:
    """Represents a Laravel route definition."""
    method: str
    path: str
    controller: Optional[str]
    action: Optional[str]
    middleware: List[str]
    line: int


@dataclass
class SymfonyRoute:
    """Represents a Symfony route definition."""
    name: str
    path: str
    controller: str
    methods: List[str]
    line: int


class LaravelExtractor:
    """
    Extracts Laravel-specific patterns.
    
    Supports:
    - Route definitions (web.php, api.php)
    - Controller methods
    - Request input handling
    - Middleware
    - Eloquent queries
    """
    
    # Laravel route patterns
    ROUTE_PATTERNS = [
        # Route::get('/path', [Controller::class, 'method'])
        r"Route::(get|post|put|patch|delete|any|match)\s*\(\s*['\"]([^'\"]+)['\"]",
        # Route::resource, Route::apiResource
        r"Route::(resource|apiResource)\s*\(\s*['\"]([^'\"]+)['\"]",
    ]
    
    # Laravel input patterns
    INPUT_PATTERNS = [
        (r"\$request->input\s*\(\s*['\"](\w+)['\"]", "body"),
        (r"\$request->get\s*\(\s*['\"](\w+)['\"]", "query"),
        (r"\$request->query\s*\(\s*['\"](\w+)['\"]", "query"),
        (r"\$request->post\s*\(\s*['\"](\w+)['\"]", "body"),
        (r"\$request->file\s*\(\s*['\"](\w+)['\"]", "file"),
        (r"\$request->cookie\s*\(\s*['\"](\w+)['\"]", "cookie"),
        (r"\$request->header\s*\(\s*['\"](\w+)['\"]", "header"),
        (r"\$request->(\w+)", "unknown"),  # $request->name
        (r"request\s*\(\s*['\"](\w+)['\"]", "body"),  # request('key')
    ]
    
    def is_laravel_file(self, content: str) -> bool:
        """Check if file uses Laravel patterns."""
        indicators = [
            "use Illuminate\\",
            "namespace App\\",
            "extends Controller",
            "Route::",
            "Eloquent",
            "->validate(",
        ]
        return any(ind in content for ind in indicators)
    
    def extract_routes(self, content: str) -> List[LaravelRoute]:
        """Extract Laravel route definitions."""
        routes = []
        
        for pattern in self.ROUTE_PATTERNS:
            for match in re.finditer(pattern, content, re.IGNORECASE):
                method = match.group(1).upper()
                path = match.group(2)
                line = content[:match.start()].count('\n') + 1
                
                # Try to extract controller info
                controller, action = self._extract_controller_action(content, match.end())
                
                # Try to extract middleware
                middleware = self._extract_middleware(content, match.start())
                
                routes.append(LaravelRoute(
                    method=method,
                    path=path,
                    controller=controller,
                    action=action,
                    middleware=middleware,
                    line=line
                ))
        
        return routes
    
    def extract_inputs(self, content: str) -> List[Dict[str, str]]:
        """Extract Laravel request inputs."""
        inputs = []
        seen = set()
        
        for pattern, source in self.INPUT_PATTERNS:
            for match in re.finditer(pattern, content):
                name = match.group(1)
                if name not in seen and name not in ['all', 'only', 'except']:
                    seen.add(name)
                    inputs.append({
                        "name": name,
                        "source": source,
                        "line": content[:match.start()].count('\n') + 1
                    })
        
        return inputs
    
    def extract_controller_methods(self, content: str) -> List[Dict[str, Any]]:
        """Extract controller action methods."""
        methods = []
        
        # Pattern for controller methods
        pattern = r"public\s+function\s+(\w+)\s*\([^)]*\)"
        
        for match in re.finditer(pattern, content):
            method_name = match.group(1)
            line = content[:match.start()].count('\n') + 1
            
            # Skip magic methods
            if method_name.startswith('__'):
                continue
            
            methods.append({
                "name": method_name,
                "line": line,
                "type": "controller_action"
            })
        
        return methods
    
    def _extract_controller_action(self, content: str, start_pos: int) -> Tuple[Optional[str], Optional[str]]:
        """Extract controller and action from route definition."""
        # Look ahead for [Controller::class, 'method']
        ahead = content[start_pos:start_pos + 200]
        
        # Pattern: [Controller::class, 'method']
        match = re.search(r"\[\s*(\w+)::class\s*,\s*['\"](\w+)['\"]", ahead)
        if match:
            return match.group(1), match.group(2)
        
        # Pattern: 'Controller@method'
        match = re.search(r"['\"](\w+)@(\w+)['\"]", ahead)
        if match:
            return match.group(1), match.group(2)
        
        return None, None
    
    def _extract_middleware(self, content: str, end_pos: int) -> List[str]:
        """Extract middleware from route definition."""
        # Look for ->middleware() chain
        behind = content[max(0, end_pos - 500):end_pos]
        
        middleware = []
        pattern = r"->middleware\s*\(\s*\[?\s*(['\"][^'\"]+['\"](?:\s*,\s*['\"][^'\"]+['\"])*)"
        
        match = re.search(pattern, behind)
        if match:
            mw_str = match.group(1)
            middleware = re.findall(r"['\"]([^'\"]+)['\"]", mw_str)
        
        return middleware


class SymfonyExtractor:
    """
    Extracts Symfony-specific patterns.
    
    Supports:
    - Route annotations/attributes
    - Controller actions
    - Request handling
    - Form handling
    """
    
    def is_symfony_file(self, content: str) -> bool:
        """Check if file uses Symfony patterns."""
        indicators = [
            "use Symfony\\",
            "extends AbstractController",
            "#[Route(",
            "@Route(",
            "use Doctrine\\",
        ]
        return any(ind in content for ind in indicators)
    
    def extract_routes(self, content: str) -> List[SymfonyRoute]:
        """Extract Symfony route definitions from annotations/attributes."""
        routes = []
        
        # PHP 8 Attribute style: #[Route('/path', name: 'route_name', methods: ['GET'])]
        attr_pattern = r"#\[Route\s*\(\s*['\"]([^'\"]+)['\"](?:[^]]*name\s*[:=]\s*['\"]([^'\"]+)['\"])?(?:[^]]*methods\s*[:=]\s*\[([^\]]+)\])?"
        
        for match in re.finditer(attr_pattern, content):
            path = match.group(1)
            name = match.group(2) or ""
            methods_str = match.group(3) or "'GET'"
            methods = re.findall(r"['\"](\w+)['\"]", methods_str)
            line = content[:match.start()].count('\n') + 1
            
            # Find controller method
            controller = self._find_following_method(content, match.end())
            
            routes.append(SymfonyRoute(
                name=name,
                path=path,
                controller=controller,
                methods=methods or ["GET"],
                line=line
            ))
        
        # Annotation style: @Route("/path")
        annot_pattern = r"@Route\s*\(\s*['\"]([^'\"]+)['\"]"
        for match in re.finditer(annot_pattern, content):
            path = match.group(1)
            line = content[:match.start()].count('\n') + 1
            controller = self._find_following_method(content, match.end())
            
            routes.append(SymfonyRoute(
                name="",
                path=path,
                controller=controller,
                methods=["GET"],
                line=line
            ))
        
        return routes
    
    def extract_inputs(self, content: str) -> List[Dict[str, str]]:
        """Extract Symfony Request inputs."""
        inputs = []
        seen = set()
        
        patterns = [
            (r"\$request->query->get\s*\(\s*['\"](\w+)['\"]", "query"),
            (r"\$request->request->get\s*\(\s*['\"](\w+)['\"]", "body"),
            (r"\$request->cookies->get\s*\(\s*['\"](\w+)['\"]", "cookie"),
            (r"\$request->headers->get\s*\(\s*['\"](\w+)['\"]", "header"),
            (r"\$request->files->get\s*\(\s*['\"](\w+)['\"]", "file"),
            (r"\$request->get\s*\(\s*['\"](\w+)['\"]", "unknown"),
        ]
        
        for pattern, source in patterns:
            for match in re.finditer(pattern, content):
                name = match.group(1)
                if name not in seen:
                    seen.add(name)
                    inputs.append({
                        "name": name,
                        "source": source,
                        "line": content[:match.start()].count('\n') + 1
                    })
        
        return inputs
    
    def _find_following_method(self, content: str, start_pos: int) -> str:
        """Find the method name following a route annotation."""
        ahead = content[start_pos:start_pos + 300]
        match = re.search(r"public\s+function\s+(\w+)", ahead)
        return match.group(1) if match else ""


class PHPFrameworkDetector:
    """Detects and extracts from PHP frameworks."""
    
    def __init__(self):
        self.laravel = LaravelExtractor()
        self.symfony = SymfonyExtractor()
    
    def detect_framework(self, content: str) -> Optional[str]:
        """Detect which PHP framework is being used."""
        if self.laravel.is_laravel_file(content):
            return "laravel"
        if self.symfony.is_symfony_file(content):
            return "symfony"
        return None
    
    def extract_all(self, content: str, file_path: str) -> Dict[str, Any]:
        """Extract all framework-specific information."""
        framework = self.detect_framework(content)
        
        result = {
            "framework": framework,
            "routes": [],
            "inputs": [],
            "sinks": [],
            "methods": []
        }
        
        if framework == "laravel":
            result["routes"] = [
                {
                    "method": r.method,
                    "path": r.path,
                    "controller": r.controller,
                    "action": r.action,
                    "middleware": r.middleware,
                    "line": r.line
                }
                for r in self.laravel.extract_routes(content)
            ]
            result["inputs"] = self.laravel.extract_inputs(content)
            result["methods"] = self.laravel.extract_controller_methods(content)
        
        elif framework == "symfony":
            result["routes"] = [
                {
                    "name": r.name,
                    "path": r.path,
                    "controller": r.controller,
                    "methods": r.methods,
                    "line": r.line
                }
                for r in self.symfony.extract_routes(content)
            ]
            result["inputs"] = self.symfony.extract_inputs(content)
        
        # Extract PHP sinks (common to all)
        result["sinks"] = self._extract_php_sinks(content)
        
        return result
    
    def _extract_php_sinks(self, content: str) -> List[Dict[str, Any]]:
        """Extract PHP dangerous function calls."""
        sinks = []
        seen = set()
        
        for sink_name, (vuln_type, severity) in PHP_DANGEROUS_SINKS.items():
            # Skip multi-word patterns for simple search
            if "::" in sink_name:
                continue
            
            pattern = rf"\b{re.escape(sink_name)}\s*\("
            for match in re.finditer(pattern, content):
                line = content[:match.start()].count('\n') + 1
                key = (sink_name, line)
                
                if key not in seen:
                    seen.add(key)
                    sinks.append({
                        "name": sink_name,
                        "vulnerability_type": vuln_type,
                        "severity": severity,
                        "line": line
                    })
        
        return sinks
