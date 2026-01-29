"""
Benchmark test for parallel vs sequential analysis.
"""

import time
import os
import sys

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.parallel_analyzer import ParallelAnalyzer
from core.parser.manager import ParserManager
from core.symbol_table import SymbolTable, Symbol, SymbolType


def benchmark_sequential(project_path: str):
    """Run sequential analysis (original method)."""
    parser_manager = ParserManager()
    
    # Collect files
    all_files = []
    for root, dirnames, files in os.walk(project_path):
        # Skip common directories
        dirnames[:] = [d for d in dirnames if d not in {
            '__pycache__', 'node_modules', '.git', '.venv', 'venv',
            'dist', 'build', '.next', 'coverage'
        }]
        for file in files:
            file_path = os.path.join(root, file)
            if parser_manager.get_parser(file_path):
                all_files.append(file_path)
    
    start_time = time.time()
    
    # Phase 1: Symbol Scan
    global_symbols = {}
    symbol_table = SymbolTable()
    
    for file_path in all_files:
        parser = parser_manager.get_parser(file_path)
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
                    symbol_table.add(Symbol(
                        name=name,
                        full_name=name,
                        type=sym_type,
                        file_path=file_path,
                        line_number=info.get("start_line", 0),
                        end_line_number=info.get("end_line", 0),
                    ))
            except Exception as e:
                pass
    
    symbol_time = time.time() - start_time
    
    # Phase 2: Full Parse
    parse_start = time.time()
    endpoints = []
    
    for file_path in all_files:
        parser = parser_manager.get_parser(file_path)
        if parser:
            try:
                with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                    content = f.read()
                parsed = parser.parse(file_path, content, global_symbols=global_symbols)
                endpoints.extend(parsed)
            except Exception as e:
                pass
    
    parse_time = time.time() - parse_start
    total_time = time.time() - start_time
    
    return {
        "method": "Sequential",
        "files": len(all_files),
        "endpoints": len(endpoints),
        "symbols": len(global_symbols),
        "symbol_time_ms": symbol_time * 1000,
        "parse_time_ms": parse_time * 1000,
        "total_time_ms": total_time * 1000
    }


def benchmark_parallel(project_path: str):
    """Run parallel analysis."""
    analyzer = ParallelAnalyzer()
    
    start_time = time.time()
    endpoints, lang_stats, symbol_table = analyzer.analyze_project(project_path)
    total_time = time.time() - start_time
    
    stats = analyzer.get_stats()
    
    return {
        "method": "Parallel",
        "workers": analyzer.max_workers,
        "files": stats["total_files"],
        "endpoints": len(endpoints),
        "symbols": len(symbol_table.get_all()),
        "total_time_ms": total_time * 1000,
        "lang_stats": stats["files_by_language"]
    }


def run_benchmark(project_path: str, runs: int = 3):
    """Run benchmark comparison."""
    print(f"\n{'='*60}")
    print(f"Benchmark: {project_path}")
    print(f"Runs: {runs}")
    print(f"{'='*60}\n")
    
    # Warm-up run
    print("Warming up...")
    _ = benchmark_sequential(project_path)
    _ = benchmark_parallel(project_path)
    print()
    
    # Sequential runs
    seq_times = []
    for i in range(runs):
        result = benchmark_sequential(project_path)
        seq_times.append(result["total_time_ms"])
        print(f"Sequential run {i+1}: {result['total_time_ms']:.1f}ms")
    
    print()
    
    # Parallel runs
    par_times = []
    for i in range(runs):
        result = benchmark_parallel(project_path)
        par_times.append(result["total_time_ms"])
        print(f"Parallel run {i+1}: {result['total_time_ms']:.1f}ms (workers={result['workers']})")
    
    # Summary
    avg_seq = sum(seq_times) / len(seq_times)
    avg_par = sum(par_times) / len(par_times)
    speedup = avg_seq / avg_par if avg_par > 0 else 0
    
    print(f"\n{'='*60}")
    print("SUMMARY")
    print(f"{'='*60}")
    print(f"Files analyzed: {result['files']}")
    print(f"Endpoints found: {result['endpoints']}")
    print(f"Sequential avg: {avg_seq:.1f}ms")
    print(f"Parallel avg:   {avg_par:.1f}ms")
    print(f"Speedup:        {speedup:.2f}x")
    print(f"{'='*60}\n")
    
    return {
        "sequential_avg_ms": avg_seq,
        "parallel_avg_ms": avg_par,
        "speedup": speedup
    }


if __name__ == "__main__":
    # Test with plob directory
    test_path = os.path.join(os.path.dirname(__file__), "..", "plob")
    test_path = os.path.abspath(test_path)
    
    if not os.path.exists(test_path):
        print(f"Test path not found: {test_path}")
        sys.exit(1)
    
    run_benchmark(test_path, runs=3)
    
    # Also test with backend directory itself
    backend_path = os.path.dirname(__file__)
    run_benchmark(backend_path, runs=3)
