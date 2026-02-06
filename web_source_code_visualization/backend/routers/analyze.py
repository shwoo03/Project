"""
Analyze Router - Project analysis endpoints
"""
import os
from typing import List
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from core.parser import ParserManager
from core.ai_analyzer import AIAnalyzer
from core.cluster_manager import ClusterManager
from core.parallel_analyzer import ParallelAnalyzer
from core.streaming_analyzer import streaming_analyzer
from core.symbol_table import SymbolTable, Symbol, SymbolType
from core.analyzer.semgrep_analyzer import semgrep_analyzer
from models import ProjectStructure, EndpointNodes, TaintFlowEdge

router = APIRouter(prefix="/api", tags=["analyze"])

# Initialize services
parser_manager = ParserManager()
ai_analyzer = AIAnalyzer()
cluster_manager = ClusterManager()
parallel_analyzer = ParallelAnalyzer()


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
    use_parallel: bool = True


class StreamAnalyzeRequest(BaseModel):
    path: str
    cluster: bool = False
    use_cache: bool = True
    format: str = "sse"


class CodeSnippetRequest(BaseModel):
    file_path: str
    start_line: int
    end_line: int


class AIAnalyzeRequest(BaseModel):
    code: str
    context: str = ""
    project_path: str = ""
    related_paths: List[str] = []


class SemgrepRequest(BaseModel):
    project_path: str


@router.post("/analyze", response_model=ProjectStructure)
def analyze_project(request: AnalyzeRequest):
    """Parse and analyze a project directory."""
    project_path = request.path
    if not os.path.exists(project_path):
        raise HTTPException(status_code=404, detail="Path not found")

    endpoints: List[EndpointNodes] = []
    language_stats = {}
    
    # Use parallel analyzer for better performance
    if request.use_parallel:
        try:
            endpoints, language_stats, symbol_table = parallel_analyzer.analyze_project(project_path)
            stats = parallel_analyzer.get_stats()
            print(f"[API] Parallel analysis complete: {stats['parsed_files']}/{stats['total_files']} files, {stats['total_time_ms']:.1f}ms")
        except Exception as e:
            print(f"[API] Parallel analysis failed, falling back to sequential: {e}")
            request.use_parallel = False
    
    # Sequential analysis (fallback or when parallel is disabled)
    if not request.use_parallel:
        all_files = []
        try:
            normalized_project_path = os.path.normpath(project_path)
            for root, _, files in os.walk(normalized_project_path):
                if "venv" in root or "node_modules" in root or ".git" in root:
                    continue
                for file in files:
                    try:
                        file_path = os.path.join(root, file)
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
        symbol_table = SymbolTable()

        for file_path in all_files:
            parser = parser_manager.get_parser(file_path)
            if parser:
                try:
                    normalized_path = os.path.normpath(file_path)
                    with open(normalized_path, "r", encoding="utf-8", errors="ignore") as f:
                        content = f.read()
                    symbols = parser.scan_symbols(file_path, content)
                    global_symbols.update(symbols)
                    
                    for name, info in symbols.items():
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
                    normalized_path = os.path.normpath(file_path)
                    with open(normalized_path, "r", encoding="utf-8", errors="ignore") as f:
                        content = f.read()
                    parsed_endpoints = parser.parse(file_path, content, global_symbols=global_symbols, symbol_table=symbol_table)
                    endpoints.extend(parsed_endpoints)
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


@router.get("/analyze/stats")
def get_analysis_stats():
    """Get statistics from the last parallel analysis."""
    return parallel_analyzer.get_stats()


async def generate_sse_stream(project_path: str, cluster: bool, use_cache: bool):
    """Generate Server-Sent Events stream for analysis."""
    async for event in streaming_analyzer.analyze_stream(project_path, cluster, use_cache):
        yield event.to_sse()


async def generate_ndjson_stream(project_path: str, cluster: bool, use_cache: bool):
    """Generate Newline-Delimited JSON stream for analysis."""
    async for event in streaming_analyzer.analyze_stream(project_path, cluster, use_cache):
        yield event.to_ndjson()


@router.post("/analyze/stream")
async def analyze_project_stream(request: StreamAnalyzeRequest):
    """
    Stream analysis results as Server-Sent Events (SSE) or NDJSON.
    
    This endpoint progressively sends analysis results as they become available,
    allowing the frontend to display progress and partial results immediately.
    """
    if not os.path.exists(request.path):
        raise HTTPException(status_code=404, detail="Path not found")
    
    if request.format == "ndjson":
        return StreamingResponse(
            generate_ndjson_stream(request.path, request.cluster, request.use_cache),
            media_type="application/x-ndjson",
            headers={
                "Cache-Control": "no-cache",
                "X-Accel-Buffering": "no",
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


@router.post("/analyze/stream/cancel")
async def cancel_streaming_analysis():
    """Cancel an ongoing streaming analysis."""
    streaming_analyzer.cancel()
    return {"message": "Cancellation requested"}


@router.post("/snippet")
def get_code_snippet(request: CodeSnippetRequest):
    """Get a code snippet from a file."""
    if not os.path.exists(request.file_path):
        raise HTTPException(status_code=404, detail="File not found")
        
    try:
        with open(request.file_path, "r", encoding="utf-8", errors="ignore") as f:
            lines = f.readlines()
            
        start = max(0, request.start_line - 1)
        end = min(len(lines), request.end_line)
        
        snippet = "".join(lines[start:end])
        return {"code": snippet}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/analyze/ai")
def analyze_code_with_ai(request: AIAnalyzeRequest):
    """Analyze code using AI for security vulnerabilities."""
    print("=" * 80)
    print("[API] /api/analyze/ai endpoint called")
    print("=" * 80)
    try:
        referenced_files = {}
        MAX_FILE_SIZE = 2000
        
        print(f"[API] Request received:")
        print(f"  - Code length: {len(request.code)}")
        print(f"  - Context: {request.context[:100]}...")
        print(f"  - Project path: {request.project_path}")
        print(f"  - Related paths count: {len(request.related_paths)}")
        
        for path in request.related_paths:
            clean_path = path.replace("file:///", "").replace("file://", "")
            if ":" in clean_path and clean_path.startswith("/"):
                clean_path = clean_path[1:]
                
            if not os.path.exists(clean_path):
                print(f"[API] Warning: Path not found: {clean_path}")
                continue
                
            try:
                with open(clean_path, "r", encoding="utf-8", errors="ignore") as f:
                    content = f.read()
                    if len(content) > MAX_FILE_SIZE:
                        content = content[:MAX_FILE_SIZE] + "\n... (truncated)"
                    referenced_files[path] = content
                    print(f"[API] Read reference file: {path} ({len(content)} chars)")
            except Exception as e:
                print(f"[API] Failed to read {clean_path}: {e}")
                pass

        print(f"\n[API] Calling AI analyzer...")
        result = ai_analyzer.analyze_code(
            code=request.code,
            context=request.context,
            referenced_files=referenced_files
        )
        
        print(f"\n[API] Validating response...")
        
        if not isinstance(result, dict):
            print("[API] ❌ Result is not a dict!")
            return {
                "success": False,
                "error": "Invalid response from AI analyzer",
                "analysis": "분석 중 내부 오류가 발생했습니다."
            }
        
        if 'analysis' in result and not result['analysis'].strip():
            print("[API] ❌ Empty analysis detected, marking as error")
            return {
                "success": False,
                "error": "AI returned empty response",
                "analysis": "AI 모델이 빈 응답을 반환했습니다. 다른 모델을 시도해주세요."
            }
        
        if 'success' not in result:
            result['success'] = 'analysis' in result and bool(result.get('analysis', '').strip())
        
        print(f"[API] ✅ Returning successful response")
        return result
        
    except Exception as e:
        print(f"[API] ❌ EXCEPTION in analyze_code_with_ai: {e}")
        import traceback
        traceback.print_exc()
        return {
            "success": False,
            "error": str(e),
            "analysis": f"API 오류: {str(e)}"
        }


@router.post("/analyze/semgrep")
def analyze_project_security(request: SemgrepRequest):
    """Run Semgrep security scan on a project."""
    findings = semgrep_analyzer.scan_project(request.project_path)
    return {"findings": findings}


@router.get("/projects")
def list_projects():
    """
    List available projects from the 'projects' directory.
    Returns a list of directory names that can be analyzed.
    """
    try:
        # Get the backend directory path
        backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        # Go up one level to workspace root
        workspace_root = os.path.dirname(backend_dir)
        projects_dir = os.path.join(workspace_root, "projects")
        
        if not os.path.exists(projects_dir):
            return {"projects": [], "projects_path": projects_dir}
        
        # Get all subdirectories in projects folder
        projects = []
        for item in os.listdir(projects_dir):
            item_path = os.path.join(projects_dir, item)
            if os.path.isdir(item_path):
                projects.append({
                    "name": item,
                    "path": item_path,
                    "full_path": os.path.abspath(item_path)
                })
        
        # Sort by name
        projects.sort(key=lambda x: x["name"])
        
        return {
            "projects": projects,
            "projects_path": projects_dir,
            "count": len(projects)
        }
    except Exception as e:
        print(f"[ERROR] Failed to list projects: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to list projects: {str(e)}")
