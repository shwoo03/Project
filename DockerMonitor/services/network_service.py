from typing import List, Dict, Any
from .base_service import BaseService
import logging

logger = logging.getLogger(__name__)

class NetworkService(BaseService):
    def _list_networks_sync(self) -> List[Dict[str, Any]]:
        """동기 네트워크 목록 조회"""
        networks = []
        for network in self.client.networks.list():
            info = network.attrs
            
            # 연결된 컨테이너 정보 파싱
            containers = []
            container_info = info.get("Containers", {}) or {}
            for cid, cdata in container_info.items():
                containers.append({
                    "id": cid[:12],
                    "name": cdata.get("Name", "unknown"),
                    "ipv4": cdata.get("IPv4Address", ""),
                    "ipv6": cdata.get("IPv6Address", ""),
                    "mac": cdata.get("MacAddress", "")
                })
            
            # IPAM 설정
            ipam = info.get("IPAM", {})
            ipam_config = ipam.get("Config", [])
            subnet = ""
            gateway = ""
            if ipam_config:
                subnet = ipam_config[0].get("Subnet", "")
                gateway = ipam_config[0].get("Gateway", "")
            
            networks.append({
                "id": info.get("Id", "")[:12],
                "name": info.get("Name", "unknown"),
                "driver": info.get("Driver", "unknown"),
                "scope": info.get("Scope", "local"),
                "internal": info.get("Internal", False),
                "subnet": subnet,
                "gateway": gateway,
                "containers": containers,
                "container_count": len(containers),
                "created": info.get("Created", "")
            })
        return networks

    async def list_networks(self) -> List[Dict[str, Any]]:
        """Docker 네트워크 목록 반환"""
        if not await self.ensure_connected():
            return []
        
        try:
            return await self.run_sync(self._list_networks_sync)
        except Exception as e:
            logger.error(f"Error listing networks: {e}")
            return []
