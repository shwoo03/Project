"""
Hierarchy Router - Class hierarchy analysis endpoints
"""
import os
from typing import List, Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel


router = APIRouter(prefix="/api/hierarchy", tags=["hierarchy"])


# Lazy initialization
def get_hierarchy_analyzer():
    """Get class hierarchy analyzer instance."""
    from core.class_hierarchy import ClassHierarchyAnalyzer
    return ClassHierarchyAnalyzer()


class HierarchyAnalysisRequest(BaseModel):
    project_path: str
    include_external: bool = False


class ClassHierarchyRequest(BaseModel):
    project_path: str
    class_name: str


class ImplementationsRequest(BaseModel):
    project_path: str
    interface_name: str


class MethodHierarchyRequest(BaseModel):
    project_path: str
    class_name: str
    method_name: str


class PolymorphicRequest(BaseModel):
    project_path: str
    base_class: str


@router.post("/analyze")
def analyze_class_hierarchy(request: HierarchyAnalysisRequest):
    """
    Analyze class hierarchy for a project.
    Returns inheritance trees and relationships.
    """
    if not os.path.exists(request.project_path):
        raise HTTPException(status_code=404, detail="Path not found")
    
    try:
        analyzer = get_hierarchy_analyzer()
        result = analyzer.analyze_project(
            request.project_path,
            include_external=request.include_external
        )
        return {
            "success": True,
            "classes": result.get("classes", []),
            "inheritance": result.get("inheritance", []),
            "statistics": result.get("statistics", {})
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/class")
def get_class_hierarchy(request: ClassHierarchyRequest):
    """
    Get complete hierarchy for a specific class.
    """
    if not os.path.exists(request.project_path):
        raise HTTPException(status_code=404, detail="Path not found")
    
    try:
        analyzer = get_hierarchy_analyzer()
        result = analyzer.get_class_hierarchy(
            request.project_path,
            request.class_name
        )
        return {
            "success": True,
            "class": request.class_name,
            "ancestors": result.get("ancestors", []),
            "descendants": result.get("descendants", []),
            "methods": result.get("methods", [])
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/implementations")
def find_implementations(request: ImplementationsRequest):
    """
    Find all implementations of an interface/abstract class.
    """
    if not os.path.exists(request.project_path):
        raise HTTPException(status_code=404, detail="Path not found")
    
    try:
        analyzer = get_hierarchy_analyzer()
        implementations = analyzer.find_implementations(
            request.project_path,
            request.interface_name
        )
        return {
            "success": True,
            "interface": request.interface_name,
            "implementations": implementations
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/method")
def analyze_method_hierarchy(request: MethodHierarchyRequest):
    """
    Analyze method override hierarchy.
    """
    if not os.path.exists(request.project_path):
        raise HTTPException(status_code=404, detail="Path not found")
    
    try:
        analyzer = get_hierarchy_analyzer()
        result = analyzer.analyze_method(
            request.project_path,
            request.class_name,
            request.method_name
        )
        return {
            "success": True,
            "class": request.class_name,
            "method": request.method_name,
            "overrides": result.get("overrides", []),
            "overridden_by": result.get("overridden_by", [])
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/polymorphic")
def find_polymorphic_calls(request: PolymorphicRequest):
    """
    Find potential polymorphic call sites for a base class.
    """
    if not os.path.exists(request.project_path):
        raise HTTPException(status_code=404, detail="Path not found")
    
    try:
        analyzer = get_hierarchy_analyzer()
        call_sites = analyzer.find_polymorphic_calls(
            request.project_path,
            request.base_class
        )
        return {
            "success": True,
            "base_class": request.base_class,
            "call_sites": call_sites
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/graph")
def get_inheritance_graph(request: HierarchyAnalysisRequest):
    """
    Get the complete inheritance graph as nodes and edges.
    """
    if not os.path.exists(request.project_path):
        raise HTTPException(status_code=404, detail="Path not found")
    
    try:
        analyzer = get_hierarchy_analyzer()
        graph = analyzer.build_graph(
            request.project_path,
            include_external=request.include_external
        )
        return {
            "success": True,
            "nodes": graph.get("nodes", []),
            "edges": graph.get("edges", [])
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
