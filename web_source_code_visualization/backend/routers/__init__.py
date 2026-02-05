# Backend Routers Package
# This package contains modular API routers split from the main application

from fastapi import APIRouter

# Import all routers
from .analyze import router as analyze_router
from .cache import router as cache_router
from .taint import router as taint_router
from .callgraph import router as callgraph_router
from .imports import router as imports_router
from .types import router as types_router
from .hierarchy import router as hierarchy_router
from .distributed import router as distributed_router
from .microservices import router as microservices_router
from .monorepo import router as monorepo_router
from .lsp import router as lsp_router
from .ml import router as ml_router
from .llm import router as llm_router
from .dataflow import router as dataflow_router
from .semantic import router as semantic_router

__all__ = [
    "analyze_router",
    "cache_router", 
    "taint_router",
    "callgraph_router",
    "imports_router",
    "types_router",
    "hierarchy_router",
    "distributed_router",
    "microservices_router",
    "monorepo_router",
    "lsp_router",
    "ml_router",
    "llm_router",
    "dataflow_router",
    "semantic_router",
]
