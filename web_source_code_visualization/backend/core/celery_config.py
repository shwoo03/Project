"""
Celery Configuration for Distributed Analysis

This module configures Celery for distributed code analysis tasks.
Supports Redis as message broker and result backend.
"""

from celery import Celery
from kombu import Queue, Exchange
import os

# Redis configuration
REDIS_HOST = os.getenv('REDIS_HOST', 'localhost')
REDIS_PORT = os.getenv('REDIS_PORT', '6379')
REDIS_DB = os.getenv('REDIS_DB', '0')
REDIS_PASSWORD = os.getenv('REDIS_PASSWORD', None)

# Build Redis URL
if REDIS_PASSWORD:
    REDIS_URL = f"redis://:{REDIS_PASSWORD}@{REDIS_HOST}:{REDIS_PORT}/{REDIS_DB}"
else:
    REDIS_URL = f"redis://{REDIS_HOST}:{REDIS_PORT}/{REDIS_DB}"

# Celery app configuration
celery_app = Celery(
    'code_analyzer',
    broker=REDIS_URL,
    backend=REDIS_URL,
    include=['core.distributed_tasks']
)

# Task queues with priorities
default_exchange = Exchange('default', type='direct')
priority_exchange = Exchange('priority', type='direct')

celery_app.conf.task_queues = (
    Queue('default', default_exchange, routing_key='default'),
    Queue('high_priority', priority_exchange, routing_key='high'),
    Queue('low_priority', priority_exchange, routing_key='low'),
    Queue('analysis', default_exchange, routing_key='analysis'),
    Queue('taint', default_exchange, routing_key='taint'),
    Queue('hierarchy', default_exchange, routing_key='hierarchy'),
)

# Task routing
celery_app.conf.task_routes = {
    'core.distributed_tasks.analyze_file_task': {'queue': 'analysis'},
    'core.distributed_tasks.analyze_project_task': {'queue': 'analysis'},
    'core.distributed_tasks.taint_analysis_task': {'queue': 'taint'},
    'core.distributed_tasks.type_inference_task': {'queue': 'analysis'},
    'core.distributed_tasks.hierarchy_analysis_task': {'queue': 'hierarchy'},
    'core.distributed_tasks.import_resolution_task': {'queue': 'analysis'},
}

# Celery configuration
celery_app.conf.update(
    # Task execution settings
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='UTC',
    enable_utc=True,
    
    # Task result settings
    result_expires=3600,  # Results expire after 1 hour
    result_extended=True,  # Include task name and args in result
    
    # Worker settings
    worker_prefetch_multiplier=4,
    worker_concurrency=None,  # Use CPU count
    worker_max_tasks_per_child=1000,  # Restart worker after 1000 tasks
    
    # Task settings
    task_acks_late=True,  # Acknowledge after task completes
    task_reject_on_worker_lost=True,  # Requeue if worker dies
    task_time_limit=600,  # 10 minute hard limit
    task_soft_time_limit=540,  # 9 minute soft limit
    
    # Rate limiting
    task_default_rate_limit='100/m',  # 100 tasks per minute default
    
    # Error handling
    task_annotations={
        '*': {
            'max_retries': 3,
            'retry_backoff': True,
            'retry_backoff_max': 600,
            'retry_jitter': True,
        }
    },
    
    # Beat scheduler (for periodic tasks)
    beat_schedule={
        'cleanup-expired-results': {
            'task': 'core.distributed_tasks.cleanup_expired_results',
            'schedule': 3600.0,  # Every hour
        },
        'update-worker-stats': {
            'task': 'core.distributed_tasks.update_worker_stats',
            'schedule': 60.0,  # Every minute
        },
    },
)

# Priority levels
class TaskPriority:
    HIGH = 9
    NORMAL = 5
    LOW = 1

# Task states
class TaskState:
    PENDING = 'PENDING'
    STARTED = 'STARTED'
    PROGRESS = 'PROGRESS'
    SUCCESS = 'SUCCESS'
    FAILURE = 'FAILURE'
    REVOKED = 'REVOKED'
    RETRY = 'RETRY'


def get_celery_app() -> Celery:
    """Get the configured Celery application."""
    return celery_app


def check_redis_connection() -> bool:
    """Check if Redis is available."""
    try:
        import redis
        r = redis.Redis(
            host=REDIS_HOST,
            port=int(REDIS_PORT),
            db=int(REDIS_DB),
            password=REDIS_PASSWORD,
            socket_timeout=5
        )
        r.ping()
        return True
    except Exception:
        return False


def get_worker_stats() -> dict:
    """Get statistics about active workers."""
    try:
        inspect = celery_app.control.inspect()
        
        # Get active workers
        active = inspect.active() or {}
        reserved = inspect.reserved() or {}
        stats = inspect.stats() or {}
        
        worker_info = {}
        for worker_name, worker_stats in stats.items():
            worker_info[worker_name] = {
                'active_tasks': len(active.get(worker_name, [])),
                'reserved_tasks': len(reserved.get(worker_name, [])),
                'pool_size': worker_stats.get('pool', {}).get('max-concurrency', 0),
                'total_tasks': worker_stats.get('total', {}),
                'broker': worker_stats.get('broker', {}),
            }
        
        return {
            'workers': worker_info,
            'total_workers': len(worker_info),
            'total_active_tasks': sum(w['active_tasks'] for w in worker_info.values()),
        }
    except Exception as e:
        return {'error': str(e), 'workers': {}, 'total_workers': 0}


def get_queue_stats() -> dict:
    """Get statistics about task queues."""
    try:
        import redis
        r = redis.Redis(
            host=REDIS_HOST,
            port=int(REDIS_PORT),
            db=int(REDIS_DB),
            password=REDIS_PASSWORD
        )
        
        queues = ['default', 'high_priority', 'low_priority', 'analysis', 'taint', 'hierarchy']
        queue_lengths = {}
        
        for queue in queues:
            try:
                length = r.llen(queue)
                queue_lengths[queue] = length
            except Exception:
                queue_lengths[queue] = 0
        
        return {
            'queues': queue_lengths,
            'total_pending': sum(queue_lengths.values()),
        }
    except Exception as e:
        return {'error': str(e), 'queues': {}, 'total_pending': 0}
