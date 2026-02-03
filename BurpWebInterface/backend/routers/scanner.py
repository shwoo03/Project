"""
Scanner Router - Vulnerability Scanning and Issue Management
Refactored to use Service Layer
"""
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from typing import Optional, List
from services import scanner_service, ScanType, Severity
from dataclasses import asdict

router = APIRouter()


class ScanConfigRequest(BaseModel):
    """Scan configuration request"""
    url: str
    scan_type: str = "active"
    scope: Optional[List[str]] = None


@router.post("/scan")
async def start_scan(config: ScanConfigRequest):
    """
    Start a new vulnerability scan
    """
    try:
        scan_type = ScanType(config.scan_type)
        scan = await scanner_service.start_scan(config.url, scan_type)
        
        return {
            "success": True,
            "scan_id": scan.id,
            "message": f"{scan_type.value.capitalize()} scan started"
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/scan/{scan_id}")
async def get_scan_status(scan_id: str):
    """
    Get the status of a scan
    """
    scan = scanner_service.get_scan(scan_id)
    if not scan:
        raise HTTPException(status_code=404, detail="Scan not found")
    
    return {
        "id": scan.id,
        "url": scan.url,
        "scan_type": scan.scan_type.value,
        "status": scan.status.value,
        "progress": scan.progress,
        "issues_found": scan.issues_found
    }


@router.get("/issues")
async def get_issues(
    severity: Optional[str] = None,
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0)
):
    """
    Get all scanner issues with optional filtering
    """
    try:
        severity_filter = Severity(severity) if severity else None
        result = await scanner_service.get_filtered_issues(
            severity=severity_filter,
            limit=limit,
            offset=offset
        )
        
        # Convert issues to dict
        result["issues"] = [asdict(i) for i in result["issues"]]
        
        return result
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid severity: {severity}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/issues/{issue_id}")
async def get_issue_detail(issue_id: str):
    """
    Get detailed information about a specific issue
    """
    try:
        issue = await scanner_service.get_issue_by_id(issue_id)
        if not issue:
            raise HTTPException(status_code=404, detail="Issue not found")
        return asdict(issue)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/scan/{scan_id}")
async def stop_scan(scan_id: str):
    """
    Stop a running scan
    """
    if not scanner_service.stop_scan(scan_id):
        raise HTTPException(status_code=404, detail="Scan not found")
    return {"success": True, "message": "Scan stopped"}


@router.get("/scans")
async def list_scans():
    """
    List all scans
    """
    scans = scanner_service.list_scans()
    return {
        "scans": [
            {
                "id": s.id,
                "url": s.url,
                "scan_type": s.scan_type.value,
                "status": s.status.value,
                "progress": s.progress,
                "issues_found": s.issues_found
            }
            for s in scans
        ]
    }


@router.get("/stats")
async def get_scanner_stats():
    """
    Get scanner statistics
    """
    try:
        stats = await scanner_service.get_stats()
        return asdict(stats)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
