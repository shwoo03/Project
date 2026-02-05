"""
Imports Router - Import resolution and module analysis endpoints
"""
import os
from typing import List, Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel


router = APIRouter(prefix="/api/imports", tags=["imports"])


# Lazy initialization
_import_resolver = None


def get_import_resolver(project_path: str):
    """Get or create import resolver for a project."""
    from core.import_resolver import ImportResolver
    return ImportResolver(project_path)


class ImportResolveRequest(BaseModel):
    project_path: str
    file_path: str
    import_name: str


class ImportGraphRequest(BaseModel):
    project_path: str
    depth: int = 5


class SymbolLookupRequest(BaseModel):
    project_path: str
    symbol_name: str
    file_context: Optional[str] = None


class ModuleAnalysisRequest(BaseModel):
    project_path: str
    module_path: str


@router.post("/resolve")
def resolve_import(request: ImportResolveRequest):
    """
    Resolve an import to its source file and symbol.
    """
    if not os.path.exists(request.project_path):
        raise HTTPException(status_code=404, detail="Project path not found")
    if not os.path.exists(request.file_path):
        raise HTTPException(status_code=404, detail="File not found")
    
    try:
        resolver = get_import_resolver(request.project_path)
        result = resolver.resolve(
            file_path=request.file_path,
            import_name=request.import_name
        )
        return {
            "success": True,
            "resolved": result is not None,
            "result": result
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/graph")
def build_import_graph(request: ImportGraphRequest):
    """
    Build import dependency graph for a project.
    """
    if not os.path.exists(request.project_path):
        raise HTTPException(status_code=404, detail="Path not found")
    
    try:
        resolver = get_import_resolver(request.project_path)
        graph = resolver.build_graph(max_depth=request.depth)
        return {
            "success": True,
            "nodes": graph.get("nodes", []),
            "edges": graph.get("edges", []),
            "statistics": graph.get("statistics", {})
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/symbol")
def lookup_symbol(request: SymbolLookupRequest):
    """
    Look up a symbol across the project.
    """
    if not os.path.exists(request.project_path):
        raise HTTPException(status_code=404, detail="Path not found")
    
    try:
        resolver = get_import_resolver(request.project_path)
        results = resolver.find_symbol(
            symbol_name=request.symbol_name,
            context_file=request.file_context
        )
        return {
            "success": True,
            "symbol": request.symbol_name,
            "definitions": results.get("definitions", []),
            "references": results.get("references", [])
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/module")
def analyze_module(request: ModuleAnalysisRequest):
    """
    Analyze a specific module's exports and dependencies.
    """
    if not os.path.exists(request.project_path):
        raise HTTPException(status_code=404, detail="Project path not found")
    
    try:
        resolver = get_import_resolver(request.project_path)
        result = resolver.analyze_module(module_path=request.module_path)
        return {
            "success": True,
            "module": request.module_path,
            "exports": result.get("exports", []),
            "imports": result.get("imports", []),
            "dependencies": result.get("dependencies", [])
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
