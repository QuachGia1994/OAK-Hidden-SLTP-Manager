# Account-Bound Mutation Safety

Status: Implemented — verification passed

## Goal
Every MT5 broker-state mutation requires explicit `path`, `login_id`, and `server`, with the live terminal/account matching the profile before the broker send.

## Implemented
- Central `validate_mt5_mutation_session()` requires path + login + server and validates the live terminal/account immediately before send.
- `send_mutation_idempotent()` and `send_order_idempotent()` require and enforce `profile_config`.
- Legacy `send_order_with_retry()` is also fenced despite having no production callers.
- Monitor, copy, pending, service-close, and entry callers now pass their profile configuration.
- Execution gateway uses the same mutation identity fence.
- Execution-capable partial identity (login XOR server) now fails closed.
- Read-only path-only profile behavior remains unchanged.

## Verification
- Option-B focused regression gate: 71 passed.
- compileall on changed production modules: PASS.
- git diff --check: PASS.
- AST production mutation-call audit: every `send_mutation_idempotent` / `send_order_idempotent` caller carries `profile_config`.
- No live broker mutations performed in this implementation phrase.

## Migration
No real login/server values were invented or written to `profiles.json`. Existing mutation-capable profiles without identity will fail closed until operator configuration migration supplies `login_id` + `server`.

## Constraints
Unrelated `d_direction_history.json` and `stock_recommendation.json` remain untouched. No commit, push, or deploy performed.
