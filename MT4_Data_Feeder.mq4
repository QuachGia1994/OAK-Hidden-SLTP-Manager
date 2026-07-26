//+------------------------------------------------------------------+
//| MT4 data feeder for the MT4-MT5 comparison server               |
//| Publication clocks follow the MT5 signal bot Broker schedule.   |
//+------------------------------------------------------------------+
#property copyright "OAK Group"
#property version   "2.00"
#property strict

input string ServerURL  = "http://127.0.0.1:5000/mt4_data";
input string BrokerName = "MT4";
input string SymbolName = "GBPUSD";

int logicalSlots[]  = {3, 4, 5, 6, 9, 12, 14, 16};
int signalHours[]   = {3, 4, 5, 6, 9, 12, 14, 16};
int signalMinutes[] = {0, 45, 45, 0, 0, 0, 0, 0};
datetime lastSentMinute = 0;

int OnInit()
{
   Print("MT4 Data Feeder v2.0 - active slots H=3,4,5,6,9,12,14,16");
   Print("Allow WebRequest for: ", ServerURL);
   return(INIT_SUCCEEDED);
}

void OnDeinit(const int reason)
{
   Print("MT4 Data Feeder stopped.");
}

datetime DateOnly(datetime value)
{
   return StrToTime(TimeToString(value, TIME_DATE));
}

bool IsRawSpecialDate(datetime value)
{
   int weekday = TimeDayOfWeek(value); // Thu=4, Fri=5 in MQL4
   if(weekday != 4 && weekday != 5)
      return false;
   if(TimeMonth(value + 7 * 86400) != TimeMonth(value))
      return true;
   datetime wednesday = value - ((weekday == 4) ? 86400 : 2 * 86400);
   int wednesdayDay = TimeDay(wednesday);
   if(wednesdayDay == 30 || wednesdayDay == 1)
      return true;
   int day = TimeDay(value);
   return weekday == 5 && (day == 3 || day == 4 || day == 7);
}

bool IsSpecialPair(datetime serverTime)
{
   int weekday = TimeDayOfWeek(serverTime);
   if(weekday != 4 && weekday != 5)
      return false;
   datetime currentDate = DateOnly(serverTime);
   datetime thursday = (weekday == 4) ? currentDate : currentDate - 86400;
   datetime friday = thursday + 86400;
   if(TimeYear(thursday) != TimeYear(friday))
      return false;
   return IsRawSpecialDate(thursday) || IsRawSpecialDate(friday);
}

bool IsPostSpecialMonday(datetime serverTime)
{
   if(TimeDayOfWeek(serverTime) != 1)
      return false;
   return IsSpecialPair(DateOnly(serverTime) - 4 * 86400);
}

bool IsSuppressedSlot(int slot, datetime serverTime)
{
   if(slot != 12 && slot != 14 && slot != 16)
      return false;
   return IsSpecialPair(serverTime) || IsPostSpecialMonday(serverTime);
}

bool ResolvePublication(datetime serverTime, int &slot, int &patternHour, bool &deactivated)
{
   int currentHour = TimeHour(serverTime);
   int currentMinute = TimeMinute(serverTime);
   bool special = IsSpecialPair(serverTime);
   for(int index = 0; index < ArraySize(logicalSlots); index++)
   {
      int publicationHour = signalHours[index];
      int publicationMinute = signalMinutes[index];
      if(logicalSlots[index] == 9 && special)
         publicationHour = 8;
      if(currentHour != publicationHour || currentMinute != publicationMinute)
         continue;
      slot = logicalSlots[index];
      if(IsSuppressedSlot(slot, serverTime))
         continue;
      patternHour = publicationMinute >= 45 ? publicationHour : publicationHour - 1;
      if(patternHour < 0)
         patternHour += 24;
      deactivated = slot == 3 && TimeDayOfWeek(serverTime) == 4 && special;
      return true;
   }
   return false;
}

string GetCandleDirection(int timeframe, int shift)
{
   double openPrice = iOpen(SymbolName, timeframe, shift);
   double closePrice = iClose(SymbolName, timeframe, shift);
   double highPrice = iHigh(SymbolName, timeframe, shift);
   double lowPrice = iLow(SymbolName, timeframe, shift);
   if(openPrice == 0 || closePrice == 0)
      return "DOJI";
   double range = highPrice - lowPrice;
   if(range <= 0 || MathAbs(closePrice - openPrice) / range < 0.05)
      return "DOJI";
   return closePrice > openPrice ? "TANG" : "GIAM";
}

int CandleShift(int activationHour, int activationMinute,
                int candleHour, int candleMinute, int timeframeMinutes)
{
   int activation = activationHour * 60 + activationMinute;
   int candle = candleHour * 60 + candleMinute;
   int difference = activation - candle;
   if(difference < 0)
      difference += 24 * 60;
   return difference / timeframeMinutes;
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

void OnTick()
{
   datetime serverTime = TimeCurrent();
   int slot = -1;
   int patternHour = -1;
   bool deactivated = false;
   if(!ResolvePublication(serverTime, slot, patternHour, deactivated))
      return;
   datetime minuteKey = serverTime - TimeSeconds(serverTime);
   if(minuteKey == lastSentMinute)
      return;
   lastSentMinute = minuteKey;

   int activationHour = TimeHour(serverTime);
   int activationMinute = TimeMinute(serverTime);
   int shiftM35 = CandleShift(activationHour, activationMinute, patternHour, 35, 5);
   int shiftM40 = CandleShift(activationHour, activationMinute, patternHour, 40, 5);
   int shiftM30 = CandleShift(activationHour, activationMinute, patternHour, 0, 30);
   string dirM35 = GetCandleDirection(PERIOD_M5, shiftM35);
   string dirM40 = GetCandleDirection(PERIOD_M5, shiftM40);
   string dirM30 = GetCandleDirection(PERIOD_M30, shiftM30);
   string signalTime = StringFormat("%02d:%02d", activationHour, activationMinute);

   string json = "{";
   json += "\"broker\":\"" + BrokerName + "\",";
   json += "\"time\":\"" + signalTime + "\",";
   json += "\"slot\":" + IntegerToString(slot) + ",";
   json += "\"pattern_hour\":" + IntegerToString(patternHour) + ",";
   json += "\"deactivated\":" + (deactivated ? "true" : "false") + ",";
   json += "\"m35\":\"" + dirM35 + "\",";
   json += "\"m40\":\"" + dirM40 + "\",";
   json += "\"m30\":\"" + dirM30 + "\"}";

   Print("[SIGNAL] H=", slot, " @ ", signalTime, " Broker: ", json);
   if(!SendDataToServer(json))
      lastSentMinute = 0; // allow another tick in this publication minute to retry
}
//+------------------------------------------------------------------+
