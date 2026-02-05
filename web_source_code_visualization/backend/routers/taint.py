"""
Taint Router - Taint analysis endpoints
"""
import os
from typing import List, Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from core.interprocedural_taint import (
    InterProceduralTaintAnalyzer,
    analyze_interprocedural_taint
)

router = APIRouter(prefix="/api/taint", tags=["taint"])

# Initialize taint analyzer
taint_analyzer = InterProceduralTaintAnalyzer()


class InterproceduralTaintRequest(BaseModel):
    project_path: str
    max_depth: int = 5


@router.post("/interprocedural")
def interprocedural_taint_analysis(request: InterproceduralTaintRequest):
    """
    Perform interprocedural taint analysis across the project.
    Tracks data flow across function calls and module boundaries.
    """
    if not os.path.exists(request.project_path):
        raise HTTPException(status_code=404, detail="Path not found")
    
    try:
        result = taint_analyzer.analyze_project(
            request.project_path,
            max_depth=request.max_depth
        )
        return {
            "success": True,
            "flows": result.get("flows", []),
            "statistics": result.get("statistics", {}),
            "call_graph": result.get("call_graph", {})
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/interprocedural/full")
def full_taint_analysis(request: InterproceduralTaintRequest):
    """
    Full interprocedural taint analysis with detailed call chains.
    """
    if not os.path.exists(request.project_path):
        raise HTTPException(status_code=404, detail="Path not found")
    
    try:
        flows = analyze_interprocedural_taint(
            request.project_path,
            max_depth=request.max_depth
        )
        return {
            "success": True,
            "flows": flows,
            "total_flows": len(flows)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


class TaintPathRequest(BaseModel):
    project_path: str
    source_file: str
    source_line: int
    sink_type: Optional[str] = None


@router.post("/paths")
def find_taint_paths(request: TaintPathRequest):
    """
    Find all taint paths from a specific source location.
    """
    if not os.path.exists(request.project_path):
        raise HTTPException(status_code=404, detail="Project path not found")
    if not os.path.exists(request.source_file):
        raise HTTPException(status_code=404, detail="Source file not found")
    
    try:
        paths = taint_analyzer.find_paths_from_source(
            project_path=request.project_path,
            source_file=request.source_file,
            source_line=request.source_line,
            sink_type=request.sink_type
        )
        return {
            "success": True,
            "source": {
                "file": request.source_file,
                "line": request.source_line
            },
            "paths": paths,
            "total_paths": len(paths)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
