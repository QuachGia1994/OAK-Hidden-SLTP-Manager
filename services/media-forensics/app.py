from __future__ import annotations

import hmac
import io
import json
import os
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

MAX_BYTES = int(os.getenv("OAK_FORENSICS_MAX_BYTES", "4000000"))
MAX_DIMENSION = int(os.getenv("OAK_FORENSICS_MAX_DIMENSION", "12000"))
MAX_PIXELS = int(os.getenv("OAK_FORENSICS_MAX_PIXELS", "40000000"))
MAX_CONCURRENT = max(1, int(os.getenv("OAK_FORENSICS_MAX_CONCURRENT", "2")))
TOKEN = os.getenv("OAK_FORENSICS_TOKEN", "")
UNIVFD_REPO = os.getenv("UNIVFD_REPO", "")
UNIVFD_CKPT = os.getenv("UNIVFD_CKPT", "")
PORT = int(os.getenv("PORT", "8787"))
C2PA_TRUST_ANCHORS_PEM = os.getenv("C2PA_TRUST_ANCHORS_PEM", "")
C2PA_TRUST_CONFIG = os.getenv("C2PA_TRUST_CONFIG", "")

_model = None
_transform = None
_model_error: str | None = None
_model_lock = threading.Lock()
_capacity = threading.BoundedSemaphore(MAX_CONCURRENT)


def _load_univfd() -> None:
    global _model, _transform, _model_error
    if _model is not None or _model_error is not None:
        return
    with _model_lock:
        if _model is not None or _model_error is not None:
            return
        if not UNIVFD_REPO or not UNIVFD_CKPT:
            _model_error = "runtime_not_configured"
            return
        try:
            sys.path.insert(0, UNIVFD_REPO)
            import torch
            import torchvision.transforms as transforms
            from models import get_model  # type: ignore

            model = get_model("CLIP:ViT-L/14")
            state_dict = torch.load(UNIVFD_CKPT, map_location="cpu", weights_only=True)
            model.fc.load_state_dict(state_dict)
            model.eval()
            device = "cuda" if torch.cuda.is_available() else "cpu"
            model.to(device)
            _model = (model, device)
            _transform = transforms.Compose([
                transforms.CenterCrop(224),
                transforms.ToTensor(),
                transforms.Normalize(
                    mean=[0.48145466, 0.4578275, 0.40821073],
                    std=[0.26862954, 0.26130258, 0.27577711],
                ),
            ])
        except Exception as exc:
            _model_error = f"load_failed:{type(exc).__name__}"


def _has_terminal_container_boundary(image_bytes: bytes, mime: str) -> bool:
    if mime == "image/png":
        return image_bytes.endswith(b"\x00\x00\x00\x00IEND\xaeB`\x82")
    if mime == "image/jpeg":
        return image_bytes.endswith(b"\xff\xd9")
    if mime == "image/webp":
        return len(image_bytes) >= 12 and image_bytes[:4] == b"RIFF" and int.from_bytes(image_bytes[4:8], "little") + 8 == len(image_bytes)
    return False


def _validate_image(image_bytes: bytes, mime: str) -> tuple[int, int]:
    from PIL import Image, UnidentifiedImageError

    if not image_bytes or len(image_bytes) > MAX_BYTES:
        raise ValueError("invalid_size")
    if mime not in {"image/jpeg", "image/png", "image/webp"}:
        raise ValueError("unsupported_media")
    if not _has_terminal_container_boundary(image_bytes, mime):
        raise ValueError("container_boundary_invalid")

    Image.MAX_IMAGE_PIXELS = MAX_PIXELS
    try:
        with Image.open(io.BytesIO(image_bytes)) as image:
            expected = {"image/jpeg": "JPEG", "image/png": "PNG", "image/webp": "WEBP"}[mime]
            if image.format != expected:
                raise ValueError("mime_mismatch")
            width, height = image.size
            if width <= 0 or height <= 0 or width > MAX_DIMENSION or height > MAX_DIMENSION or width * height > MAX_PIXELS:
                raise ValueError("unsafe_dimensions")
            image.verify()
        # Force a full decode after verify() so truncated/corrupt payloads do not reach model inference.
        with Image.open(io.BytesIO(image_bytes)) as image:
            image.load()
    except (UnidentifiedImageError, OSError) as exc:
        raise ValueError("decode_failed") from exc
    return width, height


def _detect_univfd(image_bytes: bytes) -> dict[str, Any]:
    _load_univfd()
    if _model is None or _transform is None:
        return {
            "detector_id": "universalfakedetect",
            "version": "cvpr2023-clip-vitl14",
            "status": "unavailable",
            "reason": _model_error or "runtime_not_configured",
        }
    try:
        import torch
        from PIL import Image

        model, device = _model
        with Image.open(io.BytesIO(image_bytes)) as image:
            tensor = _transform(image.convert("RGB")).unsqueeze(0).to(device)
        with torch.no_grad():
            score = float(model(tensor).sigmoid().flatten()[0].item())
        return {
            "detector_id": "universalfakedetect",
            "version": "cvpr2023-clip-vitl14",
            "status": "ok",
            "raw_score": max(0.0, min(1.0, score)),
        }
    except Exception as exc:
        return {
            "detector_id": "universalfakedetect",
            "version": "cvpr2023-clip-vitl14",
            "status": "failed",
            "reason": f"inference_failed:{type(exc).__name__}",
        }


def _c2pa(image_bytes: bytes, mime: str) -> dict[str, Any]:
    marker = b"c2pa" in image_bytes[:2_000_000].lower() or b"content credentials" in image_bytes[:2_000_000].lower()
    try:
        from c2pa import Context, Reader

        settings: dict[str, Any] = {
            "verify": {
                "remote_manifest_fetch": False,
                "ocsp_fetch": False,
                "verify_trust": True,
                "verify_after_reading": True,
            }
        }
        trust_configured = bool(C2PA_TRUST_ANCHORS_PEM)
        if trust_configured:
            settings["trust"] = {"trust_anchors": C2PA_TRUST_ANCHORS_PEM}
            if C2PA_TRUST_CONFIG:
                settings["trust"]["trust_config"] = C2PA_TRUST_CONFIG

        ctx = Context.from_dict(settings)
        reader = Reader(mime, io.BytesIO(image_bytes), context=ctx)
        parsed = json.loads(reader.json())
        active_id = parsed.get("active_manifest")
        manifests = parsed.get("manifests") or {}
        if not active_id or active_id not in manifests:
            return {"state": "not_detected", "standard": "c2pa", "trust_chain": "not_applicable"}

        active = manifests.get(active_id) or {}
        validation = reader.get_validation_state()
        validation_results = reader.get_validation_results()
        state_name = str(validation or "").strip().lower()

        # c2pa-python explicitly documents that validation_state can be Invalid without loaded trust settings.
        # Therefore lack of configured trust is never labeled as an invalid signature/manifest.
        if not trust_configured:
            state = "present_unverified"
            trust_chain = "not_configured"
            reason = "trust_anchors_not_configured"
        elif state_name == "trusted":
            state = "verified"
            trust_chain = "trusted"
            reason = None
        elif state_name == "invalid":
            state = "invalid"
            trust_chain = "failed"
            reason = "sdk_validation_invalid"
        else:
            state = "present_unverified"
            trust_chain = "unknown"
            reason = f"sdk_validation_state:{state_name or 'unknown'}"

        actions: list[dict[str, Any]] = []
        for assertion in active.get("assertions") or []:
            if str(assertion.get("label") or "").startswith("c2pa.actions"):
                data = assertion.get("data") or {}
                if isinstance(data, dict):
                    actions.extend(data.get("actions") or [])
        source_types: list[str] = []
        for action in actions[:20]:
            if not isinstance(action, dict):
                continue
            dst = action.get("digitalSourceType") or action.get("digital_source_type")
            if isinstance(dst, str):
                source_types.append(dst[:220])

        result: dict[str, Any] = {
            "state": state,
            "standard": "c2pa",
            "trust_chain": trust_chain,
            "claim_generator": str(active.get("claim_generator") or "")[:160],
            "digital_source_types": source_types[:8],
            "validation_status_count": min(100, len(validation_results or [])),
        }
        if reason:
            result["reason"] = reason
        return result
    except Exception as exc:
        return {
            "state": "present_unverified" if marker else "verification_error",
            "standard": "c2pa" if marker else None,
            "trust_chain": "unknown",
            "reason": f"c2pa_reader:{type(exc).__name__}",
        }


def analyze(image_bytes: bytes, mime: str) -> dict[str, Any]:
    started = time.monotonic()
    width, height = _validate_image(image_bytes, mime)
    with ThreadPoolExecutor(max_workers=2, thread_name_prefix="oak-forensics") as pool:
        c2pa_future = pool.submit(_c2pa, image_bytes, mime)
        detector_future = pool.submit(_detect_univfd, image_bytes)
        c2pa_result = c2pa_future.result()
        detector_result = detector_future.result()
    return {
        "ok": True,
        "technical": {"width": width, "height": height},
        "c2pa": c2pa_result,
        "detectors": [detector_result],
        "latency_ms": int((time.monotonic() - started) * 1000),
    }


class Handler(BaseHTTPRequestHandler):
    server_version = "OAKMediaForensics/2.0"

    def log_message(self, fmt: str, *args: Any) -> None:
        # Never log request bodies, image bytes, model scores, manifests, or authorization values.
        sys.stderr.write("[media-forensics] " + (fmt % args) + "\n")

    def _json(self, status: int, payload: dict[str, Any]) -> None:
        body = json.dumps(payload, separators=(",", ":")).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        if self.path == "/health":
            _load_univfd()
            self._json(200, {
                "ok": True,
                "detector": "ready" if _model is not None else "unavailable",
                "c2pa": "c2pa-python",
                "max_concurrent": MAX_CONCURRENT,
            })
            return
        if self.path == "/version":
            self._json(200, {
                "service": "oak-media-forensics",
                "version": "2",
                "detector": "universalfakedetect/cvpr2023-clip-vitl14",
                "calibration_contract": "upstream-0.5-class-boundary/no-probability",
            })
            return
        self._json(404, {"ok": False})

    def do_POST(self) -> None:
        if self.path != "/v1/detect/image":
            self._json(404, {"ok": False})
            return
        supplied = self.headers.get("Authorization", "")
        expected = f"Bearer {TOKEN}" if TOKEN else ""
        if not expected or not hmac.compare_digest(supplied, expected):
            self._json(401, {"ok": False, "code": "UNAUTHORIZED"})
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            length = 0
        if length <= 0 or length > MAX_BYTES:
            self._json(413, {"ok": False, "code": "IMAGE_TOO_LARGE"})
            return
        mime = self.headers.get("Content-Type", "application/octet-stream").split(";", 1)[0].strip().lower()
        if mime not in {"image/jpeg", "image/png", "image/webp"}:
            self._json(415, {"ok": False, "code": "UNSUPPORTED_MEDIA"})
            return
        if not _capacity.acquire(blocking=False):
            self._json(503, {"ok": False, "code": "FORENSICS_BUSY"})
            return
        try:
            image_bytes = self.rfile.read(length)
            if len(image_bytes) != length:
                self._json(400, {"ok": False, "code": "TRUNCATED_BODY"})
                return
            try:
                result = analyze(image_bytes, mime)
            except ValueError as exc:
                self._json(400, {"ok": False, "code": str(exc).upper()[:80]})
                return
            self._json(200, result)
        finally:
            _capacity.release()


def main() -> None:
    ThreadingHTTPServer(("0.0.0.0", PORT), Handler).serve_forever()


if __name__ == "__main__":
    main()
