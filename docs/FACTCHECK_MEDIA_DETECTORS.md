# OAK Gatekeeper — Media detector gate

Updated: 2026-08-19

This document separates research candidates from code/models that actually execute in the OAK production path. A public GitHub repository is not sufficient evidence of commercial-use permission or production readiness.

| Candidate | Repository | Code license observed | Checkpoint / dataset constraints | OAK disposition |
| --- | --- | --- | --- | --- |
| UniversalFakeDetect | WisconsinAIVision/UniversalFakeDetect | MIT | `fc_weights.pth` is distributed in the upstream repository; no separate checkpoint terms were found in the repo. Evaluation datasets retain their own terms. | Production specialist #1 adapter. Runtime requires an external checkout + checkpoint and a host capable of keeping CLIP ViT-L/14 loaded. |
| AIDE | shilinyan99/AIDE | MIT | Published checkpoints exist. The associated Chameleon dataset is explicitly academic-research-only and prohibits commercial use. | Research/eval only. Chameleon must never enter OAK commercial production, fixtures, training, or repository. |
| SAFE | Ouxiang-Li/SAFE | Apache-2.0 | Checkpoint is published; upstream benchmark datasets retain separate licenses. | Best candidate for a second whole-image specialist, but not promoted: no controlled OAK bake-off currently demonstrates complementary value sufficient to justify another model/runtime. |
| AI-GenBench | MI-BioLab/AI-GenBench | BSD-3-Clause | Benchmark combines datasets with source-specific licenses; those licenses must be checked per dataset. | Benchmark/reference only, not a production dependency. |
| MediaEval 2026 SID | mever-team/mediaeval2026-sid | Challenge/reference repository; dataset terms are separate | Challenge/test data is governed by usage agreements and source terms. | Evaluation/reference only; no challenge data is committed. |
| IAPL | liyih/IAPL | License not sufficiently established by the reviewed public material for production promotion | Checkpoints are published externally; underlying evaluation datasets include separately licensed sources such as Chameleon/GenImage. | Research only until code/checkpoint license and OAK complementarity are verified. |
| PROBE-AIGI-Detection | Amamiya-C/PROBE-AIGI-Detection | License not sufficiently established by the reviewed public material for production promotion | Model weights are published; separate checkpoint terms were not established in this stage. | Research/failure-analysis only. |
| SIDA | hzlsaber/SIDA | License not sufficiently established by the reviewed public material for production promotion | Requires large language/vision models plus SAM-style localization assets with their own terms and substantial runtime. | Manipulation-localization research only. No heatmap/mask is exposed unless a real localizer executes. |

## Promotion rule

A detector is added to `SPECIALIST_DETECTOR_REGISTRY` only after all four conditions are satisfied: production-compatible license, reproducible checkpoint, bounded runtime, and controlled OAK evaluation showing complementary value. Correlated output that merely adds latency is rejected.

Current production registry contains only `universalfakedetect`. SAFE is intentionally not registered because no controlled licensed fixture set is present yet, so there is no factual basis to claim it improves OAK over UniversalFakeDetect.

## SynthID

The reviewed official Google interfaces expose SynthID verification to supported Google/Gemini user experiences, but this stage did not find a documented public image-verification API that OAK can call from the current server environment. OAK therefore has no SynthID detector adapter and does not scan pixels/strings as a substitute.

Status: **SynthID verification unavailable through current public integration.**

## Runtime truth

The repository contains a reproducible, authenticated sidecar contract and a registry-backed UniversalFakeDetect adapter. A detector is only called `active` after `/health`, `/version`, and a controlled `/v1/detect/image` inference prove that the model is loaded on the deployed runtime. Source integration alone is never treated as runtime activation.

As of 2026-08-19, UniversalFakeDetect is active on the user's Windows i9-9900K CPU runtime behind a dedicated Cloudflare Tunnel. Production introspection reports the forensics service healthy, specialist detector active, and `specialistDevice=cpu`. This is an operational CPU host, not a GPU deployment; PC/tunnel outages must remain an explicit degraded mode.
