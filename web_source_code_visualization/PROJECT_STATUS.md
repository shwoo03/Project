# Project Status: Web Source Code Visualization Tool

This document summarizes the current state of the project to assist future AI sessions in picking up the work immediately.

## 1. Project Overview
A security analysis tool that visualizes the call graph and flow of a target web application (Python/Flask).
- **Backend**: FastAPI (`backend/`), Python Tree-sitter for parsing.
- **Frontend**: Next.js + ReactFlow (`frontend/`).

## 2. Core Features Implemented
1.  **Project Structure Visualization**:
    - Parses Python files to identify Routes (`@app.route`), Functions, Inputs (`request.args`), and Calls.
    - Visualizes them as a DAG (Directed Acyclic Graph) using `dagre` layout.
2.  **Detail Panel & Source Code Viewer**:
    - Clicking a node opens a slide-over panel.
    - Shows metadata (URL, Method, Params) and **Actual Source Code** with syntax highlighting.
    - **Fix**: Resolves function definition locations correctly (clicking a call shows the `def` block).
3.  **Backtrace Highlighting**:
    - Clicking a deep node (e.g., sink function) highlights the upstream path (who called this?) in neon yellow.
4.  **Template Linking**:
    - Detects `render_template("page.html")` calls.
    - Resolves the HTML file path (searches `templates/` directory).
    - Creates a clickable node for the template; clicking it shows the HTML source.
    - **Fix**: Handles absolute/relative path resolution with `os.path`.

## 3. Key Architecture & Files
### Backend (`backend/`)

#### Parser Module (`core/parser/`) - **Refactored 2026-01-30**
The parser was refactored from a monolithic 938-line file into modular components:

-   **`python.py`** (~450 lines): Main PythonParser class
    -   Clean, focused on orchestration
    -   Uses tree-sitter-python for AST parsing
    -   Delegates to framework extractors and helpers

-   **`helpers.py`**: Shared helper functions
    -   `InputExtractor`: User input detection (request.args, form, cookies, etc.)
    -   `SanitizationAnalyzer`: Tracks input flow through sanitizers
    -   `extract_params()`, `extract_sanitizers()`, `extract_identifiers()`
    -   `extract_render_template_context()`: Template context variable extraction

-   **`extractors.py`**: Basic extraction utilities
    -   Constants: `SANITIZER_FUNCTIONS`, `SANITIZER_BASE_NAMES`
    -   `get_node_text()`, `is_sanitizer()`, `extract_path_params()`
    -   `extract_template_usage()`, `find_template_path()`

-   **`frameworks/`**: Framework-specific extractors
    -   `base_framework.py`: Abstract base class, `RouteInfo`, `InputInfo`, `FrameworkRegistry`
    -   `flask_extractor.py`: Flask route and input detection
        -   `@app.route`, `@blueprint.route` patterns
        -   `request.args.get()`, `request.form.get()`, etc.
    -   `fastapi_extractor.py`: FastAPI route and input detection
        -   `@app.get`, `@router.post`, etc.
        -   Path parameters `{id}`, Query/Body injection

-   **Backup**: `python_backup.py` - Original 938-line version for reference

#### Semgrep Analyzer (`core/analyzer/`) - **Fixed 2026-01-30**
-   **`semgrep_analyzer.py`**: Security scanner wrapper
    -   **한글 경로 문제 해결**:
        -   임시 디렉토리로 프로젝트 복사 후 스캔
        -   `--quiet` 플래그로 deprecated 경고 무시
        -   자동 Semgrep 명령어 감지 (semgrep.exe vs python -m semgrep)
    -   **새 기능**: `scan_with_registry()` - Semgrep 레지스트리 규칙 사용 가능
    -   **개선**: 타임아웃 지원, 로깅, JSON 파싱 에러 처리

-   **`main.py`**: FastAPI app.
    -   `/api/analyze`: Triggers parsing.
    -   `/api/snippet`: Reads file content for frontend viewer.

### Frontend (`frontend/`)
-   **`components/Visualizer.tsx`**: Main graph component.
    -   Uses `reactflow` and `dagre`.
    -   Handles `onNodeClick` to fetch snippets (`/api/snippet`).
    -   Implements Backtrace logic (finding upstream nodes/edges).
    -   **Layout**: Details panel is 800px wide.

## 4. Troubleshooting History (Context for AI)
1.  **Parser Scope Error**: `extract_inputs` was referencing variables out of scope. -> *Fixed by reordering functions in `python.py`.*
2.  **Missing Import**: `render_template` logic failed due to missing `import os`. -> *Fixed.*
3.  **Visualizer Blank**: Was caused by the parser crashing silently. Always check `debug_parser.py` if no nodes appear.
4.  **Semgrep Korean Path**: `semgrep.exe` launcher failed with non-ASCII paths -> *Fixed by copying to temp dir.*
5.  **Parser Size**: 938-line monolithic file -> *Refactored into modular components.*

## 5. File Structure After Refactoring
```
backend/core/parser/
├── __init__.py
├── base.py              # BaseParser abstract class
├── extractors.py        # Basic extraction utilities
├── helpers.py           # InputExtractor, SanitizationAnalyzer
├── manager.py           # ParserManager
├── python.py            # Main PythonParser (~450 lines)
├── python_backup.py     # Original version (backup)
├── javascript.py
├── java.py
├── go.py
├── php.py
└── frameworks/
    ├── __init__.py
    ├── base_framework.py    # BaseFrameworkExtractor, FrameworkRegistry
    ├── flask_extractor.py   # Flask-specific extraction
    └── fastapi_extractor.py # FastAPI-specific extraction
```

## 6. Next Recommended Tasks
1.  **Django Extractor**:
    -   Create `frameworks/django_extractor.py`
    -   Handle `urls.py` patterns, `views.py` parsing
2.  **Security Sink Detection**:
    -   Identify dangerous functions (`os.system`, `eval`, `subprocess.call`, etc.)
    -   Mark them with `type="sink"` or `is_dangerous=True`
    -   Frontend: Render with Red/Warning styling
3.  **Attack Surface Summary**:
    -   Dashboard showing total Inputs, Routes, Sinks
4.  **Test Coverage**:
    -   Add unit tests for each framework extractor
    -   Test edge cases (decorators with multiple methods, nested routes)
