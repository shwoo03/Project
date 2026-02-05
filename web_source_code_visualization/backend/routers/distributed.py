"""
Distributed Router - Distributed analysis and Celery endpoints
"""
import os
import asyncio
from typing import List, Optional
from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect
from pydantic import BaseModel

router = APIRouter(prefix="/api/distributed", tags=["distributed"])


class DistributedAnalysisRequest(BaseModel):
    project_path: str
    priority: str = "normal"
    max_workers: int = 4


class TaskStatusRequest(BaseModel):
    task_id: str


class LargeScaleAnalysisRequest(BaseModel):
    project_path: str
    max_files: int = 50000
    partitioning_strategy: str = "balanced"
    include_taint: bool = True
    cache_enabled: bool = True
    worker_count: Optional[int] = None


class CacheOperationRequest(BaseModel):
    operation: str
    project_id: Optional[str] = None
    file_paths: Optional[List[str]] = None


class ClusterInfoRequest(BaseModel):
    include_workers: bool = True
    include_stats: bool = True


@router.post("/analyze")
def start_distributed_analysis(request: DistributedAnalysisRequest):
    """
    Start a distributed analysis task using Celery.
    """
    if not os.path.exists(request.project_path):
        raise HTTPException(status_code=404, detail="Path not found")
    
    try:
        from core.celery_tasks import analyze_project_task
        
        task = analyze_project_task.delay(
            project_path=request.project_path,
            priority=request.priority,
            max_workers=request.max_workers
        )
        
        return {
            "success": True,
            "task_id": task.id,
            "status": "PENDING"
        }
    except ImportError:
        raise HTTPException(
            status_code=503,
            detail="Celery not configured. Install redis and celery."
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/status")
def get_task_status(request: TaskStatusRequest):
    """
    Get the status of a distributed analysis task.
    """
    try:
        from core.celery_tasks import celery_app
        
        result = celery_app.AsyncResult(request.task_id)
        
        response = {
            "success": True,
            "task_id": request.task_id,
            "status": result.status
        }
        
        if result.ready():
            if result.successful():
                response["result"] = result.result
            else:
                response["error"] = str(result.result)
        
        return response
    except ImportError:
        raise HTTPException(status_code=503, detail="Celery not configured")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/large-scale-analyze")
def large_scale_distributed_analysis(request: LargeScaleAnalysisRequest):
    """
    Analyze a large-scale project using distributed processing.
    """
    if not os.path.exists(request.project_path):
        raise HTTPException(status_code=404, detail="Project path not found")
    
    try:
        from core.distributed_analyzer import create_distributed_analyzer
        
        analyzer = create_distributed_analyzer(
            worker_count=request.worker_count,
            partition_size=100
        )
        
        result = analyzer.analyze_project(
            project_path=request.project_path,
            max_files=request.max_files,
            partitioning_strategy=request.partitioning_strategy,
            include_taint=request.include_taint
        )
        
        return {
            "success": True,
            "session_id": result.session_id,
            "total_files": result.total_files,
            "files_analyzed": result.files_analyzed,
            "duration_ms": result.duration_ms,
            "statistics": result.statistics
        }
    except ImportError as e:
        raise HTTPException(status_code=503, detail=f"Dependencies not installed: {e}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/cache")
def distributed_cache_operations(request: CacheOperationRequest):
    """
    Perform operations on the distributed Redis cache.
    """
    try:
        from core.distributed_analyzer import RedisCache, REDIS_AVAILABLE
        
        if not REDIS_AVAILABLE:
            raise HTTPException(status_code=503, detail="Redis not installed")
        
        cache = RedisCache()
        if not cache.connect_sync():
            raise HTTPException(status_code=503, detail="Redis connection failed")
        
        if request.operation == "stats":
            loop = asyncio.new_event_loop()
            try:
                stats = loop.run_until_complete(cache.get_stats())
            finally:
                loop.close()
            return {"success": True, "operation": "stats", "stats": stats}
        
        elif request.operation == "invalidate":
            if not request.project_id:
                raise HTTPException(status_code=400, detail="project_id required")
            
            loop = asyncio.new_event_loop()
            try:
                count = loop.run_until_complete(cache.invalidate_project(request.project_id))
            finally:
                loop.close()
            return {"success": True, "operation": "invalidate", "keys_deleted": count}
        
        else:
            raise HTTPException(status_code=400, detail=f"Unknown operation: {request.operation}")
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/cache/stats")
def get_distributed_cache_stats():
    """Get Redis cache statistics."""
    try:
        from core.distributed_analyzer import get_cache_stats
        stats = get_cache_stats()
        return {"success": True, "stats": stats}
    except Exception as e:
        return {"success": False, "error": str(e)}


@router.post("/cluster")
def get_cluster_info(request: ClusterInfoRequest):
    """Get distributed cluster information."""
    try:
        from core.distributed_analyzer import ClusterOrchestrator
        
        orchestrator = ClusterOrchestrator()
        response = {"success": True, "cluster_available": True}
        
        if request.include_stats:
            response["stats"] = orchestrator.get_cluster_stats()
        
        if request.include_workers:
            response["workers"] = [
                {
                    "id": w.worker_id,
                    "hostname": w.hostname,
                    "status": w.status.value,
                    "active_tasks": w.active_tasks,
                    "is_healthy": w.is_healthy
                }
                for w in orchestrator.get_healthy_workers()
            ]
        
        return response
    except Exception as e:
        return {"success": False, "cluster_available": False, "error": str(e)}


@router.get("/partitioning/preview")
def preview_file_partitioning(
    project_path: str,
    strategy: str = "balanced",
    partition_size: int = 100,
    max_files: int = 10000
):
    """Preview file partitioning for distributed analysis."""
    if not os.path.exists(project_path):
        raise HTTPException(status_code=404, detail="Path not found")
    
    try:
        from core.distributed_analyzer import DistributedAnalyzer, WorkloadBalancer
        
        analyzer = DistributedAnalyzer(partition_size=partition_size)
        files = analyzer.discover_files(project_path, max_files)
        
        balancer = WorkloadBalancer(target_partition_size=partition_size)
        partitions = balancer.partition_files(files, strategy)
        
        return {
            "success": True,
            "total_files": len(files),
            "partition_count": len(partitions),
            "partitions": [
                {
                    "id": p.partition_id,
                    "file_count": len(p.files),
                    "total_size_bytes": p.total_size_bytes
                }
                for p in partitions
            ]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# WebSocket for progress updates
@router.websocket("/ws/progress")
async def websocket_progress(websocket: WebSocket):
    """WebSocket endpoint for real-time progress updates."""
    await websocket.accept()
    
    try:
        while True:
            data = await websocket.receive_json()
            task_id = data.get("task_id")
            
            if task_id:
                try:
                    from core.celery_tasks import celery_app
                    result = celery_app.AsyncResult(task_id)
                    await websocket.send_json({
                        "task_id": task_id,
                        "status": result.status,
                        "ready": result.ready()
                    })
                except Exception as e:
                    await websocket.send_json({"error": str(e)})
            
            await asyncio.sleep(0.5)
    
    except WebSocketDisconnect:
        pass
