# Media authenticity evaluation harness

`manifest.json` defines the required failure-mode categories without committing benchmark/image blobs. Add only locally licensed fixtures to `cases` using the documented `id`, `category`, `file`, and `locale` fields, then run:

```text
python fixtures/media-eval/run_eval.py --endpoint https://<deployment>/api/factcheck/media
```

If the target deployment requires an API authorization header, provide it with `--authorization` or `OAK_FACTCHECK_AUTH`.

The harness prints one JSON object per case containing bounded provenance state, metadata/container signals, normalized specialist detector evidence, Gemini model + visual observations, final OAK verdict, evidence agreement, limitations, and share ID. It deliberately does not compute a synthetic accuracy percentage and does not retain image bytes.

Required categories: real camera JPEG, screenshot, social-media recompressed real, edited/resaved real, AI-generated, recompressed AI, screenshot of AI, metadata-stripped real, metadata-stripped AI. GenImage and RAID are reference datasets only and are not vendored. SPAI is evaluation-only; SIDA/manipulation localization remains deferred until a real verified runtime exists.
