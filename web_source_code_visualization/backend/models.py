from typing import List, Optional, Literal
from pydantic import BaseModel, Field

class Parameter(BaseModel):
    name: str
    type: Optional[str] = None
    source: Literal['query', 'body', 'path', 'header', 'cookie', 'unknown'] = 'unknown'

class EndpointNodes(BaseModel):
    id: str
    path: str
    method: str = "ALL"
    language: str
    file_path: str
    line_number: int
    end_line_number: int = 0
    params: List[Parameter] = []
    children: List['EndpointNodes'] = []
    depth: int = 1
    type: Literal['root', 'child', 'input', 'call', 'default'] = 'root' 
    filters: List[dict] = []
    sanitization: List[dict] = []
    template_context: List[dict] = []
    template_usage: List[dict] = []

    class Config:
        populate_by_name = True

class ProjectStructure(BaseModel):
    root_path: str
    language_stats: dict[str, int]
    endpoints: List[EndpointNodes]
