from pathlib import Path
from unittest.mock import patch

import worker_runtime


def test_stop_request_targets_exact_worker_pid(tmp_path: Path):
    with patch.object(worker_runtime, "ROOT", tmp_path), patch.object(worker_runtime.os, "getpid", return_value=123):
        stop_path = worker_runtime._stop_request_path("Vantage")
        stop_path.write_text("123", encoding="utf-8")
        assert worker_runtime._consume_stop_request("Vantage") is True
        assert not stop_path.exists()


def test_stale_stop_request_does_not_stop_new_worker(tmp_path: Path):
    with patch.object(worker_runtime, "ROOT", tmp_path), patch.object(worker_runtime.os, "getpid", return_value=456):
        stop_path = worker_runtime._stop_request_path("Vantage")
        stop_path.write_text("123", encoding="utf-8")
        assert worker_runtime._consume_stop_request("Vantage") is False
        assert not stop_path.exists()
