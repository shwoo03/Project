# Project Overview: SourceViz (Web Source Code Visualization & Security Analysis)

## 1. Project Purpose
**SourceViz** is a specialized static analysis (SAST) and visualization tool designed for **Capture The Flag (CTF)** and **Wargame** solving.
It parses source code (Express.js, Flask, HTML), visualizes the application structure as an interactive graph, and automatically detects vulnerabilities (RCE, SQLi, Insecure Auth, etc.) using a custom rule engine and LLM auditing.

## 2. Tech Stack
- **Frontend**: Next.js 14, Tailwind CSS, React Flow (Visualization), Lucide React (Icons).
- **Backend/Analysis**: Node.js scripts (`scripts/analyze.js`), Babel Parser (AST), Groq SDK (AI Audit).
- **Rule Engine**: Custom plugin-based system in `scripts/rules/*.js`.

## 3. Key Architectures

### 3.1 Analysis Engine (`scripts/analyze.js`)
- **Hybrid Parsing**:
  - **JavaScript/TypeScript**: Uses `@babel/parser` and `@babel/traverse` to build an AST. Detecting routes (`app.get`, `router.post`) and tracking variable data flow (Taint Analysis).
  - **Python (Flask)**: Uses Regex/Heuristics to extract `@app.route` decorators and `request.*` parameters.
  - **HTML**: Scans for comments (`<!-- -->`) containing sensitive keywords (flags, keys).
- **Output**: Generates a JSON list of routes, sinks, and flow paths.

### 3.2 Detection Rules (`scripts/rules/*.js`)
Modular rule files loaded dynamically by `analyze.js`.
- **Structure**:
  ```javascript
  module.exports = {
    name: 'RuleName',
    type: 'sink' | 'sanitizer',
    isSink: (node) => { return { type, detail, flowPath? } | false }
  };
  ```
- **Current Rules**:
  - `rce.js`: Command Injection (`exec`, `eval`, `spawn`).
  - `sqli.js`: SQL Injection (String usage in `query`, `execute`).
  - `insecure_auth.js`: Unsigned cookie usage (`req.cookies` without verifying signature).
  - `sensitive_comments.js`: Flags (`DH{...}`) or secrets in comments.
  - `sanitization.js`: Weak filters (`replace` without global flag).

### 3.3 AI Security Auditor (`src/app/api/ai-audit/route.ts`)
- Integrates **Groq API** (Llama 3.3 / 3.1) to audit code snippets.
- **Failover Strategy**: Tries models in order: Llama 3.3 -> Llama 3.1 -> Mixtral -> Gemma.
- **Persona**: Acts as a "CTF Mentor" to provide exploit payloads and PoCs.

### 3.4 Exploit Generator (`src/components/ExploitGenerator.tsx`)
- Automatically generates **Python/Requests** scripts to exploit detected vulnerabilities.
- Pre-fills URL and parameters based on analysis data.

## 4. Directory Structure
```
/
├── scripts/
│   ├── analyze.js        # Core analysis script
│   └── rules/            # Detection plugins (.js)
├── src/
│   ├── app/
│   │   ├── page.tsx      # Main Dashboard (React Flow)
│   │   └── api/ai-audit/ # AI Proxy Route
│   ├── lib/
│   │   └── graph-transformer.ts # JSON -> Graph Node conversion
│   └── components/       # Custom Nodes, Drawers, Tools
├── test_source/          # Vulnerable code for regression testing (Express, Flask, HTML)
└── .env                  # GROQ_API_KEY
```

## 5. How to Extend
To add a new vulnerability detection:
1. Create `scripts/rules/[vuln_name].js`.
2. Implement `isSink(node)` logic (AST checking for JS, or update `analyze.js` regex for non-JS).
3. Run `npm run dev` and test with `node scripts/analyze.js [target_path]`.
