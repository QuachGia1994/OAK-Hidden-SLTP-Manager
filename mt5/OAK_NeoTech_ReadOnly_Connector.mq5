#property strict
#property version   "1.03"
#property description "OAK NeoTech telemetry connector. Investor Password recommended; Master requires explicit web risk acceptance."

input string InpPairingCode = "";
input string InpApiBaseUrl = "https://www.oakgatekeeper.uk";
input int    InpHistoryDays = 370;
input int    InpSyncSeconds = 300;
input int    InpHttpTimeoutMs = 20000;

#define OAK_CONNECTOR_VERSION "1.0.3"
#define OAK_PAIR_SCHEMA "oak-neotech-readonly-pair-v1"
#define OAK_INGEST_SCHEMA "oak-neotech-readonly-ingest-v1"
#define OAK_MAX_TRADING_DEALS 6000
#define OAK_MAX_CASHFLOWS 1000

string g_connector_id="";
string g_connector_token="";
string g_access_mode="READ_ONLY";
string g_pair_code_hash="";
bool   g_sync_busy=false;
bool   g_sync_enabled=false;
bool   g_loaded_legacy_credentials=false;

string OakJsonEscape(const string value)
  {
   string out="";
   for(int i=0;i<StringLen(value);i++)
     {
      ushort c=StringGetCharacter(value,i);
      if(c=='\\') out+="\\\\";
      else if(c=='\"') out+="\\\"";
      else if(c==10) out+="\\n";
      else if(c==13) out+="\\r";
      else if(c==9) out+="\\t";
      else if(c<32) out+=StringFormat("\\u%04x",(int)c);
      else out+=ShortToString(c);
     }
   return out;
  }

string OakJsonQuote(const string value) { return "\""+OakJsonEscape(value)+"\""; }
string OakJsonBool(const bool value) { return value ? "true" : "false"; }

string OakNormalizePairingCode(const string raw_value)
  {
   string value=raw_value;
   StringTrimLeft(value);
   StringTrimRight(value);
   StringToUpper(value);
   string out="";
   for(int i=0;i<StringLen(value);i++)
     {
      ushort c=StringGetCharacter(value,i);
      if((c>='A' && c<='Z') || (c>='0' && c<='9')) out+=ShortToString(c);
     }
   return out;
  }

string OakJsonNumber(const double value,const int digits=8)
  {
   if(!MathIsValidNumber(value)) return "0";
   string text=DoubleToString(value,digits);
   while(StringFind(text,".")>=0 && StringSubstr(text,StringLen(text)-1)=="0") text=StringSubstr(text,0,StringLen(text)-1);
   if(StringLen(text)>0 && StringSubstr(text,StringLen(text)-1)==".") text=StringSubstr(text,0,StringLen(text)-1);
   return text;
  }

string OakHex(const uchar &bytes[])
  {
   string out="";
   for(int i=0;i<ArraySize(bytes);i++) out+=StringFormat("%02x",(int)bytes[i]);
   return out;
  }

string OakSha256(const string text)
  {
   uchar bytes[],key[],hash[];
   int copied=StringToCharArray(text,bytes,0,-1,CP_UTF8);
   if(copied<=0) return "";
   if(ArraySize(bytes)>0 && bytes[ArraySize(bytes)-1]==0) ArrayResize(bytes,ArraySize(bytes)-1);
   if(CryptEncode(CRYPT_HASH_SHA256,bytes,key,hash)<=0) return "";
   return OakHex(hash);
  }

string OakApiBase()
  {
   string value=InpApiBaseUrl;
   StringTrimLeft(value);
   StringTrimRight(value);
   while(StringLen(value)>0 && StringSubstr(value,StringLen(value)-1)=="/") value=StringSubstr(value,0,StringLen(value)-1);
   return value;
  }

string OakCredentialIdentityHash()
  {
   string broker=AccountInfoString(ACCOUNT_COMPANY);
   string server=AccountInfoString(ACCOUNT_SERVER);
   StringTrimLeft(broker); StringTrimRight(broker); StringToLower(broker);
   StringTrimLeft(server); StringTrimRight(server); StringToLower(server);
   string identity=broker+"\n"+server+"\n"+IntegerToString((long)AccountInfoInteger(ACCOUNT_LOGIN));
   return StringSubstr(OakSha256(identity),0,24);
  }

string OakCredentialFile()
  {
   return "OAKNeoTech\\readonly_"+IntegerToString((long)AccountInfoInteger(ACCOUNT_LOGIN))+"_"+OakCredentialIdentityHash()+".dat";
  }

string OakLegacyCredentialFile()
  {
   return "OAKNeoTech\\readonly_"+IntegerToString((long)AccountInfoInteger(ACCOUNT_LOGIN))+".dat";
  }

void OakResetCredentials()
  {
   g_connector_id="";
   g_connector_token="";
   g_access_mode="READ_ONLY";
   g_pair_code_hash="";
   g_loaded_legacy_credentials=false;
  }

bool OakSaveCredentials()
  {
   if(g_connector_id=="" || g_connector_token=="") return false;
   FolderCreate("OAKNeoTech");
   int handle=FileOpen(OakCredentialFile(),FILE_WRITE|FILE_TXT|FILE_ANSI);
   if(handle==INVALID_HANDLE) return false;
   FileWriteString(handle,g_connector_id+"\n"+g_connector_token+"\n"+g_access_mode+"\n"+g_pair_code_hash+"\n");
   FileClose(handle);
   return true;
  }

bool OakLoadCredentials()
  {
   OakResetCredentials();
   int handle=FileOpen(OakCredentialFile(),FILE_READ|FILE_TXT|FILE_ANSI);
   if(handle==INVALID_HANDLE)
     {
      handle=FileOpen(OakLegacyCredentialFile(),FILE_READ|FILE_TXT|FILE_ANSI);
      if(handle==INVALID_HANDLE) return false;
      g_loaded_legacy_credentials=true;
     }
   g_connector_id=FileReadString(handle);
   g_connector_token=FileReadString(handle);
   g_access_mode=FileIsEnding(handle) ? "READ_ONLY" : FileReadString(handle);
   g_pair_code_hash=FileIsEnding(handle) ? "" : FileReadString(handle);
   FileClose(handle);
   StringTrimLeft(g_connector_id); StringTrimRight(g_connector_id);
   StringTrimLeft(g_connector_token); StringTrimRight(g_connector_token);
   StringTrimLeft(g_access_mode); StringTrimRight(g_access_mode);
   StringTrimLeft(g_pair_code_hash); StringTrimRight(g_pair_code_hash);
   if(g_access_mode!="TRADING_CAPABLE_ACCEPTED") g_access_mode="READ_ONLY";
   return g_connector_id!="" && g_connector_token!="";
  }

string OakJsonStringValue(const string json,const string key)
  {
   string needle="\""+key+"\":\"";
   int start=StringFind(json,needle);
   if(start<0) return "";
   start+=StringLen(needle);
   string out="";
   bool escaped=false;
   for(int i=start;i<StringLen(json);i++)
     {
      ushort c=StringGetCharacter(json,i);
      if(escaped)
        {
         if(c=='n') out+="\n";
         else if(c=='r') out+="\r";
         else if(c=='t') out+="\t";
         else out+=ShortToString(c);
         escaped=false;
         continue;
        }
      if(c=='\\') { escaped=true; continue; }
      if(c=='\"') return out;
      out+=ShortToString(c);
     }
   return "";
  }

bool OakHttpPost(const string path,const string json,const string extra_headers,string &response_text,int &http_code)
  {
   string url=OakApiBase()+path;
   string headers="Content-Type: application/json\r\nAccept: application/json\r\n"+extra_headers;
   char body[],response[];
   StringToCharArray(json,body,0,-1,CP_UTF8);
   if(ArraySize(body)>0 && body[ArraySize(body)-1]==0) ArrayResize(body,ArraySize(body)-1);
   string response_headers="";
   ResetLastError();
   http_code=WebRequest("POST",url,headers,InpHttpTimeoutMs,body,response,response_headers);
   int terminal_error=GetLastError();
   response_text=CharArrayToString(response,0,-1,CP_UTF8);
   if(http_code<0)
     {
      if(terminal_error==4014)
         Print("[OAK NeoTech] WebRequest blocked. Add ",OakApiBase()," to MT5 Tools > Options > Expert Advisors > Allow WebRequest for listed URL.");
      else
         PrintFormat("[OAK NeoTech] HTTP request failed err=%d",terminal_error);
      return false;
     }
   return http_code>=200 && http_code<300;
  }

string OakAccountMode()
  {
   long mode=AccountInfoInteger(ACCOUNT_TRADE_MODE);
   if(mode==ACCOUNT_TRADE_MODE_REAL) return "REAL";
   if(mode==ACCOUNT_TRADE_MODE_DEMO) return "DEMO";
   if(mode==ACCOUNT_TRADE_MODE_CONTEST) return "CONTEST";
   return "UNKNOWN";
  }

bool OakReadOnlyVerified()
  {
   return !((bool)AccountInfoInteger(ACCOUNT_TRADE_ALLOWED));
  }

string OakAccountJson(const bool include_numbers)
  {
   string out="{"
      +"\"login\":"+OakJsonQuote(IntegerToString((long)AccountInfoInteger(ACCOUNT_LOGIN)))
      +",\"broker\":"+OakJsonQuote(AccountInfoString(ACCOUNT_COMPANY))
      +",\"server\":"+OakJsonQuote(AccountInfoString(ACCOUNT_SERVER))
      +",\"currency\":"+OakJsonQuote(AccountInfoString(ACCOUNT_CURRENCY))
      +",\"mode\":"+OakJsonQuote(OakAccountMode())
      +",\"tradeAllowed\":"+OakJsonBool((bool)AccountInfoInteger(ACCOUNT_TRADE_ALLOWED))
      +",\"tradeExpert\":"+OakJsonBool((bool)AccountInfoInteger(ACCOUNT_TRADE_EXPERT));
   if(include_numbers)
      out+=",\"balance\":"+OakJsonNumber(AccountInfoDouble(ACCOUNT_BALANCE),2)
         +",\"equity\":"+OakJsonNumber(AccountInfoDouble(ACCOUNT_EQUITY),2)
         +",\"leverage\":"+IntegerToString((long)AccountInfoInteger(ACCOUNT_LEVERAGE));
   return out+"}";
  }

bool OakPair()
  {
   string code=OakNormalizePairingCode(InpPairingCode);
   if(code=="")
     {
      Print("[OAK NeoTech] Pairing code is empty. Generate one at /neotech on OAK Gatekeeper.");
      return false;
     }
   string body="{\"schemaVersion\":"+OakJsonQuote(OAK_PAIR_SCHEMA)
      +",\"pairingCode\":"+OakJsonQuote(code)
      +",\"account\":"+OakAccountJson(false)
      +",\"connectorVersion\":"+OakJsonQuote(OAK_CONNECTOR_VERSION)+"}";
   string response="";
   int code_http=-1;
   if(!OakHttpPost("/api/neotech/connector/pair",body,"",response,code_http))
     {
      PrintFormat("[OAK NeoTech] Pairing failed HTTP=%d",code_http);
      return false;
     }
   string connector_id=OakJsonStringValue(response,"connectorId");
   string connector_token=OakJsonStringValue(response,"connectorToken");
   string access_mode=OakJsonStringValue(response,"accessMode");
   if(connector_id=="" || connector_token=="")
     {
      Print("[OAK NeoTech] Pairing response did not contain connector credentials.");
      return false;
     }
   g_connector_id=connector_id;
   g_connector_token=connector_token;
   g_access_mode=(access_mode=="TRADING_CAPABLE_ACCEPTED" ? "TRADING_CAPABLE_ACCEPTED" : "READ_ONLY");
   g_pair_code_hash=OakSha256(code);
   if(!OakSaveCredentials())
     {
      g_connector_id="";
      g_connector_token="";
      Print("[OAK NeoTech] Pairing succeeded but local credential storage failed; access was not retained.");
      return false;
     }
   g_loaded_legacy_credentials=false;
   Print("[OAK NeoTech] Pairing complete. Mode=",g_access_mode," connector ",StringSubstr(g_connector_id,MathMax(0,StringLen(g_connector_id)-8))," is active.");
   return true;
  }

int OakServerUtcOffsetMinutes(const long server_seconds)
  {
   MqlDateTime dt;
   TimeToStruct((datetime)server_seconds,dt);
   return (dt.mon>=4 && dt.mon<=10) ? 180 : 120;
  }

long OakUtcMscFromServerMsc(const long server_msc)
  {
   long seconds=server_msc/1000;
   long remainder=server_msc-seconds*1000;
   return (seconds-(long)OakServerUtcOffsetMinutes(seconds)*60L)*1000L+remainder;
  }

string OakEntryName(const long entry)
  {
   if(entry==DEAL_ENTRY_IN) return "IN";
   if(entry==DEAL_ENTRY_OUT) return "OUT";
   if(entry==DEAL_ENTRY_OUT_BY) return "OUT_BY";
   return "INOUT";
  }

string OakSideName(const long type)
  {
   return type==DEAL_TYPE_SELL ? "SELL" : "BUY";
  }

string OakReasonName(const long reason)
  {
   if(reason==DEAL_REASON_CLIENT || reason==ORDER_REASON_CLIENT) return "CLIENT";
   if(reason==DEAL_REASON_MOBILE || reason==ORDER_REASON_MOBILE) return "MOBILE";
   if(reason==DEAL_REASON_WEB || reason==ORDER_REASON_WEB) return "WEB";
   if(reason==DEAL_REASON_EXPERT || reason==ORDER_REASON_EXPERT) return "EXPERT";
   return "OTHER";
  }

bool OakForexCalcMode(const long mode)
  {
   return mode==SYMBOL_CALC_MODE_FOREX || mode==SYMBOL_CALC_MODE_FOREX_NO_LEVERAGE;
  }

string OakTradingDealJson(const ulong ticket,bool &reason_complete,bool &product_complete)
  {
   string symbol=HistoryDealGetString(ticket,DEAL_SYMBOL);
   SymbolSelect(symbol,true);
   ulong order_ticket=(ulong)HistoryDealGetInteger(ticket,DEAL_ORDER);
   ulong position_id=(ulong)HistoryDealGetInteger(ticket,DEAL_POSITION_ID);
   long server_msc=(long)HistoryDealGetInteger(ticket,DEAL_TIME_MSC);
   long server_seconds=server_msc/1000;
   long deal_reason=HistoryDealGetInteger(ticket,DEAL_REASON);
   long order_reason=(order_ticket>0 ? HistoryOrderGetInteger(order_ticket,ORDER_REASON) : -1);
   bool reason_reliable=(deal_reason>=0 && order_ticket>0 && order_reason>=0);
   if(!reason_reliable) reason_complete=false;
   string base=SymbolInfoString(symbol,SYMBOL_CURRENCY_BASE);
   string profit=SymbolInfoString(symbol,SYMBOL_CURRENCY_PROFIT);
   long calc_mode=SymbolInfoInteger(symbol,SYMBOL_TRADE_CALC_MODE);
   if(base=="" || profit=="") product_complete=false;
   double sl=(order_ticket>0 ? HistoryOrderGetDouble(order_ticket,ORDER_SL) : 0.0);
   double tp=(order_ticket>0 ? HistoryOrderGetDouble(order_ticket,ORDER_TP) : 0.0);
   double point=SymbolInfoDouble(symbol,SYMBOL_POINT);
   int digits=(int)SymbolInfoInteger(symbol,SYMBOL_DIGITS);
   return "{"
      +"\"ticket\":"+OakJsonQuote(StringFormat("%I64u",ticket))
      +",\"orderTicket\":"+OakJsonQuote(StringFormat("%I64u",order_ticket))
      +",\"positionId\":"+OakJsonQuote(StringFormat("%I64u",position_id))
      +",\"symbol\":"+OakJsonQuote(symbol)
      +",\"baseCurrency\":"+OakJsonQuote(base)
      +",\"profitCurrency\":"+OakJsonQuote(profit)
      +",\"forexCalc\":"+OakJsonBool(OakForexCalcMode(calc_mode))
      +",\"timeMsc\":"+IntegerToString(OakUtcMscFromServerMsc(server_msc))
      +",\"serverUtcOffsetMinutes\":"+IntegerToString(OakServerUtcOffsetMinutes(server_seconds))
      +",\"entry\":"+OakJsonQuote(OakEntryName(HistoryDealGetInteger(ticket,DEAL_ENTRY)))
      +",\"side\":"+OakJsonQuote(OakSideName(HistoryDealGetInteger(ticket,DEAL_TYPE)))
      +",\"dealReason\":"+OakJsonQuote(OakReasonName(deal_reason))
      +",\"orderReason\":"+OakJsonQuote(OakReasonName(order_reason))
      +",\"reasonReliable\":"+OakJsonBool(reason_reliable)
      +",\"magic\":"+IntegerToString((long)HistoryDealGetInteger(ticket,DEAL_MAGIC))
      +",\"comment\":"+OakJsonQuote(HistoryDealGetString(ticket,DEAL_COMMENT))
      +",\"volume\":"+OakJsonNumber(HistoryDealGetDouble(ticket,DEAL_VOLUME),8)
      +",\"price\":"+OakJsonNumber(HistoryDealGetDouble(ticket,DEAL_PRICE),digits)
      +",\"profit\":"+OakJsonNumber(HistoryDealGetDouble(ticket,DEAL_PROFIT),2)
      +",\"commission\":"+OakJsonNumber(HistoryDealGetDouble(ticket,DEAL_COMMISSION),2)
      +",\"swap\":"+OakJsonNumber(HistoryDealGetDouble(ticket,DEAL_SWAP),2)
      +",\"fee\":"+OakJsonNumber(HistoryDealGetDouble(ticket,DEAL_FEE),2)
      +",\"sl\":"+OakJsonNumber(sl,digits)
      +",\"tp\":"+OakJsonNumber(tp,digits)
      +",\"point\":"+OakJsonNumber(point,10)
      +",\"digits\":"+IntegerToString(digits)
      +",\"sltpSnapshotReliable\":"+OakJsonBool(order_ticket>0)
      +",\"sltpTimelineComplete\":false}";
  }

bool OakCashFlowKind(const long type,const double amount,string &kind)
  {
   if(type==DEAL_TYPE_BALANCE)
     {
      kind=amount>=0.0 ? "DEPOSIT" : "WITHDRAWAL";
      return true;
     }
   if(type==DEAL_TYPE_CREDIT) { kind="CREDIT"; return true; }
   if(type==DEAL_TYPE_CHARGE) { kind="FEE"; return true; }
   if(type==DEAL_TYPE_CORRECTION) { kind="CORRECTION"; return true; }
   if(type==DEAL_TYPE_COMMISSION || type==DEAL_TYPE_COMMISSION_DAILY || type==DEAL_TYPE_COMMISSION_MONTHLY) { kind="FEE"; return true; }
   return false;
  }

string OakCashFlowJson(const ulong ticket,const string kind)
  {
   long server_msc=(long)HistoryDealGetInteger(ticket,DEAL_TIME_MSC);
   return "{"
      +"\"ticket\":"+OakJsonQuote(StringFormat("%I64u",ticket))
      +",\"timeMsc\":"+IntegerToString(OakUtcMscFromServerMsc(server_msc))
      +",\"amount\":"+OakJsonNumber(HistoryDealGetDouble(ticket,DEAL_PROFIT),2)
      +",\"kind\":"+OakJsonQuote(kind)
      +",\"comment\":"+OakJsonQuote(HistoryDealGetString(ticket,DEAL_COMMENT))+"}";
  }

string OakNonce()
  {
   string seed=IntegerToString((long)TimeLocal())+":"+IntegerToString((long)GetMicrosecondCount())+":"+IntegerToString(MathRand());
   return StringSubstr(OakSha256(seed),0,32);
  }

bool OakBuildIngest(string &body)
  {
   datetime server_now=TimeTradeServer();
   datetime utc_now=TimeGMT();
   int days=MathMax(30,MathMin(800,InpHistoryDays));
   datetime history_start=(datetime)((long)server_now-(long)days*86400L);
   if(!HistorySelect(history_start,server_now)) return false;

   int total=HistoryDealsTotal();
   string deals_json="[";
   string cash_json="[";
   int trading_count=0;
   int cash_count=0;
   bool truncated=false;
   bool first_deal=true;
   bool first_cash=true;
   bool reason_complete=true;
   bool product_complete=true;
   long earliest_utc=0;

   for(int i=total-1;i>=0;i--)
     {
      ulong ticket=HistoryDealGetTicket(i);
      if(ticket==0) continue;
      long type=HistoryDealGetInteger(ticket,DEAL_TYPE);
      if(type==DEAL_TYPE_BUY || type==DEAL_TYPE_SELL)
        {
         if(trading_count>=OAK_MAX_TRADING_DEALS) { truncated=true; continue; }
         long server_msc=(long)HistoryDealGetInteger(ticket,DEAL_TIME_MSC);
         long utc_seconds=OakUtcMscFromServerMsc(server_msc)/1000;
         if(earliest_utc==0 || utc_seconds<earliest_utc) earliest_utc=utc_seconds;
         string item=OakTradingDealJson(ticket,reason_complete,product_complete);
         if(!first_deal) deals_json+=",";
         deals_json+=item;
         first_deal=false;
         trading_count++;
         continue;
        }
      string kind="";
      double amount=HistoryDealGetDouble(ticket,DEAL_PROFIT);
      if(cash_count<OAK_MAX_CASHFLOWS && OakCashFlowKind(type,amount,kind))
        {
         if(!first_cash) cash_json+=",";
         cash_json+=OakCashFlowJson(ticket,kind);
         first_cash=false;
         cash_count++;
        }
     }
   deals_json+="]";
   cash_json+="]";

   long requested_start_utc=(long)utc_now-(long)days*86400L;
   string history="{"
      +"\"requestedStartUtc\":"+IntegerToString(requested_start_utc)
      +",\"requestedEndUtc\":"+IntegerToString((long)utc_now)
      +",\"earliestDealUtc\":"+(earliest_utc>0 ? IntegerToString(earliest_utc) : "null")
      +",\"complete\":"+OakJsonBool(!truncated)
      +",\"openingReasonComplete\":"+OakJsonBool(reason_complete)
      +",\"productMetadataComplete\":"+OakJsonBool(product_complete)
      +",\"sltpTimelineComplete\":false}";

   string equity="[{\"atUtc\":"+IntegerToString((long)utc_now)
      +",\"balance\":"+OakJsonNumber(AccountInfoDouble(ACCOUNT_BALANCE),2)
      +",\"equity\":"+OakJsonNumber(AccountInfoDouble(ACCOUNT_EQUITY),2)+"}]";

   body="{\"schemaVersion\":"+OakJsonQuote(OAK_INGEST_SCHEMA)
      +",\"collectedAtUtc\":"+IntegerToString((long)utc_now)
      +",\"connectorVersion\":"+OakJsonQuote(OAK_CONNECTOR_VERSION)
      +",\"account\":"+OakAccountJson(true)
      +",\"history\":"+history
      +",\"deals\":"+deals_json
      +",\"cashFlows\":"+cash_json
      +",\"equityPoints\":"+equity+"}";
   return true;
  }

bool OakSync()
  {
   if(g_sync_busy || g_connector_id=="" || g_connector_token=="") return false;
   if(!OakReadOnlyVerified() && g_access_mode!="TRADING_CAPABLE_ACCEPTED")
     {
      Print("[OAK NeoTech] Sync blocked: this connector was paired as READ_ONLY but ACCOUNT_TRADE_ALLOWED is true. Create a Master-enabled pairing on /neotech or re-login with Investor Password.");
      return false;
     }
   g_sync_busy=true;
   string body="";
   if(!OakBuildIngest(body))
     {
      g_sync_busy=false;
      Print("[OAK NeoTech] Unable to read MT5 history.");
      return false;
     }
   long timestamp=(long)TimeGMT();
   string nonce=OakNonce();
   string hash=OakSha256(body);
   string headers="Authorization: Bearer "+g_connector_token+"\r\n"
      +"X-OAK-Connector-Id: "+g_connector_id+"\r\n"
      +"X-OAK-Connector-Timestamp: "+IntegerToString(timestamp)+"\r\n"
      +"X-OAK-Connector-Nonce: "+nonce+"\r\n"
      +"Idempotency-Key: "+hash+"\r\n";
   string response="";
   int http_code=-1;
   bool ok=OakHttpPost("/api/neotech/connector/ingest",body,headers,response,http_code);
   g_sync_busy=false;
   if(!ok)
     {
      PrintFormat("[OAK NeoTech] Sync failed HTTP=%d",http_code);
      return false;
     }
   if(g_loaded_legacy_credentials)
     {
      if(OakSaveCredentials()) g_loaded_legacy_credentials=false;
      else Print("[OAK NeoTech] Legacy credential verified but server-scoped migration could not be saved yet.");
     }
   Print("[OAK NeoTech] Telemetry snapshot synced. No MT5 password was transmitted. Mode=",g_access_mode);
   return true;
  }

int OnInit()
  {
   MathSrand((int)(GetTickCount()^(uint)TimeLocal()));
   g_sync_enabled=false;
   bool loaded=OakLoadCredentials();
   string requested_code=OakNormalizePairingCode(InpPairingCode);
   string requested_hash=requested_code=="" ? "" : OakSha256(requested_code);
   bool capability_mismatch=loaded && !OakReadOnlyVerified() && g_access_mode!="TRADING_CAPABLE_ACCEPTED";
   bool fresh_code=loaded && capability_mismatch && g_pair_code_hash!="" && requested_hash!="" && requested_hash!=g_pair_code_hash;
   bool legacy_master_upgrade=loaded && g_pair_code_hash=="" && requested_hash!="" && capability_mismatch;
   bool must_pair=!loaded || fresh_code || legacy_master_upgrade;
   EventSetTimer(MathMax(60,InpSyncSeconds));
   if(must_pair && !OakPair())
     {
      Print("[OAK NeoTech] Connector stays attached in WAITING_PAIR state for this account. Set a valid pairing code in EA Properties when ready; no detach/attach is required.");
      return INIT_SUCCEEDED;
     }
   if(!OakReadOnlyVerified() && g_access_mode!="TRADING_CAPABLE_ACCEPTED")
     {
      Alert("This connector is paired READ_ONLY but the MT5 session can trade. Generate a fresh Master pairing code on /neotech and enter it in EA Properties; the connector will remain attached.");
      Print("[OAK NeoTech] Connector stays attached in WAITING_AUTHORIZATION state; telemetry sync is disabled for this account.");
      return INIT_SUCCEEDED;
     }
   g_sync_enabled=true;
   OakSync();
   return INIT_SUCCEEDED;
  }

void OnDeinit(const int reason)
  {
   EventKillTimer();
  }

void OnTimer()
  {
   if(g_sync_enabled) OakSync();
  }
