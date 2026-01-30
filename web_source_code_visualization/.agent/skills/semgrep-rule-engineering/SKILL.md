---
name: Semgrep Rule Engineering
description: A specialized skill for adding new vulnerability samples, debugging false positives, and tuning Semgrep rules using Taint Analysis.
---

# Semgrep Rule Engineering Skill

This skill guides you through the process of adding new vulnerability samples (learning materials), diagnosing detection issues, and refining Semgrep security rules.

## Capabilities
- **Add New Sample**: Create vulnerable code snippets in `plob/` to teach specific vulnerability classes.
- **Tune Rules**: Adjust `custom_security.yaml` to detect new patterns or fix false positives.
- **Verify Detection**: Create and run specialized test scripts to ensure high precision.

## Workflow

### 1. Add New Vulnerability Sample
When the user asks to "add a [VULN_TYPE] sample" or "fix an issue with [VULN_TYPE]":

1.  **Analyze the Request**:
    - Determine the vulnerability type (e.g., SQLi, XSS, Auth Bypass).
    - Identify the target level (e.g., `LEVEL 1`, `새싹`).

2.  **Create Sample Structure**:
    - Create directory: `plob/[LEVEL]/[PROBLEM_NAME]/`
    - Create `app.py`: Write a minimal Flask application that exhibits the vulnerability.
    - Create `metadata.json`: Define the expected findings (Rule ID, Line Number, Severity).
    - **CRITICAL**: Do NOT create duplicate files like `app_test.py` or `.bak`. Keep it clean.

3.  **Analyze Taint Flow**:
    - **Source**: Where does input come from? (`request.args`, `request.cookies`)
    - **Sink**: Where does it execute dangerously? (`execute`, `eval`, `return`)
    - **Sanitizer**: Is there any validation? (`int()`, `escape()`)

### 2. Verify & Tune (The Loop)

1.  **Create Test Script**:
    - Create `backend/test_[PROBLEM_NAME].py`.
    - Use `test_rule_precision.test_sample` to scan just that directory.
    - Print detailed findings (Rule ID, Line, Code).

2.  **Run & Observe**:
    - Run the script: `python backend/test_[PROBLEM_NAME].py`
    - **False Positive?** -> Add the safe function to `pattern-sanitizers` in `custom_security.yaml`.
    - **False Negative?** -> Add the missing function to `pattern-sinks` or `pattern-sources`.
    - **Wrong Rule?** -> Create a new rule if the logic is unique (e.g., `commented-out-auth-logic`).

3.  **Clean Up**:
    - Once verified, DELETE the test script (`backend/test_[PROBLEM_NAME].py`).
    - Update `task.md` with completion status.

## Common Patterns & Fixes

- **SQL Injection**:
    - If `f-string` is used, ensure `sqli-taint-flask` sink covers it.
    - If `query_db(...)` is used safely elsewhere, add it as a sanitizer to *other* rules (like XSS) if it causes FPs.
- **Reflected XSS**:
    - Sink should strictly be `make_response` or `return`.
    - Sanitizers must include `render_template` (Jinja2 auto-escapes).
- **Auth Bypass**:
    - Look for "checking input against hardcoded string" patterns.
    - Beware of sanitizers like `session.get()` being flagged as sources if configured incorrectly.

## Rules of Engagement
- **Precision First**: Better to miss a tricky case than to flood the user with 100 false alarms.
- **Documentation**: Always explain *why* a detected item is a False Positive to the user before fixing it.
