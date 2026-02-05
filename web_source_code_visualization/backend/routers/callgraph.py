"""
Callgraph Router - Call graph analysis endpoints
"""
import os
from typing import List, Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from core.call_graph_analyzer import CallGraphAnalyzer

router = APIRouter(prefix="/api/callgraph", tags=["callgraph"])

# Initialize call graph analyzer
call_graph_analyzer = CallGraphAnalyzer()


class CallGraphRequest(BaseModel):
    project_path: str
    entry_point: Optional[str] = None
    max_depth: int = 10


class CallGraphPathRequest(BaseModel):
    project_path: str
    source_function: str
    target_function: str


@router.post("")
def analyze_call_graph(request: CallGraphRequest):
    """
    Analyze call graph for a project.
    Returns nodes (functions) and edges (calls).
    """
    if not os.path.exists(request.project_path):
        raise HTTPException(status_code=404, detail="Path not found")
    
    try:
        result = call_graph_analyzer.analyze_project(
            request.project_path,
            entry_point=request.entry_point,
            max_depth=request.max_depth
        )
        return {
            "success": True,
            "nodes": result.get("nodes", []),
            "edges": result.get("edges", []),
            "statistics": result.get("statistics", {})
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/paths")
def find_call_paths(request: CallGraphPathRequest):
    """
    Find all call paths between two functions.
    """
    if not os.path.exists(request.project_path):
        raise HTTPException(status_code=404, detail="Path not found")
    
    try:
        paths = call_graph_analyzer.find_paths(
            request.project_path,
            request.source_function,
            request.target_function
        )
        return {
            "success": True,
            "source": request.source_function,
            "target": request.target_function,
            "paths": paths,
            "total_paths": len(paths)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


class MetricsRequest(BaseModel):
    project_path: str


@router.post("/metrics")
def get_call_graph_metrics(request: MetricsRequest):
    """
    Get complexity metrics from call graph analysis.
    """
    if not os.path.exists(request.project_path):
        raise HTTPException(status_code=404, detail="Path not found")
    
    try:
        metrics = call_graph_analyzer.get_metrics(request.project_path)
        return {
            "success": True,
            "metrics": metrics
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
