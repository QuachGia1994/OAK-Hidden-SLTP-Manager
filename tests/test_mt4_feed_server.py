import os
import tempfile
import unittest
from datetime import datetime, timezone
from unittest.mock import patch
from mt4_feed_test_environment import install_isolated_mt4_feed_database

install_isolated_mt4_feed_database()

import mt4_feed_server
from repositories.mt4_feed_store import MT4FeedStore


class TestMT4FeedServer(unittest.TestCase):
    def setUp(self):
        self.temp_db = tempfile.NamedTemporaryFile(delete=False, suffix=".db")
        self.temp_db.close()
        self.store = MT4FeedStore(db_path=self.temp_db.name)
        self.original_store = mt4_feed_server.feed_store
        mt4_feed_server.feed_store = self.store
        with mt4_feed_server.feed_error_lock:
            mt4_feed_server.last_feed_error = None
        self.client = mt4_feed_server.app.test_client()

    def tearDown(self):
        mt4_feed_server.feed_store = self.original_store
        self.store.close()
        if os.path.exists(self.temp_db.name):
            os.unlink(self.temp_db.name)

    @staticmethod
    def _completed_bar():
        return {
            "broker_open_at": "2026-08-01 13:30:00",
            "broker_close_at": "2026-08-01 14:00:00",
            "open": "2400.10",
            "high": "2401.20",
            "low": "2399.90",
            "close": "2400.80",
            "tick_volume": 42,
            "is_complete": True,
        }

    def test_heartbeat_and_bars_round_trip(self):
        heartbeat = {
            "schema_version": 2,
            "source_id": "ea-test",
            "broker_time": "2026-08-01T14:00:00",
            "broker_time_utc": "2026-08-01T11:00:00",
            "broker_utc_offset": 3,
            "observed_at_utc": datetime.now(timezone.utc).isoformat(),
            "last_sequence": 1,
        }
        response = self.client.post("/mt4-feed/heartbeat", json=heartbeat)
        self.assertEqual(response.status_code, 200)

        payload = {
            "schema_version": 2,
            "source_id": "ea-test",
            "symbol": "XAUUSD",
            "resolved_symbol": "XAUUSD",
            "timeframe": "M30",
            "bars": [self._completed_bar()],
        }
        response = self.client.post("/mt4-feed/bars", json=payload)
        self.assertEqual(response.status_code, 200)
        response = self.client.get(
            "/mt4-feed/bars?symbol=XAUUSD&timeframe=M30&start=2026-08-01%2013:00:00&end=2026-08-01%2014:00:00"
        )
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertEqual(data["count"], 1)
        self.assertEqual(data["bars"][0]["close_exact"], "2400.80")

    def test_incomplete_or_wrong_schema_is_rejected(self):
        response = self.client.post("/mt4-feed/heartbeat", json={"schema_version": 1})
        self.assertEqual(response.status_code, 400)

    def test_health_exposes_the_last_local_ingest_error_until_that_endpoint_recovers(self):
        response = self.client.post("/mt4-feed/heartbeat", json={"schema_version": 1})
        self.assertEqual(response.status_code, 400)
        health = self.client.get("/mt4-feed/health").get_json()
        self.assertEqual(health["data_state"], "disconnected")
        self.assertEqual(health["last_feed_error"]["endpoint"], "heartbeat")
        self.assertEqual(health["last_feed_error"]["message"], "schema_version must be 2")

        heartbeat = {
            "schema_version": 2,
            "source_id": "ea-test",
            "broker_time": "2026-08-01T14:00:00",
            "broker_time_utc": "2026-08-01T11:00:00",
            "broker_utc_offset": 3,
            "observed_at_utc": datetime.now(timezone.utc).isoformat(),
            "last_sequence": 1,
        }
        self.assertEqual(self.client.post("/mt4-feed/heartbeat", json=heartbeat).status_code, 200)
        self.assertNotIn("last_feed_error", self.client.get("/mt4-feed/health").get_json())
        response = self.client.post(
            "/mt4-feed/bars",
            json={"schema_version": 2, "symbol": "XAUUSD", "timeframe": "M30", "bars": [{"is_complete": False}]},
        )
        self.assertEqual(response.status_code, 400)

    def test_backfill_bars_alone_keep_feed_disconnected_until_a_heartbeat(self):
        """Weekend backfill publishes history bars without a live tick, but the
        health endpoint must stay 'disconnected' (Signal Bot stays blocked from
        start) until a fresh heartbeat arrives."""
        payload = {
            "schema_version": 2,
            "source_id": "ea-test",
            "symbol": "XAUUSD",
            "resolved_symbol": "XAUUSD",
            "timeframe": "M30",
            "bars": [self._completed_bar()],
        }
        response = self.client.post("/mt4-feed/bars", json=payload)
        self.assertEqual(response.status_code, 200)

        health = self.client.get("/mt4-feed/health").get_json()
        self.assertEqual(health["data_state"], "disconnected")

        heartbeat = {
            "schema_version": 2,
            "source_id": "ea-test",
            "broker_time": "2026-08-01T14:00:00",
            "broker_time_utc": "2026-08-01T11:00:00",
            "broker_utc_offset": 3,
            "observed_at_utc": datetime.now(timezone.utc).isoformat(),
            "last_sequence": 1,
        }
        self.assertEqual(self.client.post("/mt4-feed/heartbeat", json=heartbeat).status_code, 200)
        self.assertEqual(self.client.get("/mt4-feed/health").get_json()["data_state"], "connected")

    def test_accepts_prefixed_and_suffixed_future_symbol(self):
        payload = {
            "schema_version": 2,
            "source_id": "ea-test",
            "symbol": "oak.#us30.cash",
            "resolved_symbol": "OAK.#US30.cash.pro",
            "timeframe": "M30",
            "bars": [self._completed_bar()],
        }
        self.assertEqual(self.client.post("/mt4-feed/bars", json=payload).status_code, 200)

        response = self.client.get(
            "/mt4-feed/bars",
            query_string={
                "symbol": "oak.#us30.cash",
                "timeframe": "M30",
                "start": "2026-08-01 13:00:00",
                "end": "2026-08-01 14:00:00",
            },
        )
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertEqual(data["symbol"], "OAK.#US30.CASH")
        self.assertEqual(data["count"], 1)
        self.assertEqual(data["bars"][0]["resolved_mt4_symbol"], "OAK.#US30.CASH.PRO")

    def test_rejects_empty_symbol_but_keeps_timeframes_strict(self):
        payload = {
            "schema_version": 2,
            "source_id": "ea-test",
            "symbol": "",
            "timeframe": "M30",
            "bars": [self._completed_bar()],
        }
        self.assertEqual(self.client.post("/mt4-feed/bars", json=payload).status_code, 400)
        self.assertEqual(
            self.client.get("/mt4-feed/bars?symbol=&timeframe=M30").status_code,
            400,
        )
        self.assertEqual(
            self.client.get("/mt4-feed/bars?symbol=BTCUSD&timeframe=D1").status_code,
            400,
        )

    def test_feed_token_is_enforced_when_configured(self):
        heartbeat = {
            "schema_version": 2,
            "source_id": "ea-test",
            "broker_time": "2026-08-01T14:00:00",
            "broker_time_utc": "2026-08-01T11:00:00",
            "broker_utc_offset": 3,
            "observed_at_utc": datetime.now(timezone.utc).isoformat(),
            "last_sequence": 1,
        }
        with patch.dict(os.environ, {"MT4_FEED_TOKEN": "secret"}, clear=False):
            self.assertEqual(self.client.post("/mt4-feed/heartbeat", json=heartbeat).status_code, 401)
            response = self.client.post(
                "/mt4-feed/heartbeat",
                json=heartbeat,
                headers={"X-MT4-FEED-TOKEN": "secret"},
            )
        self.assertEqual(response.status_code, 200)

    def test_loopback_health_bypasses_token_and_redacts_account_metadata(self):
        heartbeat = {
            "schema_version": 2,
            "source_id": "ea-test",
            "account": "sensitive-account",
            "server": "sensitive-server",
            "broker_time": "2026-08-01T14:00:00",
            "broker_time_utc": "2026-08-01T11:00:00",
            "broker_utc_offset": 3,
            "observed_at_utc": datetime.now(timezone.utc).isoformat(),
            "last_sequence": 1,
        }
        with patch.dict(os.environ, {"MT4_FEED_TOKEN": "secret"}, clear=False):
            self.assertEqual(
                self.client.post(
                    "/mt4-feed/heartbeat",
                    json=heartbeat,
                    headers={"X-MT4-FEED-TOKEN": "secret"},
                ).status_code,
                200,
            )
            health = self.client.get("/mt4-feed/health")

        self.assertEqual(health.status_code, 200)
        returned = health.get_json()["heartbeat"]
        self.assertNotIn("account", returned)
        self.assertNotIn("server", returned)


if __name__ == "__main__":
    unittest.main()
