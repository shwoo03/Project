from fastapi import APIRouter, WebSocket, WebSocketDisconnect
import asyncio
import logging
from services import exec_service

router = APIRouter(tags=["terminal"])
logger = logging.getLogger(__name__)


def extract_raw_socket(socket_response):
    """
    Docker socket 응답에서 실제 쓰기 가능한 소켓 객체를 추출합니다.
    Windows와 Linux 환경 모두 지원합니다.
    """
    sock = socket_response

    # 1차: SocketIO의 _sock 접근 시도
    if hasattr(sock, '_sock'):
        inner_sock = sock._sock
        if hasattr(inner_sock, 'sendall'):
            return inner_sock
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

    logger.warning(f"Could not extract raw socket from {type(sock)}, using original")
    return sock


@router.websocket("/ws/exec/{container_id}")
async def terminal_websocket(websocket: WebSocket, container_id: str):
    await websocket.accept()

    # Exec 인스턴스 생성
    exec_id = await exec_service.create_exec_instance(container_id)
    if not exec_id:
        await websocket.send_text("\r\n[ERROR] Failed to create exec instance\r\n")
        await websocket.close(code=1000, reason="Failed to create exec instance")
        return

    # Docker socket 가져오기
    socket_response = await exec_service.get_exec_socket(exec_id)

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

    loop = asyncio.get_running_loop()
    running = True

    async def forward_output():
        """Docker 소켓에서 WebSocket으로 출력 전달"""
        nonlocal running
        try:
            while running:
                try:
                    data = await loop.run_in_executor(None, lambda: raw_sock.recv(4096))
                    if not data:
                        logger.info("Docker socket closed (empty read)")
                        break
                    await websocket.send_bytes(data)
                except BlockingIOError:
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
                    await loop.run_in_executor(None, lambda: raw_sock.sendall(payload))
                except WebSocketDisconnect:
                    logger.info("WebSocket disconnected by client")
                    break
                except BrokenPipeError:
                    logger.info("Docker socket pipe broken")
                    break
                except OSError as e:
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
        task_output = asyncio.create_task(forward_output())
        task_input = asyncio.create_task(forward_input())

        logger.info(f"Terminal session started for container={container_id}, exec_id={exec_id}")

        done, pending = await asyncio.wait(
            [task_output, task_input],
            return_when=asyncio.FIRST_COMPLETED,
        )

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

        try:
            raw_sock.close()
        except Exception:
            pass

        if socket_response is not raw_sock:
            try:
                socket_response.close()
            except Exception:
                pass

        try:
            await websocket.close()
        except Exception:
            pass

        logger.info(f"Terminal session ended for container={container_id}")
