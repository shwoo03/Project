"""
Docker Monitor 커스텀 예외 클래스 정의
"""


class DockerMonitorException(Exception):
    """기본 예외 클래스"""
    def __init__(self, message: str = "Docker Monitor 에러가 발생했습니다", code: str = "DOCKER_MONITOR_ERROR"):
        self.message = message
        self.code = code
        super().__init__(self.message)


class DockerConnectionError(DockerMonitorException):
    """Docker 데몬 연결 실패"""
    def __init__(self, message: str = "Docker 데몬에 연결할 수 없습니다"):
        super().__init__(message=message, code="DOCKER_CONNECTION_ERROR")


class ContainerNotFoundError(DockerMonitorException):
    """컨테이너를 찾을 수 없음"""
    def __init__(self, container_id: str):
        super().__init__(
            message=f"컨테이너를 찾을 수 없습니다: {container_id}",
            code="CONTAINER_NOT_FOUND"
        )
        self.container_id = container_id


class ImageNotFoundError(DockerMonitorException):
    """이미지를 찾을 수 없음"""
    def __init__(self, image_id: str):
        super().__init__(
            message=f"이미지를 찾을 수 없습니다: {image_id}",
            code="IMAGE_NOT_FOUND"
        )
        self.image_id = image_id


class VolumeNotFoundError(DockerMonitorException):
    """볼륨을 찾을 수 없음"""
    def __init__(self, volume_name: str):
        super().__init__(
            message=f"볼륨을 찾을 수 없습니다: {volume_name}",
            code="VOLUME_NOT_FOUND"
        )
        self.volume_name = volume_name


class NetworkNotFoundError(DockerMonitorException):
    """네트워크를 찾을 수 없음"""
    def __init__(self, network_id: str):
        super().__init__(
            message=f"네트워크를 찾을 수 없습니다: {network_id}",
            code="NETWORK_NOT_FOUND"
        )
        self.network_id = network_id


class InvalidActionError(DockerMonitorException):
    """유효하지 않은 액션"""
    def __init__(self, action: str, valid_actions: list[str] = None):
        valid = valid_actions or ["start", "stop", "restart"]
        super().__init__(
            message=f"유효하지 않은 액션입니다: {action}. 사용 가능: {', '.join(valid)}",
            code="INVALID_ACTION"
        )
        self.action = action
        self.valid_actions = valid


class ContainerActionError(DockerMonitorException):
    """컨테이너 액션 실행 실패"""
    def __init__(self, container_id: str, action: str, reason: str = None):
        message = f"컨테이너 {action} 실패: {container_id}"
        if reason:
            message += f" - {reason}"
        super().__init__(message=message, code="CONTAINER_ACTION_ERROR")
        self.container_id = container_id
        self.action = action


class ImageDeleteError(DockerMonitorException):
    """이미지 삭제 실패"""
    def __init__(self, image_id: str, reason: str = None):
        message = f"이미지 삭제 실패: {image_id}"
        if reason:
            message += f" - {reason}"
        super().__init__(message=message, code="IMAGE_DELETE_ERROR")
        self.image_id = image_id


class VolumeOperationError(DockerMonitorException):
    """볼륨 작업 실패"""
    def __init__(self, operation: str, volume_name: str, reason: str = None):
        message = f"볼륨 {operation} 실패: {volume_name}"
        if reason:
            message += f" - {reason}"
        super().__init__(message=message, code="VOLUME_OPERATION_ERROR")
        self.operation = operation
        self.volume_name = volume_name
