"""
Dataflow Router - Advanced data-flow analysis endpoints
"""
import os
from typing import List, Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from core.cfg_builder import CFGBuilder, ControlFlowGraph
from core.pdg_generator import PDGGenerator, ProgramDependenceGraph
from core.advanced_dataflow_analyzer import (
    AdvancedDataFlowAnalyzer,
    AnalysisSensitivity,
    TaintPDGAnalyzer,
    analyze_with_advanced_dataflow,
    build_project_cfgs,
    generate_project_pdgs
)

router = APIRouter(prefix="/api/dataflow", tags=["dataflow"])

# Global instances
_cfg_builder: Optional[CFGBuilder] = None
_pdg_generator: Optional[PDGGenerator] = None
_advanced_analyzer: Optional[AdvancedDataFlowAnalyzer] = None


def get_cfg_builder() -> CFGBuilder:
    global _cfg_builder
    if _cfg_builder is None:
        _cfg_builder = CFGBuilder()
    return _cfg_builder


def get_pdg_generator() -> PDGGenerator:
    global _pdg_generator
    if _pdg_generator is None:
        _pdg_generator = PDGGenerator()
    return _pdg_generator


def get_advanced_analyzer(sensitivity: str = "path_sensitive") -> AdvancedDataFlowAnalyzer:
    global _advanced_analyzer
    sens = AnalysisSensitivity(sensitivity)
    if _advanced_analyzer is None or _advanced_analyzer.sensitivity != sens:
        _advanced_analyzer = AdvancedDataFlowAnalyzer(sensitivity=sens)
    return _advanced_analyzer


class CFGRequest(BaseModel):
    file_path: Optional[str] = None
    project_path: Optional[str] = None
    function_name: Optional[str] = None


class DataFlowRequest(BaseModel):
    project_path: str
    sensitivity: str = "path_sensitive"
    max_depth: int = 10
    include_infeasible: bool = False


class SlicingRequest(BaseModel):
    file_path: str
    function_name: str
    criterion_line: int
    criterion_vars: Optional[List[str]] = None
    direction: str = "backward"


def _serialize_cfg(cfg: ControlFlowGraph) -> dict:
    """Serialize a CFG to JSON-serializable dict."""
    nodes = []
    for node_id, node in cfg.nodes.items():
        nodes.append({
            "id": node_id,
            "type": node.node_type.value,
            "line_start": node.line_start,
            "line_end": node.line_end,
            "code": node.code[:100],
            "defined_vars": list(node.defined_vars),
            "used_vars": list(node.used_vars)
        })
    
    edges = []
    for edge in cfg.edges:
        edges.append({
            "source": edge.source_id,
            "target": edge.target_id,
            "type": edge.edge_type.value,
            "condition": edge.condition
        })
    
    return {
        "function_name": cfg.function_name,
        "node_count": len(nodes),
        "edge_count": len(edges),
        "nodes": nodes,
        "edges": edges
    }


def _serialize_pdg(pdg: ProgramDependenceGraph) -> dict:
    """Serialize a PDG to JSON-serializable dict."""
    nodes = []
    for node_id, node in pdg.nodes.items():
        nodes.append({
            "id": node_id,
            "line": node.cfg_node.line_start,
            "code": node.cfg_node.code[:100],
            "type": node.cfg_node.node_type.value,
            "defined_vars": list(node.defined_vars),
            "used_vars": list(node.used_vars)
        })
    
    control_edges = []
    data_edges = []
    for edge in pdg.edges:
        e = {
            "source": edge.source_id,
            "target": edge.target_id,
            "type": edge.dependence_type.value,
            "variable": edge.variable
        }
        if edge.dependence_type.value == "control":
            control_edges.append(e)
        else:
            data_edges.append(e)
    
    return {
        "function_name": pdg.function_name,
        "node_count": len(nodes),
        "control_edge_count": len(control_edges),
        "data_edge_count": len(data_edges),
        "nodes": nodes,
        "control_edges": control_edges,
        "data_edges": data_edges
    }


@router.post("/cfg")
def build_cfg(request: CFGRequest):
    """Build Control Flow Graph for a file or function."""
    try:
        builder = get_cfg_builder()
        
        if request.file_path:
            cfgs = builder.build_from_file(request.file_path)
            
            if request.function_name and request.function_name in cfgs:
                cfg = cfgs[request.function_name]
                return {
                    "success": True,
                    "function": request.function_name,
                    "cfg": _serialize_cfg(cfg)
                }
            else:
                return {
                    "success": True,
                    "file": request.file_path,
                    "functions": list(cfgs.keys()),
                    "cfgs": {name: _serialize_cfg(cfg) for name, cfg in cfgs.items()}
                }
        
        elif request.project_path:
            cfgs = build_project_cfgs(request.project_path)
            return {
                "success": True,
                "project": request.project_path,
                "function_count": len(cfgs),
                "functions": list(cfgs.keys())[:100]
            }
        
        else:
            raise HTTPException(status_code=400, detail="file_path or project_path required")
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/pdg")
def build_pdg(request: CFGRequest):
    """Build Program Dependence Graph for a file or function."""
    try:
        generator = get_pdg_generator()
        
        if request.file_path:
            pdgs = generator.generate_from_file(request.file_path)
            
            if request.function_name and request.function_name in pdgs:
                pdg = pdgs[request.function_name]
                return {
                    "success": True,
                    "function": request.function_name,
                    "pdg": _serialize_pdg(pdg)
                }
            else:
                return {
                    "success": True,
                    "file": request.file_path,
                    "functions": list(pdgs.keys()),
                    "pdgs": {name: _serialize_pdg(pdg) for name, pdg in pdgs.items()}
                }
        
        else:
            raise HTTPException(status_code=400, detail="file_path required")
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/analyze")
def analyze_advanced_dataflow(request: DataFlowRequest):
    """Perform advanced data-flow analysis on a project."""
    try:
        findings = analyze_with_advanced_dataflow(
            request.project_path,
            sensitivity=request.sensitivity
        )
        
        if not request.include_infeasible:
            findings = [f for f in findings if f.get('is_feasible', True)]
        
        by_type = {}
        for finding in findings:
            vuln_type = finding.get('vulnerability_type', 'unknown')
            if vuln_type not in by_type:
                by_type[vuln_type] = []
            by_type[vuln_type].append(finding)
        
        return {
            "success": True,
            "project": request.project_path,
            "sensitivity": request.sensitivity,
            "total_findings": len(findings),
            "by_type": {k: len(v) for k, v in by_type.items()},
            "findings": findings[:100]
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/slice")
def compute_slice(request: SlicingRequest):
    """Compute a program slice."""
    try:
        generator = get_pdg_generator()
        pdgs = generator.generate_from_file(request.file_path)
        
        pdg = pdgs.get(request.function_name)
        if not pdg:
            raise HTTPException(
                status_code=404,
                detail=f"Function {request.function_name} not found"
            )
        
        # Find criterion node by line
        criterion_node = None
        for node_id, node in pdg.nodes.items():
            if node.cfg_node.line_start == request.criterion_line:
                criterion_node = node_id
                break
        
        if not criterion_node:
            raise HTTPException(
                status_code=404,
                detail=f"No node found at line {request.criterion_line}"
            )
        
        criterion_vars = set(request.criterion_vars) if request.criterion_vars else None
        
        if request.direction == "backward":
            slice_nodes = pdg.get_backward_slice(criterion_node, criterion_vars)
        else:
            slice_nodes = pdg.get_forward_slice(criterion_node, criterion_vars)
        
        slice_info = []
        for node_id in slice_nodes:
            node = pdg.nodes.get(node_id)
            if node:
                slice_info.append({
                    "node_id": node_id,
                    "line": node.cfg_node.line_start,
                    "code": node.cfg_node.code,
                    "type": node.cfg_node.node_type.value
                })
        
        slice_info.sort(key=lambda x: x['line'])
        
        return {
            "success": True,
            "function": request.function_name,
            "direction": request.direction,
            "criterion_line": request.criterion_line,
            "slice_size": len(slice_nodes),
            "slice": slice_info
        }
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/taint-pdg")
def analyze_taint_with_pdg(request: CFGRequest):
    """Perform taint analysis using PDG for precise tracking."""
    try:
        analyzer = TaintPDGAnalyzer()
        generator = get_pdg_generator()
        
        if request.file_path:
            pdgs = generator.generate_from_file(request.file_path)
            
            all_findings = []
            for name, pdg in pdgs.items():
                findings = analyzer.analyze_pdg(pdg)
                all_findings.extend(findings)
            
            return {
                "success": True,
                "file": request.file_path,
                "functions_analyzed": len(pdgs),
                "findings": all_findings
            }
        
        elif request.project_path:
            pdgs = generate_project_pdgs(request.project_path)
            
            all_findings = []
            for name, pdg in pdgs.items():
                findings = analyzer.analyze_pdg(pdg)
                for f in findings:
                    f['function'] = name
                all_findings.extend(findings)
            
            return {
                "success": True,
                "project": request.project_path,
                "functions_analyzed": len(pdgs),
                "findings": all_findings[:100]
            }
        
        else:
            raise HTTPException(status_code=400, detail="file_path or project_path required")
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/stats")
def get_dataflow_stats():
    """Get data-flow analysis statistics."""
    try:
        if _advanced_analyzer:
            return {
                "success": True,
                "available": True,
                "statistics": _advanced_analyzer.statistics,
                "cfg_cache_size": len(_advanced_analyzer._cfg_cache),
                "pdg_cache_size": len(_advanced_analyzer._pdg_cache)
            }
        else:
            return {
                "success": True,
                "available": False,
                "message": "No analysis has been performed yet"
            }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
