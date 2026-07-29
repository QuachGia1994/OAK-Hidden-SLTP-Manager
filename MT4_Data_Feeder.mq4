//+------------------------------------------------------------------+
//| MT4 data feeder for the MT4-MT5 v71 comparison server           |
//+------------------------------------------------------------------+
#property copyright "OAK Group"
#property version   "2.10"
#property strict

input string ServerURL    = "http://127.0.0.1:5000/mt4_data";
input string BrokerName   = "MT4";
input string XauUsdSymbol = "XAUUSD";
input string GbpUsdSymbol = "GBPUSD";
input string GbpAudSymbol = "GBPAUD";
input string GbpJpySymbol = "GBPJPY";
input string GbpCadSymbol = "GBPCAD";

int logicalSlots[]    = {3, 7, 9, 12, 14, 16};
int deadlineHours[]   = {4, 8, 10, 13, 15, 17};
int deadlineMinutes[] = {25, 25, 25, 25, 25, 25};
datetime lastAttemptMinutes[6];
int completedDateKeys[6];

int OnInit()
{
   string symbols[5];
   BuildSymbolList(symbols);
   for(int index = 0; index < ArraySize(symbols); index++)
      SymbolSelect(symbols[index], true);
   Print("MT4 Data Feeder v2.10 - v71 H3 three-H1 + four-H1 signals");
   Print("Allow WebRequest for: ", ServerURL);
   EventSetTimer(1);
   return(INIT_SUCCEEDED);
}

void OnDeinit(const int reason)
{
   EventKillTimer();
   Print("MT4 Data Feeder stopped.");
}

void BuildSymbolList(string &symbols[])
{
   symbols[0] = XauUsdSymbol;
   symbols[1] = GbpUsdSymbol;
   symbols[2] = GbpAudSymbol;
   symbols[3] = GbpJpySymbol;
   symbols[4] = GbpCadSymbol;
}

int DateKey(datetime value)
{
   return TimeYear(value) * 10000 + TimeMonth(value) * 100 + TimeDay(value);
}

bool IsEligibleMinute(int index, datetime serverTime, datetime currentMinute)
{
   datetime todayStart = StrToTime(TimeToString(serverTime, TIME_DATE));
   datetime publication = todayStart + logicalSlots[index] * 3600;
   datetime deadline = todayStart + deadlineHours[index] * 3600
      + deadlineMinutes[index] * 60;
   return currentMinute >= publication && currentMinute <= deadline;
}

string ReverseSignal(string signal)
{
   if(signal == "BUY") return "SELL";
   if(signal == "SELL") return "BUY";
   return "WAIT";
}

string DirectionToSignal(string direction)
{
   if(direction == "TANG") return "BUY";
   if(direction == "GIAM") return "SELL";
   return "WAIT";
}

string GetRawCandleDirection(string symbolName, int timeframe, int shift)
{
   if(shift < 0) return "MISSING";
   double openPrice = iOpen(symbolName, timeframe, shift);
   double closePrice = iClose(symbolName, timeframe, shift);
   double highPrice = iHigh(symbolName, timeframe, shift);
   double lowPrice = iLow(symbolName, timeframe, shift);
   if(openPrice == 0 || closePrice == 0) return "MISSING";
   double range = highPrice - lowPrice;
   if(range <= 0 || MathAbs(closePrice - openPrice) / range < 0.02)
      return "DOJI";
   return closePrice > openPrice ? "TANG" : "GIAM";
}

string GetResolvedDirection(string symbolName, int timeframe, datetime candleTime)
{
   int shift = iBarShift(symbolName, timeframe, candleTime, true);
   string direction = GetRawCandleDirection(symbolName, timeframe, shift);
   if(direction != "DOJI") return direction;
   string previous = GetRawCandleDirection(symbolName, timeframe, shift + 1);
   if(previous != "TANG" && previous != "GIAM") return "MISSING";
   if(timeframe == PERIOD_M15)
      return previous == "TANG" ? "GIAM" : "TANG";
   return previous;
}

string ClassifyThree(string c1, string c2, string c3)
{
   if(c1 == "TANG" && c2 == "TANG" && c3 == "TANG") return "SW";
   if(c1 == "GIAM" && c2 == "TANG" && c3 == "TANG") return "SW";
   if(c1 == "GIAM" && c2 == "TANG" && c3 == "GIAM") return "BT";
   if(c1 == "GIAM" && c2 == "GIAM" && c3 == "TANG") return "BT";
   if(c1 == "GIAM" && c2 == "GIAM" && c3 == "GIAM") return "SW";
   if(c1 == "TANG" && c2 == "GIAM" && c3 == "GIAM") return "SW";
   if(c1 == "TANG" && c2 == "GIAM" && c3 == "TANG") return "BT";
   if(c1 == "TANG" && c2 == "TANG" && c3 == "GIAM") return "BT";
   return "WAIT";
}

string ClassifyFour(string c1, string c2, string c3, string c4)
{
   if((c1 != "TANG" && c1 != "GIAM") ||
      (c2 != "TANG" && c2 != "GIAM") ||
      (c3 != "TANG" && c3 != "GIAM") ||
      (c4 != "TANG" && c4 != "GIAM")) return "WAIT";
   if(c1 == "TANG")
   {
      if(c2 == "TANG" && c3 == "TANG") return "SW";
      if(c2 == "GIAM" && c3 == "TANG") return c4 == "GIAM" ? "SW" : "BT";
      return c2 == "GIAM" ? "SW" : "BT";
   }
   if(c2 == "GIAM" && c3 == "GIAM") return "SW";
   if(c2 == "TANG" && c3 == "GIAM") return c4 == "TANG" ? "SW" : "BT";
   return c2 == "TANG" ? "SW" : "BT";
}

string DeriveSignalBase(string baseDirection, string group)
{
   string signal = DirectionToSignal(baseDirection);
   if(signal == "WAIT" || (group != "SW" && group != "BT")) return "WAIT";
   return group == "SW" ? ReverseSignal(signal) : signal;
}

string ApplyEntryRule(string signalBase, string entryTime, int slot)
{
   if(signalBase != "BUY" && signalBase != "SELL") return "WAIT";
   string h11 = StringFormat("%02d:11", slot);
   string h49 = StringFormat("%02d:49", slot);
   string plus25 = StringFormat("%02d:25", slot + 1);
   string result = "WAIT";
   if(entryTime == plus25) result = signalBase;
   else if(entryTime == h11 || entryTime == h49) result = ReverseSignal(signalBase);
   if(entryTime == "15:25" || entryTime == "16:49") result = ReverseSignal(result);
   return result;
}

string DeriveXauEntryBasis(datetime slotTime)
{
   string base = GetResolvedDirection(XauUsdSymbol, PERIOD_M15, slotTime - 30 * 60);
   string p1 = GetResolvedDirection(XauUsdSymbol, PERIOD_M15, slotTime - 45 * 60);
   string p2 = GetResolvedDirection(XauUsdSymbol, PERIOD_M15, slotTime - 60 * 60);
   string p3 = GetResolvedDirection(XauUsdSymbol, PERIOD_M15, slotTime - 75 * 60);
   string offset15 = GetResolvedDirection(XauUsdSymbol, PERIOD_M15, slotTime - 15 * 60);
   string group = ClassifyThree(p1, p2, p3);
   string provisional = DeriveSignalBase(base, group);
   string offsetSignal = DirectionToSignal(offset15);
   if(provisional == "WAIT" || offsetSignal == "WAIT") return "WAIT";
   return provisional == offsetSignal ? ReverseSignal(provisional) : provisional;
}

string SelectEntryTime(int slot, datetime slotTime, datetime serverTime)
{
   string xauSignal = DeriveXauEntryBasis(slotTime);
   string initialDirection = GetResolvedDirection(GbpAudSymbol, PERIOD_M15, slotTime - 15 * 60);
   string initialSignal = DirectionToSignal(initialDirection);
   if(xauSignal == "WAIT" || initialSignal == "WAIT") return "";
   bool same = xauSignal == initialSignal;
   if((slot == 3 || slot == 7) && same) return StringFormat("%02d:11", slot);
   if(slot >= 9 && !same) return StringFormat("%02d:11", slot);
   if(serverTime < slotTime + 45 * 60) return "";
   string followupDirection = GetResolvedDirection(GbpAudSymbol, PERIOD_M15, slotTime + 30 * 60);
   string followupSignal = DirectionToSignal(followupDirection);
   if(followupSignal == "WAIT") return "";
   bool followupSame = xauSignal == followupSignal;
   if(slot == 3) return followupSame ? "03:49" : "04:25";
   if(slot == 7) return followupSame ? "07:49" : "08:25";
   return followupSame ? StringFormat("%02d:25", slot + 1) : StringFormat("%02d:49", slot);
}

string EvaluateH3Source(string symbolName, datetime referenceTime, string &group)
{
   datetime referenceStart = StrToTime(TimeToString(referenceTime, TIME_DATE));
   for(int daysBack = 1; daysBack <= 7; daysBack++)
   {
      datetime sourceStart = referenceStart - daysBack * 86400;
      int weekday = TimeDayOfWeek(sourceStart);
      if(weekday == 0 || weekday == 6) continue;
      string c1 = GetResolvedDirection(symbolName, PERIOD_H1, sourceStart + 4 * 3600);
      if(c1 != "TANG" && c1 != "GIAM") continue;
      string c2 = GetResolvedDirection(symbolName, PERIOD_H1, sourceStart + 3 * 3600);
      string c3 = GetResolvedDirection(symbolName, PERIOD_H1, sourceStart + 2 * 3600);
      group = ClassifyThree(c1, c2, c3);
      return DeriveSignalBase(c1, group);
   }
   group = "WAIT";
   return "WAIT";
}

string EvaluatePairSignal(string symbolName, int slot, datetime slotTime,
                          datetime serverTime, string entryTime, string &group)
{
   if(slot == 3)
   {
      datetime reference = slotTime;
      if(TimeDayOfWeek(slotTime) == 4) reference = slotTime - 3 * 86400;
      string result = EvaluateH3Source(symbolName, reference, group);
      if(TimeDayOfWeek(slotTime) == 4 && group == "SW") return "WAIT";
      return result;
   }
   string plus25 = StringFormat("%02d:25", slot + 1);
   datetime baseTime = entryTime == plus25 ? slotTime : slotTime - 3600;
   if(serverTime < baseTime + 3600) return "WAIT";
   string c1 = GetResolvedDirection(symbolName, PERIOD_H1, baseTime);
   string c2 = GetResolvedDirection(symbolName, PERIOD_H1, baseTime - 3600);
   string c3 = GetResolvedDirection(symbolName, PERIOD_H1, baseTime - 7200);
   string c4 = GetResolvedDirection(symbolName, PERIOD_H1, baseTime - 10800);
   group = ClassifyFour(c1, c2, c3, c4);
   return ApplyEntryRule(DeriveSignalBase(c1, group), entryTime, slot);
}

bool SendDataToServer(string jsonPayload)
{
   string headers = "Content-Type: application/json\r\n";
   char postData[];
   char resultData[];
   string resultHeaders;
   int length = StringToCharArray(jsonPayload, postData, 0, WHOLE_ARRAY, CP_UTF8) - 1;
   if(length < 0) return false;
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
   datetime todayStart = StrToTime(TimeToString(serverTime, TIME_DATE));
   datetime slotTime = todayStart + slot * 3600;
   string symbols[5];
   BuildSymbolList(symbols);
   string signals[5];
   string groups[5];
   bool thursdayH3 = slot == 3 && TimeDayOfWeek(slotTime) == 4;
   if(thursdayH3)
      for(int h3Index = 0; h3Index < 5; h3Index++)
         signals[h3Index] = EvaluatePairSignal(
            symbols[h3Index], slot, slotTime, serverTime, "", groups[h3Index]
         );

   bool terminalWait = thursdayH3 && groups[0] == "SW";
   string entryTime = "";
   if(!terminalWait)
   {
      entryTime = SelectEntryTime(slot, slotTime, serverTime);
      if(entryTime == "") return false;
      if(!thursdayH3)
         for(int pairIndex = 0; pairIndex < 5; pairIndex++)
            signals[pairIndex] = EvaluatePairSignal(
               symbols[pairIndex], slot, slotTime, serverTime, entryTime, groups[pairIndex]
            );
   }
   if(signals[0] == "WAIT" && !terminalWait) return false;

   string fields[5] = {"xauusd", "gbpusd", "gbpaud", "gbpjpy", "gbpcad"};
   string json = "{";
   json += "\"broker\":\"" + BrokerName + "\",";
   json += "\"time\":\"" + StringFormat("%02d:00", slot) + "\",";
   json += "\"slot\":" + IntegerToString(slot) + ",";
   json += "\"entry_time\":\"" + entryTime + "\",";
   json += "\"terminal_wait\":" + (terminalWait ? "true" : "false") + ",";
   for(int outputIndex = 0; outputIndex < 5; outputIndex++)
   {
      json += "\"" + fields[outputIndex] + "_signal\":\"" + signals[outputIndex] + "\",";
      json += "\"" + fields[outputIndex] + "_group\":\"" + groups[outputIndex] + "\"";
      json += outputIndex < 4 ? "," : "}";
   }
   Print("[SIGNAL] H=", slot, " entry=", entryTime, " Broker: ", json);
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
         !IsEligibleMinute(index, serverTime, currentMinute)) continue;
      lastAttemptMinutes[index] = currentMinute;
      if(SendSlotData(index, serverTime)) completedDateKeys[index] = dateKey;
   }
}

void OnTick() { ProcessEligibleSlots(); }
void OnTimer() { ProcessEligibleSlots(); }
//+------------------------------------------------------------------+
