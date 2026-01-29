"""
Microservice API Tracking Module

This module provides comprehensive analysis of microservice architectures:
- OpenAPI/Swagger specification parsing
- gRPC proto file analysis  
- REST endpoint call relationship detection
- Service-to-service data flow visualization

Supports discovering API contracts and tracing inter-service communications.
"""

import os
import re
import json
import yaml
from typing import Dict, List, Optional, Set, Tuple, Any
from dataclasses import dataclass, field, asdict
from enum import Enum
from pathlib import Path
import logging

logger = logging.getLogger(__name__)


# =============================================================================
# Enums and Data Classes
# =============================================================================

class APIProtocol(str, Enum):
    """API protocol types."""
    REST = "rest"
    GRPC = "grpc"
    GRAPHQL = "graphql"
    WEBSOCKET = "websocket"
    UNKNOWN = "unknown"


class HTTPMethod(str, Enum):
    """HTTP methods."""
    GET = "GET"
    POST = "POST"
    PUT = "PUT"
    DELETE = "DELETE"
    PATCH = "PATCH"
    HEAD = "HEAD"
    OPTIONS = "OPTIONS"


class ServiceType(str, Enum):
    """Microservice types."""
    API_GATEWAY = "api_gateway"
    BACKEND = "backend"
    FRONTEND = "frontend"
    DATABASE = "database"
    MESSAGE_QUEUE = "message_queue"
    CACHE = "cache"
    AUTH = "auth"
    UNKNOWN = "unknown"


@dataclass
class APIParameter:
    """API parameter definition."""
    name: str
    location: str  # path, query, header, body, cookie
    param_type: str
    required: bool = False
    description: str = ""
    default: Any = None
    schema: Optional[Dict] = None


@dataclass
class APIEndpoint:
    """Single API endpoint definition."""
    path: str
    method: str
    operation_id: Optional[str] = None
    summary: str = ""
    description: str = ""
    tags: List[str] = field(default_factory=list)
    parameters: List[APIParameter] = field(default_factory=list)
    request_body: Optional[Dict] = None
    responses: Dict[str, Dict] = field(default_factory=dict)
    security: List[Dict] = field(default_factory=list)
    deprecated: bool = False
    
    def to_dict(self) -> Dict:
        return {
            'path': self.path,
            'method': self.method,
            'operation_id': self.operation_id,
            'summary': self.summary,
            'description': self.description,
            'tags': self.tags,
            'parameters': [asdict(p) for p in self.parameters],
            'request_body': self.request_body,
            'responses': self.responses,
            'security': self.security,
            'deprecated': self.deprecated
        }


@dataclass
class GRPCMethod:
    """gRPC service method definition."""
    name: str
    service: str
    input_type: str
    output_type: str
    client_streaming: bool = False
    server_streaming: bool = False
    description: str = ""
    
    def to_dict(self) -> Dict:
        return asdict(self)


@dataclass
class GRPCService:
    """gRPC service definition."""
    name: str
    package: str
    methods: List[GRPCMethod] = field(default_factory=list)
    file_path: str = ""
    
    def to_dict(self) -> Dict:
        return {
            'name': self.name,
            'package': self.package,
            'methods': [m.to_dict() for m in self.methods],
            'file_path': self.file_path
        }


@dataclass
class ServiceDefinition:
    """Microservice definition."""
    name: str
    service_type: ServiceType
    protocol: APIProtocol
    base_url: Optional[str] = None
    version: str = ""
    description: str = ""
    endpoints: List[APIEndpoint] = field(default_factory=list)
    grpc_services: List[GRPCService] = field(default_factory=list)
    dependencies: List[str] = field(default_factory=list)
    source_files: List[str] = field(default_factory=list)
    spec_file: Optional[str] = None
    
    def to_dict(self) -> Dict:
        return {
            'name': self.name,
            'service_type': self.service_type.value,
            'protocol': self.protocol.value,
            'base_url': self.base_url,
            'version': self.version,
            'description': self.description,
            'endpoints': [e.to_dict() for e in self.endpoints],
            'grpc_services': [s.to_dict() for s in self.grpc_services],
            'dependencies': self.dependencies,
            'source_files': self.source_files,
            'spec_file': self.spec_file
        }


@dataclass
class ServiceCall:
    """Inter-service API call."""
    caller_service: str
    callee_service: str
    endpoint_path: str
    method: str
    protocol: APIProtocol
    file_path: str
    line_number: int
    call_type: str = "sync"  # sync, async
    data_flow: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict:
        return {
            'caller_service': self.caller_service,
            'callee_service': self.callee_service,
            'endpoint_path': self.endpoint_path,
            'method': self.method,
            'protocol': self.protocol.value,
            'file_path': self.file_path,
            'line_number': self.line_number,
            'call_type': self.call_type,
            'data_flow': self.data_flow
        }


@dataclass
class ServiceGraph:
    """Service dependency graph for visualization."""
    nodes: List[Dict]
    edges: List[Dict]
    
    def to_dict(self) -> Dict:
        return {
            'nodes': self.nodes,
            'edges': self.edges
        }


# =============================================================================
# OpenAPI/Swagger Parser
# =============================================================================

class OpenAPIParser:
    """
    Parser for OpenAPI/Swagger specifications.
    
    Supports:
    - OpenAPI 3.0.x, 3.1.x
    - Swagger 2.0
    - YAML and JSON formats
    """
    
    def __init__(self):
        self.specs: Dict[str, Dict] = {}
    
    def parse_file(self, file_path: str) -> Optional[ServiceDefinition]:
        """Parse an OpenAPI/Swagger specification file."""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Try YAML first, then JSON
            try:
                spec = yaml.safe_load(content)
            except yaml.YAMLError:
                spec = json.loads(content)
            
            if not spec:
                return None
            
            return self._parse_spec(spec, file_path)
            
        except Exception as e:
            logger.error(f"Error parsing OpenAPI file {file_path}: {e}")
            return None
    
    def _parse_spec(self, spec: Dict, file_path: str) -> ServiceDefinition:
        """Parse OpenAPI/Swagger spec into ServiceDefinition."""
        # Detect version
        is_openapi3 = 'openapi' in spec
        is_swagger2 = 'swagger' in spec and spec.get('swagger', '').startswith('2')
        
        # Extract basic info
        info = spec.get('info', {})
        service_name = info.get('title', 'Unknown Service')
        version = info.get('version', '')
        description = info.get('description', '')
        
        # Extract base URL
        base_url = self._extract_base_url(spec, is_openapi3)
        
        # Extract endpoints
        endpoints = self._extract_endpoints(spec, is_openapi3)
        
        return ServiceDefinition(
            name=service_name,
            service_type=ServiceType.BACKEND,
            protocol=APIProtocol.REST,
            base_url=base_url,
            version=version,
            description=description,
            endpoints=endpoints,
            spec_file=file_path
        )
    
    def _extract_base_url(self, spec: Dict, is_openapi3: bool) -> str:
        """Extract base URL from spec."""
        if is_openapi3:
            servers = spec.get('servers', [])
            if servers:
                return servers[0].get('url', '')
        else:
            # Swagger 2.0
            host = spec.get('host', '')
            base_path = spec.get('basePath', '')
            schemes = spec.get('schemes', ['https'])
            if host:
                return f"{schemes[0]}://{host}{base_path}"
        return ''
    
    def _extract_endpoints(self, spec: Dict, is_openapi3: bool) -> List[APIEndpoint]:
        """Extract all endpoints from spec."""
        endpoints = []
        paths = spec.get('paths', {})
        
        for path, path_item in paths.items():
            if not isinstance(path_item, dict):
                continue
            
            for method in ['get', 'post', 'put', 'delete', 'patch', 'head', 'options']:
                if method not in path_item:
                    continue
                
                operation = path_item[method]
                endpoint = self._parse_operation(path, method.upper(), operation, is_openapi3)
                endpoints.append(endpoint)
        
        return endpoints
    
    def _parse_operation(self, path: str, method: str, operation: Dict, is_openapi3: bool) -> APIEndpoint:
        """Parse a single operation into APIEndpoint."""
        parameters = []
        
        # Parse parameters
        for param in operation.get('parameters', []):
            parameters.append(APIParameter(
                name=param.get('name', ''),
                location=param.get('in', 'query'),
                param_type=self._get_param_type(param, is_openapi3),
                required=param.get('required', False),
                description=param.get('description', ''),
                default=param.get('default'),
                schema=param.get('schema')
            ))
        
        # Parse request body (OpenAPI 3.x)
        request_body = None
        if is_openapi3 and 'requestBody' in operation:
            request_body = operation['requestBody']
        
        # Parse responses
        responses = {}
        for status_code, response in operation.get('responses', {}).items():
            responses[str(status_code)] = {
                'description': response.get('description', ''),
                'content': response.get('content', response.get('schema', {}))
            }
        
        return APIEndpoint(
            path=path,
            method=method,
            operation_id=operation.get('operationId'),
            summary=operation.get('summary', ''),
            description=operation.get('description', ''),
            tags=operation.get('tags', []),
            parameters=parameters,
            request_body=request_body,
            responses=responses,
            security=operation.get('security', []),
            deprecated=operation.get('deprecated', False)
        )
    
    def _get_param_type(self, param: Dict, is_openapi3: bool) -> str:
        """Extract parameter type."""
        if is_openapi3:
            schema = param.get('schema', {})
            return schema.get('type', 'string')
        else:
            return param.get('type', 'string')


# =============================================================================
# gRPC Proto Parser
# =============================================================================

class GRPCProtoParser:
    """
    Parser for gRPC Protocol Buffer (.proto) files.
    
    Extracts:
    - Service definitions
    - RPC methods
    - Message types
    - Streaming configurations
    """
    
    def __init__(self):
        self.messages: Dict[str, Dict] = {}
        self.enums: Dict[str, List[str]] = {}
    
    def parse_file(self, file_path: str) -> List[GRPCService]:
        """Parse a .proto file and extract services."""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            return self._parse_proto(content, file_path)
            
        except Exception as e:
            logger.error(f"Error parsing proto file {file_path}: {e}")
            return []
    
    def _parse_proto(self, content: str, file_path: str) -> List[GRPCService]:
        """Parse proto content and extract services."""
        services = []
        
        # Extract package name
        package_match = re.search(r'package\s+([\w.]+)\s*;', content)
        package = package_match.group(1) if package_match else ""
        
        # Extract service definitions
        service_pattern = r'service\s+(\w+)\s*\{([^}]*)\}'
        for match in re.finditer(service_pattern, content, re.DOTALL):
            service_name = match.group(1)
            service_body = match.group(2)
            
            methods = self._extract_methods(service_body, service_name)
            
            services.append(GRPCService(
                name=service_name,
                package=package,
                methods=methods,
                file_path=file_path
            ))
        
        # Extract messages for reference
        self._extract_messages(content)
        
        return services
    
    def _extract_methods(self, service_body: str, service_name: str) -> List[GRPCMethod]:
        """Extract RPC methods from service body."""
        methods = []
        
        # Pattern for RPC definition
        rpc_pattern = r'rpc\s+(\w+)\s*\(\s*(stream\s+)?(\w+)\s*\)\s*returns\s*\(\s*(stream\s+)?(\w+)\s*\)'
        
        for match in re.finditer(rpc_pattern, service_body):
            method_name = match.group(1)
            client_streaming = match.group(2) is not None
            input_type = match.group(3)
            server_streaming = match.group(4) is not None
            output_type = match.group(5)
            
            methods.append(GRPCMethod(
                name=method_name,
                service=service_name,
                input_type=input_type,
                output_type=output_type,
                client_streaming=client_streaming,
                server_streaming=server_streaming
            ))
        
        return methods
    
    def _extract_messages(self, content: str):
        """Extract message definitions."""
        message_pattern = r'message\s+(\w+)\s*\{([^}]*)\}'
        
        for match in re.finditer(message_pattern, content, re.DOTALL):
            message_name = match.group(1)
            message_body = match.group(2)
            
            fields = self._extract_fields(message_body)
            self.messages[message_name] = {'fields': fields}
    
    def _extract_fields(self, message_body: str) -> List[Dict]:
        """Extract fields from message body."""
        fields = []
        
        field_pattern = r'(repeated\s+)?(\w+)\s+(\w+)\s*=\s*(\d+)'
        
        for match in re.finditer(field_pattern, message_body):
            is_repeated = match.group(1) is not None
            field_type = match.group(2)
            field_name = match.group(3)
            field_number = int(match.group(4))
            
            fields.append({
                'name': field_name,
                'type': field_type,
                'number': field_number,
                'repeated': is_repeated
            })
        
        return fields


# =============================================================================
# Service Call Detector
# =============================================================================

class ServiceCallDetector:
    """
    Detects inter-service API calls in source code.
    
    Supports:
    - HTTP client calls (requests, axios, fetch, http)
    - gRPC client calls
    - Message queue publications
    """
    
    # HTTP client patterns by language
    HTTP_PATTERNS = {
        'python': [
            # requests library
            r'requests\.(get|post|put|delete|patch|head|options)\s*\(\s*["\']([^"\']+)["\']',
            # httpx
            r'httpx\.(get|post|put|delete|patch)\s*\(\s*["\']([^"\']+)["\']',
            # aiohttp
            r'session\.(get|post|put|delete|patch)\s*\(\s*["\']([^"\']+)["\']',
            # urllib
            r'urlopen\s*\(\s*["\']([^"\']+)["\']',
        ],
        'javascript': [
            # fetch API
            r'fetch\s*\(\s*[`"\']([^`"\']+)[`"\'](?:\s*,\s*\{[^}]*method\s*:\s*["\'](\w+)["\'])?',
            # axios
            r'axios\.(get|post|put|delete|patch)\s*\(\s*[`"\']([^`"\']+)[`"\']',
            r'axios\s*\(\s*\{[^}]*url\s*:\s*[`"\']([^`"\']+)[`"\']',
            # got
            r'got\.(get|post|put|delete|patch)\s*\(\s*[`"\']([^`"\']+)[`"\']',
        ],
        'java': [
            # RestTemplate
            r'restTemplate\.(getForObject|postForObject|exchange)\s*\(\s*["\']([^"\']+)["\']',
            # WebClient
            r'\.uri\s*\(\s*["\']([^"\']+)["\']',
            # HttpClient
            r'HttpRequest\.newBuilder\s*\(\s*\)\s*\.uri\s*\(.*?["\']([^"\']+)["\']',
        ],
        'go': [
            # net/http
            r'http\.(Get|Post|Head)\s*\(\s*["\']([^"\']+)["\']',
            # custom client
            r'client\.(Get|Post|Do)\s*\(\s*["\']([^"\']+)["\']',
        ]
    }
    
    # gRPC client patterns
    GRPC_PATTERNS = {
        'python': [
            r'(\w+)Stub\s*\(',
            r'grpc\.insecure_channel\s*\(\s*["\']([^"\']+)["\']',
        ],
        'javascript': [
            r'new\s+(\w+)Client\s*\(',
            r'grpc\.credentials\.createInsecure\s*\(',
        ],
        'java': [
            r'(\w+)Grpc\.newBlockingStub\s*\(',
            r'ManagedChannelBuilder\.forAddress\s*\(\s*["\']([^"\']+)["\']',
        ],
        'go': [
            r'pb\.New(\w+)Client\s*\(',
            r'grpc\.Dial\s*\(\s*["\']([^"\']+)["\']',
        ]
    }
    
    def __init__(self):
        self.calls: List[ServiceCall] = []
    
    def detect_calls(self, file_path: str, content: str, caller_service: str) -> List[ServiceCall]:
        """Detect all service calls in a file."""
        calls = []
        
        # Determine language
        ext = os.path.splitext(file_path)[1].lower()
        language = self._get_language(ext)
        
        if not language:
            return calls
        
        lines = content.split('\n')
        
        # Detect HTTP calls
        http_calls = self._detect_http_calls(content, lines, language, file_path, caller_service)
        calls.extend(http_calls)
        
        # Detect gRPC calls
        grpc_calls = self._detect_grpc_calls(content, lines, language, file_path, caller_service)
        calls.extend(grpc_calls)
        
        return calls
    
    def _get_language(self, ext: str) -> Optional[str]:
        """Get language from file extension."""
        ext_map = {
            '.py': 'python',
            '.js': 'javascript',
            '.ts': 'javascript',
            '.jsx': 'javascript',
            '.tsx': 'javascript',
            '.java': 'java',
            '.go': 'go',
        }
        return ext_map.get(ext)
    
    def _detect_http_calls(
        self, 
        content: str, 
        lines: List[str], 
        language: str, 
        file_path: str,
        caller_service: str
    ) -> List[ServiceCall]:
        """Detect HTTP client calls."""
        calls = []
        
        patterns = self.HTTP_PATTERNS.get(language, [])
        
        for pattern in patterns:
            for match in re.finditer(pattern, content, re.IGNORECASE):
                # Find line number
                pos = match.start()
                line_num = content[:pos].count('\n') + 1
                
                # Extract method and URL
                groups = match.groups()
                if len(groups) >= 2:
                    method = groups[0].upper() if groups[0] else 'GET'
                    url = groups[1]
                else:
                    method = 'GET'
                    url = groups[0] if groups else ''
                
                # Parse URL to identify service
                callee_service = self._identify_service_from_url(url)
                
                calls.append(ServiceCall(
                    caller_service=caller_service,
                    callee_service=callee_service,
                    endpoint_path=url,
                    method=method,
                    protocol=APIProtocol.REST,
                    file_path=file_path,
                    line_number=line_num
                ))
        
        return calls
    
    def _detect_grpc_calls(
        self,
        content: str,
        lines: List[str],
        language: str,
        file_path: str,
        caller_service: str
    ) -> List[ServiceCall]:
        """Detect gRPC client calls."""
        calls = []
        
        patterns = self.GRPC_PATTERNS.get(language, [])
        
        for pattern in patterns:
            for match in re.finditer(pattern, content, re.IGNORECASE):
                pos = match.start()
                line_num = content[:pos].count('\n') + 1
                
                groups = match.groups()
                service_name = groups[0] if groups else 'Unknown'
                
                calls.append(ServiceCall(
                    caller_service=caller_service,
                    callee_service=service_name,
                    endpoint_path=f"grpc://{service_name}",
                    method='RPC',
                    protocol=APIProtocol.GRPC,
                    file_path=file_path,
                    line_number=line_num
                ))
        
        return calls
    
    def _identify_service_from_url(self, url: str) -> str:
        """Try to identify service name from URL."""
        # Common patterns
        patterns = [
            r'https?://([^/:]+)',  # Extract hostname
            r'/api/(\w+)/',  # Extract from path
            r'(\w+-service)',  # Service naming convention
            r'(\w+)-api',  # API naming convention
        ]
        
        for pattern in patterns:
            match = re.search(pattern, url)
            if match:
                return match.group(1)
        
        return 'external'


# =============================================================================
# Microservice Analyzer
# =============================================================================

class MicroserviceAnalyzer:
    """
    Main analyzer for microservice architectures.
    
    Combines:
    - OpenAPI/Swagger parsing
    - gRPC proto parsing
    - Service call detection
    - Dependency graph generation
    """
    
    def __init__(self, project_path: str = None):
        self.project_path = project_path
        self.openapi_parser = OpenAPIParser()
        self.grpc_parser = GRPCProtoParser()
        self.call_detector = ServiceCallDetector()
        
        self.services: Dict[str, ServiceDefinition] = {}
        self.calls: List[ServiceCall] = []
        self.spec_files: List[str] = []
        self.proto_files: List[str] = []
    
    def analyze_project(self, project_path: str = None) -> Dict:
        """
        Analyze a microservice project.
        
        Returns comprehensive analysis including:
        - Discovered services
        - API endpoints
        - Service calls
        - Dependency graph
        """
        if project_path:
            self.project_path = project_path
        
        if not self.project_path or not os.path.exists(self.project_path):
            return {'error': 'Invalid project path'}
        
        # Reset state
        self.services = {}
        self.calls = []
        self.spec_files = []
        self.proto_files = []
        
        # Step 1: Discover spec files
        self._discover_spec_files()
        
        # Step 2: Parse OpenAPI specs
        for spec_file in self.spec_files:
            service = self.openapi_parser.parse_file(spec_file)
            if service:
                self.services[service.name] = service
        
        # Step 3: Parse proto files
        for proto_file in self.proto_files:
            grpc_services = self.grpc_parser.parse_file(proto_file)
            for grpc_svc in grpc_services:
                service_name = grpc_svc.name
                if service_name in self.services:
                    self.services[service_name].grpc_services.append(grpc_svc)
                else:
                    self.services[service_name] = ServiceDefinition(
                        name=service_name,
                        service_type=ServiceType.BACKEND,
                        protocol=APIProtocol.GRPC,
                        grpc_services=[grpc_svc]
                    )
        
        # Step 4: Detect service calls in source code
        self._detect_service_calls()
        
        # Step 5: Build dependency graph
        graph = self._build_service_graph()
        
        return {
            'project_path': self.project_path,
            'services': {name: svc.to_dict() for name, svc in self.services.items()},
            'service_calls': [call.to_dict() for call in self.calls],
            'graph': graph.to_dict(),
            'stats': {
                'total_services': len(self.services),
                'total_endpoints': sum(len(s.endpoints) for s in self.services.values()),
                'total_grpc_services': sum(len(s.grpc_services) for s in self.services.values()),
                'total_calls': len(self.calls),
                'spec_files': len(self.spec_files),
                'proto_files': len(self.proto_files)
            }
        }
    
    def _discover_spec_files(self):
        """Discover OpenAPI and proto files in project."""
        spec_patterns = ['openapi.yaml', 'openapi.yml', 'openapi.json',
                        'swagger.yaml', 'swagger.yml', 'swagger.json',
                        'api.yaml', 'api.yml', 'api.json']
        
        for root, dirs, files in os.walk(self.project_path):
            # Skip common non-relevant directories
            dirs[:] = [d for d in dirs if d not in [
                'node_modules', '__pycache__', '.git', 'venv', 'env', 
                'dist', 'build', 'target', '.idea', '.vscode'
            ]]
            
            for file in files:
                file_lower = file.lower()
                file_path = os.path.join(root, file)
                
                # Check for OpenAPI/Swagger
                if file_lower in spec_patterns or file_lower.endswith(('.yaml', '.yml', '.json')):
                    if self._is_openapi_file(file_path):
                        self.spec_files.append(file_path)
                
                # Check for proto files
                if file.endswith('.proto'):
                    self.proto_files.append(file_path)
    
    def _is_openapi_file(self, file_path: str) -> bool:
        """Check if file is an OpenAPI/Swagger spec."""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read(2000)  # Read first 2000 chars
            
            # Quick check for OpenAPI/Swagger markers
            markers = ['openapi:', 'swagger:', '"openapi":', '"swagger":',
                      'paths:', '"paths":']
            return any(marker in content for marker in markers)
        except:
            return False
    
    def _detect_service_calls(self):
        """Detect service calls in source files."""
        extensions = {'.py', '.js', '.ts', '.tsx', '.jsx', '.java', '.go'}
        
        # Determine caller service from directory structure
        def get_caller_service(file_path: str) -> str:
            rel_path = os.path.relpath(file_path, self.project_path)
            parts = rel_path.split(os.sep)
            
            # Look for service indicators
            for part in parts:
                if 'service' in part.lower() or part in self.services:
                    return part
            
            return parts[0] if parts else 'main'
        
        for root, dirs, files in os.walk(self.project_path):
            dirs[:] = [d for d in dirs if d not in [
                'node_modules', '__pycache__', '.git', 'venv', 'env',
                'dist', 'build', 'target'
            ]]
            
            for file in files:
                ext = os.path.splitext(file)[1].lower()
                if ext not in extensions:
                    continue
                
                file_path = os.path.join(root, file)
                caller_service = get_caller_service(file_path)
                
                try:
                    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                        content = f.read()
                    
                    calls = self.call_detector.detect_calls(file_path, content, caller_service)
                    self.calls.extend(calls)
                except Exception as e:
                    logger.warning(f"Error reading {file_path}: {e}")
    
    def _build_service_graph(self) -> ServiceGraph:
        """Build a service dependency graph for visualization."""
        nodes = []
        edges = []
        node_ids = set()
        edge_set = set()
        
        # Add services as nodes
        for name, service in self.services.items():
            nodes.append({
                'id': name,
                'label': name,
                'type': service.service_type.value,
                'protocol': service.protocol.value,
                'endpoints': len(service.endpoints),
                'grpc_methods': sum(len(s.methods) for s in service.grpc_services)
            })
            node_ids.add(name)
        
        # Add call targets as nodes if not already present
        for call in self.calls:
            if call.callee_service not in node_ids:
                nodes.append({
                    'id': call.callee_service,
                    'label': call.callee_service,
                    'type': 'external',
                    'protocol': call.protocol.value,
                    'endpoints': 0,
                    'grpc_methods': 0
                })
                node_ids.add(call.callee_service)
            
            if call.caller_service not in node_ids:
                nodes.append({
                    'id': call.caller_service,
                    'label': call.caller_service,
                    'type': 'internal',
                    'protocol': 'unknown',
                    'endpoints': 0,
                    'grpc_methods': 0
                })
                node_ids.add(call.caller_service)
        
        # Add edges from calls
        for call in self.calls:
            edge_key = (call.caller_service, call.callee_service, call.method)
            
            if edge_key not in edge_set:
                edges.append({
                    'source': call.caller_service,
                    'target': call.callee_service,
                    'method': call.method,
                    'protocol': call.protocol.value,
                    'label': f"{call.method}"
                })
                edge_set.add(edge_key)
        
        return ServiceGraph(nodes=nodes, edges=edges)
    
    def get_service(self, service_name: str) -> Optional[Dict]:
        """Get details of a specific service."""
        if service_name in self.services:
            return self.services[service_name].to_dict()
        return None
    
    def get_service_calls(self, service_name: str = None) -> List[Dict]:
        """Get service calls, optionally filtered by service."""
        if service_name:
            filtered = [c for c in self.calls 
                       if c.caller_service == service_name or c.callee_service == service_name]
            return [c.to_dict() for c in filtered]
        return [c.to_dict() for c in self.calls]
    
    def get_data_flow(self, source_service: str, target_service: str) -> List[Dict]:
        """Get data flow between two services."""
        flows = []
        
        for call in self.calls:
            if call.caller_service == source_service and call.callee_service == target_service:
                flows.append(call.to_dict())
        
        return flows


# =============================================================================
# Convenience Functions
# =============================================================================

def analyze_microservices(project_path: str) -> Dict:
    """Analyze microservices in a project."""
    analyzer = MicroserviceAnalyzer(project_path)
    return analyzer.analyze_project()


def parse_openapi(file_path: str) -> Optional[Dict]:
    """Parse a single OpenAPI file."""
    parser = OpenAPIParser()
    service = parser.parse_file(file_path)
    return service.to_dict() if service else None


def parse_proto(file_path: str) -> List[Dict]:
    """Parse a single proto file."""
    parser = GRPCProtoParser()
    services = parser.parse_file(file_path)
    return [s.to_dict() for s in services]
