//+------------------------------------------------------------------+
//| OAK raw MT4 market-data publisher (v87)                          |
//| The EA publishes candles and a Broker clock only.  Signal rules  |
//| live in the Python core and are never calculated here.           |
//+------------------------------------------------------------------+
#property copyright "OAK Group"
#property version   "2.16"
#property strict

// MT4 WebRequest publishes through default HTTP port 80.  The local server
// still exposes :5001 separately for desktop/Bot health checks.
input string FeedBaseURL = "http://127.0.0.1/mt4-feed";
input string FeedToken = "";
input string SourceId = "mt4_ea";

long sequenceNumber = 0;
string effectiveFeedBaseURL = "";
string chartCanonicalSymbol = "";
string chartResolvedSymbol = "";
bool chartUsesCoreCanonical = false;
bool backfillPending = true;
datetime lastClockWarningAt = 0;
datetime lastBackfillAttemptAt = 0;
datetime lastBackfillLogAt = 0;
datetime lastBackfillIncompleteLogAt = 0;
datetime lastLiveTickUtc = 0;
datetime lastPublishedTickUtc = 0;

#define BACKFILL_DAYS 45
#define BACKFILL_RETRY_SECONDS 30

string ResolveFeedBaseURL()
{
   // MT4 keeps an EA's old input values on each chart after recompilation.
   // Migrate the prior v87 :5001 loopback setting automatically so existing
   // charts do not keep failing WebRequest after the server changes to :80.
   if(StringFind(FeedBaseURL, "http://127.0.0.1:") == 0)
   {
      Print("[MT4 FEED] Migrating legacy loopback FeedBaseURL to HTTP port 80.");
      return "http://127.0.0.1/mt4-feed";
   }
   return FeedBaseURL;
}

// Keep a stable JSON/database-safe key for a chart symbol that has not yet
// been added to the signal core.  Fixed-width UTF-16 hex makes punctuation
// reversible and collision-proof: EUR.USD, EUR-USD and EUR_USD cannot share
// a storage key.  The exact broker spelling remains in chartResolvedSymbol.
string FallbackCanonicalSymbol(string normalized)
{
   string fallback = "RAW_";
   for(int index = 0; index < StringLen(normalized); index++)
      fallback += StringFormat("%04X", StringGetCharacter(normalized, index));
   return fallback;
}

bool IsAsciiAlphaNumeric(int code)
{
   return (code >= 65 && code <= 90) || (code >= 48 && code <= 57);
}

// GOLD is a valid broker alias only when it is a complete token, optionally
// surrounded by broker separators such as '.', '+', '_' or '#'.  This avoids
// turning unrelated symbols such as GOLDMAN into XAUUSD.
bool IsGoldAlias(string normalized)
{
   int length = StringLen(normalized);
   int searchFrom = 0;
   while(searchFrom < length)
   {
      int position = StringFind(normalized, "GOLD", searchFrom);
      if(position < 0) return false;
      int end = position + 4;
      bool leftBoundary = position == 0 || !IsAsciiAlphaNumeric(StringGetCharacter(normalized, position - 1));
      bool rightBoundary = end >= length || !IsAsciiAlphaNumeric(StringGetCharacter(normalized, end));
      if(leftBoundary && rightBoundary) return true;
      searchFrom = end;
   }
   return false;
}

bool ResolveChartSymbol()
{
   string normalized = Symbol();
   StringToUpper(normalized);
   chartResolvedSymbol = Symbol();
   chartUsesCoreCanonical = true;

   // StringFind deliberately permits both broker prefixes and suffixes:
   // e.g. OAK.XAUUSD.a, mGBPUSD, and GBPJPY.pro all resolve correctly.
   if(StringFind(normalized, "XAUUSD") >= 0 || IsGoldAlias(normalized))
      chartCanonicalSymbol = "XAUUSD";
   else if(StringFind(normalized, "GBPUSD") >= 0)
      chartCanonicalSymbol = "GBPUSD";
   else if(StringFind(normalized, "GBPAUD") >= 0)
      chartCanonicalSymbol = "GBPAUD";
   else if(StringFind(normalized, "GBPJPY") >= 0)
      chartCanonicalSymbol = "GBPJPY";
   else if(StringFind(normalized, "GBPCAD") >= 0)
      chartCanonicalSymbol = "GBPCAD";
   else
   {
      // Publish a normalized raw symbol instead of rejecting the chart.  It
      // lets the feeder be attached to future symbols now; the collector/core
      // can opt into that symbol independently when it is ready to consume it.
      chartUsesCoreCanonical = false;
      chartCanonicalSymbol = FallbackCanonicalSymbol(normalized);
   }

   return StringLen(chartResolvedSymbol) > 0;
}

string IsoBrokerTime(datetime value)
{
   return StringFormat("%04d-%02d-%02d %02d:%02d:%02d",
                       TimeYear(value), TimeMonth(value), TimeDay(value),
                       TimeHour(value), TimeMinute(value), TimeSeconds(value));
}

string LongText(long value)
{
   return DoubleToString((double)value, 0);
}

string JsonEscape(string value)
{
   StringReplace(value, "\\", "\\\\");
   StringReplace(value, "\"", "\\\"");
   return value;
}

bool PostJson(string endpoint, string payload)
{
   string headers = "Content-Type: application/json\r\n";
   if(StringLen(FeedToken) > 0)
      headers += "X-MT4-FEED-TOKEN: " + FeedToken + "\r\n";
   char body[], response[];
   string responseHeaders;
   int length = StringToCharArray(payload, body, 0, WHOLE_ARRAY, CP_UTF8) - 1;
   if(length <= 0) return false;
   ArrayResize(body, length);
   ResetLastError();
   int status = WebRequest("POST", effectiveFeedBaseURL + endpoint, headers, 5000, body, response, responseHeaders);
   int errorCode = GetLastError();
   if(status < 200 || status >= 300)
   {
      Print("[MT4 FEED] POST failed endpoint=", endpoint, " status=", status, " error=", errorCode);
      if(status == -1 && errorCode == 5200)
      {
         Print("[MT4 FEED] WebRequest is blocked. Set FeedBaseURL to http://127.0.0.1/mt4-feed (no custom port) and allow http://127.0.0.1 in Tools > Options > Expert Advisors > Allow WebRequest for listed URL.");
      }
      return false;
   }
   return true;
}

bool ResolveBrokerOffset(datetime brokerNow, datetime utcNow, int &offsetHours)
{
   int offsetSeconds = (int)(brokerNow - utcNow);
   offsetHours = (int)MathRound((double)offsetSeconds / 3600.0);
   if(offsetHours < -14 || offsetHours > 14)
      return false;
   // TimeCurrent freezes at the last quote when the market is closed.  A
   // fresh broker clock must remain close to a whole-hour UTC offset.
   return MathAbs(offsetSeconds - (offsetHours * 3600)) <= 30;
}

bool PublishHeartbeat()
{
   sequenceNumber++;
   datetime brokerNow = TimeCurrent();
   datetime utcNow = TimeGMT();
   int offsetHours = 0;
   if(!ResolveBrokerOffset(brokerNow, utcNow, offsetHours))
   {
      if(lastClockWarningAt == 0 || utcNow - lastClockWarningAt >= 60)
      {
         Print("[MT4 FEED] Broker clock is stale/inconsistent; waiting for a live tick before publishing heartbeat or bars.");
         lastClockWarningAt = utcNow;
      }
      return false;
   }
   datetime brokerTimeUtc = brokerNow - (offsetHours * 3600);
   string payload = "{";
   payload += "\"schema_version\":2,";
   payload += "\"source_id\":\"" + JsonEscape(SourceId) + "\",";
   payload += "\"account\":\"" + IntegerToString(AccountNumber()) + "\",";
   payload += "\"server\":\"" + JsonEscape(AccountServer()) + "\",";
   payload += "\"chart_symbol\":\"" + JsonEscape(chartResolvedSymbol) + "\",";
   payload += "\"broker_time\":\"" + IsoBrokerTime(brokerNow) + "\",";
   payload += "\"broker_time_utc\":\"" + IsoBrokerTime(brokerTimeUtc) + "\",";
   payload += "\"broker_utc_offset\":" + IntegerToString(offsetHours) + ",";
   payload += "\"observed_at_utc\":\"" + IsoBrokerTime(utcNow) + "\",";
   payload += "\"last_sequence\":" + LongText(sequenceNumber);
   payload += "}";
   return PostJson("/heartbeat", payload);
}

string TimeframeName(int timeframe)
{
   if(timeframe == PERIOD_M30) return "M30";
   if(timeframe == PERIOD_H1) return "H1";
   return "H4";
}

int BackfillBars(int timeframe)
{
   // Roughly 45 calendar days of completed FX candles, including a small
   // weekend/history-loading buffer.  The actual readiness check below uses
   // timestamps rather than assuming a fixed number of trading-day bars.
   if(timeframe == PERIOD_H4) return 300;
   if(timeframe == PERIOD_H1) return 1150;
   return 2300;
}

bool HasBackfillHistory(int timeframe)
{
   int available = iBars(chartResolvedSymbol, timeframe);
   if(available <= 1) return false;
   int oldestShift = MathMin(available - 1, BackfillBars(timeframe));
   datetime oldestOpen = iTime(chartResolvedSymbol, timeframe, oldestShift);
   datetime requiredOpen = TimeCurrent() - (BACKFILL_DAYS * 86400);
   return oldestOpen > 0 && oldestOpen <= requiredOpen;
}

bool PublishBars(string canonicalSymbol, string resolvedSymbol, int timeframe, int count)
{
   int available = iBars(resolvedSymbol, timeframe);
   // Shift 0 is the currently forming candle.  The feed contract accepts
   // completed raw bars only, so never publish it as if it were complete.
   if(available <= 1) return false;
   int limit = MathMin(available - 1, count);
   string payload = "{";
   payload += "\"schema_version\":2,";
   payload += "\"source_id\":\"" + JsonEscape(SourceId) + "\",";
   payload += "\"symbol\":\"" + JsonEscape(canonicalSymbol) + "\",";
   payload += "\"resolved_symbol\":\"" + JsonEscape(resolvedSymbol) + "\",";
   payload += "\"timeframe\":\"" + TimeframeName(timeframe) + "\",";
   payload += "\"bars\":[";
   int emitted = 0;
   for(int shift = limit; shift >= 1; shift--)
   {
      datetime openAt = iTime(resolvedSymbol, timeframe, shift);
      if(openAt <= 0) continue;
      if(emitted > 0) payload += ",";
      datetime closeAt = openAt + PeriodSeconds(timeframe);
      payload += "{\"broker_open_at\":\"" + IsoBrokerTime(openAt) + "\",";
      payload += "\"broker_close_at\":\"" + IsoBrokerTime(closeAt) + "\",";
      int priceDigits = (int)MarketInfo(resolvedSymbol, MODE_DIGITS);
      payload += "\"open\":\"" + DoubleToString(iOpen(resolvedSymbol, timeframe, shift), priceDigits) + "\",";
      payload += "\"high\":\"" + DoubleToString(iHigh(resolvedSymbol, timeframe, shift), priceDigits) + "\",";
      payload += "\"low\":\"" + DoubleToString(iLow(resolvedSymbol, timeframe, shift), priceDigits) + "\",";
      payload += "\"close\":\"" + DoubleToString(iClose(resolvedSymbol, timeframe, shift), priceDigits) + "\",";
      payload += "\"tick_volume\":" + LongText(iVolume(resolvedSymbol, timeframe, shift)) + ",\"is_complete\":true}";
      emitted++;
   }
   payload += "]}";
   if(emitted <= 0) return false;
   if(!PostJson("/bars", payload)) return false;
   Print("[MT4 FEED] Bars published symbol=", canonicalSymbol,
         " timeframe=", TimeframeName(timeframe), " bars=", emitted);
   return true;
}

void LogInsufficientHistory(int timeframe)
{
   // Throttle the incomplete-backfill diagnostic to once per minute so a quiet
   // weekend or a broker that loads history slowly does not flood the Experts log.
   datetime utcNow = TimeGMT();
   if(lastBackfillIncompleteLogAt != 0 && utcNow - lastBackfillIncompleteLogAt < 60)
      return;
   lastBackfillIncompleteLogAt = utcNow;
   int available = iBars(chartResolvedSymbol, timeframe);
   int oldestShift = MathMin(available - 1, BackfillBars(timeframe));
   datetime oldestOpen = iTime(chartResolvedSymbol, timeframe, oldestShift);
   datetime requiredOpen = TimeCurrent() - (BACKFILL_DAYS * 86400);
   Print("[MT4 FEED] Backfill history insufficient symbol=", chartResolvedSymbol,
         " timeframe=", TimeframeName(timeframe),
         " available=", available,
         " oldest_open=", IsoBrokerTime(oldestOpen),
         " required_open<=", IsoBrokerTime(requiredOpen));
}

bool PublishChartBars(bool backfill)
{
   int timeframes[3] = {PERIOD_M30, PERIOD_H1, PERIOD_H4};
   bool backfillComplete = true;
   for(int t = 0; t < ArraySize(timeframes); t++)
   {
      int count = backfill ? BackfillBars(timeframes[t]) : 3;
      bool published = PublishBars(chartCanonicalSymbol, chartResolvedSymbol, timeframes[t], count);
      if(backfill && (!published || !HasBackfillHistory(timeframes[t])))
      {
         backfillComplete = false;
         LogInsufficientHistory(timeframes[t]);
      }
   }
   return !backfill || backfillComplete;
}

int OnInit()
{
   effectiveFeedBaseURL = ResolveFeedBaseURL();
   if(!ResolveChartSymbol())
   {
      Print("[MT4 FEED] Chart symbol is empty; cannot publish market data.");
      return INIT_FAILED;
   }
   if(!SymbolSelect(chartResolvedSymbol, true))
   {
      Print("[MT4 FEED] Cannot select chart symbol: ", chartResolvedSymbol);
      return INIT_FAILED;
   }
   Print("MT4 raw feed publisher v87 chart=", chartResolvedSymbol,
         " canonical=", chartCanonicalSymbol,
         " mode=", (chartUsesCoreCanonical ? "core" : "raw"),
         " endpoint=", effectiveFeedBaseURL,
         ". Attach one instance to every chart to publish.");
   EventSetTimer(3);
   Print("[MT4 FEED] Backfill bars publish immediately from History Center; heartbeat/live bars wait for the first live chart tick.");
   return INIT_SUCCEEDED;
}

void OnDeinit(const int reason)
{
   EventKillTimer();
}

void OnTimer()
{
   datetime utcNow = TimeGMT();
   // BACKFILL branch is independent of the live-tick gate.  MT4's History
   // Center already holds closed candles even while the market is closed
   // (weekend) or before the first chart tick after attach, so the 45-day
   // backfill must publish without requiring a fresh live tick.  Bar
   // timestamps come from the Broker clock via iTime()/iOpen(), never from
   // OnTick(), so no fresh tick is needed here.
   if(backfillPending &&
      (lastBackfillAttemptAt == 0 || utcNow - lastBackfillAttemptAt >= BACKFILL_RETRY_SECONDS))
   {
      lastBackfillAttemptAt = utcNow;
      if(lastBackfillLogAt == 0 || utcNow - lastBackfillLogAt >= 60)
      {
         Print("[MT4 FEED] Backfill allowed without fresh live tick.");
         lastBackfillLogAt = utcNow;
      }
      backfillPending = !PublishChartBars(true);
      if(!backfillPending)
         Print("[MT4 FEED] 45-day chart backfill is complete.");
   }
   // HEARTBEAT LIVE branch keeps the deliberate tick gate: TimeCurrent can
   // retain a weekend/terminal-start timestamp that still resembles a valid
   // UTC offset.  A heartbeat must always be caused by a chart tick observed
   // after the EA started; otherwise the Signal Bot could briefly see a false
   // CONNECTED state from a frozen Broker clock.
   if(lastLiveTickUtc <= lastPublishedTickUtc)
   {
      if(lastClockWarningAt == 0 || utcNow - lastClockWarningAt >= 60)
      {
         Print("[MT4 FEED] No fresh chart tick; waiting before publishing heartbeat or bars.");
         lastClockWarningAt = utcNow;
      }
      return;
   }
   if(!PublishHeartbeat()) return;
   lastPublishedTickUtc = lastLiveTickUtc;
   PublishChartBars(false);
}

void OnTick()
{
   // Timer owns publishing; a tick only authorizes the next timer batch.
   lastLiveTickUtc = TimeGMT();
}
//+------------------------------------------------------------------+
