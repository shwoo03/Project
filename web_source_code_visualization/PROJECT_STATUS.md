# Project Status: Web Source Code Visualization Tool

This document summarizes the current state of the project to assist future AI sessions in picking up the work immediately.

**Last Updated**: 2026-01-30

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

### 2.4 Call Graph Analysis (NEW - 2026-01-30)
- **Function-to-function call tracking**: Who calls whom?
- **Entry point detection**: Route handlers, main functions
- **Sink identification**: Functions that reach dangerous operations
- **Path finding**: Find all paths from entry points to sinks
- **Metrics**: Fan-in, fan-out, hub detection, orphan detection

### 2.5 Detail Panel & Source Code Viewer
- Clicking a node opens a slide-over panel
- Shows metadata (URL, Method, Params) and source code with syntax highlighting
- AI security analysis button for deep code review

### 2.6 Backtrace Highlighting
- Clicking a deep node highlights the upstream path in neon yellow
- Helps trace data flow backwards

### 2.7 Template Linking
- Detects `render_template()` calls
- Resolves template file paths
- Shows template source code

## 3. Key Architecture & Files

### Backend (`backend/`)

#### Main Application
- **`main.py`**: FastAPI app with endpoints:
  - `POST /api/analyze` - Parse and analyze project
  - `POST /api/snippet` - Get source code snippet
  - `POST /api/analyze/ai` - AI-powered security analysis
  - `POST /api/analyze/semgrep` - Semgrep security scan
  - `POST /api/callgraph` - Call graph analysis (NEW)
  - `POST /api/callgraph/paths` - Find paths to sinks (NEW)
  - `POST /api/callgraph/metrics` - Function metrics (NEW)

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
- **`taint_analyzer.py`**: Taint analysis engine
- **`call_graph_analyzer.py`**: Call graph builder (NEW)
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
│   ├── Visualizer.tsx      # Main graph component
│   ├── controls/
│   │   └── ControlBar.tsx  # Top control bar with toggles
│   ├── panels/
│   │   ├── DetailPanel.tsx # Node detail view
│   │   └── FileTreeSidebar.tsx
│   └── feedback/
│       └── ErrorToast.tsx
├── types/
│   ├── graph.ts            # TypeScript interfaces
│   └── errors.ts           # Error handling types
├── hooks/
│   ├── useBacktrace.ts     # Backtrace highlighting logic
│   └── useResizePanel.ts   # Panel resize handling
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
```

## 6. Troubleshooting History

1. **Parser Scope Error**: Variables out of scope → Fixed by reordering
2. **Semgrep Korean Path**: Non-ASCII paths → Fixed by copying to temp dir
3. **Parser Size**: 938-line monolith → Refactored to modular components
4. **tree-sitter-typescript missing**: → Installed in venv
5. **nonlocal error in main.py**: → Removed unnecessary nonlocal declaration

## 7. Future Enhancements

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
