# Project Status: Web Source Code Visualization Tool

This document summarizes the current state of the project to assist future AI sessions in picking up the work immediately.

**Last Updated**: 2026-01-30  
**Version**: 0.15.0  
**Roadmap**: See [ROADMAP3.md](ROADMAP3.md) for future development plans

## 1. Project Overview
A comprehensive security analysis tool that visualizes the call graph, data flow, and security vulnerabilities of web applications across multiple languages and frameworks.

- **Backend**: FastAPI (`backend/`), Python Tree-sitter for parsing
- **Frontend**: Next.js 16 + ReactFlow + TailwindCSS (`frontend/`)
- **Supported Languages**: Python, JavaScript/TypeScript, PHP, Java, Go

## 2. Core Features Implemented

### 2.1 Project Structure Visualization
- Parses source files to identify Routes, Functions, Inputs, and Calls
- Visualizes as a DAG (Directed Acyclic Graph) using `dagre` layout
- Supports hierarchical node expansion/collapse

### 2.2 Multi-Language Parser Support
| Language | Framework Support |
|----------|-------------------|
| **Python** | Flask, FastAPI, Django (with DRF) |
| **JavaScript** | Express.js, DOM API, React |
| **TypeScript** | Next.js, React, Express |
| **PHP** | Laravel, Symfony |
| **Java** | Spring Boot, Servlet |
| **Go** | Gin, net/http |

### 2.3 Security Analysis Features
- **Taint Analysis**: Tracks data flow from user inputs (sources) to dangerous functions (sinks)
- **Taint Flow Visualization**: Red dashed animated edges showing input→sink paths
- **Sink Detection**: Identifies dangerous functions (eval, exec, SQL queries, etc.)
- **Semgrep Integration**: External security scanner with custom rules support
- **AI-Powered Analysis**: Groq LLM integration for code security review
- **Inter-Procedural Taint Analysis** ✨ NEW: Tracks taint across function calls

### 2.4 Call Graph Analysis
- **Function-to-function call tracking**: Who calls whom?
- **Entry point detection**: Route handlers, main functions
- **Sink identification**: Functions that reach dangerous operations
- **Path finding**: Find all paths from entry points to sinks
- **Metrics**: Fan-in, fan-out, hub detection, orphan detection

### 2.5 Parallel Analysis Engine
- **File**: `backend/core/parallel_analyzer.py`
- **Auto mode selection**: Sequential for <100 files, Parallel for ≥100 files
- **ThreadPoolExecutor**: Concurrent file processing with CPU-based worker count
- **Statistics tracking**: Parse time, success/failure rates, language distribution

### 2.6 Analysis Caching System
- **File**: `backend/core/analysis_cache.py`
- **SQLite-based**: Persistent cache with file hash validation
- **Incremental analysis**: Only re-parse changed files
- **Performance**: 23x speedup on repeated analysis (95.7% time saved)

### 2.7 UI Virtualization
- **Virtualized File Tree**: Handles 10,000+ files with smooth scrolling
- **Progressive Node Loading**: Loads large graphs in batches to prevent UI freeze
- **Performance Monitor**: Real-time FPS and render statistics
- **Viewport Optimization**: Renders only visible elements
- **Files**:
  - `frontend/components/panels/VirtualizedFileTree.tsx`
  - `frontend/components/virtualized/VirtualizedCodeViewer.tsx`
  - `frontend/components/feedback/PerformanceMonitor.tsx`
  - `frontend/hooks/useViewportOptimization.ts`

### 2.8 Streaming API ✨ NEW
- **Real-time Analysis**: Server-Sent Events (SSE) and NDJSON streaming
- **Progress Tracking**: Phase-based progress with file counts and percentages
- **Incremental Results**: Endpoints and taint flows delivered in batches
- **Cancellation Support**: AbortController for stream termination
- **Visual Progress UI**: StreamingProgress component with phase indicators
- **Event Types**:
  - `init` - Analysis initialization info
  - `progress` - File processing updates
  - `symbols` - Symbol table chunks
  - `endpoints` - Endpoint batches
  - `taint` - Taint flow results
  - `stats` - Final statistics
  - `complete` - Analysis completion
  - `error` - Error information
- **Files**:
  - `backend/core/streaming_analyzer.py` - Async streaming engine
  - `frontend/hooks/useStreamingAnalysis.ts` - Stream consumer hook
  - `frontend/components/feedback/StreamingProgress.tsx` - Progress UI
- **API Endpoints**:
  - `POST /api/analyze/stream?format=sse|ndjson` - Streaming analysis
  - `POST /api/analyze/stream/cancel` - Cancel ongoing stream

### 2.9 Detail Panel & Source Code Viewer
- Clicking a node opens a slide-over panel
- Shows metadata (URL, Method, Params) and source code with syntax highlighting
- AI security analysis button for deep code review

### 2.10 Backtrace Highlighting
- Clicking a deep node highlights the upstream path in neon yellow
- Helps trace data flow backwards

### 2.11 Template Linking
- Detects `render_template()` calls
- Resolves template file paths
- Shows template source code

### 2.12 Inter-Procedural Taint Analysis
- **Function Summaries**: Captures how functions propagate taint (input→output mapping)
- **Call Graph Integration**: Follows taint through function call chains
- **Context-Sensitive**: Considers call context for precise tracking
- **Recursive Handling**: Detects and safely handles recursive calls
- **Configurable Depth**: Limits analysis depth to prevent infinite loops
- **Sanitizer Recognition**: Detects when taint is sanitized (html.escape, shlex.quote, etc.)
- **Vulnerability Types**: XSS, SQLi, Command Injection, Path Traversal, SSTI, SSRF
- **Files**:
  - `backend/core/interprocedural_taint.py` - Analysis engine
  - `backend/test_interprocedural.py` - Test suite

### 2.13 Enhanced Import Resolution ✨ NEW
- **Module Dependency Graph**: Complete project dependency mapping
- **Multi-Language Support**: Python, JavaScript/TypeScript
- **Import Types**:
  - Python: `import`, `from...import`, relative (`.`, `..`), aliases, dynamic
  - JavaScript: ES6 (`import`), CommonJS (`require`), dynamic (`import()`)
  - TypeScript: ES6, type imports, path aliases (@/)
- **Symbol Resolution**: "Go to definition" functionality
- **Circular Detection**: Identifies circular import chains
- **Resolution Rate**: 86.7% on real projects
- **Files**:
  - `backend/core/import_resolver.py` - Import resolution engine
  - `backend/test_import_resolver.py` - Test suite

### 2.14 Type Inference ✨ NEW
- **Multi-Source Type Inference**: Extracts types from annotations, literals, and expressions
- **Language Support**: Python, JavaScript, TypeScript
- **Type Categories**: Primitive, Collection, Class, Function, Union, Generic, Any, None, Unknown
- **Confidence Scoring**: Each inferred type includes confidence level
- **Inference Sources**:
  - Python: Type annotations, literals, docstrings, function return types
  - JavaScript: Literal inference, JSDoc comments, class definitions
  - TypeScript: Full type system (interfaces, generics, unions)
- **Key Features**:
  - Variable type tracking with scope awareness
  - Function signature extraction (params, return types, decorators)
  - Class type information (attributes, methods, base classes)
  - Type history tracking for variables
- **Stats on Real Project**:
  - 54 files analyzed
  - 939 types from annotations, 1165 from literals, 864 inferred
  - 2968 variables, 523 functions, 96 classes
- **Files**:
  - `backend/core/type_inferencer.py` - Type inference engine (~1000 LOC)
  - `backend/test_type_inferencer.py` - Test suite (6 tests)

### 2.15 Class Hierarchy Analysis ✨ NEW
- **Inheritance Graph**: Complete class inheritance relationship mapping
- **Multi-Language Support**: Python, JavaScript, TypeScript
- **Class Kinds**: CLASS, ABSTRACT_CLASS, INTERFACE, MIXIN, PROTOCOL, ENUM, DATACLASS
- **Method Kinds**: INSTANCE, STATIC, CLASS_METHOD, ABSTRACT, PROPERTY, CONSTRUCTOR
- **Key Features**:
  - Method Resolution Order (MRO) using C3 linearization algorithm
  - Method override detection with parent tracking
  - Diamond inheritance detection
  - Interface implementation tracking
  - Polymorphic call resolution
  - Visualization-ready inheritance graph
- **Language-Specific**:
  - Python: `@abstractmethod`, `@staticmethod`, `@classmethod`, `@property`, `ABC`, `Protocol`
  - JavaScript: ES6 classes, prototype patterns, constructor detection
  - TypeScript: Interfaces, abstract classes, implements clauses
- **Stats on Real Project**:
  - 96 classes, 366 methods, 51 overrides
  - 48 inheritance edges, 0 diamond patterns
- **Files**:
  - `backend/core/class_hierarchy.py` - Class hierarchy analyzer (~1200 LOC)
  - `backend/test_class_hierarchy.py` - Test suite (9 tests)

### 2.16 Distributed Analysis Architecture ✨ NEW
- **Celery + Redis**: Asynchronous distributed task processing
- **Task Queues**: Priority-based queuing (high, normal, low)
- **Worker Scaling**: Multiple specialized queues (default, analysis, taint, hierarchy)
- **Real-time Progress**: WebSocket-based progress reporting
- **Key Features**:
  - File-level parallelism with distributed workers
  - Task routing by analysis type
  - Progress tracking with phase indicators
  - Fault tolerance (retries, timeouts, result expiration)
  - Periodic cleanup and stats tasks
  - Full analysis workflow (parallel execution)
- **Task Types**:
  - `analyze_file_task` - Single file analysis
  - `analyze_project_task` - Full project distributed analysis
  - `taint_analysis_task` - Dedicated taint analysis
  - `type_inference_task` - Type inference analysis
  - `hierarchy_analysis_task` - Class hierarchy analysis
  - `import_resolution_task` - Import resolution
  - `full_analysis_workflow` - All analyses in parallel
- **WebSocket Protocol**:
  - `subscribe/unsubscribe` - Task progress subscription
  - `progress` - Real-time progress updates
  - `status` - Task status queries
  - `result` - Completion results
  - `worker_stats/queue_stats` - System monitoring
- **Files**:
  - `backend/core/celery_config.py` - Celery configuration
  - `backend/core/distributed_tasks.py` - Distributed task definitions
  - `backend/core/websocket_progress.py` - WebSocket progress reporter
  - `backend/test_distributed.py` - Test suite (9 tests)

### 2.17 Microservice API Tracking ✨ NEW
- **OpenAPI/Swagger Parsing**: Supports Swagger 2.0, OpenAPI 3.0.x, 3.1.x
- **gRPC Proto Parsing**: Extracts services, methods, streaming configuration
- **Service Call Detection**: Identifies inter-service HTTP/gRPC calls
- **Multi-Language Support**: Python, JavaScript, Java, Go
- **Key Features**:
  - OpenAPI spec parsing (YAML/JSON)
  - gRPC proto file analysis
  - HTTP client call detection (requests, axios, fetch, RestTemplate)
  - gRPC client call detection
  - Service dependency graph generation
  - Data flow between services tracking
- **API Protocols**: REST, gRPC, GraphQL, WebSocket
- **Service Types**: API Gateway, Backend, Frontend, Database, Message Queue, Cache
- **HTTP Client Patterns**:
  - Python: `requests`, `httpx`, `aiohttp`, `urllib`
  - JavaScript: `fetch`, `axios`, `got`
  - Java: `RestTemplate`, `WebClient`, `HttpClient`
  - Go: `net/http`, custom clients
- **gRPC Client Patterns**:
  - Python: `grpc.insecure_channel`, Stub classes
  - JavaScript: `grpc.credentials`
  - Java: `ManagedChannelBuilder`, newBlockingStub
  - Go: `grpc.Dial`, pb.NewClient
- **Visualization**: Service graph with nodes and edges for dependencies
- **Files**:
  - `backend/core/microservice_analyzer.py` - Microservice analyzer (~960 LOC)
  - `backend/test_microservice.py` - Test suite (8 tests)

### 2.18 Monorepo Support ✨ NEW
- **Multi-Project Detection**: Automatically detects monorepo structures
- **Build Configuration Parsing**: Parses various build files
- **Shared Library Tracking**: Identifies shared packages across projects
- **Dependency Graph**: Internal dependency visualization
- **Supported Monorepo Tools**:
  - JavaScript: npm/yarn/pnpm workspaces, Lerna, Turborepo, Nx, Rush
  - Java: Maven multi-module, Gradle multi-project
  - Go: Go workspaces (go.work)
  - Rust: Cargo workspaces
  - Python: Poetry monorepos
- **Supported Build Files**:
  - `package.json` (npm/yarn/pnpm)
  - `pom.xml` (Maven)
  - `build.gradle` / `build.gradle.kts` (Gradle)
  - `go.mod` / `go.work` (Go)
  - `Cargo.toml` (Rust)
  - `pyproject.toml` (Python)
- **Key Features**:
  - Project discovery by workspace patterns
  - Internal dependency resolution
  - Shared package identification
  - Topological build order calculation
  - Affected projects analysis (change impact)
  - Visualization-ready dependency graph
- **Files**:
  - `backend/core/monorepo_analyzer.py` - Monorepo analyzer (~950 LOC)
  - `backend/test_monorepo.py` - Test suite (9 tests)

### 2.19 Language Server Protocol (LSP) Integration ✨ NEW
- **LSP Client**: Communicates with language servers via JSON-RPC over stdio
- **Multi-Language Support**: Python (Pyright), TypeScript, JavaScript, Java (JDT LS), Go (gopls), Rust (rust-analyzer)
- **Code Intelligence Features**:
  - **Go-to-Definition**: Navigate to symbol definitions with IDE-level accuracy
  - **Find References**: Find all references to a symbol across the project
  - **Hover Info**: Display type information, documentation, and signatures
  - **Code Completion**: Intelligent autocomplete suggestions
  - **Document Symbols**: Hierarchical symbol list for files
  - **Workspace Symbols**: Search symbols across entire project
  - **Diagnostics**: Compiler errors and warnings from language servers
- **LSP Manager**: Manages multiple language servers simultaneously
- **Document Lifecycle**: Automatic document open/close/update synchronization
- **Language Servers**:
  - Python: `pyright-langserver` (.py, .pyi)
  - TypeScript: `typescript-language-server` (.ts, .tsx)
  - JavaScript: `typescript-language-server` (.js, .jsx)
  - Java: `jdtls` (.java)
  - Go: `gopls` (.go)
  - Rust: `rust-analyzer` (.rs)
- **JSON-RPC Transport**: Full LSP protocol implementation with request/response/notification handling
- **Key Features**:
  - Subprocess-based server spawning
  - Automatic server initialization and shutdown
  - File extension-based server selection
  - IDE-level type information extraction
  - Real-time diagnostics updates
  - Graceful error handling
- **API Coverage**: 10 endpoints for comprehensive LSP functionality
- **Files**:
  - `backend/core/lsp_client.py` - LSP client and manager (~900 LOC)
  - `backend/test_lsp.py` - Test suite (32 tests, 31 passed, 1 skipped)

### 2.20 ML-based Vulnerability Detection ✨ NEW
- **Machine Learning Classification**: Reduces False Positive Rate from ~50% to <15%
- **Multi-Feature Extraction**: AST, semantic, contextual, and pattern features
- **Ensemble Model**: Combines rule-based and feature-weighted classifiers
- **False Positive Filtering**: Pattern-based, contextual, and historical filtering
- **Key Features**:
  - **Feature Extraction** (~550 LOC):
    - Structural: AST complexity, nesting depth, branch count, loop count
    - Semantic: Type annotations, symbol resolution, function boundaries
    - Contextual: Entry points, sanitizers, call graph integration
    - Pattern: Dangerous patterns, sanitizer patterns, framework indicators
  - **ML Vulnerability Detector** (~600 LOC):
    - Ensemble classification (Rule-based + Feature-weighted)
    - Confidence scoring (0.0-1.0)
    - Severity prediction (Critical → Info)
    - Risk and mitigating factor analysis
    - Fix recommendations generation
    - Online learning via feedback
  - **False Positive Filter** (~450 LOC):
    - Pattern-based: ORM, parameterized queries, escaping functions
    - Contextual: Framework detection (Django, Flask, Spring, Express)
    - Historical: Learns from past false positives
    - Multi-layer filtering pipeline
- **Vulnerability Types Supported**:
  - SQL Injection, XSS, Command Injection, Code Injection
  - Path Traversal, SSRF, Template Injection, Open Redirect
- **Framework Detection**:
  - Python: Flask, Django, FastAPI
  - JavaScript: Express, React
  - Java: Spring Boot
  - PHP: Laravel
- **API Endpoints**:
  - `POST /api/ml/analyze` - ML-based vulnerability analysis
  - `POST /api/ml/feedback` - Submit prediction feedback
  - `GET /api/ml/stats` - Get ML analyzer statistics
  - `POST /api/ml/reset-stats` - Reset statistics
- **Files**:
  - `backend/core/ml_feature_extractor.py` - Feature extraction engine (~550 LOC)
  - `backend/core/ml_vulnerability_detector.py` - ML classifier (~600 LOC)
  - `backend/core/ml_false_positive_filter.py` - FP filter (~450 LOC)
  - `backend/test_ml_analyzer.py` - Test suite (20+ tests)

### 2.21 LLM-based Advanced Security Analysis ✨ NEW
- **LLM Integration**: Groq API with multi-model fallback (GPT-OSS-120B, LLaMA 3.3 70B, Qwen3 32B)
- **Business Logic Analysis**: Detects complex vulnerabilities beyond pattern matching
- **Authentication Analysis**: JWT, Session, OAuth/SAML vulnerability detection
- **API Security Analysis**: GraphQL, Rate Limiting, Data Exposure detection
- **Intelligent Remediation**: Context-aware fix generation with test cases
- **Key Features**:
  - **Business Logic Analyzer**:
    - Broken Access Control (BAC)
    - IDOR (Insecure Direct Object Reference)
    - Race Conditions
    - State Management Issues
    - Business Logic Bypass
  - **Authentication Analyzer**:
    - JWT Vulnerabilities (Algorithm Confusion, Missing Validation, None Algorithm)
    - Session Fixation, Session Management Flaws
    - OAuth/SAML Misconfigurations
    - Password Policy Violations
    - Credential Exposure
  - **API Security Analyzer**:
    - GraphQL Query Complexity Attacks
    - Missing Rate Limiting
    - API Key Exposure
    - Data Exposure in Responses
    - Mass Assignment Vulnerabilities
  - **Intelligent Remediator**:
    - Framework-specific code fixes (Flask, Django, FastAPI, Express, Spring)
    - Security pattern recommendations
    - Automated test case generation
    - Confidence scoring (high/medium/low)
- **Framework Detection**: Flask, Django, FastAPI, Express, Koa, NestJS, Spring
- **Auth Mechanism Detection**: JWT, Session, OAuth, SAML, Basic Auth, API Key
- **API Endpoints**:
  - `POST /api/llm/analyze` - LLM-based security analysis (full/business_logic/authentication/api_security)
  - `POST /api/llm/remediation` - Generate fix suggestions with test cases
  - `POST /api/llm/analyze/batch` - Batch project analysis
  - `GET /api/llm/stats` - LLM analyzer statistics
- **Files**:
  - `backend/core/llm_security_analyzer.py` - LLM security analyzer (~750 LOC)
  - `backend/test_llm_analyzer.py` - Test suite (20+ tests)

### 2.22 Advanced Data-Flow Analysis ✨ NEW
- **Control Flow Graph (CFG)**: 소스 코드에서 제어 흐름 그래프 생성
- **Program Dependence Graph (PDG)**: 제어/데이터 의존성 그래프 생성
- **Path-Sensitive Analysis**: 실행 경로별 독립적인 분석
- **Context-Sensitive Analysis**: 호출 컨텍스트를 고려한 정밀 분석
- **Symbolic Execution**: 심볼릭 값과 경로 조건 추적
- **Multi-Language Support**: Python, JavaScript, TypeScript
- **Key Features**:
  - **CFG Builder** (~900 LOC):
    - Python CFG: if/for/while/try/with 구문 지원
    - JavaScript CFG: if/for/while/switch/do-while 구문 지원
    - TypeScript CFG: JavaScript + 타입 구문 지원
    - Dominator Computation: 지배자 트리 계산
    - Loop Detection: 자연 루프 탐지
    - Path Enumeration: 실행 경로 열거
  - **PDG Generator** (~700 LOC):
    - Control Dependencies: 제어 의존성 분석
    - Data Dependencies: 데이터 의존성 (def-use 체인)
    - Reaching Definitions: 도달 정의 분석
    - Backward Slicing: 역방향 프로그램 슬라이싱
    - Forward Slicing: 순방향 프로그램 슬라이싱
    - Taint PDG Analyzer: PDG 기반 정밀 테인트 분석
  - **Advanced Data-Flow Analyzer** (~800 LOC):
    - Flow-Insensitive Analysis: 빠르지만 정밀도 낮음
    - Flow-Sensitive Analysis: 문장 순서 고려
    - Path-Sensitive Analysis: 경로 조건 기반 분석
    - Context-Sensitive Analysis: k-CFA 스타일 호출 컨텍스트
    - Symbolic State Tracking: 심볼릭 값 추적
    - Path Condition Management: 경로 조건 관리
    - Feasibility Checking: 불가능한 경로 필터링
    - Points-to Analysis: 별칭(Alias) 탐지
- **Analysis Sensitivity Levels**:
  - FLOW_INSENSITIVE: 가장 빠름, 정밀도 낮음
  - FLOW_SENSITIVE: 문장 순서 인식
  - PATH_SENSITIVE: 경로별 독립 분석 (권장)
  - CONTEXT_SENSITIVE: 호출 컨텍스트 고려 (가장 정밀)
- **Academic Foundation**:
  - IFDS/IDE Framework: Interprocedural 분석
  - CFL-Reachability: 문맥 자유 언어 도달성
  - Demand-Driven Analysis: 필요 기반 분석
  - Incremental Analysis: 증분 분석 지원
- **API Endpoints**:
  - `POST /api/dataflow/cfg` - CFG 생성 (파일/프로젝트)
  - `POST /api/dataflow/pdg` - PDG 생성 (의존성 그래프)
  - `POST /api/dataflow/analyze` - 고급 데이터 흐름 분석
  - `POST /api/dataflow/slice` - 프로그램 슬라이싱 (backward/forward)
  - `POST /api/dataflow/taint-pdg` - PDG 기반 정밀 테인트 분석
  - `GET /api/dataflow/stats` - 분석 통계
- **Files**:
  - `backend/core/cfg_builder.py` - Control Flow Graph 빌더 (~900 LOC)
  - `backend/core/pdg_generator.py` - Program Dependence Graph 생성기 (~700 LOC)
  - `backend/core/advanced_dataflow_analyzer.py` - 고급 데이터 흐름 분석기 (~800 LOC)
  - `backend/test_dataflow_analyzer.py` - 테스트 스위트 (30+ tests)

### 2.23 Distributed Analysis Architecture ✨ NEW
- **대규모 프로젝트 분석**: 10,000+ 파일 분석 지원
- **분산 캐싱**: Redis 기반 분산 캐싱 시스템
- **워크로드 밸런싱**: 복잡도 기반 최적 분배
- **클러스터 오케스트레이션**: 워커 관리 및 헬스 체크
- **Multi-Language Support**: Python, JavaScript, TypeScript, PHP, Java, Go
- **Key Features**:
  - **DistributedAnalyzer** (~500 LOC):
    - 자동 파일 탐색 (50,000+ 파일)
    - ThreadPool/ProcessPool 기반 병렬 처리
    - 심볼 테이블 통합 및 결과 병합
    - 실시간 진행 콜백
    - Fault Tolerance (파티션별 에러 격리)
  - **RedisCache** (~250 LOC):
    - Async/Sync Redis 연결
    - SHA256 해시 기반 파일 캐싱
    - 24시간 기본 TTL
    - 프로젝트 단위 캐시 무효화
    - 캐시 통계 (히트율, 메모리)
  - **WorkloadBalancer** (~200 LOC):
    - 파일 복잡도 추정 (언어, 크기 기반)
    - Simple/Balanced/Size 파티셔닝 전략
    - 워커 선택 알고리즘
  - **ClusterOrchestrator** (~150 LOC):
    - 워커 등록/해제
    - 하트비트 기반 헬스 체크
    - 클러스터 통계
    - 태스크 라우팅
- **Analysis Pipeline**:
  - DISCOVERY → PARTITIONING → PARSING → SYMBOL_RESOLUTION
  - → TAINT_ANALYSIS → AGGREGATION → FINALIZATION
- **Partitioning Strategies**:
  - Simple: 단순 파일 수 기반
  - Balanced: 복잡도 기반 균형 분배 (권장)
  - Size: 파일 크기 기반
- **API Endpoints**:
  - `POST /api/distributed/large-scale-analyze` - 대규모 분석
  - `POST /api/distributed/large-scale-analyze/full` - 전체 결과
  - `POST /api/distributed/cache` - 캐시 작업
  - `GET /api/distributed/cache/stats` - 캐시 통계
  - `POST /api/distributed/cluster` - 클러스터 정보
  - `GET /api/distributed/partitioning/preview` - 파티셔닝 미리보기
- **Files**:
  - `backend/core/distributed_analyzer.py` - 분산 분석 엔진 (~1100 LOC)
  - `backend/test_distributed_analyzer.py` - 테스트 스위트 (25+ tests)

### 2.24 Frontend Performance Optimization ✨ NEW
- **React Query 데이터 페칭**: @tanstack/react-query 기반 데이터 관리
- **무한 스크롤**: 가상화된 취약점 목록 (@tanstack/react-virtual)
- **Web Worker 그래프 레이아웃**: 백그라운드 스레드에서 레이아웃 계산
- **Service Worker 캐싱**: API 응답 및 정적 자산 캐싱
- **Key Features**:
  - **React Query Integration** (~340 LOC):
    - QueryClient 설정 (staleTime: 5분, gcTime: 30분)
    - 분석/보안스캔/콜그래프 전용 훅
    - 무한 쿼리 지원 (useInfiniteVulnerabilities)
    - 프리페치 및 캐시 무효화 유틸리티
  - **Infinite Scroll VulnerabilityList** (~230 LOC):
    - @tanstack/react-virtual 기반 가상화
    - 자동 페이지 로드 (스크롤 감지)
    - 심각도별 필터링
    - 선택 상태 관리
  - **Web Worker Graph Layout** (~500 LOC):
    - Dagre 레이아웃 알고리즘 (토폴로지 정렬)
    - 점진적 레이아웃 (대규모 그래프용)
    - 진행 상황 보고
    - 타임아웃 및 취소 지원
  - **Service Worker Caching** (~350 LOC):
    - API 응답 캐싱 (stale-while-revalidate)
    - 정적 자산 프리캐싱
    - 오프라인 지원
    - 업데이트 알림 배너
- **Caching Strategies**:
  - 분석 결과: 10분 (stale-while-revalidate)
  - 보안 스캔: 5분 (stale-while-revalidate)
  - 콜그래프: 10분 (stale-while-revalidate)
  - 코드 스니펫: 30분 (cache-first)
- **Files**:
  - `frontend/lib/queryClient.ts` - React Query 클라이언트 설정
  - `frontend/components/providers/QueryProvider.tsx` - Query Provider
  - `frontend/hooks/useAnalysisQuery.ts` - 분석 쿼리 훅
  - `frontend/components/virtualized/InfiniteVulnerabilityList.tsx` - 무한 스크롤 목록
  - `frontend/public/workers/graphLayoutWorker.js` - 그래프 레이아웃 워커
  - `frontend/hooks/useGraphLayoutWorker.ts` - 워커 훅
  - `frontend/public/sw.js` - Service Worker
  - `frontend/lib/serviceWorker.ts` - SW 관리 유틸리티
  - `frontend/hooks/useServiceWorker.ts` - SW 훅
  - `frontend/components/providers/ServiceWorkerProvider.tsx` - SW Provider

## 3. Key Architecture & Files

### Backend (`backend/`)

#### Main Application
- **`main.py`**: FastAPI app with endpoints:
  - `POST /api/analyze` - Parse and analyze project (supports parallel mode)
  - `POST /api/analyze/stream` - Streaming analysis (SSE/NDJSON)
  - `POST /api/analyze/stream/cancel` - Cancel streaming analysis
  - `GET /api/analyze/stats` - Get analysis statistics
  - `POST /api/snippet` - Get source code snippet
  - `POST /api/analyze/ai` - AI-powered security analysis
  - `POST /api/analyze/semgrep` - Semgrep security scan
  - `POST /api/taint/interprocedural` - Inter-procedural taint analysis
  - `POST /api/taint/interprocedural/full` - Full analysis with summaries
  - `POST /api/taint/paths` - Taint path discovery
  - `POST /api/imports/resolve` - Import resolution & dependency graph
  - `POST /api/imports/graph` - Visualization-friendly dependency graph
  - `POST /api/imports/symbol` - Symbol definition resolution
  - `POST /api/imports/module` - Module details with exports
  - `POST /api/types/analyze` - Full project type analysis
  - `POST /api/types/variable` - Query variable type
  - `POST /api/types/function` - Query function signature
  - `POST /api/types/class` - Query class type info
  - `POST /api/hierarchy/analyze` - Full class hierarchy analysis
  - `POST /api/hierarchy/class` - Get class ancestors/descendants
  - `POST /api/hierarchy/implementations` - Find interface implementors
  - `POST /api/hierarchy/method` - Get method override chain
  - `POST /api/hierarchy/polymorphic` - Resolve polymorphic call targets
  - `POST /api/hierarchy/graph` - Visualization-ready inheritance graph
  - `GET /api/distributed/status` - Distributed system status ✨ NEW
  - `POST /api/distributed/analyze` - Start distributed analysis ✨ NEW
  - `POST /api/distributed/workflow` - Full analysis workflow ✨ NEW
  - `POST /api/distributed/task/status` - Task status query ✨ NEW
  - `POST /api/distributed/task/result` - Task result query ✨ NEW
  - `POST /api/distributed/task/cancel` - Cancel task ✨ NEW
  - `GET /api/distributed/workers` - Worker info ✨ NEW
  - `POST /api/distributed/large-scale-analyze` - Large-scale analysis ✨ NEW
  - `POST /api/distributed/large-scale-analyze/full` - Full large-scale results ✨ NEW
  - `POST /api/distributed/cache` - Cache operations ✨ NEW
  - `GET /api/distributed/cache/stats` - Cache statistics ✨ NEW
  - `POST /api/distributed/cluster` - Cluster info ✨ NEW
  - `GET /api/distributed/partitioning/preview` - Partitioning preview ✨ NEW
  - `POST /api/ml/analyze` - ML-based vulnerability analysis ✨ NEW
  - `POST /api/ml/feedback` - Submit ML prediction feedback ✨ NEW
  - `GET /api/ml/stats` - Get ML analyzer statistics ✨ NEW
  - `POST /api/ml/reset-stats` - Reset ML statistics ✨ NEW
  - `POST /api/llm/analyze` - LLM-based security analysis ✨ NEW
  - `POST /api/llm/remediation` - Generate fix suggestions ✨ NEW
  - `POST /api/llm/analyze/batch` - Batch project analysis ✨ NEW
  - `GET /api/llm/stats` - LLM analyzer statistics ✨ NEW
  - `GET /api/distributed/queues` - Queue info ✨ NEW
  - `WebSocket /ws/progress` - Real-time progress ✨ NEW
  - `POST /api/microservices/analyze` - Full microservice analysis ✨ NEW
  - `POST /api/microservices/openapi/parse` - Parse OpenAPI/Swagger spec ✨ NEW
  - `POST /api/microservices/proto/parse` - Parse gRPC proto file ✨ NEW
  - `POST /api/microservices/service` - Get service details ✨ NEW
  - `POST /api/microservices/calls` - Get service calls ✨ NEW
  - `POST /api/microservices/dataflow` - Get data flow between services ✨ NEW
  - `POST /api/microservices/graph` - Get service dependency graph ✨ NEW
  - `POST /api/monorepo/analyze` - Full monorepo analysis ✨ NEW
  - `POST /api/monorepo/project` - Get project details ✨ NEW
  - `POST /api/monorepo/graph` - Get dependency graph ✨ NEW
  - `POST /api/monorepo/affected` - Get affected projects ✨ NEW
  - `POST /api/monorepo/dependencies` - Get project dependencies ✨ NEW
  - `POST /api/monorepo/build-order` - Get build order ✨ NEW
  - `POST /api/lsp/initialize` - Initialize LSP servers ✨ NEW
  - `POST /api/lsp/shutdown` - Shutdown LSP servers ✨ NEW
  - `GET /api/lsp/status` - LSP server status ✨ NEW
  - `GET /api/lsp/available` - Available language servers ✨ NEW
  - `POST /api/lsp/definition` - Go-to-definition ✨ NEW
  - `POST /api/lsp/references` - Find references ✨ NEW
  - `POST /api/lsp/hover` - Hover information ✨ NEW
  - `POST /api/lsp/completions` - Code completions ✨ NEW
  - `POST /api/lsp/symbols` - Document symbols ✨ NEW
  - `POST /api/lsp/workspace-symbols` - Workspace symbol search ✨ NEW
  - `POST /api/lsp/diagnostics` - Get diagnostics ✨ NEW
  - `POST /api/dataflow/cfg` - Build CFG ✨ NEW
  - `POST /api/dataflow/pdg` - Build PDG ✨ NEW
  - `POST /api/dataflow/analyze` - Advanced data-flow analysis ✨ NEW
  - `POST /api/dataflow/slice` - Program slicing ✨ NEW
  - `POST /api/dataflow/taint-pdg` - PDG-based taint analysis ✨ NEW
  - `GET /api/dataflow/stats` - Data-flow statistics ✨ NEW
  - `POST /api/callgraph` - Call graph analysis
  - `POST /api/callgraph/paths` - Find paths to sinks
  - `POST /api/callgraph/metrics` - Function metrics
  - `GET /api/cache/stats` - Cache statistics
  - `POST /api/cache/invalidate` - Selective cache invalidation
  - `DELETE /api/cache` - Clear all cache

#### Parser Module (`core/parser/`)
```
├── __init__.py
├── base.py              # BaseParser abstract class
├── manager.py           # ParserManager - auto-selects parser by file extension
├── python.py            # Flask, FastAPI, Django support
├── javascript.py        # Express, DOM XSS detection
├── typescript.py        # Next.js, React, Express (NEW)
├── php.py               # Laravel, Symfony (ENHANCED)
├── java.py              # Spring Boot, Servlet
├── go.py                # Gin, net/http
├── extractors.py        # Shared extraction utilities
├── helpers.py           # InputExtractor, SanitizationAnalyzer
└── frameworks/
    ├── base_framework.py    # BaseFrameworkExtractor
    ├── flask_extractor.py   # Flask patterns
    ├── fastapi_extractor.py # FastAPI patterns
    ├── django_extractor.py  # Django/DRF patterns (ENHANCED)
    └── php_extractor.py     # Laravel/Symfony patterns (NEW)
```

#### Security Analysis (`core/`)
- **`parallel_analyzer.py`**: Parallel/sequential file processing
- **`analysis_cache.py`**: SQLite-based analysis caching
- **`taint_analyzer.py`**: Taint analysis engine
- **`interprocedural_taint.py`**: Inter-procedural taint analysis
- **`import_resolver.py`**: Enhanced import resolution
- **`type_inferencer.py`**: Type inference engine
- **`class_hierarchy.py`**: Class hierarchy analyzer
- **`celery_config.py`**: Celery + Redis configuration
- **`distributed_tasks.py`**: Distributed analysis tasks
- **`websocket_progress.py`**: WebSocket progress reporter
- **`microservice_analyzer.py`**: Microservice API tracking
- **`monorepo_analyzer.py`**: Monorepo structure analyzer ✨ NEW
- **`lsp_client.py`**: Language Server Protocol client ✨ NEW
- **`cfg_builder.py`**: Control Flow Graph builder ✨ NEW
- **`pdg_generator.py`**: Program Dependence Graph generator ✨ NEW
- **`advanced_dataflow_analyzer.py`**: Advanced data-flow analyzer ✨ NEW
- **`distributed_analyzer.py`**: Distributed analysis architecture ✨ NEW
- **`call_graph_analyzer.py`**: Call graph builder
- **`streaming_analyzer.py`**: Streaming analysis engine
- **`ai_analyzer.py`**: Groq LLM integration
- **`cluster_manager.py`**: Node grouping logic
- **`symbol_table.py`**: Cross-file symbol resolution
- **`analyzer/semgrep_analyzer.py`**: Semgrep wrapper

#### Models (`models.py`)
```python
- EndpointNodes      # Graph node representation
- Parameter          # Function parameters
- TaintFlowEdge      # Source→Sink visualization edge
- CallGraphNode      # Function in call graph (NEW)
- CallGraphEdge      # Call relationship (NEW)
- CallGraphData      # Complete call graph (NEW)
- ProjectStructure   # Analysis result container
```

### Frontend (`frontend/`)

#### Components
```
├── components/
│   ├── Visualizer.tsx           # Main graph component (ReactFlowProvider wrapped)
│   ├── controls/
│   │   └── ControlBar.tsx       # Top control bar with toggles
│   ├── panels/
│   │   ├── DetailPanel.tsx      # Node detail view
│   │   ├── FileTreeSidebar.tsx  # Original file tree (deprecated)
│   │   └── VirtualizedFileTree.tsx  # Virtualized file tree ✨ NEW
│   ├── virtualized/             # ✨ NEW folder
│   │   └── VirtualizedCodeViewer.tsx  # Large code viewer
│   └── feedback/
│       ├── ErrorToast.tsx
│       └── PerformanceMonitor.tsx   # FPS/stats monitor ✨ NEW
├── types/
│   ├── graph.ts            # TypeScript interfaces
│   └── errors.ts           # Error handling types
├── hooks/
│   ├── useBacktrace.ts     # Backtrace highlighting logic
│   ├── useResizePanel.ts   # Panel resize handling
│   └── useViewportOptimization.ts  # Viewport culling ✨ NEW
└── utils/
    ├── nodeStyles.ts       # Node styling by type
    └── filterBehavior.ts   # Filter helpers
```

## 4. UI Controls

| Button | Description |
|--------|-------------|
| **▶ 시각화** | Analyze project and render graph |
| **🛡️ 보안 스캔** | Run Semgrep security scan |
| **Call Graph** | Toggle call graph view (NEW) |
| **Taint** | Show/hide taint flow edges |
| **Sink** | Show/hide sink nodes |
| **📂** | Toggle file tree sidebar |

## 5. Dependencies

### Backend (`requirements.txt`)
```
fastapi, uvicorn, pydantic
tree-sitter, tree-sitter-python, tree-sitter-javascript
tree-sitter-typescript, tree-sitter-php, tree-sitter-java, tree-sitter-go
groq, httpx, python-dotenv
semgrep (optional, for security scanning)
```

### Frontend (`package.json`)
```
next@16, react@19, reactflow
dagre, framer-motion
lucide-react, react-markdown
react-syntax-highlighter, tailwindcss
@tanstack/react-virtual   # ✨ NEW - UI virtualization
```

## 6. Troubleshooting History

1. **Parser Scope Error**: Variables out of scope → Fixed by reordering
2. **Semgrep Korean Path**: Non-ASCII paths → Fixed by copying to temp dir
3. **Parser Size**: 938-line monolith → Refactored to modular components
4. **tree-sitter-typescript missing**: → Installed in venv
5. **nonlocal error in main.py**: → Removed unnecessary nonlocal declaration

## 7. Recent Additions (2026-01-30)

### 7.1 Parallel Analyzer
- **File**: `backend/core/parallel_analyzer.py`
- **Features**:
  - `ThreadPoolExecutor` 기반 병렬 파일 분석
  - 자동 모드 선택 (파일 < 100개: 순차, >= 100개: 병렬)
  - CPU 코어 수 기반 워커 자동 설정
  - 분석 통계 수집 및 리포팅
- **API**: `GET /api/analyze/stats` - 분석 통계 조회

### 7.2 Analysis Caching
- **File**: `backend/core/analysis_cache.py`
- **Features**:
  - SQLite 기반 분석 결과 캐싱
  - SHA256 파일 해시로 변경 감지
  - 증분 분석 (변경된 파일만 재파싱)
- **Performance**: 23x 속도 향상 (95.7% 시간 절약)
- **API**: `GET /api/cache/stats`, `POST /api/cache/invalidate`, `DELETE /api/cache`

### 7.3 UI Virtualization ✨ NEW
- **Files**:
  - `frontend/components/panels/VirtualizedFileTree.tsx` - 가상화된 파일 트리
  - `frontend/components/virtualized/VirtualizedCodeViewer.tsx` - 대용량 코드 뷰어
  - `frontend/components/feedback/PerformanceMonitor.tsx` - 성능 모니터
  - `frontend/hooks/useViewportOptimization.ts` - 뷰포트 최적화
- **Features**:
  - @tanstack/react-virtual 기반 가상 스크롤링
  - 10,000+ 파일 부드러운 렌더링
  - 점진적 노드 로딩 (UI 프리징 방지)
  - 실시간 FPS 모니터링
  - ReactFlow 성능 최적화 (1000+ 노드 시 드래그 비활성화)

### 7.4 Development Roadmap
- **File**: `ROADMAP.md`
- Phase 1~3 구현 계획 문서화

## 8. Future Enhancements

### High Priority
- [ ] **Vulnerability Dashboard**: Statistics and charts
- [ ] **Report Export**: PDF/HTML/JSON output
- [ ] **Interactive Filters**: Filter by vulnerability type

### Medium Priority
- [ ] **Data Flow Tracing**: Variable-level tracking
- [ ] **Search Function**: Find nodes by name
- [ ] **History Comparison**: Compare analysis results

### Low Priority
- [ ] **Real-time File Watching**: Auto-refresh on file change
- [ ] **CI/CD Integration**: GitHub Actions support
- [ ] **Collaboration**: Comments and assignments

---

## 2.20 Bug Fix: Analysis Stuck Issue (2026-01-31)

### Issue
- 분석 버튼 클릭 시 "분석 중..." 메시지에서 멈춤
- 한글 경로(`새싹` 등) 포함 디렉토리 분석 실패
- 백엔드 서버 시작 오류

### Resolution ✅
1. **한글 경로 처리 개선**
   - `os.path.normpath()` 추가로 경로 정규화
   - Unicode 인코딩 에러 핸들링 강화
   
2. **파일 접근성 검증**
   - `os.access()`, `os.path.isfile()` 체크 추가
   - 접근 불가능한 파일 자동 스킵

3. **에러 핸들링 강화**
   - `UnicodeDecodeError`, `IOError`, `OSError` 분리 처리
   - 상세한 로깅 추가

4. **진단 도구 추가**
   - `diagnose_directory.py` - 디렉토리 분석 진단
   - `check_backend.py` - 백엔드 서버 상태 확인
   - `start_server.ps1` - 자동 서버 시작 스크립트

### Files Modified
- `backend/core/streaming_analyzer.py`
- `backend/main.py`

### Files Added
- `backend/diagnose_directory.py`
- `backend/check_backend.py`
- `backend/start_server.ps1`
- `docs/TROUBLESHOOTING_ANALYSIS_STUCK.md`
- `QUICK_FIX.md`
- `FIXED.md`

**Version**: 0.11.1 → 0.11.2
