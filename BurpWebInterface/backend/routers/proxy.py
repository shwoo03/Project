"""
Proxy Router - HTTP Proxy History and Request Management
Refactored to use Service Layer
"""
from fastapi import APIRouter, HTTPException, Query, Depends
from typing import Optional
from services import proxy_service, ProxyFilter
from dataclasses import asdict

router = APIRouter()


@router.get("/history")
async def get_proxy_history(
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    method: Optional[str] = None,
    host: Optional[str] = None,
    status_code: Optional[int] = None,
    path_contains: Optional[str] = None
):
    """
    Get proxy history entries with optional filtering
    """
    try:
        filters = ProxyFilter(
            method=method,
            host=host,
            status_code=status_code,
            path_contains=path_contains
        )
        
        result = await proxy_service.get_history(
            limit=limit,
            offset=offset,
            filters=filters if any([method, host, status_code, path_contains]) else None
        )
        
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/request/{request_id}")
async def get_request_details(request_id: str):
    """
    Get detailed information about a specific request
    """
    try:
        details = await proxy_service.get_request_details(request_id)
        if not details:
            raise HTTPException(status_code=404, detail="Request not found")
        return details
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/request/{request_id}/to-repeater")
async def send_to_repeater(request_id: str):
    """
    Send a request from proxy history to Repeater
    """
    try:
        result = await proxy_service.send_to_repeater(request_id)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/stats")
async def get_proxy_stats():
    """
    Get proxy statistics (request counts, methods distribution, etc.)
    """
    try:
        stats = await proxy_service.get_stats()
        return asdict(stats)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
