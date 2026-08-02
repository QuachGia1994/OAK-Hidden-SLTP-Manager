"""Guard the v87 MT4 EA endpoint and chart-symbol ingestion contract."""
from pathlib import Path
import unittest


SOURCE = Path(__file__).resolve().parents[1] / "MT4_Data_Feeder.mq4"


class MT4DataFeederSourceTests(unittest.TestCase):
    def test_v87_endpoint_and_chart_symbol_resolution_are_present(self):
        source = SOURCE.read_text(encoding="utf-8")

        self.assertIn('input string FeedBaseURL = "http://127.0.0.1/mt4-feed";', source)
        self.assertIn("default HTTP port 80", source)
        self.assertIn("bool ResolveChartSymbol()", source)
        self.assertIn("chartResolvedSymbol = Symbol();", source)
        self.assertIn("StringFind deliberately permits both broker prefixes and suffixes", source)
        self.assertIn('StringFind(normalized, "XAUUSD") >= 0', source)
        self.assertIn('StringFind(normalized, "GBPUSD") >= 0', source)
        self.assertIn('StringFind(normalized, "GBPAUD") >= 0', source)
        self.assertIn('StringFind(normalized, "GBPJPY") >= 0', source)
        self.assertIn('StringFind(normalized, "GBPCAD") >= 0', source)
        self.assertIn("Backfill bars publish immediately from History Center; heartbeat/live bars wait for the first live chart tick.", source)
        self.assertIn("Attach one instance to every chart to publish.", source)

    def test_unknown_chart_symbols_publish_a_safe_raw_fallback_instead_of_failing_init(self):
        source = SOURCE.read_text(encoding="utf-8")

        self.assertIn("string FallbackCanonicalSymbol(string normalized)", source)
        self.assertIn('string fallback = "RAW_";', source)
        self.assertIn('StringFormat("%04X", StringGetCharacter(normalized, index))', source)
        self.assertNotIn("StringSetCharacter(fallback, index, 95)", source)
        self.assertIn("chartCanonicalSymbol = FallbackCanonicalSymbol(normalized);", source)
        self.assertIn("chartUsesCoreCanonical = false;", source)
        self.assertNotIn("Unsupported chart symbol", source)
        self.assertIn("return StringLen(chartResolvedSymbol) > 0;", source)

    def test_gold_alias_requires_token_boundaries_instead_of_an_arbitrary_substring(self):
        source = SOURCE.read_text(encoding="utf-8")

        self.assertIn("bool IsGoldAlias(string normalized)", source)
        self.assertIn('StringFind(normalized, "GOLD", searchFrom)', source)
        self.assertIn("bool leftBoundary", source)
        self.assertIn("bool rightBoundary", source)
        self.assertIn('StringFind(normalized, "XAUUSD") >= 0 || IsGoldAlias(normalized)', source)
        self.assertNotIn('StringFind(normalized, "GOLD") >= 0', source)

    def test_webrequest_permission_failure_has_an_actionable_no_custom_port_remedy(self):
        source = SOURCE.read_text(encoding="utf-8")

        self.assertIn("int errorCode = GetLastError();", source)
        self.assertIn("status == -1 && errorCode == 5200", source)
        self.assertIn("http://127.0.0.1/mt4-feed (no custom port)", source)
        self.assertIn("allow http://127.0.0.1 in Tools > Options > Expert Advisors", source)
        self.assertNotIn("MessageBox(", source)

    def test_legacy_chart_input_is_migrated_to_the_no_port_endpoint(self):
        source = SOURCE.read_text(encoding="utf-8")

        self.assertIn("string ResolveFeedBaseURL()", source)
        self.assertIn('StringFind(FeedBaseURL, "http://127.0.0.1:") == 0', source)
        self.assertIn('return "http://127.0.0.1/mt4-feed";', source)
        self.assertIn("effectiveFeedBaseURL = ResolveFeedBaseURL();", source)
        self.assertIn('WebRequest("POST", effectiveFeedBaseURL + endpoint', source)

    def test_stale_broker_clock_skips_heartbeat_and_bars_until_a_live_tick_returns(self):
        source = SOURCE.read_text(encoding="utf-8")

        self.assertIn("bool ResolveBrokerOffset(datetime brokerNow, datetime utcNow, int &offsetHours)", source)
        self.assertIn("MathAbs(offsetSeconds - (offsetHours * 3600)) <= 30", source)
        self.assertIn("Broker clock is stale/inconsistent", source)
        self.assertIn("waiting for a live tick before publishing heartbeat or bars", source)
        self.assertIn("if(!PublishHeartbeat()) return;", source)
        self.assertIn("PublishChartBars(false);", source)

    def test_terminal_start_cannot_publish_a_frozen_weekend_clock_before_a_live_tick(self):
        source = SOURCE.read_text(encoding="utf-8")

        self.assertIn("datetime lastLiveTickUtc = 0;", source)
        self.assertIn("datetime lastPublishedTickUtc = 0;", source)
        self.assertIn("Backfill bars publish immediately from History Center; heartbeat/live bars wait for the first live chart tick.", source)
        self.assertIn("if(lastLiveTickUtc <= lastPublishedTickUtc)", source)
        self.assertIn("No fresh chart tick; waiting before publishing heartbeat or bars.", source)
        self.assertIn("lastPublishedTickUtc = lastLiveTickUtc;", source)
        self.assertIn("lastLiveTickUtc = TimeGMT();", source)

    def test_startup_backfill_waits_for_45_days_of_completed_chart_history(self):
        source = SOURCE.read_text(encoding="utf-8")

        self.assertIn("#define BACKFILL_DAYS 45", source)
        self.assertIn("#define BACKFILL_RETRY_SECONDS 30", source)
        self.assertIn("if(timeframe == PERIOD_H4) return 300;", source)
        self.assertIn("if(timeframe == PERIOD_H1) return 1150;", source)
        self.assertIn("return 2300;", source)
        self.assertIn("bool HasBackfillHistory(int timeframe)", source)
        self.assertIn("TimeCurrent() - (BACKFILL_DAYS * 86400)", source)
        self.assertIn("backfillPending = !PublishChartBars(true);", source)
        self.assertIn("utcNow - lastBackfillAttemptAt >= BACKFILL_RETRY_SECONDS", source)

    def test_backfill_publishes_without_a_live_tick_but_heartbeat_stays_gated(self):
        """Backfill must not depend on lastLiveTickUtc/OnTick(); the heartbeat live
        gate must remain untouched so the feed stays 'disconnected' until a real tick."""
        source = SOURCE.read_text(encoding="utf-8")

        # Backfill branch runs on its own timer gate (backfillPending + retry),
        # independent of lastLiveTickUtc.
        self.assertIn("backfillPending = !PublishChartBars(true);", source)
        backfill_start = source.index("void OnTimer()")
        backfill_gate = source.find("if(backfillPending &&", backfill_start)
        tick_gate = source.find("if(lastLiveTickUtc <= lastPublishedTickUtc)", backfill_start)
        self.assertNotEqual(backfill_gate, -1)
        self.assertNotEqual(tick_gate, -1)
        # The backfill branch must be evaluated before (or independent of) the
        # live-tick gate, so it can publish on a quiet weekend/market-closed.
        self.assertLess(backfill_gate, tick_gate)

        # The heartbeat live gate is intentionally kept for freshness semantics.
        self.assertIn("No fresh chart tick; waiting before publishing heartbeat or bars.", source)
        self.assertIn("lastPublishedTickUtc = lastLiveTickUtc;", source)
        self.assertIn("lastLiveTickUtc = TimeGMT();", source)
        self.assertIn("PublishChartBars(false);", source)

    def test_backfill_runs_without_a_live_tick_and_logs_diagnostics(self):
        """Backfill must not depend on lastLiveTickUtc/OnTick(); the heartbeat live
        gate must remain untouched so the feed stays 'disconnected' until a real tick."""
        source = SOURCE.read_text(encoding="utf-8")
        self.assertIn("Backfill allowed without fresh live tick.", source)
        self.assertIn("45-day chart backfill is complete.", source)
        self.assertIn("Bars published symbol=", source)
        self.assertIn("Backfill history insufficient symbol=", source)
        self.assertIn("LogInsufficientHistory(int timeframe)", source)
        self.assertIn("lastBackfillLogAt", source)
        self.assertIn("lastBackfillIncompleteLogAt", source)

    def test_v87_ea_has_no_manual_per_symbol_inputs_or_legacy_endpoint(self):
        source = SOURCE.read_text(encoding="utf-8")

        self.assertNotIn("input string XauUsdSymbol", source)
        self.assertNotIn("input string GbpUsdSymbol", source)
        self.assertNotIn("/mt4_data", source)
        self.assertNotIn("LongToString", source)
        self.assertNotIn("127.0.0.1:5001/mt4-feed", source)


if __name__ == "__main__":
    unittest.main()
