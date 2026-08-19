# OAK Media Forensics Service

Bounded sidecar for Fact Check Image Authenticity. It stays outside Vercel/Next because UniversalFakeDetect requires PyTorch/CLIP weights and a runtime that can keep the model loaded once per process.

## Runtime contract

- `GET /health`
- `GET /version`
- `POST /v1/detect/image` with raw JPEG/PNG/WEBP bytes and `Authorization: Bearer <OAK_FORENSICS_TOKEN>`.
- Max request bytes defaults to 4,000,000; max dimension 12,000; max decoded pixels 40,000,000.
- Pillow performs format, dimension, verify and full-decode checks before C2PA/model work; terminal container boundaries reject trailing polyglot payloads.
- Work is bounded by `OAK_FORENSICS_MAX_CONCURRENT` (default 2). Excess work receives `FORENSICS_BUSY` instead of building an unbounded GPU queue.
- C2PA and UniversalFakeDetect execute concurrently after validation.
- The service never writes user image bytes to disk and does not log request bodies, model scores, manifests or authorization values.
- The endpoint accepts bytes only. It has no arbitrary-URL fetch path.

## C2PA

Uses the maintained official `c2pa-python` binding (`0.37.4`, backed by `c2pa-rs`). Remote-manifest and OCSP fetches are disabled.

Semantic states are `verified`, `invalid`, `present_unverified`, `not_detected`, `verification_error`; the dashboard boundary can additionally represent `unsupported` when the runtime is not active. Trust-chain state is reported separately as `trusted`, `not_configured`, `failed`, `not_applicable` or `unknown`.

A manifest becomes `verified` only when explicit `C2PA_TRUST_ANCHORS_PEM` is configured and the SDK reports a trusted validation state. This distinction is required because c2pa-python documents that validation state can be `Invalid` when trust settings are not loaded. Therefore a readable manifest without configured trust anchors is `present_unverified/not_configured`, not `invalid`.

Only bounded facts leave the service: state, trust-chain state, claim generator, up to eight digital-source-type strings and validation-status count. Full manifests, certificate identity material and raw validation payloads are not returned to the public result.

Environment:

- `C2PA_TRUST_ANCHORS_PEM` — deployment trust anchors in PEM form.
- `C2PA_TRUST_CONFIG` — optional C2PA EKU trust policy string.

## UniversalFakeDetect

The service integrates the official CVPR 2023 UniversalFakeDetect `CLIP:ViT-L/14` path using an external upstream checkout plus `fc_weights.pth`; model weights are intentionally not committed.

Required runtime configuration:

- `UNIVFD_REPO` — local checkout of `WisconsinAIVision/UniversalFakeDetect`.
- `UNIVFD_CKPT` — path to upstream `fc_weights.pth`.

Inference reproduces upstream `CenterCrop(224)` and CLIP normalization. Upstream evaluates accuracy at a sigmoid class boundary of `0.5`; OAK uses that only as a class direction and labels it `weak` until a controlled OAK calibration set exists. The raw score is never exposed as an AI-generation probability and never reaches React, Redis or public share snapshots.

If the checkout/checkpoint/model runtime is missing, the service stays healthy and returns detector status `unavailable`; it never fabricates detector evidence.

## Deployment state

Repository integration does not imply a remote GPU deployment. OAK production activates this service only when both `FACTCHECK_FORENSICS_URL` and `FACTCHECK_FORENSICS_TOKEN` are configured on the dashboard deployment. Until then Image Authenticity continues with local validation/metadata + Gemini and explicitly records provenance/detector runtime limitations.

**SPECIALIST DETECTOR IMPLEMENTED — RUNTIME NOT ACTIVATED** unless those deployment settings point to a healthy service with the configured upstream model/checkpoint.

SPAI remains an evaluation-only candidate. SIDA/manipulation localization is deferred until a real localizer runtime is implemented and verified; OAK does not generate synthetic heatmaps.
