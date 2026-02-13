from .container_service import ContainerService
from .image_service import ImageService
from .network_service import NetworkService
from .volume_service import VolumeService
from .exec_service import ExecService

# 서비스 인스턴스 (싱글톤)
container_service = ContainerService()
image_service = ImageService()
network_service = NetworkService()
volume_service = VolumeService()
exec_service = ExecService()

_all_services = [container_service, image_service, network_service, volume_service, exec_service]


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
    'init_services',
]
