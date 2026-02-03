"""
Repeater Service - Business logic for HTTP Request Editor
"""
from typing import Optional, Dict, List, Any
from dataclasses import dataclass, field
from services.base import BaseService


@dataclass
class RepeaterTab:
    """Repeater tab data"""
    id: str
    name: str
    request: str
    host: str
    port: int = 443
    use_https: bool = True
    response: Optional[str] = None
    history: List[Dict[str, Any]] = field(default_factory=list)


@dataclass
class SendResult:
    """Result of sending a request"""
    success: bool
    response: Optional[str] = None
    status_code: Optional[int] = None
    elapsed_time: Optional[float] = None
    error: Optional[str] = None


class RepeaterService(BaseService):
    """Service for Repeater-related operations"""
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._tabs: Dict[str, RepeaterTab] = {}
    
    # Tab Management
    def list_tabs(self) -> List[RepeaterTab]:
        """Get all repeater tabs"""
        return list(self._tabs.values())
    
    def get_tab(self, tab_id: str) -> Optional[RepeaterTab]:
        """Get a specific tab by ID"""
        return self._tabs.get(tab_id)
    
    def create_tab(self, tab: RepeaterTab) -> RepeaterTab:
        """Create a new repeater tab"""
        self._tabs[tab.id] = tab
        return tab
    
    def update_tab(self, tab_id: str, tab: RepeaterTab) -> Optional[RepeaterTab]:
        """Update an existing tab"""
        if tab_id not in self._tabs:
            return None
        self._tabs[tab_id] = tab
        return tab
    
    def delete_tab(self, tab_id: str) -> bool:
        """Delete a tab"""
        if tab_id not in self._tabs:
            return False
        del self._tabs[tab_id]
        return True
    
    def tab_exists(self, tab_id: str) -> bool:
        """Check if a tab exists"""
        return tab_id in self._tabs
    
    # Request Sending
    async def send_request(
        self,
        request: str,
        host: str,
        port: int = 443,
        use_https: bool = True
    ) -> SendResult:
        """
        Send an HTTP request through Burp
        
        Args:
            request: Raw HTTP request string
            host: Target host
            port: Target port
            use_https: Whether to use HTTPS
            
        Returns:
            SendResult with response data
        """
        try:
            result = await self.mcp.send_request(
                request=request,
                host=host,
                port=port,
                use_https=use_https
            )
            
            return SendResult(
                success=True,
                response=result.get("response"),
                status_code=result.get("status_code"),
                elapsed_time=result.get("elapsed_time")
            )
        except Exception as e:
            return SendResult(
                success=False,
                error=str(e)
            )
    
    async def send_tab_request(self, tab_id: str) -> Optional[SendResult]:
        """
        Send the request from a specific tab
        
        Args:
            tab_id: ID of the tab
            
        Returns:
            SendResult or None if tab not found
        """
        tab = self.get_tab(tab_id)
        if not tab:
            return None
        
        result = await self.send_request(
            request=tab.request,
            host=tab.host,
            port=tab.port,
            use_https=tab.use_https
        )
        
        # Update tab with response and add to history
        if result.success:
            tab.response = result.response
            tab.history.append({
                "request": tab.request,
                "response": result.response,
                "status_code": result.status_code,
                "elapsed_time": result.elapsed_time
            })
            self._tabs[tab_id] = tab
        
        return result
    
    # Utility Methods
    def parse_host_from_request(self, request: str) -> Optional[str]:
        """Extract host from HTTP request headers"""
        for line in request.split('\n'):
            if line.lower().startswith('host:'):
                return line.split(':', 1)[1].strip()
        return None


# Singleton instance
repeater_service = RepeaterService()
