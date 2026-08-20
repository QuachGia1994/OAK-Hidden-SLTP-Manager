# -*- coding: utf-8 -*-
"""Cross-process file lock backed by OS advisory byte/file locking.

The lock file is intentionally persistent. Ownership lives in the operating
system lock attached to the open file descriptor, so a crashed process releases
its lock automatically and one owner can never unlink another owner's lock.
"""
from __future__ import annotations

import os
import time

if os.name == "nt":
    import msvcrt
else:  # pragma: no cover - production runtime is Windows; CI may exercise POSIX.
    import fcntl


class FileLock:
    def __init__(self, lock_file, timeout=5):
        self.lock_file = lock_file
        self.timeout = max(0.0, float(timeout))
        self.fd = None

    def _try_lock(self) -> bool:
        if self.fd is None:
            return False
        os.lseek(self.fd, 0, os.SEEK_SET)
        if os.name == "nt":
            # msvcrt byte-range locking requires the byte to exist.
            if os.fstat(self.fd).st_size < 1:
                os.write(self.fd, b"\0")
                os.fsync(self.fd)
            os.lseek(self.fd, 0, os.SEEK_SET)
            try:
                msvcrt.locking(self.fd, msvcrt.LK_NBLCK, 1)
                return True
            except OSError:
                return False
        try:
            fcntl.flock(self.fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            return True
        except (BlockingIOError, OSError):
            return False

    def __enter__(self):
        try:
            self.fd = os.open(self.lock_file, os.O_CREAT | os.O_RDWR, 0o600)
        except OSError:
            self.fd = None
            return None

        started = time.monotonic()
        while True:
            if self._try_lock():
                return self
            if time.monotonic() - started >= self.timeout:
                os.close(self.fd)
                self.fd = None
                return None
            time.sleep(0.05)

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.fd is None:
            return
        try:
            os.lseek(self.fd, 0, os.SEEK_SET)
            if os.name == "nt":
                try:
                    msvcrt.locking(self.fd, msvcrt.LK_UNLCK, 1)
                except OSError:
                    pass
            else:  # pragma: no cover - production runtime is Windows.
                try:
                    fcntl.flock(self.fd, fcntl.LOCK_UN)
                except OSError:
                    pass
        finally:
            os.close(self.fd)
            self.fd = None
