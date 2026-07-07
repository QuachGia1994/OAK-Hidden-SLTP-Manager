# -*- coding: utf-8 -*-
"""AppController - orchestrates all services for the desktop app."""
import threading
from services.mt5_service import MT5Service
from services.telegram_service import TelegramService
from oak_logger import setup_logger

log = setup_logger("controller")


class AppController:
    """Central controller that manages service lifecycle."""

    def __init__(self, config):
        self._config = config
        self._mt5 = MT5Service(path=config.get("mt5_path"))
        self._telegram = TelegramService(
            token=config.get("telegram_token", ""),
            chat_id=config.get("telegram_chat_id", 0),
        )
        self._running = False
        self._threads = []

    @property
    def mt5(self):
        return self._mt5

    @property
    def telegram(self):
        return self._telegram

    @property
    def is_running(self):
        return self._running

    def start(self):
        """Start all services."""
        if self._running:
            return
        self._running = True
        log.info("AppController starting...")

        # Connect MT5
        if not self._mt5.connect():
            log.error("MT5 connection failed")

        log.info("AppController started")

    def stop(self):
        """Stop all services gracefully."""
        if not self._running:
            return
        self._running = False
        log.info("AppController stopping...")

        # Disconnect MT5
        self._mt5.disconnect()

        # Wait for threads
        for t in self._threads:
            t.join(timeout=5)
        self._threads.clear()

        log.info("AppController stopped")

    def get_status(self):
        """Get overall system status."""
        return {
            "mt5_connected": self._mt5.is_connected,
            "telegram_configured": self._telegram.is_configured,
            "running": self._running,
        }
