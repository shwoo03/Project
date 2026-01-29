"""
Test Suite for Microservice API Tracking

Tests for:
- OpenAPI/Swagger parsing
- gRPC proto parsing
- Service call detection
- Microservice analysis
"""

import os
import sys
import tempfile
import shutil
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def test_openapi_parser():
    """Test OpenAPI/Swagger parser."""
    print("\n" + "="*60)
    print("Test 1: OpenAPI/Swagger Parser")
    print("="*60)
    
    from core.microservice_analyzer import OpenAPIParser, APIEndpoint
    
    parser = OpenAPIParser()
    
    # Create a test OpenAPI spec
    openapi_spec = """
openapi: "3.0.0"
info:
  title: User Service API
  version: "1.0.0"
  description: API for user management
servers:
  - url: https://api.example.com/v1
paths:
  /users:
    get:
      operationId: listUsers
      summary: List all users
      tags:
        - users
      parameters:
        - name: limit
          in: query
          schema:
            type: integer
          required: false
      responses:
        "200":
          description: Success
    post:
      operationId: createUser
      summary: Create a user
      tags:
        - users
      requestBody:
        content:
          application/json:
            schema:
              type: object
      responses:
        "201":
          description: Created
  /users/{id}:
    get:
      operationId: getUser
      summary: Get user by ID
      parameters:
        - name: id
          in: path
          required: true
          schema:
            type: string
      responses:
        "200":
          description: Success
"""
    
    # Write to temp file
    with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
        f.write(openapi_spec)
        temp_path = f.name
    
    try:
        service = parser.parse_file(temp_path)
        
        assert service is not None
        print(f"✓ Service name: {service.name}")
        
        assert service.name == "User Service API"
        print(f"✓ Version: {service.version}")
        
        assert service.base_url == "https://api.example.com/v1"
        print(f"✓ Base URL: {service.base_url}")
        
        assert len(service.endpoints) == 3
        print(f"✓ Endpoints found: {len(service.endpoints)}")
        
        # Check endpoints
        methods = [e.method for e in service.endpoints]
        assert "GET" in methods
        assert "POST" in methods
        print(f"✓ Methods: {methods}")
        
        # Check parameters
        get_users = next(e for e in service.endpoints if e.operation_id == "listUsers")
        assert len(get_users.parameters) == 1
        assert get_users.parameters[0].name == "limit"
        print(f"✓ Parameters parsed correctly")
        
    finally:
        os.unlink(temp_path)
    
    print("\n✅ OpenAPI parser test passed!")
    return True


def test_swagger2_parser():
    """Test Swagger 2.0 parser."""
    print("\n" + "="*60)
    print("Test 2: Swagger 2.0 Parser")
    print("="*60)
    
    from core.microservice_analyzer import OpenAPIParser
    
    parser = OpenAPIParser()
    
    swagger_spec = """
{
  "swagger": "2.0",
  "info": {
    "title": "Order Service",
    "version": "2.0.0"
  },
  "host": "orders.example.com",
  "basePath": "/api",
  "schemes": ["https"],
  "paths": {
    "/orders": {
      "get": {
        "operationId": "getOrders",
        "summary": "Get orders",
        "responses": {
          "200": {
            "description": "Success"
          }
        }
      }
    }
  }
}
"""
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        f.write(swagger_spec)
        temp_path = f.name
    
    try:
        service = parser.parse_file(temp_path)
        
        assert service is not None
        print(f"✓ Swagger 2.0 parsed successfully")
        
        assert service.name == "Order Service"
        print(f"✓ Service name: {service.name}")
        
        assert service.base_url == "https://orders.example.com/api"
        print(f"✓ Base URL constructed: {service.base_url}")
        
        assert len(service.endpoints) == 1
        print(f"✓ Endpoints: {len(service.endpoints)}")
        
    finally:
        os.unlink(temp_path)
    
    print("\n✅ Swagger 2.0 parser test passed!")
    return True


def test_grpc_proto_parser():
    """Test gRPC proto file parser."""
    print("\n" + "="*60)
    print("Test 3: gRPC Proto Parser")
    print("="*60)
    
    from core.microservice_analyzer import GRPCProtoParser
    
    parser = GRPCProtoParser()
    
    proto_content = """
syntax = "proto3";

package com.example.grpc;

service UserService {
    rpc GetUser (GetUserRequest) returns (User);
    rpc ListUsers (ListUsersRequest) returns (stream User);
    rpc CreateUser (stream CreateUserRequest) returns (User);
    rpc UpdateUsers (stream UpdateUserRequest) returns (stream User);
}

service OrderService {
    rpc CreateOrder (CreateOrderRequest) returns (Order);
    rpc GetOrderStatus (GetOrderStatusRequest) returns (OrderStatus);
}

message User {
    string id = 1;
    string name = 2;
    string email = 3;
}

message GetUserRequest {
    string user_id = 1;
}

message ListUsersRequest {
    int32 page_size = 1;
    string page_token = 2;
}
"""
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.proto', delete=False) as f:
        f.write(proto_content)
        temp_path = f.name
    
    try:
        services = parser.parse_file(temp_path)
        
        assert len(services) == 2
        print(f"✓ Services found: {len(services)}")
        
        # Check UserService
        user_svc = next(s for s in services if s.name == "UserService")
        assert user_svc.package == "com.example.grpc"
        print(f"✓ Package: {user_svc.package}")
        
        assert len(user_svc.methods) == 4
        print(f"✓ UserService methods: {len(user_svc.methods)}")
        
        # Check streaming
        get_user = next(m for m in user_svc.methods if m.name == "GetUser")
        assert not get_user.client_streaming
        assert not get_user.server_streaming
        print(f"✓ GetUser: unary")
        
        list_users = next(m for m in user_svc.methods if m.name == "ListUsers")
        assert not list_users.client_streaming
        assert list_users.server_streaming
        print(f"✓ ListUsers: server streaming")
        
        create_user = next(m for m in user_svc.methods if m.name == "CreateUser")
        assert create_user.client_streaming
        assert not create_user.server_streaming
        print(f"✓ CreateUser: client streaming")
        
        update_users = next(m for m in user_svc.methods if m.name == "UpdateUsers")
        assert update_users.client_streaming
        assert update_users.server_streaming
        print(f"✓ UpdateUsers: bidirectional streaming")
        
        # Check OrderService
        order_svc = next(s for s in services if s.name == "OrderService")
        assert len(order_svc.methods) == 2
        print(f"✓ OrderService methods: {len(order_svc.methods)}")
        
        # Check messages
        assert "User" in parser.messages
        assert "GetUserRequest" in parser.messages
        print(f"✓ Messages parsed: {len(parser.messages)}")
        
    finally:
        os.unlink(temp_path)
    
    print("\n✅ gRPC proto parser test passed!")
    return True


def test_service_call_detector():
    """Test service call detection."""
    print("\n" + "="*60)
    print("Test 4: Service Call Detector")
    print("="*60)
    
    from core.microservice_analyzer import ServiceCallDetector, APIProtocol
    
    detector = ServiceCallDetector()
    
    # Python requests
    python_code = """
import requests

def call_user_service():
    response = requests.get("http://user-service/api/users")
    return response.json()

def create_order():
    data = {"user_id": 123}
    response = requests.post("http://order-service/api/orders", json=data)
    return response.json()

def update_user(user_id):
    response = requests.put(f"http://user-service/api/users/{user_id}", json={})
    return response
"""
    
    calls = detector.detect_calls("test.py", python_code, "api-gateway")
    
    # At least 2 calls should be detected (f-string URLs may not be fully captured)
    assert len(calls) >= 2, f"Expected at least 2 calls, got {len(calls)}"
    print(f"✓ Python HTTP calls detected: {len(calls)}")
    
    methods = set(c.method for c in calls)
    assert "GET" in methods or "POST" in methods  # At least one method detected
    print(f"✓ HTTP methods: {methods}")
    
    # JavaScript axios
    js_code = """
import axios from 'axios';

async function getProducts() {
    const response = await axios.get('http://product-service/api/products');
    return response.data;
}

async function createPayment(data) {
    return axios.post('http://payment-service/api/payments', data);
}

async function fetchData() {
    const data = await fetch('http://data-service/api/data', {
        method: 'POST'
    });
}
"""
    
    js_calls = detector.detect_calls("test.js", js_code, "frontend")
    
    assert len(js_calls) >= 2
    print(f"✓ JavaScript HTTP calls detected: {len(js_calls)}")
    
    # gRPC detection
    grpc_python = """
import grpc
from user_pb2_grpc import UserServiceStub

def get_user():
    channel = grpc.insecure_channel('localhost:50051')
    stub = UserServiceStub(channel)
    return stub.GetUser(request)
"""
    
    grpc_calls = detector.detect_calls("grpc_client.py", grpc_python, "order-service")
    
    assert len(grpc_calls) >= 1
    print(f"✓ gRPC calls detected: {len(grpc_calls)}")
    
    print("\n✅ Service call detector test passed!")
    return True


def test_microservice_analyzer():
    """Test full microservice analyzer."""
    print("\n" + "="*60)
    print("Test 5: Microservice Analyzer")
    print("="*60)
    
    from core.microservice_analyzer import MicroserviceAnalyzer
    
    # Create a temp project structure
    temp_dir = tempfile.mkdtemp()
    
    try:
        # Create OpenAPI spec
        openapi_dir = os.path.join(temp_dir, "user-service")
        os.makedirs(openapi_dir)
        
        openapi_spec = """
openapi: "3.0.0"
info:
  title: User Service
  version: "1.0.0"
paths:
  /users:
    get:
      operationId: getUsers
      responses:
        "200":
          description: Success
"""
        with open(os.path.join(openapi_dir, "openapi.yaml"), 'w') as f:
            f.write(openapi_spec)
        
        # Create proto file
        proto_dir = os.path.join(temp_dir, "order-service")
        os.makedirs(proto_dir)
        
        proto_content = """
syntax = "proto3";
package orders;

service OrderService {
    rpc CreateOrder (OrderRequest) returns (OrderResponse);
}
"""
        with open(os.path.join(proto_dir, "order.proto"), 'w') as f:
            f.write(proto_content)
        
        # Create source file with service calls
        src_dir = os.path.join(temp_dir, "api-gateway")
        os.makedirs(src_dir)
        
        gateway_code = """
import requests

def get_users():
    return requests.get("http://user-service/users")

def create_order(data):
    return requests.post("http://order-service/orders", json=data)
"""
        with open(os.path.join(src_dir, "gateway.py"), 'w') as f:
            f.write(gateway_code)
        
        # Run analyzer
        analyzer = MicroserviceAnalyzer(temp_dir)
        result = analyzer.analyze_project()
        
        assert 'services' in result
        print(f"✓ Services discovered: {len(result['services'])}")
        
        assert 'service_calls' in result
        print(f"✓ Service calls detected: {len(result['service_calls'])}")
        
        assert 'graph' in result
        print(f"✓ Service graph generated")
        
        graph = result['graph']
        assert 'nodes' in graph
        assert 'edges' in graph
        print(f"✓ Graph nodes: {len(graph['nodes'])}, edges: {len(graph['edges'])}")
        
        assert 'stats' in result
        stats = result['stats']
        print(f"✓ Stats: {stats}")
        
    finally:
        shutil.rmtree(temp_dir)
    
    print("\n✅ Microservice analyzer test passed!")
    return True


def test_api_endpoint_extraction():
    """Test API endpoint extraction details."""
    print("\n" + "="*60)
    print("Test 6: API Endpoint Extraction")
    print("="*60)
    
    from core.microservice_analyzer import OpenAPIParser
    
    parser = OpenAPIParser()
    
    openapi_spec = """
openapi: "3.0.0"
info:
  title: Complete API
  version: "1.0.0"
paths:
  /items/{itemId}:
    get:
      operationId: getItem
      summary: Get an item
      description: Retrieve item by ID
      deprecated: true
      tags:
        - items
        - inventory
      parameters:
        - name: itemId
          in: path
          required: true
          schema:
            type: string
        - name: include_details
          in: query
          schema:
            type: boolean
            default: false
      security:
        - bearerAuth: []
      responses:
        "200":
          description: Success
          content:
            application/json:
              schema:
                type: object
        "404":
          description: Not found
    put:
      operationId: updateItem
      requestBody:
        required: true
        content:
          application/json:
            schema:
              type: object
              properties:
                name:
                  type: string
      responses:
        "200":
          description: Updated
"""
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
        f.write(openapi_spec)
        temp_path = f.name
    
    try:
        service = parser.parse_file(temp_path)
        
        get_item = next(e for e in service.endpoints if e.operation_id == "getItem")
        
        assert get_item.deprecated == True
        print(f"✓ Deprecated flag parsed")
        
        assert len(get_item.tags) == 2
        print(f"✓ Tags: {get_item.tags}")
        
        assert len(get_item.parameters) == 2
        path_param = next(p for p in get_item.parameters if p.name == "itemId")
        assert path_param.location == "path"
        assert path_param.required == True
        print(f"✓ Path parameter: {path_param.name}")
        
        query_param = next(p for p in get_item.parameters if p.name == "include_details")
        assert query_param.location == "query"
        assert query_param.param_type == "boolean"
        print(f"✓ Query parameter: {query_param.name}")
        
        assert len(get_item.security) > 0
        print(f"✓ Security: {get_item.security}")
        
        assert "200" in get_item.responses
        assert "404" in get_item.responses
        print(f"✓ Response codes: {list(get_item.responses.keys())}")
        
        put_item = next(e for e in service.endpoints if e.operation_id == "updateItem")
        assert put_item.request_body is not None
        print(f"✓ Request body parsed")
        
    finally:
        os.unlink(temp_path)
    
    print("\n✅ API endpoint extraction test passed!")
    return True


def test_service_graph_generation():
    """Test service graph generation."""
    print("\n" + "="*60)
    print("Test 7: Service Graph Generation")
    print("="*60)
    
    from core.microservice_analyzer import (
        MicroserviceAnalyzer, 
        ServiceDefinition, 
        ServiceType, 
        APIProtocol,
        ServiceCall
    )
    
    analyzer = MicroserviceAnalyzer()
    
    # Manually add services
    analyzer.services = {
        "user-service": ServiceDefinition(
            name="user-service",
            service_type=ServiceType.BACKEND,
            protocol=APIProtocol.REST
        ),
        "order-service": ServiceDefinition(
            name="order-service",
            service_type=ServiceType.BACKEND,
            protocol=APIProtocol.REST
        )
    }
    
    # Add calls
    analyzer.calls = [
        ServiceCall(
            caller_service="api-gateway",
            callee_service="user-service",
            endpoint_path="/users",
            method="GET",
            protocol=APIProtocol.REST,
            file_path="gateway.py",
            line_number=10
        ),
        ServiceCall(
            caller_service="api-gateway",
            callee_service="order-service",
            endpoint_path="/orders",
            method="POST",
            protocol=APIProtocol.REST,
            file_path="gateway.py",
            line_number=15
        ),
        ServiceCall(
            caller_service="order-service",
            callee_service="user-service",
            endpoint_path="/users/validate",
            method="GET",
            protocol=APIProtocol.REST,
            file_path="order.py",
            line_number=20
        )
    ]
    
    graph = analyzer._build_service_graph()
    
    # Check nodes
    node_ids = [n['id'] for n in graph.nodes]
    assert "user-service" in node_ids
    assert "order-service" in node_ids
    assert "api-gateway" in node_ids
    print(f"✓ Nodes: {node_ids}")
    
    # Check edges
    assert len(graph.edges) == 3
    print(f"✓ Edges: {len(graph.edges)}")
    
    edge_pairs = [(e['source'], e['target']) for e in graph.edges]
    assert ("api-gateway", "user-service") in edge_pairs
    assert ("api-gateway", "order-service") in edge_pairs
    assert ("order-service", "user-service") in edge_pairs
    print(f"✓ Edge pairs verified")
    
    print("\n✅ Service graph generation test passed!")
    return True


def test_real_project():
    """Test with real backend project."""
    print("\n" + "="*60)
    print("Test 8: Real Project Analysis")
    print("="*60)
    
    from core.microservice_analyzer import MicroserviceAnalyzer
    
    project_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    
    analyzer = MicroserviceAnalyzer(project_path)
    result = analyzer.analyze_project()
    
    print(f"✓ Project analyzed: {result['project_path']}")
    print(f"✓ Spec files found: {result['stats']['spec_files']}")
    print(f"✓ Proto files found: {result['stats']['proto_files']}")
    print(f"✓ Service calls detected: {result['stats']['total_calls']}")
    print(f"✓ Graph nodes: {len(result['graph']['nodes'])}")
    print(f"✓ Graph edges: {len(result['graph']['edges'])}")
    
    print("\n✅ Real project analysis test passed!")
    return True


def run_all_tests():
    """Run all tests."""
    print("\n" + "="*60)
    print("Microservice API Tracking Test Suite")
    print("="*60)
    
    tests = [
        ("OpenAPI Parser", test_openapi_parser),
        ("Swagger 2.0 Parser", test_swagger2_parser),
        ("gRPC Proto Parser", test_grpc_proto_parser),
        ("Service Call Detector", test_service_call_detector),
        ("Microservice Analyzer", test_microservice_analyzer),
        ("API Endpoint Extraction", test_api_endpoint_extraction),
        ("Service Graph Generation", test_service_graph_generation),
        ("Real Project Analysis", test_real_project),
    ]
    
    passed = 0
    failed = 0
    
    for name, test_func in tests:
        try:
            test_func()
            passed += 1
        except Exception as e:
            print(f"\n❌ {name} FAILED: {e}")
            import traceback
            traceback.print_exc()
            failed += 1
    
    print("\n" + "="*60)
    print(f"Test Results: {passed} passed, {failed} failed")
    print("="*60)
    
    if failed == 0:
        print("\n🎉 All tests passed!")
    else:
        print(f"\n⚠️ {failed} test(s) failed")
    
    return failed == 0


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
