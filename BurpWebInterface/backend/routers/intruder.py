"""
Intruder Router - Automated Attack Configuration and Execution
Refactored to use Service Layer
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, List, Dict
from services import intruder_service, AttackConfig, AttackType
from dataclasses import asdict

router = APIRouter()


class IntruderConfigRequest(BaseModel):
    """Intruder attack configuration request"""
    request: str
    host: str
    port: int = 443
    use_https: bool = True
    attack_type: str = "sniper"
    positions: List[Dict[str, int]] = []
    payloads: List[str] = []


@router.post("/attack")
async def start_attack(config: IntruderConfigRequest):
    """
    Start a new Intruder attack
    """
    try:
        # Convert to service model
        attack_config = AttackConfig(
            request=config.request,
            host=config.host,
            port=config.port,
            use_https=config.use_https,
            attack_type=AttackType(config.attack_type),
            positions=config.positions,
            payloads=config.payloads
        )
        
        attack = await intruder_service.start_attack(attack_config)
        
        return {
            "success": True,
            "attack_id": attack.id,
            "message": "Attack started"
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/attack/{attack_id}")
async def get_attack_status(attack_id: str):
    """
    Get the status of an attack
    """
    if not intruder_service.attack_exists(attack_id):
        raise HTTPException(status_code=404, detail="Attack not found")
    
    try:
        attack = await intruder_service.update_attack_status(attack_id)
        if not attack:
            raise HTTPException(status_code=404, detail="Attack not found")
        
        return {
            "id": attack.id,
            "status": attack.status.value,
            "progress": attack.progress,
            "requests_sent": attack.requests_sent,
            "requests_total": attack.requests_total,
            "results": [asdict(r) for r in attack.results]
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/attack/{attack_id}/results")
async def get_attack_results(
    attack_id: str, 
    filter_status: Optional[int] = None,
    min_length: Optional[int] = None,
    max_length: Optional[int] = None
):
    """
    Get detailed results of an attack with optional filtering
    """
    if not intruder_service.attack_exists(attack_id):
        raise HTTPException(status_code=404, detail="Attack not found")
    
    try:
        # Update status first
        await intruder_service.update_attack_status(attack_id)
        
        # Get filtered results
        results = intruder_service.get_filtered_results(
            attack_id,
            status_code=filter_status,
            min_length=min_length,
            max_length=max_length
        )
        
        return {
            "attack_id": attack_id,
            "total": len(results),
            "results": [asdict(r) for r in results]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/attack/{attack_id}/pause")
async def pause_attack(attack_id: str):
    """
    Pause an ongoing attack
    """
    if not intruder_service.pause_attack(attack_id):
        raise HTTPException(status_code=404, detail="Attack not found")
    return {"success": True, "message": "Attack paused"}


@router.post("/attack/{attack_id}/resume")
async def resume_attack(attack_id: str):
    """
    Resume a paused attack
    """
    if not intruder_service.resume_attack(attack_id):
        raise HTTPException(status_code=404, detail="Attack not found")
    return {"success": True, "message": "Attack resumed"}


@router.delete("/attack/{attack_id}")
async def stop_attack(attack_id: str):
    """
    Stop and delete an attack
    """
    if not intruder_service.stop_attack(attack_id):
        raise HTTPException(status_code=404, detail="Attack not found")
    return {"success": True, "message": "Attack stopped and deleted"}


@router.get("/attacks")
async def list_attacks():
    """
    List all attacks
    """
    attacks = intruder_service.list_attacks()
    return {
        "attacks": [
            {
                "id": a.id,
                "status": a.status.value,
                "progress": a.progress,
                "requests_sent": a.requests_sent,
                "requests_total": a.requests_total
            }
            for a in attacks
        ]
    }
