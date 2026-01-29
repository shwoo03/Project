"""
Streaming Analysis Module for Large Projects

This module provides streaming analysis capabilities for handling
large codebases without loading all results into memory at once.
Uses Server-Sent Events (SSE) for real-time progress updates.
"""

import os
import json
import time
import asyncio
from typing import AsyncGenerator, List, Dict, Any, Optional, Callable
from dataclasses import dataclass, asdict
from enum import Enum
from concurrent.futures import ThreadPoolExecutor, as_completed

from core.parser import ParserManager
from core.symbol_table import SymbolTable, Symbol, SymbolType
from core.analysis_cache import analysis_cache
from models import EndpointNodes, TaintFlowEdge


class StreamEventType(Enum):
    """Types of streaming events."""
    INIT = "init"              # Analysis started
    PROGRESS = "progress"      # Progress update
    FILE_PARSED = "file"       # Single file parsed
    SYMBOLS = "symbols"        # Symbol scan complete
    ENDPOINTS = "endpoints"    # Batch of endpoints
    TAINT_FLOWS = "taint"      # Taint flow edges
    STATS = "stats"            # Statistics update
    COMPLETE = "complete"      # Analysis complete
    ERROR = "error"            # Error occurred


@dataclass
class StreamEvent:
    """A streaming event to be sent to the client."""
    type: StreamEventType
    data: Dict[str, Any]
    timestamp: float = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = time.time()
    
    def to_sse(self) -> str:
        """Convert to Server-Sent Event format."""
        event_data = {
            "type": self.type.value,
            "data": self.data,
            "timestamp": self.timestamp
        }
        return f"data: {json.dumps(event_data)}\n\n"
    
    def to_ndjson(self) -> str:
        """Convert to Newline-Delimited JSON format."""
        event_data = {
            "type": self.type.value,
            "data": self.data,
            "timestamp": self.timestamp
        }
        return json.dumps(event_data) + "\n"


class StreamingAnalyzer:
    """
    Streaming analyzer that yields results progressively.
    
    Features:
    - Real-time progress updates
    - Batch endpoint streaming
    - Memory-efficient for large projects
    - Supports SSE and NDJSON formats
    """
    
    # Configuration
    BATCH_SIZE = 10  # Number of files per batch update
    SUPPORTED_EXTENSIONS = {'.py', '.js', '.jsx', '.ts', '.tsx', '.php', '.java', '.go'}
    SKIP_DIRS = {'venv', 'node_modules', '.git', '__pycache__', '.cache', 'dist', 'build'}
    
    def __init__(self):
        self.parser_manager = ParserManager()
        self._cancel_flag = False
    
    def cancel(self):
        """Request cancellation of ongoing analysis."""
        self._cancel_flag = True
    
    def _collect_files(self, project_path: str) -> List[str]:
        """Collect all parseable files from project."""
        files = []
        for root, dirs, filenames in os.walk(project_path):
            # Skip ignored directories
            dirs[:] = [d for d in dirs if d not in self.SKIP_DIRS]
            
            for filename in filenames:
                ext = os.path.splitext(filename)[1].lower()
                if ext in self.SUPPORTED_EXTENSIONS:
                    files.append(os.path.join(root, filename))
        
        return files
    
    async def analyze_stream(
        self,
        project_path: str,
        cluster: bool = False,
        use_cache: bool = True
    ) -> AsyncGenerator[StreamEvent, None]:
        """
        Stream analysis results as they become available.
        
        Yields StreamEvent objects that can be converted to SSE or NDJSON.
        
        Args:
            project_path: Path to project to analyze
            cluster: Whether to cluster endpoints
            use_cache: Whether to use cached results
            
        Yields:
            StreamEvent objects with analysis progress and results
        """
        self._cancel_flag = False
        start_time = time.time()
        
        # Validate path
        if not os.path.exists(project_path):
            yield StreamEvent(
                type=StreamEventType.ERROR,
                data={"message": "Path not found", "path": project_path}
            )
            return
        
        # Phase 1: Initialize and collect files
        yield StreamEvent(
            type=StreamEventType.INIT,
            data={
                "project_path": project_path,
                "message": "Collecting files..."
            }
        )
        
        all_files = self._collect_files(project_path)
        total_files = len(all_files)
        
        if total_files == 0:
            yield StreamEvent(
                type=StreamEventType.COMPLETE,
                data={
                    "message": "No parseable files found",
                    "total_files": 0,
                    "elapsed_ms": (time.time() - start_time) * 1000
                }
            )
            return
        
        yield StreamEvent(
            type=StreamEventType.PROGRESS,
            data={
                "phase": "collecting",
                "total_files": total_files,
                "message": f"Found {total_files} files to analyze"
            }
        )
        
        # Phase 2: Symbol Scan (lightweight first pass)
        yield StreamEvent(
            type=StreamEventType.PROGRESS,
            data={"phase": "symbols", "message": "Scanning symbols..."}
        )
        
        symbol_table = SymbolTable()
        global_symbols = {}
        symbols_scanned = 0
        
        for file_path in all_files:
            if self._cancel_flag:
                yield StreamEvent(
                    type=StreamEventType.ERROR,
                    data={"message": "Analysis cancelled"}
                )
                return
            
            parser = self.parser_manager.get_parser(file_path)
            if parser:
                try:
                    with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                        content = f.read()
                    
                    symbols = parser.scan_symbols(file_path, content)
                    global_symbols.update(symbols)
                    
                    # Add to symbol table
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
                    
                    symbols_scanned += 1
                except Exception as e:
                    pass  # Silent fail for symbol scan
            
            # Yield progress every batch
            if symbols_scanned % self.BATCH_SIZE == 0:
                yield StreamEvent(
                    type=StreamEventType.PROGRESS,
                    data={
                        "phase": "symbols",
                        "scanned": symbols_scanned,
                        "total": total_files,
                        "percent": round((symbols_scanned / total_files) * 100)
                    }
                )
                # Allow other async tasks to run
                await asyncio.sleep(0)
        
        yield StreamEvent(
            type=StreamEventType.SYMBOLS,
            data={
                "total_symbols": len(global_symbols),
                "files_scanned": symbols_scanned
            }
        )
        
        # Phase 3: Parse files and stream endpoints
        yield StreamEvent(
            type=StreamEventType.PROGRESS,
            data={"phase": "parsing", "message": "Parsing files..."}
        )
        
        all_endpoints: List[EndpointNodes] = []
        language_stats: Dict[str, int] = {}
        parsed_count = 0
        cached_count = 0
        failed_count = 0
        batch_endpoints: List[Dict] = []
        
        for file_path in all_files:
            if self._cancel_flag:
                yield StreamEvent(
                    type=StreamEventType.ERROR,
                    data={"message": "Analysis cancelled"}
                )
                return
            
            parser = self.parser_manager.get_parser(file_path)
            if not parser:
                continue
            
            endpoints = []
            from_cache = False
            
            try:
                # Check cache first
                if use_cache:
                    file_hash = analysis_cache.compute_file_hash(file_path)
                    cached = analysis_cache.get_cached(file_path, file_hash)
                    
                    if cached is not None:
                        endpoints = cached
                        from_cache = True
                        cached_count += 1
                
                # Parse if not cached
                if not from_cache:
                    with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                        content = f.read()
                    
                    endpoints = parser.parse(
                        file_path, content,
                        global_symbols=global_symbols,
                        symbol_table=symbol_table
                    )
                    
                    # Cache the result
                    if use_cache and endpoints:
                        file_hash = analysis_cache.compute_file_hash(file_path)
                        analysis_cache.save(file_path, file_hash, endpoints)
                
                all_endpoints.extend(endpoints)
                
                # Update language stats
                lang = parser.__class__.__name__.replace("Parser", "").lower()
                language_stats[lang] = language_stats.get(lang, 0) + 1
                
                parsed_count += 1
                
                # Serialize endpoints for streaming
                for ep in endpoints:
                    batch_endpoints.append(self._endpoint_to_dict(ep))
                
                # Yield batch of endpoints
                if len(batch_endpoints) >= self.BATCH_SIZE:
                    yield StreamEvent(
                        type=StreamEventType.ENDPOINTS,
                        data={
                            "endpoints": batch_endpoints,
                            "parsed": parsed_count,
                            "cached": cached_count,
                            "total": total_files
                        }
                    )
                    batch_endpoints = []
                    await asyncio.sleep(0)
                
            except Exception as e:
                failed_count += 1
            
            # Progress update
            if (parsed_count + failed_count) % self.BATCH_SIZE == 0:
                yield StreamEvent(
                    type=StreamEventType.PROGRESS,
                    data={
                        "phase": "parsing",
                        "parsed": parsed_count,
                        "cached": cached_count,
                        "failed": failed_count,
                        "total": total_files,
                        "percent": round(((parsed_count + failed_count) / total_files) * 100)
                    }
                )
        
        # Yield remaining endpoints
        if batch_endpoints:
            yield StreamEvent(
                type=StreamEventType.ENDPOINTS,
                data={
                    "endpoints": batch_endpoints,
                    "parsed": parsed_count,
                    "cached": cached_count,
                    "total": total_files
                }
            )
        
        # Phase 4: Clustering (if enabled)
        if cluster and all_endpoints:
            yield StreamEvent(
                type=StreamEventType.PROGRESS,
                data={"phase": "clustering", "message": "Clustering endpoints..."}
            )
            
            from core.cluster_manager import ClusterManager
            cluster_manager = ClusterManager()
            all_endpoints = cluster_manager.cluster_endpoints(all_endpoints)
            await asyncio.sleep(0)
        
        # Phase 5: Taint flow analysis
        yield StreamEvent(
            type=StreamEventType.PROGRESS,
            data={"phase": "taint", "message": "Analyzing taint flows..."}
        )
        
        taint_flows = self._collect_taint_flows(all_endpoints)
        
        if taint_flows:
            yield StreamEvent(
                type=StreamEventType.TAINT_FLOWS,
                data={
                    "flows": [self._taint_flow_to_dict(f) for f in taint_flows],
                    "count": len(taint_flows)
                }
            )
        
        # Phase 6: Complete
        elapsed_ms = (time.time() - start_time) * 1000
        
        yield StreamEvent(
            type=StreamEventType.STATS,
            data={
                "language_stats": language_stats,
                "total_files": total_files,
                "parsed_files": parsed_count,
                "cached_files": cached_count,
                "failed_files": failed_count,
                "total_endpoints": len(all_endpoints),
                "taint_flows": len(taint_flows)
            }
        )
        
        yield StreamEvent(
            type=StreamEventType.COMPLETE,
            data={
                "message": "Analysis complete",
                "elapsed_ms": round(elapsed_ms, 1),
                "project_path": project_path,
                "summary": {
                    "files": parsed_count,
                    "endpoints": len(all_endpoints),
                    "taint_flows": len(taint_flows),
                    "cache_hit_rate": round((cached_count / max(parsed_count, 1)) * 100, 1)
                }
            }
        )
    
    def _endpoint_to_dict(self, ep: EndpointNodes) -> Dict[str, Any]:
        """Convert EndpointNodes to dictionary for JSON serialization."""
        return {
            "id": ep.id,
            "type": ep.type,
            "path": ep.path,
            "method": ep.method,
            "file_path": ep.file_path,
            "line_number": ep.line_number,
            "end_line_number": getattr(ep, 'end_line_number', None),
            "params": [{"name": p.name, "type": p.type, "source": p.source} for p in (ep.params or [])],
            "filters": [{"name": f.name, "args": f.args, "line": f.line} for f in (ep.filters or [])],
            "metadata": ep.metadata or {},
            "children": [self._endpoint_to_dict(c) for c in (ep.children or [])]
        }
    
    def _taint_flow_to_dict(self, flow: TaintFlowEdge) -> Dict[str, Any]:
        """Convert TaintFlowEdge to dictionary."""
        return {
            "id": flow.id,
            "source_node_id": flow.source_node_id,
            "sink_node_id": flow.sink_node_id,
            "source_name": flow.source_name,
            "sink_name": flow.sink_name,
            "vulnerability_type": flow.vulnerability_type,
            "severity": flow.severity,
            "path": flow.path,
            "sanitized": flow.sanitized
        }
    
    def _collect_taint_flows(self, endpoints: List[EndpointNodes]) -> List[TaintFlowEdge]:
        """Collect taint flow edges from endpoints."""
        taint_flows = []
        flow_id = 0
        
        def find_sources_and_sinks(node: EndpointNodes):
            sources = []
            sinks = []
            
            if node.params:
                for param in node.params:
                    sources.append({
                        "node_id": node.id,
                        "name": param.name,
                        "source_type": param.source
                    })
            
            if node.type == "sink":
                sink_info = node.metadata.get("sink_type", "unknown") if node.metadata else "unknown"
                sinks.append({
                    "node_id": node.id,
                    "name": node.path.replace("⚠️ ", ""),
                    "vulnerability_type": sink_info,
                    "severity": node.metadata.get("severity", "MEDIUM") if node.metadata else "MEDIUM"
                })
            
            for child in (node.children or []):
                child_sources, child_sinks = find_sources_and_sinks(child)
                sources.extend(child_sources)
                sinks.extend(child_sinks)
            
            return sources, sinks
        
        for ep in endpoints:
            sources, sinks = find_sources_and_sinks(ep)
            
            for source in sources:
                for sink in sinks:
                    flow_id += 1
                    vuln_type = sink.get("vulnerability_type", "general")
                    
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


# Singleton instance
streaming_analyzer = StreamingAnalyzer()
