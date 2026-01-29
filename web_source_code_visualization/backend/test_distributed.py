"""
Test Suite for Distributed Analysis Architecture

Tests for:
- Celery configuration
- Distributed tasks
- WebSocket progress reporting
- Task status tracking
"""

import os
import sys
import time
import json
from datetime import datetime
from unittest.mock import Mock, patch, MagicMock

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def test_celery_config():
    """Test Celery configuration module."""
    print("\n" + "="*60)
    print("Test 1: Celery Configuration")
    print("="*60)
    
    from core.celery_config import (
        celery_app,
        TaskPriority,
        TaskState,
        REDIS_HOST,
        REDIS_PORT,
        REDIS_URL
    )
    
    # Test celery app exists
    assert celery_app is not None
    print(f"✓ Celery app created: {celery_app.main}")
    
    # Test configuration
    assert celery_app.conf.task_serializer == 'json'
    print(f"✓ Task serializer: {celery_app.conf.task_serializer}")
    
    assert celery_app.conf.result_expires == 3600
    print(f"✓ Result expiration: {celery_app.conf.result_expires}s")
    
    # Test task queues
    queue_names = [q.name for q in celery_app.conf.task_queues]
    expected_queues = ['default', 'high_priority', 'low_priority', 'analysis', 'taint', 'hierarchy']
    for q in expected_queues:
        assert q in queue_names, f"Queue {q} not found"
    print(f"✓ Task queues configured: {queue_names}")
    
    # Test priority levels
    assert TaskPriority.HIGH == 9
    assert TaskPriority.NORMAL == 5
    assert TaskPriority.LOW == 1
    print(f"✓ Priority levels: HIGH={TaskPriority.HIGH}, NORMAL={TaskPriority.NORMAL}, LOW={TaskPriority.LOW}")
    
    # Test task states
    assert TaskState.PENDING == 'PENDING'
    assert TaskState.PROGRESS == 'PROGRESS'
    assert TaskState.SUCCESS == 'SUCCESS'
    print(f"✓ Task states defined")
    
    # Test Redis URL
    print(f"✓ Redis URL: {REDIS_URL}")
    
    print("\n✅ Celery configuration test passed!")
    return True


def test_distributed_tasks_module():
    """Test distributed tasks module structure."""
    print("\n" + "="*60)
    print("Test 2: Distributed Tasks Module")
    print("="*60)
    
    from core.distributed_tasks import (
        AnalysisType,
        ProgressUpdate,
        AnalysisResult,
        analyze_file_task,
        analyze_project_task,
        taint_analysis_task,
        type_inference_task,
        hierarchy_analysis_task,
        import_resolution_task,
        full_analysis_workflow,
        get_task_status,
        get_task_result
    )
    
    # Test AnalysisType enum
    assert AnalysisType.FULL == "full"
    assert AnalysisType.TAINT == "taint"
    assert AnalysisType.TYPE_INFERENCE == "type_inference"
    print(f"✓ AnalysisType enum: {[t.value for t in AnalysisType]}")
    
    # Test ProgressUpdate dataclass
    progress = ProgressUpdate(
        task_id="test-123",
        phase="parsing",
        current=5,
        total=10,
        percentage=50.0,
        message="Parsing files...",
        timestamp=datetime.utcnow().isoformat()
    )
    assert progress.task_id == "test-123"
    assert progress.percentage == 50.0
    print(f"✓ ProgressUpdate dataclass works")
    
    # Test AnalysisResult dataclass
    result = AnalysisResult(
        task_id="test-123",
        status="success",
        analysis_type="full",
        duration_ms=1234.56,
        files_analyzed=10,
        results={},
        errors=[],
        timestamp=datetime.utcnow().isoformat()
    )
    assert result.status == "success"
    print(f"✓ AnalysisResult dataclass works")
    
    # Test task functions exist
    assert callable(analyze_file_task)
    assert callable(analyze_project_task)
    assert callable(taint_analysis_task)
    assert callable(type_inference_task)
    assert callable(hierarchy_analysis_task)
    assert callable(import_resolution_task)
    assert callable(full_analysis_workflow)
    print(f"✓ All task functions are defined")
    
    # Test helper functions
    assert callable(get_task_status)
    assert callable(get_task_result)
    print(f"✓ Helper functions are defined")
    
    print("\n✅ Distributed tasks module test passed!")
    return True


def test_websocket_progress_module():
    """Test WebSocket progress reporting module."""
    print("\n" + "="*60)
    print("Test 3: WebSocket Progress Module")
    print("="*60)
    
    from core.websocket_progress import (
        MessageType,
        ProgressMessage,
        StatusMessage,
        ResultMessage,
        ConnectionManager,
        ProgressReporter,
        TaskProgressPoller,
        connection_manager,
        progress_poller
    )
    
    # Test MessageType enum
    assert MessageType.CONNECT == "connect"
    assert MessageType.PROGRESS == "progress"
    assert MessageType.RESULT == "result"
    print(f"✓ MessageType enum: {[m.value for m in MessageType]}")
    
    # Test ProgressMessage
    progress = ProgressMessage(
        task_id="test-123",
        phase="analyzing",
        current=5,
        total=10,
        percentage=50.0,
        message="Analyzing...",
        timestamp=datetime.utcnow().isoformat()
    )
    msg_dict = progress.to_dict()
    assert msg_dict['type'] == MessageType.PROGRESS
    assert msg_dict['data']['task_id'] == "test-123"
    print(f"✓ ProgressMessage serialization works")
    
    # Test StatusMessage
    status = StatusMessage(
        task_id="test-123",
        status="running",
        ready=False
    )
    msg_dict = status.to_dict()
    assert msg_dict['type'] == MessageType.STATUS
    print(f"✓ StatusMessage serialization works")
    
    # Test ResultMessage
    result = ResultMessage(
        task_id="test-123",
        status="complete",
        result={"endpoints": 10},
        duration_ms=1234.56,
        timestamp=datetime.utcnow().isoformat()
    )
    msg_dict = result.to_dict()
    assert msg_dict['type'] == MessageType.RESULT
    print(f"✓ ResultMessage serialization works")
    
    # Test ConnectionManager
    assert isinstance(connection_manager, ConnectionManager)
    stats = connection_manager.get_stats()
    assert 'active_connections' in stats
    print(f"✓ ConnectionManager instance exists")
    
    # Test ProgressReporter
    reporter = ProgressReporter("test-task-id")
    assert reporter.task_id == "test-task-id"
    print(f"✓ ProgressReporter can be instantiated")
    
    # Test TaskProgressPoller
    assert isinstance(progress_poller, TaskProgressPoller)
    print(f"✓ TaskProgressPoller instance exists")
    
    print("\n✅ WebSocket progress module test passed!")
    return True


def test_task_routing():
    """Test task routing configuration."""
    print("\n" + "="*60)
    print("Test 4: Task Routing Configuration")
    print("="*60)
    
    from core.celery_config import celery_app
    
    task_routes = celery_app.conf.task_routes
    
    # Check routing for each task type
    expected_routes = {
        'core.distributed_tasks.analyze_file_task': 'analysis',
        'core.distributed_tasks.analyze_project_task': 'analysis',
        'core.distributed_tasks.taint_analysis_task': 'taint',
        'core.distributed_tasks.type_inference_task': 'analysis',
        'core.distributed_tasks.hierarchy_analysis_task': 'hierarchy',
        'core.distributed_tasks.import_resolution_task': 'analysis',
    }
    
    for task_name, expected_queue in expected_routes.items():
        if task_name in task_routes:
            actual_queue = task_routes[task_name].get('queue')
            assert actual_queue == expected_queue, f"Task {task_name} routed to {actual_queue}, expected {expected_queue}"
            print(f"✓ {task_name.split('.')[-1]} → {actual_queue}")
    
    print("\n✅ Task routing test passed!")
    return True


def test_analysis_simulation():
    """Test analysis task logic (without actually running Celery)."""
    print("\n" + "="*60)
    print("Test 5: Analysis Task Simulation")
    print("="*60)
    
    from core.distributed_tasks import get_file_hash
    
    # Test file hash function
    test_file = os.path.abspath(__file__)
    hash1 = get_file_hash(test_file)
    hash2 = get_file_hash(test_file)
    assert hash1 == hash2
    assert len(hash1) == 64  # SHA256 produces 64 hex characters
    print(f"✓ File hash function works: {hash1[:16]}...")
    
    # Test hash for non-existent file
    no_hash = get_file_hash("/nonexistent/file.py")
    assert no_hash == ""
    print(f"✓ Non-existent file returns empty hash")
    
    # Test project root detection
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    backend_dir = os.path.join(project_root, "backend")
    
    # Count Python files in backend
    py_files = []
    for root, dirs, files in os.walk(backend_dir):
        dirs[:] = [d for d in dirs if d not in ['__pycache__', 'venv', 'node_modules']]
        for f in files:
            if f.endswith('.py'):
                py_files.append(os.path.join(root, f))
    
    print(f"✓ Found {len(py_files)} Python files in backend")
    
    print("\n✅ Analysis simulation test passed!")
    return True


def test_priority_queuing():
    """Test priority-based task queuing."""
    print("\n" + "="*60)
    print("Test 6: Priority Queuing")
    print("="*60)
    
    from core.celery_config import TaskPriority
    
    # Test priority values
    priorities = [
        ("HIGH", TaskPriority.HIGH, 9),
        ("NORMAL", TaskPriority.NORMAL, 5),
        ("LOW", TaskPriority.LOW, 1)
    ]
    
    for name, value, expected in priorities:
        assert value == expected
        print(f"✓ {name} priority = {value}")
    
    # Test priority ordering
    assert TaskPriority.HIGH > TaskPriority.NORMAL > TaskPriority.LOW
    print(f"✓ Priority ordering: HIGH > NORMAL > LOW")
    
    print("\n✅ Priority queuing test passed!")
    return True


def test_beat_schedule():
    """Test Celery beat schedule for periodic tasks."""
    print("\n" + "="*60)
    print("Test 7: Beat Schedule (Periodic Tasks)")
    print("="*60)
    
    from core.celery_config import celery_app
    
    beat_schedule = celery_app.conf.beat_schedule
    
    # Check cleanup task
    assert 'cleanup-expired-results' in beat_schedule
    cleanup_task = beat_schedule['cleanup-expired-results']
    assert cleanup_task['task'] == 'core.distributed_tasks.cleanup_expired_results'
    assert cleanup_task['schedule'] == 3600.0  # Every hour
    print(f"✓ Cleanup task: every {cleanup_task['schedule']}s")
    
    # Check stats update task
    assert 'update-worker-stats' in beat_schedule
    stats_task = beat_schedule['update-worker-stats']
    assert stats_task['task'] == 'core.distributed_tasks.update_worker_stats'
    assert stats_task['schedule'] == 60.0  # Every minute
    print(f"✓ Stats update task: every {stats_task['schedule']}s")
    
    print("\n✅ Beat schedule test passed!")
    return True


def test_main_api_endpoints():
    """Test that distributed API endpoints are registered."""
    print("\n" + "="*60)
    print("Test 8: API Endpoints Registration")
    print("="*60)
    
    from main import app
    
    # Get all routes
    routes = [route.path for route in app.routes]
    
    expected_endpoints = [
        "/api/distributed/status",
        "/api/distributed/analyze",
        "/api/distributed/workflow",
        "/api/distributed/task/status",
        "/api/distributed/task/result",
        "/api/distributed/task/cancel",
        "/api/distributed/workers",
        "/api/distributed/queues",
        "/ws/progress",
        "/api/distributed/ws/stats"
    ]
    
    for endpoint in expected_endpoints:
        assert endpoint in routes, f"Endpoint {endpoint} not found"
        print(f"✓ {endpoint}")
    
    print("\n✅ API endpoints registration test passed!")
    return True


def test_connection_manager_operations():
    """Test ConnectionManager operations."""
    print("\n" + "="*60)
    print("Test 9: ConnectionManager Operations")
    print("="*60)
    
    from core.websocket_progress import ConnectionManager
    import asyncio
    
    # Create fresh instance for testing
    cm = ConnectionManager()
    
    # Test initial state
    assert len(cm.active_connections) == 0
    assert len(cm.task_subscriptions) == 0
    print(f"✓ Initial state: empty")
    
    # Test stats
    stats = cm.get_stats()
    assert stats['active_connections'] == 0
    assert stats['total_subscriptions'] == 0
    print(f"✓ Stats: {stats}")
    
    print("\n✅ ConnectionManager operations test passed!")
    return True


def run_all_tests():
    """Run all tests."""
    print("\n" + "="*60)
    print("Distributed Analysis Architecture Test Suite")
    print("="*60)
    
    tests = [
        ("Celery Configuration", test_celery_config),
        ("Distributed Tasks Module", test_distributed_tasks_module),
        ("WebSocket Progress Module", test_websocket_progress_module),
        ("Task Routing", test_task_routing),
        ("Analysis Simulation", test_analysis_simulation),
        ("Priority Queuing", test_priority_queuing),
        ("Beat Schedule", test_beat_schedule),
        ("API Endpoints", test_main_api_endpoints),
        ("ConnectionManager", test_connection_manager_operations),
    ]
    
    passed = 0
    failed = 0
    
    for name, test_func in tests:
        try:
            test_func()
            passed += 1
        except Exception as e:
            print(f"\n❌ {name} FAILED: {e}")
            import traceback
            traceback.print_exc()
            failed += 1
    
    print("\n" + "="*60)
    print(f"Test Results: {passed} passed, {failed} failed")
    print("="*60)
    
    if failed == 0:
        print("\n🎉 All tests passed!")
    else:
        print(f"\n⚠️ {failed} test(s) failed")
    
    return failed == 0


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
