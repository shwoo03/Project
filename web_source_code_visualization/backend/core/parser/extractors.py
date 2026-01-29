"""
Shared extraction utilities for Python parser.
These functions are used by both parse() and scan_symbols() methods.
"""

from typing import List, Dict, Set
import re
import os

# ============================================
# Constants
# ============================================

SANITIZER_FUNCTIONS: Set[str] = {
    "bleach.clean",
    "markupsafe.escape",
    "html.escape",
    "flask.escape",
    "werkzeug.utils.escape",
    "cgi.escape",
    "urllib.parse.quote",
    "urllib.parse.quote_plus",
}

SANITIZER_BASE_NAMES: Set[str] = {
    "escape",
    "sanitize",
}

# ============================================
# Node Text Helper
# ============================================

def get_node_text(node) -> str:
    """Extract text from tree-sitter node."""
    return node.text.decode('utf-8')

# ============================================
# Sanitizer Detection
# ============================================

def is_sanitizer(func_name: str) -> bool:
    """Check if function name is a known sanitizer."""
    lowered = func_name.lower()
    if lowered in SANITIZER_FUNCTIONS:
        return True
    base = lowered.split(".")[-1]
    return base in SANITIZER_BASE_NAMES

def extract_sanitizers(node) -> List[Dict]:
    """Extract sanitizer function calls from AST node."""
    sanitizers = []
    if node.type == 'call':
        func_node = node.child_by_field_name('function')
        if func_node:
            func_name = get_node_text(func_node)
            if is_sanitizer(func_name):
                args_list = []
                args_node = node.child_by_field_name('arguments')
                if args_node:
                    for child in args_node.children:
                        if child.is_named:
                            args_list.append(get_node_text(child))
                sanitizers.append({
                    "name": func_name,
                    "args": args_list,
                    "line": node.start_point.row + 1
                })

    for child in node.children:
        sanitizers.extend(extract_sanitizers(child))
    return sanitizers

# ============================================
# Path Parameter Extraction
# ============================================

def extract_path_params(path_text: str) -> List[str]:
    """
    Extract path parameters from route path.
    Flask: <id>, <int:id>
    FastAPI: {id}
    """
    flask_params = re.findall(r"<(?:[^:<>]+:)?([^<>]+)>", path_text)
    fastapi_params = re.findall(r"\{([^}]+)\}", path_text)
    return flask_params + fastapi_params

# ============================================
# Template Analysis
# ============================================

def extract_template_usage(template_path: str) -> List[Dict]:
    """
    Extract variable usage from Jinja2 template file.
    Looks for {{ variable }} patterns.
    """
    usage = []
    try:
        with open(template_path, "r", encoding="utf-8", errors="ignore") as f:
            lines = f.readlines()
    except Exception:
        return usage

    for idx, line in enumerate(lines, start=1):
        for match in re.finditer(r"{{([^}]+)}}", line):
            expr = match.group(1).strip()
            expr = expr.split("|")[0].strip()
            var_match = re.match(r"[A-Za-z_][A-Za-z0-9_]*", expr)
            if var_match:
                usage.append({
                    "name": var_match.group(0),
                    "line": idx,
                    "snippet": line.strip()
                })
    return usage

def find_template_path(base_dir: str, template_name: str) -> str | None:
    """
    Find template file path by searching common locations.
    Returns None if not found.
    """
    candidates = [
        os.path.join(base_dir, "templates", template_name),
        os.path.join(os.path.dirname(base_dir), "templates", template_name)
    ]
    
    for c in candidates:
        if os.path.exists(c):
            return c
    return None

# ============================================
# Input Detection
# ============================================

INPUT_PATTERNS = {
    "request.args.get": "GET",
    "request.form.get": "POST",
    "request.cookies.get": "COOKIE",
    "request.headers.get": "HEADER",
    "request.files.get": "FILE",
    "request.view_args.get": "PATH",
    "request.json.get": "BODY_JSON",
    "request.get_json": "BODY_JSON",
    "request.get_data": "BODY_RAW",
}

SUBSCRIPT_PATTERNS = {
    "request.args": "GET",
    "request.form": "POST",
    "request.cookies": "COOKIE",
    "request.headers": "HEADER",
    "request.files": "FILE",
    "request.view_args": "PATH",
    "request.json": "BODY_JSON",
    "request.data": "BODY_RAW",
}

def get_input_source_from_call(func_text: str) -> str | None:
    """Determine input source type from function call text."""
    for pattern, source in INPUT_PATTERNS.items():
        if pattern in func_text:
            return source
    return None

def get_input_source_from_subscript(value_text: str) -> str | None:
    """Determine input source type from subscript access."""
    return SUBSCRIPT_PATTERNS.get(value_text)
