"""
Test suite for Distributed Analysis Architecture.

Tests for:
- RedisCache: Distributed caching system
- WorkloadBalancer: File partitioning and load balancing
- DistributedAnalyzer: Large-scale parallel analysis
- ClusterOrchestrator: Cluster management
"""

import os
import sys
import tempfile
import time
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.distributed_analyzer import (
    # Enums and data structures
    AnalysisPhase,
    WorkerStatus,
    FilePartition,
    WorkerInfo,
    AnalysisProgress,
    CachedResult,
    DistributedAnalysisResult,
    # Classes
    RedisCache,
    WorkloadBalancer,
    DistributedAnalyzer,
    ClusterOrchestrator,
    # Convenience functions
    create_distributed_analyzer,
    analyze_large_project,
    get_cache_stats,
)


class TestAnalysisPhase(unittest.TestCase):
    """Tests for AnalysisPhase enum."""
    
    def test_all_phases_exist(self):
        """Test that all expected phases are defined."""
        expected_phases = [
            'INITIALIZING', 'DISCOVERY', 'PARTITIONING', 'PARSING',
            'SYMBOL_RESOLUTION', 'TAINT_ANALYSIS', 'AGGREGATION',
            'FINALIZATION', 'COMPLETE', 'FAILED'
        ]
        for phase in expected_phases:
            self.assertTrue(hasattr(AnalysisPhase, phase))
    
    def test_phase_values(self):
        """Test phase string values."""
        self.assertEqual(AnalysisPhase.INITIALIZING.value, "initializing")
        self.assertEqual(AnalysisPhase.COMPLETE.value, "complete")


class TestWorkerStatus(unittest.TestCase):
    """Tests for WorkerStatus enum."""
    
    def test_all_statuses_exist(self):
        """Test that all expected statuses are defined."""
        expected = ['IDLE', 'BUSY', 'OVERLOADED', 'FAILED', 'SHUTTING_DOWN']
        for status in expected:
            self.assertTrue(hasattr(WorkerStatus, status))


class TestFilePartition(unittest.TestCase):
    """Tests for FilePartition dataclass."""
    
    def test_creation(self):
        """Test FilePartition creation."""
        partition = FilePartition(
            partition_id=1,
            files=['file1.py', 'file2.py'],
            total_size_bytes=1000,
            estimated_complexity=2.5
        )
        
        self.assertEqual(partition.partition_id, 1)
        self.assertEqual(len(partition.files), 2)
        self.assertEqual(partition.status, "pending")
        self.assertIsNone(partition.worker_id)
    
    def test_processing_time(self):
        """Test processing time calculation."""
        partition = FilePartition(
            partition_id=0,
            files=['a.py'],
            total_size_bytes=500,
            estimated_complexity=1.0
        )
        
        # No start/end time
        self.assertIsNone(partition.processing_time)
        
        # With times
        partition.start_time = 1000.0
        partition.end_time = 1005.5
        self.assertAlmostEqual(partition.processing_time, 5.5)


class TestWorkerInfo(unittest.TestCase):
    """Tests for WorkerInfo dataclass."""
    
    def test_is_healthy(self):
        """Test worker health check."""
        # Healthy worker
        worker = WorkerInfo(
            worker_id="worker-1",
            hostname="localhost",
            status=WorkerStatus.IDLE,
            active_tasks=0,
            completed_tasks=10,
            failed_tasks=1,
            cpu_usage=25.0,
            memory_usage=50.0,
            last_heartbeat=datetime.utcnow()
        )
        self.assertTrue(worker.is_healthy)
        
        # Unhealthy - bad status
        worker.status = WorkerStatus.FAILED
        self.assertFalse(worker.is_healthy)
        
        # Unhealthy - stale heartbeat
        worker.status = WorkerStatus.IDLE
        worker.last_heartbeat = datetime.utcnow() - timedelta(seconds=120)
        self.assertFalse(worker.is_healthy)


class TestAnalysisProgress(unittest.TestCase):
    """Tests for AnalysisProgress dataclass."""
    
    def test_percentage_calculation(self):
        """Test progress percentage calculation."""
        progress = AnalysisProgress(
            session_id="test-123",
            phase=AnalysisPhase.PARSING,
            total_files=100,
            processed_files=25,
            failed_files=5,
            current_partition=2,
            total_partitions=4,
            start_time=datetime.utcnow()
        )
        
        self.assertEqual(progress.percentage, 25.0)
    
    def test_percentage_zero_files(self):
        """Test percentage with zero files."""
        progress = AnalysisProgress(
            session_id="test",
            phase=AnalysisPhase.INITIALIZING,
            total_files=0,
            processed_files=0,
            failed_files=0,
            current_partition=0,
            total_partitions=0,
            start_time=datetime.utcnow()
        )
        
        self.assertEqual(progress.percentage, 0.0)
    
    def test_to_dict(self):
        """Test progress serialization."""
        progress = AnalysisProgress(
            session_id="test-456",
            phase=AnalysisPhase.COMPLETE,
            total_files=50,
            processed_files=50,
            failed_files=2,
            current_partition=5,
            total_partitions=5,
            start_time=datetime.utcnow()
        )
        
        d = progress.to_dict()
        self.assertEqual(d['session_id'], "test-456")
        self.assertEqual(d['phase'], "complete")
        self.assertEqual(d['percentage'], 100.0)


class TestWorkloadBalancer(unittest.TestCase):
    """Tests for WorkloadBalancer class."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.balancer = WorkloadBalancer(
            target_partition_size=10,
            max_partition_size=50
        )
        
        # Create temporary test files
        self.temp_dir = tempfile.mkdtemp()
        self.test_files = []
        
        for i in range(25):
            ext = ['.py', '.js', '.ts'][i % 3]
            file_path = os.path.join(self.temp_dir, f"test_{i}{ext}")
            with open(file_path, 'w') as f:
                f.write(f"# Test file {i}\n" * (i + 1))
            self.test_files.append(file_path)
    
    def tearDown(self):
        """Clean up temp files."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_estimate_file_complexity(self):
        """Test file complexity estimation."""
        py_file = self.test_files[0]  # .py file
        js_file = self.test_files[1]  # .js file
        
        py_complexity = self.balancer.estimate_file_complexity(py_file)
        js_complexity = self.balancer.estimate_file_complexity(js_file)
        
        # Both should be positive
        self.assertGreater(py_complexity, 0)
        self.assertGreater(js_complexity, 0)
    
    def test_partition_simple(self):
        """Test simple partitioning."""
        partitions = self.balancer.partition_files(
            self.test_files,
            strategy="simple"
        )
        
        # Should have multiple partitions
        self.assertGreater(len(partitions), 0)
        
        # All files should be covered
        all_partitioned_files = []
        for p in partitions:
            all_partitioned_files.extend(p.files)
        self.assertEqual(len(all_partitioned_files), len(self.test_files))
    
    def test_partition_balanced(self):
        """Test balanced partitioning by complexity."""
        partitions = self.balancer.partition_files(
            self.test_files,
            strategy="balanced"
        )
        
        # Should have partitions
        self.assertGreater(len(partitions), 0)
        
        # Check partition properties
        for p in partitions:
            self.assertIsInstance(p, FilePartition)
            self.assertGreater(len(p.files), 0)
            self.assertGreaterEqual(p.estimated_complexity, 0)
    
    def test_partition_by_size(self):
        """Test partitioning by file size."""
        partitions = self.balancer.partition_files(
            self.test_files,
            strategy="size"
        )
        
        self.assertGreater(len(partitions), 0)
        
        # Total bytes should match
        total_bytes = sum(p.total_size_bytes for p in partitions)
        expected_bytes = sum(os.path.getsize(f) for f in self.test_files)
        self.assertEqual(total_bytes, expected_bytes)
    
    def test_empty_file_list(self):
        """Test partitioning empty file list."""
        partitions = self.balancer.partition_files([])
        self.assertEqual(len(partitions), 0)
    
    def test_select_worker(self):
        """Test worker selection."""
        partition = FilePartition(
            partition_id=0,
            files=['a.py'],
            total_size_bytes=100,
            estimated_complexity=1.0
        )
        
        workers = [
            WorkerInfo(
                worker_id="w1",
                hostname="host1",
                status=WorkerStatus.IDLE,
                active_tasks=5,
                completed_tasks=0,
                failed_tasks=0,
                cpu_usage=80.0,
                memory_usage=50.0,
                last_heartbeat=datetime.utcnow()
            ),
            WorkerInfo(
                worker_id="w2",
                hostname="host2",
                status=WorkerStatus.IDLE,
                active_tasks=1,
                completed_tasks=0,
                failed_tasks=0,
                cpu_usage=20.0,
                memory_usage=30.0,
                last_heartbeat=datetime.utcnow()
            ),
        ]
        
        selected = self.balancer.select_worker(partition, workers)
        
        # Should select the less loaded worker
        self.assertIsNotNone(selected)
        self.assertEqual(selected.worker_id, "w2")  # Lower load


class TestDistributedAnalyzer(unittest.TestCase):
    """Tests for DistributedAnalyzer class."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.analyzer = DistributedAnalyzer(
            worker_count=2,
            cache_enabled=False,  # Disable Redis for tests
            partition_size=5
        )
        
        # Create a test project
        self.temp_dir = tempfile.mkdtemp()
        
        # Create Python files
        py_dir = os.path.join(self.temp_dir, "src")
        os.makedirs(py_dir)
        
        for i in range(10):
            file_path = os.path.join(py_dir, f"module_{i}.py")
            with open(file_path, 'w') as f:
                f.write(f'''
def function_{i}(param):
    """A test function."""
    result = process(param)
    return result

class Class_{i}:
    def method(self):
        pass
''')
        
        # Create JS files
        js_dir = os.path.join(self.temp_dir, "js")
        os.makedirs(js_dir)
        
        for i in range(5):
            file_path = os.path.join(js_dir, f"script_{i}.js")
            with open(file_path, 'w') as f:
                f.write(f'''
function handler_{i}(req, res) {{
    const data = req.query.input;
    res.send(data);
}}
''')
    
    def tearDown(self):
        """Clean up temp files."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_discover_files(self):
        """Test file discovery."""
        files = self.analyzer.discover_files(self.temp_dir)
        
        # Should find 15 files (10 Python + 5 JS)
        self.assertEqual(len(files), 15)
        
        # Check extensions
        extensions = {os.path.splitext(f)[1] for f in files}
        self.assertIn('.py', extensions)
        self.assertIn('.js', extensions)
    
    def test_discover_files_with_limit(self):
        """Test file discovery with limit."""
        files = self.analyzer.discover_files(self.temp_dir, max_files=5)
        
        self.assertEqual(len(files), 5)
    
    def test_excluded_directories(self):
        """Test that excluded directories are skipped."""
        # Create a node_modules directory
        node_modules = os.path.join(self.temp_dir, "node_modules")
        os.makedirs(node_modules)
        
        with open(os.path.join(node_modules, "excluded.js"), 'w') as f:
            f.write("// Should be excluded")
        
        files = self.analyzer.discover_files(self.temp_dir)
        
        # node_modules should be excluded
        for file_path in files:
            self.assertNotIn("node_modules", file_path)
    
    def test_analyze_project(self):
        """Test full project analysis."""
        result = self.analyzer.analyze_project(
            self.temp_dir,
            max_files=100,
            include_taint=False  # Skip taint for speed
        )
        
        self.assertIsInstance(result, DistributedAnalysisResult)
        self.assertEqual(result.project_path, self.temp_dir)
        self.assertEqual(result.total_files, 15)
        self.assertGreater(result.files_analyzed, 0)
        self.assertGreater(result.duration_ms, 0)
        
        # Should have found some functions
        self.assertGreater(len(result.functions), 0)
    
    def test_analyze_empty_project(self):
        """Test analyzing empty project."""
        empty_dir = tempfile.mkdtemp()
        
        try:
            result = self.analyzer.analyze_project(empty_dir)
            
            self.assertEqual(result.total_files, 0)
            self.assertEqual(result.files_analyzed, 0)
        finally:
            os.rmdir(empty_dir)
    
    def test_progress_callback(self):
        """Test progress callback is called."""
        progress_updates = []
        
        def callback(progress):
            progress_updates.append(progress)
        
        analyzer = DistributedAnalyzer(
            worker_count=1,
            cache_enabled=False,
            progress_callback=callback
        )
        
        result = analyzer.analyze_project(
            self.temp_dir,
            max_files=5,
            include_taint=False
        )
        
        # Should have received progress updates
        self.assertGreater(len(progress_updates), 0)


class TestRedisCache(unittest.TestCase):
    """Tests for RedisCache class."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.cache = RedisCache(
            redis_url="redis://localhost:6379",
            default_ttl=3600,
            key_prefix="test:"
        )
    
    def test_make_key(self):
        """Test key prefix application."""
        key = self.cache._make_key("mykey")
        self.assertEqual(key, "test:mykey")
    
    def test_compute_file_hash(self):
        """Test file hash computation."""
        # Create a temp file
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.py') as f:
            f.write("print('hello')")
            temp_path = f.name
        
        try:
            hash1 = RedisCache.compute_file_hash(temp_path)
            hash2 = RedisCache.compute_file_hash(temp_path)
            
            # Same content should produce same hash
            self.assertEqual(hash1, hash2)
            self.assertEqual(len(hash1), 64)  # SHA256 hex length
        finally:
            os.unlink(temp_path)
    
    def test_compute_hash_nonexistent_file(self):
        """Test hash of nonexistent file."""
        hash_value = RedisCache.compute_file_hash("/nonexistent/file.py")
        self.assertEqual(hash_value, "")
    
    @patch('redis.from_url')
    def test_connect_sync_success(self, mock_redis):
        """Test successful sync connection."""
        mock_client = MagicMock()
        mock_client.ping.return_value = True
        mock_redis.return_value = mock_client
        
        # Patch REDIS_AVAILABLE
        import core.distributed_analyzer as da
        original_available = da.REDIS_AVAILABLE
        da.REDIS_AVAILABLE = True
        
        try:
            result = self.cache.connect_sync()
            self.assertTrue(result)
            self.assertTrue(self.cache._connected)
        finally:
            da.REDIS_AVAILABLE = original_available
    
    def test_get_without_connection(self):
        """Test get returns None without connection."""
        result = self.cache.get_sync("some_key")
        self.assertIsNone(result)
    
    def test_set_without_connection(self):
        """Test set returns False without connection."""
        result = self.cache.set_sync("key", {"data": 123})
        self.assertFalse(result)


class TestClusterOrchestrator(unittest.TestCase):
    """Tests for ClusterOrchestrator class."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.orchestrator = ClusterOrchestrator(
            heartbeat_interval=30,
            worker_timeout=120
        )
    
    def test_register_worker(self):
        """Test worker registration."""
        result = self.orchestrator.register_worker(
            worker_id="worker-001",
            hostname="server1.local",
            capabilities=['parse', 'taint']
        )
        
        self.assertTrue(result)
        self.assertIn("worker-001", self.orchestrator._workers)
    
    def test_unregister_worker(self):
        """Test worker unregistration."""
        self.orchestrator.register_worker("w1", "host1")
        
        result = self.orchestrator.unregister_worker("w1")
        self.assertTrue(result)
        self.assertNotIn("w1", self.orchestrator._workers)
        
        # Unregistering nonexistent worker
        result = self.orchestrator.unregister_worker("w999")
        self.assertFalse(result)
    
    def test_update_worker_status(self):
        """Test worker status update."""
        self.orchestrator.register_worker("w1", "host1")
        
        self.orchestrator.update_worker_status(
            "w1",
            status=WorkerStatus.BUSY,
            active_tasks=5,
            cpu_usage=75.0
        )
        
        worker = self.orchestrator._workers["w1"]
        self.assertEqual(worker.status, WorkerStatus.BUSY)
        self.assertEqual(worker.active_tasks, 5)
        self.assertEqual(worker.cpu_usage, 75.0)
    
    def test_heartbeat(self):
        """Test worker heartbeat."""
        self.orchestrator.register_worker("w1", "host1")
        
        old_heartbeat = self.orchestrator._workers["w1"].last_heartbeat
        time.sleep(0.01)
        
        self.orchestrator.heartbeat("w1", {"cpu_usage": 50.0})
        
        new_heartbeat = self.orchestrator._workers["w1"].last_heartbeat
        self.assertGreater(new_heartbeat, old_heartbeat)
    
    def test_get_healthy_workers(self):
        """Test getting healthy workers."""
        self.orchestrator.register_worker("w1", "host1")
        self.orchestrator.register_worker("w2", "host2")
        self.orchestrator.register_worker("w3", "host3")
        
        # Make w3 unhealthy
        self.orchestrator._workers["w3"].status = WorkerStatus.FAILED
        
        healthy = self.orchestrator.get_healthy_workers()
        
        self.assertEqual(len(healthy), 2)
        self.assertNotIn(
            "w3",
            [w.worker_id for w in healthy]
        )
    
    def test_get_cluster_stats(self):
        """Test cluster statistics."""
        self.orchestrator.register_worker("w1", "host1")
        self.orchestrator.register_worker("w2", "host2")
        
        self.orchestrator._workers["w1"].active_tasks = 3
        self.orchestrator._workers["w1"].completed_tasks = 10
        self.orchestrator._workers["w2"].active_tasks = 2
        self.orchestrator._workers["w2"].completed_tasks = 15
        
        stats = self.orchestrator.get_cluster_stats()
        
        self.assertEqual(stats['total_workers'], 2)
        self.assertEqual(stats['healthy_workers'], 2)
        self.assertEqual(stats['total_active_tasks'], 5)
        self.assertEqual(stats['total_completed_tasks'], 25)
    
    def test_select_workers_for_task(self):
        """Test worker selection for tasks."""
        self.orchestrator.register_worker("w1", "host1", capabilities=['parse', 'taint'])
        self.orchestrator.register_worker("w2", "host2", capabilities=['parse'])
        
        self.orchestrator._workers["w1"].active_tasks = 5
        self.orchestrator._workers["w2"].active_tasks = 1
        
        selected = self.orchestrator.select_workers_for_task("parse", count=1)
        
        # Should select w2 (lower load)
        self.assertEqual(len(selected), 1)
        self.assertEqual(selected[0].worker_id, "w2")


class TestConvenienceFunctions(unittest.TestCase):
    """Tests for convenience functions."""
    
    def test_create_distributed_analyzer(self):
        """Test analyzer creation function."""
        analyzer = create_distributed_analyzer(
            worker_count=4,
            partition_size=50
        )
        
        self.assertIsInstance(analyzer, DistributedAnalyzer)
        self.assertEqual(analyzer.worker_count, 4)
        self.assertEqual(analyzer.partition_size, 50)


class TestDistributedAnalysisResult(unittest.TestCase):
    """Tests for DistributedAnalysisResult dataclass."""
    
    def test_to_dict(self):
        """Test result serialization."""
        result = DistributedAnalysisResult(
            session_id="abc123",
            project_path="/test/project",
            total_files=100,
            files_analyzed=95,
            files_cached=20,
            files_failed=5,
            duration_ms=5000.0,
            endpoints=[{"id": 1}],
            functions=[{"name": "foo"}],
            classes=[{"name": "Bar"}],
            imports=["/import1"],
            taint_flows=[{"source": "a", "sink": "b"}],
            symbol_table={"funcs": {}},
            statistics={"parsed": 95},
            errors=["Error 1"],
            timestamp="2026-01-30T12:00:00"
        )
        
        d = result.to_dict()
        
        self.assertEqual(d['session_id'], "abc123")
        self.assertEqual(d['total_files'], 100)
        self.assertEqual(d['files_analyzed'], 95)
        self.assertEqual(len(d['endpoints']), 1)
        self.assertEqual(len(d['taint_flows']), 1)


class TestIntegration(unittest.TestCase):
    """Integration tests for distributed analysis."""
    
    def test_full_pipeline(self):
        """Test complete analysis pipeline."""
        # Create a realistic test project
        temp_dir = tempfile.mkdtemp()
        
        try:
            # Create Flask app
            app_code = '''
from flask import Flask, request

app = Flask(__name__)

@app.route('/api/users', methods=['GET'])
def get_users():
    user_id = request.args.get('id')
    return f"User: {user_id}"

@app.route('/api/data', methods=['POST'])
def post_data():
    data = request.json
    process(data)
    return {"status": "ok"}
'''
            with open(os.path.join(temp_dir, "app.py"), 'w') as f:
                f.write(app_code)
            
            # Create utility module
            util_code = '''
def process(data):
    return data.strip()

def validate(input_str):
    if not input_str:
        raise ValueError("Empty input")
    return True
'''
            with open(os.path.join(temp_dir, "utils.py"), 'w') as f:
                f.write(util_code)
            
            # Run analysis
            analyzer = DistributedAnalyzer(
                worker_count=1,
                cache_enabled=False
            )
            
            result = analyzer.analyze_project(
                temp_dir,
                include_taint=False
            )
            
            # Verify results
            self.assertEqual(result.total_files, 2)
            self.assertEqual(result.files_analyzed, 2)
            self.assertGreater(len(result.functions), 0)
            
        finally:
            import shutil
            shutil.rmtree(temp_dir, ignore_errors=True)


class TestPerformance(unittest.TestCase):
    """Performance tests for distributed analysis."""
    
    def test_partition_large_file_list(self):
        """Test partitioning performance with many files."""
        balancer = WorkloadBalancer(target_partition_size=100)
        
        # Create fake file list
        files = [f"/project/file_{i}.py" for i in range(10000)]
        
        start = time.time()
        partitions = balancer._partition_simple(files)
        duration = time.time() - start
        
        # Should complete quickly
        self.assertLess(duration, 1.0)  # Under 1 second
        self.assertGreater(len(partitions), 0)
    
    def test_analyzer_initialization(self):
        """Test analyzer initialization is fast."""
        start = time.time()
        
        for _ in range(10):
            analyzer = DistributedAnalyzer(
                worker_count=4,
                cache_enabled=False
            )
        
        duration = time.time() - start
        
        # 10 initializations should be fast
        self.assertLess(duration, 0.5)


if __name__ == '__main__':
    unittest.main(verbosity=2)
