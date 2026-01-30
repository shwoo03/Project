"""
Program Dependence Graph (PDG) Generator.

Builds Program Dependence Graphs combining:
- Control Dependence Graph (CDG): Control flow dependencies
- Data Dependence Graph (DDG): Data flow dependencies

Key concepts:
- Control Dependence: Statement B is control-dependent on A if A's outcome 
  determines whether B executes
- Data Dependence: Statement B is data-dependent on A if A defines a variable
  that B uses and there's a path from A to B without redefinition

Uses:
- Slicing: Find all statements affecting a variable
- Vulnerability analysis: Track data flow to sinks
- Dead code detection
- Optimization
"""

import os
from typing import List, Dict, Set, Optional, Tuple, Any
from dataclasses import dataclass, field
from enum import Enum
from collections import defaultdict

from .cfg_builder import (
    CFGBuilder, ControlFlowGraph, CFGNode, CFGEdge,
    CFGNodeType, EdgeType, build_project_cfgs
)


class DependenceType(Enum):
    """Types of program dependence."""
    CONTROL = "control"          # Control dependence
    DATA_FLOW = "data_flow"      # Use-def chain
    DATA_ANTI = "data_anti"      # Def-use chain (anti-dependence)
    DATA_OUTPUT = "data_output"  # Def-def chain (output dependence)
    CALL = "call"                # Function call dependence
    PARAMETER = "parameter"      # Parameter passing


@dataclass
class DefUseInfo:
    """Definition-Use information for a variable."""
    variable: str
    def_node_id: str
    def_line: int
    use_nodes: List[Tuple[str, int]] = field(default_factory=list)  # (node_id, line)
    
    def __hash__(self):
        return hash((self.variable, self.def_node_id))


@dataclass
class PDGEdge:
    """Represents an edge in the Program Dependence Graph."""
    source_id: str
    target_id: str
    dependence_type: DependenceType
    variable: Optional[str] = None  # For data dependencies
    label: Optional[str] = None     # Additional info
    
    def __hash__(self):
        return hash((self.source_id, self.target_id, self.dependence_type))


@dataclass
class PDGNode:
    """
    Node in the Program Dependence Graph.
    Wraps CFG node with additional PDG-specific info.
    """
    id: str
    cfg_node: CFGNode
    
    # Dependence info
    control_dependencies: Set[str] = field(default_factory=set)  # Nodes this depends on
    data_dependencies: Dict[str, Set[str]] = field(default_factory=dict)  # var -> def nodes
    
    # Variable info
    defined_vars: Set[str] = field(default_factory=set)
    used_vars: Set[str] = field(default_factory=set)
    
    # For slicing
    in_backward_slice: bool = False
    in_forward_slice: bool = False
    slice_criterion: bool = False
    
    def __hash__(self):
        return hash(self.id)


@dataclass
class ProgramDependenceGraph:
    """Complete Program Dependence Graph for a function."""
    function_name: str
    qualified_name: str
    file_path: str
    
    # Source CFG
    cfg: Optional[ControlFlowGraph] = None
    
    # PDG nodes and edges
    nodes: Dict[str, PDGNode] = field(default_factory=dict)
    edges: List[PDGEdge] = field(default_factory=list)
    
    # Indexed dependencies
    control_edges: List[PDGEdge] = field(default_factory=list)
    data_edges: List[PDGEdge] = field(default_factory=list)
    
    # Def-Use chains
    def_use_chains: Dict[str, List[DefUseInfo]] = field(default_factory=dict)  # var -> chains
    
    # Reaching definitions at each node
    reaching_defs: Dict[str, Dict[str, Set[str]]] = field(default_factory=dict)  # node -> var -> def_nodes
    
    def add_node(self, node: PDGNode):
        """Add a node to the PDG."""
        self.nodes[node.id] = node
    
    def add_edge(self, edge: PDGEdge):
        """Add an edge to the PDG."""
        self.edges.append(edge)
        
        if edge.dependence_type == DependenceType.CONTROL:
            self.control_edges.append(edge)
        elif edge.dependence_type in (DependenceType.DATA_FLOW, 
                                       DependenceType.DATA_ANTI, 
                                       DependenceType.DATA_OUTPUT):
            self.data_edges.append(edge)
    
    def get_backward_slice(self, criterion_node_id: str, 
                           criterion_vars: Optional[Set[str]] = None) -> Set[str]:
        """
        Compute backward slice from a criterion.
        
        A backward slice includes all nodes that can affect the criterion.
        
        Args:
            criterion_node_id: The slicing criterion node
            criterion_vars: Variables of interest (None = all used vars)
        
        Returns:
            Set of node IDs in the slice
        """
        slice_nodes = set()
        worklist = [criterion_node_id]
        
        criterion_node = self.nodes.get(criterion_node_id)
        if not criterion_node:
            return slice_nodes
        
        # Get variables to track
        if criterion_vars is None:
            criterion_vars = criterion_node.used_vars.copy()
        
        visited = set()
        vars_to_track = criterion_vars.copy()
        
        while worklist:
            node_id = worklist.pop()
            if node_id in visited:
                continue
            visited.add(node_id)
            slice_nodes.add(node_id)
            
            node = self.nodes.get(node_id)
            if not node:
                continue
            
            # Follow control dependencies
            for ctrl_dep in node.control_dependencies:
                if ctrl_dep not in visited:
                    worklist.append(ctrl_dep)
            
            # Follow data dependencies for tracked variables
            for var in list(vars_to_track):
                if var in node.data_dependencies:
                    for def_node_id in node.data_dependencies[var]:
                        if def_node_id not in visited:
                            worklist.append(def_node_id)
                            # Track variables used in the def node
                            def_node = self.nodes.get(def_node_id)
                            if def_node:
                                vars_to_track.update(def_node.used_vars)
        
        return slice_nodes
    
    def get_forward_slice(self, criterion_node_id: str,
                          criterion_vars: Optional[Set[str]] = None) -> Set[str]:
        """
        Compute forward slice from a criterion.
        
        A forward slice includes all nodes affected by the criterion.
        
        Args:
            criterion_node_id: The slicing criterion node
            criterion_vars: Variables of interest (None = all defined vars)
        
        Returns:
            Set of node IDs in the slice
        """
        slice_nodes = set()
        worklist = [criterion_node_id]
        
        criterion_node = self.nodes.get(criterion_node_id)
        if not criterion_node:
            return slice_nodes
        
        # Get variables to track
        if criterion_vars is None:
            criterion_vars = criterion_node.defined_vars.copy()
        
        visited = set()
        vars_to_track = criterion_vars.copy()
        
        while worklist:
            node_id = worklist.pop()
            if node_id in visited:
                continue
            visited.add(node_id)
            slice_nodes.add(node_id)
            
            # Find nodes that depend on this node
            for edge in self.edges:
                if edge.source_id == node_id:
                    if edge.dependence_type == DependenceType.CONTROL:
                        if edge.target_id not in visited:
                            worklist.append(edge.target_id)
                    elif edge.dependence_type == DependenceType.DATA_FLOW:
                        if edge.variable in vars_to_track:
                            if edge.target_id not in visited:
                                worklist.append(edge.target_id)
                                # Track new defs at target
                                target_node = self.nodes.get(edge.target_id)
                                if target_node:
                                    vars_to_track.update(target_node.defined_vars)
        
        return slice_nodes
    
    def get_data_flow_paths(self, source_var: str, source_node: str,
                            target_node: str, max_paths: int = 100) -> List[List[str]]:
        """
        Find all data flow paths from source to target involving a variable.
        
        Returns:
            List of paths (each path is a list of node IDs)
        """
        paths = []
        
        def dfs(current: str, path: List[str], current_var: str):
            if len(paths) >= max_paths:
                return
            
            if current == target_node:
                paths.append(path.copy())
                return
            
            node = self.nodes.get(current)
            if not node:
                return
            
            # Find data edges from this node
            for edge in self.data_edges:
                if edge.source_id == current and edge.variable:
                    # Track variable transformation
                    next_var = edge.variable if current_var == edge.variable else None
                    if next_var or edge.target_id == target_node:
                        if edge.target_id not in path:
                            path.append(edge.target_id)
                            dfs(edge.target_id, path, edge.variable)
                            path.pop()
        
        dfs(source_node, [source_node], source_var)
        return paths


class PDGGenerator:
    """
    Generates Program Dependence Graphs from Control Flow Graphs.
    
    Algorithm:
    1. Build CFG (using CFGBuilder)
    2. Compute post-dominators
    3. Build Control Dependence Graph
    4. Compute reaching definitions
    5. Build Data Dependence Graph
    6. Combine into PDG
    """
    
    def __init__(self):
        self.cfg_builder = CFGBuilder()
    
    def generate_from_cfg(self, cfg: ControlFlowGraph) -> ProgramDependenceGraph:
        """
        Generate PDG from an existing CFG.
        
        Args:
            cfg: The control flow graph
        
        Returns:
            The program dependence graph
        """
        pdg = ProgramDependenceGraph(
            function_name=cfg.function_name,
            qualified_name=cfg.qualified_name,
            file_path=cfg.file_path,
            cfg=cfg
        )
        
        # Create PDG nodes from CFG nodes
        for node_id, cfg_node in cfg.nodes.items():
            pdg_node = PDGNode(
                id=node_id,
                cfg_node=cfg_node,
                defined_vars=cfg_node.defined_vars.copy(),
                used_vars=cfg_node.used_vars.copy()
            )
            pdg.add_node(pdg_node)
        
        # Step 1: Compute post-dominators
        post_doms = self._compute_post_dominators(cfg)
        
        # Step 2: Build Control Dependence Graph
        self._build_control_dependencies(cfg, pdg, post_doms)
        
        # Step 3: Compute reaching definitions
        reaching_defs = self._compute_reaching_definitions(cfg, pdg)
        pdg.reaching_defs = reaching_defs
        
        # Step 4: Build Data Dependence Graph
        self._build_data_dependencies(cfg, pdg, reaching_defs)
        
        # Step 5: Build def-use chains
        self._build_def_use_chains(pdg)
        
        return pdg
    
    def generate_from_file(self, file_path: str) -> Dict[str, ProgramDependenceGraph]:
        """
        Generate PDGs for all functions in a file.
        
        Returns:
            Dict mapping qualified function names to their PDGs
        """
        cfgs = self.cfg_builder.build_from_file(file_path)
        pdgs = {}
        
        for name, cfg in cfgs.items():
            pdg = self.generate_from_cfg(cfg)
            pdg.file_path = file_path
            pdgs[name] = pdg
        
        return pdgs
    
    def _compute_post_dominators(self, cfg: ControlFlowGraph) -> Dict[str, Set[str]]:
        """
        Compute post-dominator sets for all nodes.
        
        Node A post-dominates B if every path from B to EXIT goes through A.
        """
        if not cfg.exit_node:
            return {}
        
        all_nodes = set(cfg.nodes.keys())
        post_doms = {}
        
        # Exit node post-dominates only itself
        post_doms[cfg.exit_node.id] = {cfg.exit_node.id}
        
        # Initialize all other nodes with all nodes
        for node_id in cfg.nodes:
            if node_id != cfg.exit_node.id:
                post_doms[node_id] = all_nodes.copy()
        
        # Reverse CFG edges for post-dominator computation
        rev_succs = defaultdict(list)
        for node_id in cfg.nodes:
            for succ_id in cfg.successors.get(node_id, []):
                rev_succs[succ_id].append(node_id)
        
        # Iterate until fixed point
        changed = True
        while changed:
            changed = False
            # Process in reverse order (from exit to entry)
            for node_id in cfg.nodes:
                if node_id == cfg.exit_node.id:
                    continue
                
                succs = cfg.successors.get(node_id, [])
                if not succs:
                    continue
                
                # Post-dom = intersection of successors' post-doms + self
                new_post_dom = all_nodes.copy()
                for succ_id in succs:
                    new_post_dom &= post_doms.get(succ_id, all_nodes)
                new_post_dom.add(node_id)
                
                if new_post_dom != post_doms.get(node_id):
                    post_doms[node_id] = new_post_dom
                    changed = True
        
        return post_doms
    
    def _build_control_dependencies(self, cfg: ControlFlowGraph, 
                                    pdg: ProgramDependenceGraph,
                                    post_doms: Dict[str, Set[str]]):
        """
        Build control dependence edges.
        
        Node B is control-dependent on A if:
        1. There's an edge A -> X where X is on a path to B
        2. B post-dominates X but not A
        """
        for node_id, cfg_node in cfg.nodes.items():
            if cfg_node.node_type in (CFGNodeType.CONDITION, CFGNodeType.LOOP_HEADER):
                # This is a predicate node
                for succ_id in cfg.successors.get(node_id, []):
                    # Find nodes control-dependent on this branch
                    self._find_control_dependent_nodes(
                        cfg, pdg, node_id, succ_id, post_doms
                    )
        
        # Entry node: all nodes not control-dependent on anything depend on entry
        if cfg.entry_node:
            for pdg_node_id, pdg_node in pdg.nodes.items():
                if not pdg_node.control_dependencies:
                    if pdg_node_id != cfg.entry_node.id:
                        pdg_node.control_dependencies.add(cfg.entry_node.id)
                        pdg.add_edge(PDGEdge(
                            source_id=cfg.entry_node.id,
                            target_id=pdg_node_id,
                            dependence_type=DependenceType.CONTROL,
                            label="entry"
                        ))
    
    def _find_control_dependent_nodes(self, cfg: ControlFlowGraph,
                                       pdg: ProgramDependenceGraph,
                                       pred_id: str, branch_id: str,
                                       post_doms: Dict[str, Set[str]]):
        """Find all nodes control-dependent on a predicate via a branch."""
        # Nodes reachable from branch but not post-dominated by predicate
        pred_post_doms = post_doms.get(pred_id, set())
        
        # Walk from branch_id
        visited = set()
        stack = [branch_id]
        
        while stack:
            node_id = stack.pop()
            if node_id in visited:
                continue
            visited.add(node_id)
            
            # Check if this node is control-dependent on pred
            node_post_doms = post_doms.get(node_id, set())
            if pred_id not in node_post_doms:
                # B is control-dependent on A
                pdg_node = pdg.nodes.get(node_id)
                if pdg_node:
                    pdg_node.control_dependencies.add(pred_id)
                    pdg.add_edge(PDGEdge(
                        source_id=pred_id,
                        target_id=node_id,
                        dependence_type=DependenceType.CONTROL,
                        label="branch"
                    ))
                
                # Continue exploring
                for succ_id in cfg.successors.get(node_id, []):
                    if succ_id not in visited:
                        stack.append(succ_id)
    
    def _compute_reaching_definitions(self, cfg: ControlFlowGraph,
                                       pdg: ProgramDependenceGraph) -> Dict[str, Dict[str, Set[str]]]:
        """
        Compute reaching definitions using dataflow analysis.
        
        For each node, compute which definitions reach that point.
        
        Returns:
            Dict[node_id, Dict[variable, Set[defining_node_ids]]]
        """
        # Initialize
        reaching = {}
        for node_id in cfg.nodes:
            reaching[node_id] = {}
        
        # Generate and kill sets
        gen_sets = {}
        kill_sets = {}
        
        for node_id, pdg_node in pdg.nodes.items():
            gen_sets[node_id] = {}
            kill_sets[node_id] = set()
            
            for var in pdg_node.defined_vars:
                gen_sets[node_id][var] = {node_id}
                kill_sets[node_id].add(var)
        
        # Worklist algorithm
        if not cfg.entry_node:
            return reaching
        
        worklist = [cfg.entry_node.id]
        
        while worklist:
            node_id = worklist.pop(0)
            
            # Compute IN set (union of predecessor OUT sets)
            in_set = {}
            for pred_id in cfg.predecessors.get(node_id, []):
                pred_reach = reaching.get(pred_id, {})
                for var, defs in pred_reach.items():
                    if var not in in_set:
                        in_set[var] = set()
                    in_set[var].update(defs)
            
            # Compute OUT set: gen ∪ (in - kill)
            out_set = {}
            
            # First, copy in_set
            for var, defs in in_set.items():
                out_set[var] = defs.copy()
            
            # Kill definitions
            for var in kill_sets.get(node_id, set()):
                if var in out_set:
                    out_set[var] = set()
            
            # Add gen
            for var, defs in gen_sets.get(node_id, {}).items():
                if var not in out_set:
                    out_set[var] = set()
                out_set[var].update(defs)
            
            # Check if changed
            if out_set != reaching.get(node_id, {}):
                reaching[node_id] = out_set
                # Add successors to worklist
                for succ_id in cfg.successors.get(node_id, []):
                    if succ_id not in worklist:
                        worklist.append(succ_id)
        
        return reaching
    
    def _build_data_dependencies(self, cfg: ControlFlowGraph,
                                  pdg: ProgramDependenceGraph,
                                  reaching_defs: Dict[str, Dict[str, Set[str]]]):
        """
        Build data dependence edges based on reaching definitions.
        
        For each use of a variable, create edges from all reaching definitions.
        """
        for node_id, pdg_node in pdg.nodes.items():
            # Compute IN set for this node (what reaches before execution)
            in_set = {}
            for pred_id in cfg.predecessors.get(node_id, []):
                pred_reach = reaching_defs.get(pred_id, {})
                for var, defs in pred_reach.items():
                    if var not in in_set:
                        in_set[var] = set()
                    in_set[var].update(defs)
            
            # For each used variable
            for var in pdg_node.used_vars:
                if var in in_set:
                    # Create data dependence from each reaching def
                    pdg_node.data_dependencies[var] = in_set[var].copy()
                    
                    for def_node_id in in_set[var]:
                        pdg.add_edge(PDGEdge(
                            source_id=def_node_id,
                            target_id=node_id,
                            dependence_type=DependenceType.DATA_FLOW,
                            variable=var,
                            label=f"def-use: {var}"
                        ))
            
            # Output dependencies (def-def)
            for var in pdg_node.defined_vars:
                if var in in_set:
                    for prev_def_id in in_set[var]:
                        if prev_def_id != node_id:
                            pdg.add_edge(PDGEdge(
                                source_id=prev_def_id,
                                target_id=node_id,
                                dependence_type=DependenceType.DATA_OUTPUT,
                                variable=var,
                                label=f"def-def: {var}"
                            ))
    
    def _build_def_use_chains(self, pdg: ProgramDependenceGraph):
        """Build complete def-use chains for analysis."""
        for node_id, pdg_node in pdg.nodes.items():
            for var in pdg_node.defined_vars:
                if var not in pdg.def_use_chains:
                    pdg.def_use_chains[var] = []
                
                # Find all uses of this definition
                def_use = DefUseInfo(
                    variable=var,
                    def_node_id=node_id,
                    def_line=pdg_node.cfg_node.line_start
                )
                
                # Search for uses
                for edge in pdg.data_edges:
                    if (edge.source_id == node_id and 
                        edge.variable == var and 
                        edge.dependence_type == DependenceType.DATA_FLOW):
                        use_node = pdg.nodes.get(edge.target_id)
                        if use_node:
                            def_use.use_nodes.append(
                                (edge.target_id, use_node.cfg_node.line_start)
                            )
                
                pdg.def_use_chains[var].append(def_use)


class TaintPDGAnalyzer:
    """
    Taint analysis using PDG for precise tracking.
    
    Combines:
    - PDG data dependencies for precise flow tracking
    - Control dependencies for implicit flows
    - Path conditions for path-sensitive analysis
    """
    
    # Sources - functions/expressions that introduce tainted data
    SOURCES = {
        'python': {
            'request.args', 'request.form', 'request.data', 'request.json',
            'request.cookies', 'request.headers', 'request.values',
            'input', 'raw_input', 'sys.stdin.read', 'sys.stdin.readline',
            'os.environ', 'os.getenv',
        },
        'javascript': {
            'req.body', 'req.query', 'req.params', 'req.cookies',
            'process.env', 'window.location', 'document.URL',
            'document.cookie', 'localStorage', 'sessionStorage',
        }
    }
    
    # Sinks - dangerous functions
    SINKS = {
        'os.system', 'subprocess.call', 'subprocess.run', 'subprocess.Popen',
        'eval', 'exec', 'compile',
        'cursor.execute', 'db.execute', 'execute',
        'render_template_string', 'Markup',
        'open', 'send_file',
        'redirect', 'requests.get', 'requests.post',
    }
    
    # Sanitizers
    SANITIZERS = {
        'escape', 'html.escape', 'markupsafe.escape',
        'quote', 'shlex.quote',
        'int', 'float', 'str',
        'parameterized query',
    }
    
    def __init__(self):
        self.pdg_generator = PDGGenerator()
    
    def analyze_pdg(self, pdg: ProgramDependenceGraph) -> List[Dict]:
        """
        Perform taint analysis on a PDG.
        
        Returns:
            List of taint flow findings
        """
        findings = []
        
        # Find source nodes
        source_nodes = self._find_source_nodes(pdg)
        
        # Find sink nodes
        sink_nodes = self._find_sink_nodes(pdg)
        
        # For each source, check if it can reach any sink
        for source_id, source_var in source_nodes:
            # Forward slice from source
            slice_nodes = pdg.get_forward_slice(source_id, {source_var} if source_var else None)
            
            for sink_id, sink_name in sink_nodes:
                if sink_id in slice_nodes:
                    # Found potential flow
                    # Get the path
                    paths = pdg.get_data_flow_paths(
                        source_var or "", source_id, sink_id
                    )
                    
                    # Check for sanitizers
                    is_sanitized = self._check_sanitization(pdg, paths)
                    
                    source_node = pdg.nodes.get(source_id)
                    sink_node = pdg.nodes.get(sink_id)
                    
                    finding = {
                        'type': 'taint_flow',
                        'source': {
                            'node_id': source_id,
                            'line': source_node.cfg_node.line_start if source_node else 0,
                            'code': source_node.cfg_node.code if source_node else '',
                            'variable': source_var
                        },
                        'sink': {
                            'node_id': sink_id,
                            'line': sink_node.cfg_node.line_start if sink_node else 0,
                            'code': sink_node.cfg_node.code if sink_node else '',
                            'function': sink_name
                        },
                        'path_length': len(paths[0]) if paths else 0,
                        'paths': [[pdg.nodes[n].cfg_node.code if n in pdg.nodes else n 
                                   for n in p] for p in paths[:3]],  # First 3 paths
                        'sanitized': is_sanitized,
                        'confidence': 0.5 if is_sanitized else 0.9,
                        'file': pdg.file_path
                    }
                    findings.append(finding)
        
        return findings
    
    def _find_source_nodes(self, pdg: ProgramDependenceGraph) -> List[Tuple[str, Optional[str]]]:
        """Find nodes that introduce tainted data."""
        sources = []
        
        all_sources = set()
        for lang_sources in self.SOURCES.values():
            all_sources.update(lang_sources)
        
        for node_id, pdg_node in pdg.nodes.items():
            code = pdg_node.cfg_node.code.lower()
            
            for source in all_sources:
                if source.lower() in code:
                    # Extract the variable being assigned
                    var = None
                    for def_var in pdg_node.defined_vars:
                        var = def_var
                        break
                    sources.append((node_id, var))
                    break
        
        return sources
    
    def _find_sink_nodes(self, pdg: ProgramDependenceGraph) -> List[Tuple[str, str]]:
        """Find nodes that call dangerous functions."""
        sinks = []
        
        for node_id, pdg_node in pdg.nodes.items():
            cfg_node = pdg_node.cfg_node
            
            if cfg_node.called_function:
                for sink in self.SINKS:
                    if sink in cfg_node.called_function.lower():
                        sinks.append((node_id, cfg_node.called_function))
                        break
            else:
                code = cfg_node.code.lower()
                for sink in self.SINKS:
                    if sink.lower() in code:
                        sinks.append((node_id, sink))
                        break
        
        return sinks
    
    def _check_sanitization(self, pdg: ProgramDependenceGraph, 
                            paths: List[List[str]]) -> bool:
        """Check if any path is sanitized."""
        for path in paths:
            path_sanitized = False
            for node_id in path:
                node = pdg.nodes.get(node_id)
                if node:
                    code = node.cfg_node.code.lower()
                    for sanitizer in self.SANITIZERS:
                        if sanitizer.lower() in code:
                            path_sanitized = True
                            break
                if path_sanitized:
                    break
            
            if not path_sanitized:
                # At least one path is not sanitized
                return False
        
        return True if paths else False


def generate_project_pdgs(project_path: str) -> Dict[str, ProgramDependenceGraph]:
    """
    Generate PDGs for all functions in a project.
    
    Returns:
        Dict mapping qualified function names to their PDGs
    """
    cfgs = build_project_cfgs(project_path)
    generator = PDGGenerator()
    pdgs = {}
    
    for name, cfg in cfgs.items():
        pdg = generator.generate_from_cfg(cfg)
        pdgs[name] = pdg
    
    return pdgs


def analyze_project_with_pdg(project_path: str) -> List[Dict]:
    """
    Analyze a project for security issues using PDG-based taint analysis.
    
    Returns:
        List of findings
    """
    pdgs = generate_project_pdgs(project_path)
    analyzer = TaintPDGAnalyzer()
    
    all_findings = []
    for name, pdg in pdgs.items():
        findings = analyzer.analyze_pdg(pdg)
        all_findings.extend(findings)
    
    return all_findings
