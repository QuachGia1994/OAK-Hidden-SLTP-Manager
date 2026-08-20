# -*- coding: utf-8 -*-
from __future__ import annotations

import json

import domain.h1_signal_public_feed as feed_module
from domain.h1_signal_public_feed import PUBLIC_SCHEMA, build_public_h1_feed, publish_h1_signal_state


def sample_state():
    return {
        "version": 2,
        "days": {
            "2026-08-20": {
                "symbols": {
                    "AUDUSD": {
                        "alerts": [
                            {
                                "slotHour": 16,
                                "pattern": "T G G",
                                "patternKind": "sw3Pure",
                                "bars": ["2026-08-20T15:00", "2026-08-20T14:00", "2026-08-20T13:00"],
                                "symbol": "AUDUSD+",
                                "profile": "Vantage",
                                "symbolH1Signal": "SELL",
                                "gbpusdH1Signal": "SELL",
                                "gbpusdBaseHour": 15,
                                "gbpusdBaseDirection": "T",
                            },
                            {
                                "slotHour": 17,
                                "pattern": "G T G",
                                "patternKind": "sw3Alternating",
                                # Missing final symbol signal must fail closed from web feed.
                            },
                        ],
                    }
                }
            }
        },
    }


def test_build_public_h1_feed_normalizes_complete_alerts_and_skips_incomplete_rows():
    feed = build_public_h1_feed(sample_state(), "Vantage", published_at="2026-08-20T13:20:00+00:00")
    assert feed["schemaVersion"] == PUBLIC_SCHEMA == 2
    assert feed["profile"] == "Vantage"
    assert feed["hours"] == list(range(3, 18))
    assert feed["symbols"] == ["XAUUSD", "EURUSD", "AUDUSD", "USDCAD", "USDJPY"]
    aud = feed["days"]["2026-08-20"]["symbols"]["AUDUSD"]
    assert set(aud) == {"alerts"}
    assert len(aud["alerts"]) == 1
    assert aud["alerts"][0] == {
        "slotHour": 16,
        "pattern": "T G G",
        "patternKind": "sw3Pure",
        "bars": ["2026-08-20T15:00", "2026-08-20T14:00", "2026-08-20T13:00"],
        "symbol": "AUDUSD+",
        "profile": "Vantage",
        "signal": "SELL",
        "gbpusdSignal": "SELL",
        "gbpusdBaseHour": 15,
        "gbpusdBaseDirection": "T",
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
    assert feed["schemaVersion"] == 2
    assert len(requests) == 2
    commands = [json.loads(request.data.decode("utf-8")) for request, _timeout in requests]
    assert commands[0][0:2] == ["SET", "robot-sltp:public:h1-signals:Vantage"]
    assert commands[1][0:2] == ["SET", "robot-sltp:public:h1-signals:latest"]
    assert all(timeout == 5 for _request, timeout in requests)
    encoded_feed = json.loads(commands[0][2])
    alert = encoded_feed["days"]["2026-08-20"]["symbols"]["AUDUSD"]["alerts"][0]
    assert alert["signal"] == "SELL"
    assert alert["patternKind"] == "sw3Pure"
    assert "dayType" not in alert
    assert "entryTime" not in alert
