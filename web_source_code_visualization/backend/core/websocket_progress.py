"""
WebSocket Progress Reporter

Real-time progress reporting via WebSocket connections.
Supports multiple concurrent clients and task progress streaming.
"""

from fastapi import WebSocket, WebSocketDisconnect
from typing import Dict, List, Set, Optional, Any
import asyncio
import json
from datetime import datetime
from dataclasses import dataclass, asdict
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class MessageType(str, Enum):
    """WebSocket message types."""
    CONNECT = "connect"
    DISCONNECT = "disconnect"
    SUBSCRIBE = "subscribe"
    UNSUBSCRIBE = "unsubscribe"
    PROGRESS = "progress"
    STATUS = "status"
    RESULT = "result"
    ERROR = "error"
    PING = "ping"
    PONG = "pong"
    WORKER_STATS = "worker_stats"
    QUEUE_STATS = "queue_stats"


@dataclass
class ProgressMessage:
    """Progress update message."""
    task_id: str
    phase: str
    current: int
    total: int
    percentage: float
    message: str
    timestamp: str
    details: Optional[Dict] = None
    
    def to_dict(self) -> Dict:
        return {
            'type': MessageType.PROGRESS,
            'data': asdict(self)
        }


@dataclass
class StatusMessage:
    """Task status message."""
    task_id: str
    status: str
    ready: bool
    successful: Optional[bool] = None
    error: Optional[str] = None
    
    def to_dict(self) -> Dict:
        return {
            'type': MessageType.STATUS,
            'data': asdict(self)
        }


@dataclass
class ResultMessage:
    """Task result message."""
    task_id: str
    status: str
    result: Dict
    duration_ms: float
    timestamp: str
    
    def to_dict(self) -> Dict:
        return {
            'type': MessageType.RESULT,
            'data': asdict(self)
        }


class ConnectionManager:
    """
    Manages WebSocket connections and message broadcasting.
    
    Features:
    - Connection tracking by client ID
    - Task subscription management
    - Broadcast to all or specific clients
    - Heartbeat monitoring
    """
    
    def __init__(self):
        # Active WebSocket connections: client_id -> WebSocket
        self.active_connections: Dict[str, WebSocket] = {}
        
        # Task subscriptions: task_id -> set of client_ids
        self.task_subscriptions: Dict[str, Set[str]] = {}
        
        # Client subscriptions: client_id -> set of task_ids
        self.client_subscriptions: Dict[str, Set[str]] = {}
        
        # Connection metadata
        self.connection_info: Dict[str, Dict] = {}
        
        # Lock for thread-safe operations
        self._lock = asyncio.Lock()
    
    async def connect(self, websocket: WebSocket, client_id: str) -> bool:
        """
        Accept a new WebSocket connection.
        
        Args:
            websocket: The WebSocket connection
            client_id: Unique client identifier
            
        Returns:
            True if connection was accepted
        """
        try:
            await websocket.accept()
            
            async with self._lock:
                self.active_connections[client_id] = websocket
                self.client_subscriptions[client_id] = set()
                self.connection_info[client_id] = {
                    'connected_at': datetime.utcnow().isoformat(),
                    'last_activity': datetime.utcnow().isoformat(),
                }
            
            # Send connection acknowledgment
            await self.send_personal_message({
                'type': MessageType.CONNECT,
                'data': {
                    'client_id': client_id,
                    'message': 'Connected to progress reporter',
                    'timestamp': datetime.utcnow().isoformat()
                }
            }, client_id)
            
            logger.info(f"Client {client_id} connected")
            return True
            
        except Exception as e:
            logger.error(f"Error accepting connection from {client_id}: {e}")
            return False
    
    async def disconnect(self, client_id: str):
        """
        Handle client disconnection.
        
        Args:
            client_id: The disconnecting client's ID
        """
        async with self._lock:
            # Remove from active connections
            if client_id in self.active_connections:
                del self.active_connections[client_id]
            
            # Clean up subscriptions
            if client_id in self.client_subscriptions:
                for task_id in self.client_subscriptions[client_id]:
                    if task_id in self.task_subscriptions:
                        self.task_subscriptions[task_id].discard(client_id)
                        if not self.task_subscriptions[task_id]:
                            del self.task_subscriptions[task_id]
                del self.client_subscriptions[client_id]
            
            # Remove connection info
            if client_id in self.connection_info:
                del self.connection_info[client_id]
        
        logger.info(f"Client {client_id} disconnected")
    
    async def subscribe_to_task(self, client_id: str, task_id: str) -> bool:
        """
        Subscribe a client to task updates.
        
        Args:
            client_id: The client's ID
            task_id: The task to subscribe to
            
        Returns:
            True if subscription was successful
        """
        async with self._lock:
            if client_id not in self.active_connections:
                return False
            
            # Add to task subscriptions
            if task_id not in self.task_subscriptions:
                self.task_subscriptions[task_id] = set()
            self.task_subscriptions[task_id].add(client_id)
            
            # Add to client subscriptions
            self.client_subscriptions[client_id].add(task_id)
        
        # Notify client of subscription
        await self.send_personal_message({
            'type': MessageType.SUBSCRIBE,
            'data': {
                'task_id': task_id,
                'message': f'Subscribed to task {task_id}',
                'timestamp': datetime.utcnow().isoformat()
            }
        }, client_id)
        
        logger.debug(f"Client {client_id} subscribed to task {task_id}")
        return True
    
    async def unsubscribe_from_task(self, client_id: str, task_id: str) -> bool:
        """
        Unsubscribe a client from task updates.
        
        Args:
            client_id: The client's ID
            task_id: The task to unsubscribe from
            
        Returns:
            True if unsubscription was successful
        """
        async with self._lock:
            if task_id in self.task_subscriptions:
                self.task_subscriptions[task_id].discard(client_id)
                if not self.task_subscriptions[task_id]:
                    del self.task_subscriptions[task_id]
            
            if client_id in self.client_subscriptions:
                self.client_subscriptions[client_id].discard(task_id)
        
        await self.send_personal_message({
            'type': MessageType.UNSUBSCRIBE,
            'data': {
                'task_id': task_id,
                'message': f'Unsubscribed from task {task_id}',
                'timestamp': datetime.utcnow().isoformat()
            }
        }, client_id)
        
        return True
    
    async def send_personal_message(self, message: Dict, client_id: str):
        """
        Send a message to a specific client.
        
        Args:
            message: The message to send
            client_id: The target client's ID
        """
        if client_id in self.active_connections:
            try:
                websocket = self.active_connections[client_id]
                await websocket.send_json(message)
                
                # Update last activity
                if client_id in self.connection_info:
                    self.connection_info[client_id]['last_activity'] = datetime.utcnow().isoformat()
                    
            except Exception as e:
                logger.error(f"Error sending message to {client_id}: {e}")
                await self.disconnect(client_id)
    
    async def broadcast(self, message: Dict):
        """
        Broadcast a message to all connected clients.
        
        Args:
            message: The message to broadcast
        """
        disconnected = []
        
        for client_id, websocket in self.active_connections.items():
            try:
                await websocket.send_json(message)
            except Exception as e:
                logger.error(f"Error broadcasting to {client_id}: {e}")
                disconnected.append(client_id)
        
        # Clean up disconnected clients
        for client_id in disconnected:
            await self.disconnect(client_id)
    
    async def send_task_progress(self, task_id: str, progress: ProgressMessage):
        """
        Send progress update to all clients subscribed to a task.
        
        Args:
            task_id: The task ID
            progress: The progress update
        """
        if task_id not in self.task_subscriptions:
            return
        
        message = progress.to_dict()
        
        for client_id in list(self.task_subscriptions.get(task_id, [])):
            await self.send_personal_message(message, client_id)
    
    async def send_task_status(self, task_id: str, status: StatusMessage):
        """
        Send status update to all clients subscribed to a task.
        
        Args:
            task_id: The task ID
            status: The status update
        """
        if task_id not in self.task_subscriptions:
            return
        
        message = status.to_dict()
        
        for client_id in list(self.task_subscriptions.get(task_id, [])):
            await self.send_personal_message(message, client_id)
    
    async def send_task_result(self, task_id: str, result: ResultMessage):
        """
        Send final result to all clients subscribed to a task.
        
        Args:
            task_id: The task ID
            result: The task result
        """
        if task_id not in self.task_subscriptions:
            return
        
        message = result.to_dict()
        
        for client_id in list(self.task_subscriptions.get(task_id, [])):
            await self.send_personal_message(message, client_id)
    
    def get_stats(self) -> Dict:
        """Get connection manager statistics."""
        return {
            'active_connections': len(self.active_connections),
            'task_subscriptions': {
                task_id: len(clients) 
                for task_id, clients in self.task_subscriptions.items()
            },
            'total_subscriptions': sum(
                len(tasks) for tasks in self.client_subscriptions.values()
            ),
        }


# Global connection manager instance
connection_manager = ConnectionManager()


class ProgressReporter:
    """
    Reports task progress via WebSocket.
    
    Usage:
        reporter = ProgressReporter(task_id)
        await reporter.report_progress('parsing', 5, 10, 'Parsing files...')
        await reporter.report_complete(result)
    """
    
    def __init__(self, task_id: str):
        self.task_id = task_id
        self.manager = connection_manager
    
    async def report_progress(
        self,
        phase: str,
        current: int,
        total: int,
        message: str,
        details: Dict = None
    ):
        """Report progress update."""
        percentage = (current / total * 100) if total > 0 else 0
        
        progress = ProgressMessage(
            task_id=self.task_id,
            phase=phase,
            current=current,
            total=total,
            percentage=round(percentage, 1),
            message=message,
            timestamp=datetime.utcnow().isoformat(),
            details=details
        )
        
        await self.manager.send_task_progress(self.task_id, progress)
    
    async def report_status(self, status: str, ready: bool = False, successful: bool = None, error: str = None):
        """Report task status change."""
        status_msg = StatusMessage(
            task_id=self.task_id,
            status=status,
            ready=ready,
            successful=successful,
            error=error
        )
        
        await self.manager.send_task_status(self.task_id, status_msg)
    
    async def report_complete(self, result: Dict, duration_ms: float):
        """Report task completion with result."""
        result_msg = ResultMessage(
            task_id=self.task_id,
            status='complete',
            result=result,
            duration_ms=duration_ms,
            timestamp=datetime.utcnow().isoformat()
        )
        
        await self.manager.send_task_result(self.task_id, result_msg)
    
    async def report_error(self, error: str):
        """Report task error."""
        await self.manager.send_task_status(
            self.task_id,
            StatusMessage(
                task_id=self.task_id,
                status='error',
                ready=True,
                successful=False,
                error=error
            )
        )


class TaskProgressPoller:
    """
    Polls Celery task progress and reports via WebSocket.
    
    This bridges the gap between Celery's task state and WebSocket clients.
    """
    
    def __init__(self, poll_interval: float = 0.5):
        self.poll_interval = poll_interval
        self.active_polls: Dict[str, asyncio.Task] = {}
        self._lock = asyncio.Lock()
    
    async def start_polling(self, task_id: str):
        """Start polling a task for progress updates."""
        async with self._lock:
            if task_id in self.active_polls:
                return  # Already polling
            
            poll_task = asyncio.create_task(self._poll_task(task_id))
            self.active_polls[task_id] = poll_task
    
    async def stop_polling(self, task_id: str):
        """Stop polling a task."""
        async with self._lock:
            if task_id in self.active_polls:
                self.active_polls[task_id].cancel()
                del self.active_polls[task_id]
    
    async def _poll_task(self, task_id: str):
        """Poll a task for progress updates."""
        from core.distributed_tasks import get_task_status
        
        reporter = ProgressReporter(task_id)
        last_progress = None
        
        try:
            while True:
                status = get_task_status(task_id)
                
                if status['status'] == 'PROGRESS':
                    progress = status.get('progress', {})
                    if progress != last_progress:
                        await reporter.report_progress(
                            phase=progress.get('phase', 'unknown'),
                            current=progress.get('current', 0),
                            total=progress.get('total', 0),
                            message=progress.get('message', ''),
                            details=progress.get('details')
                        )
                        last_progress = progress
                
                elif status['ready']:
                    if status.get('successful'):
                        result = status.get('result', {})
                        await reporter.report_complete(
                            result=result,
                            duration_ms=result.get('duration_ms', 0)
                        )
                    else:
                        await reporter.report_error(status.get('error', 'Unknown error'))
                    
                    # Stop polling on completion
                    break
                
                else:
                    await reporter.report_status(status['status'])
                
                await asyncio.sleep(self.poll_interval)
                
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error(f"Error polling task {task_id}: {e}")
        finally:
            async with self._lock:
                if task_id in self.active_polls:
                    del self.active_polls[task_id]


# Global progress poller instance
progress_poller = TaskProgressPoller()


async def handle_websocket_message(websocket: WebSocket, client_id: str, message: Dict):
    """
    Handle incoming WebSocket messages from clients.
    
    Supported message types:
    - subscribe: Subscribe to task updates
    - unsubscribe: Unsubscribe from task updates
    - ping: Heartbeat ping
    - status: Request task status
    """
    msg_type = message.get('type')
    data = message.get('data', {})
    
    if msg_type == 'subscribe':
        task_id = data.get('task_id')
        if task_id:
            await connection_manager.subscribe_to_task(client_id, task_id)
            # Start polling for this task
            await progress_poller.start_polling(task_id)
    
    elif msg_type == 'unsubscribe':
        task_id = data.get('task_id')
        if task_id:
            await connection_manager.unsubscribe_from_task(client_id, task_id)
    
    elif msg_type == 'ping':
        await connection_manager.send_personal_message({
            'type': MessageType.PONG,
            'data': {'timestamp': datetime.utcnow().isoformat()}
        }, client_id)
    
    elif msg_type == 'status':
        task_id = data.get('task_id')
        if task_id:
            from core.distributed_tasks import get_task_status
            status = get_task_status(task_id)
            await connection_manager.send_personal_message({
                'type': MessageType.STATUS,
                'data': status
            }, client_id)
    
    elif msg_type == 'worker_stats':
        from core.celery_config import get_worker_stats
        stats = get_worker_stats()
        await connection_manager.send_personal_message({
            'type': MessageType.WORKER_STATS,
            'data': stats
        }, client_id)
    
    elif msg_type == 'queue_stats':
        from core.celery_config import get_queue_stats
        stats = get_queue_stats()
        await connection_manager.send_personal_message({
            'type': MessageType.QUEUE_STATS,
            'data': stats
        }, client_id)


def get_connection_manager() -> ConnectionManager:
    """Get the global connection manager instance."""
    return connection_manager


def get_progress_poller() -> TaskProgressPoller:
    """Get the global progress poller instance."""
    return progress_poller
