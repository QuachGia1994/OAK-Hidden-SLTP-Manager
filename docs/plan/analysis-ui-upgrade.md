# Analysis UI upgrade

## Goal
Upgrade NativeQt Accounts, Performance, History, and News views for faster trading-oriented interpretation without changing trading execution or data ownership.

## Scope
- Accounts: visual account stats, clearer live-position table, broker symbol preservation.
- Performance: primary/secondary KPI hierarchy and professional equity/drawdown chart presentation.
- History: summary metrics, symbol/type filters, clearer realized P/L presentation.
- News: impact/currency filters, impact hierarchy, explicit cache/broker-day state.
- Preserve existing read-only data sources and NativeQt architecture.

## Out of scope
- Telegram commands or scheduled-close execution.
- MT5 order execution or terminal lifecycle.
- Profile routing/start/stop ownership.
- Existing unrelated working-tree files.

## Acceptance criteria
- UI renders with live/open-position data unchanged in meaning.
- Existing performance calculations remain the source of truth.
- History and News filters operate locally without mutating data.
- Empty/error states remain explicit.
- Focused tests and full pytest pass.
- NativeQt runtime smoke verifies all four Analysis tabs after restart.

## Verification
- `py_compile` for NativeQt shell.
- Focused Analysis tests.
- Full pytest.
- Diff review and side-effect scan.
- Runtime visual acceptance on Accounts, Performance, History, News.
