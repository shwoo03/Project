"""
Intruder Service - Business logic for Automated Attacks
"""
from typing import Optional, Dict, List, Any
from dataclasses import dataclass, field
from enum import Enum
import uuid
from services.base import BaseService


class AttackType(str, Enum):
    SNIPER = "sniper"
    BATTERING_RAM = "battering_ram"
    PITCHFORK = "pitchfork"
    CLUSTER_BOMB = "cluster_bomb"


class AttackStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    STOPPED = "stopped"
    ERROR = "error"


@dataclass
class AttackConfig:
    """Configuration for an Intruder attack"""
    request: str
    host: str
    port: int = 443
    use_https: bool = True
    attack_type: AttackType = AttackType.SNIPER
    positions: List[Dict[str, int]] = field(default_factory=list)
    payloads: List[str] = field(default_factory=list)


@dataclass
class AttackResult:
    """Result of a single attack request"""
    payload: str
    status_code: int
    length: int
    elapsed_time: float
    response: Optional[str] = None


@dataclass
class Attack:
    """Intruder attack state"""
    id: str
    config: AttackConfig
    status: AttackStatus = AttackStatus.PENDING
    progress: float = 0.0
    requests_sent: int = 0
    requests_total: int = 0
    results: List[AttackResult] = field(default_factory=list)
    error: Optional[str] = None


class IntruderService(BaseService):
    """Service for Intruder-related operations"""
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._attacks: Dict[str, Attack] = {}
    
    # Attack Management
    def list_attacks(self) -> List[Attack]:
        """Get all attacks"""
        return list(self._attacks.values())
    
    def get_attack(self, attack_id: str) -> Optional[Attack]:
        """Get a specific attack"""
        return self._attacks.get(attack_id)
    
    def attack_exists(self, attack_id: str) -> bool:
        """Check if an attack exists"""
        return attack_id in self._attacks
    
    async def start_attack(self, config: AttackConfig) -> Attack:
        """
        Start a new Intruder attack
        
        Args:
            config: Attack configuration
            
        Returns:
            Created Attack object
        """
        attack_id = str(uuid.uuid4())
        
        attack = Attack(
            id=attack_id,
            config=config,
            status=AttackStatus.RUNNING,
            requests_total=len(config.payloads)
        )
        
        self._attacks[attack_id] = attack
        
        # Start attack via MCP
        await self.mcp.start_intruder_attack({
            "id": attack_id,
            "request": config.request,
            "host": config.host,
            "port": config.port,
            "https": config.use_https,
            "attack_type": config.attack_type.value,
            "positions": config.positions,
            "payloads": config.payloads
        })
        
        return attack
    
    async def update_attack_status(self, attack_id: str) -> Optional[Attack]:
        """
        Fetch and update attack status from MCP
        
        Args:
            attack_id: ID of the attack
            
        Returns:
            Updated Attack or None
        """
        attack = self.get_attack(attack_id)
        if not attack:
            return None
        
        result = await self.mcp.get_intruder_results(attack_id)
        
        attack.progress = result.get("progress", attack.progress)
        attack.requests_sent = result.get("requests_sent", attack.requests_sent)
        
        status_str = result.get("status", attack.status.value)
        if status_str in [s.value for s in AttackStatus]:
            attack.status = AttackStatus(status_str)
        
        # Update results
        raw_results = result.get("results", [])
        attack.results = [
            AttackResult(
                payload=r.get("payload", ""),
                status_code=r.get("status_code", 0),
                length=r.get("length", 0),
                elapsed_time=r.get("elapsed_time", 0.0),
                response=r.get("response")
            )
            for r in raw_results
        ]
        
        self._attacks[attack_id] = attack
        return attack
    
    def pause_attack(self, attack_id: str) -> bool:
        """Pause an attack"""
        attack = self.get_attack(attack_id)
        if not attack:
            return False
        attack.status = AttackStatus.PAUSED
        self._attacks[attack_id] = attack
        return True
    
    def resume_attack(self, attack_id: str) -> bool:
        """Resume a paused attack"""
        attack = self.get_attack(attack_id)
        if not attack:
            return False
        attack.status = AttackStatus.RUNNING
        self._attacks[attack_id] = attack
        return True
    
    def stop_attack(self, attack_id: str) -> bool:
        """Stop and remove an attack"""
        if attack_id not in self._attacks:
            return False
        del self._attacks[attack_id]
        return True
    
    def get_filtered_results(
        self, 
        attack_id: str, 
        status_code: Optional[int] = None,
        min_length: Optional[int] = None,
        max_length: Optional[int] = None
    ) -> List[AttackResult]:
        """
        Get filtered results for an attack
        
        Args:
            attack_id: ID of the attack
            status_code: Filter by status code
            min_length: Minimum response length
            max_length: Maximum response length
            
        Returns:
            Filtered list of results
        """
        attack = self.get_attack(attack_id)
        if not attack:
            return []
        
        results = attack.results
        
        if status_code is not None:
            results = [r for r in results if r.status_code == status_code]
        
        if min_length is not None:
            results = [r for r in results if r.length >= min_length]
        
        if max_length is not None:
            results = [r for r in results if r.length <= max_length]
        
        return results


# Singleton instance
intruder_service = IntruderService()
