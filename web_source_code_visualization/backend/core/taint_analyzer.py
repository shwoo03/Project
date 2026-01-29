"""
Taint Analysis Module for Security Flow Tracking.

This module tracks the flow of user-controlled data (tainted data) through the application,
from sources (user inputs) to sinks (dangerous functions).

Key concepts:
- Source: Where untrusted data enters (request.args, form, cookies, etc.)
- Sink: Dangerous functions that can cause security issues (os.system, eval, etc.)
- Sanitizer: Functions that clean/escape data (html.escape, etc.)
- Taint: The "dirty" state that flows from sources to sinks
"""

from typing import List, Dict, Set, Optional, Any, Tuple
from dataclasses import dataclass, field
from enum import Enum
import re


class TaintType(Enum):
    """Types of security-relevant taint."""
    XSS = "xss"                    # Cross-Site Scripting
    SQLI = "sql_injection"         # SQL Injection
    CMDI = "command_injection"     # Command Injection
    PATH = "path_traversal"        # Path Traversal
    SSTI = "template_injection"    # Server-Side Template Injection
    CODE = "code_injection"        # Code Injection (eval, exec)
    SSRF = "ssrf"                  # Server-Side Request Forgery
    OPEN_REDIRECT = "open_redirect" # Open Redirect
    GENERAL = "general"            # General untrusted input


@dataclass
class TaintSource:
    """Represents a source of tainted data."""
    name: str                      # Variable or parameter name
    source_type: str               # GET, POST, COOKIE, HEADER, etc.
    line: int                      # Line number
    file_path: str                 # File where source is located
    taint_types: Set[TaintType] = field(default_factory=lambda: {TaintType.GENERAL})
    
    def __hash__(self):
        return hash((self.name, self.line, self.file_path))


@dataclass
class TaintSink:
    """Represents a dangerous sink function."""
    name: str                      # Function name (e.g., "os.system")
    category: TaintType            # Type of vulnerability
    line: int                      # Line number
    file_path: str                 # File where sink is located
    args: List[str] = field(default_factory=list)  # Arguments passed to sink
    severity: str = "HIGH"         # HIGH, MEDIUM, LOW
    
    def __hash__(self):
        return hash((self.name, self.line, self.file_path))


@dataclass
class TaintFlow:
    """Represents a flow from source to sink."""
    source: TaintSource
    sink: TaintSink
    path: List[str] = field(default_factory=list)  # Variable flow path
    sanitized: bool = False        # Whether sanitizer was applied
    sanitizer_name: Optional[str] = None  # Name of sanitizer if applied
    confidence: float = 1.0        # Confidence level (0.0 - 1.0)


# ============================================
# Sink Definitions by Category
# ============================================

DANGEROUS_SINKS: Dict[str, Tuple[TaintType, str]] = {
    # Command Injection (HIGH)
    "os.system": (TaintType.CMDI, "HIGH"),
    "os.popen": (TaintType.CMDI, "HIGH"),
    "os.spawn": (TaintType.CMDI, "HIGH"),
    "os.spawnl": (TaintType.CMDI, "HIGH"),
    "os.spawnle": (TaintType.CMDI, "HIGH"),
    "os.spawnlp": (TaintType.CMDI, "HIGH"),
    "os.spawnlpe": (TaintType.CMDI, "HIGH"),
    "os.spawnv": (TaintType.CMDI, "HIGH"),
    "os.spawnve": (TaintType.CMDI, "HIGH"),
    "os.spawnvp": (TaintType.CMDI, "HIGH"),
    "os.spawnvpe": (TaintType.CMDI, "HIGH"),
    "subprocess.call": (TaintType.CMDI, "HIGH"),
    "subprocess.run": (TaintType.CMDI, "HIGH"),
    "subprocess.Popen": (TaintType.CMDI, "HIGH"),
    "subprocess.check_output": (TaintType.CMDI, "HIGH"),
    "subprocess.check_call": (TaintType.CMDI, "HIGH"),
    "commands.getoutput": (TaintType.CMDI, "HIGH"),
    "commands.getstatusoutput": (TaintType.CMDI, "HIGH"),
    
    # Code Injection (CRITICAL)
    "eval": (TaintType.CODE, "HIGH"),
    "exec": (TaintType.CODE, "HIGH"),
    "compile": (TaintType.CODE, "HIGH"),
    "execfile": (TaintType.CODE, "HIGH"),
    "__import__": (TaintType.CODE, "MEDIUM"),
    
    # SQL Injection (HIGH)
    "cursor.execute": (TaintType.SQLI, "HIGH"),
    "db.execute": (TaintType.SQLI, "HIGH"),
    "connection.execute": (TaintType.SQLI, "HIGH"),
    "engine.execute": (TaintType.SQLI, "HIGH"),
    "session.execute": (TaintType.SQLI, "HIGH"),
    "raw": (TaintType.SQLI, "MEDIUM"),  # Django raw SQL
    
    # Path Traversal (HIGH)
    "open": (TaintType.PATH, "MEDIUM"),
    "os.path.join": (TaintType.PATH, "MEDIUM"),
    "os.makedirs": (TaintType.PATH, "MEDIUM"),
    "os.remove": (TaintType.PATH, "HIGH"),
    "os.unlink": (TaintType.PATH, "HIGH"),
    "os.rmdir": (TaintType.PATH, "HIGH"),
    "shutil.rmtree": (TaintType.PATH, "HIGH"),
    "shutil.copy": (TaintType.PATH, "MEDIUM"),
    "shutil.move": (TaintType.PATH, "MEDIUM"),
    "send_file": (TaintType.PATH, "HIGH"),  # Flask
    "send_from_directory": (TaintType.PATH, "MEDIUM"),  # Flask
    
    # Template Injection (HIGH)
    "render_template_string": (TaintType.SSTI, "HIGH"),
    "Template": (TaintType.SSTI, "MEDIUM"),  # Jinja2 Template()
    "Markup": (TaintType.XSS, "MEDIUM"),     # Flask Markup (bypasses escaping)
    
    # XSS (when using unsafe methods)
    "Response": (TaintType.XSS, "LOW"),
    "make_response": (TaintType.XSS, "LOW"),
    "jsonify": (TaintType.XSS, "LOW"),
    
    # SSRF
    "requests.get": (TaintType.SSRF, "MEDIUM"),
    "requests.post": (TaintType.SSRF, "MEDIUM"),
    "requests.put": (TaintType.SSRF, "MEDIUM"),
    "requests.delete": (TaintType.SSRF, "MEDIUM"),
    "urllib.request.urlopen": (TaintType.SSRF, "MEDIUM"),
    "urllib.urlopen": (TaintType.SSRF, "MEDIUM"),
    "httpx.get": (TaintType.SSRF, "MEDIUM"),
    "httpx.post": (TaintType.SSRF, "MEDIUM"),
    
    # Open Redirect
    "redirect": (TaintType.OPEN_REDIRECT, "MEDIUM"),
    "RedirectResponse": (TaintType.OPEN_REDIRECT, "MEDIUM"),
}

# Sinks that are dangerous only with shell=True
SHELL_SINKS = {
    "subprocess.run",
    "subprocess.call",
    "subprocess.Popen",
    "subprocess.check_output",
    "subprocess.check_call",
}

# Sanitizers by taint type
SANITIZERS_BY_TYPE: Dict[TaintType, Set[str]] = {
    TaintType.XSS: {
        "html.escape", "markupsafe.escape", "flask.escape",
        "bleach.clean", "cgi.escape", "escape",
    },
    TaintType.SQLI: {
        "parameterized",  # Using parameterized queries
        "quote", "escape_string",
    },
    TaintType.CMDI: {
        "shlex.quote", "shlex.split", "pipes.quote",
    },
    TaintType.PATH: {
        "os.path.basename", "secure_filename",  # Werkzeug
        "os.path.normpath",
    },
    TaintType.SSTI: {
        "html.escape", "markupsafe.escape",
    },
}


class TaintAnalyzer:
    """
    Analyzes code for taint flow from sources to sinks.
    
    Usage:
        analyzer = TaintAnalyzer()
        analyzer.add_source(TaintSource(...))
        analyzer.add_sink(TaintSink(...))
        analyzer.track_assignment("user_input", "cmd")
        flows = analyzer.analyze()
    """
    
    def __init__(self):
        self.sources: List[TaintSource] = []
        self.sinks: List[TaintSink] = []
        self.sanitizers: List[Dict] = []
        
        # Variable taint tracking: var_name -> TaintSource
        self.tainted_vars: Dict[str, TaintSource] = {}
        
        # Assignment tracking: target -> source_var
        self.assignments: List[Tuple[str, str, int]] = []  # (target, source, line)
        
        # Call tracking for propagation
        self.calls: List[Dict] = []
    
    def add_source(self, source: TaintSource):
        """Register a taint source."""
        self.sources.append(source)
        self.tainted_vars[source.name] = source
    
    def add_sink(self, sink: TaintSink):
        """Register a dangerous sink."""
        self.sinks.append(sink)
    
    def add_sanitizer(self, sanitizer: Dict):
        """Register a sanitizer call."""
        self.sanitizers.append(sanitizer)
    
    def track_assignment(self, target: str, source_expr: str, line: int):
        """Track variable assignment for taint propagation."""
        self.assignments.append((target, source_expr, line))
        
        # Propagate taint if source is tainted
        if source_expr in self.tainted_vars:
            self.tainted_vars[target] = self.tainted_vars[source_expr]
    
    def is_tainted(self, var_name: str) -> bool:
        """Check if a variable is tainted."""
        return var_name in self.tainted_vars
    
    def get_taint_source(self, var_name: str) -> Optional[TaintSource]:
        """Get the original taint source for a variable."""
        return self.tainted_vars.get(var_name)
    
    def _check_sanitized(self, var_name: str, taint_type: TaintType) -> Tuple[bool, Optional[str]]:
        """Check if a variable has been sanitized for a specific taint type."""
        for san in self.sanitizers:
            # Check if this sanitizer was applied to the variable
            if var_name in san.get("args", []) or var_name == san.get("via"):
                san_name = san.get("sanitizer", san.get("name", ""))
                
                # Check if sanitizer is effective for this taint type
                effective_sanitizers = SANITIZERS_BY_TYPE.get(taint_type, set())
                san_base = san_name.split(".")[-1].lower()
                
                if san_name.lower() in effective_sanitizers or san_base in effective_sanitizers:
                    return True, san_name
        
        return False, None
    
    def _extract_identifiers(self, expr: str) -> List[str]:
        """Extract variable identifiers from an expression."""
        # Simple regex to find identifiers
        return re.findall(r'\b([a-zA-Z_][a-zA-Z0-9_]*)\b', expr)
    
    def analyze(self) -> List[TaintFlow]:
        """
        Analyze all registered sources, sinks, and assignments to find taint flows.
        
        Returns:
            List of TaintFlow objects representing vulnerable data flows
        """
        flows = []
        
        for sink in self.sinks:
            # Check each argument to the sink
            for arg in sink.args:
                identifiers = self._extract_identifiers(arg)
                
                for ident in identifiers:
                    source = self.get_taint_source(ident)
                    
                    if source:
                        # Found a tainted variable reaching a sink!
                        sanitized, sanitizer_name = self._check_sanitized(ident, sink.category)
                        
                        # Build the path from source to sink
                        path = self._build_path(source.name, ident)
                        
                        flow = TaintFlow(
                            source=source,
                            sink=sink,
                            path=path,
                            sanitized=sanitized,
                            sanitizer_name=sanitizer_name,
                            confidence=0.5 if sanitized else 1.0
                        )
                        flows.append(flow)
        
        return flows
    
    def _build_path(self, source_var: str, sink_var: str) -> List[str]:
        """Build the variable flow path from source to sink."""
        path = [source_var]
        
        if source_var == sink_var:
            return path
        
        # Simple path building from assignments
        current = source_var
        visited = {source_var}
        
        for _ in range(10):  # Limit iterations
            found_next = False
            for target, source_expr, _ in self.assignments:
                if current in source_expr and target not in visited:
                    path.append(target)
                    visited.add(target)
                    current = target
                    found_next = True
                    
                    if current == sink_var:
                        return path
                    break
            
            if not found_next:
                break
        
        if sink_var not in path:
            path.append(sink_var)
        
        return path
    
    def get_summary(self) -> Dict[str, Any]:
        """Get a summary of the taint analysis."""
        flows = self.analyze()
        
        vulnerable_flows = [f for f in flows if not f.sanitized]
        sanitized_flows = [f for f in flows if f.sanitized]
        
        by_type = {}
        for flow in vulnerable_flows:
            ttype = flow.sink.category.value
            if ttype not in by_type:
                by_type[ttype] = []
            by_type[ttype].append(flow)
        
        return {
            "total_sources": len(self.sources),
            "total_sinks": len(self.sinks),
            "total_flows": len(flows),
            "vulnerable_flows": len(vulnerable_flows),
            "sanitized_flows": len(sanitized_flows),
            "by_vulnerability_type": {k: len(v) for k, v in by_type.items()},
            "flows": flows
        }


def detect_sink(func_name: str) -> Optional[Tuple[TaintType, str]]:
    """
    Check if a function name is a known dangerous sink.
    
    Returns:
        Tuple of (TaintType, severity) if sink, None otherwise
    """
    # Direct match
    if func_name in DANGEROUS_SINKS:
        return DANGEROUS_SINKS[func_name]
    
    # Check base name (e.g., "subprocess.call" -> "call")
    base_name = func_name.split(".")[-1]
    for sink_name, info in DANGEROUS_SINKS.items():
        if sink_name.endswith(f".{base_name}") or sink_name == base_name:
            return info
    
    return None


def is_sink_dangerous_without_shell(func_name: str, args_text: str) -> bool:
    """
    Check if a subprocess call is dangerous (has shell=True).
    """
    if func_name not in SHELL_SINKS:
        return True  # Not a shell sink, always dangerous
    
    # Check for shell=True in arguments
    return "shell=True" in args_text or "shell = True" in args_text
