"""
Burp Suite MCP Web Interface - FastAPI Application
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from contextlib import asynccontextmanager

from core.config import settings
from core.mcp_client import mcp_manager
from routers import proxy, repeater, intruder, scanner, collaborator, websocket


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan events"""
    # Startup
    print("🚀 Starting Burp Suite Web Interface...")
    await mcp_manager.connect()
    yield
    # Shutdown
    print("🔒 Shutting down...")
    await mcp_manager.disconnect()


app = FastAPI(
    title="Burp Suite Web Interface",
    description="Web interface for Burp Suite via MCP",
    version="1.0.0",
    lifespan=lifespan
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(proxy.router, prefix="/api/proxy", tags=["Proxy"])
app.include_router(repeater.router, prefix="/api/repeater", tags=["Repeater"])
app.include_router(intruder.router, prefix="/api/intruder", tags=["Intruder"])
app.include_router(scanner.router, prefix="/api/scanner", tags=["Scanner"])
app.include_router(collaborator.router, prefix="/api/collaborator", tags=["Collaborator"])
app.include_router(websocket.router, tags=["WebSocket"])


@app.get("/")
async def root():
    return {"message": "Burp Suite Web Interface API", "status": "running"}


@app.get("/api/health")
async def health_check():
    """Health check endpoint"""
    mcp_status = await mcp_manager.check_connection()
    return {
        "status": "healthy",
        "mcp_connected": mcp_status,
        "version": "1.0.0"
    }


@app.get("/api/mcp/tools")
async def list_mcp_tools():
    """List available MCP tools from Burp Suite"""
    tools = await mcp_manager.list_tools()
    return {"tools": tools}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG
    )
