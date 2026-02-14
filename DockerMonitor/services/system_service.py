"""
Docker System Info 서비스 - docker system df 정보 조회
"""
from typing import Dict, Any
from .base_service import BaseService
import logging

logger = logging.getLogger(__name__)


class SystemService(BaseService):
    """Docker 시스템 정보 (디스크 사용량 등) 조회 서비스"""

    def _format_bytes(self, size: int) -> str:
        """바이트를 사람이 읽기 쉬운 형태로 변환"""
        for unit in ["B", "KB", "MB", "GB", "TB"]:
            if abs(size) < 1024.0:
                return f"{size:.2f} {unit}"
            size /= 1024.0
        return f"{size:.2f} PB"

    def _get_system_df_sync(self) -> Dict[str, Any]:
        """docker system df 정보를 동기로 조회"""
        try:
            df_data = self.client.df()

            # 이미지 정보
            images = df_data.get("Images", []) or []
            images_active = sum(1 for img in images if img.get("Containers", 0) > 0)
            images_total_size = sum(img.get("Size", 0) for img in images)
            images_reclaimable = sum(
                img.get("Size", 0) for img in images if img.get("Containers", 0) == 0
            )

            # 컨테이너 정보
            containers = df_data.get("Containers", []) or []
            containers_running = sum(1 for c in containers if c.get("State", "") == "running")
            containers_stopped = sum(1 for c in containers if c.get("State", "") != "running")
            containers_total_size = sum(c.get("SizeRw", 0) for c in containers)

            # 볼륨 정보
            volumes = df_data.get("Volumes", []) or []
            volumes_active = sum(1 for v in volumes if v.get("UsageData", {}).get("RefCount", 0) > 0)
            volumes_total_size = sum(
                v.get("UsageData", {}).get("Size", 0) for v in volumes
                if v.get("UsageData", {}).get("Size", -1) >= 0
            )
            volumes_reclaimable = sum(
                v.get("UsageData", {}).get("Size", 0) for v in volumes
                if v.get("UsageData", {}).get("RefCount", 0) == 0
                and v.get("UsageData", {}).get("Size", -1) >= 0
            )

            # 빌드 캐시 정보
            build_cache = df_data.get("BuildCache", []) or []
            build_cache_total_size = sum(bc.get("Size", 0) for bc in build_cache)
            build_cache_reclaimable = sum(
                bc.get("Size", 0) for bc in build_cache if not bc.get("InUse", False)
            )

            # Docker 호스트 정보
            info = self.client.info()
            version = self.client.version()

            return {
                "images": {
                    "total": len(images),
                    "active": images_active,
                    "total_size": images_total_size,
                    "total_size_human": self._format_bytes(images_total_size),
                    "reclaimable": images_reclaimable,
                    "reclaimable_human": self._format_bytes(images_reclaimable),
                },
                "containers": {
                    "total": len(containers),
                    "running": containers_running,
                    "stopped": containers_stopped,
                    "total_size": containers_total_size,
                    "total_size_human": self._format_bytes(containers_total_size),
                },
                "volumes": {
                    "total": len(volumes),
                    "active": volumes_active,
                    "total_size": volumes_total_size,
                    "total_size_human": self._format_bytes(volumes_total_size),
                    "reclaimable": volumes_reclaimable,
                    "reclaimable_human": self._format_bytes(volumes_reclaimable),
                },
                "build_cache": {
                    "total": len(build_cache),
                    "total_size": build_cache_total_size,
                    "total_size_human": self._format_bytes(build_cache_total_size),
                    "reclaimable": build_cache_reclaimable,
                    "reclaimable_human": self._format_bytes(build_cache_reclaimable),
                },
                "host": {
                    "os": info.get("OperatingSystem", ""),
                    "architecture": info.get("Architecture", ""),
                    "kernel": info.get("KernelVersion", ""),
                    "cpus": info.get("NCPU", 0),
                    "memory_total": info.get("MemTotal", 0),
                    "memory_total_human": self._format_bytes(info.get("MemTotal", 0)),
                    "docker_version": version.get("Version", ""),
                    "api_version": version.get("ApiVersion", ""),
                    "storage_driver": info.get("Driver", ""),
                    "docker_root_dir": info.get("DockerRootDir", ""),
                },
            }
        except Exception as e:
            logger.error(f"Error getting system df: {e}")
            raise

    async def get_system_info(self) -> Dict[str, Any]:
        """Docker 시스템 정보 조회"""
        if not await self.ensure_connected():
            return {}
        return await self.run_sync(self._get_system_df_sync)
