"""
Base class for framework-specific extractors.
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
import re


@dataclass
class RouteInfo:
    """Extracted route information."""
    path: str
    method: str
    is_route: bool = True
    path_params: List[str] = None
    
    def __post_init__(self):
        if self.path_params is None:
            self.path_params = []


@dataclass
class InputInfo:
    """Extracted input/parameter information."""
    name: str
    source: str  # GET, POST, COOKIE, HEADER, FILE, PATH, BODY_JSON, BODY_RAW
    type: str = "UserInput"
    line: int = 0


class BaseFrameworkExtractor(ABC):
    """
    Abstract base class for framework-specific extractors.
    
    Each framework extractor is responsible for:
    1. Detecting if a decorator is a route decorator
    2. Parsing route path and method
    3. Extracting inputs from request objects
    """
    
    @property
    @abstractmethod
    def name(self) -> str:
        """Framework name for logging/identification."""
        pass
    
    @abstractmethod
    def is_route_decorator(self, decorator_text: str) -> bool:
        """Check if the decorator text represents a route decorator."""
        pass
    
    @abstractmethod
    def parse_route(self, decorator_text: str) -> RouteInfo:
        """
        Parse route information from decorator text.
        
        Returns:
            RouteInfo with path, method, and path_params
        """
        pass
    
    @abstractmethod
    def extract_input_from_call(self, node, get_text_func) -> Optional[InputInfo]:
        """
        Extract input information from a function call node.
        
        Args:
            node: Tree-sitter call node
            get_text_func: Function to get text from node
            
        Returns:
            InputInfo if this is an input call, None otherwise
        """
        pass
    
    @abstractmethod
    def extract_input_from_subscript(self, node, get_text_func) -> Optional[InputInfo]:
        """
        Extract input information from a subscript access node.
        
        Args:
            node: Tree-sitter subscript node
            get_text_func: Function to get text from node
            
        Returns:
            InputInfo if this is an input access, None otherwise
        """
        pass
    
    def extract_path_params(self, path_text: str) -> List[str]:
        """
        Extract path parameters from route path.
        Override in subclass for framework-specific patterns.
        """
        return []


class FrameworkRegistry:
    """Registry for framework extractors."""
    
    _extractors: List[BaseFrameworkExtractor] = []
    
    @classmethod
    def register(cls, extractor: BaseFrameworkExtractor):
        """Register a framework extractor."""
        cls._extractors.append(extractor)
    
    @classmethod
    def get_extractors(cls) -> List[BaseFrameworkExtractor]:
        """Get all registered extractors."""
        return cls._extractors.copy()
    
    @classmethod
    def find_route_extractor(cls, decorator_text: str) -> Optional[BaseFrameworkExtractor]:
        """Find the extractor that can handle this decorator."""
        for extractor in cls._extractors:
            if extractor.is_route_decorator(decorator_text):
                return extractor
        return None
