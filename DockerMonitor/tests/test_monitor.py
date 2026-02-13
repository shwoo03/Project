"""
모니터 상태 변경 감지 테스트
"""
import pytest
from core.monitor import DockerMonitor


def test_detect_status_changes_initial():
    """최초 호출 시 이벤트 없음 (이전 상태가 없으므로)"""
    m = DockerMonitor.__new__(DockerMonitor)
    m._prev_statuses = {}

    containers = [
        {"id": "abc", "name": "web", "status": "running"},
        {"id": "def", "name": "db", "status": "running"},
    ]
    events = m._detect_status_changes(containers)
    assert len(events) == 0


def test_detect_status_changes_stopped():
    """running → exited 감지"""
    m = DockerMonitor.__new__(DockerMonitor)
    m._prev_statuses = {"abc": "running", "def": "running"}

    containers = [
        {"id": "abc", "name": "web", "status": "exited"},
        {"id": "def", "name": "db", "status": "running"},
    ]
    events = m._detect_status_changes(containers)
    assert len(events) == 1
    assert events[0]["name"] == "web"
    assert events[0]["from"] == "running"
    assert events[0]["to"] == "exited"


def test_detect_status_changes_started():
    """exited → running 감지"""
    m = DockerMonitor.__new__(DockerMonitor)
    m._prev_statuses = {"abc": "exited"}

    containers = [{"id": "abc", "name": "web", "status": "running"}]
    events = m._detect_status_changes(containers)
    assert len(events) == 1
    assert events[0]["to"] == "running"


def test_detect_status_changes_removed():
    """컨테이너 제거 감지"""
    m = DockerMonitor.__new__(DockerMonitor)
    m._prev_statuses = {"abc": "running", "del123456789": "exited"}

    containers = [{"id": "abc", "name": "web", "status": "running"}]
    events = m._detect_status_changes(containers)
    assert len(events) == 1
    assert events[0]["to"] == "removed"


def test_detect_no_changes():
    """변경 없음"""
    m = DockerMonitor.__new__(DockerMonitor)
    m._prev_statuses = {"abc": "running"}

    containers = [{"id": "abc", "name": "web", "status": "running"}]
    events = m._detect_status_changes(containers)
    assert len(events) == 0
