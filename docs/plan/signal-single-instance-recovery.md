# Signal Tab Single-Instance Recovery

Status: Implemented — unit verification passed; runtime UI verification pending

## Goal
Make the Signal tab recover automatically when a launched bot reports that another instance is already running, while always exposing the conflicting PID.

## Scope
- SignalProcessSupervisor launch/recovery flow.
- Known duplicate-instance messages from managed Python bots.
- Signal-tab PID/status feedback.
- Regression tests for duplicate detection and one-shot recovery.

## Required behavior
1. Start a bot normally and show its PID immediately.
2. If the child reports an existing instance with a PID, identify that PID in the console/status.
3. Validate the conflicting PID belongs to the expected managed process when Windows metadata permits.
4. Stop the conflicting process, then restart the current tab process once.
5. If automatic recovery cannot safely identify/stop the conflicting PID, leave the current process stopped and show the PID so the user can terminate it manually.
6. Never loop indefinitely on duplicate-instance errors.
7. Existing explicit Stop behavior must remain intentional and must not trigger auto-restart.

## Safety
- Windows process termination is limited to a PID reported by the managed child and validated against the expected worker where possible.
- No live MT5 trading mutation is introduced.
- No trading strategy, risk, profile identity, or authentication policy changes.
- Do not touch unrelated runtime JSON or scratch artifacts.

## Verification
- Unit-test duplicate-message parsing and recovery decisions.
- Run focused supervisor/command-construction tests.
- Run compileall on changed Python modules.
- Run git diff --check and review the final diff.
- Runtime UI verification is required before calling the feature runtime-verified.
