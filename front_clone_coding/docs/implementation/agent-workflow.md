# Agent Workflow

This project uses an explicit multi-step agent workflow for non-trivial requests.

## Default Flow

`Research -> Plan -> Implement -> Test`

- `Research`
  - Use `repo_mapper` or another read-only exploration pass when the user asks for research, the affected area is unclear, or the codebase must be grounded before editing.
  - Research output should summarize the current implementation shape, affected modules, and source-of-truth files.

- `Plan`
  - Use the `planner` agent for complex features, refactors, architecture work, or any multi-file change that would otherwise leave decisions to the implementer.
  - The planner must not write code.
  - The planner output should be decision-complete and should include:
    - goal and success criteria
    - affected subsystems
    - ordered implementation steps
    - required tests and validation
    - assumptions and public contract changes

- `Implement`
  - Use GPT-5.3-Codex workers for implementation.
  - Recommended worker routing:
    - `crawler_worker` for crawl/runtime/scope behavior
    - `pipeline_worker` for processors, manifests, scaffold, and output flow
    - `ui_worker` for dashboard and API contracts
  - Implementation handoffs should include:
    - objective
    - constraints
    - success criteria
    - affected files or subsystems
    - the approved plan

- `Test`
  - Use the GPT-5.3-Codex `test_worker` for regression coverage, focused verification, and contract checks.
  - The test handoff should include:
    - what changed
    - expected behavior
    - required commands
    - known risks to target

## When To Start With Planner

Start with `planner` when any of the following is true:

- the request spans multiple subsystems
- the user asks for a roadmap, plan, or design
- the change affects a public contract or generated output shape
- the safest implementation order is not obvious
- the work involves both product and technical tradeoffs

## Explicit Prompt Templates

### Research Request

```text
Research this request before planning.
Goal:
Constraints:
Success criteria:
Relevant files/modules:
What is still unknown:
```

### Planner Request

```text
Create a decision-complete implementation plan.
Goal:
Constraints:
Success criteria:
Relevant files/modules:
Research required: yes/no
Public contracts that may change:
```

### Implementation / Test Handoff

```text
Implement or verify this approved plan.
Goal:
Constraints:
Success criteria:
Relevant files/modules:
Approved plan:
Validation required:
```

## Expected Artifacts

- Research summary or grounded findings
- Planner output with ordered implementation steps
- Implementation summary with changed areas
- Test summary with commands run and remaining risks
