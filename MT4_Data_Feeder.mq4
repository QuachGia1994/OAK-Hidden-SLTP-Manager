//+------------------------------------------------------------------+
//|                                         MT4_Data_Feeder.mq4      |
//|                          Data Feeder for MT4-MT5 Dual Signal     |
//|                          Gui du lieu nến tu MT4 ve Python Server |
//+------------------------------------------------------------------+
#property copyright "OAK Group"
#property version   "1.00"
#property strict

//+------------------------------------------------------------------+
//| CAU HINH                                                           |
//+------------------------------------------------------------------+
input string   ServerURL     = "http://127.0.0.1:5000/mt4_data";
input string   BrokerName    = "MT4";
input string   SymbolName    = "GBPUSD";
input int      MagicNumber   = 99999;

// Gio kich hoat (Server Time) - phut 50
int targetHours[] = {1, 7, 9, 14, 15, 16};

//+------------------------------------------------------------------+
//| Expert initialization function                                     |
//+------------------------------------------------------------------+
int OnInit()
{
   Print("===========================================");
   Print("MT4 Data Feeder v1.0 - Khoi dong");
   Print("Server: ", ServerURL);
   Print("Broker: ", BrokerName);
   Print("Symbol: ", SymbolName);
   Print("Target Hours: 01, 07, 09, 14, 15, 16");
   Print("===========================================");

   // Kiem tra WebRequest permission
   // BUOC QUAN TRONG: Phai tick vao "Allow WebRequest for listed URL"
   // trong Tools -> Options -> Expert Advisors -> Allow WebRequest for listed URL:
   //   http://127.0.0.1:5000
   Print("[SETUP] Neu thay loi WebRequest, hay:");
   Print("  1. Vao Tools -> Options -> Expert Advisors");
   Print("  2. Tick vao 'Allow WebRequest for listed URL'");
   Print("  3. Them: http://127.0.0.1:5000");
   Print("  4. Restart MT4");

   return(INIT_SUCCEEDED);
}

//+------------------------------------------------------------------+
//| Expert deinitialization function                                   |
//+------------------------------------------------------------------+
void OnDeinit(const int reason)
{
   Print("MT4 Data Feeder - Dung.");
}

//+------------------------------------------------------------------+
//| Xac dinh huong nến                                                |
//| Tra ve: "TANG", "GIAM", hoac "DOJI"                              |
//+------------------------------------------------------------------+
string GetCandleDirection(int timeframe, int shift)
{
   double openPrice  = iOpen(SymbolName, timeframe, shift);
   double closePrice = iClose(SymbolName, timeframe, shift);
   double highPrice  = iHigh(SymbolName, timeframe, shift);
   double lowPrice   = iLow(SymbolName, timeframe, shift);

   // Kiem tra rỗng
   if(openPrice == 0 || closePrice == 0)
   {
      Print("[WARN] Du lieu rỗng TF=", timeframe, " shift=", shift);
      return "DOJI";
   }

   double body = MathAbs(closePrice - openPrice);
   double range = highPrice - lowPrice;

   if(range == 0)
      return "DOJI";

   // DOJI: body nho hon 5% cua range
   if(body / range < 0.05)
      return "DOJI";

   if(closePrice > openPrice)
      return "TANG";
   else if(closePrice < openPrice)
      return "GIAM";

   return "DOJI";
}

//+------------------------------------------------------------------+
//| Tinh so nến M5 lùi tu thoi diem H:50                              |
//| M5@H:35 -> shift = (H*60+50 - H*60-35) / 5 = 3                  |
//| M5@H:40 -> shift = (H*60+50 - H*60-40) / 5 = 2                  |
//+------------------------------------------------------------------+
int GetM5Shift(int activationHour, int candleMinute)
{
   int currentMinutes = activationHour * 60 + 50;
   int candleMinutes  = activationHour * 60 + candleMinute;
   return (currentMinutes - candleMinutes) / 5;
}

//+------------------------------------------------------------------+
//| Tinh so nến M15 lùi tu thoi diem H:50                             |
//| M15@H:30 -> shift = (H*60+50 - H*60-30) / 15 = 1 (round)       |
//| Chi dung khi (50-30)/15 = 1.33 -> lay shift 1                    |
//+------------------------------------------------------------------+
int GetM15Shift(int activationHour, int candleMinute)
{
   int currentMinutes = activationHour * 60 + 50;
   int candleMinutes  = activationHour * 60 + candleMinute;
   int diff = currentMinutes - candleMinutes;
   // Round len de lay nến chua dong (gan nhat voi thoi diem can lay)
   return (diff + 14) / 15;  // ceil(diff/15)
}

//+------------------------------------------------------------------+
//| Tinh so nến H1 lùi tu thoi diem H:50                              |
//| H1@(H-1):00 -> can tinh tu thoi diem H:50                        |
//| So phut tu (H-1):00 den H:50 = 60 + 50 = 110 phut               |
//| H1 shift = 110/60 = 1.83 -> lay shift 2 (nến da dong truoc do)  |
//| NHUNG: Tai thoi diem H:50, nến H:00 chua dong,                  |
//|        nến (H-1):00 la nến truoc do -> shift = 2                 |
//+------------------------------------------------------------------+
int GetH1Shift(int activationHour)
{
   // H:50 hien tai. Can lay H1@(H-1):00
   // H1@H:00 dang chay (chua dong) -> shift = 1
   // H1@(H-1):00 da dong -> shift = 2
   return 2;
}

//+------------------------------------------------------------------+
//| Gui du lieu qua WebRequest POST                                    |
//+------------------------------------------------------------------+
bool SendDataToServer(string jsonPayload)
{
   string headers = "Content-Type: application/json\r\n";
   char   postData[];
   char   resultData[];
   string resultHeaders;

   // Chuyen string sang char array
   int len = StringLen(jsonPayload);
   ArrayResize(postData, len);
   for(int i = 0; i < len; i++)
      postData[i] = (uchar)StringGetCharacter(jsonPayload, i);

   Print("[WebRequest] Dang gui: ", jsonPayload);

   int res = WebRequest(
      "POST",
      ServerURL,
      headers,
      5000,          // timeout 5s
      postData,
      resultData,
      resultHeaders
   );

   if(res == -1)
   {
      int err = GetLastError();
      Print("[ERROR] WebRequest that bai! Error code: ", err);
      if(err == 4060)
      {
         Print("=============================================");
         Print("Huong dan fix loi 4060:");
         Print("  1. Vao Tools -> Options -> Expert Advisors");
         Print("  2. Tick vao 'Allow WebRequest for listed URL'");
         Print("  3. Them URL: http://127.0.0.1:5000");
         Print("  4. Restart MT4");
         Print("=============================================");
      }
      return false;
   }

   // Doc ket qua tu server
   string result = "";
   for(int i = 0; i < ArraySize(resultData); i++)
      result += CharToString((uchar)resultData[i]);

   Print("[WebRequest] Response (", res, "): ", result);
   return true;
}

//+------------------------------------------------------------------+
//| OnTick - Vong lloop chinh                                          |
//+------------------------------------------------------------------+
void OnTick()
{
   // Lay Server Time
   datetime serverTime = TimeCurrent();
   int hour   = TimeHour(serverTime);
   int minute = TimeMinute(serverTime);
   int second = TimeSecond(serverTime);

   // Chi kich hoat tai phut 50, giay 00
   if(minute != 50 || second != 0)
      return;

   // Kiem tra gio kich hoat
   bool isTarget = false;
   for(int i = 0; i < ArraySize(targetHours); i++)
   {
      if(hour == targetHours[i])
      {
         isTarget = true;
         break;
      }
   }
   if(!isTarget)
      return;

   Print("===========================================");
   Print("[SIGNAL] Kich hoat tai ", TimeToStr(serverTime, TIME_DATE|TIME_MINUTES|TIME_SECONDS));

   // --- BƯỚC 1: Lay nến M5 ---
   int shiftM35 = GetM5Shift(hour, 35);
   int shiftM40 = GetM5Shift(hour, 40);

   string dirM35 = GetCandleDirection(PERIOD_M5, shiftM35);
   string dirM40 = GetCandleDirection(PERIOD_M5, shiftM40);

   Print("[M5] Shift=", shiftM35, " M5@35=", dirM35);
   Print("[M5] Shift=", shiftM40, " M5@40=", dirM40);

   // --- BƯỚC 2: Lay H1 va M15 ---
   int shiftH1  = GetH1Shift(hour);
   int shiftM15 = GetM15Shift(hour, 30);

   string dirH1  = GetCandleDirection(PERIOD_H1, shiftH1);
   string dirM15 = GetCandleDirection(PERIOD_M15, shiftM15);

   int h1Hour = hour - 1;
   if(h1Hour < 0) h1Hour = 23;

   Print("[H1]  Shift=", shiftH1, " H1@", h1Hour, ":00=", dirH1);
   Print("[M15] Shift=", shiftM15, " M15@", hour, ":30=", dirM15);

   // --- BƯỚC 3: Dong goi JSON ---
   string timeStr = IntegerToString(hour) + ":50";

   string json = "{";
   json += "\"broker\":\"" + BrokerName + "\",";
   json += "\"time\":\"" + timeStr + "\",";
   json += "\"m35\":\"" + dirM35 + "\",";
   json += "\"m40\":\"" + dirM40 + "\",";
   json += "\"h1\":\"" + dirH1 + "\",";
   json += "\"m15\":\"" + dirM15 + "\"";
   json += "}";

   Print("[JSON] ", json);

   // --- BƯỚC 4: Gui len Server ---
   bool ok = SendDataToServer(json);
   if(ok)
      Print("[OK] Da gui thanh cong!");
   else
      Print("[FAIL] Gui that bai!");

   Print("===========================================");
}
//+------------------------------------------------------------------+
