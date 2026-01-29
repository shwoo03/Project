import os
from typing import List, Optional, Any, Dict
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv

from core.parser import ParserManager
from core.ai_analyzer import AIAnalyzer
from core.cluster_manager import ClusterManager
from models import ProjectStructure, EndpointNodes

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

class AnalyzeRequest(BaseModel):
    path: str
    cluster: bool = False

@app.post("/api/analyze", response_model=ProjectStructure)
def analyze_project(request: AnalyzeRequest):
    project_path = request.path
    if not os.path.exists(project_path):
        raise HTTPException(status_code=404, detail="Path not found")

    endpoints: List[EndpointNodes] = []
    language_stats = {}
    
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
                        full_name=name, # TODO: Resolve full name with module path
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
                
                print(f"Error parsing {file_path}: {e}")
    
    # Phase 3: Clustering (Optional)
    if request.cluster:
        endpoints = cluster_manager.cluster_endpoints(endpoints)

    return ProjectStructure(
        root_path=project_path,
        language_stats=language_stats,
        endpoints=endpoints
    )
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
