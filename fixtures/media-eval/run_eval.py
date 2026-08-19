from __future__ import annotations

import argparse
import json
import mimetypes
import os
import pathlib
import urllib.request
import uuid


def multipart(image_path: pathlib.Path, locale: str) -> tuple[bytes, str]:
    boundary = f"oak-{uuid.uuid4().hex}"
    mime = mimetypes.guess_type(image_path.name)[0] or "application/octet-stream"
    chunks = [
        f"--{boundary}\r\nContent-Disposition: form-data; name=\"locale\"\r\n\r\n{locale}\r\n".encode(),
        f"--{boundary}\r\nContent-Disposition: form-data; name=\"image\"; filename=\"{image_path.name}\"\r\nContent-Type: {mime}\r\n\r\n".encode(),
        image_path.read_bytes(),
        f"\r\n--{boundary}--\r\n".encode(),
    ]
    return b"".join(chunks), boundary


def main() -> None:
    parser = argparse.ArgumentParser(description="Run bounded OAK media-authenticity evaluation cases against an existing dashboard deployment.")
    parser.add_argument("--endpoint", default="http://127.0.0.1:3000/api/factcheck/media")
    parser.add_argument("--manifest", default=str(pathlib.Path(__file__).with_name("manifest.json")))
    parser.add_argument("--authorization", default=os.getenv("OAK_FACTCHECK_AUTH", ""))
    args = parser.parse_args()

    manifest_path = pathlib.Path(args.manifest).resolve()
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    cases = manifest.get("cases") or []
    if not cases:
        raise SystemExit("No eval cases configured. Add local/licensed fixture paths to manifest.json; dataset blobs are intentionally not committed.")

    for case in cases:
        image_path = (manifest_path.parent / case["file"]).resolve()
        body, boundary = multipart(image_path, case.get("locale", "EN"))
        headers = {"Content-Type": f"multipart/form-data; boundary={boundary}"}
        if args.authorization:
            headers["Authorization"] = args.authorization
        request = urllib.request.Request(args.endpoint, data=body, headers=headers, method="POST")
        with urllib.request.urlopen(request, timeout=60) as response:
            payload = json.load(response)
        result = payload.get("result") or {}
        signals = result.get("signals") or []
        output = {
            "id": case.get("id"),
            "category": case.get("category"),
            "provenance": result.get("provenance"),
            "metadataSignals": [s for s in signals if s.get("source") in {"metadata", "container"}],
            "specialistDetectors": result.get("specialistDetectors"),
            "geminiAssessment": {
                "model": result.get("model"),
                "visualSignals": [s for s in signals if s.get("source") == "visual"],
            },
            "finalOakVerdict": result.get("verdict"),
            "evidenceAgreement": result.get("evidenceAgreement"),
            "limitations": result.get("limitations"),
            "shareId": payload.get("shareId"),
        }
        print(json.dumps(output, ensure_ascii=False, separators=(",", ":")))


if __name__ == "__main__":
    main()
