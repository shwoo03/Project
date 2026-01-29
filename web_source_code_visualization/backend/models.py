from typing import List, Optional, Literal
from pydantic import BaseModel, Field

# Parameter source types
ParameterSource = Literal[
    'query', 'body', 'path', 'header', 'cookie', 'unknown', 'arg',
    # JavaScript additional sources
    'url', 'url_query', 'url_hash', 'url_path', 'referrer', 'window_name',
    'local_storage', 'session_storage', 'form', 'file'
]

# Endpoint node types
EndpointType = Literal[
    'root', 'child', 'input', 'call', 'default', 'database', 'cluster',
    # Security analysis types
    'sink', 'api_call', 'event_handler', 'taint_flow', 'source'
]

class Parameter(BaseModel):
    name: str
    type: Optional[str] = None
    source: ParameterSource = 'unknown'

class TaintFlowEdge(BaseModel):
    """Represents a taint flow from source to sink for visualization."""
    id: str
    source_node_id: str  # ID of the source node (input)
    sink_node_id: str    # ID of the sink node
    source_name: str     # Variable name at source
    sink_name: str       # Function name at sink
    vulnerability_type: str  # SQLI, XSS, CMDI, etc.
    severity: str = "HIGH"   # HIGH, MEDIUM, LOW
    path: List[str] = []     # Variable flow path
    sanitized: bool = False
    sanitizer: Optional[str] = None

class EndpointNodes(BaseModel):
    id: str
    path: str
    method: str = "ALL"
    language: str
    file_path: str
    line_number: int
    end_line_number: int = 0
    params: List[Parameter] = []
    children: List['EndpointNodes'] = []
    depth: int = 1
    type: EndpointType = 'root' 
    filters: List[dict] = []
    sanitization: List[dict] = []
    template_context: List[dict] = []
    template_usage: List[dict] = []
    metadata: dict = {}

    class Config:
        populate_by_name = True

class ProjectStructure(BaseModel):
    root_path: str
    language_stats: dict[str, int]
    endpoints: List[EndpointNodes]
    taint_flows: List[TaintFlowEdge] = []  # Taint flow edges for visualization
    call_graph: Optional['CallGraphData'] = None  # Call graph data


class CallGraphNode(BaseModel):
    """Represents a function/method in the call graph."""
    id: str
    name: str
    qualified_name: str  # module.class.method
    file_path: str
    line_number: int
    end_line: int = 0
    node_type: str = "function"  # function, method, class, module
    is_entry_point: bool = False  # Route handlers, main, etc.
    is_sink: bool = False  # Dangerous functions
    callers: List[str] = []  # List of node IDs that call this
    callees: List[str] = []  # List of node IDs this calls


class CallGraphEdge(BaseModel):
    """Represents a call relationship in the call graph."""
    id: str
    source_id: str  # Caller node ID
    target_id: str  # Callee node ID
    call_site_line: int  # Line number where the call occurs
    call_type: str = "direct"  # direct, callback, async, decorator


class CallGraphData(BaseModel):
    """Complete call graph data for a project."""
    nodes: List[CallGraphNode] = []
    edges: List[CallGraphEdge] = []
    entry_points: List[str] = []  # Node IDs of entry points
    sinks: List[str] = []  # Node IDs of dangerous sinks
