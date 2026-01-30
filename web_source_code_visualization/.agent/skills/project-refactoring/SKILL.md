---
name: Project Refactoring
description: A skill for systematic code improvements, cleanup, and architectural enhancements.
---

# Project Refactoring Skill

This skill helps you clean up technical debt, improve code structure, and ensure the project remains maintainable.

## Capabilities
- **Identify Dead Code**: Find and remove unused files or functions.
- **Standardize Patterns**: Ensure consistent coding style across new and old modules.
- **Optimize Performance**: Spot bottlenecks or inefficient logic.

## Workflow

1.  **Assessment**:
    - Read `PROJECT_STATUS.md` or `task.md` to understand current context.
    - specialized tools like `fd` (find) and `rg` (grep) to survey the codebase.

2.  **Safety Check**:
    - Before deleting or renaming, verify references using `grep_search`.
    - Create a plan (using `task_boundary` or `implementation_plan.md`) if the change affects multiple files.

3.  **Execution**:
    - Refactor small chunks at a time.
    - Verify after each significant change.
    - **Duplicate Prevention**: Actively look for file duplication (e.g., `e.py` vs `app.py`) and merge/delete.

4.  **Documentation**:
    - Update `RULE_GUIDE.md` or `README.md` if architectural patterns change.

## Specific Targets in This Project
- **Test Scripts**: Ensure no `test_*.py` files are left in `backend/` after a task is done.
- **Rule Duplication**: Ensure `custom_security.yaml` does not have duplicate Rule IDs.
- **Parser Logic**: Keep `backend/core/parser/` clean and testable.
