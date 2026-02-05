"""
Cache Router - Cache management endpoints
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, List

from core.analysis_cache import analysis_cache

router = APIRouter(prefix="/api/cache", tags=["cache"])


class CacheInvalidateRequest(BaseModel):
    project_path: Optional[str] = None
    file_paths: Optional[List[str]] = None


@router.get("/stats")
def get_cache_stats():
    """Get cache statistics."""
    return {
        "success": True,
        "stats": analysis_cache.get_stats()
    }


@router.post("/invalidate")
def invalidate_cache(request: CacheInvalidateRequest):
    """Invalidate cache entries for a project or specific files."""
    if request.project_path:
        count = analysis_cache.invalidate_project(request.project_path)
        return {
            "success": True,
            "invalidated_count": count,
            "scope": "project",
            "path": request.project_path
        }
    elif request.file_paths:
        count = 0
        for path in request.file_paths:
            if analysis_cache.invalidate_file(path):
                count += 1
        return {
            "success": True,
            "invalidated_count": count,
            "scope": "files"
        }
    else:
        raise HTTPException(
            status_code=400,
            detail="Either project_path or file_paths must be provided"
        )


@router.delete("")
def clear_cache():
    """Clear all cache entries."""
    analysis_cache.clear()
    return {
        "success": True,
        "message": "Cache cleared"
    }
