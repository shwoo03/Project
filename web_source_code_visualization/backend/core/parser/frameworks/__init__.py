"""
Framework-specific extractors for Python web frameworks.
Each extractor handles route detection, input extraction, and framework-specific patterns.
"""

from .flask_extractor import FlaskExtractor
from .fastapi_extractor import FastAPIExtractor
from .base_framework import BaseFrameworkExtractor, FrameworkRegistry, RouteInfo, InputInfo

__all__ = [
    'BaseFrameworkExtractor',
    'FrameworkRegistry',
    'RouteInfo',
    'InputInfo',
    'FlaskExtractor', 
    'FastAPIExtractor',
]
