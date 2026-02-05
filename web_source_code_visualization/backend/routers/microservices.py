"""
Microservices Router - Microservice analysis endpoints
"""
import os
from typing import List, Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from core.microservice_analyzer import MicroserviceAnalyzer

router = APIRouter(prefix="/api/microservices", tags=["microservices"])

# Initialize microservice analyzer
microservice_analyzer = MicroserviceAnalyzer()


class MicroserviceAnalysisRequest(BaseModel):
    project_path: str
    include_external: bool = True


class ServiceCallsRequest(BaseModel):
    project_path: str
    service_name: str


class DataFlowRequest(BaseModel):
    project_path: str
    start_service: str
    end_service: Optional[str] = None


@router.post("/analyze")
def analyze_microservices(request: MicroserviceAnalysisRequest):
    """
    Analyze microservice architecture.
    Discovers services, APIs, and inter-service communication.
    """
    if not os.path.exists(request.project_path):
        raise HTTPException(status_code=404, detail="Path not found")
    
    try:
        result = microservice_analyzer.analyze_project(
            request.project_path,
            include_external=request.include_external
        )
        return {
            "success": True,
            "services": result.get("services", []),
            "apis": result.get("apis", []),
            "communication": result.get("communication", []),
            "statistics": result.get("statistics", {})
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/openapi")
def parse_openapi(request: MicroserviceAnalysisRequest):
    """
    Parse OpenAPI/Swagger specifications in the project.
    """
    if not os.path.exists(request.project_path):
        raise HTTPException(status_code=404, detail="Path not found")
    
    try:
        specs = microservice_analyzer.parse_openapi_specs(request.project_path)
        return {
            "success": True,
            "specifications": specs
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/protobuf")
def parse_protobuf(request: MicroserviceAnalysisRequest):
    """
    Parse Protocol Buffer definitions in the project.
    """
    if not os.path.exists(request.project_path):
        raise HTTPException(status_code=404, detail="Path not found")
    
    try:
        protos = microservice_analyzer.parse_protobuf(request.project_path)
        return {
            "success": True,
            "services": protos.get("services", []),
            "messages": protos.get("messages", [])
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/calls")
def get_service_calls(request: ServiceCallsRequest):
    """
    Get all external calls made by a service.
    """
    if not os.path.exists(request.project_path):
        raise HTTPException(status_code=404, detail="Path not found")
    
    try:
        calls = microservice_analyzer.get_service_calls(
            request.project_path,
            request.service_name
        )
        return {
            "success": True,
            "service": request.service_name,
            "outgoing_calls": calls.get("outgoing", []),
            "incoming_calls": calls.get("incoming", [])
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/dataflow")
def trace_data_flow(request: DataFlowRequest):
    """
    Trace data flow between microservices.
    """
    if not os.path.exists(request.project_path):
        raise HTTPException(status_code=404, detail="Path not found")
    
    try:
        flows = microservice_analyzer.trace_data_flow(
            request.project_path,
            request.start_service,
            request.end_service
        )
        return {
            "success": True,
            "start_service": request.start_service,
            "end_service": request.end_service,
            "flows": flows
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/graph")
def get_service_graph(request: MicroserviceAnalysisRequest):
    """
    Get the microservice dependency graph.
    """
    if not os.path.exists(request.project_path):
        raise HTTPException(status_code=404, detail="Path not found")
    
    try:
        graph = microservice_analyzer.build_graph(request.project_path)
        return {
            "success": True,
            "nodes": graph.get("nodes", []),
            "edges": graph.get("edges", [])
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
