# -*- coding: utf-8 -*-
from __future__ import annotations

import json
from types import SimpleNamespace

import domain.h1_signal_public_feed as feed_module
from domain.h1_signal_public_feed import PUBLIC_SCHEMA, build_public_h1_feed, publish_h1_signal_state


def sample_state():
    return {
        "version": 2,
        "days": {
            "2026-08-20": {
                "symbols": {
                    "AUDUSD": {
                        "dayType": "SW",
                        "firstSignalHour": 3,
                        "alerts": [
                            {
                                "slotHour": 16,
                                "pattern": "T G G",
                                "bars": ["2026-08-20T15:00", "2026-08-20T14:00", "2026-08-20T13:00"],
                                "symbol": "AUDUSD+",
                                "profile": "Vantage",
                                "symbolH1Signal": "BUY",
                                "dayType": "SW",
                                "gbpusdH1Signal": "SELL",
                                "gbpusdBaseHour": 15,
                                "gbpusdBaseDirection": "T",
                                "gbpusdBlockHour": 15,
                                "gbpusdGroup": "Sw",
                            },
                            {
                                "slotHour": 17,
                                "pattern": "G T T",
                                "dayType": "SW",
                                # Missing final symbol signal must fail closed from the web feed.
                            },
                        ],
                    }
                }
            }
        },
    }


def test_build_public_h1_feed_normalizes_complete_alerts_and_skips_incomplete_rows():
    feed = build_public_h1_feed(sample_state(), "Vantage", published_at="2026-08-20T13:20:00+00:00")
    assert feed["schemaVersion"] == PUBLIC_SCHEMA == 1
    assert feed["profile"] == "Vantage"
    assert feed["hours"] == list(range(3, 18))
    assert feed["symbols"] == ["XAUUSD", "EURUSD", "AUDUSD", "USDCAD", "USDJPY"]
    aud = feed["days"]["2026-08-20"]["symbols"]["AUDUSD"]
    assert aud["dayType"] == "SW"
    assert aud["firstSignalHour"] == 3
    assert len(aud["alerts"]) == 1
    alert = aud["alerts"][0]
    assert alert == {
        "slotHour": 16,
        "pattern": "T G G",
        "bars": ["2026-08-20T15:00", "2026-08-20T14:00", "2026-08-20T13:00"],
        "symbol": "AUDUSD+",
        "profile": "Vantage",
        "signal": "BUY",
        "dayType": "SW",
        "gbpusdSignal": "SELL",
        "gbpusdBaseHour": 15,
        "gbpusdBaseDirection": "T",
        "gbpusdBlockHour": 15,
        "gbpusdGroup": "Sw",
    }


def test_publish_h1_signal_state_writes_profile_and_latest_keys(monkeypatch):
    requests = []

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

        def read(self):
            return b'{"result":"OK"}'

    def fake_urlopen(request, timeout):
        requests.append((request, timeout))
        return FakeResponse()

    monkeypatch.setenv("UPSTASH_REDIS_REST_URL", "https://redis.example.test")
    monkeypatch.setenv("UPSTASH_REDIS_REST_TOKEN", "token")
    monkeypatch.setattr(feed_module, "urlopen", fake_urlopen)

    feed = publish_h1_signal_state(sample_state(), "Vantage")
    assert feed["schemaVersion"] == 1
    assert len(requests) == 2
    commands = [json.loads(request.data.decode("utf-8")) for request, _timeout in requests]
    assert commands[0][0:2] == ["SET", "robot-sltp:public:h1-signals:Vantage"]
    assert commands[1][0:2] == ["SET", "robot-sltp:public:h1-signals:latest"]
    assert all(timeout == 5 for _request, timeout in requests)
    encoded_feed = json.loads(commands[0][2])
    alert = encoded_feed["days"]["2026-08-20"]["symbols"]["AUDUSD"]["alerts"][0]
    assert alert["signal"] == "BUY"
    assert "entryTime" not in alert
