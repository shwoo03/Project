"""Core module init"""
from .config import settings
from .mcp_client import mcp_manager

__all__ = ["settings", "mcp_manager"]
