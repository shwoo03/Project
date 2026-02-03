"""
Collaborator Router - Out-of-Band Testing with Burp Collaborator
Refactored to use Service Layer
"""
from fastapi import APIRouter, HTTPException
from typing import Optional
from services import collaborator_service
from dataclasses import asdict

router = APIRouter()


@router.post("/payload")
async def generate_payload(description: Optional[str] = None):
    """
    Generate a new Burp Collaborator payload
    """
    try:
        payload = await collaborator_service.generate_payload(description)
        
        return {
            "success": True,
            "payload": payload.payload,
            "created_at": payload.created_at.isoformat()
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/payloads")
async def list_payloads():
    """
    List all generated payloads
    """
    payloads = collaborator_service.list_payloads()
    return {
        "payloads": [
            {
                "payload": p.payload,
                "created_at": p.created_at.isoformat(),
                "description": p.description
            }
            for p in payloads
        ]
    }


@router.get("/poll")
async def poll_interactions():
    """
    Poll for new Collaborator interactions
    """
    try:
        from datetime import datetime
        
        interactions = await collaborator_service.poll_interactions()
        
        return {
            "interactions": [
                {
                    "id": i.id,
                    "type": i.type.value,
                    "timestamp": i.timestamp.isoformat(),
                    "client_ip": i.client_ip,
                    "payload": i.payload,
                    "details": i.details
                }
                for i in interactions
            ],
            "count": len(interactions),
            "polled_at": datetime.now().isoformat()
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/interactions")
async def get_all_interactions(
    interaction_type: Optional[str] = None,
    payload: Optional[str] = None
):
    """
    Get all Collaborator interactions with optional filtering
    """
    try:
        from services.collaborator_service import InteractionType
        
        type_filter = None
        if interaction_type:
            try:
                type_filter = InteractionType(interaction_type.upper())
            except ValueError:
                raise HTTPException(status_code=400, detail=f"Invalid interaction type: {interaction_type}")
        
        interactions = collaborator_service.get_filtered_interactions(
            interaction_type=type_filter,
            payload_contains=payload
        )
        
        return {
            "interactions": [
                {
                    "id": i.id,
                    "type": i.type.value,
                    "timestamp": i.timestamp.isoformat(),
                    "client_ip": i.client_ip,
                    "payload": i.payload,
                    "details": i.details
                }
                for i in interactions
            ],
            "count": len(interactions)
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/payloads")
async def clear_payloads():
    """
    Clear all stored payloads
    """
    count = collaborator_service.clear_payloads()
    return {"success": True, "message": f"{count} payloads cleared"}


@router.delete("/interactions")
async def clear_interactions():
    """
    Clear all stored interactions
    """
    count = collaborator_service.clear_interactions()
    return {"success": True, "message": f"{count} interactions cleared"}
