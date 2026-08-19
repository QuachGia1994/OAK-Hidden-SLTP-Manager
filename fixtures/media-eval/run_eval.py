from __future__ import annotations

import argparse
import json
import mimetypes
import os
import pathlib
import time
import urllib.error
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


def run_case(endpoint: str, authorization: str, manifest_path: pathlib.Path, case: dict) -> dict:
    image_path = (manifest_path.parent / case["file"]).resolve()
    body, boundary = multipart(image_path, case.get("locale", "EN"))
    headers = {"Content-Type": f"multipart/form-data; boundary={boundary}"}
    if authorization:
        headers["x-api-key"] = authorization
    request = urllib.request.Request(endpoint, data=body, headers=headers, method="POST")
    started = time.monotonic()
    failure_state = None
    payload: dict = {}
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            payload = json.load(response)
    except urllib.error.HTTPError as exc:
        failure_state = f"http_{exc.code}"
        try:
            payload = json.load(exc)
        except Exception:
            payload = {}
    except Exception as exc:
        failure_state = f"transport_{type(exc).__name__}"
    latency_ms = int((time.monotonic() - started) * 1000)
    result = payload.get("result") or {}
    signals = result.get("signals") or []
    return {
        "id": case.get("id"),
        "groundTruthCategory": case.get("category"),
        "groundTruthNote": case.get("groundTruthNote"),
        "licenseNote": case.get("licenseNote"),
        "c2paState": result.get("provenance"),
        "metadataSignals": [s for s in signals if s.get("source") in {"metadata", "container"}],
        "specialistDetectors": result.get("specialistDetectors"),
        "geminiAssessment": {
            "model": result.get("model"),
            "visualSignals": [s for s in signals if s.get("source") == "visual"],
        },
        "finalOakVerdict": result.get("verdict"),
        "evidenceAgreement": result.get("evidenceAgreement"),
        "requestLatencyMs": latency_ms,
        "failureState": failure_state or (None if payload.get("ok") else payload.get("code") or "response_not_ok"),
        "limitations": result.get("limitations"),
        "shareId": payload.get("shareId"),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Run bounded OAK media-authenticity evaluation cases against a dashboard deployment.")
    parser.add_argument("--endpoint", default="http://127.0.0.1:3000/api/factcheck/media")
    parser.add_argument("--manifest", default=str(pathlib.Path(__file__).with_name("manifest.json")))
    parser.add_argument("--authorization", default=os.getenv("OAK_FACTCHECK_AUTH", ""))
    args = parser.parse_args()

    manifest_path = pathlib.Path(args.manifest).resolve()
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    cases = manifest.get("cases") or []
    if not cases:
        raise SystemExit("No eval cases configured. Add local/licensed fixture paths; dataset blobs are intentionally not committed.")

    for case in cases:
        print(json.dumps(run_case(args.endpoint, args.authorization, manifest_path, case), ensure_ascii=False, separators=(",", ":")))


if __name__ == "__main__":
    main()
