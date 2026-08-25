#property strict
#property version   "1.03"
#property description "OAK cloud bridge + standalone MT5 account manager"

// OAK Cloud Manager EA
// - No Python/desktop runtime required while the MT5 terminal is open.
// - Cloud mailbox: Upstash REST (same v1 keys as dashboard/src/lib/mt5-bridge.ts).
// - Local management: automatic SL/TP, entry netting, BE, close-at-R, R partials,
//   and per-position partial rules armed by Telegram/cloud.
// - WebRequest is intentionally synchronous. The timer uses a short timeout and
//   never retries an ambiguous broker mutation. INVALID_FILL is the only broker
//   request retry, matching the existing Python safety contract.

input group "OAK Cloud Bridge"
input bool   InpBridgeEnabled              = true;
input string InpBridgeProfile              = "";       // Bridge profile
input long   InpExpectedLogin              = 0;        // MT5 account login
input string InpUpstashRestUrl             = "";       // Upstash REST URL
input string InpUpstashRestToken           = "";       // Upstash REST token
input int    InpHttpTimeoutMs              = 1200;
input int    InpPollSeconds                = 1;         // Local manager timer; OnTick remains primary
input int    InpCloudPollSeconds           = 10;        // Upstash queue poll; runtime clamps to 10..15s

input group "Local PC Failover"
input bool   InpLocalFailoverEnabled       = true;      // PC-local backup mailbox; controller owns failover activation
input int    InpLocalFailoverPollSeconds   = 1;         // Local disk mailbox poll; no Redis traffic

input group "Execution"
input long   InpTradeMagic                 = 0;
input int    InpDeviationPoints            = 20;
input bool   InpNetCloseOpposite           = true;
input bool   InpNetSkipSameDirection       = true;
input bool   InpNetRemoveOppositePending   = true;
input double InpMaxLotPerTrade             = 5.0;
input double InpMaxExposurePerSymbol       = 10.0;

input group "Automatic Protection"
input bool   InpManageOpenPositions        = true;
input long   InpManageMagic                = -1;        // -1 = all positions, including manual/mobile
input string InpManagedSymbols             = "";        // Empty = all; comma-separated roots allowed
input bool   InpAutoAttachSLTP              = true;
input double InpFxSLPoints                 = 500.0;
input double InpFxTPPoints                 = 10000.0;
input double InpGoldSLPoints               = 1000.0;
input double InpGoldTPPoints               = 20000.0;

input group "R Management"
input double InpBreakEvenAtR               = 0.0;       // 0 = disabled
input double InpBreakEvenOffsetPoints      = 0.0;
input double InpCloseAtR                   = 0.0;       // 0 = disabled; full close at >= R
input string InpPartialRLevels             = "";        // Example: 1,2
input string InpPartialPercents            = "50";      // 1 pct = current-volume mode; list = original-volume mode

#define OAK_TASK_PREFIX       "oak:mt5:bridge:task:v1:"
#define OAK_QUEUE_PREFIX      "oak:mt5:bridge:queue:v1:"
#define OAK_ARBITER_PREFIX    "oak:mt5:bridge:arbiter:v1:"
#define OAK_HEARTBEAT_PREFIX  "oak:mt5:bridge:heartbeat:v1:"
#define OAK_TASK_TTL          604800
#define OAK_HEARTBEAT_TTL     45
#define OAK_EA_VERSION        "1.03"
#define OAK_LOCAL_DIR         "OAKLocalFailover\\"

string g_profile = "";
long   g_login = 0;
string g_server = "";
bool   g_bridge_ready = false;
datetime g_last_heartbeat = 0;
datetime g_last_cloud_poll = 0;
datetime g_last_cloud_ok = 0;
datetime g_last_local_poll = 0;
int g_cloud_failure_streak = 0;
int g_cloud_success_streak = 0;
double g_partial_r[];
double g_partial_pct[];
string g_pending_final_id = "";
string g_pending_final_task = "";

// -----------------------------------------------------------------------------
// String / JSON helpers (minimal parser for the fixed bridge schema)
// -----------------------------------------------------------------------------
string Trim(string value)
{
   StringTrimLeft(value);
   StringTrimRight(value);
   return value;
}

string Lower(string value)
{
   StringToLower(value);
   return value;
}

string Upper(string value)
{
   StringToUpper(value);
   return value;
}

string JsonEscape(string value)
{
   StringReplace(value, "\\", "\\\\");
   StringReplace(value, "\"", "\\\"");
   StringReplace(value, "\r", "\\r");
   StringReplace(value, "\n", "\\n");
   StringReplace(value, "\t", "\\t");
   return value;
}

string JsonUnescape(string value)
{
   string out = "";
   int n = StringLen(value);
   bool esc = false;
   for(int i=0; i<n; i++)
   {
      ushort c = StringGetCharacter(value, i);
      if(!esc)
      {
         if(c == '\\') { esc = true; continue; }
         out += ShortToString(c);
         continue;
      }
      esc = false;
      if(c == 'n') out += "\n";
      else if(c == 'r') out += "\r";
      else if(c == 't') out += "\t";
      else if(c == 'b') out += ShortToString(8);
      else if(c == 'f') out += ShortToString(12);
      else out += ShortToString(c);
   }
   if(esc) out += "\\";
   return out;
}

int SkipWs(const string text, int pos)
{
   int n = StringLen(text);
   while(pos < n)
   {
      ushort c = StringGetCharacter(text, pos);
      if(c!=' ' && c!='\r' && c!='\n' && c!='\t') break;
      pos++;
   }
   return pos;
}

int JsonValueStart(const string json, const string key)
{
   string needle = "\"" + key + "\"";
   int p = StringFind(json, needle);
   if(p < 0) return -1;
   p = StringFind(json, ":", p + StringLen(needle));
   if(p < 0) return -1;
   return SkipWs(json, p + 1);
}

int JsonValueEnd(const string json, int start)
{
   if(start < 0 || start >= StringLen(json)) return start;
   ushort first = StringGetCharacter(json, start);
   if(first == '"')
   {
      bool esc = false;
      for(int i=start+1; i<StringLen(json); i++)
      {
         ushort c = StringGetCharacter(json, i);
         if(esc) { esc = false; continue; }
         if(c == '\\') { esc = true; continue; }
         if(c == '"') return i + 1;
      }
      return StringLen(json);
   }
   if(first == '{' || first == '[')
   {
      ushort open = first;
      ushort close = (first == '{' ? '}' : ']');
      int depth = 0;
      bool in_string = false;
      bool esc = false;
      for(int i=start; i<StringLen(json); i++)
      {
         ushort c = StringGetCharacter(json, i);
         if(in_string)
         {
            if(esc) { esc = false; continue; }
            if(c == '\\') { esc = true; continue; }
            if(c == '"') in_string = false;
            continue;
         }
         if(c == '"') { in_string = true; continue; }
         if(c == open) depth++;
         else if(c == close)
         {
            depth--;
            if(depth == 0) return i + 1;
         }
      }
      return StringLen(json);
   }
   int i = start;
   while(i < StringLen(json))
   {
      ushort c = StringGetCharacter(json, i);
      if(c == ',' || c == '}') break;
      i++;
   }
   return i;
}

string JsonRaw(const string json, const string key)
{
   int s = JsonValueStart(json, key);
   if(s < 0) return "";
   int e = JsonValueEnd(json, s);
   return Trim(StringSubstr(json, s, e - s));
}

string JsonString(const string json, const string key)
{
   string raw = JsonRaw(json, key);
   if(StringLen(raw) >= 2 && StringGetCharacter(raw,0) == '"' && StringGetCharacter(raw,StringLen(raw)-1) == '"')
      return JsonUnescape(StringSubstr(raw, 1, StringLen(raw)-2));
   return "";
}

long JsonLong(const string json, const string key, long fallback=0)
{
   string raw = JsonRaw(json, key);
   if(raw == "" || raw == "null") return fallback;
   return (long)StringToInteger(raw);
}

double JsonDouble(const string json, const string key, double fallback=0.0)
{
   string raw = JsonRaw(json, key);
   if(raw == "" || raw == "null") return fallback;
   return StringToDouble(raw);
}

string JsonUpsertRaw(string json, const string key, const string raw_value)
{
   int s = JsonValueStart(json, key);
   if(s >= 0)
   {
      int e = JsonValueEnd(json, s);
      return StringSubstr(json, 0, s) + raw_value + StringSubstr(json, e);
   }
   int last = StringLen(json) - 1;
   while(last >= 0 && StringGetCharacter(json,last) != '}') last--;
   if(last < 0) return json;
   string prefix = StringSubstr(json, 0, last);
   string sep = (StringLen(Trim(StringSubstr(prefix, 1))) > 0 ? "," : "");
   return prefix + sep + "\"" + key + "\":" + raw_value + StringSubstr(json,last);
}

string JsonQuote(const string value) { return "\"" + JsonEscape(value) + "\""; }

long NowMs() { return (long)TimeGMT() * 1000; }

void Utf8ToHttpBytes(const string text, char &out[])
{
   uchar bytes[];
   int copied=StringToCharArray(text,bytes,0,WHOLE_ARRAY,CP_UTF8);
   int size=(copied>0 ? copied-1 : 0); // exclude terminal zero
   ArrayResize(out,size);
   for(int i=0;i<size;i++) out[i]=(char)bytes[i];
}

string HttpBytesToUtf8(const char &data[])
{
   int size=ArraySize(data);
   uchar bytes[];
   ArrayResize(bytes,size);
   for(int i=0;i<size;i++) bytes[i]=(uchar)data[i];
   return CharArrayToString(bytes,0,size,CP_UTF8);
}

// -----------------------------------------------------------------------------
// Redis REST helpers
// -----------------------------------------------------------------------------
bool HttpRedis(const string body, string &response)
{
   response = "";
   if(InpUpstashRestUrl == "" || InpUpstashRestToken == "") return false;
   char data[];
   char result[];
   string result_headers = "";
   Utf8ToHttpBytes(body,data);
   string headers = "Authorization: Bearer " + InpUpstashRestToken + "\r\nContent-Type: application/json\r\n";
   ResetLastError();
   int code = WebRequest("POST", InpUpstashRestUrl, headers, InpHttpTimeoutMs, data, result, result_headers);
   if(code < 200 || code >= 300)
   {
      PrintFormat("[OAK-EA] Redis WebRequest failed http=%d err=%d", code, GetLastError());
      return false;
   }
   response = HttpBytesToUtf8(result);
   if(JsonRaw(response, "error") != "" && JsonRaw(response, "error") != "null")
   {
      Print("[OAK-EA] Redis error: ", response);
      return false;
   }
   return true;
}

bool RedisCommand(string &args[], string &result_raw)
{
   string body = "[";
   for(int i=0; i<ArraySize(args); i++)
   {
      if(i > 0) body += ",";
      body += JsonQuote(args[i]);
   }
   body += "]";
   string response = "";
   if(!HttpRedis(body, response)) return false;
   result_raw = JsonRaw(response, "result");
   return true;
}

string RedisResultString(const string raw)
{
   if(StringLen(raw) >= 2 && StringGetCharacter(raw,0) == '"' && StringGetCharacter(raw,StringLen(raw)-1) == '"')
      return JsonUnescape(StringSubstr(raw, 1, StringLen(raw)-2));
   return "";
}

bool RedisGet(const string key, string &value)
{
   string args[]; ArrayResize(args,2); args[0]="GET"; args[1]=key;
   string raw="";
   if(!RedisCommand(args, raw)) return false;
   if(raw == "null") { value=""; return true; }
   value = RedisResultString(raw);
   return true;
}

bool RedisSet(const string key, const string value, int ttl_sec, bool nx, string &server_result)
{
   string args[];
   ArrayResize(args, nx ? 6 : 5);
   args[0]="SET"; args[1]=key; args[2]=value;
   if(nx)
   {
      args[3]="NX"; args[4]="EX"; args[5]=IntegerToString(ttl_sec);
   }
   else
   {
      args[3]="EX"; args[4]=IntegerToString(ttl_sec);
   }
   string raw="";
   if(!RedisCommand(args, raw)) return false;
   server_result = RedisResultString(raw);
   return true;
}

string ProfileKey() { return Lower(Trim(g_profile)); }
string TaskKey(const string id) { return OAK_TASK_PREFIX + id; }
string QueueKey() { return OAK_QUEUE_PREFIX + ProfileKey(); }
string ArbiterKey(const string id) { return OAK_ARBITER_PREFIX + id; }
string HeartbeatKey() { return OAK_HEARTBEAT_PREFIX + ProfileKey(); }

bool RedisLIndex0(const string key, string &value)
{
   string args[]; ArrayResize(args,3); args[0]="LINDEX"; args[1]=key; args[2]="0";
   string raw="";
   if(!RedisCommand(args,raw)) return false;
   value = (raw=="null" ? "" : RedisResultString(raw));
   return true;
}

void RedisLRemOne(const string key, const string value)
{
   string args[]; ArrayResize(args,4); args[0]="LREM"; args[1]=key; args[2]="1"; args[3]=value;
   string ignored=""; RedisCommand(args,ignored);
}

bool RedisHeartbeatAndPeekQueue(const string heartbeat, string &task_id)
{
   // One EVAL replaces a separate heartbeat SET plus queue LINDEX. Upstash
   // treats the Lua invocation as one Redis command while keeping both actions
   // atomic from other clients' perspective.
   string script="redis.call('SET',KEYS[1],ARGV[1],'EX',ARGV[2]); return redis.call('LINDEX',KEYS[2],0)";
   string args[]; ArrayResize(args,7);
   args[0]="EVAL"; args[1]=script; args[2]="2";
   args[3]=HeartbeatKey(); args[4]=QueueKey();
   args[5]=heartbeat; args[6]=IntegerToString(OAK_HEARTBEAT_TTL);
   string raw="";
   if(!RedisCommand(args,raw)) return false;
   task_id=(raw=="null" ? "" : RedisResultString(raw));
   return true;
}

// -----------------------------------------------------------------------------
// Local PC failover mailbox (MetaTrader FILE_COMMON, no Redis dependency)
// -----------------------------------------------------------------------------
string LocalProfileKey()
{
   string value=Lower(Trim(g_profile));
   string out="";
   for(int i=0;i<StringLen(value);i++)
   {
      ushort c=StringGetCharacter(value,i);
      bool safe=(c>='a' && c<='z') || (c>='0' && c<='9') || c=='-' || c=='_';
      out+=safe ? ShortToString(c) : "_";
   }
   return out;
}

string LocalStatusPath() { return OAK_LOCAL_DIR+"status_"+LocalProfileKey()+".json"; }
string LocalAccountKey() { return IntegerToString(g_login); }
string LocalTaskPath(const string ledger) { return OAK_LOCAL_DIR+"task_"+LocalProfileKey()+"_"+LocalAccountKey()+"_"+ledger+".json"; }
string LocalClaimPath(const string ledger) { return OAK_LOCAL_DIR+"claim_"+LocalProfileKey()+"_"+LocalAccountKey()+"_"+ledger+".json"; }
string LocalResultPath(const string ledger) { return OAK_LOCAL_DIR+"result_"+LocalProfileKey()+"_"+LocalAccountKey()+"_"+ledger+".json"; }
string LocalTaskFilter() { return OAK_LOCAL_DIR+"task_"+LocalProfileKey()+"_"+LocalAccountKey()+"_*.json"; }

bool WriteCommonText(const string path,const string text)
{
   int handle=FileOpen(path,FILE_WRITE|FILE_TXT|FILE_ANSI|FILE_COMMON);
   if(handle==INVALID_HANDLE)
   {
      PrintFormat("[OAK-EA] local file write open failed path=%s err=%d",path,GetLastError());
      return false;
   }
   FileWriteString(handle,text);
   FileFlush(handle);
   FileClose(handle);
   return true;
}

bool ReadCommonText(const string path,string &text)
{
   text="";
   int handle=FileOpen(path,FILE_READ|FILE_TXT|FILE_ANSI|FILE_COMMON);
   if(handle==INVALID_HANDLE) return false;
   while(!FileIsEnding(handle)) text+=FileReadString(handle);
   FileClose(handle);
   return true;
}

void DeleteCommonText(const string path)
{
   if(FileIsExist(path,FILE_COMMON)) FileDelete(path,FILE_COMMON);
}

bool IsLowerHex(const string value,const int expected_len)
{
   if(StringLen(value)!=expected_len) return false;
   for(int i=0;i<expected_len;i++)
   {
      ushort c=StringGetCharacter(value,i);
      if(!((c>='0' && c<='9') || (c>='a' && c<='f'))) return false;
   }
   return true;
}

bool IsDigits(const string value)
{
   if(StringLen(value)==0) return false;
   for(int i=0;i<StringLen(value);i++)
   {
      ushort c=StringGetCharacter(value,i);
      if(c<'0' || c>'9') return false;
   }
   return true;
}

bool IsSafeAccountSuffix(const string value)
{
   int n=StringLen(value);
   if(n<8 || n>80) return false;
   for(int i=0;i<n;i++)
   {
      ushort c=StringGetCharacter(value,i);
      if(!((c>='a' && c<='z') || (c>='A' && c<='Z') || (c>='0' && c<='9') || c=='_' || c=='-')) return false;
   }
   return true;
}

string Sha256HexUtf8(const string text)
{
   uchar source[],key[],digest[];
   int copied=StringToCharArray(text,source,0,WHOLE_ARRAY,CP_UTF8);
   if(copied<=0) return "";
   ArrayResize(source,copied-1); // exclude terminal zero from the hashed bytes
   ResetLastError();
   int count=CryptEncode(CRYPT_HASH_SHA256,source,key,digest);
   if(count<=0) return "";
   string out="";
   for(int i=0;i<count;i++) out+=StringFormat("%02x",(int)digest[i]);
   return out;
}

bool CanonicalOriginMatchesAccount(const string origin,const string provider_account_id)
{
   string parts[];
   if(StringSplit(origin,':',parts)!=5) return false;
   if(parts[0]!="tg" || !IsDigits(parts[1]) || !IsDigits(parts[2]) || parts[3]!="mt5" || !IsSafeAccountSuffix(parts[4])) return false;
   long update_id=(long)StringToInteger(parts[1]);
   long command_index=(long)StringToInteger(parts[2]);
   if(update_id<=0 || command_index<0) return false;
   if(IntegerToString(update_id)!=parts[1] || IntegerToString(command_index)!=parts[2]) return false;
   return provider_account_id=="mt5:"+parts[4];
}

bool ValidOriginLedger(const string origin,const string ledger)
{
   if(!IsLowerHex(ledger,40)) return false;
   string hash=Sha256HexUtf8(origin);
   return StringLen(hash)==64 && StringSubstr(hash,0,40)==ledger;
}

bool AtomicCreateCommonText(const string final_path,const string text)
{
   string temp_path=final_path+".tmp."+IntegerToString((long)GetTickCount64())+"."+IntegerToString((long)MathRand());
   if(!WriteCommonText(temp_path,text)) return false;
   ResetLastError();
   bool moved=FileMove(temp_path,FILE_COMMON,final_path,FILE_COMMON); // no FILE_REWRITE: existing destination wins
   if(!moved) DeleteCommonText(temp_path);
   return moved;
}

string TaskIdString(const string task)
{
   string id=JsonString(task,"id");
   if(id=="") id=JsonString(task,"taskId");
   return id;
}

bool ValidateBridgeTaskEnvelope(const string task,string &detail)
{
   detail="";
   if(StringLen(task)<=0 || StringLen(task)>16384) { detail="task payload size is invalid"; return false; }
   if(JsonLong(task,"version",0)!=2) { detail="task version must be 2"; return false; }
   string action=Lower(JsonString(task,"action"));
   if(action!="positions" && action!="entry" && action!="close" && action!="modify" && action!="partial") { detail="unsupported MT5 task action"; return false; }
   string source=Lower(JsonString(task,"source"));
   if(action=="positions")
   {
      if(source!="cloud-read" && source!="local-failover") { detail="invalid read-only task source"; return false; }
   }
   else if(source!="telegram-cloud" && source!="local-failover") { detail="invalid mutation task source"; return false; }
   if(Lower(JsonString(task,"bridgeProfile"))!=ProfileKey()) { detail="bridge profile mismatch"; return false; }
   if(JsonLong(task,"login",0)!=g_login) { detail="login mismatch"; return false; }
   if(JsonString(task,"server")!=g_server) { detail="server mismatch"; return false; }
   string provider=JsonString(task,"providerAccountId");
   if(StringFind(provider,"mt5:")!=0 || !IsSafeAccountSuffix(StringSubstr(provider,4))) { detail="invalid provider account id"; return false; }
   string payload=JsonRaw(task,"payload");
   if(payload=="" || StringLen(payload)>8192) { detail="task payload is missing/too large"; return false; }
   if(action=="positions") return true;

   string origin=JsonString(task,"originKey");
   string ledger=JsonString(task,"ledgerKey");
   string digest=JsonString(task,"taskDigest");
   if(!CanonicalOriginMatchesAccount(origin,provider)) { detail="origin/account identity mismatch"; return false; }
   if(!ValidOriginLedger(origin,ledger)) { detail="origin ledger hash mismatch"; return false; }
   if(!IsLowerHex(digest,64)) { detail="task digest is invalid"; return false; }
   if(action=="entry")
   {
      string protection=JsonRaw(task,"protection");
      if(JsonDouble(protection,"slPoints",0)<=0 || JsonDouble(protection,"tpPoints",0)<=0) { detail="entry protection must contain positive SL/TP points"; return false; }
      string side=Upper(JsonString(payload,"side"));
      if((side!="BUY" && side!="SELL") || JsonString(payload,"symbol")=="" || JsonDouble(payload,"lot",0)<=0) { detail="entry payload is invalid"; return false; }
   }
   return true;
}

string ClaimEnvelope(const string task)
{
   return "{\"version\":2"
      +",\"taskId\":"+JsonQuote(TaskIdString(task))
      +",\"originKey\":"+JsonQuote(JsonString(task,"originKey"))
      +",\"ledgerKey\":"+JsonQuote(JsonString(task,"ledgerKey"))
      +",\"taskDigest\":"+JsonQuote(JsonString(task,"taskDigest"))
      +",\"providerAccountId\":"+JsonQuote(JsonString(task,"providerAccountId"))
      +",\"bridgeProfile\":"+JsonQuote(g_profile)
      +",\"login\":"+IntegerToString(g_login)
      +",\"server\":"+JsonQuote(g_server)
      +",\"action\":"+JsonQuote(Lower(JsonString(task,"action")))
      +",\"source\":"+JsonQuote(Lower(JsonString(task,"source")))
      +",\"at\":"+IntegerToString(NowMs())+"}";
}

void WriteLocalStatus(const bool cloud_ok)
{
   if(!InpLocalFailoverEnabled || g_profile=="") return;
   string json="{\"profile\":"+JsonQuote(g_profile)
      +",\"login\":"+IntegerToString(g_login)
      +",\"server\":"+JsonQuote(g_server)
      +",\"eaVersion\":"+JsonQuote(OAK_EA_VERSION)
      +",\"at\":"+IntegerToString(NowMs())
      +",\"bridgeReady\":"+(g_bridge_ready?"true":"false")
      +",\"cloudOk\":"+(cloud_ok?"true":"false")
      +",\"cloudFailureStreak\":"+IntegerToString(g_cloud_failure_streak)
      +",\"cloudSuccessStreak\":"+IntegerToString(g_cloud_success_streak)
      +",\"lastCloudOk\":"+IntegerToString((long)g_last_cloud_ok*1000)
      +"}";
   WriteCommonText(LocalStatusPath(),json);
}

// -----------------------------------------------------------------------------
// Position state helpers
// -----------------------------------------------------------------------------
string StateKey(const long identifier, const string suffix)
{
   return "OAKM." + IntegerToString(g_login) + "." + IntegerToString(identifier) + "." + suffix;
}

double StateGet(const long identifier, const string suffix, const double fallback=0.0)
{
   string key = StateKey(identifier,suffix);
   return GlobalVariableCheck(key) ? GlobalVariableGet(key) : fallback;
}

void StateSet(const long identifier, const string suffix, const double value)
{
   GlobalVariableSet(StateKey(identifier,suffix), value);
}

void StateDel(const long identifier, const string suffix)
{
   string key=StateKey(identifier,suffix);
   if(GlobalVariableCheck(key)) GlobalVariableDel(key);
}

long SelectedPositionId()
{
   long id = (long)PositionGetInteger(POSITION_IDENTIFIER);
   if(id <= 0) id = (long)PositionGetInteger(POSITION_TICKET);
   return id;
}

int VolumeDigits(double step)
{
   int digits=0;
   double v=step;
   while(digits < 8 && MathAbs(v - MathRound(v)) > 1e-9) { v *= 10.0; digits++; }
   return digits;
}

double NormalizeVolume(const string symbol, double volume)
{
   double minv=SymbolInfoDouble(symbol,SYMBOL_VOLUME_MIN);
   double maxv=SymbolInfoDouble(symbol,SYMBOL_VOLUME_MAX);
   double step=SymbolInfoDouble(symbol,SYMBOL_VOLUME_STEP);
   if(step <= 0) step = minv > 0 ? minv : 0.01;
   volume = MathRound(volume/step)*step;
   if(minv>0) volume=MathMax(minv,volume);
   if(maxv>0) volume=MathMin(maxv,volume);
   return NormalizeDouble(volume,VolumeDigits(step));
}

bool IsGold(const string symbol)
{
   string u=Upper(symbol);
   return StringFind(u,"XAU")>=0 || StringFind(u,"GOLD")>=0;
}

void DefaultProtection(const string symbol, double &sl_points, double &tp_points)
{
   if(IsGold(symbol)) { sl_points=InpGoldSLPoints; tp_points=InpGoldTPPoints; }
   else { sl_points=InpFxSLPoints; tp_points=InpFxTPPoints; }
}

bool SymbolManaged(const string symbol)
{
   if(Trim(InpManagedSymbols)=="") return true;
   string list[];
   int n=StringSplit(InpManagedSymbols,',',list);
   string u=Upper(symbol);
   for(int i=0;i<n;i++)
   {
      string token=Upper(Trim(list[i]));
      if(token!="" && StringFind(u,token)>=0) return true;
   }
   return false;
}

bool SelectedPositionManaged()
{
   if(!InpManageOpenPositions) return false;
   long magic=(long)PositionGetInteger(POSITION_MAGIC);
   if(InpManageMagic!=-1 && magic!=InpManageMagic) return false;
   return SymbolManaged(PositionGetString(POSITION_SYMBOL));
}

bool ParseDoubleList(const string text, double &out[])
{
   ArrayResize(out,0);
   string raw=Trim(text);
   if(raw=="") return true;
   string parts[];
   int n=StringSplit(raw,',',parts);
   for(int i=0;i<n;i++)
   {
      string p=Trim(parts[i]);
      if(p=="") continue;
      double v=StringToDouble(p);
      if(v<=0) continue;
      int size=ArraySize(out);
      ArrayResize(out,size+1);
      out[size]=v;
   }
   return true;
}

// -----------------------------------------------------------------------------
// Broker trade helpers
// -----------------------------------------------------------------------------
ENUM_ORDER_TYPE_FILLING PreferredFilling(const string symbol)
{
   long exec=SymbolInfoInteger(symbol,SYMBOL_TRADE_EXEMODE);
   long flags=SymbolInfoInteger(symbol,SYMBOL_FILLING_MODE);
   if((flags & SYMBOL_FILLING_IOC)==SYMBOL_FILLING_IOC) return ORDER_FILLING_IOC;
   if((flags & SYMBOL_FILLING_FOK)==SYMBOL_FILLING_FOK) return ORDER_FILLING_FOK;
   if(exec != SYMBOL_TRADE_EXECUTION_MARKET) return ORDER_FILLING_RETURN;
   return ORDER_FILLING_FOK;
}

bool RetcodeDone(const uint retcode)
{
   return retcode==TRADE_RETCODE_DONE || retcode==TRADE_RETCODE_DONE_PARTIAL || retcode==TRADE_RETCODE_PLACED;
}

bool SendTradeRequest(MqlTradeRequest &req, MqlTradeResult &res, string &detail)
{
   req.type_filling=PreferredFilling(req.symbol);
   ResetLastError();
   bool sent=OrderSend(req,res);
   if(!sent)
   {
      detail=StringFormat("OrderSend transport error=%d",GetLastError());
      return false; // ambiguous transport result: no blind retry
   }
   if(RetcodeDone(res.retcode)) { detail=res.comment; return true; }
   if(res.retcode!=TRADE_RETCODE_INVALID_FILL)
   {
      detail=StringFormat("retcode=%u %s",res.retcode,res.comment);
      return false;
   }

   ENUM_ORDER_TYPE_FILLING candidates[3]={ORDER_FILLING_IOC,ORDER_FILLING_FOK,ORDER_FILLING_RETURN};
   ENUM_ORDER_TYPE_FILLING first=req.type_filling;
   for(int i=0;i<3;i++)
   {
      if(candidates[i]==first) continue;
      long exec=SymbolInfoInteger(req.symbol,SYMBOL_TRADE_EXEMODE);
      if(candidates[i]==ORDER_FILLING_RETURN && exec==SYMBOL_TRADE_EXECUTION_MARKET) continue;
      req.type_filling=candidates[i];
      ZeroMemory(res);
      ResetLastError();
      sent=OrderSend(req,res);
      if(!sent)
      {
         detail=StringFormat("OrderSend transport error=%d after INVALID_FILL",GetLastError());
         return false;
      }
      if(RetcodeDone(res.retcode)) { detail=res.comment; return true; }
      if(res.retcode!=TRADE_RETCODE_INVALID_FILL) break;
   }
   detail=StringFormat("retcode=%u %s",res.retcode,res.comment);
   return false;
}

bool ModifyPosition(const ulong ticket, double sl, double tp, string &detail)
{
   if(!PositionSelectByTicket(ticket)) { detail="position not found"; return false; }
   string symbol=PositionGetString(POSITION_SYMBOL);
   int digits=(int)SymbolInfoInteger(symbol,SYMBOL_DIGITS);
   MqlTradeRequest req; MqlTradeResult res; ZeroMemory(req); ZeroMemory(res);
   req.action=TRADE_ACTION_SLTP;
   req.position=ticket;
   req.symbol=symbol;
   req.sl=(sl>0 ? NormalizeDouble(sl,digits) : 0.0);
   req.tp=(tp>0 ? NormalizeDouble(tp,digits) : 0.0);
   ResetLastError();
   bool sent=OrderSend(req,res);
   if(!sent) { detail=StringFormat("SLTP transport error=%d",GetLastError()); return false; }
   if(RetcodeDone(res.retcode) || res.retcode==TRADE_RETCODE_NO_CHANGES) { detail=res.comment; return true; }
   detail=StringFormat("SLTP retcode=%u %s",res.retcode,res.comment);
   return false;
}

bool ClosePositionVolume(const ulong ticket, double requested_volume, bool keep_min_remainder, string &detail)
{
   if(!PositionSelectByTicket(ticket)) { detail="position not found"; return true; }
   string symbol=PositionGetString(POSITION_SYMBOL);
   double current=PositionGetDouble(POSITION_VOLUME);
   long ptype=PositionGetInteger(POSITION_TYPE);
   double minv=SymbolInfoDouble(symbol,SYMBOL_VOLUME_MIN);
   double step=SymbolInfoDouble(symbol,SYMBOL_VOLUME_STEP);
   double volume=MathMin(requested_volume,current);
   if(keep_min_remainder && volume>=current-1e-10)
   {
      if(current<=minv+1e-10) { detail="position already at minimum volume; partial skipped"; return false; }
      volume=current-minv;
   }
   if(step>0) volume=MathRound(volume/step)*step;
   volume=NormalizeDouble(volume,VolumeDigits(step>0?step:0.01));
   if(volume<=0 || (minv>0 && volume<minv-1e-10)) { detail="partial volume below broker minimum"; return false; }

   MqlTick tick;
   if(!SymbolInfoTick(symbol,tick)) { detail="tick unavailable"; return false; }
   MqlTradeRequest req; MqlTradeResult res; ZeroMemory(req); ZeroMemory(res);
   req.action=TRADE_ACTION_DEAL;
   req.position=ticket;
   req.symbol=symbol;
   req.volume=volume;
   req.type=(ptype==POSITION_TYPE_BUY ? ORDER_TYPE_SELL : ORDER_TYPE_BUY);
   req.price=(ptype==POSITION_TYPE_BUY ? tick.bid : tick.ask);
   req.deviation=InpDeviationPoints;
   req.magic=(ulong)PositionGetInteger(POSITION_MAGIC);
   req.type_time=ORDER_TIME_GTC;
   req.comment="OAK Manager Close";
   return SendTradeRequest(req,res,detail);
}

bool ClosePositionFull(const ulong ticket, string &detail)
{
   if(!PositionSelectByTicket(ticket)) { detail="already closed"; return true; }
   return ClosePositionVolume(ticket,PositionGetDouble(POSITION_VOLUME),false,detail);
}

bool DeletePending(const ulong ticket, string &detail)
{
   MqlTradeRequest req; MqlTradeResult res; ZeroMemory(req); ZeroMemory(res);
   req.action=TRADE_ACTION_REMOVE;
   req.order=ticket;
   ResetLastError();
   bool sent=OrderSend(req,res);
   if(!sent) { detail=StringFormat("remove transport error=%d",GetLastError()); return false; }
   if(RetcodeDone(res.retcode)) { detail=res.comment; return true; }
   detail=StringFormat("remove retcode=%u %s",res.retcode,res.comment);
   return false;
}

bool IsOppositePending(long order_type, bool entering_buy)
{
   if(entering_buy)
      return order_type==ORDER_TYPE_SELL_LIMIT || order_type==ORDER_TYPE_SELL_STOP || order_type==ORDER_TYPE_SELL_STOP_LIMIT;
   return order_type==ORDER_TYPE_BUY_LIMIT || order_type==ORDER_TYPE_BUY_STOP || order_type==ORDER_TYPE_BUY_STOP_LIMIT;
}

string ResolveSymbol(string requested)
{
   requested=Upper(Trim(requested));
   if(requested=="") return "";
   if(SymbolSelect(requested,true)) return requested;
   if(IsGold(requested))
   {
      string gold[8]={"XAUUSD","GOLD","XAUUSD+","GOLD+","XAUUSD.M","GOLD.M","XAUUSD.PRO","GOLD.PRO"};
      for(int i=0;i<8;i++) if(SymbolSelect(gold[i],true)) return gold[i];
   }
   int total=SymbolsTotal(false);
   string best="";
   int best_diff=1000000;
   for(int i=0;i<total;i++)
   {
      string name=SymbolName(i,false);
      string u=Upper(name);
      if(StringFind(u,requested)>=0 || StringFind(requested,u)>=0)
      {
         int diff=(int)MathAbs(StringLen(name)-StringLen(requested));
         if(diff<best_diff) { best=name; best_diff=diff; }
      }
   }
   if(best!="") SymbolSelect(best,true);
   return best;
}

bool PreEntryNet(const string symbol, bool buy, string &detail)
{
   // Same-direction guard first: do not mutate opposite positions if the new
   // entry will be skipped anyway.
   if(InpNetSkipSameDirection)
   {
      for(int i=PositionsTotal()-1;i>=0;i--)
      {
         ulong ticket=PositionGetTicket(i);
         if(ticket==0) continue;
         if(PositionGetString(POSITION_SYMBOL)!=symbol) continue;
         long type=PositionGetInteger(POSITION_TYPE);
         if((buy && type==POSITION_TYPE_BUY) || (!buy && type==POSITION_TYPE_SELL))
         { detail="same-direction position already exists"; return false; }
      }
   }

   if(InpNetCloseOpposite)
   {
      for(int i=PositionsTotal()-1;i>=0;i--)
      {
         ulong ticket=PositionGetTicket(i);
         if(ticket==0) continue;
         if(PositionGetString(POSITION_SYMBOL)!=symbol) continue;
         long type=PositionGetInteger(POSITION_TYPE);
         bool opposite=(buy && type==POSITION_TYPE_SELL) || (!buy && type==POSITION_TYPE_BUY);
         if(!opposite) continue;
         string close_detail="";
         if(!ClosePositionFull(ticket,close_detail))
         { detail="failed to net opposite #"+IntegerToString((long)ticket)+": "+close_detail; return false; }
      }
   }

   if(InpNetRemoveOppositePending)
   {
      for(int i=OrdersTotal()-1;i>=0;i--)
      {
         ulong ticket=OrderGetTicket(i);
         if(ticket==0) continue;
         if(OrderGetString(ORDER_SYMBOL)!=symbol) continue;
         long type=OrderGetInteger(ORDER_TYPE);
         if(!IsOppositePending(type,buy)) continue;
         string remove_detail="";
         if(!DeletePending(ticket,remove_detail))
         { detail="failed to remove opposite pending #"+IntegerToString((long)ticket)+": "+remove_detail; return false; }
      }
   }
   detail="netting ok";
   return true;
}

bool EntryCommentExists(const string symbol, const string comment, ulong &ticket)
{
   for(int i=PositionsTotal()-1;i>=0;i--)
   {
      ulong t=PositionGetTicket(i);
      if(t==0) continue;
      if(PositionGetString(POSITION_SYMBOL)==symbol && PositionGetString(POSITION_COMMENT)==comment)
      { ticket=t; return true; }
   }
   return false;
}

bool WaitForUsableTick(const string symbol, MqlTick &tick, string &detail)
{
   ResetLastError();
   if(!SymbolSelect(symbol,true))
   {
      detail=StringFormat("symbol select failed: %s err=%d",symbol,GetLastError());
      return false;
   }

   const ulong started=GetTickCount64();
   const ulong timeout_ms=2500;
   bool synchronized=false;
   int last_error=0;
   while(GetTickCount64()-started<=timeout_ms)
   {
      synchronized=SymbolIsSynchronized(symbol);
      ResetLastError();
      if(synchronized && SymbolInfoTick(symbol,tick) && tick.bid>0 && tick.ask>0)
      {
         detail="";
         return true;
      }
      last_error=GetLastError();
      Sleep(50);
   }

   detail=StringFormat(
      "tick unavailable after sync wait: %s synchronized=%s err=%d",
      symbol,
      synchronized ? "yes" : "no",
      last_error
   );
   return false;
}

bool SendMarketEntry(const string symbol, bool buy, double lots, double sl_points, double tp_points, const string comment, ulong &broker_ref, string &detail)
{
   if(lots<=0) { detail="lot must be positive"; return false; }
   if(InpMaxLotPerTrade>0 && lots>InpMaxLotPerTrade+1e-10) { detail="lot exceeds EA max-lot guard"; return false; }
   double minv=SymbolInfoDouble(symbol,SYMBOL_VOLUME_MIN);
   double maxv=SymbolInfoDouble(symbol,SYMBOL_VOLUME_MAX);
   double step=SymbolInfoDouble(symbol,SYMBOL_VOLUME_STEP);
   if(minv<=0 || maxv<=0 || step<=0) { detail="symbol volume constraints unavailable"; return false; }
   lots=NormalizeVolume(symbol,lots);

   if(InpMaxExposurePerSymbol>0)
   {
      double exposure=0;
      for(int i=PositionsTotal()-1;i>=0;i--)
      {
         ulong t=PositionGetTicket(i); if(t==0) continue;
         if(PositionGetString(POSITION_SYMBOL)==symbol) exposure+=PositionGetDouble(POSITION_VOLUME);
      }
      if(exposure+lots>InpMaxExposurePerSymbol+1e-10) { detail="symbol exposure guard exceeded"; return false; }
   }

   ulong existing=0;
   if(comment!="" && EntryCommentExists(symbol,comment,existing))
   { broker_ref=existing; detail="existing entry reconciled by comment"; return true; }

   string net_detail="";
   if(!PreEntryNet(symbol,buy,net_detail)) { detail=net_detail; return false; }
   MqlTick tick;
   if(!WaitForUsableTick(symbol,tick,detail)) return false;
   double point=SymbolInfoDouble(symbol,SYMBOL_POINT);
   int digits=(int)SymbolInfoInteger(symbol,SYMBOL_DIGITS);
   double price=(buy?tick.ask:tick.bid);
   if(price<=0 || point<=0) { detail="price/point unavailable"; return false; }
   if(sl_points<=0 || tp_points<=0) DefaultProtection(symbol,sl_points,tp_points);
   if(sl_points<=0 || tp_points<=0) { detail="SL/TP points must be positive"; return false; }

   MqlTradeRequest req; MqlTradeResult res; ZeroMemory(req); ZeroMemory(res);
   req.action=TRADE_ACTION_DEAL;
   req.symbol=symbol;
   req.volume=lots;
   req.type=(buy?ORDER_TYPE_BUY:ORDER_TYPE_SELL);
   req.price=price;
   req.sl=NormalizeDouble(buy ? price-sl_points*point : price+sl_points*point,digits);
   req.tp=NormalizeDouble(buy ? price+tp_points*point : price-tp_points*point,digits);
   req.deviation=InpDeviationPoints;
   req.magic=(ulong)InpTradeMagic;
   req.type_time=ORDER_TIME_GTC;
   req.comment=comment;
   bool ok=SendTradeRequest(req,res,detail);
   if(ok) broker_ref=(res.order>0?res.order:res.deal);
   return ok;
}

// -----------------------------------------------------------------------------
// Automatic account management
// -----------------------------------------------------------------------------
bool PriceAllowsSL(const string symbol, long ptype, double sl)
{
   if(sl<=0) return true;
   MqlTick tick; if(!SymbolInfoTick(symbol,tick)) return false;
   double point=SymbolInfoDouble(symbol,SYMBOL_POINT);
   double distance=MathMax((double)SymbolInfoInteger(symbol,SYMBOL_TRADE_STOPS_LEVEL),(double)SymbolInfoInteger(symbol,SYMBOL_TRADE_FREEZE_LEVEL))*point;
   if(ptype==POSITION_TYPE_BUY) return sl <= tick.bid-distance+point*0.1;
   return sl >= tick.ask+distance-point*0.1;
}

bool PriceAllowsTP(const string symbol, long ptype, double tp)
{
   if(tp<=0) return true;
   MqlTick tick; if(!SymbolInfoTick(symbol,tick)) return false;
   double point=SymbolInfoDouble(symbol,SYMBOL_POINT);
   double distance=MathMax((double)SymbolInfoInteger(symbol,SYMBOL_TRADE_STOPS_LEVEL),(double)SymbolInfoInteger(symbol,SYMBOL_TRADE_FREEZE_LEVEL))*point;
   if(ptype==POSITION_TYPE_BUY) return tp >= tick.bid+distance-point*0.1;
   return tp <= tick.ask-distance+point*0.1;
}

double CurrentR(long ptype, double open_price, double current_price, double point, double risk_points)
{
   if(point<=0 || risk_points<=0) return 0.0;
   double diff=(ptype==POSITION_TYPE_BUY ? current_price-open_price : open_price-current_price)/point;
   return diff/risk_points;
}

bool AttemptThrottle(const long id, const string name, int seconds)
{
   double last=StateGet(id,"try_"+name,0.0);
   double now=(double)TimeCurrent();
   if(last>0 && now-last<seconds) return false;
   StateSet(id,"try_"+name,now);
   return true;
}

void EnsureSelectedProtection(const ulong ticket, const long id)
{
   if(!InpAutoAttachSLTP) return;
   string symbol=PositionGetString(POSITION_SYMBOL);
   long type=PositionGetInteger(POSITION_TYPE);
   double open=PositionGetDouble(POSITION_PRICE_OPEN);
   double sl=PositionGetDouble(POSITION_SL);
   double tp=PositionGetDouble(POSITION_TP);
   double point=SymbolInfoDouble(symbol,SYMBOL_POINT);
   int digits=(int)SymbolInfoInteger(symbol,SYMBOL_DIGITS);
   double default_sl=0,default_tp=0; DefaultProtection(symbol,default_sl,default_tp);
   bool be_moved=StateGet(id,"be",0)>0.5;
   double target_sl=sl;
   double target_tp=tp;
   if(sl<=0 && default_sl>0)
   {
      if(be_moved)
         target_sl=(type==POSITION_TYPE_BUY ? open+InpBreakEvenOffsetPoints*point : open-InpBreakEvenOffsetPoints*point);
      else
         target_sl=(type==POSITION_TYPE_BUY ? open-default_sl*point : open+default_sl*point);
      target_sl=NormalizeDouble(target_sl,digits);
      if(!PriceAllowsSL(symbol,type,target_sl)) target_sl=0;
   }
   if(tp<=0 && default_tp>0)
   {
      target_tp=(type==POSITION_TYPE_BUY ? open+default_tp*point : open-default_tp*point);
      target_tp=NormalizeDouble(target_tp,digits);
      if(!PriceAllowsTP(symbol,type,target_tp)) target_tp=0;
   }
   bool need=(sl<=0 && target_sl>0) || (tp<=0 && target_tp>0);
   if(!need || !AttemptThrottle(id,"protect",10)) return;
   string detail="";
   ModifyPosition(ticket,(sl>0?sl:target_sl),(tp>0?tp:target_tp),detail);
}

void ManageSelectedPosition(const ulong ticket)
{
   if(!SelectedPositionManaged()) return;
   long id=SelectedPositionId();
   string symbol=PositionGetString(POSITION_SYMBOL);
   long type=PositionGetInteger(POSITION_TYPE);
   double point=SymbolInfoDouble(symbol,SYMBOL_POINT);
   double open=PositionGetDouble(POSITION_PRICE_OPEN);
   double current=PositionGetDouble(POSITION_PRICE_CURRENT);
   double sl=PositionGetDouble(POSITION_SL);
   double volume=PositionGetDouble(POSITION_VOLUME);
   if(point<=0 || open<=0 || volume<=0) return;

   double risk=StateGet(id,"risk",0.0);
   if(risk<=0)
   {
      if(sl>0) risk=MathAbs(open-sl)/point;
      else { double dsl=0,dtp=0; DefaultProtection(symbol,dsl,dtp); risk=dsl; }
      if(risk>0) StateSet(id,"risk",risk);
   }
   if(StateGet(id,"orig",0.0)<=0) StateSet(id,"orig",volume);

   EnsureSelectedProtection(ticket,id);
   double r=CurrentR(type,open,current,point,risk);

   // Full close at configured R before lower-priority partial/BE actions.
   if(InpCloseAtR>0 && risk>0 && r>=InpCloseAtR && StateGet(id,"rr_done",0)<0.5 && AttemptThrottle(id,"rr",5))
   {
      string detail="";
      if(ClosePositionFull(ticket,detail)) StateSet(id,"rr_done",1.0);
      return;
   }

   // R-based partials, persisted as a bit mask.
   if(risk>0 && ArraySize(g_partial_r)>0 && ArraySize(g_partial_pct)>0)
   {
      long mask=(long)StateGet(id,"rmask",0.0);
      bool original_mode=ArraySize(g_partial_pct)>1;
      double original=StateGet(id,"orig",volume);
      for(int i=0;i<ArraySize(g_partial_r) && i<52;i++)
      {
         long bit=((long)1)<<i;
         if((mask & bit)!=0 || r<g_partial_r[i]) continue;
         double pct=(i<ArraySize(g_partial_pct)?g_partial_pct[i]:g_partial_pct[ArraySize(g_partial_pct)-1]);
         double requested=(original_mode?original:volume)*(pct/100.0);
         string detail="";
         if(ClosePositionVolume(ticket,requested,pct<99.9,detail))
         {
            mask|=bit; StateSet(id,"rmask",(double)mask);
            if(!PositionSelectByTicket(ticket)) return;
            volume=PositionGetDouble(POSITION_VOLUME);
         }
         break; // one broker mutation per management pass
      }
   }

   // Dynamic partial armed by cloud: profit currency or absolute price.
   if(StateGet(id,"pp_armed",0)>0.5 && PositionSelectByTicket(ticket))
   {
      int mode=(int)StateGet(id,"pp_mode",0);
      double threshold=StateGet(id,"pp_threshold",0);
      double requested=StateGet(id,"pp_volume",0);
      double profit=PositionGetDouble(POSITION_PROFIT)+PositionGetDouble(POSITION_SWAP);
      double px=PositionGetDouble(POSITION_PRICE_CURRENT);
      bool hit=(mode==1 && profit>=threshold) || (mode==2 && ((type==POSITION_TYPE_BUY && px>=threshold) || (type==POSITION_TYPE_SELL && px<=threshold)));
      if(hit && requested>0 && AttemptThrottle(id,"pp",5))
      {
         string detail="";
         if(ClosePositionVolume(ticket,requested,true,detail))
         {
            StateSet(id,"pp_armed",0); StateDel(id,"pp_mode"); StateDel(id,"pp_threshold"); StateDel(id,"pp_volume");
            if(!PositionSelectByTicket(ticket)) return;
         }
      }
   }

   // Auto break-even. Preserve initial risk in GlobalVariables after SL moves.
   if(InpBreakEvenAtR>0 && risk>0 && r>=InpBreakEvenAtR && StateGet(id,"be",0)<0.5 && AttemptThrottle(id,"be",10))
   {
      if(!PositionSelectByTicket(ticket)) return;
      double cur_sl=PositionGetDouble(POSITION_SL);
      double cur_tp=PositionGetDouble(POSITION_TP);
      int digits=(int)SymbolInfoInteger(symbol,SYMBOL_DIGITS);
      double target=NormalizeDouble(type==POSITION_TYPE_BUY ? open+InpBreakEvenOffsetPoints*point : open-InpBreakEvenOffsetPoints*point,digits);
      bool improves=(cur_sl<=0) || (type==POSITION_TYPE_BUY && target>cur_sl+point*0.1) || (type==POSITION_TYPE_SELL && target<cur_sl-point*0.1);
      if(improves && PriceAllowsSL(symbol,type,target))
      {
         string detail="";
         if(ModifyPosition(ticket,target,cur_tp,detail)) StateSet(id,"be",1.0);
      }
      else if(!improves) StateSet(id,"be",1.0);
   }
}

void ManageAccount()
{
   if(!InpManageOpenPositions) return;
   for(int i=PositionsTotal()-1;i>=0;i--)
   {
      ulong ticket=PositionGetTicket(i);
      if(ticket==0) continue;
      ManageSelectedPosition(ticket);
   }
}

// -----------------------------------------------------------------------------
// Cloud task execution
// -----------------------------------------------------------------------------
string ResultJson(bool ok, const string action, const string detail, bool uncertain=false, const string broker_ref="", const string positions_raw="")
{
   string json="{\"ok\":"+(ok?"true":"false")+",\"action\":"+JsonQuote(action)+",\"detail\":"+JsonQuote(detail);
   if(uncertain) json+=",\"uncertain\":true";
   if(broker_ref!="") json+=",\"brokerRef\":"+JsonQuote(broker_ref);
   if(positions_raw!="") json+=",\"positions\":"+positions_raw;
   json+="}";
   return json;
}

string PositionSnapshotJson()
{
   string out="[";
   bool first=true;
   for(int i=0;i<PositionsTotal();i++)
   {
      ulong ticket=PositionGetTicket(i); if(ticket==0) continue;
      if(!first) out+=","; first=false;
      string symbol=PositionGetString(POSITION_SYMBOL);
      string side=(PositionGetInteger(POSITION_TYPE)==POSITION_TYPE_BUY?"BUY":"SELL");
      out+="{\"ticket\":"+IntegerToString((long)ticket)
         +",\"symbol\":"+JsonQuote(symbol)
         +",\"side\":"+JsonQuote(side)
         +",\"lots\":"+DoubleToString(PositionGetDouble(POSITION_VOLUME),8)
         +",\"profit\":"+DoubleToString(PositionGetDouble(POSITION_PROFIT)+PositionGetDouble(POSITION_SWAP),2)
         +",\"openPrice\":"+DoubleToString(PositionGetDouble(POSITION_PRICE_OPEN),10)
         +",\"currentPrice\":"+DoubleToString(PositionGetDouble(POSITION_PRICE_CURRENT),10)
         +",\"sl\":"+DoubleToString(PositionGetDouble(POSITION_SL),10)
         +",\"tp\":"+DoubleToString(PositionGetDouble(POSITION_TP),10)+"}";
   }
   out+="]";
   return out;
}

string ExecuteEntryTask(const string task)
{
   string payload=JsonRaw(task,"payload");
   string protection=JsonRaw(task,"protection");
   string side=Upper(JsonString(payload,"side"));
   string symbol=ResolveSymbol(JsonString(payload,"symbol"));
   double lots=JsonDouble(payload,"lot",0);
   double slp=JsonDouble(protection,"slPoints",0);
   double tpp=JsonDouble(protection,"tpPoints",0);
   if(symbol=="" || (side!="BUY" && side!="SELL")) return ResultJson(false,"entry","invalid symbol/side");
   string ledger=JsonString(task,"ledgerKey");
   string comment=(IsLowerHex(ledger,40)?"OAK:"+StringSubstr(ledger,0,16):"OAK Cloud");
   ulong ref=0; string detail="";
   bool ok=SendMarketEntry(symbol,side=="BUY",lots,slp,tpp,comment,ref,detail);
   return ResultJson(ok,"entry",ok?(side+" "+symbol+" "+DoubleToString(lots,2)+" lot"):detail,false,ok?IntegerToString((long)ref):"");
}

string ExecuteCloseTask(const string task)
{
   string payload=JsonRaw(task,"payload");
   string scope=Upper(JsonString(payload,"scope"));
   string symbol=(scope=="" || scope=="ALL" ? "" : ResolveSymbol(scope));
   if(scope!="" && scope!="ALL" && symbol=="") return ResultJson(false,"close","close symbol could not be resolved");
   int total=0,closed=0; string failures="";
   ulong tickets[]; ArrayResize(tickets,0);
   for(int i=0;i<PositionsTotal();i++)
   {
      ulong t=PositionGetTicket(i); if(t==0) continue;
      if(symbol!="" && PositionGetString(POSITION_SYMBOL)!=symbol) continue;
      int n=ArraySize(tickets); ArrayResize(tickets,n+1); tickets[n]=t;
   }
   total=ArraySize(tickets);
   for(int i=0;i<total;i++)
   {
      string detail="";
      if(ClosePositionFull(tickets[i],detail)) closed++;
      else { if(failures!="") failures+="; "; failures+="#"+IntegerToString((long)tickets[i])+" "+detail; }
   }
   if(total==0) return ResultJson(true,"close","No matching open position");
   if(closed==total) return ResultJson(true,"close","Closed "+IntegerToString(closed)+" position(s)");
   return ResultJson(false,"close","Closed "+IntegerToString(closed)+"/"+IntegerToString(total)+"; "+failures);
}

string ExecuteModifyTask(const string task)
{
   string payload=JsonRaw(task,"payload");
   string field=Upper(JsonString(payload,"field"));
   string symbol=ResolveSymbol(JsonString(payload,"symbol"));
   double value=JsonDouble(payload,"value",0);
   if((field!="SL" && field!="TP") || symbol=="" || value<=0) return ResultJson(false,"modify","invalid modify request");
   int total=0,updated=0; string failures="";
   ulong tickets[]; ArrayResize(tickets,0);
   for(int i=0;i<PositionsTotal();i++)
   {
      ulong t=PositionGetTicket(i); if(t==0) continue;
      if(PositionGetString(POSITION_SYMBOL)!=symbol) continue;
      int n=ArraySize(tickets); ArrayResize(tickets,n+1); tickets[n]=t;
   }
   total=ArraySize(tickets);
   for(int i=0;i<total;i++)
   {
      if(!PositionSelectByTicket(tickets[i])) continue;
      double sl=PositionGetDouble(POSITION_SL),tp=PositionGetDouble(POSITION_TP);
      if(field=="SL") sl=value; else tp=value;
      string detail="";
      if(ModifyPosition(tickets[i],sl,tp,detail)) updated++;
      else { if(failures!="") failures+="; "; failures+="#"+IntegerToString((long)tickets[i])+" "+detail; }
   }
   if(total==0) return ResultJson(true,"modify","No matching open position");
   if(updated==total) return ResultJson(true,"modify","Updated "+field+" on "+IntegerToString(updated)+" position(s)");
   return ResultJson(false,"modify","Updated "+IntegerToString(updated)+"/"+IntegerToString(total)+"; "+failures);
}

string ExecutePartialTask(const string task)
{
   string payload=JsonRaw(task,"payload");
   long requested_ticket=JsonLong(payload,"ticket",0);
   string requested_symbol=(requested_ticket>0 ? "" : ResolveSymbol(JsonString(payload,"symbol")));
   string mode=Lower(JsonString(payload,"mode"));
   double threshold=JsonDouble(payload,"threshold",0);
   double volume=JsonDouble(payload,"volume",0);
   if((mode!="profit" && mode!="price") || threshold<=0 || volume<=0) return ResultJson(false,"partial","invalid partial rule");

   ulong matched=0; int matches=0;
   for(int i=0;i<PositionsTotal();i++)
   {
      ulong t=PositionGetTicket(i); if(t==0) continue;
      bool match=(requested_ticket>0 ? (long)t==requested_ticket : (requested_symbol!="" && PositionGetString(POSITION_SYMBOL)==requested_symbol));
      if(match) { matched=t; matches++; }
   }
   if(matches==0) return ResultJson(false,"partial","target position not found");
   if(matches>1 && requested_ticket<=0) return ResultJson(false,"partial","symbol target is ambiguous; use ticket");
   if(!PositionSelectByTicket(matched)) return ResultJson(false,"partial","target position disappeared");
   long id=SelectedPositionId();
   StateSet(id,"pp_mode",mode=="profit"?1.0:2.0);
   StateSet(id,"pp_threshold",threshold);
   StateSet(id,"pp_volume",volume);
   StateSet(id,"pp_armed",1.0);
   return ResultJson(true,"partial","Armed "+mode+" partial on #"+IntegerToString((long)matched)+" threshold="+DoubleToString(threshold,2)+" volume="+DoubleToString(volume,2));
}

string ExecuteTask(const string task)
{
   string action=Lower(JsonString(task,"action"));
   if(action=="positions") return ResultJson(true,"positions",IntegerToString(PositionsTotal())+" open position(s)",false,"",PositionSnapshotJson());
   if(action=="entry") return ExecuteEntryTask(task);
   if(action=="close") return ExecuteCloseTask(task);
   if(action=="modify") return ExecuteModifyTask(task);
   if(action=="partial") return ExecutePartialTask(task);
   return ResultJson(false,action==""?"unknown":action,"unsupported MT5 EA action");
}

bool IsSafeReadLedger(const string ledger)
{
   if(StringFind(ledger,"read_")!=0 || StringLen(ledger)<8 || StringLen(ledger)>96) return false;
   for(int i=5;i<StringLen(ledger);i++)
   {
      ushort c=StringGetCharacter(ledger,i);
      if(!((c>='a' && c<='z') || (c>='A' && c<='Z') || (c>='0' && c<='9') || c=='_' || c=='-')) return false;
   }
   return true;
}

string TaskResultEnvelope(const string task,const string result)
{
   bool ok=(JsonRaw(result,"ok")=="true");
   bool uncertain=(JsonRaw(result,"uncertain")=="true");
   string status=uncertain?"uncertain":(ok?"done":"failed");
   return "{\"version\":2"
      +",\"taskId\":"+JsonQuote(TaskIdString(task))
      +",\"originKey\":"+JsonQuote(JsonString(task,"originKey"))
      +",\"ledgerKey\":"+JsonQuote(JsonString(task,"ledgerKey"))
      +",\"taskDigest\":"+JsonQuote(JsonString(task,"taskDigest"))
      +",\"providerAccountId\":"+JsonQuote(JsonString(task,"providerAccountId"))
      +",\"bridgeProfile\":"+JsonQuote(g_profile)
      +",\"login\":"+IntegerToString(g_login)
      +",\"server\":"+JsonQuote(g_server)
      +",\"action\":"+JsonQuote(Lower(JsonString(task,"action")))
      +",\"status\":"+JsonQuote(status)
      +",\"result\":"+result
      +",\"at\":"+IntegerToString(NowMs())+"}";
}

bool LedgerEvidenceMatchesTask(const string envelope,const string task)
{
   return JsonString(envelope,"originKey")==JsonString(task,"originKey")
      && JsonString(envelope,"taskDigest")==JsonString(task,"taskDigest")
      && JsonString(envelope,"providerAccountId")==JsonString(task,"providerAccountId")
      && Lower(JsonString(envelope,"bridgeProfile"))==ProfileKey()
      && JsonLong(envelope,"login",0)==g_login
      && JsonString(envelope,"server")==g_server
      && Lower(JsonString(envelope,"action"))==Lower(JsonString(task,"action"));
}

string ExecuteMutationWithOriginFence(const string task)
{
   string action=Lower(JsonString(task,"action"));
   string ledger=JsonString(task,"ledgerKey");
   string result_path=LocalResultPath(ledger);
   string claim_path=LocalClaimPath(ledger);
   string persisted="";
   if(ReadCommonText(result_path,persisted) && persisted!="")
   {
      if(!LedgerEvidenceMatchesTask(persisted,task))
         return ResultJson(false,action,"origin result ledger conflict; broker replay refused",true);
      string existing_result=JsonRaw(persisted,"result");
      return existing_result!="" ? existing_result : ResultJson(false,action,"origin result ledger is malformed; broker replay refused",true);
   }

   string claim=ClaimEnvelope(task);
   if(!AtomicCreateCommonText(claim_path,claim))
   {
      string existing_claim="";
      if(!ReadCommonText(claim_path,existing_claim) || existing_claim=="")
         return ResultJson(false,action,"atomic origin claim failed without readable owner evidence; broker replay refused",true);
      if(!LedgerEvidenceMatchesTask(existing_claim,task))
         return ResultJson(false,action,"origin claim ledger conflict; broker replay refused",true);
      return ResultJson(false,action,"origin already claimed without final result; automatic replay is disabled",true);
   }

   // The durable claim exists before the only broker-facing ExecuteTask call.
   string result=ExecuteTask(task);
   string envelope=TaskResultEnvelope(task,result);
   if(!AtomicCreateCommonText(result_path,envelope))
   {
      string existing="";
      if(ReadCommonText(result_path,existing) && existing!="" && LedgerEvidenceMatchesTask(existing,task))
      {
         string existing_result=JsonRaw(existing,"result");
         if(existing_result!="") return existing_result;
      }
      return ResultJson(false,action,"broker attempt completed but durable result persistence failed; outcome is uncertain",true);
   }
   return result;
}

bool FindLocalTaskPath(string &task_path)
{
   task_path="";
   string found="";
   long handle=FileFindFirst(LocalTaskFilter(),found,FILE_COMMON);
   if(handle==INVALID_HANDLE) return false;
   FileFindClose(handle);
   task_path=OAK_LOCAL_DIR+found;
   return true;
}

void PollLocalFailoverOnce()
{
   if(!InpLocalFailoverEnabled || g_profile=="") return;
   datetime now=TimeCurrent();
   int interval=(InpLocalFailoverPollSeconds>0?InpLocalFailoverPollSeconds:1);
   if(g_last_local_poll!=0 && now-g_last_local_poll<interval) return;
   g_last_local_poll=now;

   string task_path="";
   if(!FindLocalTaskPath(task_path)) return;
   string task="";
   if(!ReadCommonText(task_path,task) || task=="") return;
   string action=Lower(JsonString(task,"action"));
   string ledger=JsonString(task,"ledgerKey");
   bool ledger_safe=IsLowerHex(ledger,40) || (action=="positions" && IsSafeReadLedger(ledger));
   if(!ledger_safe || task_path!=LocalTaskPath(ledger))
   {
      Print("[OAK-EA] malformed local task path/ledger rejected before broker execution");
      DeleteCommonText(task_path);
      return;
   }

   string validation="";
   if(!ValidateBridgeTaskEnvelope(task,validation))
   {
      string failed=ResultJson(false,action==""?"unknown":action,"invalid local task envelope: "+validation);
      AtomicCreateCommonText(LocalResultPath(ledger),TaskResultEnvelope(task,failed));
      DeleteCommonText(task_path);
      return;
   }

   if(action=="positions")
   {
      string read_result=ExecuteTask(task);
      AtomicCreateCommonText(LocalResultPath(ledger),TaskResultEnvelope(task,read_result));
      DeleteCommonText(task_path);
      return;
   }

   ExecuteMutationWithOriginFence(task);
   DeleteCommonText(task_path);
}

bool StoreTaskJson(const string id, const string task_json)
{
   string server="";
   return RedisSet(TaskKey(id),task_json,OAK_TASK_TTL,false,server);
}

void PersistFinalTask(const string id, const string task_json)
{
   if(StoreTaskJson(id,task_json))
   {
      if(g_pending_final_id==id) { g_pending_final_id=""; g_pending_final_task=""; }
      return;
   }
   g_pending_final_id=id;
   g_pending_final_task=task_json;
   Print("[OAK-EA] final result upload deferred; broker mutation will NOT be replayed");
}

void FlushPendingFinalTask()
{
   if(g_pending_final_id=="" || g_pending_final_task=="") return;
   if(StoreTaskJson(g_pending_final_id,g_pending_final_task))
   {
      g_pending_final_id="";
      g_pending_final_task="";
   }
}

string HeartbeatJson()
{
   return "{\"profile\":"+JsonQuote(g_profile)
      +",\"login\":"+IntegerToString(g_login)
      +",\"server\":"+JsonQuote(g_server)
      +",\"runtime\":\"mql5-ea\""
      +",\"version\":"+JsonQuote(OAK_EA_VERSION)
      +",\"at\":"+IntegerToString(NowMs())+"}";
}

void PublishHeartbeat()
{
   if(!g_bridge_ready) return;
   string server="";
   if(RedisSet(HeartbeatKey(),HeartbeatJson(),OAK_HEARTBEAT_TTL,false,server)) g_last_heartbeat=TimeCurrent();
}

void PollCloudOnce()
{
   if(!g_bridge_ready)
   {
      if(InpLocalFailoverEnabled) WriteLocalStatus(false);
      return;
   }
   datetime now=TimeCurrent();
   int requested=(InpCloudPollSeconds>0 ? InpCloudPollSeconds : 10);
   int interval=(requested<10 ? 10 : (requested>15 ? 15 : requested));
   if(g_last_cloud_poll!=0 && (now-g_last_cloud_poll)<interval) return;
   // Set before network I/O so an outage cannot turn the 1s local timer into a
   // Redis retry storm. Local position management continues independently.
   g_last_cloud_poll=now;

   string task_id="";
   if(!RedisHeartbeatAndPeekQueue(HeartbeatJson(),task_id))
   {
      g_cloud_failure_streak++;
      g_cloud_success_streak=0;
      WriteLocalStatus(false);
      return;
   }
   g_cloud_failure_streak=0;
   g_cloud_success_streak++;
   g_last_cloud_ok=now;
   g_last_heartbeat=now;
   WriteLocalStatus(true);
   FlushPendingFinalTask();
   if(g_pending_final_id!="" || task_id=="") return;
   string claim_token="ea:"+ProfileKey()+":"+IntegerToString((long)GetTickCount64());
   string claim_result="";
   if(!RedisSet(ArbiterKey(task_id),claim_token,OAK_TASK_TTL,true,claim_result)) return;
   RedisLRemOne(QueueKey(),task_id);
   if(claim_result!="OK") return;

   string task="";
   if(!RedisGet(TaskKey(task_id),task) || task=="") return;
   string action=Lower(JsonString(task,"action"));
   string validation="";
   if(JsonString(task,"status")!="pending" || !ValidateBridgeTaskEnvelope(task,validation))
   {
      string rejected=ResultJson(false,action==""?"unknown":action,"MT5 EA rejected task before broker execution: "+(validation==""?"invalid task status":validation));
      task=JsonUpsertRaw(task,"status",JsonQuote("failed"));
      task=JsonUpsertRaw(task,"result",rejected);
      task=JsonUpsertRaw(task,"updatedAt",IntegerToString(NowMs()));
      PersistFinalTask(task_id,task);
      return;
   }

   task=JsonUpsertRaw(task,"status",JsonQuote("running"));
   task=JsonUpsertRaw(task,"updatedAt",IntegerToString(NowMs()));
   if(!StoreTaskJson(task_id,task)) return; // Redis arbiter is owned; no broker call until running state is durable

   // Both cloud and local mutations converge on the same FILE_COMMON origin
   // claim before ExecuteTask. Positions remain read-only and do not consume it.
   string result=(action=="positions" ? ExecuteTask(task) : ExecuteMutationWithOriginFence(task));
   bool ok=(JsonRaw(result,"ok")=="true");
   bool uncertain=(JsonRaw(result,"uncertain")=="true");
   task=JsonUpsertRaw(task,"status",JsonQuote(uncertain?"uncertain":(ok?"done":"failed")));
   task=JsonUpsertRaw(task,"result",result);
   task=JsonUpsertRaw(task,"updatedAt",IntegerToString(NowMs()));
   PersistFinalTask(task_id,task);
}

// -----------------------------------------------------------------------------
// EA lifecycle
// -----------------------------------------------------------------------------
int OnInit()
{
   g_login=(long)AccountInfoInteger(ACCOUNT_LOGIN);
   g_server=AccountInfoString(ACCOUNT_SERVER);
   g_profile=Trim(InpBridgeProfile);
   ParseDoubleList(InpPartialRLevels,g_partial_r);
   ParseDoubleList(InpPartialPercents,g_partial_pct);

   if(InpExpectedLogin>0 && g_login!=InpExpectedLogin)
   {
      PrintFormat("[OAK-EA] ACCOUNT MISMATCH actual=%I64d expected=%I64d. EA stopped.",g_login,InpExpectedLogin);
      return INIT_FAILED;
   }

   g_bridge_ready=InpBridgeEnabled && InpExpectedLogin>0 && g_login==InpExpectedLogin && g_profile!="" && InpUpstashRestUrl!="" && InpUpstashRestToken!="";
   if(InpBridgeEnabled && !g_bridge_ready)
      Print("[OAK-EA] Cloud bridge disabled: set BridgeProfile, ExpectedLogin, Upstash URL/token. Local account management remains active.");
   else if(g_bridge_ready)
      PrintFormat("[OAK-EA] Cloud bridge ready profile=%s login=%I64d server=%s",g_profile,g_login,g_server);

   if(InpLocalFailoverEnabled)
   {
      FolderCreate(OAK_LOCAL_DIR,FILE_COMMON);
      WriteLocalStatus(false);
      PrintFormat("[OAK-EA] Local PC failover mailbox enabled profile=%s",g_profile);
   }

   int timer=(InpPollSeconds>0 ? InpPollSeconds : 1);
   if(!EventSetTimer(timer))
   {
      PrintFormat("[OAK-EA] EventSetTimer failed err=%d",GetLastError());
      return INIT_FAILED;
   }
   if(g_bridge_ready) PublishHeartbeat();
   ManageAccount();
   return INIT_SUCCEEDED;
}

void OnDeinit(const int reason)
{
   EventKillTimer();
   if(InpLocalFailoverEnabled) DeleteCommonText(LocalStatusPath());
}

void OnTimer()
{
   ManageAccount();
   PollCloudOnce();
   PollLocalFailoverOnce();
}

void OnTick()
{
   // Price-triggered management should not wait for the next network poll.
   ManageAccount();
}

void OnTradeTransaction(const MqlTradeTransaction &trans,
                        const MqlTradeRequest &request,
                        const MqlTradeResult &result)
{
   // Attach protection to a newly created/changed position as soon as the
   // terminal reports the trade transaction; later ticks/timers remain backup.
   if(trans.type==TRADE_TRANSACTION_DEAL_ADD || trans.type==TRADE_TRANSACTION_POSITION)
      ManageAccount();
}
