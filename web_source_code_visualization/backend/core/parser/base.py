from abc import ABC, abstractmethod
from typing import List
from models import EndpointNodes

class BaseParser(ABC):
    @abstractmethod
    def can_parse(self, file_path: str) -> bool:
        """Check if the parser supports the given file."""
        pass

    @abstractmethod
    def parse(self, file_path: str, content: str) -> List[EndpointNodes]:
        """Parse source code and return a list of endpoints."""
        pass
