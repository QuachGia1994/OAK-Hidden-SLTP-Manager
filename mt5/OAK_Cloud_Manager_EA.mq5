#property strict
#property version   "1.10"
#property description "OAK local-only MT5 execution manager"

// OAK Local Manager EA
// - Trading control is PC-local only: controller -> FILE_COMMON -> this EA -> MT5.
// - No Upstash/Vercel/cloud mailbox is consulted by the runtime execution path.
// - Local management: automatic SL/TP, entry netting, BE, close-at-R, R partials,
//   and per-position partial rules armed by the local controller.
// - Broker mutations are never blindly retried after an ambiguous transport result.

input group "Local PC Control"
input string InpLocalProfile               = "";        // Optional local label; blank = local_<login>
input string InpLocalProviderAccountId     = "";        // Optional mt5:<suffix>; blank = deterministic login/server hash
input int    InpLocalPollMsV107            = 100;       // FILE_COMMON mailbox poll interval in ms (clamped 100..5000)

// Legacy cloud symbols stay compile-time disabled so older helper code cannot
// appear in MT5 Inputs and cannot perform network polling in local-only mode.
const bool   InpBridgeEnabled              = false;
const bool   InpAutoBindAccount            = false;
const string InpBridgeProfile              = "";
const long   InpExpectedLogin              = 0;
const string InpUpstashRestUrl             = "";
const string InpUpstashRestToken           = "";
const int    InpHttpTimeoutMs              = 1200;
const int    InpCloudPollSeconds           = 10;
const bool   InpLocalPrimaryEnabled        = true;
const bool   InpLocalFailoverEnabled       = true;

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
#define OAK_EA_VERSION        "1.10"
#define OAK_LOCAL_DIR         "OAKLocalFailover\\"

string g_profile = "";
string g_provider_account_id = "";
long   g_login = 0;
string g_server = "";
string g_terminal_id = "";
bool   g_bridge_ready = false;
datetime g_last_bind_attempt = 0;
datetime g_last_heartbeat = 0;
datetime g_last_cloud_poll = 0;
datetime g_last_cloud_ok = 0;
ulong    g_last_local_poll_ms = 0;
ulong    g_last_local_status_ms = 0;
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

string NormalizeServerIdentity(string value)
{
   value=Lower(Trim(value));
   string out="";
   bool pending_space=false;
   for(int i=0;i<StringLen(value);i++)
   {
      ushort c=StringGetCharacter(value,i);
      bool whitespace=(c==' ' || c=='\t' || c=='\r' || c=='\n');
      if(whitespace)
      {
         if(StringLen(out)>0) pending_space=true;
         continue;
      }
      if(pending_space) out+=" ";
      pending_space=false;
      out+=ShortToString(c);
   }
   return out;
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

string AutoBindServerHash()
{
   return StringSubstr(Sha256HexUtf8(NormalizeServerIdentity(g_server)),0,40);
}

string AutoBindExactKey()
{
   return "oak:mt5:bridge:auto-bind:v1:exact:"+IntegerToString(g_login)+":"+AutoBindServerHash();
}

string AutoBindLoginKey()
{
   return "oak:mt5:bridge:auto-bind:v1:login:"+IntegerToString(g_login);
}

string LocalTerminalId()
{
   string identity=Lower(Trim(TerminalInfoString(TERMINAL_DATA_PATH)));
   if(identity=="") identity=Lower(Trim(TerminalInfoString(TERMINAL_PATH)));
   string hash=Sha256HexUtf8(identity);
   return StringLen(hash)==64 ? "mt5term:"+StringSubstr(hash,0,24) : "";
}

bool ConfigureLocalPrimaryIdentity(string &detail)
{
   detail="";
   string profile=Trim(InpLocalProfile);
   if(profile=="") profile="local_"+IntegerToString(g_login);
   string provider=Trim(InpLocalProviderAccountId);
   if(provider=="")
   {
      string hash=Sha256HexUtf8(IntegerToString(g_login)+"|"+NormalizeServerIdentity(g_server));
      if(StringLen(hash)!=64) { detail="local provider hash could not be generated"; return false; }
      provider="mt5:"+StringSubstr(hash,0,32);
   }
   if(StringFind(provider,"mt5:")!=0 || !IsSafeAccountSuffix(StringSubstr(provider,4)))
   {
      detail="InpLocalProviderAccountId must be blank or mt5:<safe-suffix>";
      return false;
   }
   g_profile=profile;
   g_provider_account_id=provider;
   g_bridge_ready=false;
   return true;
}

bool ApplyAutoBindRecord(const string record,const bool exact,string &detail)
{
   detail="";
   if(JsonLong(record,"version",0)!=1) { detail="auto-bind record version mismatch"; return false; }
   if(JsonLong(record,"login",0)!=g_login) { detail="auto-bind login mismatch"; return false; }
   string provider=JsonString(record,"providerAccountId");
   string profile=Trim(JsonString(record,"bridgeProfile"));
   string server_hash=Lower(JsonString(record,"serverHash"));
   if(StringFind(provider,"mt5:")!=0 || !IsSafeAccountSuffix(StringSubstr(provider,4))) { detail="auto-bind provider id is invalid"; return false; }
   if(profile=="") { detail="auto-bind bridge profile is empty"; return false; }
   if(exact && server_hash!=AutoBindServerHash()) { detail="auto-bind server mismatch"; return false; }
   if(!exact && server_hash!="") { detail="login-only auto-bind must not carry a server identity"; return false; }
   g_provider_account_id=provider;
   g_profile=profile;
   return true;
}

bool ResolveAutoBind(string &detail)
{
   detail="";
   g_profile="";
   g_provider_account_id="";
   string record="";
   if(!RedisGet(AutoBindExactKey(),record)) { detail="exact auto-bind lookup unavailable"; return false; }
   if(record!="")
   {
      if(ApplyAutoBindRecord(record,true,detail)) return true;
      return false;
   }
   if(!RedisGet(AutoBindLoginKey(),record)) { detail="login auto-bind lookup unavailable"; return false; }
   if(record!="")
   {
      if(ApplyAutoBindRecord(record,false,detail)) return true;
      return false;
   }
   detail="no enabled MT5 auto-bind mapping for current login/server";
   return false;
}

void RefreshBridgeBinding(const bool force=false)
{
   if(InpLocalPrimaryEnabled)
   {
      // Local-primary identity is derived from the running terminal (login+server,
      // deterministic provider suffix) and never requires Upstash/Vercel credentials.
      // The legacy cloud bridge stays intentionally inactive while local-primary is on.
      if(!force && g_profile!="" && g_provider_account_id!="") return;
      string local_detail="";
      if(!ConfigureLocalPrimaryIdentity(local_detail))
      {
         if(force) PrintFormat("[OAK-EA] Local-primary identity refused: %s",local_detail);
         g_bridge_ready=false;
         return;
      }
      g_bridge_ready=false;
      if(force) PrintFormat("[OAK-EA] Local-primary identity bound profile=%s provider=%s login=%I64d server=%s",g_profile,g_provider_account_id,g_login,g_server);
      return;
   }
   if(!InpBridgeEnabled)
   {
      g_bridge_ready=false;
      g_profile="";
      g_provider_account_id="";
      return;
   }
   datetime now=TimeCurrent();
   if(!force && g_bridge_ready) return;
   if(!force && g_last_bind_attempt!=0 && now-g_last_bind_attempt<15) return;
   g_last_bind_attempt=now;
   g_bridge_ready=false;

   if(InpAutoBindAccount)
   {
      string detail="";
      if(!ResolveAutoBind(detail))
      {
         PrintFormat("[OAK-EA] Cloud bridge waiting for account binding login=%I64d server=%s: %s",g_login,g_server,detail);
         return;
      }
   }
   else
   {
      g_profile=Trim(InpBridgeProfile);
      g_provider_account_id="";
      if(InpExpectedLogin<=0 || g_login!=InpExpectedLogin)
      {
         PrintFormat("[OAK-EA] Fixed bridge mode unbound actual=%I64d expected=%I64d",g_login,InpExpectedLogin);
         return;
      }
   }

   if(g_profile=="" || InpUpstashRestUrl=="" || InpUpstashRestToken=="")
   {
      Print("[OAK-EA] Cloud bridge waiting: profile or Upstash credentials are incomplete. Local account management remains active.");
      return;
   }
   g_bridge_ready=true;
   PrintFormat("[OAK-EA] Cloud bridge bound profile=%s provider=%s login=%I64d server=%s",g_profile,g_provider_account_id==""?"fixed":g_provider_account_id,g_login,g_server);
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
string LocalEventPath(const string event_id)
{
   string hash=Sha256HexUtf8(event_id);
   if(StringLen(hash)!=64) return "";
   return OAK_LOCAL_DIR+"event_"+LocalProfileKey()+"_"+LocalAccountKey()+"_"+StringSubstr(hash,0,40)+".json";
}
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

bool EmitLocalTradeEvent(const string event_id,const string event_type,const string fields_json)
{
   if(g_profile=="" || g_provider_account_id=="" || event_id=="" || event_type=="") return false;
   string path=LocalEventPath(event_id);
   if(path=="") return false;
   string json="{\"version\":1"
      +",\"eventId\":"+JsonQuote(event_id)
      +",\"eventType\":"+JsonQuote(event_type)
      +",\"profile\":"+JsonQuote(g_profile)
      +",\"providerAccountId\":"+JsonQuote(g_provider_account_id)
      +",\"login\":"+IntegerToString(g_login)
      +",\"server\":"+JsonQuote(g_server)
      +",\"at\":"+IntegerToString(NowMs())
      +fields_json
      +"}";
   if(FileIsExist(path,FILE_COMMON)) return true;
   if(AtomicCreateCommonText(path,json)) return true;
   if(FileIsExist(path,FILE_COMMON)) return true;
   PrintFormat("[OAK-EA] local trade event persistence failed type=%s id=%s",event_type,event_id);
   return false;
}

string PositionSideText(const long position_type)
{
   return position_type==POSITION_TYPE_BUY ? "BUY" : "SELL";
}

string ExitDealPositionSide(const long deal_type)
{
   if(deal_type==DEAL_TYPE_SELL) return "BUY";
   if(deal_type==DEAL_TYPE_BUY) return "SELL";
   return "";
}

bool IsPendingOrderTypeValue(const long order_type)
{
   return order_type==ORDER_TYPE_BUY_LIMIT || order_type==ORDER_TYPE_SELL_LIMIT
      || order_type==ORDER_TYPE_BUY_STOP || order_type==ORDER_TYPE_SELL_STOP
      || order_type==ORDER_TYPE_BUY_STOP_LIMIT || order_type==ORDER_TYPE_SELL_STOP_LIMIT;
}

void EmitBreakEvenEvent(const ulong ticket,const long position_id,const string symbol,const long position_type,const double volume,const double sl)
{
   int digits=(int)SymbolInfoInteger(symbol,SYMBOL_DIGITS);
   string event_id="be:"+IntegerToString(position_id);
   string fields=",\"ticket\":"+IntegerToString((long)ticket)
      +",\"positionId\":"+IntegerToString(position_id)
      +",\"symbol\":"+JsonQuote(symbol)
      +",\"side\":"+JsonQuote(PositionSideText(position_type))
      +",\"volume\":"+DoubleToString(volume,8)
      +",\"sl\":"+DoubleToString(sl,digits);
   EmitLocalTradeEvent(event_id,"break_even",fields);
}

double RemainingVolumeForPositionId(const long position_id)
{
   if(position_id<=0) return 0.0;
   for(int i=0;i<PositionsTotal();i++)
   {
      ulong ticket=PositionGetTicket(i);
      if(ticket==0) continue;
      long id=(long)PositionGetInteger(POSITION_IDENTIFIER);
      if(id<=0) id=(long)PositionGetInteger(POSITION_TICKET);
      if(id==position_id) return PositionGetDouble(POSITION_VOLUME);
   }
   return 0.0;
}

void EmitPositionBreakEvenIfApplicable(const ulong ticket)
{
   if(ticket==0 || !PositionSelectByTicket(ticket)) return;
   string symbol=PositionGetString(POSITION_SYMBOL);
   long type=PositionGetInteger(POSITION_TYPE);
   double open=PositionGetDouble(POSITION_PRICE_OPEN);
   double sl=PositionGetDouble(POSITION_SL);
   double point=SymbolInfoDouble(symbol,SYMBOL_POINT);
   if(open<=0 || sl<=0 || point<=0) return;
   bool at_or_beyond_be=(type==POSITION_TYPE_BUY ? sl>=open-point*0.1 : sl<=open+point*0.1);
   if(!at_or_beyond_be) return;
   EmitBreakEvenEvent(ticket,SelectedPositionId(),symbol,type,PositionGetDouble(POSITION_VOLUME),sl);
}

void EmitDealTradeEvents(const ulong deal)
{
   if(deal==0 || !HistoryDealSelect(deal)) return;
   long entry=HistoryDealGetInteger(deal,DEAL_ENTRY);
   long reason=HistoryDealGetInteger(deal,DEAL_REASON);
   long deal_type=HistoryDealGetInteger(deal,DEAL_TYPE);
   ulong order=(ulong)HistoryDealGetInteger(deal,DEAL_ORDER);
   long position_id=HistoryDealGetInteger(deal,DEAL_POSITION_ID);
   string symbol=HistoryDealGetString(deal,DEAL_SYMBOL);
   double volume=HistoryDealGetDouble(deal,DEAL_VOLUME);
   double price=HistoryDealGetDouble(deal,DEAL_PRICE);
   double profit=HistoryDealGetDouble(deal,DEAL_PROFIT);
   int digits=(int)SymbolInfoInteger(symbol,SYMBOL_DIGITS);

   if(reason==DEAL_REASON_SL && (entry==DEAL_ENTRY_OUT || entry==DEAL_ENTRY_OUT_BY))
   {
      string fields=",\"deal\":"+IntegerToString((long)deal)
         +",\"order\":"+IntegerToString((long)order)
         +",\"positionId\":"+IntegerToString(position_id)
         +",\"symbol\":"+JsonQuote(symbol)
         +",\"side\":"+JsonQuote(ExitDealPositionSide(deal_type))
         +",\"volume\":"+DoubleToString(volume,8)
         +",\"price\":"+DoubleToString(price,digits)
         +",\"profit\":"+DoubleToString(profit,2);
      EmitLocalTradeEvent("sl:"+IntegerToString((long)deal),"stop_loss",fields);
   }

   if((entry==DEAL_ENTRY_OUT || entry==DEAL_ENTRY_OUT_BY) && reason!=DEAL_REASON_SL)
   {
      double remaining=RemainingVolumeForPositionId(position_id);
      if(remaining>0)
      {
         string fields=",\"positionId\":"+IntegerToString(position_id)
            +",\"symbol\":"+JsonQuote(symbol)
            +",\"side\":"+JsonQuote(ExitDealPositionSide(deal_type))
            +",\"closedVolume\":"+DoubleToString(volume,8)
            +",\"remainingVolume\":"+DoubleToString(remaining,8)
            +",\"price\":"+DoubleToString(price,digits)
            +",\"profit\":"+DoubleToString(profit,2)
            +",\"deal\":"+IntegerToString((long)deal);
         EmitLocalTradeEvent("partial:"+IntegerToString((long)deal),"partial_close",fields);
      }
   }

   if(entry==DEAL_ENTRY_IN && order>0)
   {
      long order_type=HistoryOrderGetInteger(order,ORDER_TYPE);
      long order_state=HistoryOrderGetInteger(order,ORDER_STATE);
      if(IsPendingOrderTypeValue(order_type) && order_state==ORDER_STATE_FILLED)
      {
         string side=(deal_type==DEAL_TYPE_BUY ? "BUY" : (deal_type==DEAL_TYPE_SELL ? "SELL" : ""));
         string fields=",\"order\":"+IntegerToString((long)order)
            +",\"deal\":"+IntegerToString((long)deal)
            +",\"positionId\":"+IntegerToString(position_id)
            +",\"symbol\":"+JsonQuote(symbol)
            +",\"side\":"+JsonQuote(side)
            +",\"volume\":"+DoubleToString(volume,8)
            +",\"price\":"+DoubleToString(price,digits);
         EmitLocalTradeEvent("pending_fill:"+IntegerToString((long)order)+":"+IntegerToString((long)deal),"pending_fill",fields);
      }
   }
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
   if(action!="positions" && action!="symbol_prepare" && action!="entry" && action!="entry_prepare" && action!="close" && action!="modify" && action!="partial") { detail="unsupported MT5 task action"; return false; }
   string source=Lower(JsonString(task,"source"));
   if(source!="local-primary") { detail="local-only EA accepts local-primary tasks only"; return false; }
   if(Lower(JsonString(task,"bridgeProfile"))!=ProfileKey()) { detail="bridge profile mismatch"; return false; }
   if(JsonLong(task,"login",0)!=g_login) { detail="login mismatch"; return false; }
   if(JsonString(task,"server")!=g_server) { detail="server mismatch"; return false; }
   string provider=JsonString(task,"providerAccountId");
   if(StringFind(provider,"mt5:")!=0 || !IsSafeAccountSuffix(StringSubstr(provider,4))) { detail="invalid provider account id"; return false; }
   if(g_provider_account_id!="" && provider!=g_provider_account_id) { detail="provider account does not match current auto-bound account"; return false; }
   string payload=JsonRaw(task,"payload");
   if(payload=="" || StringLen(payload)>8192) { detail="task payload is missing/too large"; return false; }
   if(action=="positions") return true;
   if(action=="symbol_prepare")
   {
      string side=Upper(JsonString(payload,"side"));
      if((side!="BUY" && side!="SELL") || JsonString(payload,"symbol")=="") { detail="symbol_prepare payload is invalid"; return false; }
      return true;
   }

   string origin=JsonString(task,"originKey");
   string ledger=JsonString(task,"ledgerKey");
   string digest=JsonString(task,"taskDigest");
   if(!CanonicalOriginMatchesAccount(origin,provider)) { detail="origin/account identity mismatch"; return false; }
   if(!ValidOriginLedger(origin,ledger)) { detail="origin ledger hash mismatch"; return false; }
   if(!IsLowerHex(digest,64)) { detail="task digest is invalid"; return false; }
   if(action=="entry" || action=="entry_prepare")
   {
      string protection=JsonRaw(task,"protection");
      if(JsonDouble(protection,"slPoints",0)<=0 || JsonDouble(protection,"tpPoints",0)<=0) { detail="entry protection must contain positive SL/TP points"; return false; }
      string side=Upper(JsonString(payload,"side"));
      if((side!="BUY" && side!="SELL") || JsonString(payload,"symbol")=="" || JsonDouble(payload,"lot",0)<=0) { detail="entry payload is invalid"; return false; }
      if(action=="entry_prepare" && !IsLowerHex(JsonString(payload,"entryLedgerKey"),40)) { detail="entry_prepare requires the final entry ledger key"; return false; }
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

void WriteLocalStatus(const bool ignored_cloud_ok=false)
{
   if(g_profile=="") return;
   string json="{\"profile\":"+JsonQuote(g_profile)
      +",\"providerAccountId\":"+JsonQuote(g_provider_account_id)
      +",\"login\":"+IntegerToString(g_login)
      +",\"server\":"+JsonQuote(g_server)
      +",\"terminalId\":"+JsonQuote(g_terminal_id)
      +",\"eaVersion\":"+JsonQuote(OAK_EA_VERSION)
      +",\"at\":"+IntegerToString(NowMs())
      +",\"localPrimary\":true"
      +",\"localReady\":"+((g_profile!="" && g_provider_account_id!="")?"true":"false")
      +",\"localPollMs\":"+IntegerToString(MathMax(100,MathMin(5000,InpLocalPollMsV107)))
      +",\"fxSlPoints\":"+DoubleToString(InpFxSLPoints,2)
      +",\"fxTpPoints\":"+DoubleToString(InpFxTPPoints,2)
      +",\"goldSlPoints\":"+DoubleToString(InpGoldSLPoints,2)
      +",\"goldTpPoints\":"+DoubleToString(InpGoldTPPoints,2)
      +"}";
   WriteCommonText(LocalStatusPath(),json);
}

bool RefreshRuntimeAccountIdentity(const bool force=false)
{
   long current_login=(long)AccountInfoInteger(ACCOUNT_LOGIN);
   string current_server=AccountInfoString(ACCOUNT_SERVER);
   if(current_login<=0 || Trim(current_server)=="") return false;
   if(!force && current_login==g_login && current_server==g_server && g_profile!="" && g_provider_account_id!="") return true;

   long previous_login=g_login;
   string previous_server=g_server;
   string previous_status=(g_profile!="" ? LocalStatusPath() : "");

   g_login=current_login;
   g_server=current_server;
   g_terminal_id=LocalTerminalId();
   g_profile="";
   g_provider_account_id="";
   g_bridge_ready=false;
   g_last_bind_attempt=0;
   g_last_heartbeat=0;
   g_last_cloud_poll=0;
   g_last_cloud_ok=0;
   g_last_local_poll_ms=0;
   g_last_local_status_ms=0;
   g_cloud_failure_streak=0;
   g_cloud_success_streak=0;
   g_pending_final_id="";
   g_pending_final_task="";

   RefreshBridgeBinding(true);
   if(g_profile=="" || g_provider_account_id=="") return false;

   string current_status=LocalStatusPath();
   if(previous_status!="" && previous_status!=current_status) DeleteCommonText(previous_status);
   WriteLocalStatus(false);
   g_last_local_status_ms=GetTickCount64();
   if(previous_login>0 && (previous_login!=g_login || previous_server!=g_server))
      PrintFormat("[OAK-EA] MT5 account changed; rebound old=%I64d/%s new=%I64d/%s profile=%s",previous_login,previous_server,g_login,g_server,g_profile);
   return true;
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
   if(step<=0) step=(minv>0?minv:0.01);
   double reserve=(keep_min_remainder ? (minv>0?minv:step) : 0.0);
   if(keep_min_remainder && current<=reserve+1e-10)
   {
      detail="position already at minimum volume; partial skipped";
      return false;
   }

   double max_close=(keep_min_remainder ? current-reserve : current);
   double volume=MathMin(requested_volume,max_close);
   // Partial semantics always round DOWN to the broker step. Example:
   // 0.05 * 50% = 0.025 with 0.01 step -> close 0.02, leave 0.03.
   double units=MathFloor((volume/step)+1e-9);
   volume=NormalizeDouble(units*step,VolumeDigits(step));
   if(volume<=0 || (minv>0 && volume<minv-1e-10)) { detail="partial volume below broker minimum"; return false; }
   if(keep_min_remainder && current-volume<reserve-1e-10)
   {
      double safe_units=MathFloor(((current-reserve)/step)+1e-9);
      volume=NormalizeDouble(safe_units*step,VolumeDigits(step));
   }
   if(volume<=0 || (keep_min_remainder && current-volume<reserve-1e-10))
   {
      detail="partial would violate minimum remainder";
      return false;
   }

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

bool SymbolMatchesRequested(string actual, string requested)
{
   actual=Upper(Trim(actual));
   requested=Upper(Trim(requested));
   if(actual=="" || requested=="") return false;
   if(actual==requested) return true;
   if(IsGold(actual) && IsGold(requested)) return true;
   if(StringLen(requested)<6) return false;
   return StringFind(actual,requested)>=0;
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
   if(best!="" && SymbolSelect(best,true)) return best;
   return "";
}

bool PrepareEntrySymbol(const string requested, const bool buy, string &symbol, string &detail)
{
   symbol=ResolveSymbol(requested);
   if(symbol=="")
   {
      detail="symbol not found or could not be added to Market Watch";
      return false;
   }
   if(!SymbolInfoInteger(symbol,SYMBOL_SELECT) && !SymbolSelect(symbol,true))
   {
      detail="symbol "+symbol+" could not be added to Market Watch";
      return false;
   }

   long trade_mode=SymbolInfoInteger(symbol,SYMBOL_TRADE_MODE);
   bool allowed=(trade_mode==SYMBOL_TRADE_MODE_FULL)
      || (buy && trade_mode==SYMBOL_TRADE_MODE_LONGONLY)
      || (!buy && trade_mode==SYMBOL_TRADE_MODE_SHORTONLY);
   if(allowed)
   {
      detail="symbol "+symbol+" is ready for "+(buy?"BUY":"SELL");
      return true;
   }

   string mode="UNKNOWN";
   if(trade_mode==SYMBOL_TRADE_MODE_DISABLED) mode="DISABLED";
   else if(trade_mode==SYMBOL_TRADE_MODE_LONGONLY) mode="LONGONLY";
   else if(trade_mode==SYMBOL_TRADE_MODE_SHORTONLY) mode="SHORTONLY";
   else if(trade_mode==SYMBOL_TRADE_MODE_CLOSEONLY) mode="CLOSEONLY";
   else if(trade_mode==SYMBOL_TRADE_MODE_FULL) mode="FULL";
   detail="symbol "+symbol+" is not tradeable for "+(buy?"BUY":"SELL")+" (trade mode "+mode+")";
   return false;
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

bool PrepareMarketEntryFields(
   const string symbol,
   bool buy,
   double requested_lots,
   double sl_points,
   double tp_points,
   double &lots,
   double &price,
   double &sl_price,
   double &tp_price,
   int &digits,
   string &detail
)
{
   if(requested_lots<=0) { detail="lot must be positive"; return false; }
   if(InpMaxLotPerTrade>0 && requested_lots>InpMaxLotPerTrade+1e-10) { detail="lot exceeds EA max-lot guard"; return false; }
   double minv=SymbolInfoDouble(symbol,SYMBOL_VOLUME_MIN);
   double maxv=SymbolInfoDouble(symbol,SYMBOL_VOLUME_MAX);
   double step=SymbolInfoDouble(symbol,SYMBOL_VOLUME_STEP);
   if(minv<=0 || maxv<=0 || step<=0) { detail="symbol volume constraints unavailable"; return false; }
   lots=NormalizeVolume(symbol,requested_lots);

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

   string net_detail="";
   if(!PreEntryNet(symbol,buy,net_detail)) { detail=net_detail; return false; }
   MqlTick tick;
   if(!WaitForUsableTick(symbol,tick,detail)) return false;
   double point=SymbolInfoDouble(symbol,SYMBOL_POINT);
   digits=(int)SymbolInfoInteger(symbol,SYMBOL_DIGITS);
   price=(buy?tick.ask:tick.bid);
   if(price<=0 || point<=0) { detail="price/point unavailable"; return false; }
   if(sl_points<=0 || tp_points<=0) DefaultProtection(symbol,sl_points,tp_points);
   if(sl_points<=0 || tp_points<=0) { detail="SL/TP points must be positive"; return false; }
   sl_price=NormalizeDouble(buy ? price-sl_points*point : price+sl_points*point,digits);
   tp_price=NormalizeDouble(buy ? price+tp_points*point : price-tp_points*point,digits);
   detail="entry fields prepared";
   return true;
}

bool SendMarketEntry(const string symbol, bool buy, double requested_lots, double sl_points, double tp_points, const string comment, ulong &broker_ref, string &detail)
{
   ulong existing=0;
   if(comment!="" && EntryCommentExists(symbol,comment,existing))
   { broker_ref=existing; detail="existing entry reconciled by comment"; return true; }

   double lots=0,price=0,sl_price=0,tp_price=0;
   int digits=0;
   if(!PrepareMarketEntryFields(symbol,buy,requested_lots,sl_points,tp_points,lots,price,sl_price,tp_price,digits,detail)) return false;

   MqlTradeRequest req; MqlTradeResult res; ZeroMemory(req); ZeroMemory(res);
   req.action=TRADE_ACTION_DEAL;
   req.symbol=symbol;
   req.volume=lots;
   req.type=(buy?ORDER_TYPE_BUY:ORDER_TYPE_SELL);
   req.price=price;
   req.sl=sl_price;
   req.tp=tp_price;
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
         if(ClosePositionVolume(ticket,requested,true,detail))
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
         if(ModifyPosition(ticket,target,cur_tp,detail))
         {
            StateSet(id,"be",1.0);
            EmitBreakEvenEvent(ticket,id,symbol,type,volume,target);
         }
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
         +",\"tp\":"+DoubleToString(PositionGetDouble(POSITION_TP),10)
         +",\"comment\":"+JsonQuote(PositionGetString(POSITION_COMMENT))+"}";
   }
   out+="]";
   return out;
}

string ExecuteSymbolPrepareTask(const string task)
{
   string payload=JsonRaw(task,"payload");
   string side=Upper(JsonString(payload,"side"));
   string symbol="";
   string detail="";
   if(!PrepareEntrySymbol(JsonString(payload,"symbol"),side=="BUY",symbol,detail))
      return ResultJson(false,"symbol_prepare",detail);
   return "{\"ok\":true"
      +",\"action\":\"symbol_prepare\""
      +",\"detail\":"+JsonQuote(detail)
      +",\"resolvedSymbol\":"+JsonQuote(symbol)
      +"}";
}

string ExecuteEntryPrepareTask(const string task)
{
   string payload=JsonRaw(task,"payload");
   string protection=JsonRaw(task,"protection");
   string side=Upper(JsonString(payload,"side"));
   string symbol="";
   string symbol_detail="";
   if(!PrepareEntrySymbol(JsonString(payload,"symbol"),side=="BUY",symbol,symbol_detail))
      return ResultJson(false,"entry_prepare",symbol_detail);
   double requested_lots=JsonDouble(payload,"lot",0);
   double slp=JsonDouble(protection,"slPoints",0);
   double tpp=JsonDouble(protection,"tpPoints",0);
   string entry_ledger=JsonString(payload,"entryLedgerKey");
   if((side!="BUY" && side!="SELL") || !IsLowerHex(entry_ledger,40))
      return ResultJson(false,"entry_prepare","invalid side/final entry ledger");

   string comment="OAK:"+StringSubstr(entry_ledger,0,16);
   ulong existing=0;
   if(EntryCommentExists(symbol,comment,existing))
      return ResultJson(false,"entry_prepare","entry comment already exists; UI replay refused",true,IntegerToString((long)existing));

   double lots=0,price=0,sl_price=0,tp_price=0;
   int digits=0;
   string detail="";
   if(!PrepareMarketEntryFields(symbol,side=="BUY",requested_lots,slp,tpp,lots,price,sl_price,tp_price,digits,detail))
      return ResultJson(false,"entry_prepare",detail);

   return "{\"ok\":true"
      +",\"action\":\"entry_prepare\""
      +",\"detail\":\"EA guards passed; MT5 UI fields prepared\""
      +",\"resolvedSymbol\":"+JsonQuote(symbol)
      +",\"side\":"+JsonQuote(side)
      +",\"volumeText\":"+JsonQuote(DoubleToString(lots,8))
      +",\"slText\":"+JsonQuote(DoubleToString(sl_price,digits))
      +",\"tpText\":"+JsonQuote(DoubleToString(tp_price,digits))
      +",\"comment\":"+JsonQuote(comment)
      +"}";
}

string ExecuteEntryTask(const string task)
{
   string payload=JsonRaw(task,"payload");
   string protection=JsonRaw(task,"protection");
   string side=Upper(JsonString(payload,"side"));
   string symbol="";
   string symbol_detail="";
   if(!PrepareEntrySymbol(JsonString(payload,"symbol"),side=="BUY",symbol,symbol_detail))
      return ResultJson(false,"entry",symbol_detail);
   double lots=JsonDouble(payload,"lot",0);
   double slp=JsonDouble(protection,"slPoints",0);
   double tpp=JsonDouble(protection,"tpPoints",0);
   if(side!="BUY" && side!="SELL") return ResultJson(false,"entry","invalid side");
   string ledger=JsonString(task,"ledgerKey");
   string comment=(IsLowerHex(ledger,40)?"OAK:"+StringSubstr(ledger,0,16):"OAK Cloud");
   ulong ref=0; string detail="";
   bool ok=SendMarketEntry(symbol,side=="BUY",lots,slp,tpp,comment,ref,detail);
   return ResultJson(ok,"entry",ok?(side+" "+symbol+" "+DoubleToString(lots,2)+" lot"):detail,false,ok?IntegerToString((long)ref):"");
}

string ExecuteCloseTask(const string task)
{
   string payload=JsonRaw(task,"payload");
   string scope=Upper(Trim(JsonString(payload,"scope")));
   int total=0,closed=0; string failures="";
   ulong tickets[]; ArrayResize(tickets,0);
   for(int i=0;i<PositionsTotal();i++)
   {
      ulong t=PositionGetTicket(i); if(t==0) continue;
      if(scope!="" && scope!="ALL" && !SymbolMatchesRequested(PositionGetString(POSITION_SYMBOL),scope)) continue;
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
   if(action=="symbol_prepare") return ExecuteSymbolPrepareTask(task);
   if(action=="entry_prepare") return ExecuteEntryPrepareTask(task);
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

void PollLocalOnce()
{
   if(g_profile=="") return;
   // Monotonic ms throttle (GetTickCount64): broker TimeCurrent() has 1s resolution
   // and would cap scheduled-entry dispatch latency at whole seconds.
   ulong now_ms=GetTickCount64();
   ulong interval=(ulong)MathMax(100,MathMin(5000,InpLocalPollMsV107));
   if(g_last_local_poll_ms!=0 && now_ms-g_last_local_poll_ms<interval) return;
   g_last_local_poll_ms=now_ms;
   if(g_last_local_status_ms==0 || now_ms-g_last_local_status_ms>=5000)
   {
      WriteLocalStatus(false);
      g_last_local_status_ms=now_ms;
   }

   string task_path="";
   if(!FindLocalTaskPath(task_path)) return;
   string task="";
   if(!ReadCommonText(task_path,task) || task=="") return;
   string action=Lower(JsonString(task,"action"));
   string ledger=JsonString(task,"ledgerKey");
   bool read_action=(action=="positions" || action=="symbol_prepare");
   bool ledger_safe=IsLowerHex(ledger,40) || (read_action && IsSafeReadLedger(ledger));
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

   if(read_action)
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
      +",\"providerAccountId\":"+JsonQuote(g_provider_account_id)
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
   g_login=0;
   g_server="";
   g_terminal_id="";
   g_profile="";
   g_provider_account_id="";
   g_bridge_ready=false;
   g_last_bind_attempt=0;
   g_pending_final_id="";
   g_pending_final_task="";
   g_last_local_poll_ms=0;
   g_last_local_status_ms=0;
   ParseDoubleList(InpPartialRLevels,g_partial_r);
   ParseDoubleList(InpPartialPercents,g_partial_pct);

   FolderCreate(OAK_LOCAL_DIR,FILE_COMMON);
   if(!RefreshRuntimeAccountIdentity(true))
   {
      Print("[OAK-EA] Current MT5 account identity is unavailable; initialization refused.");
      return INIT_FAILED;
   }
   PrintFormat("[OAK-EA] Local-only mailbox enabled profile=%s provider=%s",g_profile,g_provider_account_id);

   // Millisecond timer drives the local FILE_COMMON mailbox near-realtime.
   int timer_ms=(InpLocalPollMsV107>0?MathMax(100,MathMin(5000,InpLocalPollMsV107)):100);
   if(!EventSetMillisecondTimer(timer_ms))
   {
      PrintFormat("[OAK-EA] EventSetMillisecondTimer failed err=%d; falling back to 1s timer",GetLastError());
      if(!EventSetTimer(1))
      {
         PrintFormat("[OAK-EA] EventSetTimer failed err=%d",GetLastError());
         return INIT_FAILED;
      }
   }
   if(g_bridge_ready) PublishHeartbeat();
   ManageAccount();
   return INIT_SUCCEEDED;
}

void OnDeinit(const int reason)
{
   EventKillTimer();
   DeleteCommonText(LocalStatusPath());
}

void OnTimer()
{
   if(!RefreshRuntimeAccountIdentity(false)) return;
   ManageAccount();
   PollLocalOnce();
}

void OnTick()
{
   // Price-triggered management should not wait for the next network poll.
   if(!RefreshRuntimeAccountIdentity(false)) return;
   ManageAccount();
}

void OnTradeTransaction(const MqlTradeTransaction &trans,
                        const MqlTradeRequest &request,
                        const MqlTradeResult &result)
{
   if(!RefreshRuntimeAccountIdentity(false)) return;
   // Persist broker-confirmed lifecycle events locally; the PC controller owns
   // Telegram delivery so no bot token is ever embedded in this EA.
   if(trans.type==TRADE_TRANSACTION_DEAL_ADD)
      EmitDealTradeEvents(trans.deal);
   if(trans.type==TRADE_TRANSACTION_POSITION)
      EmitPositionBreakEvenIfApplicable(trans.position);

   // Attach protection to a newly created/changed position as soon as the
   // terminal reports the trade transaction; later ticks/timers remain backup.
   if(trans.type==TRADE_TRANSACTION_DEAL_ADD || trans.type==TRADE_TRANSACTION_POSITION)
      ManageAccount();
}
