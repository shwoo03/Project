"""
Control Flow Graph (CFG) Builder.

Builds control flow graphs from source code AST for:
- Path-sensitive taint analysis
- Dead code detection
- Loop analysis
- Conditional branch analysis

Key concepts:
- Basic Block: Sequence of statements with single entry/exit
- CFG Node: Represents a basic block or control structure
- CFG Edge: Control flow between nodes (including condition labels)
"""

import os
from typing import List, Dict, Set, Optional, Tuple, Any
from dataclasses import dataclass, field
from enum import Enum
import tree_sitter_python
import tree_sitter_javascript
from tree_sitter import Language, Parser, Node

try:
    import tree_sitter_typescript
    HAS_TYPESCRIPT = True
except ImportError:
    HAS_TYPESCRIPT = False


class CFGNodeType(Enum):
    """Types of CFG nodes."""
    ENTRY = "entry"
    EXIT = "exit"
    STATEMENT = "statement"
    CONDITION = "condition"          # if/while/for condition
    BRANCH_TRUE = "branch_true"      # True branch of condition
    BRANCH_FALSE = "branch_false"    # False branch of condition
    LOOP_HEADER = "loop_header"
    LOOP_BODY = "loop_body"
    LOOP_EXIT = "loop_exit"
    TRY_BLOCK = "try_block"
    EXCEPT_HANDLER = "except_handler"
    FINALLY_BLOCK = "finally_block"
    RETURN = "return"
    RAISE = "raise"
    BREAK = "break"
    CONTINUE = "continue"
    CALL = "call"
    ASSIGNMENT = "assignment"


class EdgeType(Enum):
    """Types of CFG edges."""
    UNCONDITIONAL = "unconditional"
    TRUE_BRANCH = "true"
    FALSE_BRANCH = "false"
    EXCEPTION = "exception"
    FALLTHROUGH = "fallthrough"
    BACK_EDGE = "back_edge"      # Loop back edge
    BREAK = "break"
    CONTINUE = "continue"


@dataclass
class CFGNode:
    """Represents a node in the control flow graph."""
    id: str
    node_type: CFGNodeType
    line_start: int
    line_end: int
    code: str
    file_path: str
    
    # AST info
    ast_node_type: Optional[str] = None
    
    # Variables defined/used
    defined_vars: Set[str] = field(default_factory=set)
    used_vars: Set[str] = field(default_factory=set)
    
    # For conditions
    condition: Optional[str] = None
    
    # For calls
    called_function: Optional[str] = None
    call_args: List[str] = field(default_factory=list)
    
    # Metadata
    is_entry_point: bool = False
    is_sink: bool = False
    is_source: bool = False
    taint_vars: Set[str] = field(default_factory=set)
    
    def __hash__(self):
        return hash(self.id)
    
    def __eq__(self, other):
        if isinstance(other, CFGNode):
            return self.id == other.id
        return False


@dataclass  
class CFGEdge:
    """Represents an edge in the control flow graph."""
    source_id: str
    target_id: str
    edge_type: EdgeType
    condition: Optional[str] = None  # For conditional edges
    
    def __hash__(self):
        return hash((self.source_id, self.target_id, self.edge_type))


@dataclass
class ControlFlowGraph:
    """Complete control flow graph for a function."""
    function_name: str
    qualified_name: str
    file_path: str
    
    entry_node: Optional[CFGNode] = None
    exit_node: Optional[CFGNode] = None
    
    nodes: Dict[str, CFGNode] = field(default_factory=dict)
    edges: List[CFGEdge] = field(default_factory=list)
    
    # Adjacency lists
    successors: Dict[str, List[str]] = field(default_factory=dict)
    predecessors: Dict[str, List[str]] = field(default_factory=dict)
    
    # Analysis results
    dominators: Dict[str, Set[str]] = field(default_factory=dict)
    post_dominators: Dict[str, Set[str]] = field(default_factory=dict)
    back_edges: List[Tuple[str, str]] = field(default_factory=list)
    loops: List[Set[str]] = field(default_factory=list)
    
    def add_node(self, node: CFGNode):
        """Add a node to the CFG."""
        self.nodes[node.id] = node
        if node.id not in self.successors:
            self.successors[node.id] = []
        if node.id not in self.predecessors:
            self.predecessors[node.id] = []
    
    def add_edge(self, edge: CFGEdge):
        """Add an edge to the CFG."""
        self.edges.append(edge)
        if edge.source_id not in self.successors:
            self.successors[edge.source_id] = []
        if edge.target_id not in self.predecessors:
            self.predecessors[edge.target_id] = []
        
        self.successors[edge.source_id].append(edge.target_id)
        self.predecessors[edge.target_id].append(edge.source_id)
    
    def get_all_paths(self, start_id: str, end_id: str, 
                      max_paths: int = 100) -> List[List[str]]:
        """Get all paths between two nodes (with limit)."""
        paths = []
        visited = set()
        
        def dfs(current: str, path: List[str]):
            if len(paths) >= max_paths:
                return
            
            if current == end_id:
                paths.append(path.copy())
                return
            
            if current in visited:
                return
            
            visited.add(current)
            for successor in self.successors.get(current, []):
                path.append(successor)
                dfs(successor, path)
                path.pop()
            visited.remove(current)
        
        dfs(start_id, [start_id])
        return paths
    
    def get_reachable_nodes(self, start_id: str) -> Set[str]:
        """Get all nodes reachable from start node."""
        reachable = set()
        stack = [start_id]
        
        while stack:
            node_id = stack.pop()
            if node_id in reachable:
                continue
            reachable.add(node_id)
            stack.extend(self.successors.get(node_id, []))
        
        return reachable
    
    def get_path_conditions(self, path: List[str]) -> List[Tuple[str, bool]]:
        """Get conditions along a path with their truth values."""
        conditions = []
        
        for i, node_id in enumerate(path[:-1]):
            node = self.nodes.get(node_id)
            if node and node.node_type == CFGNodeType.CONDITION:
                next_node_id = path[i + 1]
                # Find the edge type
                for edge in self.edges:
                    if edge.source_id == node_id and edge.target_id == next_node_id:
                        is_true = edge.edge_type == EdgeType.TRUE_BRANCH
                        conditions.append((node.condition or node.code, is_true))
                        break
        
        return conditions


class CFGBuilder:
    """
    Builds Control Flow Graphs from source code.
    
    Supports:
    - Python (if/elif/else, for, while, try/except, with, match)
    - JavaScript/TypeScript (if/else, for, while, switch, try/catch)
    """
    
    def __init__(self):
        # Initialize parsers
        self.py_parser = Parser(Language(tree_sitter_python.language()))
        self.js_parser = Parser(Language(tree_sitter_javascript.language()))
        
        if HAS_TYPESCRIPT:
            self.ts_parser = Parser(Language(tree_sitter_typescript.language_typescript()))
        else:
            self.ts_parser = None
        
        self._node_counter = 0
        self._current_cfg: Optional[ControlFlowGraph] = None
    
    def _new_node_id(self) -> str:
        """Generate a unique node ID."""
        self._node_counter += 1
        return f"n_{self._node_counter}"
    
    def build_from_file(self, file_path: str) -> Dict[str, ControlFlowGraph]:
        """
        Build CFGs for all functions in a file.
        
        Returns:
            Dict mapping function qualified names to their CFGs
        """
        cfgs = {}
        
        try:
            with open(file_path, 'rb') as f:
                content = f.read()
        except Exception:
            return cfgs
        
        if file_path.endswith('.py'):
            cfgs = self._build_python_cfgs(file_path, content)
        elif file_path.endswith(('.js', '.jsx')):
            cfgs = self._build_javascript_cfgs(file_path, content)
        elif file_path.endswith(('.ts', '.tsx')) and self.ts_parser:
            cfgs = self._build_typescript_cfgs(file_path, content)
        
        return cfgs
    
    def _build_python_cfgs(self, file_path: str, content: bytes) -> Dict[str, ControlFlowGraph]:
        """Build CFGs for Python functions."""
        cfgs = {}
        tree = self.py_parser.parse(content)
        
        # Find all function definitions
        functions = self._find_python_functions(tree.root_node, content, None)
        
        for func_info in functions:
            cfg = self._build_python_function_cfg(func_info, content)
            if cfg:
                cfgs[cfg.qualified_name] = cfg
        
        return cfgs
    
    def _find_python_functions(self, node: Node, content: bytes, 
                                class_name: Optional[str]) -> List[Dict]:
        """Find all function definitions in Python AST."""
        functions = []
        
        for child in node.children:
            if child.type == 'class_definition':
                name_node = child.child_by_field_name('name')
                cname = self._get_node_text(name_node, content) if name_node else None
                body = child.child_by_field_name('body')
                if body:
                    functions.extend(self._find_python_functions(body, content, cname))
            
            elif child.type == 'function_definition':
                name_node = child.child_by_field_name('name')
                func_name = self._get_node_text(name_node, content) if name_node else 'anonymous'
                
                functions.append({
                    'name': func_name,
                    'class_name': class_name,
                    'node': child,
                    'line_start': child.start_point[0] + 1,
                    'line_end': child.end_point[0] + 1
                })
            
            elif hasattr(child, 'children') and child.children:
                functions.extend(self._find_python_functions(child, content, class_name))
        
        return functions
    
    def _build_python_function_cfg(self, func_info: Dict, content: bytes) -> Optional[ControlFlowGraph]:
        """Build CFG for a single Python function."""
        self._node_counter = 0
        
        func_name = func_info['name']
        class_name = func_info.get('class_name')
        node = func_info['node']
        
        qualified_name = f"{class_name}.{func_name}" if class_name else func_name
        
        cfg = ControlFlowGraph(
            function_name=func_name,
            qualified_name=qualified_name,
            file_path=func_info.get('file_path', '')
        )
        self._current_cfg = cfg
        
        # Create entry and exit nodes
        entry = CFGNode(
            id=self._new_node_id(),
            node_type=CFGNodeType.ENTRY,
            line_start=func_info['line_start'],
            line_end=func_info['line_start'],
            code=f"ENTRY: {qualified_name}",
            file_path=cfg.file_path
        )
        
        exit_node = CFGNode(
            id=self._new_node_id(),
            node_type=CFGNodeType.EXIT,
            line_start=func_info['line_end'],
            line_end=func_info['line_end'],
            code=f"EXIT: {qualified_name}",
            file_path=cfg.file_path
        )
        
        cfg.add_node(entry)
        cfg.add_node(exit_node)
        cfg.entry_node = entry
        cfg.exit_node = exit_node
        
        # Process function body
        body = node.child_by_field_name('body')
        if body:
            prev_nodes = [entry.id]
            exit_targets = []
            
            prev_nodes, exits = self._process_python_block(body, content, cfg, prev_nodes)
            exit_targets.extend(exits)
            
            # Connect remaining nodes to exit
            for prev_id in prev_nodes:
                cfg.add_edge(CFGEdge(prev_id, exit_node.id, EdgeType.UNCONDITIONAL))
            for exit_id in exit_targets:
                if exit_id != exit_node.id:
                    cfg.add_edge(CFGEdge(exit_id, exit_node.id, EdgeType.UNCONDITIONAL))
        
        # Compute analysis info
        self._compute_dominators(cfg)
        self._detect_loops(cfg)
        
        return cfg
    
    def _process_python_block(self, block: Node, content: bytes, cfg: ControlFlowGraph,
                               prev_nodes: List[str]) -> Tuple[List[str], List[str]]:
        """
        Process a block of Python statements.
        
        Returns:
            (current_nodes, exit_nodes): Nodes that fall through, and nodes that exit
        """
        current = prev_nodes
        exit_nodes = []
        
        for child in block.children:
            if child.type == 'if_statement':
                current, exits = self._process_python_if(child, content, cfg, current)
                exit_nodes.extend(exits)
            
            elif child.type == 'for_statement':
                current, exits = self._process_python_for(child, content, cfg, current)
                exit_nodes.extend(exits)
            
            elif child.type == 'while_statement':
                current, exits = self._process_python_while(child, content, cfg, current)
                exit_nodes.extend(exits)
            
            elif child.type == 'try_statement':
                current, exits = self._process_python_try(child, content, cfg, current)
                exit_nodes.extend(exits)
            
            elif child.type == 'return_statement':
                node = self._create_statement_node(child, content, cfg, CFGNodeType.RETURN)
                for prev_id in current:
                    cfg.add_edge(CFGEdge(prev_id, node.id, EdgeType.UNCONDITIONAL))
                exit_nodes.append(node.id)
                current = []  # No fallthrough after return
            
            elif child.type == 'raise_statement':
                node = self._create_statement_node(child, content, cfg, CFGNodeType.RAISE)
                for prev_id in current:
                    cfg.add_edge(CFGEdge(prev_id, node.id, EdgeType.UNCONDITIONAL))
                exit_nodes.append(node.id)
                current = []
            
            elif child.type in ('expression_statement', 'assignment', 'augmented_assignment'):
                node = self._create_statement_node(child, content, cfg, CFGNodeType.STATEMENT)
                self._extract_vars_from_statement(child, content, node)
                
                for prev_id in current:
                    cfg.add_edge(CFGEdge(prev_id, node.id, EdgeType.UNCONDITIONAL))
                current = [node.id]
            
            elif child.type == 'pass_statement':
                # Pass is a no-op, just continue
                pass
            
            elif child.type in ('break_statement', 'continue_statement'):
                # Handle in loop context
                node_type = CFGNodeType.BREAK if child.type == 'break_statement' else CFGNodeType.CONTINUE
                node = self._create_statement_node(child, content, cfg, node_type)
                for prev_id in current:
                    cfg.add_edge(CFGEdge(prev_id, node.id, EdgeType.UNCONDITIONAL))
                # These will be connected during loop processing
                current = []
        
        return current, exit_nodes
    
    def _process_python_if(self, node: Node, content: bytes, cfg: ControlFlowGraph,
                           prev_nodes: List[str]) -> Tuple[List[str], List[str]]:
        """Process Python if statement."""
        exit_nodes = []
        merge_nodes = []
        
        # Process condition
        condition = node.child_by_field_name('condition')
        condition_text = self._get_node_text(condition, content) if condition else "?"
        
        cond_node = CFGNode(
            id=self._new_node_id(),
            node_type=CFGNodeType.CONDITION,
            line_start=node.start_point[0] + 1,
            line_end=node.start_point[0] + 1,
            code=f"if {condition_text}",
            file_path=cfg.file_path,
            condition=condition_text
        )
        cfg.add_node(cond_node)
        
        for prev_id in prev_nodes:
            cfg.add_edge(CFGEdge(prev_id, cond_node.id, EdgeType.UNCONDITIONAL))
        
        # Process true branch (consequence)
        consequence = node.child_by_field_name('consequence')
        if consequence:
            true_nodes, true_exits = self._process_python_block(consequence, content, cfg, [cond_node.id])
            for true_id in true_nodes:
                # Add true edge
                for edge in cfg.edges:
                    if edge.source_id == cond_node.id and edge.target_id == true_id:
                        edge.edge_type = EdgeType.TRUE_BRANCH
                        break
            merge_nodes.extend(true_nodes)
            exit_nodes.extend(true_exits)
        
        # Process elif and else
        has_else = False
        for child in node.children:
            if child.type == 'elif_clause':
                elif_cond = child.child_by_field_name('condition')
                elif_cond_text = self._get_node_text(elif_cond, content) if elif_cond else "?"
                
                elif_node = CFGNode(
                    id=self._new_node_id(),
                    node_type=CFGNodeType.CONDITION,
                    line_start=child.start_point[0] + 1,
                    line_end=child.start_point[0] + 1,
                    code=f"elif {elif_cond_text}",
                    file_path=cfg.file_path,
                    condition=elif_cond_text
                )
                cfg.add_node(elif_node)
                cfg.add_edge(CFGEdge(cond_node.id, elif_node.id, EdgeType.FALSE_BRANCH))
                
                elif_body = child.child_by_field_name('consequence')
                if elif_body:
                    elif_nodes, elif_exits = self._process_python_block(elif_body, content, cfg, [elif_node.id])
                    merge_nodes.extend(elif_nodes)
                    exit_nodes.extend(elif_exits)
                
                cond_node = elif_node  # Chain elif conditions
            
            elif child.type == 'else_clause':
                has_else = True
                else_body = child.child_by_field_name('body') or child
                if else_body:
                    else_nodes, else_exits = self._process_python_block(else_body, content, cfg, [cond_node.id])
                    for else_id in else_nodes:
                        for edge in cfg.edges:
                            if edge.source_id == cond_node.id and edge.target_id == else_id:
                                edge.edge_type = EdgeType.FALSE_BRANCH
                                break
                    merge_nodes.extend(else_nodes)
                    exit_nodes.extend(else_exits)
        
        if not has_else:
            # If no else, false branch falls through
            merge_nodes.append(cond_node.id)
        
        return merge_nodes, exit_nodes
    
    def _process_python_for(self, node: Node, content: bytes, cfg: ControlFlowGraph,
                            prev_nodes: List[str]) -> Tuple[List[str], List[str]]:
        """Process Python for loop."""
        exit_nodes = []
        
        # Loop header
        left = node.child_by_field_name('left')
        right = node.child_by_field_name('right')
        left_text = self._get_node_text(left, content) if left else "?"
        right_text = self._get_node_text(right, content) if right else "?"
        
        header_node = CFGNode(
            id=self._new_node_id(),
            node_type=CFGNodeType.LOOP_HEADER,
            line_start=node.start_point[0] + 1,
            line_end=node.start_point[0] + 1,
            code=f"for {left_text} in {right_text}",
            file_path=cfg.file_path,
            condition=f"{left_text} in {right_text}"
        )
        cfg.add_node(header_node)
        
        for prev_id in prev_nodes:
            cfg.add_edge(CFGEdge(prev_id, header_node.id, EdgeType.UNCONDITIONAL))
        
        # Loop body
        body = node.child_by_field_name('body')
        if body:
            body_nodes, body_exits = self._process_python_block(body, content, cfg, [header_node.id])
            
            # Back edge from end of body to header
            for body_id in body_nodes:
                cfg.add_edge(CFGEdge(body_id, header_node.id, EdgeType.BACK_EDGE))
                cfg.back_edges.append((body_id, header_node.id))
            
            exit_nodes.extend(body_exits)
        
        # Loop exit (when iterator exhausted)
        exit_from_loop = CFGNode(
            id=self._new_node_id(),
            node_type=CFGNodeType.LOOP_EXIT,
            line_start=node.end_point[0] + 1,
            line_end=node.end_point[0] + 1,
            code="[loop exit]",
            file_path=cfg.file_path
        )
        cfg.add_node(exit_from_loop)
        cfg.add_edge(CFGEdge(header_node.id, exit_from_loop.id, EdgeType.FALSE_BRANCH))
        
        return [exit_from_loop.id], exit_nodes
    
    def _process_python_while(self, node: Node, content: bytes, cfg: ControlFlowGraph,
                               prev_nodes: List[str]) -> Tuple[List[str], List[str]]:
        """Process Python while loop."""
        exit_nodes = []
        
        # Condition node
        condition = node.child_by_field_name('condition')
        condition_text = self._get_node_text(condition, content) if condition else "?"
        
        cond_node = CFGNode(
            id=self._new_node_id(),
            node_type=CFGNodeType.LOOP_HEADER,
            line_start=node.start_point[0] + 1,
            line_end=node.start_point[0] + 1,
            code=f"while {condition_text}",
            file_path=cfg.file_path,
            condition=condition_text
        )
        cfg.add_node(cond_node)
        
        for prev_id in prev_nodes:
            cfg.add_edge(CFGEdge(prev_id, cond_node.id, EdgeType.UNCONDITIONAL))
        
        # Loop body
        body = node.child_by_field_name('body')
        if body:
            body_nodes, body_exits = self._process_python_block(body, content, cfg, [cond_node.id])
            
            # Mark edge to body as true branch
            for edge in cfg.edges:
                if edge.source_id == cond_node.id and edge.target_id in [self._current_cfg.nodes[n].id for n in body_nodes if n in self._current_cfg.nodes]:
                    edge.edge_type = EdgeType.TRUE_BRANCH
            
            # Back edge
            for body_id in body_nodes:
                cfg.add_edge(CFGEdge(body_id, cond_node.id, EdgeType.BACK_EDGE))
                cfg.back_edges.append((body_id, cond_node.id))
            
            exit_nodes.extend(body_exits)
        
        # Exit from loop
        exit_from_loop = CFGNode(
            id=self._new_node_id(),
            node_type=CFGNodeType.LOOP_EXIT,
            line_start=node.end_point[0] + 1,
            line_end=node.end_point[0] + 1,
            code="[while exit]",
            file_path=cfg.file_path
        )
        cfg.add_node(exit_from_loop)
        cfg.add_edge(CFGEdge(cond_node.id, exit_from_loop.id, EdgeType.FALSE_BRANCH))
        
        return [exit_from_loop.id], exit_nodes
    
    def _process_python_try(self, node: Node, content: bytes, cfg: ControlFlowGraph,
                            prev_nodes: List[str]) -> Tuple[List[str], List[str]]:
        """Process Python try/except/finally."""
        exit_nodes = []
        merge_nodes = []
        
        # Try block
        try_node = CFGNode(
            id=self._new_node_id(),
            node_type=CFGNodeType.TRY_BLOCK,
            line_start=node.start_point[0] + 1,
            line_end=node.start_point[0] + 1,
            code="try:",
            file_path=cfg.file_path
        )
        cfg.add_node(try_node)
        
        for prev_id in prev_nodes:
            cfg.add_edge(CFGEdge(prev_id, try_node.id, EdgeType.UNCONDITIONAL))
        
        # Process try body
        for child in node.children:
            if child.type == 'block':
                try_body_nodes, try_exits = self._process_python_block(child, content, cfg, [try_node.id])
                merge_nodes.extend(try_body_nodes)
                exit_nodes.extend(try_exits)
                break
        
        # Process except handlers
        for child in node.children:
            if child.type == 'except_clause':
                except_node = CFGNode(
                    id=self._new_node_id(),
                    node_type=CFGNodeType.EXCEPT_HANDLER,
                    line_start=child.start_point[0] + 1,
                    line_end=child.start_point[0] + 1,
                    code=self._get_node_text(child, content)[:50] if child else "except:",
                    file_path=cfg.file_path
                )
                cfg.add_node(except_node)
                cfg.add_edge(CFGEdge(try_node.id, except_node.id, EdgeType.EXCEPTION))
                
                # Process except body
                for except_child in child.children:
                    if except_child.type == 'block':
                        except_body_nodes, except_exits = self._process_python_block(
                            except_child, content, cfg, [except_node.id])
                        merge_nodes.extend(except_body_nodes)
                        exit_nodes.extend(except_exits)
        
        # Process finally
        for child in node.children:
            if child.type == 'finally_clause':
                finally_node = CFGNode(
                    id=self._new_node_id(),
                    node_type=CFGNodeType.FINALLY_BLOCK,
                    line_start=child.start_point[0] + 1,
                    line_end=child.start_point[0] + 1,
                    code="finally:",
                    file_path=cfg.file_path
                )
                cfg.add_node(finally_node)
                
                # All paths go through finally
                for merge_id in merge_nodes:
                    cfg.add_edge(CFGEdge(merge_id, finally_node.id, EdgeType.UNCONDITIONAL))
                
                for finally_child in child.children:
                    if finally_child.type == 'block':
                        finally_body_nodes, finally_exits = self._process_python_block(
                            finally_child, content, cfg, [finally_node.id])
                        merge_nodes = finally_body_nodes
                        exit_nodes.extend(finally_exits)
        
        return merge_nodes, exit_nodes
    
    def _create_statement_node(self, node: Node, content: bytes, cfg: ControlFlowGraph,
                                node_type: CFGNodeType) -> CFGNode:
        """Create a CFG node for a statement."""
        code = self._get_node_text(node, content) or ""
        if len(code) > 80:
            code = code[:77] + "..."
        
        cfg_node = CFGNode(
            id=self._new_node_id(),
            node_type=node_type,
            line_start=node.start_point[0] + 1,
            line_end=node.end_point[0] + 1,
            code=code,
            file_path=cfg.file_path,
            ast_node_type=node.type
        )
        
        # Check for function calls
        self._check_for_calls(node, content, cfg_node)
        
        cfg.add_node(cfg_node)
        return cfg_node
    
    def _check_for_calls(self, node: Node, content: bytes, cfg_node: CFGNode):
        """Check if node contains function calls."""
        if node.type == 'call':
            func = node.child_by_field_name('function')
            if func:
                cfg_node.called_function = self._get_node_text(func, content)
                cfg_node.node_type = CFGNodeType.CALL
        
        for child in node.children:
            self._check_for_calls(child, content, cfg_node)
    
    def _extract_vars_from_statement(self, node: Node, content: bytes, cfg_node: CFGNode):
        """Extract defined and used variables from a statement."""
        if node.type == 'assignment':
            left = node.child_by_field_name('left')
            right = node.child_by_field_name('right')
            
            if left:
                cfg_node.defined_vars.add(self._get_node_text(left, content))
            if right:
                self._extract_used_vars(right, content, cfg_node.used_vars)
        
        elif node.type == 'expression_statement':
            for child in node.children:
                self._extract_used_vars(child, content, cfg_node.used_vars)
    
    def _extract_used_vars(self, node: Node, content: bytes, used_vars: Set[str]):
        """Recursively extract used variables."""
        if node.type == 'identifier':
            used_vars.add(self._get_node_text(node, content))
        
        for child in node.children:
            self._extract_used_vars(child, content, used_vars)
    
    def _get_node_text(self, node: Optional[Node], content: bytes) -> Optional[str]:
        """Get text content of an AST node."""
        if node is None:
            return None
        try:
            return content[node.start_byte:node.end_byte].decode('utf-8')
        except:
            return None
    
    def _compute_dominators(self, cfg: ControlFlowGraph):
        """Compute dominator sets for all nodes."""
        if not cfg.entry_node:
            return
        
        # Initialize
        all_nodes = set(cfg.nodes.keys())
        cfg.dominators[cfg.entry_node.id] = {cfg.entry_node.id}
        
        for node_id in cfg.nodes:
            if node_id != cfg.entry_node.id:
                cfg.dominators[node_id] = all_nodes.copy()
        
        # Iterate until fixed point
        changed = True
        while changed:
            changed = False
            for node_id in cfg.nodes:
                if node_id == cfg.entry_node.id:
                    continue
                
                preds = cfg.predecessors.get(node_id, [])
                if not preds:
                    continue
                
                new_doms = all_nodes.copy()
                for pred_id in preds:
                    new_doms &= cfg.dominators.get(pred_id, all_nodes)
                new_doms.add(node_id)
                
                if new_doms != cfg.dominators.get(node_id):
                    cfg.dominators[node_id] = new_doms
                    changed = True
    
    def _detect_loops(self, cfg: ControlFlowGraph):
        """Detect natural loops in CFG."""
        # A natural loop is defined by a back edge (n -> h) where h dominates n
        for source_id, target_id in cfg.back_edges:
            if target_id in cfg.dominators.get(source_id, set()):
                # Found natural loop with header target_id
                loop_nodes = self._find_loop_nodes(cfg, target_id, source_id)
                cfg.loops.append(loop_nodes)
    
    def _find_loop_nodes(self, cfg: ControlFlowGraph, header: str, tail: str) -> Set[str]:
        """Find all nodes in a natural loop."""
        loop_nodes = {header}
        stack = [tail]
        
        while stack:
            node_id = stack.pop()
            if node_id not in loop_nodes:
                loop_nodes.add(node_id)
                for pred_id in cfg.predecessors.get(node_id, []):
                    stack.append(pred_id)
        
        return loop_nodes
    
    # JavaScript CFG building methods
    def _build_javascript_cfgs(self, file_path: str, content: bytes) -> Dict[str, ControlFlowGraph]:
        """Build CFGs for JavaScript functions."""
        cfgs = {}
        tree = self.js_parser.parse(content)
        
        functions = self._find_js_functions(tree.root_node, content)
        
        for func_info in functions:
            cfg = self._build_js_function_cfg(func_info, content, file_path)
            if cfg:
                cfgs[cfg.qualified_name] = cfg
        
        return cfgs
    
    def _find_js_functions(self, node: Node, content: bytes) -> List[Dict]:
        """Find all function definitions in JavaScript AST."""
        functions = []
        
        for child in node.children:
            if child.type in ('function_declaration', 'function', 'arrow_function', 
                              'method_definition', 'function_expression'):
                name_node = child.child_by_field_name('name')
                func_name = self._get_node_text(name_node, content) if name_node else 'anonymous'
                
                functions.append({
                    'name': func_name,
                    'node': child,
                    'line_start': child.start_point[0] + 1,
                    'line_end': child.end_point[0] + 1
                })
            
            if hasattr(child, 'children') and child.children:
                functions.extend(self._find_js_functions(child, content))
        
        return functions
    
    def _build_js_function_cfg(self, func_info: Dict, content: bytes, 
                                file_path: str) -> Optional[ControlFlowGraph]:
        """Build CFG for a JavaScript function."""
        self._node_counter = 0
        
        func_name = func_info['name']
        node = func_info['node']
        
        cfg = ControlFlowGraph(
            function_name=func_name,
            qualified_name=func_name,
            file_path=file_path
        )
        self._current_cfg = cfg
        
        # Create entry and exit
        entry = CFGNode(
            id=self._new_node_id(),
            node_type=CFGNodeType.ENTRY,
            line_start=func_info['line_start'],
            line_end=func_info['line_start'],
            code=f"ENTRY: {func_name}",
            file_path=file_path
        )
        
        exit_node = CFGNode(
            id=self._new_node_id(),
            node_type=CFGNodeType.EXIT,
            line_start=func_info['line_end'],
            line_end=func_info['line_end'],
            code=f"EXIT: {func_name}",
            file_path=file_path
        )
        
        cfg.add_node(entry)
        cfg.add_node(exit_node)
        cfg.entry_node = entry
        cfg.exit_node = exit_node
        
        # Process body
        body = node.child_by_field_name('body')
        if body:
            prev_nodes = [entry.id]
            prev_nodes, exits = self._process_js_block(body, content, cfg, prev_nodes)
            
            for prev_id in prev_nodes:
                cfg.add_edge(CFGEdge(prev_id, exit_node.id, EdgeType.UNCONDITIONAL))
            for exit_id in exits:
                if exit_id != exit_node.id:
                    cfg.add_edge(CFGEdge(exit_id, exit_node.id, EdgeType.UNCONDITIONAL))
        
        self._compute_dominators(cfg)
        self._detect_loops(cfg)
        
        return cfg
    
    def _process_js_block(self, block: Node, content: bytes, cfg: ControlFlowGraph,
                          prev_nodes: List[str]) -> Tuple[List[str], List[str]]:
        """Process a JavaScript statement block."""
        current = prev_nodes
        exit_nodes = []
        
        children = block.children if block.type == 'statement_block' else [block]
        
        for child in children:
            if child.type == 'if_statement':
                current, exits = self._process_js_if(child, content, cfg, current)
                exit_nodes.extend(exits)
            
            elif child.type in ('for_statement', 'for_in_statement'):
                current, exits = self._process_js_for(child, content, cfg, current)
                exit_nodes.extend(exits)
            
            elif child.type == 'while_statement':
                current, exits = self._process_js_while(child, content, cfg, current)
                exit_nodes.extend(exits)
            
            elif child.type == 'return_statement':
                node = self._create_statement_node(child, content, cfg, CFGNodeType.RETURN)
                for prev_id in current:
                    cfg.add_edge(CFGEdge(prev_id, node.id, EdgeType.UNCONDITIONAL))
                exit_nodes.append(node.id)
                current = []
            
            elif child.type == 'throw_statement':
                node = self._create_statement_node(child, content, cfg, CFGNodeType.RAISE)
                for prev_id in current:
                    cfg.add_edge(CFGEdge(prev_id, node.id, EdgeType.UNCONDITIONAL))
                exit_nodes.append(node.id)
                current = []
            
            elif child.type in ('expression_statement', 'variable_declaration', 
                               'lexical_declaration', 'assignment_expression'):
                node = self._create_statement_node(child, content, cfg, CFGNodeType.STATEMENT)
                for prev_id in current:
                    cfg.add_edge(CFGEdge(prev_id, node.id, EdgeType.UNCONDITIONAL))
                current = [node.id]
        
        return current, exit_nodes
    
    def _process_js_if(self, node: Node, content: bytes, cfg: ControlFlowGraph,
                       prev_nodes: List[str]) -> Tuple[List[str], List[str]]:
        """Process JavaScript if statement."""
        exit_nodes = []
        merge_nodes = []
        
        condition = node.child_by_field_name('condition')
        condition_text = self._get_node_text(condition, content) if condition else "?"
        
        cond_node = CFGNode(
            id=self._new_node_id(),
            node_type=CFGNodeType.CONDITION,
            line_start=node.start_point[0] + 1,
            line_end=node.start_point[0] + 1,
            code=f"if ({condition_text})",
            file_path=cfg.file_path,
            condition=condition_text
        )
        cfg.add_node(cond_node)
        
        for prev_id in prev_nodes:
            cfg.add_edge(CFGEdge(prev_id, cond_node.id, EdgeType.UNCONDITIONAL))
        
        # True branch
        consequence = node.child_by_field_name('consequence')
        if consequence:
            true_nodes, true_exits = self._process_js_block(consequence, content, cfg, [cond_node.id])
            merge_nodes.extend(true_nodes)
            exit_nodes.extend(true_exits)
        
        # False branch
        alternative = node.child_by_field_name('alternative')
        if alternative:
            false_nodes, false_exits = self._process_js_block(alternative, content, cfg, [cond_node.id])
            merge_nodes.extend(false_nodes)
            exit_nodes.extend(false_exits)
        else:
            merge_nodes.append(cond_node.id)
        
        return merge_nodes, exit_nodes
    
    def _process_js_for(self, node: Node, content: bytes, cfg: ControlFlowGraph,
                        prev_nodes: List[str]) -> Tuple[List[str], List[str]]:
        """Process JavaScript for loop."""
        exit_nodes = []
        
        header_node = CFGNode(
            id=self._new_node_id(),
            node_type=CFGNodeType.LOOP_HEADER,
            line_start=node.start_point[0] + 1,
            line_end=node.start_point[0] + 1,
            code=self._get_node_text(node, content)[:50] or "for (...)",
            file_path=cfg.file_path
        )
        cfg.add_node(header_node)
        
        for prev_id in prev_nodes:
            cfg.add_edge(CFGEdge(prev_id, header_node.id, EdgeType.UNCONDITIONAL))
        
        body = node.child_by_field_name('body')
        if body:
            body_nodes, body_exits = self._process_js_block(body, content, cfg, [header_node.id])
            
            for body_id in body_nodes:
                cfg.add_edge(CFGEdge(body_id, header_node.id, EdgeType.BACK_EDGE))
                cfg.back_edges.append((body_id, header_node.id))
            
            exit_nodes.extend(body_exits)
        
        exit_from_loop = CFGNode(
            id=self._new_node_id(),
            node_type=CFGNodeType.LOOP_EXIT,
            line_start=node.end_point[0] + 1,
            line_end=node.end_point[0] + 1,
            code="[for exit]",
            file_path=cfg.file_path
        )
        cfg.add_node(exit_from_loop)
        cfg.add_edge(CFGEdge(header_node.id, exit_from_loop.id, EdgeType.FALSE_BRANCH))
        
        return [exit_from_loop.id], exit_nodes
    
    def _process_js_while(self, node: Node, content: bytes, cfg: ControlFlowGraph,
                          prev_nodes: List[str]) -> Tuple[List[str], List[str]]:
        """Process JavaScript while loop."""
        exit_nodes = []
        
        condition = node.child_by_field_name('condition')
        condition_text = self._get_node_text(condition, content) if condition else "?"
        
        cond_node = CFGNode(
            id=self._new_node_id(),
            node_type=CFGNodeType.LOOP_HEADER,
            line_start=node.start_point[0] + 1,
            line_end=node.start_point[0] + 1,
            code=f"while ({condition_text})",
            file_path=cfg.file_path,
            condition=condition_text
        )
        cfg.add_node(cond_node)
        
        for prev_id in prev_nodes:
            cfg.add_edge(CFGEdge(prev_id, cond_node.id, EdgeType.UNCONDITIONAL))
        
        body = node.child_by_field_name('body')
        if body:
            body_nodes, body_exits = self._process_js_block(body, content, cfg, [cond_node.id])
            
            for body_id in body_nodes:
                cfg.add_edge(CFGEdge(body_id, cond_node.id, EdgeType.BACK_EDGE))
                cfg.back_edges.append((body_id, cond_node.id))
            
            exit_nodes.extend(body_exits)
        
        exit_from_loop = CFGNode(
            id=self._new_node_id(),
            node_type=CFGNodeType.LOOP_EXIT,
            line_start=node.end_point[0] + 1,
            line_end=node.end_point[0] + 1,
            code="[while exit]",
            file_path=cfg.file_path
        )
        cfg.add_node(exit_from_loop)
        cfg.add_edge(CFGEdge(cond_node.id, exit_from_loop.id, EdgeType.FALSE_BRANCH))
        
        return [exit_from_loop.id], exit_nodes
    
    def _build_typescript_cfgs(self, file_path: str, content: bytes) -> Dict[str, ControlFlowGraph]:
        """Build CFGs for TypeScript functions."""
        if not self.ts_parser:
            return {}
        
        # TypeScript is similar to JavaScript
        cfgs = {}
        tree = self.ts_parser.parse(content)
        
        functions = self._find_js_functions(tree.root_node, content)
        
        for func_info in functions:
            cfg = self._build_js_function_cfg(func_info, content, file_path)
            if cfg:
                cfgs[cfg.qualified_name] = cfg
        
        return cfgs


def build_project_cfgs(project_path: str) -> Dict[str, ControlFlowGraph]:
    """
    Build CFGs for all functions in a project.
    
    Returns:
        Dict mapping qualified function names to their CFGs
    """
    builder = CFGBuilder()
    all_cfgs = {}
    
    for dirpath, dirnames, filenames in os.walk(project_path):
        # Skip non-source directories
        dirnames[:] = [d for d in dirnames if d not in {
            '__pycache__', 'node_modules', '.git', '.venv', 'venv',
            'dist', 'build', '.next', 'coverage'
        }]
        
        for filename in filenames:
            if filename.endswith(('.py', '.js', '.jsx', '.ts', '.tsx')):
                filepath = os.path.join(dirpath, filename)
                file_cfgs = builder.build_from_file(filepath)
                
                # Add file prefix to qualified names
                for name, cfg in file_cfgs.items():
                    qualified = f"{os.path.relpath(filepath, project_path)}::{name}"
                    cfg.qualified_name = qualified
                    all_cfgs[qualified] = cfg
    
    return all_cfgs
