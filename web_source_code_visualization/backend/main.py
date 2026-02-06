"""
Web Source Code Visualization API
Main entry point - Refactored version with modular routers
"""
import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

# Load .env from root directory
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(__file__)), '.env'))

# Create FastAPI app
app = FastAPI(
    title="Web Source Code Visualization API",
    description="Security-focused code analysis and visualization API",
    version="2.0.0"
)

# CORS Setup
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:10009", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Import and include routers
from routers import (
    analyze_router,
    cache_router,
    taint_router,
    callgraph_router,
    imports_router,
    types_router,
    hierarchy_router,
    distributed_router,
    microservices_router,
    monorepo_router,
    lsp_router,
    ml_router,
    llm_router,
    dataflow_router,
    semantic_router,
)

# Include all routers
app.include_router(analyze_router)
app.include_router(cache_router)
app.include_router(taint_router)
app.include_router(callgraph_router)
app.include_router(imports_router)
app.include_router(types_router)
app.include_router(hierarchy_router)
app.include_router(distributed_router)
app.include_router(microservices_router)
app.include_router(monorepo_router)
app.include_router(lsp_router)
app.include_router(ml_router)
app.include_router(llm_router)
app.include_router(dataflow_router)
app.include_router(semantic_router)


@app.get("/")
def root():
    """API root endpoint."""
    return {
        "name": "Web Source Code Visualization API",
        "version": "2.0.0",
        "status": "running"
    }


@app.get("/health")
def health_check():
    """Health check endpoint."""
    return {"status": "healthy"}


@app.get("/api/docs")
def get_api_docs():
    """Get available API endpoints."""
    return {
        "endpoints": [
            {"prefix": "/api/analyze", "description": "Project analysis endpoints"},
            {"prefix": "/api/cache", "description": "Cache management endpoints"},
            {"prefix": "/api/taint", "description": "Taint analysis endpoints"},
            {"prefix": "/api/callgraph", "description": "Call graph analysis endpoints"},
            {"prefix": "/api/imports", "description": "Import resolution endpoints"},
            {"prefix": "/api/types", "description": "Type inference endpoints"},
            {"prefix": "/api/hierarchy", "description": "Class hierarchy endpoints"},
            {"prefix": "/api/distributed", "description": "Distributed analysis endpoints"},
            {"prefix": "/api/microservices", "description": "Microservice analysis endpoints"},
            {"prefix": "/api/monorepo", "description": "Monorepo analysis endpoints"},
            {"prefix": "/api/lsp", "description": "Language Server Protocol endpoints"},
            {"prefix": "/api/ml", "description": "ML vulnerability detection endpoints"},
            {"prefix": "/api/llm", "description": "LLM security analysis endpoints"},
            {"prefix": "/api/dataflow", "description": "Advanced data-flow analysis endpoints"},
            {"prefix": "/api/semantic", "description": "Semantic analysis endpoints"},
        ]
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
