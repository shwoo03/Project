"""
Docker Compose 관리 서비스 - docker compose CLI 래핑
"""
import asyncio
import json
import logging
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)


class ComposeService:
    """Docker Compose CLI를 통한 프로젝트 관리"""

    async def _run_command(self, *args: str, cwd: str = None) -> tuple[int, str, str]:
        """docker compose 명령 실행"""
        cmd = ["docker", "compose", *args]
        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=cwd,
            )
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=120)
            return proc.returncode, stdout.decode("utf-8", errors="replace"), stderr.decode("utf-8", errors="replace")
        except asyncio.TimeoutError:
            logger.error(f"Command timed out: {' '.join(cmd)}")
            return -1, "", "Command timed out"
        except FileNotFoundError:
            logger.error("docker compose CLI not found")
            return -1, "", "docker compose CLI not found"
        except Exception as e:
            logger.error(f"Error running command: {e}")
            return -1, "", str(e)

    async def list_projects(self) -> List[Dict[str, Any]]:
        """Compose 프로젝트 목록 반환"""
        code, stdout, stderr = await self._run_command("ls", "--format", "json")
        if code != 0:
            logger.error(f"Failed to list compose projects: {stderr}")
            return []

        try:
            # docker compose ls --format json은 JSON 배열을 반환
            projects = json.loads(stdout) if stdout.strip() else []
            result = []
            for proj in projects:
                result.append({
                    "name": proj.get("Name", ""),
                    "status": proj.get("Status", ""),
                    "config_files": proj.get("ConfigFiles", ""),
                })
            return result
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse compose ls output: {e}")
            return []

    async def get_project_services(self, config_file: str) -> List[Dict[str, Any]]:
        """특정 프로젝트의 서비스 목록 반환"""
        code, stdout, stderr = await self._run_command(
            "-f", config_file, "ps", "--format", "json", "-a"
        )
        if code != 0:
            logger.error(f"Failed to get services: {stderr}")
            return []

        try:
            services = []
            # docker compose ps --format json은 줄별 JSON 또는 배열을 반환
            for line in stdout.strip().split("\n"):
                line = line.strip()
                if not line:
                    continue
                try:
                    svc = json.loads(line)
                    # 단일 오브젝트 또는 배열
                    if isinstance(svc, list):
                        services.extend(svc)
                    else:
                        services.append(svc)
                except json.JSONDecodeError:
                    continue

            result = []
            for svc in services:
                result.append({
                    "name": svc.get("Name", svc.get("Service", "")),
                    "service": svc.get("Service", ""),
                    "state": svc.get("State", svc.get("Status", "")),
                    "status": svc.get("Status", ""),
                    "ports": svc.get("Publishers") or svc.get("Ports", ""),
                    "image": svc.get("Image", ""),
                })
            return result
        except Exception as e:
            logger.error(f"Failed to parse compose ps output: {e}")
            return []

    async def project_action(self, config_file: str, action: str) -> Dict[str, Any]:
        """Compose 프로젝트에 액션 수행 (up, down, restart, pull)"""
        valid_actions = ["up", "down", "restart", "pull", "stop", "start"]
        if action not in valid_actions:
            return {"success": False, "error": f"Invalid action: {action}"}

        args = ["-f", config_file]
        if action == "up":
            args.extend(["up", "-d"])
        elif action == "down":
            args.append("down")
        elif action == "restart":
            args.append("restart")
        elif action == "pull":
            args.append("pull")
        elif action == "stop":
            args.append("stop")
        elif action == "start":
            args.append("start")

        code, stdout, stderr = await self._run_command(*args)

        if code == 0:
            return {"success": True, "message": f"Action '{action}' completed", "output": stdout}
        else:
            return {"success": False, "error": stderr or "Action failed", "output": stdout}


# 싱글톤 인스턴스
compose_service = ComposeService()
