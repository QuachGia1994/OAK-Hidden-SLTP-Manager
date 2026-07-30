//+------------------------------------------------------------------+
//| MT4 data feeder for the MT4-MT5 v72 comparison server           |
//+------------------------------------------------------------------+
#property copyright "OAK Group"
#property version   "2.12"
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
int deadlineMinutes[] = {49, 25, 25, 25, 25, 25};
datetime lastAttemptMinutes[6];
int completedDateKeys[6];

int OnInit()
{
   string symbols[5];
   BuildSymbolList(symbols);
   for(int index = 0; index < ArraySize(symbols); index++)
      SymbolSelect(symbols[index], true);
   Print("MT4 Data Feeder v2.12 - signal v72 GBP signals then XAU entry layers");
   EventSetTimer(1);
   return(INIT_SUCCEEDED);
}

void OnDeinit(const int reason)
{
   EventKillTimer();
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

string GetM30Direction(string symbolName, datetime candleOpenTime)
{
   int shift = iBarShift(symbolName, PERIOD_M30, candleOpenTime, true);
   if(shift < 0 || iTime(symbolName, PERIOD_M30, shift) != candleOpenTime) return "MISSING";
   double openPrice = iOpen(symbolName, PERIOD_M30, shift);
   double highPrice = iHigh(symbolName, PERIOD_M30, shift);
   double lowPrice = iLow(symbolName, PERIOD_M30, shift);
   double closePrice = iClose(symbolName, PERIOD_M30, shift);
   if(!MathIsValidNumber(openPrice) || !MathIsValidNumber(highPrice) ||
      !MathIsValidNumber(lowPrice) || !MathIsValidNumber(closePrice)) return "MISSING";
   if(highPrice < MathMax(openPrice, closePrice) ||
      lowPrice > MathMin(openPrice, closePrice) || highPrice < lowPrice) return "MISSING";
   if(closePrice > openPrice) return "TANG";
   if(closePrice < openPrice) return "GIAM";
   return "DOJI";
}

string ClassifyThree(string c1, string c2, string c3, int &ruleNumber)
{
   ruleNumber = 0;
   if(c1 == "TANG" && c2 == "TANG" && c3 == "TANG") { ruleNumber = 1; return "SW"; }
   if(c1 == "GIAM" && c2 == "TANG" && c3 == "TANG") { ruleNumber = 2; return "SW"; }
   if(c1 == "GIAM" && c2 == "TANG" && c3 == "GIAM") { ruleNumber = 3; return "BT"; }
   if(c1 == "GIAM" && c2 == "GIAM" && c3 == "TANG") { ruleNumber = 4; return "BT"; }
   if(c1 == "GIAM" && c2 == "GIAM" && c3 == "GIAM") { ruleNumber = 5; return "SW"; }
   if(c1 == "TANG" && c2 == "GIAM" && c3 == "GIAM") { ruleNumber = 6; return "SW"; }
   if(c1 == "TANG" && c2 == "GIAM" && c3 == "TANG") { ruleNumber = 7; return "BT"; }
   if(c1 == "TANG" && c2 == "TANG" && c3 == "GIAM") { ruleNumber = 8; return "BT"; }
   return "WAIT";
}

string ClassifyFour(string c1, string c2, string c3, string c4, int &ruleNumber)
{
   ruleNumber = 0;
   if((c1 != "TANG" && c1 != "GIAM") || (c2 != "TANG" && c2 != "GIAM") ||
      (c3 != "TANG" && c3 != "GIAM") || (c4 != "TANG" && c4 != "GIAM")) return "WAIT";
   if(c1 == "TANG" && c2 == "TANG" && c3 == "TANG") { ruleNumber = 1; return "SW"; }
   if(c1 == "TANG" && c2 == "GIAM" && c3 == "TANG" && c4 == "GIAM") { ruleNumber = 2; return "SW"; }
   if(c1 == "TANG" && c2 == "GIAM" && c3 == "GIAM") { ruleNumber = 3; return "SW"; }
   if(c1 == "TANG" && c2 == "TANG" && c3 == "GIAM") { ruleNumber = 4; return "BT"; }
   if(c1 == "TANG") { ruleNumber = 5; return "BT"; }
   if(c2 == "GIAM" && c3 == "GIAM") { ruleNumber = 6; return "SW"; }
   if(c2 == "TANG" && c3 == "GIAM" && c4 == "TANG") { ruleNumber = 7; return "SW"; }
   if(c2 == "TANG" && c3 == "TANG") { ruleNumber = 8; return "SW"; }
   if(c2 == "GIAM") { ruleNumber = 9; return "BT"; }
   ruleNumber = 10;
   return "BT";
}

string SelectXauEntry(int slot, string layer1Group, string layer2Group)
{
   if((layer1Group != "SW" && layer1Group != "BT") ||
      (layer2Group != "SW" && layer2Group != "BT")) return "";
   string earlyEntry;
   string lateEntry;
   if(layer1Group == "SW")
   {
      earlyEntry = StringFormat("%02d:49", slot);
      lateEntry = slot == 3 ? "04:49" : StringFormat("%02d:25", slot + 1);
   }
   else
   {
      earlyEntry = StringFormat("%02d:11", slot);
      lateEntry = StringFormat("%02d:49", slot);
   }
   return layer2Group == "SW" ? earlyEntry : lateEntry;
}

string NextFullHourEntry(string xauEntry)
{
   if(StringLen(xauEntry) != 5) return "";
   int hour = (int)StringToInteger(StringSubstr(xauEntry, 0, 2));
   return StringFormat("%02d:00", (hour + 1) % 24);
}

bool EvaluateGbpSignal(string symbolName, datetime slotTime,
                       string &signal, string &layer1Group)
{
   int ruleNumber = 0;
   layer1Group = ClassifyFour(
      GetM30Direction(symbolName, slotTime - 60 * 60),
      GetM30Direction(symbolName, slotTime - 90 * 60),
      GetM30Direction(symbolName, slotTime - 120 * 60),
      GetM30Direction(symbolName, slotTime - 150 * 60), ruleNumber);
   string baseSignal = DirectionToSignal(GetM30Direction(symbolName, slotTime - 60 * 60));
   signal = layer1Group == "SW" ? ReverseSignal(baseSignal) : baseSignal;
   if(layer1Group == "WAIT" || signal == "WAIT") { signal = "WAIT"; return false; }
   return true;
}

bool EvaluateXauTiming(int slot, datetime slotTime, string &entryTime,
                       string &layer1Group, string &layer2Group)
{
   int layer1Rule = 0;
   if(slot == 3)
      layer1Group = ClassifyThree(
         GetM30Direction(XauUsdSymbol, slotTime - 60 * 60),
         GetM30Direction(XauUsdSymbol, slotTime - 90 * 60),
         GetM30Direction(XauUsdSymbol, slotTime - 120 * 60), layer1Rule);
   else
      layer1Group = ClassifyFour(
         GetM30Direction(XauUsdSymbol, slotTime - 90 * 60),
         GetM30Direction(XauUsdSymbol, slotTime - 120 * 60),
         GetM30Direction(XauUsdSymbol, slotTime - 150 * 60),
         GetM30Direction(XauUsdSymbol, slotTime - 180 * 60), layer1Rule);
   int layer2Rule = 0;
   if(slot == 3)
      layer2Group = ClassifyFour(
         GetM30Direction(XauUsdSymbol, slotTime - 30 * 60),
         GetM30Direction(XauUsdSymbol, slotTime - 60 * 60),
         GetM30Direction(XauUsdSymbol, slotTime - 90 * 60),
         GetM30Direction(XauUsdSymbol, slotTime - 120 * 60), layer2Rule);
   else
      layer2Group = ClassifyFour(
         GetM30Direction(XauUsdSymbol, slotTime - 60 * 60),
         GetM30Direction(XauUsdSymbol, slotTime - 90 * 60),
         GetM30Direction(XauUsdSymbol, slotTime - 120 * 60),
         GetM30Direction(XauUsdSymbol, slotTime - 150 * 60), layer2Rule);
   entryTime = SelectXauEntry(slot, layer1Group, layer2Group);
   return entryTime != "";
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
   if(response == -1) { Print("[ERROR] WebRequest failed: ", GetLastError()); return false; }
   return response >= 200 && response < 300;
}

bool SendSlotData(int index, datetime serverTime)
{
   int slot = logicalSlots[index];
   datetime todayStart = StrToTime(TimeToString(serverTime, TIME_DATE));
   datetime slotTime = todayStart + slot * 3600;
   string symbols[5];
   BuildSymbolList(symbols);
   string signals[5], entries[5], groups[5];
   for(int pairIndex = 1; pairIndex < 5; pairIndex++)
      EvaluateGbpSignal(symbols[pairIndex], slotTime, signals[pairIndex], groups[pairIndex]);

   string xauEntry;
   string xauLayer1;
   string xauLayer2;
   if(!EvaluateXauTiming(slot, slotTime, xauEntry, xauLayer1, xauLayer2)) return false;
   entries[0] = xauEntry;
   groups[0] = xauLayer1;
   signals[0] = (slot == 3 || slot == 14 || slot == 16)
      ? signals[2] : ReverseSignal(signals[2]);
   if(signals[2] == "WAIT") { signals[0] = "WAIT"; entries[0] = ""; }
   string gbpEntry = NextFullHourEntry(xauEntry);
   for(int entryIndex = 1; entryIndex < 5; entryIndex++)
      entries[entryIndex] = signals[entryIndex] == "WAIT" ? "" : gbpEntry;

   string fields[5] = {"xauusd", "gbpusd", "gbpaud", "gbpjpy", "gbpcad"};
   string json = "{";
   json += "\"broker\":\"" + BrokerName + "\",";
   json += "\"time\":\"" + StringFormat("%02d:00", slot) + "\",";
   json += "\"slot\":" + IntegerToString(slot) + ",";
   json += "\"logic_version\":72,";
   for(int outputIndex = 0; outputIndex < 5; outputIndex++)
   {
      json += "\"" + fields[outputIndex] + "_signal\":\"" + signals[outputIndex] + "\",";
      json += "\"" + fields[outputIndex] + "_entry\":\"" + entries[outputIndex] + "\",";
      json += "\"" + fields[outputIndex] + "_group\":\"" + groups[outputIndex] + "\"";
      json += outputIndex < 4 ? "," : "}";
   }
   return SendDataToServer(json);
}

void ProcessEligibleSlots()
{
   datetime serverTime = TimeCurrent();
   datetime currentMinute = serverTime - TimeSeconds(serverTime);
   int dateKey = DateKey(serverTime);
   for(int index = 0; index < ArraySize(logicalSlots); index++)
   {
      if(completedDateKeys[index] == dateKey || lastAttemptMinutes[index] == currentMinute ||
         !IsEligibleMinute(index, serverTime, currentMinute)) continue;
      lastAttemptMinutes[index] = currentMinute;
      if(SendSlotData(index, serverTime)) completedDateKeys[index] = dateKey;
   }
}

void OnTick() { ProcessEligibleSlots(); }
void OnTimer() { ProcessEligibleSlots(); }
//+------------------------------------------------------------------+
