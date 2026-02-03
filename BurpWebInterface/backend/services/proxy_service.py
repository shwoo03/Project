"""
Proxy Service - Business logic for HTTP Proxy History
"""
from typing import Optional, List, Dict, Any
from dataclasses import dataclass
from services.base import BaseService
from core.websocket import manager

@dataclass
class ProxyFilter:
    """Filter options for proxy history"""
    method: Optional[str] = None
    host: Optional[str] = None
    status_code: Optional[int] = None
    path_contains: Optional[str] = None


@dataclass
class ProxyStats:
    """Proxy statistics"""
    total_requests: int
    methods: Dict[str, int]
    status_codes: Dict[int, int]
    top_hosts: Dict[str, int]


class ProxyService(BaseService):
    """Service for Proxy-related operations"""
    
    async def get_history(
        self, 
        limit: int = 100, 
        offset: int = 0,
        filters: Optional[ProxyFilter] = None
    ) -> Dict[str, Any]:
        """
        Get proxy history with optional filtering
        
        Args:
            limit: Maximum number of entries to return
            offset: Offset for pagination
            filters: Optional filter criteria
            
        Returns:
            Dictionary with entries, total count, and pagination info
        """
        entries = await self.mcp.get_proxy_history(limit=limit, offset=offset)
        
        # Apply filters if provided
        if filters:
            entries = self._apply_filters(entries, filters)
        
        return {
            "entries": entries,
            "total": len(entries),
            "limit": limit,
            "offset": offset
        }
    
    def _apply_filters(self, entries: List[Dict], filters: ProxyFilter) -> List[Dict]:
        """Apply filter criteria to entries"""
        result = entries
        
        if filters.method:
            result = [e for e in result if e.get("method", "").upper() == filters.method.upper()]
        
        if filters.host:
            result = [e for e in result if filters.host.lower() in e.get("host", "").lower()]
        
        if filters.status_code:
            result = [e for e in result if e.get("status_code") == filters.status_code]
        
        if filters.path_contains:
            result = [e for e in result if filters.path_contains.lower() in e.get("path", "").lower()]
        
        return result
    
    async def get_request_details(self, request_id: str) -> Optional[Dict]:
        """
        Get detailed information about a specific request
        """
        return await self.mcp.get_request_details(request_id)
    
    async def send_to_repeater(self, request_id: str) -> Dict:
        """
        Send a request from proxy history to Repeater
        """
        result = await self.mcp.send_to_repeater(request_id)
        return {
            "success": True,
            "message": "Request sent to Repeater",
            "result": result
        }
    
    async def get_stats(self) -> ProxyStats:
        """
        Calculate proxy statistics
        """
        entries = await self.mcp.get_proxy_history(limit=1000, offset=0)
        
        methods: Dict[str, int] = {}
        status_codes: Dict[int, int] = {}
        hosts: Dict[str, int] = {}
        
        for entry in entries:
            # Count methods
            method = entry.get("method", "UNKNOWN")
            methods[method] = methods.get(method, 0) + 1
            
            # Count status codes
            status = entry.get("status_code", 0)
            status_codes[status] = status_codes.get(status, 0) + 1
            
            # Count hosts
            host = entry.get("host", "unknown")
            hosts[host] = hosts.get(host, 0) + 1
        
        # Get top 10 hosts
        top_hosts = dict(sorted(hosts.items(), key=lambda x: x[1], reverse=True)[:10])
        
        return ProxyStats(
            total_requests=len(entries),
            methods=methods,
            status_codes=status_codes,
            top_hosts=top_hosts
        )

    async def broadcast_new_request(self, request_data: Dict[str, Any]):
        """
        Broadcast a new request to all connected clients
        """
        await manager.broadcast({
            "type": "PROXY_NEW_REQUEST",
            "data": request_data
        })


# Singleton instance
proxy_service = ProxyService()
