//+------------------------------------------------------------------+
//| OAK raw MT4 market-data publisher (v87)                          |
//| The EA publishes candles and a Broker clock only.  Signal rules  |
//| live in the Python core and are never calculated here.           |
//+------------------------------------------------------------------+
#property copyright "OAK Group"
#property version   "2.13"
#property strict

input string FeedBaseURL = "http://127.0.0.1:5001/mt4-feed";
input string FeedToken = "";
input string SourceId = "mt4_ea";
input string BrokerName = "MT4";
input string XauUsdSymbol = "XAUUSD";
input string GbpUsdSymbol = "GBPUSD";
input string GbpAudSymbol = "GBPAUD";
input string GbpJpySymbol = "GBPJPY";
input string GbpCadSymbol = "GBPCAD";

long sequenceNumber = 0;
bool backfillSent = false;

void BuildSymbols(string &canonicalSymbols[], string &resolvedSymbols[])
{
   canonicalSymbols[0] = "XAUUSD";
   canonicalSymbols[1] = "GBPUSD";
   canonicalSymbols[2] = "GBPAUD";
   canonicalSymbols[3] = "GBPJPY";
   canonicalSymbols[4] = "GBPCAD";
   resolvedSymbols[0] = XauUsdSymbol;
   resolvedSymbols[1] = GbpUsdSymbol;
   resolvedSymbols[2] = GbpAudSymbol;
   resolvedSymbols[3] = GbpJpySymbol;
   resolvedSymbols[4] = GbpCadSymbol;
}

string IsoBrokerTime(datetime value)
{
   return StringFormat("%04d-%02d-%02d %02d:%02d:%02d",
                       TimeYear(value), TimeMonth(value), TimeDay(value),
                       TimeHour(value), TimeMinute(value), TimeSeconds(value));
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
   int status = WebRequest("POST", FeedBaseURL + endpoint, headers, 5000, body, response, responseHeaders);
   if(status < 200 || status >= 300)
   {
      Print("[MT4 FEED] POST failed endpoint=", endpoint, " status=", status, " error=", GetLastError());
      return false;
   }
   return true;
}

void PublishHeartbeat()
{
   sequenceNumber++;
   datetime brokerNow = TimeCurrent();
   datetime utcNow = TimeGMT();
   int offsetSeconds = (int)(brokerNow - utcNow);
   int offsetHours = offsetSeconds / 3600;
   string payload = "{";
   payload += "\"schema_version\":2,";
   payload += "\"source_id\":\"" + JsonEscape(SourceId) + "\",";
   payload += "\"account\":\"" + IntegerToString(AccountNumber()) + "\",";
   payload += "\"server\":\"" + JsonEscape(AccountServer()) + "\",";
   payload += "\"broker_time\":\"" + IsoBrokerTime(brokerNow) + "\",";
   payload += "\"broker_time_utc\":\"" + IsoBrokerTime(utcNow) + "\",";
   payload += "\"broker_utc_offset\":" + IntegerToString(offsetHours) + ",";
   payload += "\"observed_at_utc\":\"" + IsoBrokerTime(utcNow) + "\",";
   payload += "\"last_sequence\":" + LongToString(sequenceNumber);
   payload += "}";
   PostJson("/heartbeat", payload);
}

string TimeframeName(int timeframe)
{
   if(timeframe == PERIOD_M30) return "M30";
   if(timeframe == PERIOD_H1) return "H1";
   return "H4";
}

int BackfillBars(int timeframe)
{
   if(timeframe == PERIOD_H4) return 1200; // at least 180 calendar days
   if(timeframe == PERIOD_H1) return 2500; // at least 90 calendar days
   return 5000;                            // at least 90 calendar days
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
      payload += "\"tick_volume\":" + LongToString(iVolume(resolvedSymbol, timeframe, shift)) + ",\"is_complete\":true}";
      emitted++;
   }
   payload += "]}";
   return emitted > 0 && PostJson("/bars", payload);
}

void PublishAllBars(bool backfill)
{
   string canonicalSymbols[5];
   string resolvedSymbols[5];
   BuildSymbols(canonicalSymbols, resolvedSymbols);
   int timeframes[3] = {PERIOD_M30, PERIOD_H1, PERIOD_H4};
   for(int s = 0; s < ArraySize(canonicalSymbols); s++)
   {
      for(int t = 0; t < ArraySize(timeframes); t++)
      {
         int count = backfill ? BackfillBars(timeframes[t]) : 3;
         PublishBars(canonicalSymbols[s], resolvedSymbols[s], timeframes[t], count);
      }
   }
}

int OnInit()
{
   string canonicalSymbols[5];
   string resolvedSymbols[5];
   BuildSymbols(canonicalSymbols, resolvedSymbols);
   for(int index = 0; index < ArraySize(resolvedSymbols); index++) SymbolSelect(resolvedSymbols[index], true);
   Print("MT4 raw feed publisher v87; Broker clock and candles only");
   EventSetTimer(3);
   PublishHeartbeat();
   PublishAllBars(true);
   backfillSent = true;
   return INIT_SUCCEEDED;
}

void OnDeinit(const int reason)
{
   EventKillTimer();
}

void OnTimer()
{
   PublishHeartbeat();
   PublishAllBars(false);
}

void OnTick()
{
   // Timer owns publishing so ticks cannot create duplicate feed batches.
}
//+------------------------------------------------------------------+
