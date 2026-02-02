from fastapi import APIRouter, WebSocket, WebSocketDisconnect
import asyncio
import logging
from core.docker_client import docker_manager

router = APIRouter(tags=["terminal"])
logger = logging.getLogger(__name__)


def extract_raw_socket(socket_response):
    """
    Docker socket 응답에서 실제 쓰기 가능한 소켓 객체를 추출합니다.
    Windows와 Linux 환경 모두 지원합니다.
    """
    # docker-py exec_start(socket=True) 반환 타입 분석:
    # - SocketIO wrapper (가장 일반적)
    # - HTTPResponse._fp (일부 버전)
    
    sock = socket_response
    
    # 1차: SocketIO의 _sock 접근 시도
    if hasattr(sock, '_sock'):
        inner_sock = sock._sock
        # inner_sock이 실제 socket인 경우
        if hasattr(inner_sock, 'sendall'):
            return inner_sock
        # inner_sock이 또 다른 wrapper인 경우
        if hasattr(inner_sock, '_sock'):
            return inner_sock._sock
    
    # 2차: 원본 소켓 그대로 사용 (이미 raw socket인 경우)
    if hasattr(sock, 'sendall'):
        return sock
    
    # 3차: _response 경로 시도 (일부 docker-py 버전)
    if hasattr(sock, '_response'):
        resp = sock._response
        if hasattr(resp, '_fp') and hasattr(resp._fp, 'fp'):
            fp = resp._fp.fp
            if hasattr(fp, 'raw') and hasattr(fp.raw, '_sock'):
                return fp.raw._sock
    
    # 찾지 못한 경우 원본 반환
    logger.warning(f"Could not extract raw socket from {type(sock)}, using original")
    return sock


@router.websocket("/ws/exec/{container_id}")
async def terminal_websocket(websocket: WebSocket, container_id: str):
    await websocket.accept()
    
    # Exec 인스턴스 생성
    exec_id = await docker_manager.create_exec_instance(container_id)
    if not exec_id:
        await websocket.send_text("\r\n[ERROR] Failed to create exec instance\r\n")
        await websocket.close(code=1000, reason="Failed to create exec instance")
        return

    # Docker socket 가져오기
    socket_response = await docker_manager.get_exec_socket(exec_id)
    
    if not socket_response:
        await websocket.send_text("\r\n[ERROR] Failed to get exec socket\r\n")
        await websocket.close(code=1000, reason="Failed to get exec socket")
        return

    # Raw 소켓 추출
    raw_sock = extract_raw_socket(socket_response)
    logger.info(f"Socket type: {type(socket_response)}, Raw socket type: {type(raw_sock)}")
    
    # 소켓을 논블로킹 모드로 설정 시도
    try:
        raw_sock.setblocking(False)
    except Exception as e:
        logger.warning(f"Could not set socket to non-blocking: {e}")
    
    loop = asyncio.get_event_loop()
    running = True
    
    async def forward_output():
        """Docker 소켓에서 WebSocket으로 출력 전달"""
        nonlocal running
        try:
            while running:
                try:
                    # 논블로킹 읽기 시도
                    data = await loop.run_in_executor(None, lambda: raw_sock.recv(4096))
                    if not data:
                        logger.info("Docker socket closed (empty read)")
                        break
                    await websocket.send_bytes(data)
                except BlockingIOError:
                    # 논블로킹 모드에서 데이터 없음 - 잠시 대기
                    await asyncio.sleep(0.01)
                except ConnectionResetError:
                    logger.info("Docker connection reset")
                    break
                except Exception as e:
                    if running:
                        logger.error(f"Output forwarding error: {e}")
                    break
        except Exception as e:
            logger.error(f"Output task error: {e}")
        finally:
            running = False
            
    async def forward_input():
        """WebSocket에서 Docker 소켓으로 입력 전달"""
        nonlocal running
        try:
            while running:
                try:
                    data = await websocket.receive_text()
                    payload = data.encode('utf-8')
                    
                    # sendall 사용 (가장 안정적)
                    await loop.run_in_executor(None, lambda: raw_sock.sendall(payload))
                    
                except WebSocketDisconnect:
                    logger.info("WebSocket disconnected by client")
                    break
                except BrokenPipeError:
                    logger.info("Docker socket pipe broken")
                    break
                except OSError as e:
                    # Windows에서 발생할 수 있는 소켓 에러
                    if e.errno == 10038:  # WSAENOTSOCK
                        logger.info("Socket is no longer valid")
                        break
                    logger.error(f"OS error during input: {e}")
                    break
                except Exception as e:
                    if running:
                        logger.error(f"Input forwarding error: {e}")
                    break
        except Exception as e:
            logger.error(f"Input task error: {e}")
        finally:
            running = False

    try:
        # 두 태스크 동시 실행
        task_output = asyncio.create_task(forward_output())
        task_input = asyncio.create_task(forward_input())
        
        logger.info(f"Terminal session started for container={container_id}, exec_id={exec_id}")
        
        # 둘 중 하나라도 종료되면 전체 종료
        done, pending = await asyncio.wait(
            [task_output, task_input], 
            return_when=asyncio.FIRST_COMPLETED
        )

        # 미완료 태스크 취소
        running = False
        for task in pending:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
                
    except Exception as e:
        logger.error(f"Terminal session error: {e}")
    finally:
        running = False
        
        # 소켓 정리
        try:
            raw_sock.close()
        except Exception:
            pass
        
        # 원본 socket_response도 정리
        if socket_response is not raw_sock:
            try:
                socket_response.close()
            except Exception:
                pass
        
        # WebSocket 정리
        try:
            await websocket.close()
        except Exception:
            pass
        
        logger.info(f"Terminal session ended for container={container_id}")
