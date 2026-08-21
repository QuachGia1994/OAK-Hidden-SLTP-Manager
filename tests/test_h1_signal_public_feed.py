# -*- coding: utf-8 -*-
from __future__ import annotations

import json

import domain.h1_signal_public_feed as feed_module
from domain.h1_signal_public_feed import PUBLIC_SCHEMA, build_public_h1_feed, publish_h1_signal_state


def sample_state():
    return {
        "version": 6,
        "days": {
            "2026-08-20": {
                "symbols": {
                    "XAUUSD": {
                        "alerts": [
                            {
                                "slotHour": 16,
                                "pattern": "T G T G",
                                "patternKind": "sw4Alternating",
                                "bars": ["2026-08-20T15:00", "2026-08-20T14:00", "2026-08-20T13:00", "2026-08-20T12:00"],
                                "symbol": "XAUUSD+",
                                "profile": "Vantage",
                                "scannerBase": "AUDUSD",
                                "scannerSymbol": "AUDUSD+",
                                "baseSymbol": "GBPUSD",
                                "baseH1Signal": "BUY",
                                "baseHour": 15,
                                "baseDirection": "T",
                                "symbolH1Signal": "BUY",
                            },
                            {
                                "slotHour": 17,
                                "pattern": "T G T",
                                "patternKind": "sw3Alternating",
                            },
                        ],
                    }
                }
            }
        },
    }


def test_build_public_h1_feed_normalizes_schema6_and_skips_incomplete_rows():
    feed = build_public_h1_feed(sample_state(), "Vantage", published_at="2026-08-20T13:20:00+00:00")
    assert feed["schemaVersion"] == PUBLIC_SCHEMA == 6
    assert feed["profile"] == "Vantage"
    assert feed["hours"] == list(range(3, 18))
    assert feed["symbols"] == ["XAUUSD", "EURUSD", "AUDUSD", "USDCAD", "USDJPY"]
    xau = feed["days"]["2026-08-20"]["symbols"]["XAUUSD"]
    assert len(xau["alerts"]) == 1
    assert xau["alerts"][0] == {
        "slotHour": 16,
        "pattern": "T G T G",
        "patternKind": "sw4Alternating",
        "bars": ["2026-08-20T15:00", "2026-08-20T14:00", "2026-08-20T13:00", "2026-08-20T12:00"],
        "symbol": "XAUUSD+",
        "profile": "Vantage",
        "scannerBase": "AUDUSD",
        "scannerSymbol": "AUDUSD+",
        "baseSymbol": "GBPUSD",
        "baseSignal": "BUY",
        "baseHour": 15,
        "baseDirection": "T",
        "signal": "BUY",
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
    assert feed["schemaVersion"] == 6
    assert len(requests) == 2
    commands = [json.loads(request.data.decode("utf-8")) for request, _timeout in requests]
    assert commands[0][0:2] == ["SET", "robot-sltp:public:h1-signals:Vantage"]
    assert commands[1][0:2] == ["SET", "robot-sltp:public:h1-signals:latest"]
    assert all(timeout == 5 for _request, timeout in requests)
    alert = json.loads(commands[0][2])["days"]["2026-08-20"]["symbols"]["XAUUSD"]["alerts"][0]
    assert alert["scannerBase"] == "AUDUSD"
    assert alert["baseSymbol"] == "GBPUSD"
    assert alert["signal"] == "BUY"
    assert alert["patternKind"] == "sw4Alternating"
    assert "targetPattern" not in alert
    assert "warningKind" not in alert
    assert "scannerSignal" not in alert
