"""
LLM Router - Large Language Model security analysis endpoints
"""
import os
from typing import List, Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel


router = APIRouter(prefix="/api/llm", tags=["llm"])


# Lazy initialization
_llm_analyzer = None


def get_llm_analyzer():
    """Get LLM security analyzer instance."""
    global _llm_analyzer
    if _llm_analyzer is None:
        from core.llm_security_analyzer import LLMSecurityAnalyzer
        _llm_analyzer = LLMSecurityAnalyzer()
    return _llm_analyzer


# Import CodeContext for lazy loading
_CodeContext = None

def get_code_context_class():
    """Get CodeContext class with lazy loading."""
    global _CodeContext
    if _CodeContext is None:
        from core.llm_security_analyzer import CodeContext
        _CodeContext = CodeContext
    return _CodeContext


def get_code_context(file_path: str, code: str, language: str, framework: Optional[str] = None):
    """Create a CodeContext for LLM analysis."""
    CodeContext = get_code_context_class()
    return CodeContext(
        file_path=file_path,
        code=code,
        language=language,
        framework=framework
    )


class LLMAnalysisRequest(BaseModel):
    file_path: str
    code: Optional[str] = None
    analysis_type: str = "full"  # auth, injection, crypto, secrets, full


class LLMRemediationRequest(BaseModel):
    vulnerability: dict
    file_path: str
    code: str


class LLMBatchRequest(BaseModel):
    path: str


@router.get("/status")
def get_llm_status():
    """
    Check LLM availability and status.
    """
    try:
        analyzer = get_llm_analyzer()
        return {
            "success": True,
            "available": analyzer.is_available(),
            "model": analyzer.get_current_model(),
            "statistics": analyzer.get_statistics()
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }


@router.post("/analyze")
def llm_analyze_code(request: LLMAnalysisRequest):
    """
    Analyze code using LLM for security vulnerabilities.
    """
    if not os.path.exists(request.file_path):
        raise HTTPException(status_code=404, detail="File not found")
    
    try:
        analyzer = get_llm_analyzer()
        
        if not analyzer.is_available():
            raise HTTPException(
                status_code=503,
                detail="LLM service unavailable. Check GROQ_API_KEY."
            )
        
        # Read code if not provided
        code = request.code
        if not code:
            with open(request.file_path, 'r', encoding='utf-8', errors='ignore') as f:
                code = f.read()
        
        # Detect language and framework
        ext = os.path.splitext(request.file_path)[1].lower()
        lang_map = {
            '.py': 'python', '.js': 'javascript', '.ts': 'typescript',
            '.java': 'java', '.php': 'php', '.go': 'go'
        }
        language = lang_map.get(ext, 'unknown')
        framework = analyzer.detect_framework(code, language)
        
        context = get_code_context(
            file_path=request.file_path,
            code=code[:8000],  # Limit code size
            language=language,
            framework=framework
        )
        
        # Run analysis
        if request.analysis_type == "full":
            results = analyzer.full_analysis(context)
        else:
            results = {request.analysis_type: analyzer.analyze(context, request.analysis_type)}
        
        return {
            "success": True,
            "file": request.file_path,
            "language": language,
            "framework": framework,
            "results": results
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/remediation")
def llm_generate_remediation(request: LLMRemediationRequest):
    """
    Generate remediation suggestions for a vulnerability.
    """
    try:
        analyzer = get_llm_analyzer()
        
        if not analyzer.is_available():
            raise HTTPException(
                status_code=503,
                detail="LLM service unavailable"
            )
        
        # Detect language
        ext = os.path.splitext(request.file_path)[1].lower()
        lang_map = {
            '.py': 'python', '.js': 'javascript', '.ts': 'typescript',
            '.java': 'java', '.php': 'php', '.go': 'go'
        }
        language = lang_map.get(ext, 'unknown')
        framework = analyzer.detect_framework(request.code, language)
        
        context = get_code_context(
            file_path=request.file_path,
            code=request.code,
            language=language,
            framework=framework
        )
        
        result = analyzer.generate_remediation(request.vulnerability, context)
        
        return {
            "success": result.success,
            "fix_suggestions": result.fix_suggestions,
            "model_used": result.model_used,
            "tokens_used": result.tokens_used,
            "error": result.error
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/analyze/batch")
def llm_analyze_project(request: LLMBatchRequest):
    """
    Batch LLM analysis for an entire project.
    """
    if not os.path.exists(request.path):
        raise HTTPException(status_code=404, detail="Path not found")
    
    try:
        analyzer = get_llm_analyzer()
        
        if not analyzer.is_available():
            raise HTTPException(
                status_code=503,
                detail="LLM service unavailable"
            )
        
        # Collect source files
        source_files = []
        for root, _, files in os.walk(request.path):
            if any(skip in root for skip in ["venv", "node_modules", ".git", "__pycache__"]):
                continue
            for file in files:
                if file.endswith(('.py', '.js', '.ts', '.php', '.java', '.go')):
                    source_files.append(os.path.join(root, file))
        
        # Limit to prevent excessive API calls
        max_files = 20
        if len(source_files) > max_files:
            source_files = source_files[:max_files]
        
        all_vulnerabilities = []
        
        for file_path in source_files:
            try:
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    code = f.read()
                
                if len(code) < 50:
                    continue
                
                ext = os.path.splitext(file_path)[1].lower()
                lang_map = {
                    '.py': 'python', '.js': 'javascript', '.ts': 'typescript',
                    '.java': 'java', '.php': 'php', '.go': 'go'
                }
                language = lang_map.get(ext, 'unknown')
                framework = analyzer.detect_framework(code, language)
                
                context = get_code_context(
                    file_path=file_path,
                    code=code[:8000],
                    language=language,
                    framework=framework
                )
                
                results = analyzer.full_analysis(context)
                
                for analysis_type, result in results.items():
                    if result.success:
                        for vuln in result.vulnerabilities:
                            vuln["file_path"] = file_path
                            vuln["analysis_type"] = analysis_type
                            all_vulnerabilities.append(vuln)
                            
            except Exception as e:
                print(f"Error analyzing {file_path}: {e}")
                continue
        
        # Group by severity
        by_severity = {"critical": [], "high": [], "medium": [], "low": []}
        for vuln in all_vulnerabilities:
            severity = vuln.get("severity", "medium").lower()
            if severity in by_severity:
                by_severity[severity].append(vuln)
        
        return {
            "success": True,
            "files_analyzed": len(source_files),
            "total_vulnerabilities": len(all_vulnerabilities),
            "by_severity": {k: len(v) for k, v in by_severity.items()},
            "vulnerabilities": all_vulnerabilities,
            "statistics": analyzer.get_statistics()
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/stats")
def llm_get_statistics():
    """Get LLM analyzer statistics."""
    try:
        analyzer = get_llm_analyzer()
        return {
            "success": True,
            "available": analyzer.is_available(),
            "statistics": analyzer.get_statistics()
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
