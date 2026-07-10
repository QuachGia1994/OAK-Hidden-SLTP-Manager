# -*- coding: utf-8 -*-
"""Cross-process file lock."""
from __future__ import annotations

import os
import time

class FileLock:
    def __init__(self, lock_file, timeout=5):
        self.lock_file = lock_file
        self.timeout = timeout
        self.fd = None

    def __enter__(self):
        start_time = time.time()
        while True:
            try:
                self.fd = os.open(self.lock_file, os.O_CREAT | os.O_EXCL | os.O_RDWR)
                return self
            except FileExistsError:
                try:
                    if os.path.exists(self.lock_file):
                        if time.time() - os.path.getmtime(self.lock_file) > self.timeout:
                            os.remove(self.lock_file)
                except: pass
                if time.time() - start_time > self.timeout:
                    return None
                time.sleep(0.1)
            except:
                return None

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.fd:
            os.close(self.fd)
            try:
                os.remove(self.lock_file)
            except: pass

