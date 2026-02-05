"""
Semantic Router - Enhanced semantic analysis endpoints
"""
import os
from typing import List, Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter(prefix="/api/semantic", tags=["semantic"])


class SemanticAnalysisRequest(BaseModel):
    code: str
    file_path: str = "unknown.py"
    language: str = "python"


class DynamicCodeCheckRequest(BaseModel):
    func_name: str
    args: List[str]


class ProjectSemanticAnalysisRequest(BaseModel):
    project_path: str
    extensions: Optional[List[str]] = None


@router.post("/analyze")
def semantic_analyze_code(request: SemanticAnalysisRequest):
    """
    Perform semantic analysis on code.
    Includes dynamic code analysis, precision taint analysis, and semantic analysis.
    """
    try:
        from core.enhanced_security_analyzer import analyze_code_semantically
        
        result = analyze_code_semantically(
            code=request.code,
            file_path=request.file_path,
            language=request.language
        )
        
        return {
            "success": True,
            **result
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/check-dynamic")
def check_dynamic_code_execution(request: DynamicCodeCheckRequest):
    """
    Check if a function call is dynamic code execution.
    Covers eval, exec, __import__, getattr, pickle.loads, etc.
    """
    try:
        from core.enhanced_security_analyzer import check_dynamic_code
        
        result = check_dynamic_code(request.func_name, request.args)
        
        if result:
            return {
                "success": True,
                **result
            }
        else:
            return {
                "success": True,
                "is_dynamic": False,
                "message": "Not a dynamic code execution pattern"
            }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/taint-rules")
def get_taint_analysis_rules():
    """
    Get taint analysis rules.
    Returns sources, sinks, sanitizers, and propagators.
    """
    try:
        from core.enhanced_security_analyzer import get_taint_rules
        
        rules = get_taint_rules()
        
        return {
            "success": True,
            "rules": rules,
            "statistics": {
                "sources": len(rules["sources"]),
                "sinks": len(rules["sinks"]),
                "sanitizers": len(rules["sanitizers"]),
                "propagators": len(rules["propagators"])
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/analyze-project")
def semantic_analyze_project(request: ProjectSemanticAnalysisRequest):
    """
    Perform semantic analysis on an entire project.
    """
    if not os.path.exists(request.project_path):
        raise HTTPException(status_code=404, detail="Project path not found")
    
    try:
        from core.enhanced_security_analyzer import EnhancedSecurityAnalyzer
        
        analyzer = EnhancedSecurityAnalyzer()
        result = analyzer.analyze_project(
            project_path=request.project_path,
            extensions=request.extensions
        )
        
        # Serialize findings
        serialized_findings = []
        for finding in result.get("findings", []):
            serialized_findings.append({
                "type": finding.vulnerability_type,
                "severity": finding.severity,
                "file": finding.file_path,
                "line": finding.line,
                "column": finding.column,
                "message": finding.message,
                "code": finding.code_snippet,
                "data_flow": finding.data_flow,
                "path_conditions": finding.path_conditions,
                "is_reachable": finding.is_reachable,
                "confidence": finding.confidence,
                "cwe": finding.cwe_id,
                "remediation": finding.remediation
            })
        
        return {
            "success": True,
            "project_path": request.project_path,
            "files_analyzed": result.get("files_analyzed", 0),
            "total_findings": result.get("total_findings", 0),
            "by_severity": result.get("by_severity", {}),
            "by_type": result.get("by_type", {}),
            "findings": serialized_findings
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/dynamic-patterns")
def get_dynamic_code_patterns():
    """
    Get dynamic code execution patterns.
    Returns function names, severity, CWE IDs, and mitigations.
    """
    try:
        from core.enhanced_security_analyzer import DYNAMIC_CODE_PATTERNS
        
        patterns = []
        for p in DYNAMIC_CODE_PATTERNS:
            patterns.append({
                "name": p.name,
                "type": p.pattern_type.value,
                "function_names": p.function_names,
                "severity": p.severity,
                "description": p.description,
                "cwe_id": p.cwe_id,
                "mitigation": p.mitigation
            })
        
        by_severity = {
            "CRITICAL": [p for p in patterns if p["severity"] == "CRITICAL"],
            "HIGH": [p for p in patterns if p["severity"] == "HIGH"],
            "MEDIUM": [p for p in patterns if p["severity"] == "MEDIUM"],
            "LOW": [p for p in patterns if p["severity"] == "LOW"]
        }
        
        return {
            "success": True,
            "total_patterns": len(patterns),
            "patterns": patterns,
            "by_severity": {k: len(v) for k, v in by_severity.items()}
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
