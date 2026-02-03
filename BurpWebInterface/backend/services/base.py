"""
Base Service - Abstract base class for all services
"""
from abc import ABC
from typing import Optional
from core.mcp_client import MCPManager, mcp_manager


class BaseService(ABC):
    """Base class for all services with common functionality"""
    
    def __init__(self, mcp: Optional[MCPManager] = None):
        self._mcp = mcp or mcp_manager
    
    @property
    def mcp(self) -> MCPManager:
        """Get MCP manager instance"""
        return self._mcp
    
    async def check_connection(self) -> bool:
        """Check if MCP is connected"""
        return await self._mcp.check_connection()
