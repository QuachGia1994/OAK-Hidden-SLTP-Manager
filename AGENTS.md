# Project agent policy

This file defines repository policy for agent-assisted work. It does not automatically select or switch the root model in a fresh chat; each session must be configured to follow these roles.

## Roles

- **Orchestrator — gpt-5.6-sol:** owns scope, the live plan, architecture, judgment, worker briefing and review, independent verification, and release decisions.
- **Default Worker — gpt-5.6-luna:** handles bounded implementation, retrieval, and test work for future stages.
- Workers inherit no context or rules. Every worker brief must name exact target paths, required rule files, constraints, acceptance criteria, and required evidence.
- The Orchestrator retains final judgment, independently reviews worker output, and verifies the repository before closing a stage.

## Coordination and safety

- Assign one writer per mutable surface; parallel work must use non-overlapping files or an explicit isolation mechanism.
- Workers must not commit, push, or deploy unless the current user explicitly delegates that exact action.
- Inspect repository state before editing and preserve all dirty or unrelated work.
- Keep changes within the current scope; do not stage, revert, clean up, or overwrite unrelated files.
