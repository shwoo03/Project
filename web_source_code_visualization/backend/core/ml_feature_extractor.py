"""
ML Feature Extractor for Vulnerability Detection.

This module extracts features from code for machine learning-based vulnerability detection.
Features are extracted from AST, data flow, control flow, and semantic information.

Key feature categories:
1. Code Structure Features (AST-based)
2. Semantic Features (type info, symbol relations)
3. Context Features (call context, data flow)
4. Historical Features (pattern matching)
"""

from typing import List, Dict, Set, Optional, Any, Tuple
from dataclasses import dataclass, field
from enum import Enum
import re
import hashlib
import numpy as np
from collections import Counter


class FeatureCategory(Enum):
    """Categories of features for ML model."""
    STRUCTURAL = "structural"      # AST-based features
    SEMANTIC = "semantic"          # Type and symbol features
    CONTEXTUAL = "contextual"      # Call context, data flow
    PATTERN = "pattern"            # Known vulnerability patterns
    HISTORICAL = "historical"      # Based on past vulnerabilities


@dataclass
class CodeContext:
    """Context information for a code snippet."""
    file_path: str
    function_name: Optional[str] = None
    class_name: Optional[str] = None
    line_start: int = 0
    line_end: int = 0
    language: str = "python"
    framework: Optional[str] = None
    
    # AST information
    node_type: Optional[str] = None
    parent_type: Optional[str] = None
    depth: int = 0
    
    # Call chain context
    call_chain: List[str] = field(default_factory=list)
    caller_count: int = 0
    callee_count: int = 0


@dataclass 
class VulnerabilityFeatures:
    """
    Feature vector for vulnerability detection.
    Contains all extracted features for a potential vulnerability.
    """
    # Identification
    feature_id: str
    vulnerability_type: str
    source_info: Dict[str, Any] = field(default_factory=dict)
    
    # Structural features (AST-based)
    structural: Dict[str, float] = field(default_factory=dict)
    
    # Semantic features
    semantic: Dict[str, float] = field(default_factory=dict)
    
    # Contextual features
    contextual: Dict[str, float] = field(default_factory=dict)
    
    # Pattern matching features
    pattern: Dict[str, float] = field(default_factory=dict)
    
    # Combined feature vector
    feature_vector: Optional[np.ndarray] = None
    
    # Original taint flow data
    taint_flow: Optional[Dict[str, Any]] = None
    
    def to_vector(self) -> np.ndarray:
        """Convert all features to a single numpy vector."""
        if self.feature_vector is not None:
            return self.feature_vector
            
        all_features = []
        all_features.extend(self.structural.values())
        all_features.extend(self.semantic.values())
        all_features.extend(self.contextual.values())
        all_features.extend(self.pattern.values())
        
        self.feature_vector = np.array(all_features, dtype=np.float32)
        return self.feature_vector
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "feature_id": self.feature_id,
            "vulnerability_type": self.vulnerability_type,
            "source_info": self.source_info,
            "structural": self.structural,
            "semantic": self.semantic,
            "contextual": self.contextual,
            "pattern": self.pattern,
            "feature_count": len(self.to_vector())
        }


class MLFeatureExtractor:
    """
    Extracts ML features from code and taint analysis results.
    
    Features are designed to help ML models distinguish between:
    - True vulnerabilities and false positives
    - Different vulnerability severities
    - Exploitability levels
    """
    
    # Known dangerous patterns by vulnerability type
    DANGEROUS_PATTERNS = {
        "sql_injection": [
            r"execute\s*\([^)]*\+",
            r"execute\s*\(.*%s",
            r"execute\s*\(.*\.format\(",
            r"execute\s*\(.*f['\"]",
            r"cursor\s*\.\s*execute\s*\(",
            r"raw\s*\(",
            r"SELECT.*WHERE.*=.*\+",
            r"INSERT.*VALUES.*\+",
        ],
        "xss": [
            r"innerHTML\s*=",
            r"document\.write\(",
            r"\.html\([^)]*\+",
            r"render_template_string\(",
            r"Markup\(",
            r"safe\s*\|",
            r"dangerouslySetInnerHTML",
        ],
        "command_injection": [
            r"os\.system\(",
            r"subprocess\.(call|run|Popen)",
            r"shell\s*=\s*True",
            r"eval\(",
            r"exec\(",
            r"`[^`]*\$",
            r"child_process",
        ],
        "path_traversal": [
            r"\.\.\/",
            r"\.\.\\\\",
            r"open\([^)]*\+",
            r"file_get_contents\(",
            r"include\s*\(",
            r"require\s*\(",
        ],
        "ssrf": [
            r"requests\.(get|post|put)\(",
            r"urllib\.request",
            r"fetch\(",
            r"axios\.",
            r"http\.get\(",
            r"curl_exec\(",
        ],
    }
    
    # Sanitizer patterns that reduce risk
    SANITIZER_PATTERNS = {
        "sql_injection": [
            r"parameterized",
            r"\?\s*,",
            r"prepared",
            r"bind_param",
            r"placeholders",
        ],
        "xss": [
            r"escape\(",
            r"html\.escape",
            r"htmlspecialchars",
            r"sanitize",
            r"encodeURIComponent",
            r"DOMPurify",
        ],
        "command_injection": [
            r"shlex\.quote",
            r"escapeshellarg",
            r"subprocess.*\[",  # Using list instead of string
        ],
        "path_traversal": [
            r"os\.path\.basename",
            r"realpath",
            r"secure_filename",
            r"Path\(.*\)\.resolve\(\)",
        ],
    }
    
    # Framework-specific context
    FRAMEWORK_INDICATORS = {
        "flask": ["from flask", "@app.route", "request.args", "request.form"],
        "django": ["from django", "HttpRequest", "request.GET", "request.POST"],
        "fastapi": ["from fastapi", "@app.get", "@app.post", "Query(", "Body("],
        "express": ["require('express')", "req.query", "req.body", "req.params"],
        "spring": ["@RequestMapping", "@GetMapping", "@PostMapping", "@RequestParam"],
        "laravel": ["Request $request", "->input(", "->get("],
    }
    
    def __init__(self):
        self.feature_names: List[str] = []
        self._initialize_feature_names()
    
    def _initialize_feature_names(self):
        """Initialize the list of feature names for the model."""
        # Structural features
        self.feature_names.extend([
            "ast_depth",
            "node_count",
            "function_complexity",
            "nesting_level",
            "control_flow_branches",
            "loop_count",
            "try_catch_present",
            "has_conditional",
        ])
        
        # Semantic features
        self.feature_names.extend([
            "is_typed",
            "has_type_annotation",
            "uses_raw_input",
            "uses_framework_input",
            "variable_reused",
            "crosses_function_boundary",
            "parameter_count",
            "return_type_known",
        ])
        
        # Contextual features
        self.feature_names.extend([
            "call_chain_length",
            "caller_count",
            "callee_count",
            "is_entry_point",
            "is_api_endpoint",
            "distance_source_sink",
            "data_transformations",
            "sanitizer_present",
        ])
        
        # Pattern features
        self.feature_names.extend([
            "dangerous_pattern_count",
            "sanitizer_pattern_count",
            "string_concat_used",
            "format_string_used",
            "direct_user_input",
            "validated_input",
            "framework_protection",
            "known_vuln_pattern",
        ])
    
    def extract_features(
        self,
        taint_flow: Dict[str, Any],
        code_content: str,
        context: CodeContext,
        symbol_table: Optional[Dict] = None,
        call_graph: Optional[Dict] = None
    ) -> VulnerabilityFeatures:
        """
        Extract all features for a potential vulnerability.
        
        Args:
            taint_flow: Taint flow data from taint analyzer
            code_content: Source code content
            context: Code context information
            symbol_table: Symbol table for semantic analysis
            call_graph: Call graph for context analysis
            
        Returns:
            VulnerabilityFeatures with all extracted features
        """
        # Generate unique feature ID
        feature_id = self._generate_feature_id(taint_flow, context)
        
        # Determine vulnerability type
        vuln_type = taint_flow.get("vulnerability_type", "unknown")
        
        # Extract features by category
        structural = self._extract_structural_features(code_content, context)
        semantic = self._extract_semantic_features(
            code_content, context, symbol_table, taint_flow
        )
        contextual = self._extract_contextual_features(
            taint_flow, context, call_graph
        )
        pattern = self._extract_pattern_features(
            code_content, vuln_type, context
        )
        
        # Create features object
        features = VulnerabilityFeatures(
            feature_id=feature_id,
            vulnerability_type=vuln_type,
            source_info={
                "file": context.file_path,
                "function": context.function_name,
                "line_start": context.line_start,
                "line_end": context.line_end,
            },
            structural=structural,
            semantic=semantic,
            contextual=contextual,
            pattern=pattern,
            taint_flow=taint_flow
        )
        
        return features
    
    def _generate_feature_id(
        self, 
        taint_flow: Dict[str, Any], 
        context: CodeContext
    ) -> str:
        """Generate unique ID for a feature set."""
        id_string = f"{context.file_path}:{context.line_start}:{taint_flow.get('sink_name', '')}"
        return hashlib.md5(id_string.encode()).hexdigest()[:12]
    
    def _extract_structural_features(
        self,
        code: str,
        context: CodeContext
    ) -> Dict[str, float]:
        """Extract AST-based structural features."""
        features = {}
        
        lines = code.split('\n')
        
        # AST depth (approximate from indentation)
        indents = [len(line) - len(line.lstrip()) for line in lines if line.strip()]
        features["ast_depth"] = float(max(indents) / 4) if indents else 0.0
        
        # Node count (approximate from keywords)
        keywords = ['def', 'class', 'if', 'else', 'elif', 'for', 'while', 
                    'try', 'except', 'with', 'return', 'yield', 'import']
        features["node_count"] = float(sum(
            1 for line in lines 
            for kw in keywords 
            if re.search(rf'\b{kw}\b', line)
        ))
        
        # Function complexity (cyclomatic complexity approximation)
        decision_points = sum(1 for line in lines if re.search(
            r'\b(if|elif|for|while|and|or|except)\b', line
        ))
        features["function_complexity"] = float(decision_points + 1)
        
        # Nesting level
        features["nesting_level"] = float(context.depth)
        
        # Control flow branches
        features["control_flow_branches"] = float(sum(
            1 for line in lines if re.search(r'\b(if|elif|else)\b', line)
        ))
        
        # Loop count
        features["loop_count"] = float(sum(
            1 for line in lines if re.search(r'\b(for|while)\b', line)
        ))
        
        # Try-catch present
        features["try_catch_present"] = 1.0 if re.search(
            r'\b(try|catch|except)\b', code
        ) else 0.0
        
        # Has conditional
        features["has_conditional"] = 1.0 if re.search(
            r'\b(if|else|elif|switch|case)\b', code
        ) else 0.0
        
        return features
    
    def _extract_semantic_features(
        self,
        code: str,
        context: CodeContext,
        symbol_table: Optional[Dict],
        taint_flow: Dict[str, Any]
    ) -> Dict[str, float]:
        """Extract semantic features from type info and symbols."""
        features = {}
        
        # Type annotations
        features["is_typed"] = 1.0 if re.search(r':\s*(str|int|float|bool|List|Dict)', code) else 0.0
        features["has_type_annotation"] = 1.0 if re.search(r'->\s*\w+', code) else 0.0
        
        # Input source type
        raw_input_patterns = [r'input\(', r'raw_input\(', r'sys\.argv', r'sys\.stdin']
        features["uses_raw_input"] = 1.0 if any(
            re.search(p, code) for p in raw_input_patterns
        ) else 0.0
        
        framework_patterns = [
            r'request\.(args|form|data|json|cookies|headers)',
            r'req\.(query|body|params)',
            r'\$_(GET|POST|REQUEST|COOKIE)',
            r'@RequestParam',
        ]
        features["uses_framework_input"] = 1.0 if any(
            re.search(p, code) for p in framework_patterns
        ) else 0.0
        
        # Variable reuse
        source_name = taint_flow.get("source_name", "")
        if source_name:
            occurrences = len(re.findall(rf'\b{re.escape(source_name)}\b', code))
            features["variable_reused"] = min(float(occurrences) / 5.0, 1.0)
        else:
            features["variable_reused"] = 0.0
        
        # Cross function boundary
        features["crosses_function_boundary"] = 1.0 if len(
            taint_flow.get("call_chain", [])
        ) > 1 else 0.0
        
        # Parameter count
        func_match = re.search(r'def\s+\w+\s*\(([^)]*)\)', code)
        if func_match:
            params = [p.strip() for p in func_match.group(1).split(',') if p.strip()]
            features["parameter_count"] = float(len(params)) / 10.0
        else:
            features["parameter_count"] = 0.0
        
        # Return type known
        features["return_type_known"] = 1.0 if re.search(r'\)\s*->\s*\w+', code) else 0.0
        
        return features
    
    def _extract_contextual_features(
        self,
        taint_flow: Dict[str, Any],
        context: CodeContext,
        call_graph: Optional[Dict]
    ) -> Dict[str, float]:
        """Extract features from call context and data flow."""
        features = {}
        
        # Call chain length
        call_chain = taint_flow.get("call_chain", context.call_chain)
        features["call_chain_length"] = min(float(len(call_chain)) / 10.0, 1.0)
        
        # Caller/callee counts
        features["caller_count"] = min(float(context.caller_count) / 20.0, 1.0)
        features["callee_count"] = min(float(context.callee_count) / 20.0, 1.0)
        
        # Is entry point (route handler, main, etc.)
        entry_patterns = [
            r'@app\.(route|get|post|put|delete)',
            r'@router\.',
            r'def\s+main\s*\(',
            r'if\s+__name__.*__main__',
            r'@RequestMapping',
            r'@GetMapping',
        ]
        is_entry = any(
            re.search(p, str(taint_flow.get("source_context", "")))
            for p in entry_patterns
        )
        features["is_entry_point"] = 1.0 if is_entry else 0.0
        
        # Is API endpoint
        features["is_api_endpoint"] = 1.0 if context.function_name and any(
            pattern in str(taint_flow.get("source_context", ""))
            for pattern in ["route", "endpoint", "api", "Request"]
        ) else 0.0
        
        # Distance between source and sink
        source_line = taint_flow.get("source_line", 0)
        sink_line = taint_flow.get("sink_line", 0)
        distance = abs(sink_line - source_line)
        features["distance_source_sink"] = min(float(distance) / 100.0, 1.0)
        
        # Data transformations count
        path = taint_flow.get("path", [])
        features["data_transformations"] = min(float(len(path)) / 10.0, 1.0)
        
        # Sanitizer present in flow
        features["sanitizer_present"] = 1.0 if taint_flow.get("sanitized", False) else 0.0
        
        return features
    
    def _extract_pattern_features(
        self,
        code: str,
        vuln_type: str,
        context: CodeContext
    ) -> Dict[str, float]:
        """Extract features from pattern matching."""
        features = {}
        
        # Normalize vulnerability type
        vuln_key = vuln_type.lower().replace("-", "_").replace(" ", "_")
        
        # Dangerous pattern count
        dangerous_patterns = self.DANGEROUS_PATTERNS.get(vuln_key, [])
        dangerous_count = sum(
            1 for p in dangerous_patterns if re.search(p, code, re.IGNORECASE)
        )
        features["dangerous_pattern_count"] = min(float(dangerous_count) / 5.0, 1.0)
        
        # Sanitizer pattern count
        sanitizer_patterns = self.SANITIZER_PATTERNS.get(vuln_key, [])
        sanitizer_count = sum(
            1 for p in sanitizer_patterns if re.search(p, code, re.IGNORECASE)
        )
        features["sanitizer_pattern_count"] = min(float(sanitizer_count) / 3.0, 1.0)
        
        # String concatenation used
        features["string_concat_used"] = 1.0 if re.search(
            r'[\'"]\s*\+|\+\s*[\'"]|\.format\(|f[\'"]', code
        ) else 0.0
        
        # Format string used
        features["format_string_used"] = 1.0 if re.search(
            r'%s|%d|\.format\(|f[\'"].*\{', code
        ) else 0.0
        
        # Direct user input (no intermediate processing)
        direct_input_patterns = [
            r'request\.\w+\[[\'"][^\'"]+[\'"]\]',
            r'request\.\w+\.get\([\'"]',
            r'\$_(GET|POST)\[[\'"]',
            r'req\.(query|body|params)\.',
        ]
        features["direct_user_input"] = 1.0 if any(
            re.search(p, code) for p in direct_input_patterns
        ) else 0.0
        
        # Validated input (has validation/check nearby)
        validation_patterns = [
            r'if\s+\w+\s*(==|!=|in|not in)',
            r'validate',
            r'check',
            r'verify',
            r'assert',
            r'isinstance\(',
            r'type\(',
        ]
        features["validated_input"] = 1.0 if any(
            re.search(p, code, re.IGNORECASE) for p in validation_patterns
        ) else 0.0
        
        # Framework protection
        framework_protection = [
            r'csrf_token',
            r'@login_required',
            r'@authenticated',
            r'@permission_required',
            r'sanitize',
            r'escape',
        ]
        features["framework_protection"] = 1.0 if any(
            re.search(p, code, re.IGNORECASE) for p in framework_protection
        ) else 0.0
        
        # Known vulnerability pattern (high confidence dangerous code)
        known_dangerous = [
            r'eval\s*\(\s*request\.',
            r'exec\s*\(\s*request\.',
            r'os\.system\s*\(\s*request\.',
            r'subprocess.*shell\s*=\s*True.*request\.',
            r'cursor\.execute\s*\([^,]*\+',
            r'innerHTML\s*=\s*[^;]*\+',
        ]
        features["known_vuln_pattern"] = 1.0 if any(
            re.search(p, code, re.IGNORECASE) for p in known_dangerous
        ) else 0.0
        
        return features
    
    def get_feature_names(self) -> List[str]:
        """Get ordered list of feature names."""
        return self.feature_names
    
    def get_feature_count(self) -> int:
        """Get total number of features."""
        return len(self.feature_names)
    
    def batch_extract(
        self,
        taint_flows: List[Dict[str, Any]],
        code_contents: Dict[str, str],
        contexts: Dict[str, CodeContext]
    ) -> List[VulnerabilityFeatures]:
        """
        Batch extract features for multiple taint flows.
        
        Args:
            taint_flows: List of taint flow data
            code_contents: Map of file paths to code content
            contexts: Map of identifiers to code contexts
            
        Returns:
            List of VulnerabilityFeatures
        """
        features_list = []
        
        for flow in taint_flows:
            file_path = flow.get("file_path", "")
            code = code_contents.get(file_path, "")
            
            # Create context if not provided
            context_key = f"{file_path}:{flow.get('source_line', 0)}"
            context = contexts.get(context_key, CodeContext(file_path=file_path))
            
            features = self.extract_features(flow, code, context)
            features_list.append(features)
        
        return features_list


# Singleton instance
_feature_extractor = None

def get_feature_extractor() -> MLFeatureExtractor:
    """Get singleton MLFeatureExtractor instance."""
    global _feature_extractor
    if _feature_extractor is None:
        _feature_extractor = MLFeatureExtractor()
    return _feature_extractor
