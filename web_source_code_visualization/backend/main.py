import os
from typing import List
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from core.parser import ParserManager
from models import ProjectStructure, EndpointNodes

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

class AnalyzeRequest(BaseModel):
    path: str

@app.post("/api/analyze", response_model=ProjectStructure)
def analyze_project(request: AnalyzeRequest):
    project_path = request.path
    if not os.path.exists(project_path):
        raise HTTPException(status_code=404, detail="Path not found")

    endpoints: List[EndpointNodes] = []
    language_stats = {}

    for root, _, files in os.walk(project_path):
        if "venv" in root or "node_modules" in root or ".git" in root:
            continue
            
        for file in files:
            file_path = os.path.join(root, file)
            parser = parser_manager.get_parser(file_path)
            
            if parser:
                try:
                    with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                        content = f.read()
                        
                    parsed_endpoints = parser.parse(file_path, content)
                    endpoints.extend(parsed_endpoints)
                    
                    # Update stats
                    lang = parser.__class__.__name__.replace("Parser", "").lower()
                    language_stats[lang] = language_stats.get(lang, 0) + 1
                    
                except Exception as e:
                    print(f"Error parsing {file_path}: {e}")

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

@app.get("/")
def read_root():
    return {"message": "API is running"}

@app.get("/health")
def health_check():
    return {"status": "ok"}
