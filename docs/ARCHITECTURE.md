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
| Engine 5 lookback/classification/Sr-Sw-Bt/base/reverse/final signal/H15 reference | `robot-sltp-pro/pattern5_engine.py` | Tauri, publisher, web feed |
| Engine 5 market-data interface | `robot-sltp-pro/market_data_provider.py` | Pattern5 engine, parity tools |
| MT5 launch/attach policy | `services/mt5_terminal_service.py` / `services/mt5_service.py` | worker, snapshot, Pattern5 |
| Desktop Python command protocol | `robot-sltp-pro/backend_bridge.py::COMMANDS` | `src/backend-client.ts` adapter |
| Desktop selected-profile state | `robot-sltp-pro/src/App.tsx::activateProfile` | desktop panels/pollers |
| Desktop IPC framing/process | `robot-sltp-pro/src-tauri/src/lib.rs` | React backend client |
| New-profile risk/config defaults | `robot-sltp-pro/backend_bridge.py::PROFILE_CREATE_DEFAULTS` | Add Profile UI |
| Public Pattern5 persistence | Upstash keys written by `publish_pattern5_site.py` | Next server Pattern5 reader |
| Web Pattern5 transport parsing/future masking | `dashboard/src/lib/pattern5.ts` | `/engine` |
| Web weekday VIP redaction | `dashboard/src/lib/vip.ts` | `/engine` server page |
| Web rendering/evidence interaction | `dashboard/src/components/Pattern5Board.tsx` | browser |
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

1. Desktop/manual publisher requests Engine 5 through `backend_bridge.py` or `publish_pattern5_site.py`.
2. `pattern5_engine.py` resolves broker symbols and reads H4 data through `MarketDataProvider`.
3. `pattern5_engine.py` alone owns the canonical block set `H3/H6/H9/H12/H15`, preserves the existing anchor/lookback slots (`4/8/12/16/20`), and calculates classification, Sr/Sw/Bt, base signal, reverse, final signal and `h15Reference`. Pattern 5's alternating four-candle sequences (`T G T G` / `G T G T`) are classified as `Sr`; the existing base-signal behavior is preserved internally while cell presentation is classification-only.
4. Local cache `robot-sltp-pro/pattern5_cache.json` is keyed by schema, profile, week and requested symbol sequence. Cache corruption is observable and recomputed; it is not authoritative trading state.
5. Publisher writes raw Engine 5 payload plus `schemaVersion` to Upstash (`robot-sltp:public:pattern5:*`).
6. Next server reads the feed through `dashboard/src/lib/pattern5.ts` and rejects legacy payloads that do not carry the schema marker; it never repairs or reclassifies stale data in the browser.
7. `dashboard/src/lib/vip.ts` applies access redaction on the server. It does not recalculate signals.
8. `Pattern5Board.tsx` renders the supplied payload. Matrix/mobile cells currently show only `group + pattern`; BUY/SELL/base/reverse remain backend payload/evidence concerns and are not recomputed in the browser. H15 reference is formatted from backend-provided `h15Reference`; the browser does not reconstruct previous-trading-day logic.

Failure behavior: missing/malformed feed produces no actionable web signal; MT5/data failures fail closed; future days are blanked server-side before render.

### Changing an Engine 5 rule

Change `robot-sltp-pro/pattern5_engine.py` and behavior tests in `tests/test_pattern5_signal_rule.py`. Do not add the rule to React/Next code. If the payload contract changes, update both TypeScript transport types and the publisher/reader contract, then build both surfaces.

## Desktop profile/runtime flow

1. `App.tsx` loads profile configuration via `desktopBackend.profiles()`.
2. `activateProfile()` is the only desktop profile transition. It synchronously fences the active profile and clears live state before polling the new profile.
3. Snapshot polling calls `desktopBackend.snapshot(profile)`; Python uses `MT5Service.connect(allow_process_start=False)`. Selecting a profile therefore observes an already-running terminal and never launches MT5.
4. Runtime-health polling is observation-only. It does not spawn worker/Telegram processes.
5. Starting `worker_runtime.py` / `oak_enginecore.py` requires the explicit **Start Runtime** user action, which calls `runtime_ensure`.
6. Async responses are applied only when their captured profile still equals `activeProfileNameRef.current`, preventing old-profile responses from overwriting new-profile state.
7. Live equity/positions are unavailable (`—`) while no valid MT5 snapshot exists; persisted SLTP/profile configuration remains visible.

Persistence:
- profile config: `profiles.json`;
- global Telegram config: `config.json`;
- pending entry/close state: domain-managed scheduled JSON files;
- process ownership observation: lock files plus Windows process command line.

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

`dashboard/src/lib/pattern5.ts` reads transport data. `dashboard/src/lib/vip.ts` owns entitlement and signal redaction. Client components never receive unredacted weekday BUY/SELL values when access is locked.

Fact Check, Tarot and Discover are secondary Tools/Labs routes and do not own trading semantics.

## Fact Check flow

Fact Check has two result domains that share one distribution layer rather than one god object:

- Claim verification: `Text → evidence search → Gemini → FactCheckResult`; image OCR feeds extracted text into this same claim path. A pure public URL first passes `ssrf.ts` / `url-ingestion.ts`, then article extraction, and converges on the claim pipeline. The subject article is excluded from independent corroborating evidence.
- Image Authenticity: `Image → validation/container bounds → deterministic metadata → C2PA + specialist detector → detector calibration → Gemini multimodal evidence reasoning → deterministic evidence fusion → ImageAuthenticityResult`. The browser only chooses intent and transports the file; forensic policy and normalization stay server/domain-side.

Image Authenticity accepts JPEG/PNG/WEBP direct uploads up to 4 MB, with byte-signature/container/dimension/pixel bounds before provider invocation. `FACTCHECK_MEDIA_MODEL` is the single Gemini selector and defaults to `gemini-3.6-flash`; it is the reasoning layer, not the policy owner. `media-forensics-client.ts` owns the optional server-to-server boundary to `services/media-forensics/`, which uses maintained official `c2pa-python` plus the upstream UniversalFakeDetect CLIP ViT-L/14 path outside Vercel. The sidecar performs its own Pillow decode safety checks and bounded concurrency, accepts authenticated bytes only, and does not persist or log user images.

C2PA may become `verified` only when an explicit trust chain is configured and the SDK reports trusted validation. A readable manifest without trust settings is `present_unverified/not_configured`, never `invalid` merely because the trust store is absent. Only bounded provenance facts cross the boundary; full manifests and identity material do not. `detector-calibration.ts` owns UniversalFakeDetect interpretation: the upstream 0.5 class boundary yields weak directional evidence only, never a probability; unknown versions/invalid scores become `uncertain`. `media-evidence-fusion.ts` owns final precedence: verified/trusted provenance cannot be overridden by Gemini or detector output; material detector-vs-visual disagreement becomes `inconclusive` when no verified provenance exists. If the sidecar is not configured or fails within its six-second client budget, analysis continues with explicit provenance/detector limitations rather than fabricated evidence.

Raw image bytes, GPS/device identifiers, full C2PA manifests, detector scores and service secrets are not stored in Redis/public shares. `share-store.ts` persists the sanitized snapshot only; `/factcheck/[id]` and its OG route read that snapshot and never rerun OCR, C2PA, detector or Gemini. SPAI remains evaluation-only; manipulation localization/SIDA is deferred until a real verified runtime exists, so no heatmap is fabricated.

`share-store.ts` owns the 30-day Redis snapshot contract. Schema `v3` discriminates `claim` vs `media_authenticity`; legacy schema 1/2 claim records are read compatibly. `/factcheck/[id]` is read-only and renders the stored normalized result without re-running Gemini, URL ingestion, OCR or media analysis.

## Verification map

- Engine 5 behavior: `tests/test_pattern5_signal_rule.py`.
- Provider/market-data contract: `tests/test_market_data_provider.py`, parity tests.
- Desktop bridge/lifecycle: `robot-sltp-pro/test_backend_bridge.py`.
- Release version consistency: `tests/test_release_metadata.py`.
- Web production/type gate: `npm --prefix dashboard run build`.
- Desktop TypeScript/Vite gate: `npm --prefix robot-sltp-pro run build`.
- Repository CI: `.github/workflows/ci.yml`.

Before changing a rule or transition, start from the canonical owner in the table above, then follow its explicit consumers. Do not patch equivalent logic into a UI component.
