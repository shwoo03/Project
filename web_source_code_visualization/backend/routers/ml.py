"""
ML Router - Machine Learning vulnerability detection endpoints
"""
import os
from typing import List, Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from core.ml_vulnerability_detector import MLVulnerabilityDetector

router = APIRouter(prefix="/api/ml", tags=["ml"])

# ML detector instance
_ml_detector: Optional[MLVulnerabilityDetector] = None


def get_ml_detector() -> MLVulnerabilityDetector:
    global _ml_detector
    if _ml_detector is None:
        _ml_detector = MLVulnerabilityDetector()
    return _ml_detector


class MLAnalysisRequest(BaseModel):
    file_path: str
    include_confidence: bool = True


class MLProjectAnalysisRequest(BaseModel):
    project_path: str
    threshold: float = 0.5
    max_files: int = 100


class MLFeedbackRequest(BaseModel):
    prediction_id: str
    is_correct: bool
    correct_label: Optional[str] = None


@router.post("/analyze")
def ml_analyze_file(request: MLAnalysisRequest):
    """
    Analyze a file using ML-based vulnerability detection.
    """
    if not os.path.exists(request.file_path):
        raise HTTPException(status_code=404, detail="File not found")
    
    try:
        detector = get_ml_detector()
        
        with open(request.file_path, 'r', encoding='utf-8', errors='ignore') as f:
            code = f.read()
        
        predictions = detector.predict(
            code=code,
            file_path=request.file_path,
            include_confidence=request.include_confidence
        )
        
        return {
            "success": True,
            "file": request.file_path,
            "predictions": predictions,
            "model_info": detector.get_model_info()
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/analyze/project")
def ml_analyze_project(request: MLProjectAnalysisRequest):
    """
    Analyze a project using ML-based vulnerability detection.
    """
    if not os.path.exists(request.project_path):
        raise HTTPException(status_code=404, detail="Path not found")
    
    try:
        detector = get_ml_detector()
        
        results = detector.analyze_project(
            project_path=request.project_path,
            threshold=request.threshold,
            max_files=request.max_files
        )
        
        return {
            "success": True,
            "project": request.project_path,
            "files_analyzed": results.get("files_analyzed", 0),
            "vulnerabilities": results.get("vulnerabilities", []),
            "statistics": results.get("statistics", {})
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/feedback")
def submit_feedback(request: MLFeedbackRequest):
    """
    Submit feedback for ML predictions to improve the model.
    """
    try:
        detector = get_ml_detector()
        
        detector.record_feedback(
            prediction_id=request.prediction_id,
            is_correct=request.is_correct,
            correct_label=request.correct_label
        )
        
        return {
            "success": True,
            "message": "Feedback recorded"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/status")
def get_ml_status():
    """
    Get ML model status and statistics.
    """
    try:
        detector = get_ml_detector()
        return {
            "success": True,
            "model_loaded": detector.is_loaded(),
            "model_info": detector.get_model_info(),
            "statistics": detector.get_statistics()
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }


@router.get("/patterns")
def get_vulnerability_patterns():
    """
    Get the vulnerability patterns used by the ML model.
    """
    try:
        detector = get_ml_detector()
        return {
            "success": True,
            "patterns": detector.get_patterns()
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
