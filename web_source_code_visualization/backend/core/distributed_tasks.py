"""
Distributed Analysis Tasks

Celery tasks for distributed code analysis.
Supports file-level parallelism, priority queuing, and progress tracking.
"""

from celery import shared_task, current_task, group, chain, chord
from celery.exceptions import SoftTimeLimitExceeded
from typing import Dict, List, Optional, Any
import os
import hashlib
import json
import time
from datetime import datetime
from dataclasses import dataclass, asdict
from enum import Enum

# Import analysis modules (lazy import to avoid circular dependencies)
def get_parser_manager():
    from core.parser.manager import ParserManager
    return ParserManager()

def get_taint_analyzer():
    from core.taint_analyzer import TaintAnalyzer
    return TaintAnalyzer()

def get_type_inferencer():
    from core.type_inferencer import TypeInferencer
    return TypeInferencer()

def get_class_hierarchy_analyzer():
    from core.class_hierarchy import ClassHierarchyAnalyzer
    return ClassHierarchyAnalyzer()

def get_import_resolver():
    from core.import_resolver import ImportResolver
    return ImportResolver()

def get_interprocedural_analyzer():
    from core.interprocedural_taint import InterProceduralTaintAnalyzer
    return InterProceduralTaintAnalyzer()


class AnalysisType(str, Enum):
    FULL = "full"
    PARSE_ONLY = "parse_only"
    TAINT = "taint"
    TYPE_INFERENCE = "type_inference"
    HIERARCHY = "hierarchy"
    IMPORTS = "imports"


@dataclass
class ProgressUpdate:
    """Progress update for task tracking."""
    task_id: str
    phase: str
    current: int
    total: int
    percentage: float
    message: str
    timestamp: str
    details: Optional[Dict] = None


@dataclass
class AnalysisResult:
    """Result from an analysis task."""
    task_id: str
    status: str
    analysis_type: str
    duration_ms: float
    files_analyzed: int
    results: Dict
    errors: List[str]
    timestamp: str


def update_progress(phase: str, current: int, total: int, message: str, details: dict = None):
    """Update task progress state."""
    if current_task:
        percentage = (current / total * 100) if total > 0 else 0
        current_task.update_state(
            state='PROGRESS',
            meta={
                'phase': phase,
                'current': current,
                'total': total,
                'percentage': round(percentage, 1),
                'message': message,
                'timestamp': datetime.utcnow().isoformat(),
                'details': details or {}
            }
        )


def get_file_hash(file_path: str) -> str:
    """Calculate SHA256 hash of a file."""
    try:
        with open(file_path, 'rb') as f:
            return hashlib.sha256(f.read()).hexdigest()
    except Exception:
        return ""


# =============================================================================
# File-Level Analysis Tasks
# =============================================================================

@shared_task(bind=True, name='core.distributed_tasks.analyze_file_task')
def analyze_file_task(self, file_path: str, project_root: str, analysis_type: str = "full") -> Dict:
    """
    Analyze a single file.
    
    Args:
        file_path: Absolute path to the file
        project_root: Root directory of the project
        analysis_type: Type of analysis to perform
        
    Returns:
        Analysis results for the file
    """
    start_time = time.time()
    errors = []
    result = {}
    
    try:
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"File not found: {file_path}")
        
        # Get file info
        file_hash = get_file_hash(file_path)
        relative_path = os.path.relpath(file_path, project_root)
        
        update_progress('parsing', 0, 1, f'Parsing {relative_path}')
        
        # Parse file
        parser_manager = get_parser_manager()
        
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
        
        parse_result = parser_manager.parse_file(file_path, content)
        
        result = {
            'file_path': file_path,
            'relative_path': relative_path,
            'file_hash': file_hash,
            'endpoints': [asdict(e) if hasattr(e, '__dict__') else e for e in parse_result.get('endpoints', [])],
            'functions': parse_result.get('functions', []),
            'classes': parse_result.get('classes', []),
            'imports': parse_result.get('imports', []),
            'taint_flows': [],
        }
        
        # Additional analysis based on type
        if analysis_type in ['full', 'taint']:
            update_progress('taint', 0, 1, f'Taint analysis: {relative_path}')
            taint_analyzer = get_taint_analyzer()
            taint_result = taint_analyzer.analyze_code(content, file_path)
            result['taint_flows'] = taint_result.get('flows', [])
        
        update_progress('complete', 1, 1, f'Completed: {relative_path}')
        
    except SoftTimeLimitExceeded:
        errors.append(f"Analysis timeout for {file_path}")
    except Exception as e:
        errors.append(f"Error analyzing {file_path}: {str(e)}")
    
    duration_ms = (time.time() - start_time) * 1000
    
    return {
        'task_id': self.request.id,
        'status': 'success' if not errors else 'error',
        'result': result,
        'errors': errors,
        'duration_ms': round(duration_ms, 2),
        'timestamp': datetime.utcnow().isoformat()
    }


# =============================================================================
# Project-Level Analysis Tasks
# =============================================================================

@shared_task(bind=True, name='core.distributed_tasks.analyze_project_task')
def analyze_project_task(
    self,
    project_path: str,
    analysis_type: str = "full",
    max_files: int = 10000,
    excluded_dirs: List[str] = None
) -> Dict:
    """
    Analyze an entire project using distributed workers.
    
    Args:
        project_path: Root directory of the project
        analysis_type: Type of analysis to perform
        max_files: Maximum number of files to analyze
        excluded_dirs: Directories to exclude
        
    Returns:
        Aggregated analysis results
    """
    start_time = time.time()
    errors = []
    
    if excluded_dirs is None:
        excluded_dirs = ['node_modules', '__pycache__', '.git', 'venv', 'env', 'dist', 'build']
    
    # Supported file extensions
    extensions = {'.py', '.js', '.ts', '.tsx', '.jsx', '.php', '.java', '.go'}
    
    try:
        # Phase 1: Discover files
        update_progress('discovery', 0, 1, 'Discovering files...')
        
        files_to_analyze = []
        for root, dirs, files in os.walk(project_path):
            # Filter excluded directories
            dirs[:] = [d for d in dirs if d not in excluded_dirs]
            
            for file in files:
                ext = os.path.splitext(file)[1].lower()
                if ext in extensions:
                    file_path = os.path.join(root, file)
                    files_to_analyze.append(file_path)
                    
                    if len(files_to_analyze) >= max_files:
                        break
            
            if len(files_to_analyze) >= max_files:
                break
        
        total_files = len(files_to_analyze)
        update_progress('discovery', 1, 1, f'Found {total_files} files')
        
        if total_files == 0:
            return {
                'task_id': self.request.id,
                'status': 'success',
                'message': 'No files to analyze',
                'results': {},
                'duration_ms': 0,
                'timestamp': datetime.utcnow().isoformat()
            }
        
        # Phase 2: Create subtasks for each file
        update_progress('queuing', 0, total_files, 'Creating analysis tasks...')
        
        # Create a group of tasks for parallel execution
        file_tasks = group([
            analyze_file_task.s(file_path, project_path, analysis_type)
            for file_path in files_to_analyze
        ])
        
        # Execute tasks and wait for results
        update_progress('analyzing', 0, total_files, 'Analyzing files...')
        
        # For synchronous execution within a task, we can use apply_async with a callback
        # or iterate through results as they complete
        async_result = file_tasks.apply_async()
        
        # Collect results
        all_results = []
        completed = 0
        
        for result in async_result.iterate():
            completed += 1
            all_results.append(result)
            
            if completed % 10 == 0 or completed == total_files:
                update_progress('analyzing', completed, total_files, 
                              f'Analyzed {completed}/{total_files} files')
        
        # Phase 3: Aggregate results
        update_progress('aggregating', 0, 1, 'Aggregating results...')
        
        aggregated = {
            'endpoints': [],
            'functions': [],
            'classes': [],
            'imports': [],
            'taint_flows': [],
            'file_results': {},
        }
        
        for file_result in all_results:
            if file_result.get('status') == 'success':
                result = file_result.get('result', {})
                rel_path = result.get('relative_path', '')
                
                aggregated['endpoints'].extend(result.get('endpoints', []))
                aggregated['functions'].extend(result.get('functions', []))
                aggregated['classes'].extend(result.get('classes', []))
                aggregated['imports'].extend(result.get('imports', []))
                aggregated['taint_flows'].extend(result.get('taint_flows', []))
                aggregated['file_results'][rel_path] = result
            else:
                errors.extend(file_result.get('errors', []))
        
        update_progress('complete', 1, 1, 'Analysis complete')
        
        duration_ms = (time.time() - start_time) * 1000
        
        return {
            'task_id': self.request.id,
            'status': 'success' if not errors else 'partial',
            'project_path': project_path,
            'files_analyzed': total_files,
            'files_succeeded': len([r for r in all_results if r.get('status') == 'success']),
            'files_failed': len([r for r in all_results if r.get('status') != 'success']),
            'results': aggregated,
            'stats': {
                'total_endpoints': len(aggregated['endpoints']),
                'total_functions': len(aggregated['functions']),
                'total_classes': len(aggregated['classes']),
                'total_taint_flows': len(aggregated['taint_flows']),
            },
            'errors': errors[:100],  # Limit error count
            'duration_ms': round(duration_ms, 2),
            'timestamp': datetime.utcnow().isoformat()
        }
        
    except SoftTimeLimitExceeded:
        return {
            'task_id': self.request.id,
            'status': 'timeout',
            'message': 'Analysis exceeded time limit',
            'errors': ['Task timeout'],
            'duration_ms': (time.time() - start_time) * 1000,
            'timestamp': datetime.utcnow().isoformat()
        }
    except Exception as e:
        return {
            'task_id': self.request.id,
            'status': 'error',
            'message': str(e),
            'errors': [str(e)],
            'duration_ms': (time.time() - start_time) * 1000,
            'timestamp': datetime.utcnow().isoformat()
        }


# =============================================================================
# Specialized Analysis Tasks
# =============================================================================

@shared_task(bind=True, name='core.distributed_tasks.taint_analysis_task')
def taint_analysis_task(
    self,
    project_path: str,
    max_depth: int = 10,
    include_interprocedural: bool = True
) -> Dict:
    """
    Perform comprehensive taint analysis on a project.
    """
    start_time = time.time()
    
    try:
        update_progress('initializing', 0, 1, 'Initializing taint analysis...')
        
        if include_interprocedural:
            analyzer = get_interprocedural_analyzer()
            result = analyzer.analyze_project(project_path, max_depth=max_depth)
        else:
            analyzer = get_taint_analyzer()
            result = analyzer.analyze_project(project_path)
        
        update_progress('complete', 1, 1, 'Taint analysis complete')
        
        return {
            'task_id': self.request.id,
            'status': 'success',
            'analysis_type': 'taint',
            'results': result,
            'duration_ms': round((time.time() - start_time) * 1000, 2),
            'timestamp': datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        return {
            'task_id': self.request.id,
            'status': 'error',
            'analysis_type': 'taint',
            'error': str(e),
            'duration_ms': round((time.time() - start_time) * 1000, 2),
            'timestamp': datetime.utcnow().isoformat()
        }


@shared_task(bind=True, name='core.distributed_tasks.type_inference_task')
def type_inference_task(self, project_path: str) -> Dict:
    """
    Perform type inference analysis on a project.
    """
    start_time = time.time()
    
    try:
        update_progress('initializing', 0, 1, 'Initializing type inference...')
        
        inferencer = get_type_inferencer()
        result = inferencer.analyze_project(project_path)
        
        update_progress('complete', 1, 1, 'Type inference complete')
        
        return {
            'task_id': self.request.id,
            'status': 'success',
            'analysis_type': 'type_inference',
            'results': result,
            'duration_ms': round((time.time() - start_time) * 1000, 2),
            'timestamp': datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        return {
            'task_id': self.request.id,
            'status': 'error',
            'analysis_type': 'type_inference',
            'error': str(e),
            'duration_ms': round((time.time() - start_time) * 1000, 2),
            'timestamp': datetime.utcnow().isoformat()
        }


@shared_task(bind=True, name='core.distributed_tasks.hierarchy_analysis_task')
def hierarchy_analysis_task(self, project_path: str) -> Dict:
    """
    Perform class hierarchy analysis on a project.
    """
    start_time = time.time()
    
    try:
        update_progress('initializing', 0, 1, 'Initializing hierarchy analysis...')
        
        analyzer = get_class_hierarchy_analyzer()
        result = analyzer.analyze_project(project_path)
        
        update_progress('complete', 1, 1, 'Hierarchy analysis complete')
        
        return {
            'task_id': self.request.id,
            'status': 'success',
            'analysis_type': 'hierarchy',
            'results': result,
            'duration_ms': round((time.time() - start_time) * 1000, 2),
            'timestamp': datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        return {
            'task_id': self.request.id,
            'status': 'error',
            'analysis_type': 'hierarchy',
            'error': str(e),
            'duration_ms': round((time.time() - start_time) * 1000, 2),
            'timestamp': datetime.utcnow().isoformat()
        }


@shared_task(bind=True, name='core.distributed_tasks.import_resolution_task')
def import_resolution_task(self, project_path: str) -> Dict:
    """
    Perform import resolution analysis on a project.
    """
    start_time = time.time()
    
    try:
        update_progress('initializing', 0, 1, 'Initializing import resolution...')
        
        resolver = get_import_resolver()
        result = resolver.resolve_project(project_path)
        
        update_progress('complete', 1, 1, 'Import resolution complete')
        
        return {
            'task_id': self.request.id,
            'status': 'success',
            'analysis_type': 'imports',
            'results': result,
            'duration_ms': round((time.time() - start_time) * 1000, 2),
            'timestamp': datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        return {
            'task_id': self.request.id,
            'status': 'error',
            'analysis_type': 'imports',
            'error': str(e),
            'duration_ms': round((time.time() - start_time) * 1000, 2),
            'timestamp': datetime.utcnow().isoformat()
        }


# =============================================================================
# Workflow Tasks (Chained Analysis)
# =============================================================================

@shared_task(bind=True, name='core.distributed_tasks.full_analysis_workflow')
def full_analysis_workflow(
    self,
    project_path: str,
    include_taint: bool = True,
    include_types: bool = True,
    include_hierarchy: bool = True,
    include_imports: bool = True
) -> Dict:
    """
    Execute a complete analysis workflow with all components.
    Uses Celery chains and chords for optimal parallelism.
    """
    start_time = time.time()
    
    try:
        update_progress('planning', 0, 1, 'Planning analysis workflow...')
        
        # Build the workflow
        parallel_tasks = []
        
        if include_taint:
            parallel_tasks.append(taint_analysis_task.s(project_path))
        if include_types:
            parallel_tasks.append(type_inference_task.s(project_path))
        if include_hierarchy:
            parallel_tasks.append(hierarchy_analysis_task.s(project_path))
        if include_imports:
            parallel_tasks.append(import_resolution_task.s(project_path))
        
        if not parallel_tasks:
            return {
                'task_id': self.request.id,
                'status': 'success',
                'message': 'No analysis types selected',
                'results': {},
                'duration_ms': 0,
                'timestamp': datetime.utcnow().isoformat()
            }
        
        update_progress('executing', 0, len(parallel_tasks), 'Executing analysis tasks...')
        
        # Execute all tasks in parallel
        workflow = group(parallel_tasks)
        async_result = workflow.apply_async()
        
        # Collect results
        results = {}
        completed = 0
        
        for result in async_result.iterate():
            completed += 1
            analysis_type = result.get('analysis_type', 'unknown')
            results[analysis_type] = result
            
            update_progress('executing', completed, len(parallel_tasks), 
                          f'Completed {analysis_type} analysis')
        
        update_progress('complete', 1, 1, 'Full analysis workflow complete')
        
        return {
            'task_id': self.request.id,
            'status': 'success',
            'project_path': project_path,
            'results': results,
            'analyses_completed': len(results),
            'duration_ms': round((time.time() - start_time) * 1000, 2),
            'timestamp': datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        return {
            'task_id': self.request.id,
            'status': 'error',
            'error': str(e),
            'duration_ms': round((time.time() - start_time) * 1000, 2),
            'timestamp': datetime.utcnow().isoformat()
        }


# =============================================================================
# Utility Tasks
# =============================================================================

@shared_task(name='core.distributed_tasks.cleanup_expired_results')
def cleanup_expired_results():
    """Periodic task to clean up expired analysis results."""
    from core.celery_config import celery_app
    
    try:
        # Get Redis client
        import redis
        from core.celery_config import REDIS_HOST, REDIS_PORT, REDIS_DB, REDIS_PASSWORD
        
        r = redis.Redis(
            host=REDIS_HOST,
            port=int(REDIS_PORT),
            db=int(REDIS_DB),
            password=REDIS_PASSWORD
        )
        
        # Clean up old task metadata
        # Celery handles result expiration automatically based on result_expires
        # This task can be extended for custom cleanup logic
        
        return {'status': 'success', 'message': 'Cleanup completed'}
        
    except Exception as e:
        return {'status': 'error', 'message': str(e)}


@shared_task(name='core.distributed_tasks.update_worker_stats')
def update_worker_stats():
    """Periodic task to update worker statistics."""
    from core.celery_config import get_worker_stats, get_queue_stats
    
    try:
        worker_stats = get_worker_stats()
        queue_stats = get_queue_stats()
        
        return {
            'status': 'success',
            'workers': worker_stats,
            'queues': queue_stats,
            'timestamp': datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        return {'status': 'error', 'message': str(e)}


@shared_task(name='core.distributed_tasks.cancel_analysis')
def cancel_analysis(task_id: str) -> Dict:
    """Cancel a running analysis task."""
    from core.celery_config import celery_app
    
    try:
        celery_app.control.revoke(task_id, terminate=True)
        return {
            'status': 'success',
            'message': f'Task {task_id} cancelled',
            'task_id': task_id
        }
    except Exception as e:
        return {
            'status': 'error',
            'message': str(e),
            'task_id': task_id
        }


# =============================================================================
# Task Result Helpers
# =============================================================================

def get_task_status(task_id: str) -> Dict:
    """Get the status of a task by ID."""
    from celery.result import AsyncResult
    from core.celery_config import celery_app
    
    result = AsyncResult(task_id, app=celery_app)
    
    response = {
        'task_id': task_id,
        'status': result.status,
        'ready': result.ready(),
        'successful': result.successful() if result.ready() else None,
    }
    
    if result.status == 'PROGRESS':
        response['progress'] = result.info
    elif result.ready():
        if result.successful():
            response['result'] = result.result
        else:
            response['error'] = str(result.result)
    
    return response


def get_task_result(task_id: str, timeout: float = None) -> Dict:
    """Get the result of a completed task."""
    from celery.result import AsyncResult
    from core.celery_config import celery_app
    
    result = AsyncResult(task_id, app=celery_app)
    
    if timeout:
        try:
            return result.get(timeout=timeout)
        except Exception as e:
            return {'error': str(e), 'task_id': task_id}
    
    if result.ready():
        if result.successful():
            return result.result
        else:
            return {'error': str(result.result), 'task_id': task_id}
    
    return {'status': 'pending', 'task_id': task_id}
