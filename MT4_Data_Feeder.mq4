//+------------------------------------------------------------------+
//| MT4 data feeder for the MT4-MT5 comparison server               |
//| Publication clocks follow the MT5 signal bot Broker schedule.   |
//+------------------------------------------------------------------+
#property copyright "OAK Group"
#property version   "2.00"
#property strict

input string ServerURL  = "http://127.0.0.1:5000/mt4_data";
input string BrokerName = "MT4";
input string GbpUsdSymbol = "GBPUSD";
input string GbpAudSymbol = "GBPAUD";
input string XauUsdSymbol = "XAUUSD";

int logicalSlots[]  = {3, 7, 9, 12, 14, 16};
int signalHours[]   = {3, 7, 9, 12, 14, 16};
int signalMinutes[] = {0, 0, 0, 0, 0, 0};
int deadlineHours[]   = {4, 8, 10, 13, 15, 17};
int deadlineMinutes[] = {25, 25, 25, 25, 25, 25};
datetime lastAttemptMinutes[6];
int completedDateKeys[6];

int OnInit()
{
   Print("MT4 Data Feeder v2.0 - active slots H=3,7,9,12,14,16");
   Print("Allow WebRequest for: ", ServerURL);
   SymbolSelect(GbpUsdSymbol, true);
   SymbolSelect(GbpAudSymbol, true);
   SymbolSelect(XauUsdSymbol, true);
   EventSetTimer(1);
   return(INIT_SUCCEEDED);
}

void OnDeinit(const int reason)
{
   EventKillTimer();
   Print("MT4 Data Feeder stopped.");
}

int DateKey(datetime value)
{
   return TimeYear(value) * 10000 + TimeMonth(value) * 100 + TimeDay(value);
}

bool IsEligibleMinute(int index, datetime serverTime, datetime currentMinute)
{
   datetime todayStart = StrToTime(TimeToString(serverTime, TIME_DATE));
   datetime publication = todayStart + signalHours[index] * 3600
      + signalMinutes[index] * 60;
   datetime deadline = todayStart + deadlineHours[index] * 3600
      + deadlineMinutes[index] * 60;
   return currentMinute >= publication && currentMinute <= deadline;
}

string GetRawCandleDirection(string symbolName, int timeframe, int shift)
{
   if(shift < 0)
      return "MISSING";
   double openPrice = iOpen(symbolName, timeframe, shift);
   double closePrice = iClose(symbolName, timeframe, shift);
   double highPrice = iHigh(symbolName, timeframe, shift);
   double lowPrice = iLow(symbolName, timeframe, shift);
   if(openPrice == 0 || closePrice == 0)
      return "MISSING";
   double range = highPrice - lowPrice;
   if(range <= 0 || MathAbs(closePrice - openPrice) / range < 0.02)
      return "DOJI";
   return closePrice > openPrice ? "TANG" : "GIAM";
}

string GetResolvedDirection(string symbolName, int timeframe, datetime candleTime)
{
   int shift = iBarShift(symbolName, timeframe, candleTime, true);
   string direction = GetRawCandleDirection(symbolName, timeframe, shift);
   if(direction != "DOJI")
      return direction;
   return GetRawCandleDirection(symbolName, timeframe, shift + 1);
}

string DeriveXauSignal(string newestDirection, string olderDirection)
{
   if((newestDirection != "TANG" && newestDirection != "GIAM") ||
      (olderDirection != "TANG" && olderDirection != "GIAM"))
      return "WAIT";
   string signal = newestDirection == "TANG" ? "BUY" : "SELL";
   if(newestDirection == olderDirection)
      signal = signal == "BUY" ? "SELL" : "BUY";
   return signal;
}

bool SendDataToServer(string jsonPayload)
{
   string headers = "Content-Type: application/json\r\n";
   char postData[];
   char resultData[];
   string resultHeaders;
   int length = StringToCharArray(jsonPayload, postData, 0, WHOLE_ARRAY, CP_UTF8) - 1;
   if(length < 0)
      return false;
   ArrayResize(postData, length);
   int response = WebRequest("POST", ServerURL, headers, 5000, postData, resultData, resultHeaders);
   if(response == -1)
   {
      Print("[ERROR] WebRequest failed: ", GetLastError());
      return false;
   }
   Print("[WebRequest] HTTP ", response);
   return response >= 200 && response < 300;
}

bool SendSlotData(int index, datetime serverTime)
{
   int slot = logicalSlots[index];
   bool deactivated = false;
   datetime todayStart = StrToTime(TimeToString(serverTime, TIME_DATE));
   datetime yesterdayStart = StrToTime(TimeToString(todayStart - 12 * 3600, TIME_DATE));
   datetime yesterdaySlot = yesterdayStart + slot * 3600;
   datetime todaySlot = todayStart + slot * 3600;
   string gbpUsdH1First = GetResolvedDirection(GbpUsdSymbol, PERIOD_H1, yesterdaySlot - 3600);
   string gbpUsdH1Second = GetResolvedDirection(GbpUsdSymbol, PERIOD_H1, yesterdaySlot - 7200);
   string gbpAudH1First = GetResolvedDirection(GbpAudSymbol, PERIOD_H1, yesterdaySlot - 3600);
   string gbpAudH1Second = GetResolvedDirection(GbpAudSymbol, PERIOD_H1, yesterdaySlot - 7200);
   string gbpUsdSignal = DeriveXauSignal(gbpUsdH1First, gbpUsdH1Second);
   string gbpAudSignal = DeriveXauSignal(gbpAudH1First, gbpAudH1Second);
   string xauM15First = "NOT_NEEDED";
   string xauM15Second = "NOT_NEEDED";
   string xauM15Third = "NOT_NEEDED";
   if(gbpUsdSignal != "WAIT" && gbpAudSignal != "WAIT" && gbpUsdSignal != gbpAudSignal)
   {
      xauM15First = GetResolvedDirection(XauUsdSymbol, PERIOD_M15, todaySlot - 30 * 60);
      xauM15Second = GetResolvedDirection(XauUsdSymbol, PERIOD_M15, todaySlot - 45 * 60);
      xauM15Third = GetResolvedDirection(XauUsdSymbol, PERIOD_M15, todaySlot - 60 * 60);
   }
   string signalTime = StringFormat("%02d:%02d", signalHours[index], signalMinutes[index]);

   string json = "{";
   json += "\"broker\":\"" + BrokerName + "\",";
   json += "\"time\":\"" + signalTime + "\",";
   json += "\"slot\":" + IntegerToString(slot) + ",";
   json += "\"deactivated\":" + (deactivated ? "true" : "false") + ",";
   json += "\"gbpusd_h1_1\":\"" + gbpUsdH1First + "\",";
   json += "\"gbpusd_h1_2\":\"" + gbpUsdH1Second + "\",";
   json += "\"gbpaud_h1_1\":\"" + gbpAudH1First + "\",";
   json += "\"gbpaud_h1_2\":\"" + gbpAudH1Second + "\",";
   json += "\"xau_m15_1\":\"" + xauM15First + "\",";
   json += "\"xau_m15_2\":\"" + xauM15Second + "\",";
   json += "\"xau_m15_3\":\"" + xauM15Third + "\"}";

   Print("[SIGNAL] H=", slot, " @ ", signalTime, " Broker: ", json);
   return SendDataToServer(json);
}

void ProcessEligibleSlots()
{
   datetime serverTime = TimeCurrent();
   datetime currentMinute = serverTime - TimeSeconds(serverTime);
   int dateKey = DateKey(serverTime);
   for(int index = 0; index < ArraySize(logicalSlots); index++)
   {
      if(completedDateKeys[index] == dateKey ||
         lastAttemptMinutes[index] == currentMinute ||
         !IsEligibleMinute(index, serverTime, currentMinute))
         continue;
      lastAttemptMinutes[index] = currentMinute;
      if(SendSlotData(index, serverTime))
         completedDateKeys[index] = dateKey;
   }
}

void OnTick()
{
   ProcessEligibleSlots();
}

void OnTimer()
{
   ProcessEligibleSlots();
}
//+------------------------------------------------------------------+
