"""
Inter-Procedural Taint Analysis Module.

This module extends basic taint analysis to track data flow across function calls,
enabling detection of vulnerabilities that span multiple functions.

Key features:
- Function summaries: Tracks which inputs affect which outputs
- Call graph integration: Propagates taint through function calls
- Context-sensitive analysis: Considers call context for precise tracking
- Recursive call handling: Detects and limits analysis of recursive functions
- Configurable depth limits: Prevents infinite analysis loops

Example:
    def get_user_input():
        return request.args.get('id')  # Source

    def process(data):
        return data.upper()

    def execute(cmd):
        os.system(cmd)  # Sink

    # Tracking: get_user_input() → process() → execute()
"""

from typing import List, Dict, Set, Optional, Any, Tuple
from dataclasses import dataclass, field
from enum import Enum
import re
import os

from .taint_analyzer import (
    TaintType, TaintSource, TaintSink, TaintFlow, 
    DANGEROUS_SINKS, SANITIZERS_BY_TYPE, detect_sink
)
from .call_graph_analyzer import CallGraphAnalyzer, FunctionInfo


class PropagationMode(Enum):
    """How taint propagates through a function."""
    DIRECT = "direct"           # Input directly becomes output
    TRANSFORMED = "transformed"  # Input is transformed but still tainted
    SANITIZED = "sanitized"      # Input is sanitized (no longer tainted)
    BLOCKED = "blocked"          # Taint does not propagate


@dataclass
class ParameterTaint:
    """Represents taint information for a function parameter."""
    name: str
    index: int
    taint_types: Set[TaintType] = field(default_factory=lambda: {TaintType.GENERAL})
    is_tainted: bool = True


@dataclass
class TaintSummary:
    """
    Summary of how a function propagates taint from inputs to outputs.
    
    This captures the taint behavior of a function without analyzing its body
    every time it's called.
    """
    function_name: str
    qualified_name: str
    file_path: str
    
    # Parameter → Output mappings
    # Key: parameter index, Value: list of (output_type, propagation_mode)
    param_to_output: Dict[int, List[Tuple[str, PropagationMode]]] = field(default_factory=dict)
    
    # Which parameters reach which sinks
    param_to_sinks: Dict[int, List[TaintSink]] = field(default_factory=dict)
    
    # Return value taint: which parameters affect the return value
    return_tainted_by: Set[int] = field(default_factory=set)
    
    # Does this function itself introduce new taint sources?
    introduces_sources: List[TaintSource] = field(default_factory=list)
    
    # Does this function contain sinks?
    contains_sinks: List[TaintSink] = field(default_factory=list)
    
    # Is this function a sanitizer for certain taint types?
    sanitizes: Set[TaintType] = field(default_factory=set)
    
    # Calls to other functions (for propagation)
    calls_functions: List[str] = field(default_factory=list)
    
    # Has this summary been computed?
    is_computed: bool = False
    
    def propagates_taint(self, param_index: int) -> bool:
        """Check if a parameter's taint propagates to return value."""
        return param_index in self.return_tainted_by
    
    def reaches_sink(self, param_index: int) -> bool:
        """Check if a parameter can reach any sink."""
        return param_index in self.param_to_sinks and len(self.param_to_sinks[param_index]) > 0


@dataclass
class CallContext:
    """Context information for a function call."""
    caller: str           # Qualified name of caller
    call_site_line: int   # Line number of the call
    arg_taints: List[Optional[TaintSource]]  # Taint source for each argument
    depth: int            # Call depth


@dataclass
class InterProceduralFlow:
    """Represents a taint flow that spans multiple functions."""
    source: TaintSource
    sink: TaintSink
    call_chain: List[str]     # Sequence of function qualified names
    path_description: str      # Human-readable path description
    confidence: float = 1.0
    sanitized: bool = False
    sanitizer_location: Optional[str] = None


class InterProceduralTaintAnalyzer:
    """
    Performs inter-procedural taint analysis by tracking data flow across function calls.
    
    Algorithm:
    1. Build call graph of the project
    2. Generate function summaries (bottom-up)
    3. Propagate taint through call graph (top-down from entry points)
    4. Report flows from sources to sinks
    """
    
    DEFAULT_MAX_DEPTH = 10
    DEFAULT_MAX_CALL_CHAIN = 20
    
    def __init__(self, max_depth: int = DEFAULT_MAX_DEPTH, 
                 max_call_chain: int = DEFAULT_MAX_CALL_CHAIN):
        self.max_depth = max_depth
        self.max_call_chain = max_call_chain
        
        # Call graph data
        self.call_graph = CallGraphAnalyzer()
        self.functions: Dict[str, FunctionInfo] = {}
        self.call_edges: List[Tuple[str, str, int]] = []
        
        # Function summaries
        self.summaries: Dict[str, TaintSummary] = {}
        
        # Analysis results
        self.flows: List[InterProceduralFlow] = []
        
        # Recursion detection
        self.in_analysis: Set[str] = set()
        
        # Statistics
        self.stats = {
            "functions_analyzed": 0,
            "summaries_computed": 0,
            "inter_procedural_flows": 0,
            "max_depth_reached": 0,
            "recursive_calls_detected": 0,
        }
    
    def analyze_project(self, root_path: str) -> Dict[str, Any]:
        """
        Perform complete inter-procedural taint analysis on a project.
        
        Returns:
            Dict containing flows, summaries, and statistics
        """
        # Step 1: Build call graph
        call_graph_data = self.call_graph.analyze_project(root_path)
        self.functions = self.call_graph.functions
        self.call_edges = self.call_graph.call_edges
        
        # Step 2: Compute function summaries (bottom-up)
        self._compute_all_summaries(root_path)
        
        # Step 3: Find entry points and propagate taint (top-down)
        entry_points = call_graph_data.get("entry_points", [])
        for entry in entry_points:
            self._analyze_from_entry_point(entry, root_path)
        
        # Step 4: Also analyze standalone functions with sources
        for qualified_name, summary in self.summaries.items():
            if summary.introduces_sources:
                self._propagate_from_function(qualified_name, summary.introduces_sources, [], 0)
        
        return {
            "flows": [self._flow_to_dict(f) for f in self.flows],
            "summaries": {k: self._summary_to_dict(v) for k, v in self.summaries.items()},
            "call_graph": call_graph_data,
            "statistics": self.stats
        }
    
    def _compute_all_summaries(self, root_path: str):
        """Compute summaries for all functions bottom-up."""
        # Topological sort (approximate - handle cycles)
        # Start with leaf functions (no callees)
        
        computed = set()
        to_compute = list(self.functions.keys())
        
        max_iterations = len(to_compute) * 2
        iteration = 0
        
        while to_compute and iteration < max_iterations:
            iteration += 1
            made_progress = False
            
            for qualified_name in list(to_compute):
                func_info = self.functions.get(qualified_name)
                if not func_info:
                    to_compute.remove(qualified_name)
                    continue
                
                # Get callees
                callees = [e[1] for e in self.call_edges if e[0] == qualified_name]
                
                # Check if all callees are computed (or we've waited too long)
                uncomputed_callees = [c for c in callees if c not in computed]
                
                if not uncomputed_callees or iteration > len(to_compute):
                    self._compute_summary(qualified_name, func_info)
                    computed.add(qualified_name)
                    to_compute.remove(qualified_name)
                    made_progress = True
            
            if not made_progress:
                # Handle remaining (likely recursive) functions
                for qualified_name in list(to_compute):
                    func_info = self.functions.get(qualified_name)
                    if func_info:
                        self._compute_summary(qualified_name, func_info)
                        computed.add(qualified_name)
                to_compute.clear()
    
    def _compute_summary(self, qualified_name: str, func_info: FunctionInfo):
        """Compute the taint summary for a single function."""
        self.stats["functions_analyzed"] += 1
        
        summary = TaintSummary(
            function_name=func_info.name,
            qualified_name=qualified_name,
            file_path=func_info.file_path
        )
        
        # Read function source code
        try:
            with open(func_info.file_path, 'r', encoding='utf-8', errors='ignore') as f:
                lines = f.readlines()
                func_lines = lines[func_info.line_start - 1:func_info.line_end]
                func_source = ''.join(func_lines)
        except Exception:
            func_source = ""
        
        # Extract parameters
        params = self._extract_parameters(func_source, func_info.name)
        
        # Detect sources in this function
        summary.introduces_sources = self._detect_sources_in_function(
            func_source, func_info.file_path, func_info.line_start
        )
        
        # Detect sinks in this function
        summary.contains_sinks = self._detect_sinks_in_function(
            func_source, func_info.file_path, func_info.line_start
        )
        
        # Detect sanitizers
        summary.sanitizes = self._detect_sanitizers_in_function(func_source)
        
        # Analyze parameter propagation
        for idx, param in enumerate(params):
            # Check if parameter reaches return
            if self._param_reaches_return(func_source, param):
                summary.return_tainted_by.add(idx)
            
            # Check if parameter reaches any sink
            for sink in summary.contains_sinks:
                if self._param_reaches_expression(func_source, param, sink.args):
                    if idx not in summary.param_to_sinks:
                        summary.param_to_sinks[idx] = []
                    summary.param_to_sinks[idx].append(sink)
        
        # Track function calls
        summary.calls_functions = [e[1] for e in self.call_edges if e[0] == qualified_name]
        
        summary.is_computed = True
        self.summaries[qualified_name] = summary
        self.stats["summaries_computed"] += 1
    
    def _extract_parameters(self, func_source: str, func_name: str) -> List[str]:
        """Extract parameter names from function definition."""
        # Python: def func(param1, param2, ...):
        py_match = re.search(
            rf'def\s+{re.escape(func_name)}\s*\(\s*([^)]*)\s*\)',
            func_source
        )
        if py_match:
            params_str = py_match.group(1)
            params = []
            for p in params_str.split(','):
                p = p.strip()
                if not p or p == 'self' or p == 'cls':
                    continue
                # Handle type annotations and defaults
                param_name = re.split(r'[=:]', p)[0].strip()
                if param_name and '*' not in param_name:
                    params.append(param_name)
            return params
        
        # JavaScript: function func(param1, param2) or (param1, param2) =>
        js_match = re.search(
            rf'(?:function\s+{re.escape(func_name)}\s*|{re.escape(func_name)}\s*=\s*(?:async\s*)?\(?)([^)]*)\)',
            func_source
        )
        if js_match:
            params_str = js_match.group(1)
            params = [p.strip().split(':')[0].strip() for p in params_str.split(',') if p.strip()]
            return params
        
        return []
    
    def _detect_sources_in_function(self, func_source: str, file_path: str, 
                                     line_offset: int) -> List[TaintSource]:
        """Detect taint sources within a function."""
        sources = []
        
        # Python sources
        source_patterns = [
            # Flask/FastAPI
            (r"request\.args\.get\(['\"](\w+)['\"]\)", "GET", TaintType.GENERAL),
            (r"request\.form\.get\(['\"](\w+)['\"]\)", "POST", TaintType.GENERAL),
            (r"request\.form\[['\"](\w+)['\"]\]", "POST", TaintType.GENERAL),
            (r"request\.args\[['\"](\w+)['\"]\]", "GET", TaintType.GENERAL),
            (r"request\.cookies\.get\(['\"](\w+)['\"]\)", "COOKIE", TaintType.GENERAL),
            (r"request\.headers\.get\(['\"](\w+)['\"]\)", "HEADER", TaintType.GENERAL),
            (r"request\.json\.get\(['\"](\w+)['\"]\)", "JSON", TaintType.GENERAL),
            (r"request\.data", "BODY", TaintType.GENERAL),
            (r"request\.get_json\(\)", "JSON", TaintType.GENERAL),
            
            # Django
            (r"request\.GET\.get\(['\"](\w+)['\"]\)", "GET", TaintType.GENERAL),
            (r"request\.POST\.get\(['\"](\w+)['\"]\)", "POST", TaintType.GENERAL),
            (r"request\.GET\[['\"](\w+)['\"]\]", "GET", TaintType.GENERAL),
            (r"request\.POST\[['\"](\w+)['\"]\]", "POST", TaintType.GENERAL),
            
            # General input
            (r"input\((.*?)\)", "STDIN", TaintType.GENERAL),
            (r"sys\.argv\[(\d+)\]", "ARGV", TaintType.GENERAL),
            (r"os\.environ\.get\(['\"](\w+)['\"]\)", "ENV", TaintType.GENERAL),
        ]
        
        for pattern, source_type, taint_type in source_patterns:
            for match in re.finditer(pattern, func_source):
                name = match.group(1) if match.groups() else source_type
                line = func_source[:match.start()].count('\n') + line_offset
                
                sources.append(TaintSource(
                    name=name,
                    source_type=source_type,
                    line=line,
                    file_path=file_path,
                    taint_types={taint_type}
                ))
        
        return sources
    
    def _detect_sinks_in_function(self, func_source: str, file_path: str,
                                   line_offset: int) -> List[TaintSink]:
        """Detect dangerous sinks within a function."""
        sinks = []
        
        for sink_name, (taint_type, severity) in DANGEROUS_SINKS.items():
            # Build pattern for the sink
            base_name = sink_name.split('.')[-1]
            pattern = rf'({re.escape(base_name)})\s*\(([^)]*)\)'
            
            for match in re.finditer(pattern, func_source):
                func_call = match.group(1)
                args_str = match.group(2)
                line = func_source[:match.start()].count('\n') + line_offset
                
                # Parse arguments
                args = [a.strip() for a in args_str.split(',') if a.strip()]
                
                sinks.append(TaintSink(
                    name=sink_name,
                    category=taint_type,
                    line=line,
                    file_path=file_path,
                    args=args,
                    severity=severity
                ))
        
        return sinks
    
    def _detect_sanitizers_in_function(self, func_source: str) -> Set[TaintType]:
        """Detect if function applies sanitizers and which taint types they handle."""
        sanitized_types = set()
        
        for taint_type, sanitizers in SANITIZERS_BY_TYPE.items():
            for san in sanitizers:
                if san in func_source:
                    sanitized_types.add(taint_type)
                    break
        
        return sanitized_types
    
    def _param_reaches_return(self, func_source: str, param: str) -> bool:
        """Check if a parameter value can reach the return statement."""
        # Simple heuristic: check if parameter appears in return statement
        return_patterns = [
            rf'return\s+.*\b{re.escape(param)}\b',
            rf'return\s+{re.escape(param)}\s*$',
            rf'return\s+.*{re.escape(param)}\s*[,\)]',
        ]
        
        for pattern in return_patterns:
            if re.search(pattern, func_source, re.MULTILINE):
                return True
        
        # Check for variable assignment and return
        assignments = re.findall(rf'(\w+)\s*=\s*.*\b{re.escape(param)}\b', func_source)
        for var in assignments:
            if re.search(rf'return\s+.*\b{re.escape(var)}\b', func_source):
                return True
        
        return False
    
    def _param_reaches_expression(self, func_source: str, param: str, 
                                   expressions: List[str]) -> bool:
        """Check if a parameter can reach any of the given expressions."""
        for expr in expressions:
            if param in expr:
                return True
            
            # Check via variable assignment
            assignments = re.findall(rf'(\w+)\s*=\s*.*\b{re.escape(param)}\b', func_source)
            for var in assignments:
                if var in expr:
                    return True
        
        return False
    
    def _analyze_from_entry_point(self, entry_point: str, root_path: str):
        """Start taint propagation from an entry point."""
        summary = self.summaries.get(entry_point)
        if not summary:
            return
        
        # Entry points typically have sources from request parameters
        if summary.introduces_sources:
            self._propagate_from_function(entry_point, summary.introduces_sources, [entry_point], 0)
    
    def _propagate_from_function(self, qualified_name: str, sources: List[TaintSource],
                                  call_chain: List[str], depth: int):
        """Propagate taint from a function through its callees."""
        if depth > self.max_depth:
            self.stats["max_depth_reached"] += 1
            return
        
        if len(call_chain) > self.max_call_chain:
            return
        
        # Detect recursion
        if qualified_name in self.in_analysis:
            self.stats["recursive_calls_detected"] += 1
            return
        
        self.in_analysis.add(qualified_name)
        
        try:
            summary = self.summaries.get(qualified_name)
            if not summary:
                return
            
            # Check for direct source → sink flows in this function
            for source in sources:
                for sink in summary.contains_sinks:
                    # Check if any source can reach this sink
                    if self._source_can_reach_sink(summary, source, sink):
                        flow = InterProceduralFlow(
                            source=source,
                            sink=sink,
                            call_chain=call_chain.copy(),
                            path_description=self._build_path_description(call_chain, source, sink),
                            confidence=1.0 - (depth * 0.1),  # Lower confidence for deeper chains
                            sanitized=bool(summary.sanitizes & {sink.category}),
                            sanitizer_location=qualified_name if summary.sanitizes else None
                        )
                        self.flows.append(flow)
                        self.stats["inter_procedural_flows"] += 1
            
            # Propagate to callees
            for callee_name in summary.calls_functions:
                callee_summary = self.summaries.get(callee_name)
                if not callee_summary:
                    continue
                
                # Propagate taint through callee
                new_chain = call_chain + [callee_name]
                
                # If callee introduces new sources, track them too
                all_sources = list(sources)
                if callee_summary.introduces_sources:
                    all_sources.extend(callee_summary.introduces_sources)
                
                self._propagate_from_function(callee_name, all_sources, new_chain, depth + 1)
        
        finally:
            self.in_analysis.discard(qualified_name)
    
    def _source_can_reach_sink(self, summary: TaintSummary, source: TaintSource,
                                sink: TaintSink) -> bool:
        """Check if a source can reach a sink within a function."""
        # Check if any parameter that's tainted by this source can reach the sink
        # For now, simple heuristic based on variable names
        
        # Direct name match
        for arg in sink.args:
            if source.name in arg:
                return True
        
        # Check param_to_sinks mapping
        for param_idx, sinks in summary.param_to_sinks.items():
            if sink in sinks:
                return True
        
        return False
    
    def _build_path_description(self, call_chain: List[str], source: TaintSource,
                                 sink: TaintSink) -> str:
        """Build a human-readable description of the taint flow path."""
        if not call_chain:
            return f"{source.name} ({source.source_type}) → {sink.name}"
        
        chain_str = " → ".join([c.split("::")[-1] for c in call_chain])
        return f"{source.name} ({source.source_type}) → [{chain_str}] → {sink.name}"
    
    def _flow_to_dict(self, flow: InterProceduralFlow) -> Dict[str, Any]:
        """Convert a flow to a dictionary for JSON serialization."""
        return {
            "source": {
                "name": flow.source.name,
                "type": flow.source.source_type,
                "line": flow.source.line,
                "file": flow.source.file_path,
                "taint_types": [t.value for t in flow.source.taint_types]
            },
            "sink": {
                "name": flow.sink.name,
                "category": flow.sink.category.value,
                "line": flow.sink.line,
                "file": flow.sink.file_path,
                "severity": flow.sink.severity,
                "args": flow.sink.args
            },
            "call_chain": flow.call_chain,
            "path_description": flow.path_description,
            "confidence": flow.confidence,
            "sanitized": flow.sanitized,
            "sanitizer_location": flow.sanitizer_location,
            "is_inter_procedural": len(flow.call_chain) > 1
        }
    
    def _summary_to_dict(self, summary: TaintSummary) -> Dict[str, Any]:
        """Convert a summary to a dictionary for JSON serialization."""
        return {
            "function_name": summary.function_name,
            "qualified_name": summary.qualified_name,
            "file_path": summary.file_path,
            "return_tainted_by_params": list(summary.return_tainted_by),
            "has_sources": len(summary.introduces_sources) > 0,
            "has_sinks": len(summary.contains_sinks) > 0,
            "sanitizes": [t.value for t in summary.sanitizes],
            "calls_count": len(summary.calls_functions),
            "param_sink_count": sum(len(v) for v in summary.param_to_sinks.values())
        }
    
    def get_taint_paths(self, source_func: str, sink_func: str) -> List[List[str]]:
        """Find all paths from a source function to a sink function."""
        return self.call_graph.find_paths_to_sink(source_func, sink_func, self.max_depth)
    
    def get_vulnerable_functions(self) -> List[Dict[str, Any]]:
        """Get list of functions that have taint flows."""
        vulnerable = {}
        
        for flow in self.flows:
            for func in flow.call_chain:
                if func not in vulnerable:
                    vulnerable[func] = {
                        "qualified_name": func,
                        "flows": [],
                        "severity": "LOW"
                    }
                vulnerable[func]["flows"].append(flow.path_description)
                
                # Update severity to highest
                if flow.sink.severity == "HIGH":
                    vulnerable[func]["severity"] = "HIGH"
                elif flow.sink.severity == "MEDIUM" and vulnerable[func]["severity"] == "LOW":
                    vulnerable[func]["severity"] = "MEDIUM"
        
        return list(vulnerable.values())


# Convenience function for API usage
def analyze_interprocedural_taint(root_path: str, max_depth: int = 10) -> Dict[str, Any]:
    """
    Analyze a project for inter-procedural taint flows.
    
    Args:
        root_path: Path to project root
        max_depth: Maximum call chain depth to analyze
        
    Returns:
        Dict with flows, summaries, and statistics
    """
    analyzer = InterProceduralTaintAnalyzer(max_depth=max_depth)
    return analyzer.analyze_project(root_path)
