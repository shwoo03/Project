from .container_service import ContainerService
from .image_service import ImageService
from .network_service import NetworkService
from .volume_service import VolumeService
from .exec_service import ExecService
from .compose_service import ComposeService
from .system_service import SystemService

# 서비스 인스턴스 (싱글톤)
container_service = ContainerService()
image_service = ImageService()
network_service = NetworkService()
volume_service = VolumeService()
exec_service = ExecService()
compose_service = ComposeService()
system_service = SystemService()

_all_services = [container_service, image_service, network_service, volume_service, exec_service, system_service]
# Note: compose_service는 CLI 기반이라 BaseService를 상속하지 않으므로 _all_services에 포함하지 않음


def init_services(client):
    """모든 서비스에 공유 Docker 클라이언트 주입"""
    from core.connection import get_executor
    executor = get_executor()
    for svc in _all_services:
        svc.set_client(client, executor)


__all__ = [
    'container_service',
    'image_service',
    'network_service',
    'volume_service',
    'exec_service',
    'compose_service',
    'system_service',
    'init_services',
]
