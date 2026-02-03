"""
Collaborator Service - Business logic for Out-of-Band Testing
"""
from typing import Optional, Dict, List, Any
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from services.base import BaseService


class InteractionType(str, Enum):
    DNS = "DNS"
    HTTP = "HTTP"
    SMTP = "SMTP"


@dataclass
class CollaboratorPayload:
    """Generated Collaborator payload"""
    payload: str
    created_at: datetime
    description: Optional[str] = None


@dataclass
class Interaction:
    """Collaborator interaction"""
    id: str
    type: InteractionType
    timestamp: datetime
    client_ip: str
    payload: str
    details: Dict[str, Any]


class CollaboratorService(BaseService):
    """Service for Collaborator-related operations"""
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._payloads: List[CollaboratorPayload] = []
        self._interactions: List[Interaction] = []
    
    # Payload Management
    async def generate_payload(self, description: Optional[str] = None) -> CollaboratorPayload:
        """
        Generate a new Collaborator payload
        
        Args:
            description: Optional description for the payload
            
        Returns:
            Generated CollaboratorPayload
        """
        payload_str = await self.mcp.generate_collaborator_payload()
        
        payload = CollaboratorPayload(
            payload=payload_str,
            created_at=datetime.now(),
            description=description
        )
        
        self._payloads.append(payload)
        return payload
    
    def list_payloads(self) -> List[CollaboratorPayload]:
        """Get all generated payloads"""
        return self._payloads.copy()
    
    def clear_payloads(self) -> int:
        """
        Clear all stored payloads
        
        Returns:
            Number of payloads cleared
        """
        count = len(self._payloads)
        self._payloads.clear()
        return count
    
    # Interaction Polling
    async def poll_interactions(self) -> List[Interaction]:
        """
        Poll for new Collaborator interactions
        
        Returns:
            List of new interactions
        """
        raw_interactions = await self.mcp.poll_collaborator()
        
        new_interactions = []
        for raw in raw_interactions:
            interaction = self._parse_interaction(raw)
            new_interactions.append(interaction)
            self._interactions.append(interaction)
        
        return new_interactions
    
    def get_all_interactions(self) -> List[Interaction]:
        """Get all stored interactions"""
        return self._interactions.copy()
    
    def get_filtered_interactions(
        self,
        interaction_type: Optional[InteractionType] = None,
        payload_contains: Optional[str] = None
    ) -> List[Interaction]:
        """
        Get filtered interactions
        
        Args:
            interaction_type: Filter by type (DNS, HTTP, SMTP)
            payload_contains: Filter by payload substring
            
        Returns:
            Filtered list of interactions
        """
        result = self._interactions
        
        if interaction_type:
            result = [i for i in result if i.type == interaction_type]
        
        if payload_contains:
            result = [i for i in result if payload_contains.lower() in i.payload.lower()]
        
        return result
    
    def clear_interactions(self) -> int:
        """
        Clear all stored interactions
        
        Returns:
            Number of interactions cleared
        """
        count = len(self._interactions)
        self._interactions.clear()
        return count
    
    def _parse_interaction(self, raw: Dict) -> Interaction:
        """Parse raw interaction data"""
        type_str = raw.get("type", "HTTP").upper()
        interaction_type = InteractionType(type_str) if type_str in [t.value for t in InteractionType] else InteractionType.HTTP
        
        timestamp_str = raw.get("timestamp", "")
        try:
            timestamp = datetime.fromisoformat(timestamp_str)
        except:
            timestamp = datetime.now()
        
        return Interaction(
            id=raw.get("id", ""),
            type=interaction_type,
            timestamp=timestamp,
            client_ip=raw.get("client_ip", ""),
            payload=raw.get("payload", ""),
            details=raw.get("details", {})
        )


# Singleton instance
collaborator_service = CollaboratorService()
