# -*- coding: utf-8 -*-
from __future__ import annotations

import json

import domain.h1_signal_public_feed as feed_module
from domain.h1_signal_public_feed import PUBLIC_SCHEMA, build_public_h1_feed, publish_h1_signal_state


def sample_state():
    return {
        "version": 10,
        "days": {
            "2026-08-20": {
                "symbols": {
                    "XAUUSD": {
                        "blockedSlots": [],
                        "alerts": [
                            {
                                "slotHour": 6,
                                "pattern": "G T T",
                                "patternKind": "sw3Pure",
                                "bars": ["2026-08-20T05:00", "2026-08-20T04:00", "2026-08-20T03:00"],
                                "symbol": "XAUUSD+",
                                "profile": "Vantage",
                                "scannerBase": "AUDUSD",
                                "scannerSymbol": "AUDUSD+",
                                "baseSymbol": "GBPUSD",
                                "baseH1Signal": "BUY",
                                "baseHour": 5,
                                "baseDirection": "T",
                                "symbolH1Signal": "BUY",
                                "postSignalInverted": False,
                                "postSignalRule": "none",
                                "tradeAllowed": True,
                                "blockedByPureSlot": None,
                            },
                            {"slotHour": 7, "pattern": "T G T", "patternKind": "obsolete"},
                        ],
                    }
                }
            }
        },
    }


def test_build_public_h1_feed_normalizes_schema7_without_repeat_metadata():
    feed = build_public_h1_feed(sample_state(), "Vantage", published_at="2026-08-20T13:20:00+00:00")
    assert feed["schemaVersion"] == PUBLIC_SCHEMA == 7
    assert feed["signalRuleVersion"] == 4
    assert feed["profile"] == "Vantage"
    assert feed["hours"] == list(range(3, 18))
    assert feed["symbols"] == ["XAUUSD", "EURUSD", "AUDUSD", "USDCAD", "USDJPY"]
    xau = feed["days"]["2026-08-20"]["symbols"]["XAUUSD"]
    assert len(xau["alerts"]) == 1
    alert = xau["alerts"][0]
    assert alert["patternKind"] == "sw3Pure"
    assert "previousPureSlot" not in alert
    assert alert["signal"] == "BUY"
    assert alert["postSignalInverted"] is False
    assert alert["postSignalRule"] == "none"
    assert alert["tradeAllowed"] is True
    assert alert["blockedByPureSlot"] is None
    assert xau["blockedSlots"] == []
    assert "sourceSignal" not in alert
    assert "postCheckApplied" not in alert


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
    assert feed["schemaVersion"] == 7
    assert feed["signalRuleVersion"] == 4
    assert len(requests) == 2
    commands = [json.loads(request.data.decode("utf-8")) for request, _timeout in requests]
    assert commands[0][0:2] == ["SET", "robot-sltp:public:h1-signals:Vantage"]
    assert commands[1][0:2] == ["SET", "robot-sltp:public:h1-signals:latest"]
    published = json.loads(commands[0][2])
    xau = published["days"]["2026-08-20"]["symbols"]["XAUUSD"]
    alert = xau["alerts"][0]
    assert alert["scannerBase"] == "AUDUSD"
    assert alert["baseSymbol"] == "GBPUSD"
    assert "previousPureSlot" not in alert
    assert alert["signal"] == "BUY"
    assert alert["postSignalRule"] == "none"
    assert alert["tradeAllowed"] is True
    assert alert["blockedByPureSlot"] is None
    assert xau["blockedSlots"] == []
