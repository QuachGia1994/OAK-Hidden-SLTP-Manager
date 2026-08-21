# ROBOT SLTP / OAK Gatekeeper Architecture

This document is the entry point for the maintained product surfaces. It describes ownership and boundaries, not every file in the repository.

## Product surfaces

- `robot-sltp-pro/`: Tauri 2 + React desktop command workstation.
- `dashboard/`: Next.js OAK Gatekeeper web shell at `oakgatekeeper.uk`.
- Python at repository root plus `domain/`, `repositories/`, `services/`: local trading/runtime domain.

Legacy NativeQt/CustomTkinter and old signal-manager surfaces are not maintained product entry points.

## Ownership map

| Concern | Canonical owner | Consumers |
| --- | --- | --- |
| Engine 5 active symbol scope | `dashboard/engine5-symbols.json` | Pattern5 engine, publisher, Tauri payload, web reader |
| Engine 5 alert-rule policy | `dashboard/engine5-alert-rules.json` | Pattern5 engine alert state machine |
| Engine 5 lookback/classification/Sr-Sw-Bt/base/reverse/final signal/H15 lifecycle/reference | `robot-sltp-pro/pattern5_engine.py` | Tauri, publisher, web feed |
| Engine 5 market-data interface | `robot-sltp-pro/market_data_provider.py` | Pattern5 engine, parity tools |
| Passive H1 Telegram pattern scanner | `domain/xau_h1_pattern_scanner.py` | `MonitorWorker`; XAUUSD/EURUSD/AUDUSD/USDCAD/USDJPY broker-suffix variants |
| Public H1 signal persistence | `domain/h1_signal_public_feed.py` | scanner owner → Upstash H1 feed → Next server reader |
| MT5 launch/attach policy | `services/mt5_terminal_service.py` / `services/mt5_service.py` | worker, snapshot, Pattern5 |
| Desktop Python command protocol | `robot-sltp-pro/backend_bridge.py::COMMANDS` | `src/backend-client.ts` adapter |
| Desktop selected-profile state | `robot-sltp-pro/src/App.tsx::activateProfile` | desktop panels/pollers |
| Desktop IPC framing/process | `robot-sltp-pro/src-tauri/src/lib.rs` | React backend client |
| New-profile risk/config defaults | `robot-sltp-pro/backend_bridge.py::PROFILE_CREATE_DEFAULTS` | Add Profile UI |
| Public Pattern5 persistence | Upstash keys written by `publish_pattern5_site.py` | Next server Pattern5 reader |
| Web Pattern5 transport parsing/future masking | `dashboard/src/lib/pattern5.ts` | `/engine` |
| Web H1 transport parsing/future masking | `dashboard/src/lib/h1-signals.ts` | `/engine` |
| Web weekday VIP redaction | `dashboard/src/lib/vip.ts` | `/engine` server page |
| Web rendering/evidence interaction | `dashboard/src/components/Pattern5Board.tsx` + `H1SignalBoard.tsx` | browser |
| Fact Check claim/URL result domain | `dashboard/src/lib/factcheck/types.ts` + `gemini.ts` | `/api/factcheck`, result/public UI |
| Fact Check URL network boundary | `dashboard/src/lib/factcheck/ssrf.ts` + `url-ingestion.ts` | `/api/factcheck` |
| Fact Check media domain/result contract | `dashboard/src/lib/factcheck/media-types.ts` | media API, fusion, result/public UI |
| Fact Check media validation/container safety | `dashboard/src/lib/factcheck/media-validate.ts` | `/api/factcheck/media` |
| Fact Check media metadata | `dashboard/src/lib/factcheck/media-metadata.ts` | media API, Gemini evidence |
| Fact Check media provenance + specialist transport | `dashboard/src/lib/factcheck/media-forensics-client.ts` + `services/media-forensics/` | media API |
| Fact Check specialist normalization/calibration | `dashboard/src/lib/factcheck/specialist-detector.ts` + `detector-calibration.ts` | forensics client, fusion |
| Fact Check media Gemini reasoning | `dashboard/src/lib/factcheck/media-gemini.ts` | media API |
| Fact Check deterministic media policy/final normalization | `dashboard/src/lib/factcheck/media-evidence-fusion.ts` | media API |
| Fact Check media public sanitization | `dashboard/src/lib/factcheck/media-sanitize.ts` | share store |
| Fact Check public persistence | `dashboard/src/lib/factcheck/share-store.ts` | claim + media public routes |
| Desktop visual tokens | `robot-sltp-pro/src/styles.css` | Tauri UI |
| Web visual tokens | `dashboard/src/app/globals.css` | Gatekeeper routes |

Transport types mirror canonical payloads in TypeScript, but they do not calculate trading semantics.

## Engine 5 flow

1. `dashboard/engine5-symbols.json` owns the active/inactive product scope. Current active scope is `GBPUSD`; `EURUSD` is temporarily disabled but remains available for explicit historical/regression calls.
2. Desktop/manual publisher requests Engine 5 through `backend_bridge.py` or `publish_pattern5_site.py`; default calculation/publishing derives from that shared active scope.
3. `pattern5_engine.py` resolves broker symbols and reads H4 data through `MarketDataProvider`.
4. `pattern5_engine.py` owns calculation semantics. Core blocks are `H3/H6/H9/H12/H15`; H15 is calculated independently with its own anchor/lookback/signal semantics and does not depend on H12 group.
5. `dashboard/engine5-alert-rules.json` is the single policy owner for H3 asset direction (`GBP/AUD/CAD=reverse`, `JPY/XAU=normal`), Sr entry minute `:11`, two-consecutive-Sr STOP threshold, block scope and alert precedence. `pattern5_engine.py` replays each trading day deterministically and emits typed, stable alert events; no alert rule is recomputed in React.
6. The Sr STOP latch begins only after the second consecutive Sr and resets on each day replay. STOP outranks later Sr entry, H3 direction and ordinary information. Alerts are advisory only; no order execution is attached.
7. Local cache `robot-sltp-pro/pattern5_cache.json` is keyed by schema, profile, week and requested symbol sequence. Schema 16 prevents reuse of conditional-H15 cache data.
8. Publisher writes schema-16 current Engine 5 payloads with `activeSymbols`, typed `alerts` and per-date `h15State` to Upstash. Existing EURUSD historical/cache records are not purged by activation changes.
9. Next server requires the current public schema, filters tables against `dashboard/engine5-symbols.json`, and masks future-day rows/alerts/state. Legacy schema-15 conditional-H15 payloads are rejected rather than reinterpreted in React.
10. `dashboard/src/lib/vip.ts` applies access redaction on the server. It does not recalculate signals or alert rules.
11. Web `Pattern5Board.tsx` and Tauri `App.tsx` render typed alert state. Presentation owns EN/VI labels only; H15 is rendered like the other independently calculated blocks.

Failure behavior: missing/malformed feed produces no actionable web signal; MT5/data failures fail closed; future days are blanked server-side before render.

### Changing an Engine 5 rule

Change `robot-sltp-pro/pattern5_engine.py` and behavior tests in `tests/test_pattern5_signal_rule.py`. Do not add the rule to React/Next code. If the payload contract changes, update both TypeScript transport types and the publisher/reader contract, then build both surfaces.

## Desktop profile/runtime flow

1. `App.tsx` loads profile configuration via `desktopBackend.profiles()`.
2. `activateProfile()` is the only desktop profile transition. It synchronously fences the active profile and clears live state before polling the new profile.
3. Snapshot polling calls `desktopBackend.snapshot(profile)`; Python uses `MT5Service.connect(allow_process_start=False)`. Selecting a profile therefore observes an already-running terminal and never launches MT5.
4. Runtime-health polling is observation-only. It does not spawn worker/Telegram processes.
5. Starting `worker_runtime.py` / `oak_enginecore.py` requires the explicit **Start Runtime** user action, which calls `runtime_ensure`.
6. Closing the Tauri application calls backend `runtime_stop_all` before the desktop backend bridge is torn down. Each configured `worker_runtime.py` receives a PID-scoped `worker_<profile>.stop` request, exits through its normal `stop_event`/`finally` cleanup path, and is force-stopped only if it does not exit within the bounded grace period. The shared `oak_enginecore.py` Telegram receiver is intentionally not stopped by this UI-close hook.
7. One worker process owns the passive H1 Telegram scanner through the existing OS-backed scanner lock. It resolves XAUUSD/EURUSD/AUDUSD/USDCAD/USDJPY suffix variants and operates only on closed H1 candles from the current broker day. XAU starts at broker H04 using H03→H02; EUR/AUD/CAD/JPY start at H03 using H02→H01. The scanner supports four pattern-local classes through H17: first-slot `TG/GT` (`SW 2 cây`); later `TGG/GTT` (`SW 3 cây thuần`); exact `TGT/GTG` (`SW 3 cây xen kẽ`) while rejecting a fourth candle that extends the sequence to `TGTG/GTGT`; and a six-candle combination whose newest three and older three are each independently `TGG/GTT` (`SW ghép 2×3 cây thuần`). The combined-six class has precedence over its embedded latest-three match and first becomes possible at H08 for XAU or H07 for FX. GBPUSD (including broker suffixes) is also read only from the current broker-day H1 chart: at scanner slot `Hn`, the first backward GBPUSD candle `H(n-1)` is the entire GBPUSD base signal (`T→BUY`, `G→SELL`), with no Pattern5 block/group dependency. Target-symbol signal is then pattern-local: `SW 3 cây thuần` follows the GBPUSD H1 signal, while `SW 2 cây`, `SW 3 cây xen kẽ`, and `SW ghép 2×3 cây thuần` reverse it. There is no daily SW/BT classification. If the required GBPUSD H(n-1) candle is missing, the pending match waits rather than falling back to another day or timeframe. Delivered slots remain persisted for replay protection; newly introduced pattern slots earlier than an already-delivered later slot may still be caught up, while an already-delivered slot can be re-enriched/reclassified without Telegram replay. Whenever normalized state changes, and once when a scanner owner first observes unchanged state, `h1_signal_public_feed.py` publishes a separate versioned H1 snapshot to Upstash; publication failure is advisory and cannot roll back Telegram/state or affect order/runtime logic. The local MT5-backed scanner remains a fallback owner only. The cloud path is `dashboard/src/app/api/h1-scanner/run/route.ts`: an authenticated GitHub Actions hourly trigger invokes a short-lived Vercel Node function, which refreshes the existing accounts-only cTrader token vault, reads current broker-day H1 through cTrader JSON/WebSocket, applies the same four pattern classes, sends Telegram, persists replay state in Upstash, and writes the same schema-2 public feed. The cloud state seeds from the existing public feed on first run so delivered local slots are not replayed during cutover. A Redis singleton lock prevents overlapping cloud invocations, and `OAK_H1_CLOUD_SCANNER_ENABLED` remains fail-closed until the local workers are stopped. Neither path executes orders or alters Engine5 active-symbol scope.
8. Async responses are applied only when their captured profile still equals `activeProfileNameRef.current`, preventing old-profile responses from overwriting new-profile state.
9. Live equity/positions are unavailable (`—`) while no valid MT5 snapshot exists; persisted SLTP/profile configuration remains visible.

Persistence:
- profile config: `profiles.json`;
- global Telegram config: `config.json`;
- pending entry/close state: domain-managed scheduled JSON files;
- process ownership observation: PID marker files plus Windows process command line; cross-process mutable-state/singleton exclusion uses OS-backed `FileLock` and never infers ownership from lock-file age.

Failure behavior:
- malformed config/lock/pending JSON is surfaced as an error; it is not converted to an empty/offline state;
- process inspection uses Windows PowerShell/CIM in one batch call and reports inspection failure in runtime health;
- MT5 snapshot failure marks only the currently selected profile offline;
- stale async results are discarded.

## Tauri IPC boundary

React calls only `robot-sltp-pro/src/backend-client.ts`. That adapter owns JSON serialization/parsing and typed command return shapes.

Rust `backend_call` owns the long-lived Python bridge process and request-id framing. Blocking pipe I/O runs inside `tauri::async_runtime::spawn_blocking`, not on the UI thread. Python command failures are returned as command errors; malformed JSON from the bridge is rejected by the TypeScript adapter.

The bridge is serialized intentionally because the Python/MT5 runtime is stateful. There is currently no hard cancellation of a Python request after it has entered a blocking pipe read; see the runtime-only risk in release notes rather than adding a timeout that cannot cancel the underlying task.

## Web access boundary

`dashboard/src/lib/pattern5.ts` and `dashboard/src/lib/h1-signals.ts` read versioned Upstash transport data. `dashboard/src/lib/vip.ts` owns entitlement and signal redaction for both feeds. H1 BUY/SELL semantics are never recalculated in React; `H1SignalBoard.tsx` only renders the scanner-published signal and opens Telegram-equivalent detail. Client components never receive unredacted weekday BUY/SELL values or raw H1 alert detail when access is locked.

Fact Check, Tarot and Discover are secondary Tools/Labs routes and do not own trading semantics.

## Fact Check flow

Fact Check has two result domains that share one distribution layer rather than one god object:

- Claim verification: `Text → evidence search → Gemini → FactCheckResult`; image OCR feeds extracted text into this same claim path. A pure public URL first passes `ssrf.ts` / `url-ingestion.ts`, then article extraction, and converges on the claim pipeline. The subject article is excluded from independent corroborating evidence.
- AI Image Detection / Image Authenticity: `Image → validation/container bounds → deterministic metadata → C2PA + enabled specialist detector registry → detector calibration → Gemini multimodal evidence reasoning → deterministic evidence fusion → ImageAuthenticityResult`. The browser exposes this explicitly as **Detect AI Image / Phát hiện ảnh AI** while keeping OCR claim checking as a separate intent; forensic policy and normalization stay server/domain-side.

Image Authenticity accepts JPEG/PNG/WEBP direct uploads up to 4 MB, with byte-signature/container/dimension/pixel bounds before provider invocation. `FACTCHECK_MEDIA_MODEL` is the single Gemini selector and defaults to `gemini-3.6-flash`; it is the reasoning layer, not the policy owner. `media-forensics-client.ts` owns the optional server-to-server boundary to `services/media-forensics/`, which uses maintained official `c2pa-python` plus the upstream UniversalFakeDetect CLIP ViT-L/14 path outside Vercel. The sidecar performs its own Pillow decode safety checks and bounded concurrency, accepts authenticated bytes only, and does not persist or log user images.

C2PA may become `verified` only when an explicit trust chain is configured and the SDK reports trusted validation. A readable manifest without trust settings is `present_unverified/not_configured`, never `invalid` merely because the trust store is absent. Only bounded provenance facts cross the boundary; full manifests and identity material do not. `specialist-detector.ts` owns the provider-neutral registry; production currently registers only UniversalFakeDetect. `detector-calibration.ts` owns its interpretation: the upstream 0.5 class boundary yields weak directional evidence only, never a probability; unknown versions/invalid scores become `uncertain`. `media-evidence-fusion.ts` owns final precedence: verified/trusted provenance cannot be overridden by Gemini or detector output; material detector/visual disagreement becomes `inconclusive`; visual-only or weak-only AI/manipulation evidence is downgraded when no live specialist/trusted provenance exists. If the sidecar is not configured or fails within its six-second client budget, analysis continues with explicit limitations rather than fabricated evidence. Candidate detector/license policy is recorded in `docs/FACTCHECK_MEDIA_DETECTORS.md`; research does not equal production activation.

Raw image bytes, GPS/device identifiers, full C2PA manifests, detector scores and service secrets are not stored in Redis/public shares. `share-store.ts` persists the sanitized snapshot only; `/factcheck/[id]` and its OG route read that snapshot and never rerun OCR, C2PA, detector or Gemini. SPAI remains evaluation-only; manipulation localization/SIDA is deferred until a real verified runtime exists, so no heatmap is fabricated.

`share-store.ts` owns the 30-day Redis snapshot contract. Schema `v3` discriminates `claim` vs `media_authenticity`; legacy schema 1/2 claim records are read compatibly. `/factcheck/[id]` is read-only and renders the stored normalized result without re-running Gemini, URL ingestion, OCR or media analysis.

## Verification map

- Engine 5 behavior: `tests/test_pattern5_signal_rule.py`.
- Provider/market-data contract: `tests/test_market_data_provider.py`, parity tests.
- Desktop bridge/lifecycle: `robot-sltp-pro/test_backend_bridge.py`.
- Release version consistency: `tests/test_release_metadata.py`.
- Web behavior/security gate: `npm --prefix dashboard run test`.
- Web production/type gate: `npm --prefix dashboard run build`.
- Desktop TypeScript/Vite gate: `npm --prefix robot-sltp-pro run build`.
- Tauri Rust compile gate: `cargo check --locked --manifest-path robot-sltp-pro/src-tauri/Cargo.toml`.
- Repository CI: `.github/workflows/ci.yml`.

Before changing a rule or transition, start from the canonical owner in the table above, then follow its explicit consumers. Do not patch equivalent logic into a UI component.
