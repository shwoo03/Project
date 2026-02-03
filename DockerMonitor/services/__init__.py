from .container_service import ContainerService
from .image_service import ImageService
from .network_service import NetworkService
from .volume_service import VolumeService
from .exec_service import ExecService

# 서비스 인스턴스 초기화 (싱글톤처럼 사용)
container_service = ContainerService()
image_service = ImageService()
network_service = NetworkService()
volume_service = VolumeService()
exec_service = ExecService()

__all__ = [
    'container_service',
    'image_service', 
    'network_service', 
    'volume_service',
    'exec_service'
]
