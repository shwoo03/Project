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
        for root, _, files in os.walk(project_path):
            if "venv" in root or "node_modules" in root or ".git" in root:
                continue
            for file in files:
                all_files.append(os.path.join(root, file))

        # Phase 1: Global Symbol Scan
        global_symbols = {}
        from core.symbol_table import SymbolTable, Symbol, SymbolType
        symbol_table = SymbolTable()

        for file_path in all_files:
            parser = parser_manager.get_parser(file_path)
            if parser:
                try:
                    with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
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
                except Exception as e:
                    print(f"Error scanning symbols {file_path}: {e}")

        # Phase 2: Detailed Parse with Global Context
        for file_path in all_files:
            parser = parser_manager.get_parser(file_path)
            if parser:
                try:
                    with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                        content = f.read()
                        
                    # Pass global_symbols to parse functionality
                    parsed_endpoints = parser.parse(file_path, content, global_symbols=global_symbols, symbol_table=symbol_table)
                    
                    endpoints.extend(parsed_endpoints)
                    
                    # Update stats
                    lang = parser.__class__.__name__.replace("Parser", "").lower()
                    language_stats[lang] = language_stats.get(lang, 0) + 1
                    
                except Exception as e:
                    print(f"Error parsing {file_path}: {e}")
    
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
