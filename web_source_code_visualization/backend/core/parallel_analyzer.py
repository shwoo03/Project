"""
Parallel Analyzer Module.

Provides parallel file parsing capabilities using concurrent.futures
for improved performance on large codebases.
"""

import os
from typing import List, Dict, Tuple, Optional, Any
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor, as_completed
from dataclasses import dataclass
import multiprocessing
import time

# Import parsers (will be initialized per-process)
from core.parser.manager import ParserManager
from core.symbol_table import SymbolTable, Symbol, SymbolType
from models import EndpointNodes


@dataclass
class ParseResult:
    """Result from parsing a single file."""
    file_path: str
    endpoints: List[Dict]  # Serializable endpoint data
    symbols: Dict[str, Dict]  # Symbol info
    language: str
    success: bool
    error: Optional[str] = None
    parse_time_ms: float = 0.0


def _init_parser_for_worker():
    """Initialize parser manager for worker process."""
    global _worker_parser_manager
    _worker_parser_manager = ParserManager()


def _scan_symbols_worker(file_path: str) -> Tuple[str, Dict[str, Dict], Optional[str]]:
    """
    Worker function to scan symbols from a single file.
    Runs in a separate process/thread.
    
    Returns:
        Tuple of (file_path, symbols_dict, error_message)
    """
    try:
        global _worker_parser_manager
        if '_worker_parser_manager' not in globals():
            _worker_parser_manager = ParserManager()
        
        parser = _worker_parser_manager.get_parser(file_path)
        if not parser:
            return (file_path, {}, None)
        
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()
        
        symbols = parser.scan_symbols(file_path, content)
        return (file_path, symbols, None)
    
    except Exception as e:
        return (file_path, {}, str(e))


def _parse_file_worker(args: Tuple[str, Dict[str, Dict]]) -> ParseResult:
    """
    Worker function to parse a single file with global context.
    Runs in a separate process/thread.
    
    Args:
        args: Tuple of (file_path, global_symbols)
    
    Returns:
        ParseResult with endpoints and metadata
    """
    file_path, global_symbols = args
    start_time = time.time()
    
    try:
        global _worker_parser_manager
        if '_worker_parser_manager' not in globals():
            _worker_parser_manager = ParserManager()
        
        parser = _worker_parser_manager.get_parser(file_path)
        if not parser:
            return ParseResult(
                file_path=file_path,
                endpoints=[],
                symbols={},
                language="unknown",
                success=True,
                parse_time_ms=0.0
            )
        
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()
        
        # Parse with global context
        endpoints = parser.parse(file_path, content, global_symbols=global_symbols)
        
        # Convert endpoints to serializable dicts
        endpoints_data = [_endpoint_to_dict(ep) for ep in endpoints]
        
        language = parser.__class__.__name__.replace("Parser", "").lower()
        elapsed_ms = (time.time() - start_time) * 1000
        
        return ParseResult(
            file_path=file_path,
            endpoints=endpoints_data,
            symbols={},
            language=language,
            success=True,
            parse_time_ms=elapsed_ms
        )
    
    except Exception as e:
        elapsed_ms = (time.time() - start_time) * 1000
        return ParseResult(
            file_path=file_path,
            endpoints=[],
            symbols={},
            language="unknown",
            success=False,
            error=str(e),
            parse_time_ms=elapsed_ms
        )


def _endpoint_to_dict(endpoint: EndpointNodes) -> Dict:
    """Convert EndpointNodes to a serializable dictionary."""
    return {
        "id": endpoint.id,
        "path": endpoint.path,
        "type": endpoint.type,
        "method": endpoint.method,
        "language": getattr(endpoint, 'language', 'unknown'),
        "line_number": endpoint.line_number,
        "end_line_number": endpoint.end_line_number,
        "file_path": endpoint.file_path,
        "depth": getattr(endpoint, 'depth', 1),
        "params": [{"name": p.name, "source": p.source, "type": p.type} for p in endpoint.params],
        "children": [_endpoint_to_dict(c) for c in endpoint.children],
        "metadata": endpoint.metadata,
        "filters": getattr(endpoint, 'filters', []),
        "sanitization": getattr(endpoint, 'sanitization', []),
        "template_context": getattr(endpoint, 'template_context', []),
        "template_usage": getattr(endpoint, 'template_usage', [])
    }


def _dict_to_endpoint(data: Dict) -> EndpointNodes:
    """Convert dictionary back to EndpointNodes."""
    from models import EndpointNodes, Parameter
    
    return EndpointNodes(
        id=data["id"],
        path=data["path"],
        type=data["type"],
        method=data.get("method", "ALL"),
        language=data.get("language", "unknown"),
        line_number=data.get("line_number", 0),
        end_line_number=data.get("end_line_number", 0),
        file_path=data.get("file_path", ""),
        depth=data.get("depth", 1),
        params=[Parameter(name=p["name"], source=p["source"], type=p.get("type")) for p in data.get("params", [])],
        children=[_dict_to_endpoint(c) for c in data.get("children", [])],
        metadata=data.get("metadata", {}),
        filters=data.get("filters", []),
        sanitization=data.get("sanitization", []),
        template_context=data.get("template_context", []),
        template_usage=data.get("template_usage", [])
    )


class ParallelAnalyzer:
    """
    Parallel file analyzer for large codebases.
    
    Uses ThreadPoolExecutor for I/O-bound symbol scanning
    and ProcessPoolExecutor for CPU-bound parsing.
    
    Automatically falls back to sequential processing for small projects
    where threading overhead would hurt performance.
    """
    
    # Directories to skip
    SKIP_DIRS = {
        '__pycache__', 'node_modules', '.git', '.venv', 'venv',
        'dist', 'build', '.next', 'coverage', '.idea', '.vscode',
        'vendor', 'target', 'bin', 'obj', '.cache'
    }
    
    # Minimum files to benefit from parallel processing
    MIN_FILES_FOR_PARALLEL = 100
    
    def __init__(self, max_workers: Optional[int] = None):
        """
        Initialize the parallel analyzer.
        
        Args:
            max_workers: Maximum number of worker processes/threads.
                        Defaults to CPU count.
        """
        self.max_workers = max_workers or max(1, multiprocessing.cpu_count() - 1)
        self.parser_manager = ParserManager()
        self._stats = {
            "total_files": 0,
            "parsed_files": 0,
            "failed_files": 0,
            "total_time_ms": 0.0,
            "files_by_language": {},
            "mode": "sequential"  # or "parallel"
        }
    
    def collect_files(self, project_path: str) -> List[str]:
        """
        Collect all parseable files from a project.
        
        Args:
            project_path: Root path of the project
            
        Returns:
            List of file paths
        """
        files = []
        
        for root, dirnames, filenames in os.walk(project_path):
            # Filter out skipped directories in-place
            dirnames[:] = [d for d in dirnames if d not in self.SKIP_DIRS]
            
            for filename in filenames:
                file_path = os.path.join(root, filename)
                
                # Check if we have a parser for this file
                if self.parser_manager.get_parser(file_path):
                    files.append(file_path)
        
        return files
    
    def scan_symbols_parallel(self, files: List[str]) -> Tuple[Dict[str, Dict], SymbolTable]:
        """
        Scan symbols from all files in parallel.
        
        Uses ThreadPoolExecutor since file I/O is the bottleneck.
        
        Args:
            files: List of file paths to scan
            
        Returns:
            Tuple of (global_symbols dict, SymbolTable)
        """
        global_symbols = {}
        symbol_table = SymbolTable()
        errors = []
        
        # Use threads for I/O-bound work
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            futures = {
                executor.submit(_scan_symbols_worker, f): f 
                for f in files
            }
            
            for future in as_completed(futures):
                file_path = futures[future]
                try:
                    _, symbols, error = future.result()
                    
                    if error:
                        errors.append((file_path, error))
                        continue
                    
                    # Merge symbols
                    global_symbols.update(symbols)
                    
                    # Populate SymbolTable
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
                
                except Exception as e:
                    errors.append((file_path, str(e)))
        
        if errors:
            print(f"[ParallelAnalyzer] Symbol scan errors: {len(errors)}")
            for path, err in errors[:5]:  # Print first 5 errors
                print(f"  - {path}: {err}")
        
        return global_symbols, symbol_table
    
    def parse_files_parallel(
        self, 
        files: List[str], 
        global_symbols: Dict[str, Dict]
    ) -> List[EndpointNodes]:
        """
        Parse all files in parallel with global context.
        
        Uses ThreadPoolExecutor for better memory sharing of global_symbols.
        
        Args:
            files: List of file paths to parse
            global_symbols: Pre-scanned global symbols for cross-file resolution
            
        Returns:
            List of all parsed EndpointNodes
        """
        all_endpoints = []
        start_time = time.time()
        
        # Prepare arguments for workers
        work_items = [(f, global_symbols) for f in files]
        
        # Use threads to share global_symbols without serialization overhead
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            futures = {
                executor.submit(_parse_file_worker, item): item[0] 
                for item in work_items
            }
            
            for future in as_completed(futures):
                file_path = futures[future]
                try:
                    result: ParseResult = future.result()
                    
                    if result.success:
                        # Convert dicts back to EndpointNodes
                        for ep_dict in result.endpoints:
                            endpoint = _dict_to_endpoint(ep_dict)
                            all_endpoints.append(endpoint)
                        
                        # Update stats
                        self._stats["parsed_files"] += 1
                        lang = result.language
                        self._stats["files_by_language"][lang] = \
                            self._stats["files_by_language"].get(lang, 0) + 1
                    else:
                        self._stats["failed_files"] += 1
                        if result.error:
                            print(f"[ParallelAnalyzer] Parse error {file_path}: {result.error}")
                
                except Exception as e:
                    self._stats["failed_files"] += 1
                    print(f"[ParallelAnalyzer] Future error {file_path}: {e}")
        
        elapsed_ms = (time.time() - start_time) * 1000
        self._stats["total_time_ms"] = elapsed_ms
        self._stats["total_files"] = len(files)
        
        return all_endpoints
    
    def analyze_project(
        self, 
        project_path: str,
        force_parallel: bool = False
    ) -> Tuple[List[EndpointNodes], Dict[str, int], SymbolTable]:
        """
        Analyze an entire project, automatically choosing sequential or parallel mode.
        
        For small projects (< MIN_FILES_FOR_PARALLEL files), uses sequential processing
        to avoid threading overhead. For larger projects, uses parallel processing.
        
        Args:
            project_path: Root path of the project
            force_parallel: Force parallel mode even for small projects
            
        Returns:
            Tuple of (endpoints, language_stats, symbol_table)
        """
        # Reset stats
        self._stats = {
            "total_files": 0,
            "parsed_files": 0,
            "failed_files": 0,
            "total_time_ms": 0.0,
            "files_by_language": {},
            "mode": "sequential"
        }
        
        total_start = time.time()
        
        # 1. Collect files
        print(f"[ParallelAnalyzer] Collecting files from {project_path}...")
        files = self.collect_files(project_path)
        print(f"[ParallelAnalyzer] Found {len(files)} parseable files")
        
        if not files:
            return [], {}, SymbolTable()
        
        # 2. Choose mode based on file count
        use_parallel = force_parallel or len(files) >= self.MIN_FILES_FOR_PARALLEL
        
        if use_parallel:
            self._stats["mode"] = "parallel"
            endpoints, symbol_table = self._analyze_parallel(files)
        else:
            self._stats["mode"] = "sequential"
            endpoints, symbol_table = self._analyze_sequential(files)
        
        total_time = (time.time() - total_start) * 1000
        self._stats["total_time_ms"] = total_time
        print(f"[ParallelAnalyzer] Total analysis time: {total_time:.1f}ms (mode={self._stats['mode']})")
        
        return endpoints, self._stats["files_by_language"], symbol_table
    
    def _analyze_sequential(self, files: List[str]) -> Tuple[List[EndpointNodes], SymbolTable]:
        """
        Analyze files sequentially (better for small projects).
        """
        print(f"[ParallelAnalyzer] Using sequential mode for {len(files)} files")
        
        global_symbols = {}
        symbol_table = SymbolTable()
        endpoints = []
        
        # Phase 1: Symbol Scan
        symbol_start = time.time()
        for file_path in files:
            parser = self.parser_manager.get_parser(file_path)
            if parser:
                try:
                    with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
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
                        ))
                except Exception as e:
                    print(f"[ParallelAnalyzer] Symbol scan error {file_path}: {e}")
        
        symbol_time = (time.time() - symbol_start) * 1000
        print(f"[ParallelAnalyzer] Symbol scan complete: {len(global_symbols)} symbols in {symbol_time:.1f}ms")
        
        # Phase 2: Full Parse
        parse_start = time.time()
        for file_path in files:
            parser = self.parser_manager.get_parser(file_path)
            if parser:
                try:
                    with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                        content = f.read()
                    parsed = parser.parse(file_path, content, global_symbols=global_symbols)
                    endpoints.extend(parsed)
                    
                    self._stats["parsed_files"] += 1
                    lang = parser.__class__.__name__.replace("Parser", "").lower()
                    self._stats["files_by_language"][lang] = \
                        self._stats["files_by_language"].get(lang, 0) + 1
                        
                except Exception as e:
                    self._stats["failed_files"] += 1
                    print(f"[ParallelAnalyzer] Parse error {file_path}: {e}")
        
        parse_time = (time.time() - parse_start) * 1000
        print(f"[ParallelAnalyzer] Parse complete: {len(endpoints)} endpoints in {parse_time:.1f}ms")
        
        self._stats["total_files"] = len(files)
        return endpoints, symbol_table
    
    def _analyze_parallel(self, files: List[str]) -> Tuple[List[EndpointNodes], SymbolTable]:
        """
        Analyze files in parallel (better for large projects).
        """
        print(f"[ParallelAnalyzer] Using parallel mode with {self.max_workers} workers")
        
        # Phase 1: Parallel symbol scanning
        symbol_start = time.time()
        global_symbols, symbol_table = self.scan_symbols_parallel(files)
        symbol_time = (time.time() - symbol_start) * 1000
        print(f"[ParallelAnalyzer] Symbol scan complete: {len(global_symbols)} symbols in {symbol_time:.1f}ms")
        
        # Phase 2: Parallel file parsing
        parse_start = time.time()
        endpoints = self.parse_files_parallel(files, global_symbols)
        parse_time = (time.time() - parse_start) * 1000
        print(f"[ParallelAnalyzer] Parse complete: {len(endpoints)} endpoints in {parse_time:.1f}ms")
        
        return endpoints, symbol_table
    
    def get_stats(self) -> Dict:
        """Get analysis statistics."""
        return self._stats.copy()


# Singleton instance for easy import
parallel_analyzer = ParallelAnalyzer()
