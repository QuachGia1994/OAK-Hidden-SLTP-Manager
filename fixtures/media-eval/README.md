# Media authenticity evaluation harness

`manifest.json` defines the required failure-mode categories without committing benchmark/image blobs. Add only locally licensed fixtures to `cases` using the documented `id`, `category`, `file`, and `locale` fields, then run:

```text
python fixtures/media-eval/run_eval.py --endpoint https://<deployment>/api/factcheck/media
```

If the target deployment requires server API authorization, provide the `DASHBOARD_API_KEY` value with `--authorization` or `OAK_FACTCHECK_AUTH`; the harness sends it only as `x-api-key` and never prints it.

The harness prints one JSON object per case containing ground-truth category/note, bounded C2PA state, metadata/container signals, normalized specialist-detector evidence, Gemini model + visual observations, final OAK verdict, evidence agreement, request latency, failure state, limitations, and share ID. It deliberately does not compute a synthetic accuracy percentage and does not retain image bytes.

Required categories are defined in `manifest.json`: camera photo, screenshot, social-media recompression, edited real photo, AI-generated photo, AI illustration, AI screenshot, AI JPEG recompression, metadata-stripped real, metadata-stripped AI, partial AI inpainting, and Photoshop composite. Dataset blobs are never vendored merely because a benchmark is public; follow `docs/FACTCHECK_MEDIA_DETECTORS.md` for repository/checkpoint/dataset license gates.
