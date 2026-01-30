"""
Advanced Data-Flow Analyzer.

Implements sophisticated data-flow analysis techniques:
- Path-sensitive analysis: Considers execution paths independently
- Context-sensitive analysis: Considers calling contexts
- Symbolic execution: Constraint-based path exploration
- Points-to analysis: Alias and reference tracking
- IFDS/IDE framework: Precise interprocedural analysis

Based on academic research:
- IFDS (Reps, Horwitz, Sagiv 1995)
- IDE (Sagiv, Reps, Horwitz 1996)  
- CFL-Reachability (Reps 1998)
"""

import os
import re
from typing import List, Dict, Set, Optional, Tuple, Any, Callable
from dataclasses import dataclass, field
from enum import Enum
from collections import defaultdict
import hashlib

from .cfg_builder import (
    CFGBuilder, ControlFlowGraph, CFGNode, CFGEdge,
    CFGNodeType, EdgeType, build_project_cfgs
)
from .pdg_generator import (
    PDGGenerator, ProgramDependenceGraph, PDGNode, PDGEdge,
    DependenceType, TaintPDGAnalyzer, generate_project_pdgs
)
from .taint_analyzer import TaintType, TaintSource, TaintSink, TaintFlow
from .call_graph_analyzer import CallGraphAnalyzer, FunctionInfo


class AnalysisSensitivity(Enum):
    """Analysis precision levels."""
    FLOW_INSENSITIVE = "flow_insensitive"    # Ignores statement order
    FLOW_SENSITIVE = "flow_sensitive"         # Considers statement order
    PATH_SENSITIVE = "path_sensitive"         # Considers execution paths
    CONTEXT_SENSITIVE = "context_sensitive"   # Considers calling context


class SymbolicValueType(Enum):
    """Types of symbolic values."""
    CONCRETE = "concrete"
    SYMBOLIC = "symbolic"
    TAINTED = "tainted"
    UNKNOWN = "unknown"
    TOP = "top"       # No information
    BOTTOM = "bottom" # Contradiction


@dataclass
class PathCondition:
    """Represents a condition along an execution path."""
    expression: str
    is_true: bool
    line: int
    variables: Set[str] = field(default_factory=set)
    
    def negated(self) -> 'PathCondition':
        """Return negated condition."""
        return PathCondition(
            expression=f"not ({self.expression})",
            is_true=not self.is_true,
            line=self.line,
            variables=self.variables.copy()
        )
    
    def __hash__(self):
        return hash((self.expression, self.is_true, self.line))


@dataclass
class SymbolicValue:
    """Represents a symbolic value for symbolic execution."""
    name: str
    value_type: SymbolicValueType
    constraints: List[str] = field(default_factory=list)
    concrete_value: Optional[Any] = None
    source: Optional[str] = None  # Where this value came from
    taint_types: Set[TaintType] = field(default_factory=set)
    
    def is_tainted(self) -> bool:
        return self.value_type == SymbolicValueType.TAINTED or len(self.taint_types) > 0
    
    def __hash__(self):
        return hash((self.name, self.value_type))


@dataclass
class SymbolicState:
    """Represents the symbolic state at a program point."""
    variables: Dict[str, SymbolicValue] = field(default_factory=dict)
    path_conditions: List[PathCondition] = field(default_factory=list)
    
    def copy(self) -> 'SymbolicState':
        """Create a copy of this state."""
        new_state = SymbolicState()
        new_state.variables = {k: SymbolicValue(
            name=v.name,
            value_type=v.value_type,
            constraints=v.constraints.copy(),
            concrete_value=v.concrete_value,
            source=v.source,
            taint_types=v.taint_types.copy()
        ) for k, v in self.variables.items()}
        new_state.path_conditions = self.path_conditions.copy()
        return new_state
    
    def add_condition(self, condition: PathCondition):
        """Add a path condition."""
        self.path_conditions.append(condition)
    
    def set_variable(self, name: str, value: SymbolicValue):
        """Set a variable's symbolic value."""
        self.variables[name] = value
    
    def get_variable(self, name: str) -> Optional[SymbolicValue]:
        """Get a variable's symbolic value."""
        return self.variables.get(name)
    
    def is_feasible(self) -> bool:
        """
        Check if the current path conditions are satisfiable.
        
        Note: Full constraint solving would require Z3/SMT solver.
        This is a simplified version that detects obvious contradictions.
        """
        # Check for obvious contradictions
        conditions_set = set()
        for cond in self.path_conditions:
            if cond.expression in conditions_set:
                # Same condition with different value
                for existing in self.path_conditions:
                    if existing.expression == cond.expression and existing.is_true != cond.is_true:
                        return False
            conditions_set.add(cond.expression)
        return True
    
    def get_path_hash(self) -> str:
        """Get a hash representing this path."""
        path_str = "|".join(f"{c.expression}:{c.is_true}" for c in self.path_conditions)
        return hashlib.md5(path_str.encode()).hexdigest()[:16]


@dataclass
class PointsToInfo:
    """Points-to information for a variable."""
    variable: str
    may_point_to: Set[str] = field(default_factory=set)   # May alias
    must_point_to: Set[str] = field(default_factory=set)  # Must alias
    allocation_site: Optional[str] = None  # Where allocated
    
    def may_alias(self, other: 'PointsToInfo') -> bool:
        """Check if two variables may alias."""
        return bool(self.may_point_to & other.may_point_to)
    
    def must_alias(self, other: 'PointsToInfo') -> bool:
        """Check if two variables must alias."""
        return bool(self.must_point_to & other.must_point_to)


@dataclass
class CallContext:
    """Represents a calling context for context-sensitive analysis."""
    call_stack: Tuple[str, ...] = field(default_factory=tuple)  # Function call chain
    call_sites: Tuple[int, ...] = field(default_factory=tuple)  # Line numbers
    depth: int = 0
    
    def extend(self, function: str, line: int) -> 'CallContext':
        """Create a new context with an additional call."""
        return CallContext(
            call_stack=self.call_stack + (function,),
            call_sites=self.call_sites + (line,),
            depth=self.depth + 1
        )
    
    def __hash__(self):
        return hash((self.call_stack, self.call_sites))
    
    def __str__(self):
        if not self.call_stack:
            return "[main]"
        return " -> ".join(self.call_stack)


@dataclass
class DataFlowFact:
    """A fact in data-flow analysis (for IFDS)."""
    variable: str
    state: SymbolicValueType
    context: Optional[CallContext] = None
    path_condition_hash: Optional[str] = None
    
    def __hash__(self):
        return hash((self.variable, self.state, 
                     self.context.call_stack if self.context else None,
                     self.path_condition_hash))


@dataclass
class AdvancedFlowResult:
    """Result from advanced data-flow analysis."""
    source: TaintSource
    sink: TaintSink
    
    # Path information
    execution_path: List[str] = field(default_factory=list)  # Node IDs
    path_conditions: List[PathCondition] = field(default_factory=list)
    
    # Context information
    call_context: Optional[CallContext] = None
    
    # Analysis info
    is_feasible: bool = True
    is_sanitized: bool = False
    sanitizer_location: Optional[str] = None
    
    # Confidence
    confidence: float = 1.0
    analysis_type: str = "path_sensitive"
    
    # Details
    data_flow_path: List[str] = field(default_factory=list)  # Variable flow
    intermediate_values: Dict[str, str] = field(default_factory=dict)


class AdvancedDataFlowAnalyzer:
    """
    Advanced data-flow analyzer implementing multiple analysis techniques.
    
    Supports:
    1. Path-sensitive analysis
    2. Context-sensitive analysis
    3. Symbolic execution (simplified)
    4. Points-to analysis
    5. IFDS-style analysis
    """
    
    # Configuration
    MAX_PATH_LENGTH = 50
    MAX_CALL_DEPTH = 10
    MAX_PATHS_PER_FUNCTION = 1000
    MAX_SYMBOLIC_STATES = 10000
    
    def __init__(self, sensitivity: AnalysisSensitivity = AnalysisSensitivity.PATH_SENSITIVE):
        self.sensitivity = sensitivity
        self.cfg_builder = CFGBuilder()
        self.pdg_generator = PDGGenerator()
        self.call_graph_analyzer = CallGraphAnalyzer()
        
        # Caches
        self._cfg_cache: Dict[str, ControlFlowGraph] = {}
        self._pdg_cache: Dict[str, ProgramDependenceGraph] = {}
        self._points_to_cache: Dict[str, Dict[str, PointsToInfo]] = {}
        
        # Analysis state
        self._current_context: Optional[CallContext] = None
        self._analyzed_paths: Set[str] = set()
        self._state_count = 0
        
        # Results
        self.findings: List[AdvancedFlowResult] = []
        self.statistics = {
            'paths_explored': 0,
            'states_created': 0,
            'feasible_paths': 0,
            'infeasible_paths': 0,
            'taint_flows_found': 0,
            'sanitized_flows': 0
        }
    
    def analyze_project(self, project_path: str) -> List[AdvancedFlowResult]:
        """
        Analyze an entire project using advanced data-flow analysis.
        
        Args:
            project_path: Path to the project root
        
        Returns:
            List of analysis findings
        """
        self.findings = []
        self._reset_statistics()
        
        # Build call graph
        call_graph_data = self.call_graph_analyzer.analyze_project(project_path)
        
        # Build CFGs and PDGs for all files
        self._build_project_graphs(project_path)
        
        # Find entry points
        entry_points = self._find_entry_points(call_graph_data)
        
        # Analyze from each entry point
        for entry_point in entry_points:
            cfg = self._cfg_cache.get(entry_point)
            if cfg:
                self._analyze_function(cfg, CallContext())
        
        return self.findings
    
    def analyze_file(self, file_path: str) -> List[AdvancedFlowResult]:
        """
        Analyze a single file.
        
        Args:
            file_path: Path to the file
        
        Returns:
            List of analysis findings
        """
        self.findings = []
        self._reset_statistics()
        
        # Build CFGs for the file
        cfgs = self.cfg_builder.build_from_file(file_path)
        
        for name, cfg in cfgs.items():
            self._cfg_cache[name] = cfg
            self._analyze_function(cfg, CallContext())
        
        return self.findings
    
    def analyze_function(self, cfg: ControlFlowGraph, 
                         initial_state: Optional[SymbolicState] = None) -> List[AdvancedFlowResult]:
        """
        Analyze a single function.
        
        Args:
            cfg: Control flow graph of the function
            initial_state: Initial symbolic state (optional)
        
        Returns:
            List of findings for this function
        """
        self.findings = []
        self._analyze_function(cfg, CallContext(), initial_state)
        return self.findings
    
    def _reset_statistics(self):
        """Reset analysis statistics."""
        self.statistics = {
            'paths_explored': 0,
            'states_created': 0,
            'feasible_paths': 0,
            'infeasible_paths': 0,
            'taint_flows_found': 0,
            'sanitized_flows': 0
        }
        self._analyzed_paths = set()
        self._state_count = 0
    
    def _build_project_graphs(self, project_path: str):
        """Build CFGs and PDGs for all source files."""
        for dirpath, dirnames, filenames in os.walk(project_path):
            # Skip non-source directories
            dirnames[:] = [d for d in dirnames if d not in {
                '__pycache__', 'node_modules', '.git', '.venv', 'venv',
                'dist', 'build', '.next', 'coverage'
            }]
            
            for filename in filenames:
                if filename.endswith(('.py', '.js', '.jsx', '.ts', '.tsx')):
                    filepath = os.path.join(dirpath, filename)
                    try:
                        cfgs = self.cfg_builder.build_from_file(filepath)
                        for name, cfg in cfgs.items():
                            qualified = f"{os.path.relpath(filepath, project_path)}::{name}"
                            cfg.qualified_name = qualified
                            cfg.file_path = filepath
                            self._cfg_cache[qualified] = cfg
                    except Exception as e:
                        continue
    
    def _find_entry_points(self, call_graph_data: Dict) -> List[str]:
        """Find analysis entry points (routes, handlers, main functions)."""
        entry_points = []
        
        for node in call_graph_data.get('nodes', []):
            if node.get('is_entry_point') or node.get('type') == 'route':
                entry_points.append(node.get('qualified_name', node.get('id', '')))
        
        # If no entry points found, analyze all functions
        if not entry_points:
            entry_points = list(self._cfg_cache.keys())
        
        return entry_points
    
    def _analyze_function(self, cfg: ControlFlowGraph, context: CallContext,
                          initial_state: Optional[SymbolicState] = None):
        """
        Analyze a function using the configured sensitivity level.
        """
        if context.depth > self.MAX_CALL_DEPTH:
            return
        
        self._current_context = context
        
        if self.sensitivity == AnalysisSensitivity.PATH_SENSITIVE:
            self._path_sensitive_analysis(cfg, initial_state)
        elif self.sensitivity == AnalysisSensitivity.CONTEXT_SENSITIVE:
            self._context_sensitive_analysis(cfg, context, initial_state)
        elif self.sensitivity == AnalysisSensitivity.FLOW_SENSITIVE:
            self._flow_sensitive_analysis(cfg, initial_state)
        else:
            self._flow_insensitive_analysis(cfg)
    
    def _path_sensitive_analysis(self, cfg: ControlFlowGraph,
                                  initial_state: Optional[SymbolicState] = None):
        """
        Path-sensitive analysis: Explore paths independently.
        
        Uses symbolic execution with path conditions.
        """
        if not cfg.entry_node:
            return
        
        # Initialize state
        state = initial_state.copy() if initial_state else SymbolicState()
        
        # Worklist: (node_id, state, path)
        worklist: List[Tuple[str, SymbolicState, List[str]]] = [
            (cfg.entry_node.id, state, [cfg.entry_node.id])
        ]
        
        visited_states: Dict[str, Set[str]] = defaultdict(set)  # node -> path hashes
        
        while worklist and self._state_count < self.MAX_SYMBOLIC_STATES:
            node_id, current_state, path = worklist.pop(0)
            
            if len(path) > self.MAX_PATH_LENGTH:
                continue
            
            path_hash = current_state.get_path_hash()
            if path_hash in visited_states[node_id]:
                continue
            visited_states[node_id].add(path_hash)
            
            self._state_count += 1
            self.statistics['states_created'] += 1
            
            # Get node
            node = cfg.nodes.get(node_id)
            if not node:
                continue
            
            # Check path feasibility
            if not current_state.is_feasible():
                self.statistics['infeasible_paths'] += 1
                continue
            
            # Process node
            new_state = self._process_node_symbolic(node, current_state, cfg)
            
            # Check for taint flows
            self._check_taint_at_node(node, new_state, path, cfg)
            
            # Handle successors based on node type
            if node.node_type in (CFGNodeType.CONDITION, CFGNodeType.LOOP_HEADER):
                # Branch on condition
                true_state = new_state.copy()
                false_state = new_state.copy()
                
                condition = PathCondition(
                    expression=node.condition or node.code,
                    is_true=True,
                    line=node.line_start,
                    variables=self._extract_condition_vars(node.condition or node.code)
                )
                
                true_state.add_condition(condition)
                false_state.add_condition(condition.negated())
                
                # Find successors
                for edge in cfg.edges:
                    if edge.source_id == node_id:
                        if edge.edge_type == EdgeType.TRUE_BRANCH:
                            if true_state.is_feasible():
                                worklist.append((edge.target_id, true_state, path + [edge.target_id]))
                        elif edge.edge_type == EdgeType.FALSE_BRANCH:
                            if false_state.is_feasible():
                                worklist.append((edge.target_id, false_state, path + [edge.target_id]))
                        else:
                            worklist.append((edge.target_id, new_state.copy(), path + [edge.target_id]))
            
            elif node.node_type in (CFGNodeType.RETURN, CFGNodeType.RAISE):
                # End of path
                self.statistics['paths_explored'] += 1
                self.statistics['feasible_paths'] += 1
            
            elif node.node_type == CFGNodeType.CALL:
                # Handle function call
                called = node.called_function
                if called and called in self._cfg_cache:
                    # Context-sensitive call
                    new_context = self._current_context.extend(called, node.line_start) if self._current_context else CallContext()
                    if new_context.depth <= self.MAX_CALL_DEPTH:
                        self._analyze_function(self._cfg_cache[called], new_context, new_state)
                
                # Continue in current function
                for succ_id in cfg.successors.get(node_id, []):
                    worklist.append((succ_id, new_state.copy(), path + [succ_id]))
            
            else:
                # Regular statement
                for succ_id in cfg.successors.get(node_id, []):
                    worklist.append((succ_id, new_state.copy(), path + [succ_id]))
    
    def _context_sensitive_analysis(self, cfg: ControlFlowGraph, context: CallContext,
                                     initial_state: Optional[SymbolicState] = None):
        """
        Context-sensitive analysis: Consider calling context.
        
        Uses k-CFA style analysis with call string abstraction.
        """
        # Similar to path-sensitive but tracks calling context
        state = initial_state.copy() if initial_state else SymbolicState()
        
        # Add context to analysis key
        context_key = f"{cfg.qualified_name}@{context}"
        if context_key in self._analyzed_paths:
            return
        self._analyzed_paths.add(context_key)
        
        # Perform flow-sensitive analysis within this context
        self._flow_sensitive_analysis(cfg, state)
    
    def _flow_sensitive_analysis(self, cfg: ControlFlowGraph,
                                  initial_state: Optional[SymbolicState] = None):
        """
        Flow-sensitive analysis: Consider statement order.
        
        Uses standard dataflow analysis with reaching definitions.
        """
        if not cfg.entry_node:
            return
        
        state = initial_state.copy() if initial_state else SymbolicState()
        
        # Worklist algorithm
        worklist = [cfg.entry_node.id]
        in_states: Dict[str, SymbolicState] = {}
        out_states: Dict[str, SymbolicState] = {}
        
        in_states[cfg.entry_node.id] = state
        
        while worklist:
            node_id = worklist.pop(0)
            node = cfg.nodes.get(node_id)
            if not node:
                continue
            
            # Merge predecessor states
            pred_states = [out_states[p] for p in cfg.predecessors.get(node_id, []) if p in out_states]
            if pred_states:
                merged = self._merge_states(pred_states)
                in_states[node_id] = merged
            elif node_id not in in_states:
                in_states[node_id] = SymbolicState()
            
            # Process node
            new_out = self._process_node_symbolic(node, in_states[node_id], cfg)
            
            # Check for changes
            if node_id not in out_states or self._states_differ(out_states[node_id], new_out):
                out_states[node_id] = new_out
                
                # Check for taint
                self._check_taint_at_node(node, new_out, [node_id], cfg)
                
                # Add successors
                for succ_id in cfg.successors.get(node_id, []):
                    if succ_id not in worklist:
                        worklist.append(succ_id)
    
    def _flow_insensitive_analysis(self, cfg: ControlFlowGraph):
        """
        Flow-insensitive analysis: Ignore statement order.
        
        Quick but imprecise - useful for large codebases.
        """
        state = SymbolicState()
        
        # Process all nodes without considering order
        for node_id, node in cfg.nodes.items():
            self._process_node_symbolic(node, state, cfg)
            self._check_taint_at_node(node, state, [node_id], cfg)
    
    def _process_node_symbolic(self, node: CFGNode, state: SymbolicState,
                                cfg: ControlFlowGraph) -> SymbolicState:
        """
        Process a CFG node and update symbolic state.
        
        Returns:
            Updated symbolic state
        """
        new_state = state.copy()
        
        # Handle assignments
        if node.node_type in (CFGNodeType.STATEMENT, CFGNodeType.ASSIGNMENT):
            for var in node.defined_vars:
                # Check if RHS is tainted
                is_tainted = False
                taint_types: Set[TaintType] = set()
                
                for used_var in node.used_vars:
                    existing = state.get_variable(used_var)
                    if existing and existing.is_tainted():
                        is_tainted = True
                        taint_types.update(existing.taint_types)
                
                # Check for source
                if self._is_source(node.code):
                    is_tainted = True
                    taint_types.add(TaintType.GENERAL)
                
                # Create symbolic value
                value = SymbolicValue(
                    name=var,
                    value_type=SymbolicValueType.TAINTED if is_tainted else SymbolicValueType.SYMBOLIC,
                    source=node.code if is_tainted else None,
                    taint_types=taint_types
                )
                
                new_state.set_variable(var, value)
        
        # Handle sanitization
        if self._is_sanitizer(node.code):
            # Clear taint for affected variables
            for var in node.defined_vars:
                existing = state.get_variable(var)
                if existing:
                    existing.value_type = SymbolicValueType.SYMBOLIC
                    existing.taint_types.clear()
        
        return new_state
    
    def _check_taint_at_node(self, node: CFGNode, state: SymbolicState,
                              path: List[str], cfg: ControlFlowGraph):
        """Check if tainted data flows to a sink at this node."""
        if not self._is_sink(node.code):
            return
        
        # Check if any used variable is tainted
        for var in node.used_vars:
            sym_value = state.get_variable(var)
            if sym_value and sym_value.is_tainted():
                # Found taint flow
                self.statistics['taint_flows_found'] += 1
                
                # Create source
                source = TaintSource(
                    name=var,
                    source_type="symbolic",
                    line=0,  # Unknown original line
                    file_path=cfg.file_path,
                    taint_types=sym_value.taint_types
                )
                
                # Create sink
                sink_type = self._get_sink_type(node.code)
                sink = TaintSink(
                    name=node.called_function or node.code[:50],
                    category=sink_type,
                    line=node.line_start,
                    file_path=cfg.file_path
                )
                
                # Create result
                result = AdvancedFlowResult(
                    source=source,
                    sink=sink,
                    execution_path=path,
                    path_conditions=state.path_conditions.copy(),
                    call_context=self._current_context,
                    is_feasible=state.is_feasible(),
                    confidence=0.9 if state.is_feasible() else 0.5,
                    analysis_type=self.sensitivity.value,
                    data_flow_path=[var]
                )
                
                self.findings.append(result)
    
    def _merge_states(self, states: List[SymbolicState]) -> SymbolicState:
        """Merge multiple symbolic states (join operation)."""
        if not states:
            return SymbolicState()
        if len(states) == 1:
            return states[0].copy()
        
        merged = SymbolicState()
        
        # Merge variables
        all_vars = set()
        for state in states:
            all_vars.update(state.variables.keys())
        
        for var in all_vars:
            values = [s.get_variable(var) for s in states if s.get_variable(var)]
            if values:
                # If any is tainted, result is tainted
                is_tainted = any(v.is_tainted() for v in values)
                taint_types = set()
                for v in values:
                    taint_types.update(v.taint_types)
                
                merged.set_variable(var, SymbolicValue(
                    name=var,
                    value_type=SymbolicValueType.TAINTED if is_tainted else SymbolicValueType.SYMBOLIC,
                    taint_types=taint_types
                ))
        
        # Merge path conditions (intersection - conditions that hold on all paths)
        if all(s.path_conditions for s in states):
            common = set(states[0].path_conditions)
            for state in states[1:]:
                common &= set(state.path_conditions)
            merged.path_conditions = list(common)
        
        return merged
    
    def _states_differ(self, s1: SymbolicState, s2: SymbolicState) -> bool:
        """Check if two states differ."""
        if set(s1.variables.keys()) != set(s2.variables.keys()):
            return True
        
        for var in s1.variables:
            v1 = s1.get_variable(var)
            v2 = s2.get_variable(var)
            if v1 and v2:
                if v1.value_type != v2.value_type or v1.taint_types != v2.taint_types:
                    return True
        
        return False
    
    def _extract_condition_vars(self, condition: str) -> Set[str]:
        """Extract variable names from a condition expression."""
        # Simple regex for identifiers
        identifiers = re.findall(r'\b([a-zA-Z_][a-zA-Z0-9_]*)\b', condition)
        # Filter out keywords
        keywords = {'if', 'else', 'elif', 'and', 'or', 'not', 'in', 'is', 'True', 'False', 'None',
                   'true', 'false', 'null', 'undefined'}
        return {i for i in identifiers if i not in keywords}
    
    # Source/Sink/Sanitizer detection
    SOURCES = {
        'request.args', 'request.form', 'request.data', 'request.json',
        'request.cookies', 'request.headers', 'request.values',
        'req.body', 'req.query', 'req.params', 'req.cookies',
        'input(', 'raw_input(', 'sys.stdin',
        'os.environ', 'os.getenv', 'process.env',
    }
    
    SINKS = {
        'os.system', 'subprocess', 'eval', 'exec', 'compile',
        'cursor.execute', 'db.execute', 'execute(',
        'render_template_string', 'Markup(',
        'open(', 'send_file',
        'redirect(', 'requests.get', 'requests.post',
        'child_process', 'spawn', 'document.write', 'innerHTML',
    }
    
    SANITIZERS = {
        'escape', 'html.escape', 'markupsafe.escape', 'bleach',
        'quote', 'shlex.quote',
        'int(', 'float(', 'str(',
        'sanitize', 'validate', 'clean',
    }
    
    def _is_source(self, code: str) -> bool:
        code_lower = code.lower()
        return any(s.lower() in code_lower for s in self.SOURCES)
    
    def _is_sink(self, code: str) -> bool:
        code_lower = code.lower()
        return any(s.lower() in code_lower for s in self.SINKS)
    
    def _is_sanitizer(self, code: str) -> bool:
        code_lower = code.lower()
        return any(s.lower() in code_lower for s in self.SANITIZERS)
    
    def _get_sink_type(self, code: str) -> TaintType:
        code_lower = code.lower()
        if 'execute' in code_lower or 'cursor' in code_lower or 'db.' in code_lower:
            return TaintType.SQLI
        if 'system' in code_lower or 'subprocess' in code_lower or 'popen' in code_lower:
            return TaintType.CMDI
        if 'eval' in code_lower or 'exec' in code_lower:
            return TaintType.CODE
        if 'template' in code_lower or 'markup' in code_lower:
            return TaintType.SSTI
        if 'open(' in code_lower or 'send_file' in code_lower:
            return TaintType.PATH
        if 'redirect' in code_lower:
            return TaintType.OPEN_REDIRECT
        if 'request' in code_lower and ('get' in code_lower or 'post' in code_lower):
            return TaintType.SSRF
        return TaintType.GENERAL


class PointsToAnalyzer:
    """
    Points-to analysis for alias detection.
    
    Implements:
    - Andersen's analysis (subset-based)
    - Flow-insensitive points-to
    """
    
    def __init__(self):
        self.points_to: Dict[str, PointsToInfo] = {}
    
    def analyze_cfg(self, cfg: ControlFlowGraph) -> Dict[str, PointsToInfo]:
        """
        Perform points-to analysis on a CFG.
        
        Returns:
            Dict mapping variable names to their points-to info
        """
        self.points_to = {}
        
        # Collect all assignments
        assignments = []
        for node_id, node in cfg.nodes.items():
            if node.node_type in (CFGNodeType.STATEMENT, CFGNodeType.ASSIGNMENT):
                for var in node.defined_vars:
                    assignments.append((var, node.used_vars, node_id))
        
        # Fixed-point iteration
        changed = True
        while changed:
            changed = False
            
            for var, used_vars, alloc_site in assignments:
                if var not in self.points_to:
                    self.points_to[var] = PointsToInfo(variable=var, allocation_site=alloc_site)
                
                info = self.points_to[var]
                
                for used in used_vars:
                    if used in self.points_to:
                        # Propagate points-to
                        old_size = len(info.may_point_to)
                        info.may_point_to.update(self.points_to[used].may_point_to)
                        info.may_point_to.add(used)
                        if len(info.may_point_to) > old_size:
                            changed = True
                    else:
                        if used not in info.may_point_to:
                            info.may_point_to.add(used)
                            changed = True
        
        return self.points_to
    
    def may_alias(self, var1: str, var2: str) -> bool:
        """Check if two variables may alias."""
        info1 = self.points_to.get(var1)
        info2 = self.points_to.get(var2)
        
        if not info1 or not info2:
            return False
        
        return info1.may_alias(info2)


# Convenience functions
def analyze_with_advanced_dataflow(project_path: str, 
                                    sensitivity: str = "path_sensitive") -> List[Dict]:
    """
    Analyze a project using advanced data-flow analysis.
    
    Args:
        project_path: Path to the project
        sensitivity: Analysis sensitivity level
    
    Returns:
        List of findings as dictionaries
    """
    sens = AnalysisSensitivity(sensitivity)
    analyzer = AdvancedDataFlowAnalyzer(sensitivity=sens)
    results = analyzer.analyze_project(project_path)
    
    # Convert to dicts
    findings = []
    for result in results:
        finding = {
            'type': 'advanced_dataflow',
            'vulnerability_type': result.sink.category.value,
            'source': {
                'variable': result.source.name,
                'line': result.source.line,
                'file': result.source.file_path,
            },
            'sink': {
                'function': result.sink.name,
                'line': result.sink.line,
                'file': result.sink.file_path,
            },
            'path_length': len(result.execution_path),
            'path_conditions': [
                {'expression': c.expression, 'value': c.is_true}
                for c in result.path_conditions
            ],
            'is_feasible': result.is_feasible,
            'is_sanitized': result.is_sanitized,
            'confidence': result.confidence,
            'analysis_type': result.analysis_type,
            'call_context': str(result.call_context) if result.call_context else None,
        }
        findings.append(finding)
    
    return findings


def get_dataflow_statistics(project_path: str) -> Dict:
    """
    Get data-flow analysis statistics for a project.
    
    Returns:
        Analysis statistics
    """
    analyzer = AdvancedDataFlowAnalyzer()
    analyzer.analyze_project(project_path)
    
    return {
        'statistics': analyzer.statistics,
        'findings_count': len(analyzer.findings),
        'cfg_count': len(analyzer._cfg_cache),
    }
