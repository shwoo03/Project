"""
Types Router - Type inference and analysis endpoints
"""
import os
from typing import List, Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel


router = APIRouter(prefix="/api/types", tags=["types"])


# Lazy initialization
def get_type_engine():
    """Get type inference engine instance."""
    from core.type_inferencer import TypeInferencer
    return TypeInferencer()


class TypeAnalysisRequest(BaseModel):
    project_path: str
    include_external: bool = False


class VariableTypeRequest(BaseModel):
    file_path: str
    variable_name: str
    line_number: int


class FunctionTypeRequest(BaseModel):
    file_path: str
    function_name: str


class ClassTypeRequest(BaseModel):
    file_path: str
    class_name: str


@router.post("/analyze")
def analyze_types(request: TypeAnalysisRequest):
    """
    Perform type inference analysis on a project.
    """
    if not os.path.exists(request.project_path):
        raise HTTPException(status_code=404, detail="Path not found")
    
    try:
        engine = get_type_engine()
        result = engine.analyze_project(
            request.project_path,
            include_external=request.include_external
        )
        return {
            "success": True,
            "type_info": result.get("type_info", {}),
            "statistics": result.get("statistics", {})
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/variable")
def get_variable_type(request: VariableTypeRequest):
    """
    Get inferred type for a specific variable.
    """
    if not os.path.exists(request.file_path):
        raise HTTPException(status_code=404, detail="File not found")
    
    try:
        engine = get_type_engine()
        type_info = engine.infer_variable_type(
            file_path=request.file_path,
            variable_name=request.variable_name,
            line_number=request.line_number
        )
        return {
            "success": True,
            "variable": request.variable_name,
            "type": type_info.get("type"),
            "confidence": type_info.get("confidence", 0.0),
            "source": type_info.get("source")
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/function")
def get_function_type(request: FunctionTypeRequest):
    """
    Get function type signature including parameters and return type.
    """
    if not os.path.exists(request.file_path):
        raise HTTPException(status_code=404, detail="File not found")
    
    try:
        engine = get_type_engine()
        type_info = engine.infer_function_type(
            file_path=request.file_path,
            function_name=request.function_name
        )
        return {
            "success": True,
            "function": request.function_name,
            "parameters": type_info.get("parameters", []),
            "return_type": type_info.get("return_type"),
            "async": type_info.get("is_async", False)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/class")
def get_class_type(request: ClassTypeRequest):
    """
    Get class type information including methods and attributes.
    """
    if not os.path.exists(request.file_path):
        raise HTTPException(status_code=404, detail="File not found")
    
    try:
        engine = get_type_engine()
        type_info = engine.analyze_class(
            file_path=request.file_path,
            class_name=request.class_name
        )
        return {
            "success": True,
            "class": request.class_name,
            "methods": type_info.get("methods", []),
            "attributes": type_info.get("attributes", []),
            "bases": type_info.get("bases", [])
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
