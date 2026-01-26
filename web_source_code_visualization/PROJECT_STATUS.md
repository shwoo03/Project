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
-   **`core/parser/python.py`**: The core logic.
    -   Uses `tree-sitter-python`.
    -   **Important**: `extract_inputs`, `extract_calls` helpers are defined inside `parse()`.
    -   **Important**: `defined_funcs` map stores `{file_path, start_line, end_line}` to link calls to definitions.
    -   **Important**: `render_template` logic tries to find sibling or parent `templates` directory.
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

## 5. Next Recommended Tasks
1.  **Security Sink Detection**:
    -   Identify dangerous functions (`os.system`, `eval`, etc.) in `python.py`.
    -   Mark them with a special `type="sink"` or `is_dangerous=True` flag.
    -   Frontend: Render with Red/Warning styling.
2.  **Attack Surface Summary**:
    -   Dashboard showing total Inputs, Routes, sinks.
