"""
Request/Response Models
"""
from pydantic import BaseModel
from typing import Optional, Dict, List, Any


class ProxyHistoryEntry(BaseModel):
    """Proxy history entry model"""
    id: str
    method: str
    url: str
    host: str
    path: str
    status_code: Optional[int] = None
    length: Optional[int] = None
    mime_type: Optional[str] = None
    timestamp: Optional[str] = None


class RequestDetail(BaseModel):
    """Detailed HTTP request model"""
    id: str
    method: str
    url: str
    host: str
    port: int
    protocol: str  # http or https
    headers: Dict[str, str]
    body: Optional[str] = None
    cookies: Optional[Dict[str, str]] = None


class ResponseDetail(BaseModel):
    """Detailed HTTP response model"""
    status_code: int
    status_text: str
    headers: Dict[str, str]
    body: Optional[str] = None
    length: int
    mime_type: Optional[str] = None
