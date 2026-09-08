#property strict
#property version   "1.06"
#property description "OAK NeoTech C5 re-entry reminder only. Read-only; never sends, modifies or closes trades."

#include "neotech\\NeoTechC5Reminder.mqh"

input group "1. TAI KHOAN"
input long InpExpectedLogin             = 0;  // Bat buoc: login MT5 dang gan EA

input group "2. NHAC C5"
input int  InpTimerSeconds              = 2;  // Chu ky day reminder qua local Telegram controller
input int  InpStartupCatchupMinutes     = 30; // Phuc hoi lenh dang mo gan day sau attach/restart

#define NC5_LOCAL_FORWARD_DIR "OAKLocalFailover\\"
#define NC5_MAX_SEEN_DEALS 256

struct NC5Reminder
  {
   ulong deal_ticket;
   string symbol;
   string text;
  };

NC5Reminder g_reminder_queue[];
ulong g_seen_deals[];

bool NC5WriteCommonText(const string path,const string text)
  {
   int handle=FileOpen(path,FILE_WRITE|FILE_TXT|FILE_ANSI|FILE_COMMON,0,CP_UTF8);
   if(handle==INVALID_HANDLE)
     {
      PrintFormat("[NEOTECH-C5] FileOpen write failed path=%s err=%d",path,GetLastError());
      return false;
     }
   FileWriteString(handle,text);
   FileFlush(handle);
   FileClose(handle);
   return true;
  }

bool NC5ReadCommonText(const string path,string &text)
  {
   text="";
   int handle=FileOpen(path,FILE_READ|FILE_TXT|FILE_ANSI|FILE_COMMON,0,CP_UTF8);
   if(handle==INVALID_HANDLE) return false;
   while(!FileIsEnding(handle)) text+=FileReadString(handle);
   FileClose(handle);
   return true;
  }

void NC5DeleteCommon(const string path)
  {
   if(FileIsExist(path,FILE_COMMON)) FileDelete(path,FILE_COMMON);
  }

bool NC5WriteCommonAtomic(const string final_path,const string text)
  {
   if(FileIsExist(final_path,FILE_COMMON)) return true;
   const string temp_path=final_path+".tmp."+IntegerToString((long)GetTickCount64())+"."+IntegerToString((long)MathRand());
   if(!NC5WriteCommonText(temp_path,text)) return false;
   ResetLastError();
   const bool moved=FileMove(temp_path,FILE_COMMON,final_path,FILE_COMMON);
   if(!moved) NC5DeleteCommon(temp_path);
   return moved || FileIsExist(final_path,FILE_COMMON);
  }

string NC5NormalizeServerIdentity(string value)
  {
   value=NC5Lower(NC5Trim(value));
   string out="";
   bool pending_space=false;
   for(int i=0;i<StringLen(value);i++)
     {
      const ushort c=StringGetCharacter(value,i);
      const bool whitespace=(c==' ' || c=='\t' || c=='\r' || c=='\n');
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

string NC5LocalProfileKey(string value)
  {
   value=NC5Lower(NC5Trim(value));
   string out="";
   for(int i=0;i<StringLen(value);i++)
     {
      const ushort c=StringGetCharacter(value,i);
      const bool safe=(c>='a' && c<='z') || (c>='0' && c<='9') || c=='-' || c=='_';
      out+=safe ? ShortToString(c) : "_";
     }
   return out;
  }

bool NC5LocalForwardIdentity(string &profile,string &provider_account_id)
  {
   profile="";
   provider_account_id="";
   const long current_login=(long)AccountInfoInteger(ACCOUNT_LOGIN);
   const string current_server=NC5NormalizeServerIdentity(AccountInfoString(ACCOUNT_SERVER));
   const long now_msc=(long)TimeGMT()*1000L;
   string found="";
   const long search=FileFindFirst(NC5_LOCAL_FORWARD_DIR+"status_*.json",found,FILE_COMMON);
   if(search==INVALID_HANDLE) return false;
   do
     {
      string json="";
      long login=0,at=0;
      string server="",candidate_profile="",candidate_provider="";
      if(!NC5ReadCommonText(NC5_LOCAL_FORWARD_DIR+found,json)) continue;
      if(!NC5JsonGetLong(json,"login",login) || login!=current_login) continue;
      if(!NC5JsonGetString(json,"server",server) || NC5NormalizeServerIdentity(server)!=current_server) continue;
      if(!NC5JsonGetString(json,"profile",candidate_profile) || NC5LocalProfileKey(candidate_profile)=="") continue;
      if(!NC5JsonGetString(json,"providerAccountId",candidate_provider) || StringFind(candidate_provider,"mt5:")!=0) continue;
      if(!NC5JsonGetLong(json,"at",at) || at<=0 || (now_msc>0 && MathAbs((double)(now_msc-at))>120000.0)) continue;
      profile=candidate_profile;
      provider_account_id=candidate_provider;
      break;
     }
   while(FileFindNext(search,found));
   FileFindClose(search);
   return profile!="" && provider_account_id!="";
  }

bool NC5EmitReminder(const ulong deal_ticket,const string canonical_symbol,const string text)
  {
   string profile="",provider_account_id="";
   if(deal_ticket==0 || canonical_symbol=="" || text=="" || !NC5LocalForwardIdentity(profile,provider_account_id)) return false;
   const long login=(long)AccountInfoInteger(ACCOUNT_LOGIN);
   const string event_id="neotech_c5:"+IntegerToString((long)deal_ticket);
   const string hash=NC5Sha256Hex(event_id);
   if(StringLen(hash)!=64) return false;
   const string path=NC5_LOCAL_FORWARD_DIR+"event_"+NC5LocalProfileKey(profile)+"_"+IntegerToString(login)+"_"+StringSubstr(hash,0,40)+".json";
   const string json="{\"version\":1"
      +",\"eventId\":"+NC5JsonQuote(event_id)
      +",\"eventType\":\"neotech_c5_reentry\""
      +",\"profile\":"+NC5JsonQuote(profile)
      +",\"providerAccountId\":"+NC5JsonQuote(provider_account_id)
      +",\"login\":"+IntegerToString(login)
      +",\"server\":"+NC5JsonQuote(AccountInfoString(ACCOUNT_SERVER))
      +",\"at\":"+IntegerToString((long)TimeGMT()*1000L)
      +",\"deal\":"+IntegerToString((long)deal_ticket)
      +",\"symbol\":"+NC5JsonQuote(canonical_symbol)
      +",\"text\":"+NC5JsonQuote(text)+"}";
   if(NC5WriteCommonAtomic(path,json)) return true;
   PrintFormat("[NEOTECH-C5] local reminder persistence failed deal=%I64u",deal_ticket);
   return false;
  }

bool NC5DealSeen(const ulong deal_ticket)
  {
   for(int i=0;i<ArraySize(g_seen_deals);i++) if(g_seen_deals[i]==deal_ticket) return true;
   return false;
  }

void NC5RememberDeal(const ulong deal_ticket)
  {
   if(ArraySize(g_seen_deals)>=NC5_MAX_SEEN_DEALS)
     {
      for(int i=1;i<ArraySize(g_seen_deals);i++) g_seen_deals[i-1]=g_seen_deals[i];
      ArrayResize(g_seen_deals,NC5_MAX_SEEN_DEALS-1);
     }
   const int n=ArraySize(g_seen_deals);
   ArrayResize(g_seen_deals,n+1);
   g_seen_deals[n]=deal_ticket;
  }

void NC5QueueReminder(const ulong deal_ticket,const string canonical_symbol,const long opened_server_seconds)
  {
   if(deal_ticket==0 || canonical_symbol=="" || opened_server_seconds<=0 || NC5DealSeen(deal_ticket)) return;
   const string text=NC5ReminderText(canonical_symbol,opened_server_seconds);
   if(text=="") return;
   NC5RememberDeal(deal_ticket);
   const int n=ArraySize(g_reminder_queue);
   ArrayResize(g_reminder_queue,n+1);
   g_reminder_queue[n].deal_ticket=deal_ticket;
   g_reminder_queue[n].symbol=canonical_symbol;
   g_reminder_queue[n].text=text;
  }

bool NC5PositionEpisodeOpening(const ulong position_id,ulong &deal_ticket,string &broker_symbol,long &opened_server_seconds)
  {
   deal_ticket=0;
   broker_symbol="";
   opened_server_seconds=0;
   if(position_id==0 || !HistorySelectByPosition(position_id)) return false;
   ulong first_in_ticket=0,latest_inout_ticket=0;
   long first_in_msc=0,latest_inout_msc=0;
   string first_in_symbol="",latest_inout_symbol="";
   const int total=HistoryDealsTotal();
   for(int i=0;i<total;i++)
     {
      const ulong ticket=HistoryDealGetTicket(i);
      if(ticket==0) continue;
      const int type=(int)HistoryDealGetInteger(ticket,DEAL_TYPE);
      if(type!=DEAL_TYPE_BUY && type!=DEAL_TYPE_SELL) continue;
      const int entry=(int)HistoryDealGetInteger(ticket,DEAL_ENTRY);
      if(entry!=DEAL_ENTRY_IN && entry!=DEAL_ENTRY_INOUT) continue;
      const long time_msc=(long)HistoryDealGetInteger(ticket,DEAL_TIME_MSC);
      const string symbol=HistoryDealGetString(ticket,DEAL_SYMBOL);
      if(entry==DEAL_ENTRY_INOUT)
        {
         if(latest_inout_ticket==0 || time_msc>=latest_inout_msc)
           {
            latest_inout_ticket=ticket;
            latest_inout_msc=time_msc;
            latest_inout_symbol=symbol;
           }
         continue;
        }
      if(first_in_ticket==0 || time_msc<first_in_msc)
        {
         first_in_ticket=ticket;
         first_in_msc=time_msc;
         first_in_symbol=symbol;
        }
     }
   if(latest_inout_ticket>0)
     {
      deal_ticket=latest_inout_ticket;
      broker_symbol=latest_inout_symbol;
      opened_server_seconds=latest_inout_msc/1000L;
      return opened_server_seconds>0;
     }
   deal_ticket=first_in_ticket;
   broker_symbol=first_in_symbol;
   opened_server_seconds=first_in_msc/1000L;
   return deal_ticket>0 && opened_server_seconds>0;
  }

void NC5QueueOpeningDeal(const ulong deal_ticket)
  {
   if(deal_ticket==0 || !HistoryDealSelect(deal_ticket)) return;
   const int type=(int)HistoryDealGetInteger(deal_ticket,DEAL_TYPE);
   const int entry=(int)HistoryDealGetInteger(deal_ticket,DEAL_ENTRY);
   if((type!=DEAL_TYPE_BUY && type!=DEAL_TYPE_SELL) || (entry!=DEAL_ENTRY_IN && entry!=DEAL_ENTRY_INOUT)) return;
   const ulong position_id=(ulong)HistoryDealGetInteger(deal_ticket,DEAL_POSITION_ID);
   ulong episode_ticket=0;
   string broker_symbol="";
   long opened_server_seconds=0;
   if(!NC5PositionEpisodeOpening(position_id,episode_ticket,broker_symbol,opened_server_seconds) || episode_ticket!=deal_ticket) return;
   string canonical="";
   if(!NC5ResolveEligibleProduct(broker_symbol,canonical)) return;
   NC5QueueReminder(deal_ticket,canonical,opened_server_seconds);
  }

void NC5QueueRecentOpenPositions()
  {
   if(InpStartupCatchupMinutes<=0) return;
   const long now_server=((long)TimeTradeServer()>0 ? (long)TimeTradeServer() : (long)TimeCurrent());
   const long cutoff=now_server-(long)InpStartupCatchupMinutes*60L;
   for(int i=0;i<PositionsTotal();i++)
     {
      const ulong position_ticket=PositionGetTicket(i);
      if(position_ticket==0) continue;
      const ulong position_id=(ulong)PositionGetInteger(POSITION_IDENTIFIER);
      ulong deal_ticket=0;
      string broker_symbol="";
      long opened_server_seconds=0;
      if(!NC5PositionEpisodeOpening(position_id,deal_ticket,broker_symbol,opened_server_seconds)) continue;
      if(opened_server_seconds<cutoff) continue;
      string canonical="";
      if(!NC5ResolveEligibleProduct(broker_symbol,canonical)) continue;
      NC5QueueReminder(deal_ticket,canonical,opened_server_seconds);
     }
  }

void NC5RemoveFirstReminder()
  {
   const int n=ArraySize(g_reminder_queue);
   if(n<=0) return;
   for(int i=1;i<n;i++) g_reminder_queue[i-1]=g_reminder_queue[i];
   ArrayResize(g_reminder_queue,n-1);
  }

void NC5FlushReminders()
  {
   while(ArraySize(g_reminder_queue)>0)
     {
      if(!NC5EmitReminder(g_reminder_queue[0].deal_ticket,g_reminder_queue[0].symbol,g_reminder_queue[0].text)) return;
      NC5RemoveFirstReminder();
     }
  }

int OnInit()
  {
   const long current_login=(long)AccountInfoInteger(ACCOUNT_LOGIN);
   if(InpExpectedLogin<=0 || current_login!=InpExpectedLogin)
     {
      Print("[NEOTECH-C5] InpExpectedLogin is required and must match the attached MT5 account.");
      return INIT_PARAMETERS_INCORRECT;
     }
   if(InpTimerSeconds<1 || InpTimerSeconds>60 || InpStartupCatchupMinutes<0 || InpStartupCatchupMinutes>120)
     {
      Print("[NEOTECH-C5] Timer must be 1..60s and startup catch-up 0..120 minutes.");
      return INIT_PARAMETERS_INCORRECT;
     }
   FolderCreate(NC5_LOCAL_FORWARD_DIR,FILE_COMMON);
   NC5QueueRecentOpenPositions();
   if(!EventSetTimer(InpTimerSeconds)) return INIT_FAILED;
   PrintFormat("[NEOTECH-C5] Reminder-only EA initialized login=%I64d timer=%ds catchup=%dm",current_login,InpTimerSeconds,InpStartupCatchupMinutes);
   return INIT_SUCCEEDED;
  }

void OnDeinit(const int reason)
  {
   EventKillTimer();
  }

void OnTimer()
  {
   NC5FlushReminders();
  }

void OnTradeTransaction(const MqlTradeTransaction &trans,const MqlTradeRequest &request,const MqlTradeResult &result)
  {
   if(trans.deal>0) NC5QueueOpeningDeal(trans.deal);
  }
