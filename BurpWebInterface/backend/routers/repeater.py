"""
Repeater Router - HTTP Request Editor and Sender
Refactored to use Service Layer
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
from services import repeater_service, RepeaterTab as ServiceTab
from dataclasses import asdict

router = APIRouter()


class SendRequestPayload(BaseModel):
    """Payload for sending HTTP request"""
    request: str
    host: str
    port: int = 443
    use_https: bool = True


class RepeaterTabRequest(BaseModel):
    """Repeater tab request model"""
    id: str
    name: str
    request: str
    host: str
    port: int = 443
    use_https: bool = True
    response: Optional[str] = None


def _to_service_tab(req: RepeaterTabRequest) -> ServiceTab:
    """Convert request model to service model"""
    return ServiceTab(
        id=req.id,
        name=req.name,
        request=req.request,
        host=req.host,
        port=req.port,
        use_https=req.use_https,
        response=req.response
    )


@router.post("/send")
async def send_request(payload: SendRequestPayload):
    """
    Send an HTTP request through Burp and get the response
    """
    try:
        result = await repeater_service.send_request(
            request=payload.request,
            host=payload.host,
            port=payload.port,
            use_https=payload.use_https
        )
        
        if not result.success:
            raise HTTPException(status_code=500, detail=result.error)
        
        return {
            "success": True,
            "response": result.response,
            "elapsed_time": result.elapsed_time,
            "status_code": result.status_code
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/tabs")
async def list_tabs():
    """
    List all Repeater tabs
    """
    tabs = repeater_service.list_tabs()
    return {"tabs": [asdict(t) for t in tabs]}


@router.post("/tabs")
async def create_tab(tab: RepeaterTabRequest):
    """
    Create a new Repeater tab
    """
    service_tab = _to_service_tab(tab)
    created = repeater_service.create_tab(service_tab)
    return {"success": True, "tab": asdict(created)}


@router.get("/tabs/{tab_id}")
async def get_tab(tab_id: str):
    """
    Get a specific Repeater tab
    """
    tab = repeater_service.get_tab(tab_id)
    if not tab:
        raise HTTPException(status_code=404, detail="Tab not found")
    return asdict(tab)


@router.put("/tabs/{tab_id}")
async def update_tab(tab_id: str, tab: RepeaterTabRequest):
    """
    Update a Repeater tab
    """
    if not repeater_service.tab_exists(tab_id):
        raise HTTPException(status_code=404, detail="Tab not found")
    
    service_tab = _to_service_tab(tab)
    updated = repeater_service.update_tab(tab_id, service_tab)
    return {"success": True, "tab": asdict(updated)}


@router.delete("/tabs/{tab_id}")
async def delete_tab(tab_id: str):
    """
    Delete a Repeater tab
    """
    if not repeater_service.delete_tab(tab_id):
        raise HTTPException(status_code=404, detail="Tab not found")
    return {"success": True, "message": "Tab deleted"}


@router.post("/tabs/{tab_id}/send")
async def send_tab_request(tab_id: str):
    """
    Send the request from a specific tab
    """
    if not repeater_service.tab_exists(tab_id):
        raise HTTPException(status_code=404, detail="Tab not found")
    
    try:
        result = await repeater_service.send_tab_request(tab_id)
        
        if not result or not result.success:
            error = result.error if result else "Unknown error"
            raise HTTPException(status_code=500, detail=error)
        
        return {
            "success": True,
            "response": result.response,
            "elapsed_time": result.elapsed_time,
            "status_code": result.status_code
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
