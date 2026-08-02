//+------------------------------------------------------------------+
//| OAK raw MT4 multi-symbol market-data publisher (v88)             |
//|                                                                  |
//| One instance publishes the full 5-symbol x 3-timeframe matrix:   |
//|   XAUUSD, GBPUSD, GBPAUD, GBPJPY, GBPCAD  (configurable)         |
//|   M30, H1, H4                          (configurable)            |
//|                                                                  |
//| The EA publishes completed candles + a Broker clock only. Signal |
//| rules live in the Python core and are never calculated here.     |
//| The attached chart symbol is used only as the heartbeat clock.   |
//+------------------------------------------------------------------+
#property copyright "OAK Group"
#property version   "3.00"
#property strict

// Feed matrix inputs (a single EA instance publishes every combination).
input string FeedSymbols = "XAUUSD,GBPUSD,GBPAUD,GBPJPY,GBPCAD";
input string FeedTimeframes = "M30,H1,H4";
input int BackfillDays = 60;
input bool AutoSelectSymbols = true;
input bool OpenChartsForHistoryWarmup = true;

// MT4 WebRequest publishes through default HTTP port 80.  The local server
// still exposes :5001 separately for desktop/Bot health checks.
input string FeedBaseURL = "http://127.0.0.1/mt4-feed";
input string FeedToken = "";

#define MAX_FEED_SYMBOLS 16
#define MAX_FEED_TIMEFRAMES 6
#define BACKFILL_RETRY_SECONDS 10
#define WARMUP_OPEN_RETRY_SECONDS 60

long sequenceNumber = 0;
string effectiveFeedBaseURL = "";
string effectiveSourceId = "";

int feedSymbolCount = 0;
string feedSymbolsCanonical[];
string feedSymbolsResolved[];
bool feedSymbolsCore[];

int feedTimeframeCount = 0;
int feedTimeframes[];

// Per (symbol, timeframe) chart-warmup bookkeeping, sized symbolCount*tfCount.
string openedChartsSymbols[];
int openedChartsTimeframes[];
bool openedChartsDone[];
datetime openedChartsLastAt[];

string chartResolvedSymbol = "";
bool backfillPending = true;
bool backfillComplete = false;
datetime lastBackfillAttemptAt = 0;
datetime lastBackfillLogAt = 0;
datetime lastBackfillIncompleteLogAt = 0;
datetime lastLiveTickUtc = 0;
datetime lastPublishedTickUtc = 0;
datetime lastClockWarningAt = 0;

//+------------------------------------------------------------------+
//| String / parsing helpers                                         |
//+------------------------------------------------------------------+
int SplitCsv(string text, string &parts[])
{
   int count = 0;
   int length = StringLen(text);
   int start = 0;
   while(start <= length)
   {
      int comma = StringFind(text, ",", start);
      if(comma < 0) comma = length;
      string item = StringSubstr(text, start, comma - start);
      StringTrimLeft(item);
      StringTrimRight(item);
      if(StringLen(item) > 0)
      {
         count++;
         ArrayResize(parts, count);
         parts[count - 1] = item;
      }
      if(comma >= length) break;
      start = comma + 1;
   }
   return count;
}

bool ContainsCanonical(string token)
{
   // Keep the feed list free of unknown tokens and duplicates.
   for(int index = 0; index < feedSymbolCount; index++)
      if(feedSymbolsCanonical[index] == token) return true;
   return false;
}

bool IsAsciiAlphaNumeric(int code)
{
   return (code >= 65 && code <= 90) || (code >= 48 && code <= 57);
}

bool IsCompleteToken(string normalized, string token)
{
   // The canonical token must be delimited by non-alphanumeric characters so
   // GBPUSD inside GBPUSDC (or XAUUSD inside XAUUSDM) is never matched.
   int position = StringFind(normalized, token);
   if(position < 0) return false;
   int end = position + StringLen(token);
   bool leftBoundary = position == 0 || !IsAsciiAlphaNumeric(StringGetCharacter(normalized, position - 1));
   bool rightBoundary = end >= StringLen(normalized) || !IsAsciiAlphaNumeric(StringGetCharacter(normalized, end));
   return leftBoundary && rightBoundary;
}

int ParseTimeframe(string name)
{
   if(name == "M30") return PERIOD_M30;
   if(name == "H1") return PERIOD_H1;
   if(name == "H4") return PERIOD_H4;
   return -1;
}

string TimeframeName(int timeframe)
{
   if(timeframe == PERIOD_M30) return "M30";
   if(timeframe == PERIOD_H1) return "H1";
   if(timeframe == PERIOD_H4) return "H4";
   return IntegerToString(timeframe);
}

int BackfillBars(int timeframe)
{
   // Roughly BackfillDays of completed candles (including weekend/history
   // loading buffer).  The readiness check uses timestamps, not bar counts.
   int tradingDays = BackfillDays + 5;
   if(timeframe == PERIOD_H4) return tradingDays * 6;
   if(timeframe == PERIOD_H1) return tradingDays * 24;
   return tradingDays * 48;
}

//+------------------------------------------------------------------+
//| Stable source identity                                           |
//+------------------------------------------------------------------+
string SymbolSetHash()
{
   // FNV-1a 32-bit fingerprint of the feed matrix.  The offset basis does not
   // fit int32, so the state must be unsigned to avoid the truncation warning.
   uint hash = 2166136261;
   string seed = FeedSymbols + "|" + FeedTimeframes;
   for(int index = 0; index < StringLen(seed); index++)
   {
      hash = hash ^ (uint)StringGetCharacter(seed, index);
      hash = hash * 16777619;
   }
   return IntegerToString((int)(hash & 0x7FFFFFFF));
}

string BuildSourceId()
{
   return "MT4_FEED_V88:" + AccountServer() + ":" + IntegerToString(AccountNumber()) + ":" + SymbolSetHash();
}

//+------------------------------------------------------------------+
//| Symbol resolution                                                |
//+------------------------------------------------------------------+
string SymbolCandidate(string canonical, int variant)
{
   // 0 exact, then common broker prefixes/suffixes.
   if(variant == 0) return canonical;
   if(variant == 1) return "m" + canonical;
   if(variant == 2) return canonical + ".a";
   if(variant == 3) return canonical + ".m";
   if(variant == 4) return canonical + "m";
   if(variant == 5) return canonical + ".i";
   if(variant == 6) return canonical + ".c";
   return canonical;
}

bool TrySelectSymbol(string symbol)
{
   if(!SymbolSelect(symbol, true)) return false;
   return (int)MarketInfo(symbol, MODE_DIGITS) > 0;
}

string ResolveBrokerSymbol(string canonical)
{
   if(!AutoSelectSymbols) return canonical;
   if(TrySelectSymbol(canonical)) return canonical;
   for(int variant = 1; variant <= 6; variant++)
   {
      string candidate = SymbolCandidate(canonical, variant);
      if(TrySelectSymbol(candidate)) return candidate;
   }
   // Scan MarketWatch for a delimited token match (broker prefix/suffix).
   string normCanonical = canonical;
   StringToUpper(normCanonical);
   int total = SymbolsTotal(true);
   for(int index = 0; index < total; index++)
   {
      string name = SymbolName(index, true);
      string normName = name;
      StringToUpper(normName);
      if(StringFind(normName, normCanonical) >= 0 && IsCompleteToken(normName, normCanonical))
         if(TrySelectSymbol(name)) return name;
   }
   return "";
}

//+------------------------------------------------------------------+
//| HTTP / JSON publishing                                           |
//+------------------------------------------------------------------+
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
   if(offsetHours < -14 || offsetHours > 14) return false;
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
   payload += "\"source_id\":\"" + JsonEscape(effectiveSourceId) + "\",";
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

//+------------------------------------------------------------------+
//| Per symbol/timeframe publishing & backfill                       |
//+------------------------------------------------------------------+
bool HasBackfillHistory(string resolved, int timeframe)
{
   int available = iBars(resolved, timeframe);
   if(available <= 1) return false;
   int oldestShift = MathMin(available - 1, BackfillBars(timeframe));
   datetime oldestOpen = iTime(resolved, timeframe, oldestShift);
   datetime requiredOpen = TimeCurrent() - (BackfillDays * 86400);
   return oldestOpen > 0 && oldestOpen <= requiredOpen;
}

bool PublishBarsFor(int symbolIndex, int tfIndex, int count)
{
   string canonical = feedSymbolsCanonical[symbolIndex];
   string resolved = feedSymbolsResolved[symbolIndex];
   int timeframe = feedTimeframes[tfIndex];
   int available = iBars(resolved, timeframe);
   // Shift 0 is the currently forming candle.  The feed contract accepts
   // completed raw bars only, so never publish it as if it were complete.
   if(available <= 1) return false;
   int limit = MathMin(available - 1, count);
   string payload = "{";
   payload += "\"schema_version\":2,";
   payload += "\"source_id\":\"" + JsonEscape(effectiveSourceId) + "\",";
   payload += "\"symbol\":\"" + JsonEscape(canonical) + "\",";
   payload += "\"resolved_symbol\":\"" + JsonEscape(resolved) + "\",";
   payload += "\"timeframe\":\"" + TimeframeName(timeframe) + "\",";
   payload += "\"bars\":[";
   int emitted = 0;
   for(int shift = limit; shift >= 1; shift--)
   {
      datetime openAt = iTime(resolved, timeframe, shift);
      if(openAt <= 0) continue;
      if(emitted > 0) payload += ",";
      datetime closeAt = openAt + PeriodSeconds(timeframe);
      payload += "{\"broker_open_at\":\"" + IsoBrokerTime(openAt) + "\",";
      payload += "\"broker_close_at\":\"" + IsoBrokerTime(closeAt) + "\",";
      int priceDigits = (int)MarketInfo(resolved, MODE_DIGITS);
      payload += "\"open\":\"" + DoubleToString(iOpen(resolved, timeframe, shift), priceDigits) + "\",";
      payload += "\"high\":\"" + DoubleToString(iHigh(resolved, timeframe, shift), priceDigits) + "\",";
      payload += "\"low\":\"" + DoubleToString(iLow(resolved, timeframe, shift), priceDigits) + "\",";
      payload += "\"close\":\"" + DoubleToString(iClose(resolved, timeframe, shift), priceDigits) + "\",";
      payload += "\"tick_volume\":" + LongText(iVolume(resolved, timeframe, shift)) + ",\"is_complete\":true}";
      emitted++;
   }
   payload += "]}";
   if(emitted <= 0) return false;
   if(!PostJson("/bars", payload)) return false;
   Print("[MT4 FEED] Bars published symbol=", canonical,
         " timeframe=", TimeframeName(timeframe), " bars=", emitted);
   return true;
}

int ChartIndex(string resolved, int timeframe)
{
   for(int index = 0; index < feedSymbolCount * feedTimeframeCount; index++)
      if(StringCompare(openedChartsSymbols[index], resolved) == 0 && openedChartsTimeframes[index] == timeframe)
         return index;
   return -1;
}

void WarmupChart(string resolved, int timeframe)
{
   // Only cells registered in openedCharts* (populated in OnInit) may auto-open.
   // An untracked cell (e.g. an unresolved symbol) must never open a chart, and
   // even tracked cells open exactly once, retrying at most every 60s on error.
   int index = ChartIndex(resolved, timeframe);
   if(index < 0) return;
   if(openedChartsDone[index]) return;   // already opened, do not spam
   datetime utcNow = TimeGMT();
   if(openedChartsLastAt[index] != 0 && utcNow - openedChartsLastAt[index] < WARMUP_OPEN_RETRY_SECONDS)
      return;                                          // throttle reopen attempts
   openedChartsLastAt[index] = utcNow;
   long chartId = ChartOpen(resolved, timeframe);
   if(chartId > 0)
   {
      openedChartsDone[index] = true;
      Print("[MT4 FEED] Warmup opened chart id=", LongText(chartId),
            " symbol=", resolved, " timeframe=", TimeframeName(timeframe));
   }
   else
   {
      Print("[MT4 FEED] Warmup ChartOpen failed symbol=", resolved,
            " timeframe=", TimeframeName(timeframe), " error=", GetLastError());
   }
}

void LogInsufficientHistory(string resolved, int timeframe)
{
   // Throttle the incomplete-backfill diagnostic to once per minute so a quiet
   // weekend or a broker that loads history slowly does not flood the Experts log.
   datetime utcNow = TimeGMT();
   if(lastBackfillIncompleteLogAt != 0 && utcNow - lastBackfillIncompleteLogAt < 60) return;
   lastBackfillIncompleteLogAt = utcNow;
   int available = iBars(resolved, timeframe);
   int required = BackfillBars(timeframe);
   Print("[MT4 FEED] Missing history symbol=", resolved,
         " timeframe=", TimeframeName(timeframe),
         " available=", available,
         " required=", required);
}

bool PublishAllBars(bool backfill)
{
   bool allComplete = true;
   for(int s = 0; s < feedSymbolCount; s++)
   {
      string resolved = feedSymbolsResolved[s];
      if(StringLen(resolved) == 0)
      {
         Print("[MT4 FEED] Missing history symbol=", feedSymbolsCanonical[s],
               " timeframe=* available=0 required=1 (unresolved broker symbol)");
         allComplete = false;
         continue;
      }
      for(int t = 0; t < feedTimeframeCount; t++)
      {
         int timeframe = feedTimeframes[t];
         int count = backfill ? BackfillBars(timeframe) : 3;
         bool published = PublishBarsFor(s, t, count);
         if(backfill && (!published || !HasBackfillHistory(resolved, timeframe)))
         {
            allComplete = false;
            LogInsufficientHistory(resolved, timeframe);
            if(OpenChartsForHistoryWarmup) WarmupChart(resolved, timeframe);
         }
      }
   }
   return allComplete;
}

//+------------------------------------------------------------------+
//| EA lifecycle                                                     |
//+------------------------------------------------------------------+
int OnInit()
{
   effectiveFeedBaseURL = ResolveFeedBaseURL();
   chartResolvedSymbol = Symbol();
   effectiveSourceId = BuildSourceId();

   string symbolTokens[];
   int symbolTokenCount = SplitCsv(FeedSymbols, symbolTokens);
   feedSymbolCount = 0;
   for(int s = 0; s < symbolTokenCount && feedSymbolCount < MAX_FEED_SYMBOLS; s++)
   {
      string token = symbolTokens[s];
      StringToUpper(token);
      if(ContainsCanonical(token)) continue;
      string resolved = ResolveBrokerSymbol(token);
      feedSymbolCount++;
      ArrayResize(feedSymbolsCanonical, feedSymbolCount);
      ArrayResize(feedSymbolsResolved, feedSymbolCount);
      ArrayResize(feedSymbolsCore, feedSymbolCount);
      feedSymbolsCanonical[feedSymbolCount - 1] = token;
      feedSymbolsResolved[feedSymbolCount - 1] = resolved;
      feedSymbolsCore[feedSymbolCount - 1] = true;
      if(StringLen(resolved) == 0)
         Print("[MT4 FEED] Cannot resolve broker symbol for ", token);
      else if(AutoSelectSymbols)
         Print("[MT4 FEED] Resolved symbol ", token, " -> ", resolved);
   }

   string timeframeTokens[];
   int timeframeTokenCount = SplitCsv(FeedTimeframes, timeframeTokens);
   feedTimeframeCount = 0;
   for(int t = 0; t < timeframeTokenCount && feedTimeframeCount < MAX_FEED_TIMEFRAMES; t++)
   {
      string tfName = timeframeTokens[t];
      StringToUpper(tfName);
      int tf = ParseTimeframe(tfName);
      if(tf < 0)
      {
         Print("[MT4 FEED] Unsupported timeframe ignored: ", tfName);
         continue;
      }
      feedTimeframeCount++;
      ArrayResize(feedTimeframes, feedTimeframeCount);
      feedTimeframes[feedTimeframeCount - 1] = tf;
   }

   if(feedSymbolCount == 0 || feedTimeframeCount == 0)
   {
      Print("[MT4 FEED] FeedSymbols/FeedTimeframes are empty; cannot publish market data.");
      return INIT_FAILED;
   }

   int combos = feedSymbolCount * feedTimeframeCount;
   ArrayResize(openedChartsSymbols, combos);
   ArrayResize(openedChartsTimeframes, combos);
   ArrayResize(openedChartsDone, combos);
   ArrayResize(openedChartsLastAt, combos);
   // Populate every (resolved symbol, timeframe) pair so ChartIndex() can match
   // a WarmupChart() call.  Without this the arrays stay empty, ChartIndex()
   // always returns -1, and ChartOpen() would be re-issued for every cell on
   // every backfill retry (10s) -- flooding the terminal with new symbol tabs.
   int comboIndex = 0;
   for(int s = 0; s < feedSymbolCount; s++)
   {
      if(StringLen(feedSymbolsResolved[s]) == 0) continue;   // unresolved: never open a chart for it
      for(int t = 0; t < feedTimeframeCount; t++)
      {
         openedChartsSymbols[comboIndex] = feedSymbolsResolved[s];
         openedChartsTimeframes[comboIndex] = feedTimeframes[t];
         openedChartsDone[comboIndex] = false;
         openedChartsLastAt[comboIndex] = 0;
         comboIndex++;
      }
   }
   // Leftover slots stay empty (unmatchable) so ChartIndex() can never hit them.
   while(comboIndex < combos)
   {
      openedChartsSymbols[comboIndex] = "";
      openedChartsTimeframes[comboIndex] = 0;
      openedChartsDone[comboIndex] = false;
      openedChartsLastAt[comboIndex] = 0;
      comboIndex++;
   }

   Print("[MT4 FEED] Multi-symbol publisher v88 source_id=", effectiveSourceId,
         " symbols=", feedSymbolCount, " timeframes=", feedTimeframeCount,
         " endpoint=", effectiveFeedBaseURL,
         " chart (clock only)=", chartResolvedSymbol,
         ". One instance publishes every symbol/timeframe; no chart per symbol needed.");
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
   // (weekend) or before the first chart tick after attach, so the
   // BackfillDays backfill must publish without requiring a fresh live tick.
   // Bar timestamps come from the Broker clock via iTime()/iOpen(), never
   // from OnTick(), so no fresh tick is needed here.
   if(backfillPending &&
      (lastBackfillAttemptAt == 0 || utcNow - lastBackfillAttemptAt >= BACKFILL_RETRY_SECONDS))
   {
      lastBackfillAttemptAt = utcNow;
      if(lastBackfillLogAt == 0 || utcNow - lastBackfillLogAt >= 60)
      {
         Print("[MT4 FEED] Backfill allowed without fresh live tick.");
         lastBackfillLogAt = utcNow;
      }
      backfillPending = !PublishAllBars(true);
      if(!backfillPending)
      {
         backfillComplete = true;
         Print("[MT4 FEED] Multi-symbol backfill is complete.");
      }
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
   PublishAllBars(false);
}

void OnTick()
{
   // Timer owns publishing; a tick only authorizes the next timer batch.
   lastLiveTickUtc = TimeGMT();
}
//+------------------------------------------------------------------+
