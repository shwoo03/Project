"""
Monorepo Router - Monorepo analysis endpoints
"""
import os
from typing import List, Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from core.monorepo_analyzer import MonorepoAnalyzer

router = APIRouter(prefix="/api/monorepo", tags=["monorepo"])

# Initialize monorepo analyzer
monorepo_analyzer = MonorepoAnalyzer()


class MonorepoAnalysisRequest(BaseModel):
    project_path: str


class ProjectDetailsRequest(BaseModel):
    project_path: str
    project_name: str


class AffectedProjectsRequest(BaseModel):
    project_path: str
    changed_files: List[str]


@router.post("/analyze")
def analyze_monorepo(request: MonorepoAnalysisRequest):
    """
    Analyze a monorepo structure.
    Discovers projects, workspaces, and dependencies.
    """
    if not os.path.exists(request.project_path):
        raise HTTPException(status_code=404, detail="Path not found")
    
    try:
        result = monorepo_analyzer.analyze(request.project_path)
        return {
            "success": True,
            "type": result.get("type"),  # npm, lerna, pnpm, etc.
            "projects": result.get("projects", []),
            "dependencies": result.get("dependencies", []),
            "statistics": result.get("statistics", {})
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/project")
def get_project_details(request: ProjectDetailsRequest):
    """
    Get details of a specific project in the monorepo.
    """
    if not os.path.exists(request.project_path):
        raise HTTPException(status_code=404, detail="Path not found")
    
    try:
        project = monorepo_analyzer.get_project(
            request.project_path,
            request.project_name
        )
        return {
            "success": True,
            "project": project
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/dependencies")
def get_dependency_graph(request: MonorepoAnalysisRequest):
    """
    Get the dependency graph between projects.
    """
    if not os.path.exists(request.project_path):
        raise HTTPException(status_code=404, detail="Path not found")
    
    try:
        graph = monorepo_analyzer.get_dependency_graph(request.project_path)
        return {
            "success": True,
            "nodes": graph.get("nodes", []),
            "edges": graph.get("edges", [])
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/affected")
def get_affected_projects(request: AffectedProjectsRequest):
    """
    Find projects affected by file changes.
    Useful for CI/CD optimization.
    """
    if not os.path.exists(request.project_path):
        raise HTTPException(status_code=404, detail="Path not found")
    
    try:
        affected = monorepo_analyzer.get_affected_projects(
            request.project_path,
            request.changed_files
        )
        return {
            "success": True,
            "changed_files": request.changed_files,
            "affected_projects": affected.get("directly_affected", []),
            "transitively_affected": affected.get("transitively_affected", [])
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/build-order")
def get_build_order(request: MonorepoAnalysisRequest):
    """
    Get the optimal build order for projects.
    """
    if not os.path.exists(request.project_path):
        raise HTTPException(status_code=404, detail="Path not found")
    
    try:
        order = monorepo_analyzer.get_build_order(request.project_path)
        return {
            "success": True,
            "build_order": order
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
