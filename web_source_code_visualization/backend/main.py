import os
from typing import List, Optional, Any, Dict
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from dotenv import load_dotenv

from core.parser import ParserManager
from core.ai_analyzer import AIAnalyzer
from core.cluster_manager import ClusterManager
from core.taint_analyzer import TaintAnalyzer, TaintSource, TaintSink, detect_sink, TaintType
from core.call_graph_analyzer import CallGraphAnalyzer
from core.parallel_analyzer import ParallelAnalyzer
from core.analysis_cache import analysis_cache
from core.streaming_analyzer import streaming_analyzer, StreamEvent
from core.interprocedural_taint import InterProceduralTaintAnalyzer, analyze_interprocedural_taint
from core.import_resolver import ImportResolver, resolve_project_imports
from core.type_inferencer import TypeInferencer, analyze_project_types
from core.class_hierarchy import ClassHierarchyAnalyzer, analyze_class_hierarchy
from core.microservice_analyzer import MicroserviceAnalyzer, analyze_microservices, parse_openapi, parse_proto
from core.monorepo_analyzer import MonorepoAnalyzer, analyze_monorepo, get_project_details, get_dependency_graph, get_affected_projects
from core.lsp_client import (
    LSPManager, get_lsp_manager, start_lsp_servers, stop_lsp_servers,
    goto_definition, find_references, get_hover_info, get_completions,
    get_symbols, search_symbols, LANGUAGE_SERVERS
)
from core.ml_vulnerability_detector import (
    MLVulnerabilityDetector, get_ml_detector, analyze_with_ml,
    PredictionResult, VulnerabilityClass, Severity
)
from core.ml_false_positive_filter import (
    FalsePositiveFilter, get_fp_filter, apply_fp_filter
)
from core.llm_security_analyzer import (
    LLMSecurityAnalyzer, get_llm_security_analyzer,
    CodeContext as LLMCodeContext, LLMAnalysisResult, AnalysisType
)
from core.cfg_builder import CFGBuilder, ControlFlowGraph, build_project_cfgs
from core.pdg_generator import PDGGenerator, ProgramDependenceGraph, TaintPDGAnalyzer, generate_project_pdgs
from core.advanced_dataflow_analyzer import (
    AdvancedDataFlowAnalyzer, AnalysisSensitivity, 
    analyze_with_advanced_dataflow, get_dataflow_statistics
)
from models import ProjectStructure, EndpointNodes, TaintFlowEdge, CallGraphData

# Load .env from root directory
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(__file__)), '.env'))

app = FastAPI(title="Web Source Code Visualization API")

# CORS Setup
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"], 
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

parser_manager = ParserManager()
ai_analyzer = AIAnalyzer()
cluster_manager = ClusterManager()
call_graph_analyzer = CallGraphAnalyzer()
parallel_analyzer = ParallelAnalyzer()  # New parallel analyzer


def collect_taint_flows(endpoints: List[EndpointNodes]) -> List[TaintFlowEdge]:
    """
    Collect taint flow edges from parsed endpoints.
    Matches input sources to sinks within the same endpoint tree.
    """
    taint_flows = []
    flow_id = 0
    
    def find_sources_and_sinks(node: EndpointNodes, parent_id: str = None):
        """Recursively find sources (inputs) and sinks in endpoint tree."""
        sources = []
        sinks = []
        
        # Check if this node is a source (has params/inputs)
        if node.params:
            for param in node.params:
                sources.append({
                    "node_id": node.id,
                    "name": param.name,
                    "source_type": param.source,
                    "line": node.line_number
                })
        
        # Check if this node is a sink
        if node.type == "sink":
            sink_info = node.metadata.get("sink_type", "unknown")
            sinks.append({
                "node_id": node.id,
                "name": node.path.replace("⚠️ ", ""),
                "vulnerability_type": sink_info,
                "severity": node.metadata.get("severity", "MEDIUM"),
                "line": node.line_number,
                "args": node.metadata.get("args", [])
            })
        
        # Recursively check children
        for child in node.children:
            child_sources, child_sinks = find_sources_and_sinks(child, node.id)
            sources.extend(child_sources)
            sinks.extend(child_sinks)
        
        return sources, sinks
    
    # Process each endpoint
    for ep in endpoints:
        sources, sinks = find_sources_and_sinks(ep)
        
        # Create taint flow edges between sources and sinks
        for source in sources:
            for sink in sinks:
                flow_id += 1
                
                # Determine vulnerability type from sink
                vuln_type = sink.get("vulnerability_type", "general")
                if vuln_type == "dom_xss":
                    vuln_type = "XSS"
                elif vuln_type == "code_injection":
                    vuln_type = "CODE"
                
                taint_flows.append(TaintFlowEdge(
                    id=f"taint-{flow_id}",
                    source_node_id=source["node_id"],
                    sink_node_id=sink["node_id"],
                    source_name=source["name"],
                    sink_name=sink["name"],
                    vulnerability_type=vuln_type.upper(),
                    severity=sink.get("severity", "MEDIUM"),
                    path=[source["name"], sink["name"]],
                    sanitized=False
                ))
    
    return taint_flows

class AnalyzeRequest(BaseModel):
    path: str
    cluster: bool = False
    use_parallel: bool = True  # Enable parallel analysis by default

@app.post("/api/analyze", response_model=ProjectStructure)
def analyze_project(request: AnalyzeRequest):
    project_path = request.path
    if not os.path.exists(project_path):
        raise HTTPException(status_code=404, detail="Path not found")

    endpoints: List[EndpointNodes] = []
    language_stats = {}
    
    # Use parallel analyzer for better performance
    if request.use_parallel:
        try:
            endpoints, language_stats, symbol_table = parallel_analyzer.analyze_project(project_path)
            
            # Print stats
            stats = parallel_analyzer.get_stats()
            print(f"[API] Parallel analysis complete: {stats['parsed_files']}/{stats['total_files']} files, {stats['total_time_ms']:.1f}ms")
            
        except Exception as e:
            print(f"[API] Parallel analysis failed, falling back to sequential: {e}")
            # Fall back to sequential analysis
            request.use_parallel = False
    
    # Sequential analysis (fallback or when parallel is disabled)
    if not request.use_parallel:
        # 1. Collect all files first
        all_files = []
        try:
            # Normalize path for Unicode handling
            normalized_project_path = os.path.normpath(project_path)
            
            for root, _, files in os.walk(normalized_project_path):
                if "venv" in root or "node_modules" in root or ".git" in root:
                    continue
                for file in files:
                    try:
                        file_path = os.path.join(root, file)
                        # Verify file is accessible
                        if os.path.isfile(file_path) and os.access(file_path, os.R_OK):
                            all_files.append(file_path)
                    except (OSError, UnicodeDecodeError) as e:
                        print(f"[WARN] Skipping file {file}: {e}")
                        continue
        except Exception as e:
            print(f"[ERROR] Failed to walk directory {project_path}: {e}")
            raise HTTPException(status_code=500, detail=f"Failed to access directory: {str(e)}")

        # Phase 1: Global Symbol Scan
        global_symbols = {}
        from core.symbol_table import SymbolTable, Symbol, SymbolType
        symbol_table = SymbolTable()

        for file_path in all_files:
            parser = parser_manager.get_parser(file_path)
            if parser:
                try:
                    # Normalize path for Unicode
                    normalized_path = os.path.normpath(file_path)
                    with open(normalized_path, "r", encoding="utf-8", errors="ignore") as f:
                        content = f.read()
                    # Scan symbols (lightweight parse)
                    symbols = parser.scan_symbols(file_path, content)
                    global_symbols.update(symbols)
                    
                    # Populate SymbolTable
                    for name, info in symbols.items():
                        # Determine type
                        sym_type = SymbolType.FUNCTION
                        if info.get("type") == "class":
                            sym_type = SymbolType.CLASS
                        elif info.get("type") == "variable":
                            sym_type = SymbolType.VARIABLE
                        
                        symbol_table.add(Symbol(
                            name=name,
                            full_name=name,
                            type=sym_type,
                            file_path=file_path,
                            line_number=info.get("start_line", 0),
                            end_line_number=info.get("end_line", 0),
                            inherits_from=info.get("inherits", [])
                        ))
                except (UnicodeDecodeError, IOError, OSError) as file_err:
                    print(f"[WARN] File read error during symbol scan {file_path}: {file_err}")
                    continue
                except Exception as e:
                    print(f"[ERROR] Error scanning symbols {file_path}: {e}")

        # Phase 2: Detailed Parse with Global Context
        for file_path in all_files:
            parser = parser_manager.get_parser(file_path)
            if parser:
                try:
                    # Normalize path for Unicode
                    normalized_path = os.path.normpath(file_path)
                    with open(normalized_path, "r", encoding="utf-8", errors="ignore") as f:
                        content = f.read()
                        
                    # Pass global_symbols to parse functionality
                    parsed_endpoints = parser.parse(file_path, content, global_symbols=global_symbols, symbol_table=symbol_table)
                    
                    endpoints.extend(parsed_endpoints)
                    
                    # Update stats
                    lang = parser.__class__.__name__.replace("Parser", "").lower()
                    language_stats[lang] = language_stats.get(lang, 0) + 1
                    
                except (UnicodeDecodeError, IOError, OSError) as file_err:
                    print(f"[WARN] File read error during parsing {file_path}: {file_err}")
                    continue
                except Exception as e:
                    print(f"[ERROR] Error parsing {file_path}: {e}")
    
    # Phase 3: Clustering (Optional)
    if request.cluster:
        endpoints = cluster_manager.cluster_endpoints(endpoints)

    # Phase 4: Collect Taint Flows for visualization
    taint_flows = collect_taint_flows(endpoints)

    return ProjectStructure(
        root_path=project_path,
        language_stats=language_stats,
        endpoints=endpoints,
        taint_flows=taint_flows
    )


@app.get("/api/analyze/stats")
def get_analysis_stats():
    """Get statistics from the last parallel analysis."""
    return parallel_analyzer.get_stats()


# ============================================
# Cache API
# ============================================

@app.get("/api/cache/stats")
def get_cache_stats():
    """Get cache statistics including hit rate and storage size."""
    stats = analysis_cache.get_stats()
    stats["db_size_mb"] = round(analysis_cache.get_db_size() / (1024 * 1024), 2)
    return stats


class CacheInvalidateRequest(BaseModel):
    project_path: Optional[str] = None
    file_path: Optional[str] = None

@app.post("/api/cache/invalidate")
def invalidate_cache(request: CacheInvalidateRequest):
    """
    Invalidate cache entries.
    
    - If project_path is provided, invalidates all files in that project
    - If file_path is provided, invalidates only that file
    - If neither is provided, clears all cache
    """
    if request.project_path:
        count = analysis_cache.invalidate_project(request.project_path)
        return {"message": f"Invalidated {count} cached files for project", "count": count}
    elif request.file_path:
        analysis_cache.invalidate(request.file_path)
        return {"message": f"Invalidated cache for file: {request.file_path}"}
    else:
        analysis_cache.clear()
        return {"message": "All cache cleared"}


@app.delete("/api/cache")
def clear_cache():
    """Clear all cached analysis results."""
    analysis_cache.clear()
    return {"message": "Cache cleared successfully"}


# ============================================
# Streaming API
# ============================================

class StreamAnalyzeRequest(BaseModel):
    path: str
    cluster: bool = False
    use_cache: bool = True
    format: str = "sse"  # "sse" or "ndjson"


async def generate_sse_stream(project_path: str, cluster: bool, use_cache: bool):
    """Generate Server-Sent Events stream for analysis."""
    async for event in streaming_analyzer.analyze_stream(project_path, cluster, use_cache):
        yield event.to_sse()


async def generate_ndjson_stream(project_path: str, cluster: bool, use_cache: bool):
    """Generate Newline-Delimited JSON stream for analysis."""
    async for event in streaming_analyzer.analyze_stream(project_path, cluster, use_cache):
        yield event.to_ndjson()


@app.post("/api/analyze/stream")
async def analyze_project_stream(request: StreamAnalyzeRequest):
    """
    Stream analysis results as Server-Sent Events (SSE) or NDJSON.
    
    This endpoint progressively sends analysis results as they become available,
    allowing the frontend to display progress and partial results immediately.
    
    Events:
    - init: Analysis started
    - progress: Progress updates (phase, percent, etc.)
    - symbols: Symbol scan complete
    - endpoints: Batch of parsed endpoints
    - taint: Taint flow edges
    - stats: Final statistics
    - complete: Analysis complete
    - error: Error occurred
    
    Usage:
    ```javascript
    const eventSource = new EventSource('/api/analyze/stream');
    eventSource.onmessage = (event) => {
        const data = JSON.parse(event.data);
        console.log(data.type, data.data);
    };
    ```
    """
    if not os.path.exists(request.path):
        raise HTTPException(status_code=404, detail="Path not found")
    
    if request.format == "ndjson":
        return StreamingResponse(
            generate_ndjson_stream(request.path, request.cluster, request.use_cache),
            media_type="application/x-ndjson",
            headers={
                "Cache-Control": "no-cache",
                "X-Accel-Buffering": "no",  # Disable nginx buffering
            }
        )
    else:
        return StreamingResponse(
            generate_sse_stream(request.path, request.cluster, request.use_cache),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            }
        )


@app.post("/api/analyze/stream/cancel")
async def cancel_streaming_analysis():
    """Cancel an ongoing streaming analysis."""
    streaming_analyzer.cancel()
    return {"message": "Cancellation requested"}


class CodeSnippetRequest(BaseModel):
    file_path: str
    start_line: int
    end_line: int

@app.post("/api/snippet")
def get_code_snippet(request: CodeSnippetRequest):
    if not os.path.exists(request.file_path):
        raise HTTPException(status_code=404, detail="File not found")
        
    try:
        with open(request.file_path, "r", encoding="utf-8", errors="ignore") as f:
            lines = f.readlines()
            
        # Adjust for 0-based index vs 1-based lines
        start = max(0, request.start_line - 1)
        end = min(len(lines), request.end_line)
        
        snippet = "".join(lines[start:end])
        return {"code": snippet}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

class AIAnalyzeRequest(BaseModel):
    code: str
    context: str = ""
    project_path: str = ""
    related_paths: List[str] = []

@app.post("/api/analyze/ai")
def analyze_code_with_ai(request: AIAnalyzeRequest):
    # Gather context from related files (Graph Traversal Results)
    referenced_files = {}
    
    # 1. Read 'related_paths' content
    # Limit to top 5 files to avoid token overflow? Or maybe 10 small ones.
    # For now, read all but truncate large files.
    MAX_FILE_SIZE = 2000 # chars
    
    for path in request.related_paths:
        clean_path = path.replace("file:///", "").replace("file://", "")
        # Windows path fix
        if ":" in clean_path and clean_path.startswith("/"):
             clean_path = clean_path[1:]
             
        if not os.path.exists(clean_path):
            continue
            
        try:
            with open(clean_path, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()
                if len(content) > MAX_FILE_SIZE:
                    content = content[:MAX_FILE_SIZE] + "\n... (truncated)"
                referenced_files[path] = content
        except Exception:
            pass

    # 2. Call AI Analyzer with referenced files
    result = ai_analyzer.analyze_code(
        code=request.code,
        context=request.context,
        referenced_files=referenced_files
    )
    
    return result

from core.analyzer.semgrep_analyzer import semgrep_analyzer

class SemgrepRequest(BaseModel):
    project_path: str

@app.post("/api/analyze/semgrep")
def analyze_project_security(request: SemgrepRequest):
    findings = semgrep_analyzer.scan_project(request.project_path)
    return {"findings": findings}

@app.get("/")
def read_root():
    return {"message": "API is running"}

@app.get("/health")
def health_check():
    return {"status": "ok"}


# ============================================
# Call Graph API
# ============================================

class CallGraphRequest(BaseModel):
    project_path: str

@app.post("/api/callgraph")
def get_call_graph(request: CallGraphRequest):
    """
    Analyze project and return call graph data.
    
    Returns nodes (functions) and edges (call relationships).
    """
    if not os.path.exists(request.project_path):
        raise HTTPException(status_code=404, detail="Path not found")
    
    try:
        graph_data = call_graph_analyzer.analyze_project(request.project_path)
        return graph_data
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


class PathToSinkRequest(BaseModel):
    project_path: str
    entry_point: str  # Qualified function name
    sink: str  # Qualified function name
    max_depth: int = 10

@app.post("/api/callgraph/paths")
def find_paths_to_sink(request: PathToSinkRequest):
    """
    Find all call paths from an entry point to a sink.
    
    Useful for tracing how user input reaches dangerous functions.
    """
    if not os.path.exists(request.project_path):
        raise HTTPException(status_code=404, detail="Path not found")
    
    try:
        # Re-analyze to ensure fresh data
        call_graph_analyzer.analyze_project(request.project_path)
        
        paths = call_graph_analyzer.find_paths_to_sink(
            request.entry_point,
            request.sink,
            request.max_depth
        )
        
        return {"paths": paths, "count": len(paths)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/callgraph/metrics")
def get_function_metrics(request: CallGraphRequest):
    """
    Get metrics for all functions in the project.
    
    Returns fan_in, fan_out, and identifies hub/orphan functions.
    """
    if not os.path.exists(request.project_path):
        raise HTTPException(status_code=404, detail="Path not found")
    
    try:
        # Re-analyze to ensure fresh data
        call_graph_analyzer.analyze_project(request.project_path)
        metrics = call_graph_analyzer.get_function_metrics()
        
        return {"metrics": metrics}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============================================
# Inter-Procedural Taint Analysis API
# ============================================

class InterProceduralRequest(BaseModel):
    project_path: str
    max_depth: int = 10
    max_call_chain: int = 20


@app.post("/api/taint/interprocedural")
def analyze_interprocedural(request: InterProceduralRequest):
    """
    Perform inter-procedural taint analysis on a project.
    
    This analyzes taint flow across function calls:
    - Function summaries: Tracks input→output taint mappings
    - Call graph integration: Propagates taint through function calls
    - Context-sensitive: Considers call context for precision
    
    Returns:
        - flows: List of inter-procedural taint flows
        - summaries: Function taint summaries
        - statistics: Analysis metrics
    """
    if not os.path.exists(request.project_path):
        raise HTTPException(status_code=404, detail="Path not found")
    
    try:
        analyzer = InterProceduralTaintAnalyzer(
            max_depth=request.max_depth,
            max_call_chain=request.max_call_chain
        )
        result = analyzer.analyze_project(request.project_path)
        
        return {
            "flows": result["flows"],
            "statistics": result["statistics"],
            "summaries_count": len(result["summaries"]),
            "vulnerable_functions": analyzer.get_vulnerable_functions()
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/taint/interprocedural/full")
def analyze_interprocedural_full(request: InterProceduralRequest):
    """
    Perform full inter-procedural taint analysis with complete summaries.
    
    Returns complete data including all function summaries.
    Warning: May be large for big projects.
    """
    if not os.path.exists(request.project_path):
        raise HTTPException(status_code=404, detail="Path not found")
    
    try:
        result = analyze_interprocedural_taint(
            request.project_path,
            max_depth=request.max_depth
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/taint/paths")
def get_taint_paths(request: CallGraphRequest):
    """
    Find all taint paths between functions.
    
    Returns paths that can propagate taint from entry points to sinks.
    """
    if not os.path.exists(request.project_path):
        raise HTTPException(status_code=404, detail="Path not found")
    
    try:
        analyzer = InterProceduralTaintAnalyzer()
        result = analyzer.analyze_project(request.project_path)
        
        # Group flows by source→sink
        paths_by_flow = {}
        for flow in result["flows"]:
            key = f"{flow['source']['file']}:{flow['source']['line']} → {flow['sink']['file']}:{flow['sink']['line']}"
            if key not in paths_by_flow:
                paths_by_flow[key] = {
                    "source": flow["source"],
                    "sink": flow["sink"],
                    "paths": []
                }
            paths_by_flow[key]["paths"].append({
                "call_chain": flow["call_chain"],
                "description": flow["path_description"],
                "sanitized": flow["sanitized"]
            })
        
        return {
            "taint_paths": list(paths_by_flow.values()),
            "total_paths": len(result["flows"])
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============================================
# Import Resolution API
# ============================================

class ImportResolverRequest(BaseModel):
    project_path: str


class SymbolResolveRequest(BaseModel):
    project_path: str
    symbol_name: str
    source_file: str


@app.post("/api/imports/resolve")
def resolve_imports(request: ImportResolverRequest):
    """
    Resolve all imports in a project and build the dependency graph.
    
    Returns:
        - modules: All discovered modules with their imports
        - edges: Dependency graph edges
        - circular_dependencies: Detected circular import chains
        - statistics: Resolution statistics
    """
    if not os.path.exists(request.project_path):
        raise HTTPException(status_code=404, detail="Path not found")
    
    try:
        result = resolve_project_imports(request.project_path)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/imports/graph")
def get_dependency_graph(request: ImportResolverRequest):
    """
    Get the module dependency graph for visualization.
    
    Returns a simplified graph structure optimized for rendering.
    """
    if not os.path.exists(request.project_path):
        raise HTTPException(status_code=404, detail="Path not found")
    
    try:
        resolver = ImportResolver(request.project_path)
        result = resolver.scan_project()
        
        # Build visualization-friendly graph
        nodes = []
        edges = []
        
        for module_name, module_info in result["modules"].items():
            nodes.append({
                "id": module_name,
                "label": module_name.split('.')[-1] if '.' in module_name else module_name,
                "full_name": module_name,
                "file_path": module_info["file_path"],
                "is_package": module_info["is_package"],
                "is_entry_point": module_info["is_entry_point"],
                "imports_count": module_info["imports_count"],
                "dependents_count": len(module_info["dependents"]),
                "dependencies_count": len(module_info["dependencies"])
            })
        
        for edge in result["edges"]:
            edges.append({
                "id": f"{edge['source']}->{edge['target']}",
                "source": edge["source"],
                "target": edge["target"],
                "import_type": edge["import_type"],
                "label": ", ".join(edge["imported_names"][:3])
            })
        
        return {
            "nodes": nodes,
            "edges": edges,
            "circular_dependencies": result["circular_dependencies"],
            "statistics": result["statistics"]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/imports/symbol")
def resolve_symbol(request: SymbolResolveRequest):
    """
    Resolve a symbol to its definition location.
    
    Useful for "go to definition" functionality.
    """
    if not os.path.exists(request.project_path):
        raise HTTPException(status_code=404, detail="Path not found")
    
    try:
        resolver = ImportResolver(request.project_path)
        resolver.scan_project()
        
        result = resolver.resolve_symbol(request.symbol_name, request.source_file)
        
        if result:
            return {"resolved": True, **result}
        else:
            return {"resolved": False, "message": f"Could not resolve symbol '{request.symbol_name}'"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/imports/module")
def get_module_info(request: SymbolResolveRequest):
    """
    Get detailed information about a specific module.
    
    Returns imports, exports, dependencies, and dependents.
    """
    if not os.path.exists(request.project_path):
        raise HTTPException(status_code=404, detail="Path not found")
    
    try:
        resolver = ImportResolver(request.project_path)
        result = resolver.scan_project()
        
        # Find module by file path or module name
        module_info = None
        for name, info in result["modules"].items():
            if info["file_path"] == request.source_file or name == request.symbol_name:
                module_info = info
                module_info["module_name"] = name
                break
        
        if module_info:
            # Get exports
            exports = resolver.get_module_exports(module_info["module_name"])
            module_info["exports"] = exports
            return module_info
        else:
            raise HTTPException(status_code=404, detail="Module not found")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============================================
# Type Inference API
# ============================================

class TypeInferenceRequest(BaseModel):
    project_path: str


class VariableTypeRequest(BaseModel):
    project_path: str
    variable_name: str
    file_path: Optional[str] = None
    scope: Optional[str] = None
    line: Optional[int] = None


class FunctionSignatureRequest(BaseModel):
    project_path: str
    function_name: str
    file_path: Optional[str] = None


@app.post("/api/types/analyze")
def analyze_types(request: TypeInferenceRequest):
    """
    Analyze the entire project for type information.
    
    Returns inferred types for variables, function signatures, and class types.
    """
    if not os.path.exists(request.project_path):
        raise HTTPException(status_code=404, detail="Path not found")
    
    try:
        result = analyze_project_types(request.project_path)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/types/variable")
def get_variable_type(request: VariableTypeRequest):
    """
    Get the inferred type for a specific variable.
    """
    if not os.path.exists(request.project_path):
        raise HTTPException(status_code=404, detail="Path not found")
    
    try:
        inferencer = TypeInferencer(request.project_path)
        inferencer.analyze_project()
        
        type_info = inferencer.get_variable_type(
            request.variable_name,
            request.file_path,
            request.scope,
            request.line
        )
        
        if type_info:
            return {"found": True, "type": type_info.to_dict()}
        else:
            return {"found": False, "message": f"Variable '{request.variable_name}' not found"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/types/function")
def get_function_type(request: FunctionSignatureRequest):
    """
    Get the type signature for a function.
    """
    if not os.path.exists(request.project_path):
        raise HTTPException(status_code=404, detail="Path not found")
    
    try:
        inferencer = TypeInferencer(request.project_path)
        inferencer.analyze_project()
        
        signature = inferencer.get_function_signature(
            request.function_name,
            request.file_path
        )
        
        if signature:
            return {
                "found": True,
                "signature": {
                    "name": signature.name,
                    "qualified_name": signature.qualified_name,
                    "parameters": [(p[0], p[1].to_dict()) for p in signature.parameters],
                    "return_type": signature.return_type.to_dict(),
                    "is_method": signature.is_method,
                    "is_async": signature.is_async,
                    "decorators": signature.decorators
                }
            }
        else:
            return {"found": False, "message": f"Function '{request.function_name}' not found"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/types/class")
def get_class_types(request: FunctionSignatureRequest):
    """
    Get type information for a class (attributes, methods with types).
    """
    if not os.path.exists(request.project_path):
        raise HTTPException(status_code=404, detail="Path not found")
    
    try:
        inferencer = TypeInferencer(request.project_path)
        inferencer.analyze_project()
        
        class_info = inferencer.get_class_info(
            request.function_name,  # Using function_name field for class name
            request.file_path
        )
        
        if class_info:
            return {
                "found": True,
                "class": {
                    "name": class_info.name,
                    "qualified_name": class_info.qualified_name,
                    "file_path": class_info.file_path,
                    "base_classes": class_info.base_classes,
                    "attributes": {k: v.to_dict() for k, v in class_info.attributes.items()},
                    "class_attributes": {k: v.to_dict() for k, v in class_info.class_attributes.items()},
                    "methods": list(class_info.methods.keys()),
                    "is_dataclass": class_info.is_dataclass,
                    "is_abstract": class_info.is_abstract
                }
            }
        else:
            return {"found": False, "message": f"Class '{request.function_name}' not found"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============================================
# Class Hierarchy API
# ============================================

class ClassHierarchyRequest(BaseModel):
    project_path: str


class ClassQueryRequest(BaseModel):
    project_path: str
    class_name: str


class PolymorphicCallRequest(BaseModel):
    project_path: str
    receiver_type: str
    method_name: str


@app.post("/api/hierarchy/analyze")
def analyze_hierarchy(request: ClassHierarchyRequest):
    """
    Analyze the entire project for class hierarchies.
    
    Returns inheritance relationships, method overrides, and class metadata.
    """
    if not os.path.exists(request.project_path):
        raise HTTPException(status_code=404, detail="Path not found")
    
    try:
        result = analyze_class_hierarchy(request.project_path)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/hierarchy/class")
def get_class_hierarchy(request: ClassQueryRequest):
    """
    Get the full inheritance hierarchy for a specific class.
    
    Returns ancestors, descendants, and methods.
    """
    if not os.path.exists(request.project_path):
        raise HTTPException(status_code=404, detail="Path not found")
    
    try:
        analyzer = ClassHierarchyAnalyzer(request.project_path)
        analyzer.analyze_project()
        
        hierarchy = analyzer.get_class_hierarchy(request.class_name)
        
        if hierarchy:
            return {"found": True, **hierarchy}
        else:
            return {"found": False, "message": f"Class '{request.class_name}' not found"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/hierarchy/implementations")
def get_implementations(request: ClassQueryRequest):
    """
    Get all classes that implement an interface or extend an abstract class.
    """
    if not os.path.exists(request.project_path):
        raise HTTPException(status_code=404, detail="Path not found")
    
    try:
        analyzer = ClassHierarchyAnalyzer(request.project_path)
        analyzer.analyze_project()
        
        implementations = analyzer.get_implementations(request.class_name)
        
        return {
            "interface": request.class_name,
            "implementations": implementations,
            "count": len(implementations)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/hierarchy/method")
def get_method_implementations(request: ClassQueryRequest):
    """
    Get all implementations of a method across the class hierarchy.
    """
    if not os.path.exists(request.project_path):
        raise HTTPException(status_code=404, detail="Path not found")
    
    try:
        analyzer = ClassHierarchyAnalyzer(request.project_path)
        analyzer.analyze_project()
        
        implementations = analyzer.get_method_implementations(request.class_name)
        
        return {
            "method_name": request.class_name,
            "implementations": implementations,
            "count": len(implementations)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/hierarchy/polymorphic")
def resolve_polymorphic(request: PolymorphicCallRequest):
    """
    Resolve possible method implementations for a polymorphic call.
    
    Given a receiver type and method name, returns all possible target methods.
    """
    if not os.path.exists(request.project_path):
        raise HTTPException(status_code=404, detail="Path not found")
    
    try:
        analyzer = ClassHierarchyAnalyzer(request.project_path)
        analyzer.analyze_project()
        
        targets = analyzer.resolve_polymorphic_call(
            request.receiver_type,
            request.method_name
        )
        
        return {
            "receiver_type": request.receiver_type,
            "method_name": request.method_name,
            "possible_targets": targets,
            "count": len(targets)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/hierarchy/graph")
def get_hierarchy_graph(request: ClassHierarchyRequest):
    """
    Get the full inheritance graph for visualization.
    
    Returns nodes (classes) and edges (inheritance relationships).
    """
    if not os.path.exists(request.project_path):
        raise HTTPException(status_code=404, detail="Path not found")
    
    try:
        analyzer = ClassHierarchyAnalyzer(request.project_path)
        analyzer.analyze_project()
        
        graph = analyzer.get_inheritance_graph()
        return graph
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# Distributed Analysis API Endpoints (Phase 3.1)
# =============================================================================

class DistributedAnalysisRequest(BaseModel):
    """Request for distributed analysis."""
    project_path: str
    analysis_type: str = "full"  # full, parse_only, taint, type_inference, hierarchy, imports
    max_files: int = 10000
    excluded_dirs: Optional[List[str]] = None
    priority: str = "normal"  # high, normal, low


class TaskStatusRequest(BaseModel):
    """Request for task status."""
    task_id: str


class TaskSubscribeRequest(BaseModel):
    """Request to subscribe to task updates."""
    task_id: str


class WorkflowRequest(BaseModel):
    """Request for full analysis workflow."""
    project_path: str
    include_taint: bool = True
    include_types: bool = True
    include_hierarchy: bool = True
    include_imports: bool = True


@app.get("/api/distributed/status")
def get_distributed_status():
    """
    Get the status of the distributed analysis system.
    
    Returns Redis connection status, worker stats, and queue stats.
    """
    try:
        from core.celery_config import check_redis_connection, get_worker_stats, get_queue_stats
        
        redis_connected = check_redis_connection()
        
        if not redis_connected:
            return {
                "status": "unavailable",
                "redis_connected": False,
                "message": "Redis is not available. Start Redis server to enable distributed analysis.",
                "workers": {},
                "queues": {}
            }
        
        worker_stats = get_worker_stats()
        queue_stats = get_queue_stats()
        
        return {
            "status": "available",
            "redis_connected": True,
            "workers": worker_stats,
            "queues": queue_stats
        }
    except ImportError:
        return {
            "status": "not_configured",
            "message": "Celery/Redis dependencies not installed. Run: pip install celery redis"
        }
    except Exception as e:
        return {
            "status": "error",
            "message": str(e)
        }


@app.post("/api/distributed/analyze")
def start_distributed_analysis(request: DistributedAnalysisRequest):
    """
    Start a distributed analysis task.
    
    Returns a task ID that can be used to track progress via WebSocket or polling.
    """
    if not os.path.exists(request.project_path):
        raise HTTPException(status_code=404, detail="Project path not found")
    
    try:
        from core.celery_config import check_redis_connection, TaskPriority
        
        if not check_redis_connection():
            raise HTTPException(
                status_code=503, 
                detail="Redis is not available. Start Redis server to enable distributed analysis."
            )
        
        from core.distributed_tasks import analyze_project_task
        
        # Determine priority
        priority_map = {
            "high": TaskPriority.HIGH,
            "normal": TaskPriority.NORMAL,
            "low": TaskPriority.LOW
        }
        priority = priority_map.get(request.priority, TaskPriority.NORMAL)
        
        # Start the task
        task = analyze_project_task.apply_async(
            args=[
                request.project_path,
                request.analysis_type,
                request.max_files,
                request.excluded_dirs
            ],
            priority=priority
        )
        
        return {
            "task_id": task.id,
            "status": "queued",
            "message": f"Analysis task queued with priority {request.priority}",
            "project_path": request.project_path,
            "analysis_type": request.analysis_type
        }
        
    except ImportError:
        raise HTTPException(
            status_code=503,
            detail="Celery/Redis dependencies not installed"
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/distributed/workflow")
def start_distributed_workflow(request: WorkflowRequest):
    """
    Start a full analysis workflow with all components.
    
    This executes taint analysis, type inference, hierarchy analysis,
    and import resolution in parallel.
    """
    if not os.path.exists(request.project_path):
        raise HTTPException(status_code=404, detail="Project path not found")
    
    try:
        from core.celery_config import check_redis_connection
        
        if not check_redis_connection():
            raise HTTPException(
                status_code=503, 
                detail="Redis is not available"
            )
        
        from core.distributed_tasks import full_analysis_workflow
        
        task = full_analysis_workflow.apply_async(
            args=[
                request.project_path,
                request.include_taint,
                request.include_types,
                request.include_hierarchy,
                request.include_imports
            ]
        )
        
        return {
            "task_id": task.id,
            "status": "queued",
            "message": "Full analysis workflow started",
            "project_path": request.project_path,
            "components": {
                "taint": request.include_taint,
                "types": request.include_types,
                "hierarchy": request.include_hierarchy,
                "imports": request.include_imports
            }
        }
        
    except ImportError:
        raise HTTPException(
            status_code=503,
            detail="Celery/Redis dependencies not installed"
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/distributed/task/status")
def get_task_status_endpoint(request: TaskStatusRequest):
    """
    Get the status of a distributed analysis task.
    
    Returns current status, progress information, and result if complete.
    """
    try:
        from core.distributed_tasks import get_task_status
        
        status = get_task_status(request.task_id)
        return status
        
    except ImportError:
        raise HTTPException(
            status_code=503,
            detail="Celery/Redis dependencies not installed"
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/distributed/task/result")
def get_task_result_endpoint(request: TaskStatusRequest):
    """
    Get the result of a completed task.
    
    Returns the full analysis result if the task is complete.
    """
    try:
        from core.distributed_tasks import get_task_result
        
        result = get_task_result(request.task_id)
        
        if result.get('status') == 'pending':
            raise HTTPException(status_code=202, detail="Task still in progress")
        
        return result
        
    except ImportError:
        raise HTTPException(
            status_code=503,
            detail="Celery/Redis dependencies not installed"
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/distributed/task/cancel")
def cancel_task_endpoint(request: TaskStatusRequest):
    """
    Cancel a running distributed analysis task.
    """
    try:
        from core.distributed_tasks import cancel_analysis
        
        result = cancel_analysis(request.task_id)
        return result
        
    except ImportError:
        raise HTTPException(
            status_code=503,
            detail="Celery/Redis dependencies not installed"
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/distributed/workers")
def get_worker_info():
    """
    Get information about active Celery workers.
    """
    try:
        from core.celery_config import check_redis_connection, get_worker_stats
        
        if not check_redis_connection():
            raise HTTPException(
                status_code=503, 
                detail="Redis is not available"
            )
        
        stats = get_worker_stats()
        return stats
        
    except ImportError:
        raise HTTPException(
            status_code=503,
            detail="Celery/Redis dependencies not installed"
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/distributed/queues")
def get_queue_info():
    """
    Get information about task queues.
    """
    try:
        from core.celery_config import check_redis_connection, get_queue_stats
        
        if not check_redis_connection():
            raise HTTPException(
                status_code=503, 
                detail="Redis is not available"
            )
        
        stats = get_queue_stats()
        return stats
        
    except ImportError:
        raise HTTPException(
            status_code=503,
            detail="Celery/Redis dependencies not installed"
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# WebSocket Endpoint for Real-time Progress
# =============================================================================

from fastapi import WebSocket, WebSocketDisconnect
import uuid

@app.websocket("/ws/progress")
async def websocket_progress_endpoint(websocket: WebSocket):
    """
    WebSocket endpoint for real-time task progress updates.
    
    Protocol:
    - Client connects and receives a client_id
    - Client sends: {"type": "subscribe", "data": {"task_id": "xxx"}}
    - Server sends progress updates for subscribed tasks
    - Client sends: {"type": "ping"} for heartbeat
    """
    client_id = str(uuid.uuid4())
    
    try:
        from core.websocket_progress import (
            connection_manager, 
            handle_websocket_message,
            progress_poller
        )
        
        # Accept connection
        connected = await connection_manager.connect(websocket, client_id)
        if not connected:
            return
        
        try:
            while True:
                # Receive message from client
                data = await websocket.receive_json()
                
                # Handle the message
                await handle_websocket_message(websocket, client_id, data)
                
        except WebSocketDisconnect:
            await connection_manager.disconnect(client_id)
            
    except ImportError:
        await websocket.accept()
        await websocket.send_json({
            "type": "error",
            "message": "WebSocket progress not available"
        })
        await websocket.close()
    except Exception as e:
        try:
            await websocket.send_json({
                "type": "error",
                "message": str(e)
            })
        except:
            pass


@app.get("/api/distributed/ws/stats")
def get_websocket_stats():
    """
    Get WebSocket connection statistics.
    """
    try:
        from core.websocket_progress import connection_manager
        
        return connection_manager.get_stats()
        
    except ImportError:
        return {"error": "WebSocket module not available"}
    except Exception as e:
        return {"error": str(e)}


# =============================================================================
# Microservice API Tracking Endpoints (Phase 3.2)
# =============================================================================

class MicroserviceAnalysisRequest(BaseModel):
    """Request for microservice analysis."""
    project_path: str


class OpenAPIParseRequest(BaseModel):
    """Request to parse OpenAPI file."""
    file_path: str


class ProtoParseRequest(BaseModel):
    """Request to parse proto file."""
    file_path: str


class ServiceQueryRequest(BaseModel):
    """Request for service query."""
    project_path: str
    service_name: str


class DataFlowRequest(BaseModel):
    """Request for data flow between services."""
    project_path: str
    source_service: str
    target_service: str


@app.post("/api/microservices/analyze")
def analyze_microservices_endpoint(request: MicroserviceAnalysisRequest):
    """
    Analyze microservice architecture in a project.
    
    Discovers:
    - OpenAPI/Swagger specifications
    - gRPC proto definitions
    - Inter-service API calls
    - Service dependency graph
    """
    if not os.path.exists(request.project_path):
        raise HTTPException(status_code=404, detail="Project path not found")
    
    try:
        analyzer = MicroserviceAnalyzer(request.project_path)
        result = analyzer.analyze_project()
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/microservices/openapi/parse")
def parse_openapi_endpoint(request: OpenAPIParseRequest):
    """
    Parse a single OpenAPI/Swagger specification file.
    
    Supports:
    - OpenAPI 3.0.x, 3.1.x
    - Swagger 2.0
    - YAML and JSON formats
    """
    if not os.path.exists(request.file_path):
        raise HTTPException(status_code=404, detail="File not found")
    
    try:
        result = parse_openapi(request.file_path)
        if result is None:
            raise HTTPException(status_code=400, detail="Not a valid OpenAPI/Swagger file")
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/microservices/proto/parse")
def parse_proto_endpoint(request: ProtoParseRequest):
    """
    Parse a gRPC Protocol Buffer (.proto) file.
    
    Extracts:
    - Service definitions
    - RPC methods
    - Streaming configurations
    """
    if not os.path.exists(request.file_path):
        raise HTTPException(status_code=404, detail="File not found")
    
    try:
        result = parse_proto(request.file_path)
        return {"services": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/microservices/service")
def get_service_details(request: ServiceQueryRequest):
    """
    Get details of a specific service.
    
    Returns endpoints, gRPC methods, and metadata.
    """
    if not os.path.exists(request.project_path):
        raise HTTPException(status_code=404, detail="Project path not found")
    
    try:
        analyzer = MicroserviceAnalyzer(request.project_path)
        analyzer.analyze_project()
        
        service = analyzer.get_service(request.service_name)
        if service is None:
            raise HTTPException(status_code=404, detail=f"Service '{request.service_name}' not found")
        
        return service
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/microservices/calls")
def get_service_calls_endpoint(request: ServiceQueryRequest):
    """
    Get all API calls involving a service.
    
    Returns both incoming and outgoing calls.
    """
    if not os.path.exists(request.project_path):
        raise HTTPException(status_code=404, detail="Project path not found")
    
    try:
        analyzer = MicroserviceAnalyzer(request.project_path)
        analyzer.analyze_project()
        
        calls = analyzer.get_service_calls(request.service_name)
        return {"service": request.service_name, "calls": calls}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/microservices/dataflow")
def get_data_flow_endpoint(request: DataFlowRequest):
    """
    Get data flow between two services.
    
    Shows all API calls from source to target service.
    """
    if not os.path.exists(request.project_path):
        raise HTTPException(status_code=404, detail="Project path not found")
    
    try:
        analyzer = MicroserviceAnalyzer(request.project_path)
        analyzer.analyze_project()
        
        flows = analyzer.get_data_flow(request.source_service, request.target_service)
        return {
            "source": request.source_service,
            "target": request.target_service,
            "flows": flows
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/microservices/graph")
def get_service_graph_endpoint(request: MicroserviceAnalysisRequest):
    """
    Get the service dependency graph for visualization.
    
    Returns nodes (services) and edges (API calls).
    """
    if not os.path.exists(request.project_path):
        raise HTTPException(status_code=404, detail="Project path not found")
    
    try:
        analyzer = MicroserviceAnalyzer(request.project_path)
        result = analyzer.analyze_project()
        
        return result.get('graph', {'nodes': [], 'edges': []})
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# Monorepo Analysis Endpoints
# =============================================================================

class MonorepoAnalysisRequest(BaseModel):
    """Request for monorepo analysis."""
    project_path: str


class MonorepoProjectRequest(BaseModel):
    """Request for specific project in monorepo."""
    project_path: str
    project_name: str


class AffectedProjectsRequest(BaseModel):
    """Request for affected projects analysis."""
    project_path: str
    changed_projects: List[str]


@app.post("/api/monorepo/analyze")
def analyze_monorepo_endpoint(request: MonorepoAnalysisRequest):
    """
    Analyze monorepo structure.
    
    Detects:
    - Monorepo tool (Lerna, Turborepo, Nx, npm/yarn/pnpm workspaces, Maven, Gradle, etc.)
    - All projects/packages in the monorepo
    - Internal dependencies between projects
    - Shared packages
    - Build order (topologically sorted)
    """
    if not os.path.exists(request.project_path):
        raise HTTPException(status_code=404, detail="Project path not found")
    
    try:
        result = analyze_monorepo(request.project_path)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/monorepo/project")
def get_monorepo_project_endpoint(request: MonorepoProjectRequest):
    """
    Get detailed information about a specific project in the monorepo.
    
    Returns:
    - Project metadata (name, version, description)
    - Dependencies (external and internal)
    - Dependents (projects that depend on this)
    - Scripts and build configuration
    """
    if not os.path.exists(request.project_path):
        raise HTTPException(status_code=404, detail="Project path not found")
    
    try:
        result = get_project_details(request.project_path, request.project_name)
        if result is None:
            raise HTTPException(status_code=404, detail=f"Project '{request.project_name}' not found")
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/monorepo/graph")
def get_monorepo_graph_endpoint(request: MonorepoAnalysisRequest):
    """
    Get the dependency graph for visualization.
    
    Returns nodes (projects) and edges (internal dependencies).
    """
    if not os.path.exists(request.project_path):
        raise HTTPException(status_code=404, detail="Project path not found")
    
    try:
        result = get_dependency_graph(request.project_path)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/monorepo/affected")
def get_affected_projects_endpoint(request: AffectedProjectsRequest):
    """
    Get projects affected by changes.
    
    Given a list of changed projects, returns:
    - All affected projects (including transitive dependents)
    - Recommended build order for affected projects
    """
    if not os.path.exists(request.project_path):
        raise HTTPException(status_code=404, detail="Project path not found")
    
    try:
        result = get_affected_projects(request.project_path, request.changed_projects)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/monorepo/dependencies")
def get_project_dependencies_endpoint(request: MonorepoProjectRequest):
    """
    Get dependencies of a specific project.
    
    Returns both direct and transitive internal dependencies.
    """
    if not os.path.exists(request.project_path):
        raise HTTPException(status_code=404, detail="Project path not found")
    
    try:
        analyzer = MonorepoAnalyzer(request.project_path)
        analyzer.analyze()
        
        direct = analyzer.get_dependencies(request.project_name, include_transitive=False)
        transitive = analyzer.get_dependencies(request.project_name, include_transitive=True)
        dependents = analyzer.get_dependents(request.project_name)
        
        return {
            "project": request.project_name,
            "direct_dependencies": direct,
            "transitive_dependencies": transitive,
            "dependents": dependents,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/monorepo/build-order")
def get_build_order_endpoint(request: MonorepoAnalysisRequest):
    """
    Get the recommended build order for all projects.
    
    Returns projects sorted topologically based on dependencies.
    """
    if not os.path.exists(request.project_path):
        raise HTTPException(status_code=404, detail="Project path not found")
    
    try:
        result = analyze_monorepo(request.project_path)
        return {
            "build_order": result.get('build_order', []),
            "shared_packages": result.get('shared_packages', []),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# LSP (Language Server Protocol) Endpoints
# =============================================================================

class LSPInitRequest(BaseModel):
    """Request to initialize LSP servers."""
    workspace_path: str
    languages: Optional[List[str]] = None  # None = all available


class LSPPositionRequest(BaseModel):
    """Request with file path and position."""
    workspace_path: str
    file_path: str
    line: int  # 0-indexed
    character: int  # 0-indexed


class LSPDocumentRequest(BaseModel):
    """Request for document-level operations."""
    workspace_path: str
    file_path: str


class LSPSymbolSearchRequest(BaseModel):
    """Request to search symbols."""
    workspace_path: str
    query: str


@app.post("/api/lsp/initialize")
def initialize_lsp_servers(request: LSPInitRequest):
    """
    Initialize LSP servers for the workspace.
    
    Starts language servers for code intelligence features.
    Supports: Python (Pyright), TypeScript, JavaScript, Java, Go, Rust
    
    Returns status of each server initialization.
    """
    if not os.path.exists(request.workspace_path):
        raise HTTPException(status_code=404, detail="Workspace path not found")
    
    try:
        manager = get_lsp_manager(request.workspace_path)
        
        if request.languages:
            results = {}
            for lang in request.languages:
                results[lang] = manager.start_server(lang)
        else:
            results = manager.start_all_available()
        
        return {
            "success": True,
            "workspace": request.workspace_path,
            "servers": results,
            "status": manager.get_status()
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/lsp/shutdown")
def shutdown_lsp_servers(request: LSPInitRequest):
    """
    Shutdown all LSP servers for the workspace.
    """
    try:
        stop_lsp_servers()
        return {"success": True, "message": "All LSP servers stopped"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/lsp/status")
def get_lsp_status(workspace_path: str):
    """
    Get status of LSP servers.
    
    Returns information about running servers and available languages.
    """
    if not os.path.exists(workspace_path):
        raise HTTPException(status_code=404, detail="Workspace path not found")
    
    try:
        manager = get_lsp_manager(workspace_path)
        return manager.get_status()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/lsp/available")
def get_available_languages():
    """
    Get list of available language servers.
    """
    return {
        "languages": [
            {
                "id": lang,
                "name": config.name,
                "extensions": config.file_extensions,
                "command": config.command[0]
            }
            for lang, config in LANGUAGE_SERVERS.items()
        ]
    }


@app.post("/api/lsp/definition")
def lsp_goto_definition(request: LSPPositionRequest):
    """
    Go to definition of symbol at position.
    
    Returns list of definition locations for the symbol
    at the specified position.
    """
    if not os.path.exists(request.workspace_path):
        raise HTTPException(status_code=404, detail="Workspace path not found")
    if not os.path.exists(request.file_path):
        raise HTTPException(status_code=404, detail="File not found")
    
    try:
        locations = goto_definition(
            request.workspace_path,
            request.file_path,
            request.line,
            request.character
        )
        return {
            "success": True,
            "definitions": locations,
            "count": len(locations)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/lsp/references")
def lsp_find_references(request: LSPPositionRequest):
    """
    Find all references to symbol at position.
    
    Returns all locations where the symbol is referenced.
    """
    if not os.path.exists(request.workspace_path):
        raise HTTPException(status_code=404, detail="Workspace path not found")
    if not os.path.exists(request.file_path):
        raise HTTPException(status_code=404, detail="File not found")
    
    try:
        locations = find_references(
            request.workspace_path,
            request.file_path,
            request.line,
            request.character
        )
        return {
            "success": True,
            "references": locations,
            "count": len(locations)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/lsp/hover")
def lsp_get_hover(request: LSPPositionRequest):
    """
    Get hover information for symbol at position.
    
    Returns documentation, type signature, and other
    information for the symbol.
    """
    if not os.path.exists(request.workspace_path):
        raise HTTPException(status_code=404, detail="Workspace path not found")
    if not os.path.exists(request.file_path):
        raise HTTPException(status_code=404, detail="File not found")
    
    try:
        hover = get_hover_info(
            request.workspace_path,
            request.file_path,
            request.line,
            request.character
        )
        return {
            "success": True,
            "hover": hover
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/lsp/completions")
def lsp_get_completions(request: LSPPositionRequest):
    """
    Get code completions at position.
    
    Returns suggested completions for the current context.
    """
    if not os.path.exists(request.workspace_path):
        raise HTTPException(status_code=404, detail="Workspace path not found")
    if not os.path.exists(request.file_path):
        raise HTTPException(status_code=404, detail="File not found")
    
    try:
        completions = get_completions(
            request.workspace_path,
            request.file_path,
            request.line,
            request.character
        )
        return {
            "success": True,
            "completions": completions,
            "count": len(completions)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/lsp/symbols")
def lsp_get_document_symbols(request: LSPDocumentRequest):
    """
    Get symbols in a document.
    
    Returns hierarchical list of all symbols (classes, functions,
    variables, etc.) in the document.
    """
    if not os.path.exists(request.workspace_path):
        raise HTTPException(status_code=404, detail="Workspace path not found")
    if not os.path.exists(request.file_path):
        raise HTTPException(status_code=404, detail="File not found")
    
    try:
        symbols = get_symbols(
            request.workspace_path,
            request.file_path
        )
        return {
            "success": True,
            "symbols": symbols,
            "count": len(symbols)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/lsp/workspace-symbols")
def lsp_search_workspace_symbols(request: LSPSymbolSearchRequest):
    """
    Search for symbols in the workspace.
    
    Returns matching symbols from all active language servers.
    """
    if not os.path.exists(request.workspace_path):
        raise HTTPException(status_code=404, detail="Workspace path not found")
    
    try:
        symbols = search_symbols(
            request.workspace_path,
            request.query
        )
        return {
            "success": True,
            "symbols": symbols,
            "count": len(symbols)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/lsp/diagnostics")
def lsp_get_diagnostics(request: LSPDocumentRequest):
    """
    Get diagnostics (errors, warnings) for a document.
    
    Returns compiler/linter errors and warnings from the
    language server.
    """
    if not os.path.exists(request.workspace_path):
        raise HTTPException(status_code=404, detail="Workspace path not found")
    if not os.path.exists(request.file_path):
        raise HTTPException(status_code=404, detail="File not found")
    
    try:
        manager = get_lsp_manager(request.workspace_path)
        diagnostics = manager.get_diagnostics(request.file_path)
        return {
            "success": True,
            "diagnostics": diagnostics,
            "count": len(diagnostics)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============================================
# ML-based Vulnerability Detection API
# ============================================

class MLAnalyzeRequest(BaseModel):
    project_path: str
    filter_false_positives: bool = True
    min_confidence: float = 0.5


class MLFeedbackRequest(BaseModel):
    feature_id: str
    is_true_positive: bool
    code_snippet: Optional[str] = None


@app.post("/api/ml/analyze")
def ml_analyze_vulnerabilities(request: MLAnalyzeRequest):
    """
    Analyze project vulnerabilities using ML-based detection.
    
    This combines:
    - Feature extraction (AST, semantic, contextual, pattern)
    - Ensemble ML classification
    - False positive filtering
    - Severity prediction
    
    Returns vulnerabilities with confidence scores and recommendations.
    """
    if not os.path.exists(request.project_path):
        raise HTTPException(status_code=404, detail="Path not found")
    
    try:
        # First, run inter-procedural taint analysis
        taint_analyzer = InterProceduralTaintAnalyzer()
        taint_result = taint_analyzer.analyze_project(request.project_path)
        
        # Collect code contents for feature extraction
        code_contents = {}
        for root, _, files in os.walk(request.project_path):
            if any(skip in root for skip in ["venv", "node_modules", ".git", "__pycache__"]):
                continue
            for file in files:
                if file.endswith(('.py', '.js', '.ts', '.php', '.java', '.go')):
                    file_path = os.path.join(root, file)
                    try:
                        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                            code_contents[file_path] = f.read()
                    except Exception:
                        pass
        
        # Convert taint flows for ML analysis
        taint_flows = []
        for flow in taint_result.get("flows", []):
            taint_flows.append({
                "file_path": flow.get("source", {}).get("file", ""),
                "function_name": flow.get("source", {}).get("function", ""),
                "source_line": flow.get("source", {}).get("line", 0),
                "sink_line": flow.get("sink", {}).get("line", 0),
                "vulnerability_type": flow.get("vulnerability_type", "general"),
                "source_type": flow.get("source", {}).get("type", "unknown"),
                "sink_type": flow.get("sink", {}).get("type", "unknown"),
                "call_chain": flow.get("call_chain", []),
                "sanitized": flow.get("sanitized", False),
            })
        
        # Run ML analysis
        ml_result = analyze_with_ml(
            taint_flows,
            code_contents,
            filter_false_positives=request.filter_false_positives
        )
        
        # Filter by confidence
        if request.min_confidence > 0:
            ml_result["results"] = [
                r for r in ml_result["results"]
                if r.get("confidence", 0) >= request.min_confidence
            ]
        
        return {
            "success": True,
            "vulnerabilities": ml_result["results"],
            "statistics": ml_result["statistics"],
            "filtered_count": ml_result["filtered_count"],
            "taint_analysis_stats": taint_result.get("statistics", {}),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/ml/feedback")
def ml_submit_feedback(request: MLFeedbackRequest):
    """
    Submit feedback on ML predictions to improve accuracy.
    
    This enables online learning by recording true/false positive feedback.
    """
    try:
        detector = get_ml_detector()
        fp_filter = get_fp_filter()
        
        # Update ML model weights based on feedback
        detector.update_weights({request.feature_id: request.is_true_positive})
        
        # Record false positive for future filtering
        if not request.is_true_positive and request.code_snippet:
            # This would be used by the historical filter
            pass
        
        return {
            "success": True,
            "message": f"Feedback recorded for {request.feature_id}",
            "is_true_positive": request.is_true_positive
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/ml/stats")
def ml_get_statistics():
    """
    Get ML analyzer statistics.
    
    Returns:
    - Total analyzed vulnerabilities
    - True/false positive rates
    - Classification distribution
    """
    try:
        detector = get_ml_detector()
        fp_filter = get_fp_filter()
        
        return {
            "success": True,
            "detection_stats": detector.get_statistics(),
            "filter_stats": fp_filter.get_statistics(),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/ml/reset-stats")
def ml_reset_statistics():
    """Reset ML statistics for fresh tracking."""
    try:
        detector = get_ml_detector()
        detector.reset_statistics()
        
        return {
            "success": True,
            "message": "Statistics reset successfully"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ============================================
# LLM-based Security Analysis API (Phase 4.2)
# ============================================

class LLMAnalyzeRequest(BaseModel):
    file_path: str
    code: Optional[str] = None
    language: Optional[str] = None
    framework: Optional[str] = None
    analysis_type: str = "full"  # full, business_logic, authentication, api_security
    related_files: Optional[Dict[str, str]] = None


class LLMRemediationRequest(BaseModel):
    file_path: str
    code: str
    vulnerability: Dict[str, Any]
    language: Optional[str] = None
    framework: Optional[str] = None


@app.post("/api/llm/analyze")
def llm_analyze_code(request: LLMAnalyzeRequest):
    """
    LLM-based security analysis for advanced vulnerability detection.
    
    Supports analysis types:
    - full: Run all analysis types (business logic, auth, API)
    - business_logic: Broken Access Control, IDOR, Race Conditions
    - authentication: JWT, Session, OAuth vulnerabilities
    - api_security: GraphQL, Rate Limiting, Data Exposure
    
    Returns detailed vulnerabilities with context-aware descriptions.
    """
    try:
        analyzer = get_llm_security_analyzer()
        
        if not analyzer.is_available():
            raise HTTPException(
                status_code=503, 
                detail="LLM service unavailable. Check GROQ_API_KEY configuration."
            )
        
        # Read code from file if not provided
        code = request.code
        if not code and os.path.exists(request.file_path):
            with open(request.file_path, 'r', encoding='utf-8', errors='ignore') as f:
                code = f.read()
        
        if not code:
            raise HTTPException(status_code=400, detail="No code provided or file not found")
        
        # Detect language if not provided
        language = request.language
        if not language:
            ext = os.path.splitext(request.file_path)[1].lower()
            lang_map = {
                '.py': 'python', '.js': 'javascript', '.ts': 'typescript',
                '.java': 'java', '.php': 'php', '.go': 'go'
            }
            language = lang_map.get(ext, 'unknown')
        
        # Detect framework if not provided
        framework = request.framework or analyzer.detect_framework(code, language)
        
        # Detect auth mechanisms
        auth_mechanisms = analyzer.detect_auth_mechanisms(code)
        
        # Build context
        context = LLMCodeContext(
            file_path=request.file_path,
            code=code,
            language=language,
            framework=framework,
            auth_mechanisms=auth_mechanisms,
            related_functions=request.related_files or {}
        )
        
        # Run analysis based on type
        if request.analysis_type == "full":
            results = analyzer.full_analysis(context)
            return {
                "success": True,
                "analysis_type": "full",
                "results": {k: v.to_dict() for k, v in results.items()},
                "detected_framework": framework,
                "auth_mechanisms": auth_mechanisms,
                "statistics": analyzer.get_statistics(),
            }
        elif request.analysis_type == "business_logic":
            result = analyzer.analyze_business_logic(context)
        elif request.analysis_type == "authentication":
            result = analyzer.analyze_authentication(context)
        elif request.analysis_type == "api_security":
            result = analyzer.analyze_api_security(context)
        else:
            raise HTTPException(status_code=400, detail=f"Unknown analysis type: {request.analysis_type}")
        
        return {
            "success": result.success,
            "analysis_type": request.analysis_type,
            "result": result.to_dict(),
            "detected_framework": framework,
            "auth_mechanisms": auth_mechanisms,
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/llm/remediation")
def llm_generate_remediation(request: LLMRemediationRequest):
    """
    Generate intelligent fix suggestions for a vulnerability.
    
    Features:
    - Context-aware code fixes
    - Framework-specific solutions
    - Test case generation
    - Security pattern recommendations
    """
    try:
        analyzer = get_llm_security_analyzer()
        
        if not analyzer.is_available():
            raise HTTPException(
                status_code=503,
                detail="LLM service unavailable. Check GROQ_API_KEY configuration."
            )
        
        # Detect language if not provided
        language = request.language
        if not language:
            ext = os.path.splitext(request.file_path)[1].lower()
            lang_map = {
                '.py': 'python', '.js': 'javascript', '.ts': 'typescript',
                '.java': 'java', '.php': 'php', '.go': 'go'
            }
            language = lang_map.get(ext, 'unknown')
        
        # Detect framework if not provided
        framework = request.framework or analyzer.detect_framework(request.code, language)
        
        # Build context
        context = LLMCodeContext(
            file_path=request.file_path,
            code=request.code,
            language=language,
            framework=framework,
        )
        
        # Generate remediation
        result = analyzer.generate_remediation(request.vulnerability, context)
        
        return {
            "success": result.success,
            "fix_suggestions": result.fix_suggestions,
            "model_used": result.model_used,
            "tokens_used": result.tokens_used,
            "analysis_time_ms": result.analysis_time_ms,
            "error": result.error,
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/llm/analyze/batch")
def llm_analyze_project(request: AnalyzeRequest):
    """
    Batch LLM analysis for an entire project.
    
    Analyzes all source files and aggregates results.
    Returns vulnerabilities grouped by type and severity.
    """
    if not os.path.exists(request.path):
        raise HTTPException(status_code=404, detail="Path not found")
    
    try:
        analyzer = get_llm_security_analyzer()
        
        if not analyzer.is_available():
            raise HTTPException(
                status_code=503,
                detail="LLM service unavailable. Check GROQ_API_KEY configuration."
            )
        
        # Collect source files
        source_files = []
        for root, _, files in os.walk(request.path):
            if any(skip in root for skip in ["venv", "node_modules", ".git", "__pycache__"]):
                continue
            for file in files:
                if file.endswith(('.py', '.js', '.ts', '.php', '.java', '.go')):
                    source_files.append(os.path.join(root, file))
        
        # Limit to prevent excessive API calls
        max_files = 20
        if len(source_files) > max_files:
            source_files = source_files[:max_files]
        
        all_vulnerabilities = []
        analysis_results = []
        
        for file_path in source_files:
            try:
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    code = f.read()
                
                if len(code) < 50:  # Skip very small files
                    continue
                
                # Detect language
                ext = os.path.splitext(file_path)[1].lower()
                lang_map = {
                    '.py': 'python', '.js': 'javascript', '.ts': 'typescript',
                    '.java': 'java', '.php': 'php', '.go': 'go'
                }
                language = lang_map.get(ext, 'unknown')
                
                # Detect framework and auth
                framework = analyzer.detect_framework(code, language)
                auth_mechanisms = analyzer.detect_auth_mechanisms(code)
                
                # Skip files without security-relevant patterns
                if not auth_mechanisms and not any(
                    kw in code.lower() for kw in 
                    ['password', 'token', 'session', 'auth', 'api', 'secret', 'key']
                ):
                    continue
                
                context = LLMCodeContext(
                    file_path=file_path,
                    code=code[:8000],  # Limit code size
                    language=language,
                    framework=framework,
                    auth_mechanisms=auth_mechanisms,
                )
                
                # Run full analysis
                results = analyzer.full_analysis(context)
                
                for analysis_type, result in results.items():
                    if result.success:
                        for vuln in result.vulnerabilities:
                            vuln["file_path"] = file_path
                            vuln["analysis_type"] = analysis_type
                            all_vulnerabilities.append(vuln)
                        
                        analysis_results.append({
                            "file": file_path,
                            "type": analysis_type,
                            "vuln_count": len(result.vulnerabilities),
                        })
                
            except Exception as e:
                print(f"Error analyzing {file_path}: {e}")
                continue
        
        # Group by severity
        by_severity = {"critical": [], "high": [], "medium": [], "low": []}
        for vuln in all_vulnerabilities:
            severity = vuln.get("severity", "medium").lower()
            if severity in by_severity:
                by_severity[severity].append(vuln)
        
        return {
            "success": True,
            "files_analyzed": len(analysis_results),
            "total_vulnerabilities": len(all_vulnerabilities),
            "by_severity": {k: len(v) for k, v in by_severity.items()},
            "vulnerabilities": all_vulnerabilities,
            "analysis_details": analysis_results,
            "statistics": analyzer.get_statistics(),
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/llm/stats")
def llm_get_statistics():
    """Get LLM analyzer statistics."""
    try:
        analyzer = get_llm_security_analyzer()
        return {
            "success": True,
            "available": analyzer.is_available(),
            "statistics": analyzer.get_statistics(),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# Advanced Data-Flow Analysis Endpoints (Phase 4.3)
# =============================================================================

# Global instances for advanced analyzers
_cfg_builder: Optional[CFGBuilder] = None
_pdg_generator: Optional[PDGGenerator] = None
_advanced_analyzer: Optional[AdvancedDataFlowAnalyzer] = None


def get_cfg_builder() -> CFGBuilder:
    """Get or create CFG builder instance."""
    global _cfg_builder
    if _cfg_builder is None:
        _cfg_builder = CFGBuilder()
    return _cfg_builder


def get_pdg_generator() -> PDGGenerator:
    """Get or create PDG generator instance."""
    global _pdg_generator
    if _pdg_generator is None:
        _pdg_generator = PDGGenerator()
    return _pdg_generator


def get_advanced_analyzer(sensitivity: str = "path_sensitive") -> AdvancedDataFlowAnalyzer:
    """Get or create advanced analyzer instance."""
    global _advanced_analyzer
    sens = AnalysisSensitivity(sensitivity)
    if _advanced_analyzer is None or _advanced_analyzer.sensitivity != sens:
        _advanced_analyzer = AdvancedDataFlowAnalyzer(sensitivity=sens)
    return _advanced_analyzer


class CFGRequest(BaseModel):
    """Request for CFG building."""
    file_path: Optional[str] = None
    project_path: Optional[str] = None
    function_name: Optional[str] = None


class DataFlowRequest(BaseModel):
    """Request for advanced data-flow analysis."""
    project_path: str
    sensitivity: str = "path_sensitive"  # flow_insensitive, flow_sensitive, path_sensitive, context_sensitive
    max_depth: int = 10
    include_infeasible: bool = False


class SlicingRequest(BaseModel):
    """Request for program slicing."""
    file_path: str
    function_name: str
    criterion_line: int
    criterion_vars: Optional[List[str]] = None
    direction: str = "backward"  # backward or forward


@app.post("/api/dataflow/cfg")
def build_cfg(request: CFGRequest):
    """
    Build Control Flow Graph for a file or function.
    
    Returns CFG nodes and edges with control flow information.
    """
    try:
        builder = get_cfg_builder()
        
        if request.file_path:
            cfgs = builder.build_from_file(request.file_path)
            
            if request.function_name and request.function_name in cfgs:
                cfg = cfgs[request.function_name]
                return {
                    "success": True,
                    "function": request.function_name,
                    "cfg": _serialize_cfg(cfg),
                }
            else:
                return {
                    "success": True,
                    "file": request.file_path,
                    "functions": list(cfgs.keys()),
                    "cfgs": {name: _serialize_cfg(cfg) for name, cfg in cfgs.items()},
                }
        
        elif request.project_path:
            cfgs = build_project_cfgs(request.project_path)
            return {
                "success": True,
                "project": request.project_path,
                "function_count": len(cfgs),
                "functions": list(cfgs.keys())[:100],  # First 100
            }
        
        else:
            raise HTTPException(status_code=400, detail="file_path or project_path required")
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/dataflow/pdg")
def build_pdg(request: CFGRequest):
    """
    Build Program Dependence Graph for a file or function.
    
    Returns PDG with control and data dependencies.
    """
    try:
        generator = get_pdg_generator()
        
        if request.file_path:
            pdgs = generator.generate_from_file(request.file_path)
            
            if request.function_name and request.function_name in pdgs:
                pdg = pdgs[request.function_name]
                return {
                    "success": True,
                    "function": request.function_name,
                    "pdg": _serialize_pdg(pdg),
                }
            else:
                return {
                    "success": True,
                    "file": request.file_path,
                    "functions": list(pdgs.keys()),
                    "pdgs": {name: _serialize_pdg(pdg) for name, pdg in pdgs.items()},
                }
        
        else:
            raise HTTPException(status_code=400, detail="file_path required")
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/dataflow/analyze")
def analyze_advanced_dataflow(request: DataFlowRequest):
    """
    Perform advanced data-flow analysis on a project.
    
    Supports:
    - Path-sensitive analysis
    - Context-sensitive analysis
    - Flow-sensitive analysis
    - Flow-insensitive analysis
    """
    try:
        findings = analyze_with_advanced_dataflow(
            request.project_path,
            sensitivity=request.sensitivity
        )
        
        # Filter infeasible paths if requested
        if not request.include_infeasible:
            findings = [f for f in findings if f.get('is_feasible', True)]
        
        # Group by vulnerability type
        by_type = {}
        for finding in findings:
            vuln_type = finding.get('vulnerability_type', 'unknown')
            if vuln_type not in by_type:
                by_type[vuln_type] = []
            by_type[vuln_type].append(finding)
        
        return {
            "success": True,
            "project": request.project_path,
            "sensitivity": request.sensitivity,
            "total_findings": len(findings),
            "by_type": {k: len(v) for k, v in by_type.items()},
            "findings": findings[:100],  # Limit response size
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/dataflow/slice")
def compute_slice(request: SlicingRequest):
    """
    Compute a program slice.
    
    Backward slice: All statements affecting the criterion.
    Forward slice: All statements affected by the criterion.
    """
    try:
        generator = get_pdg_generator()
        pdgs = generator.generate_from_file(request.file_path)
        
        pdg = pdgs.get(request.function_name)
        if not pdg:
            raise HTTPException(
                status_code=404,
                detail=f"Function {request.function_name} not found"
            )
        
        # Find criterion node by line
        criterion_node = None
        for node_id, node in pdg.nodes.items():
            if node.cfg_node.line_start == request.criterion_line:
                criterion_node = node_id
                break
        
        if not criterion_node:
            raise HTTPException(
                status_code=404,
                detail=f"No node found at line {request.criterion_line}"
            )
        
        # Compute slice
        criterion_vars = set(request.criterion_vars) if request.criterion_vars else None
        
        if request.direction == "backward":
            slice_nodes = pdg.get_backward_slice(criterion_node, criterion_vars)
        else:
            slice_nodes = pdg.get_forward_slice(criterion_node, criterion_vars)
        
        # Build slice info
        slice_info = []
        for node_id in slice_nodes:
            node = pdg.nodes.get(node_id)
            if node:
                slice_info.append({
                    "node_id": node_id,
                    "line": node.cfg_node.line_start,
                    "code": node.cfg_node.code,
                    "type": node.cfg_node.node_type.value,
                })
        
        # Sort by line
        slice_info.sort(key=lambda x: x['line'])
        
        return {
            "success": True,
            "function": request.function_name,
            "direction": request.direction,
            "criterion_line": request.criterion_line,
            "criterion_vars": list(criterion_vars) if criterion_vars else None,
            "slice_size": len(slice_nodes),
            "slice": slice_info,
        }
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/dataflow/taint-pdg")
def analyze_taint_with_pdg(request: CFGRequest):
    """
    Perform taint analysis using PDG for precise tracking.
    """
    try:
        analyzer = TaintPDGAnalyzer()
        generator = get_pdg_generator()
        
        if request.file_path:
            pdgs = generator.generate_from_file(request.file_path)
            
            all_findings = []
            for name, pdg in pdgs.items():
                findings = analyzer.analyze_pdg(pdg)
                all_findings.extend(findings)
            
            return {
                "success": True,
                "file": request.file_path,
                "functions_analyzed": len(pdgs),
                "findings": all_findings,
            }
        
        elif request.project_path:
            pdgs = generate_project_pdgs(request.project_path)
            
            all_findings = []
            for name, pdg in pdgs.items():
                findings = analyzer.analyze_pdg(pdg)
                for f in findings:
                    f['function'] = name
                all_findings.extend(findings)
            
            return {
                "success": True,
                "project": request.project_path,
                "functions_analyzed": len(pdgs),
                "findings": all_findings[:100],
            }
        
        else:
            raise HTTPException(status_code=400, detail="file_path or project_path required")
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/dataflow/stats")
def get_dataflow_stats():
    """Get data-flow analysis statistics."""
    try:
        analyzer = _advanced_analyzer
        if analyzer:
            return {
                "success": True,
                "available": True,
                "statistics": analyzer.statistics,
                "cfg_cache_size": len(analyzer._cfg_cache),
                "pdg_cache_size": len(analyzer._pdg_cache),
            }
        else:
            return {
                "success": True,
                "available": False,
                "message": "No analysis has been performed yet",
            }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


def _serialize_cfg(cfg: ControlFlowGraph) -> dict:
    """Serialize a CFG to JSON-serializable dict."""
    nodes = []
    for node_id, node in cfg.nodes.items():
        nodes.append({
            "id": node_id,
            "type": node.node_type.value,
            "line_start": node.line_start,
            "line_end": node.line_end,
            "code": node.code[:100],
            "condition": node.condition,
            "defined_vars": list(node.defined_vars),
            "used_vars": list(node.used_vars),
            "is_entry": node.node_type.value == "entry",
            "is_exit": node.node_type.value == "exit",
        })
    
    edges = []
    for edge in cfg.edges:
        edges.append({
            "source": edge.source_id,
            "target": edge.target_id,
            "type": edge.edge_type.value,
            "condition": edge.condition,
        })
    
    return {
        "function_name": cfg.function_name,
        "qualified_name": cfg.qualified_name,
        "node_count": len(nodes),
        "edge_count": len(edges),
        "nodes": nodes,
        "edges": edges,
        "loops": [list(loop) for loop in cfg.loops],
        "back_edges": cfg.back_edges,
    }


def _serialize_pdg(pdg: ProgramDependenceGraph) -> dict:
    """Serialize a PDG to JSON-serializable dict."""
    nodes = []
    for node_id, node in pdg.nodes.items():
        nodes.append({
            "id": node_id,
            "line": node.cfg_node.line_start,
            "code": node.cfg_node.code[:100],
            "type": node.cfg_node.node_type.value,
            "defined_vars": list(node.defined_vars),
            "used_vars": list(node.used_vars),
            "control_deps": list(node.control_dependencies),
            "data_deps": {k: list(v) for k, v in node.data_dependencies.items()},
        })
    
    control_edges = []
    data_edges = []
    for edge in pdg.edges:
        e = {
            "source": edge.source_id,
            "target": edge.target_id,
            "type": edge.dependence_type.value,
            "variable": edge.variable,
            "label": edge.label,
        }
        if edge.dependence_type.value == "control":
            control_edges.append(e)
        else:
            data_edges.append(e)
    
    return {
        "function_name": pdg.function_name,
        "qualified_name": pdg.qualified_name,
        "node_count": len(nodes),
        "control_edge_count": len(control_edges),
        "data_edge_count": len(data_edges),
        "nodes": nodes,
        "control_edges": control_edges,
        "data_edges": data_edges,
        "def_use_chains": {
            var: [{"def_node": d.def_node_id, "uses": d.use_nodes} 
                  for d in chains]
            for var, chains in pdg.def_use_chains.items()
        },
    }