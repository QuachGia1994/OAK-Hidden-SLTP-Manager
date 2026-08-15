# -*- coding: utf-8 -*-
"""Dedicated background worker entrypoint for the Tauri runtime."""
from __future__ import annotations

import argparse
import json
import os
import re
import signal
import subprocess
import sys
import threading
import time
from datetime import datetime
from pathlib import Path

from domain import i18n as _i18n
from domain.monitor_worker import MonitorWorker

ROOT = Path(__file__).resolve().parent
PROFILES_FILE = ROOT / "profiles.json"
SETTINGS_FILE = ROOT / "settings.json"


def _safe_profile_name(profile: str) -> str:
    return re.sub(r"[^\w\-]", "_", profile or "unknown")


def _pid_is_live_python(pid: int) -> bool:
    if pid <= 0:
        return False
    if os.name != "nt":
        try:
            os.kill(pid, 0)
            return True
        except OSError:
            return False
    try:
        result = subprocess.run(
            ["tasklist", "/FI", f"PID eq {pid}", "/NH"],
            capture_output=True,
            text=True,
            timeout=3,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
    except (OSError, subprocess.SubprocessError):
        return False
    output = (result.stdout or "").lower()
    return str(pid) in output and "python" in output


def _acquire_worker_lock(profile: str) -> tuple[Path, int | None]:
    path = ROOT / f"worker_{_safe_profile_name(profile)}.lock"
    if path.exists():
        try:
            old_pid = int((path.read_text(encoding="utf-8") or "0").strip())
        except (OSError, ValueError):
            old_pid = 0
        if _pid_is_live_python(old_pid) and old_pid != os.getpid():
            raise RuntimeError(f"Worker for {profile} already running (PID {old_pid})")
        try:
            path.unlink()
        except OSError:
            pass
    fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_RDWR)
    os.write(fd, str(os.getpid()).encode("utf-8"))
    return path, fd


def _release_worker_lock(path: Path, fd: int | None) -> None:
    if fd is not None:
        try:
            os.close(fd)
        except OSError:
            pass
    try:
        if path.exists() and path.read_text(encoding="utf-8").strip() == str(os.getpid()):
            path.unlink()
    except OSError:
        pass


def _load_profile(profile: str) -> dict:
    if not PROFILES_FILE.exists():
        raise RuntimeError(f"Missing {PROFILES_FILE.name}")
    data = json.loads(PROFILES_FILE.read_text(encoding="utf-8"))
    config = data.get(profile)
    if not isinstance(config, dict):
        raise RuntimeError(f"Unknown profile: {profile}")
    return {**config, "profile_name": profile}


def _load_language() -> None:
    if not SETTINGS_FILE.exists():
        return
    try:
        settings = json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
        lang = settings.get("lang")
        if lang in ("VN", "EN"):
            _i18n.CURRENT_LANG = lang
    except (OSError, ValueError, json.JSONDecodeError):
        pass


def run_worker(profile: str) -> int:
    lock_path, lock_fd = _acquire_worker_lock(profile)
    stop_event = threading.Event()

    def log(message: str) -> None:
        stamp = datetime.now().strftime("%H:%M:%S")
        print(f"[{stamp}] {message}", flush=True)

    def stop_handler(_signum, _frame) -> None:
        log("Stopping worker...")
        stop_event.set()

    try:
        _load_language()
        config = _load_profile(profile)
        signal.signal(signal.SIGINT, stop_handler)
        signal.signal(signal.SIGTERM, stop_handler)
        worker = MonitorWorker(config, log, stop_event)
        log(f"Worker Process Started: {profile} (PID {os.getpid()}, single-instance)")
        worker.start()
        while worker.is_alive():
            try:
                time.sleep(0.5)
            except KeyboardInterrupt:
                stop_event.set()
                break
        worker.join()
        return 2 if getattr(worker, "launch_failed", False) else 0
    finally:
        _release_worker_lock(lock_path, lock_fd)


def main() -> int:
    parser = argparse.ArgumentParser(description="ROBOT SLTP Tauri worker")
    parser.add_argument("--worker", action="store_true", help="Run profile monitor worker")
    parser.add_argument("--profile", required=True, help="Profile name")
    args = parser.parse_args()
    if not args.worker:
        parser.error("--worker is required")
    try:
        return run_worker(args.profile)
    except Exception as exc:
        print(f"Worker Error: {exc}", file=sys.stderr, flush=True)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
