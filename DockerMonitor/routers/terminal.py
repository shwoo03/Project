from fastapi import APIRouter, WebSocket, WebSocketDisconnect
import asyncio
import logging
import socket
import os
import sys
from core.docker_client import docker_manager

router = APIRouter(tags=["terminal"])
logger = logging.getLogger(__name__)

@router.websocket("/ws/exec/{container_id}")
async def terminal_websocket(websocket: WebSocket, container_id: str):
    await websocket.accept()
    
    exec_id = await docker_manager.create_exec_instance(container_id)
    if not exec_id:
        await websocket.close(code=1000, reason="Failed to create exec instance")
        return

    # docker-py의 socket은 raw socket (Windows에서는 NamedPipe일 수도 있음)
    # Windows에서 asyncio로 NamedPipe를 다루는 건 복잡할 수 있음.
    # 안전하게 ThreadExecutor를 사용하여 blocking read를 수행하는 것이 좋음.
    
    sock = await docker_manager.get_exec_socket(exec_id)
    

    if not sock:
        await websocket.close(code=1000, reason="Failed to get exec socket")
        return

    logger.info(f"Socket details - Type: {type(sock)}, Dir: {dir(sock)}")
    if hasattr(sock, 'fileno'):
        try:
            logger.info(f"Socket fileno: {sock.fileno()}")
        except:
            logger.info("Socket fileno() failed")
            
    try:
        # 두 개의 비동기 태스크 실행
        # 1. Docker Socket -> WebSocket (Output)
        # 2. WebSocket -> Docker Socket (Input)
        
        loop = asyncio.get_event_loop()
        
        loop = asyncio.get_event_loop()
        
        async def forward_output():
            try:
                while True:
                    # Blocking read in thread pool
                    # Docker socket on Windows/Linux differences:
                    # Some return 'recv', some might need 'read'
                    if hasattr(sock, 'recv'):
                        data = await loop.run_in_executor(None, sock.recv, 4096)
                    elif hasattr(sock, 'read'):
                        data = await loop.run_in_executor(None, sock.read, 4096)
                    else:
                        logger.error("Socket object has no recv or read method")
                        break
                        
                    if not data:
                        break
                    await websocket.send_bytes(data)
            except Exception as e:
                logger.error(f"Output forwarding error: {e}")
                # Log traceback for debugging
                import traceback
                logger.error(traceback.format_exc())
            
        async def forward_input():
            try:
                while True:
                    data = await websocket.receive_text()
                    payload = data.encode()
                    
                    # Try multiple write methods
                    success = False
                    errors = []
                    
                    # Method 1: os.write with fileno (Most reliable for raw pipes on Windows if available)
                    if not success:
                        try:
                            if hasattr(sock, 'fileno'):
                                fd = sock.fileno()
                                if fd != -1:
                                    os.write(fd, payload)
                                    success = True
                        except Exception as e:
                            errors.append(f"os.write: {e}")

                    # Method 2: sock.send
                    if not success:
                        try:
                            if hasattr(sock, 'send'):
                                sock.send(payload)
                                success = True
                        except Exception as e:
                            errors.append(f"sock.send: {e}")

                    # Method 3: sock._sock.send (Underlying socket/ssl wrapper)
                    if not success:
                        try:
                            if hasattr(sock, '_sock') and hasattr(sock._sock, 'send'):
                                sock._sock.send(payload)
                                success = True
                        except Exception as e:
                            errors.append(f"sock._sock.send: {e}")
                            
                    # Method 4: sock.write (File-like)
                    if not success:
                        try:
                            if hasattr(sock, 'write'):
                                sock.write(payload)
                                if hasattr(sock, 'flush'):
                                    sock.flush()
                                success = True
                        except Exception as e:
                            errors.append(f"sock.write: {e}")

                    if not success:
                        logger.error(f"Failed to write to docker socket. Methods tried: {errors}")
                        # Don't break immediately, let the user see the error in logs or try again
                        # break 
                        pass

            except WebSocketDisconnect:
                pass
            except Exception as e:
                logger.error(f"Input forwarding error: {e}")

        # 태스크 동시 실행
        task_output = asyncio.create_task(forward_output())
        task_input = asyncio.create_task(forward_input())
        
        logger.info(f"Terminal session started for {container_id}, exec_id={exec_id}")
        
        # 둘 중 하나라도 끝나면 종료 (보통 output이 끝나면(exit) 종료)
        done, pending = await asyncio.wait(
            [task_output, task_input], 
            return_when=asyncio.FIRST_COMPLETED
        )

        for task in pending:
            task.cancel()
            
    except Exception as e:
        logger.error(f"Terminal session error: {e}")
        import traceback
        logger.error(traceback.format_exc())
    finally:
        # sock.close() might fail on some wrappers
        try:
            sock.close()
        except:
            pass
        try:
            await websocket.close()
        except:
            pass

