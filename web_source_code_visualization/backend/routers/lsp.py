"""
LSP Router - Language Server Protocol endpoints
"""
import os
from typing import List, Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from core.lsp_client import LSPClient

router = APIRouter(prefix="/api/lsp", tags=["lsp"])

# LSP client instance
_lsp_client: Optional[LSPClient] = None


def get_lsp_client() -> LSPClient:
    global _lsp_client
    if _lsp_client is None:
        _lsp_client = LSPClient()
    return _lsp_client


class LSPInitRequest(BaseModel):
    project_path: str
    language: str = "python"


class LSPPositionRequest(BaseModel):
    file_path: str
    line: int
    column: int


class LSPCompletionRequest(BaseModel):
    file_path: str
    line: int
    column: int
    trigger_char: Optional[str] = None


class LSPDiagnosticsRequest(BaseModel):
    file_path: str


@router.post("/init")
def initialize_lsp(request: LSPInitRequest):
    """
    Initialize LSP client for a project.
    """
    if not os.path.exists(request.project_path):
        raise HTTPException(status_code=404, detail="Path not found")
    
    try:
        client = get_lsp_client()
        result = client.initialize(
            project_path=request.project_path,
            language=request.language
        )
        return {
            "success": True,
            "capabilities": result.get("capabilities", {}),
            "server_info": result.get("server_info", {})
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/definition")
def go_to_definition(request: LSPPositionRequest):
    """
    Find the definition of a symbol at the given position.
    """
    if not os.path.exists(request.file_path):
        raise HTTPException(status_code=404, detail="File not found")
    
    try:
        client = get_lsp_client()
        locations = client.get_definition(
            file_path=request.file_path,
            line=request.line,
            column=request.column
        )
        return {
            "success": True,
            "locations": locations
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/references")
def find_references(request: LSPPositionRequest):
    """
    Find all references to a symbol at the given position.
    """
    if not os.path.exists(request.file_path):
        raise HTTPException(status_code=404, detail="File not found")
    
    try:
        client = get_lsp_client()
        references = client.get_references(
            file_path=request.file_path,
            line=request.line,
            column=request.column
        )
        return {
            "success": True,
            "references": references
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/hover")
def get_hover_info(request: LSPPositionRequest):
    """
    Get hover information for a symbol.
    """
    if not os.path.exists(request.file_path):
        raise HTTPException(status_code=404, detail="File not found")
    
    try:
        client = get_lsp_client()
        hover = client.get_hover(
            file_path=request.file_path,
            line=request.line,
            column=request.column
        )
        return {
            "success": True,
            "hover": hover
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/completions")
def get_completions(request: LSPCompletionRequest):
    """
    Get completion suggestions at a position.
    """
    if not os.path.exists(request.file_path):
        raise HTTPException(status_code=404, detail="File not found")
    
    try:
        client = get_lsp_client()
        completions = client.get_completions(
            file_path=request.file_path,
            line=request.line,
            column=request.column,
            trigger_char=request.trigger_char
        )
        return {
            "success": True,
            "completions": completions
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/diagnostics")
def get_diagnostics(request: LSPDiagnosticsRequest):
    """
    Get diagnostics (errors, warnings) for a file.
    """
    if not os.path.exists(request.file_path):
        raise HTTPException(status_code=404, detail="File not found")
    
    try:
        client = get_lsp_client()
        diagnostics = client.get_diagnostics(request.file_path)
        return {
            "success": True,
            "diagnostics": diagnostics
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/status")
def get_lsp_status():
    """
    Get LSP client status.
    """
    try:
        client = get_lsp_client()
        return {
            "success": True,
            "initialized": client.is_initialized(),
            "server_running": client.is_running()
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }


@router.post("/shutdown")
def shutdown_lsp():
    """
    Shutdown the LSP server.
    """
    try:
        client = get_lsp_client()
        client.shutdown()
        return {
            "success": True,
            "message": "LSP server shutdown"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
