#property strict
#property version   "1.10"
#property description "OAK NeoTech C5 discipline helper: standalone popup + C5 LOOK + optional Telegram. Read-only."

#include "neotech\\NeoTechC5Reminder.mqh"

input group "1. NHAC C5"
input int  InpTimerSeconds              = 2;    // Chu ky helper
input int  InpStartupCatchupMinutes     = 30;   // Phuc hoi lenh dang mo gan day sau attach/restart
input bool InpLocalPopup                = true; // Popup C5 khi khong co Telegram controller
input bool InpLookButton                = true; // Nut C5 LOOK tren chart

#define NC5_LOCAL_FORWARD_DIR "OAKLocalFailover\\"
#define NC5_LOOK_BUTTON_NAME "OAK_NC5_C5_LOOK"
#define NC5_MAX_SEEN_DEALS 256

struct NC5Reminder
  {
   ulong deal_ticket;
   string symbol;
   string text;
   string local_text;
  };

NC5Reminder g_reminder_queue[];
ulong g_seen_deals[];
long g_bound_login=0;
string g_bound_server="";

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

bool NC5ReplaceCommonAtomic(const string final_path,const string text)
  {
   const string temp_path=final_path+".tmp."+IntegerToString((long)GetTickCount64())+"."+IntegerToString((long)MathRand());
   if(!NC5WriteCommonText(temp_path,text)) return false;
   NC5DeleteCommon(final_path);
   ResetLastError();
   const bool moved=FileMove(temp_path,FILE_COMMON,final_path,FILE_COMMON);
   if(!moved) NC5DeleteCommon(temp_path);
   return moved;
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

bool NC5SymbolListed(const string &symbols[],const string symbol)
  {
   for(int i=0;i<ArraySize(symbols);i++) if(symbols[i]==symbol) return true;
   return false;
  }

void NC5AppendUniqueSymbol(string &symbols[],const string symbol)
  {
   if(symbol=="" || NC5SymbolListed(symbols,symbol)) return;
   const int n=ArraySize(symbols);
   ArrayResize(symbols,n+1);
   symbols[n]=symbol;
  }

string NC5SymbolsJson(const string &symbols[])
  {
   string out="[";
   for(int i=0;i<ArraySize(symbols);i++)
     {
      if(i>0) out+=",";
      out+=NC5JsonQuote(symbols[i]);
     }
   return out+"]";
  }

int NC5CollectCurrentSessionSymbols(const long start_server_seconds,const long end_server_seconds,string &symbols[])
  {
   ArrayResize(symbols,0);
   const long now_server=((long)TimeTradeServer()>0 ? (long)TimeTradeServer() : (long)TimeCurrent());
   const long select_end=MathMin(now_server,end_server_seconds-1);
   if(start_server_seconds<=0 || select_end<start_server_seconds || !HistorySelect((datetime)start_server_seconds,(datetime)select_end)) return 0;
   ulong candidates[];
   ArrayResize(candidates,0);
   const int total=HistoryDealsTotal();
   for(int i=0;i<total;i++)
     {
      const ulong ticket=HistoryDealGetTicket(i);
      if(ticket==0) continue;
      const int type=(int)HistoryDealGetInteger(ticket,DEAL_TYPE);
      const int entry=(int)HistoryDealGetInteger(ticket,DEAL_ENTRY);
      if((type!=DEAL_TYPE_BUY && type!=DEAL_TYPE_SELL) || (entry!=DEAL_ENTRY_IN && entry!=DEAL_ENTRY_INOUT)) continue;
      const long time_seconds=(long)HistoryDealGetInteger(ticket,DEAL_TIME_MSC)/1000L;
      if(time_seconds<start_server_seconds || time_seconds>=end_server_seconds) continue;
      const int n=ArraySize(candidates);
      ArrayResize(candidates,n+1);
      candidates[n]=ticket;
     }
   for(int i=0;i<ArraySize(candidates);i++)
     {
      const ulong ticket=candidates[i];
      if(!HistoryDealSelect(ticket)) continue;
      const ulong position_id=(ulong)HistoryDealGetInteger(ticket,DEAL_POSITION_ID);
      ulong episode_ticket=0;
      string broker_symbol="";
      long opened_server_seconds=0;
      if(!NC5PositionEpisodeOpening(position_id,episode_ticket,broker_symbol,opened_server_seconds) || episode_ticket!=ticket) continue;
      if(opened_server_seconds<start_server_seconds || opened_server_seconds>=end_server_seconds) continue;
      string canonical="";
      if(NC5ResolveEligibleProduct(broker_symbol,canonical)) NC5AppendUniqueSymbol(symbols,canonical);
     }
   return ArraySize(symbols);
  }

bool NC5PublishLookSnapshot()
  {
   string profile="",provider_account_id="";
   if(!NC5LocalForwardIdentity(profile,provider_account_id)) return false;
   const long login=(long)AccountInfoInteger(ACCOUNT_LOGIN);
   const long now_server=((long)TimeTradeServer()>0 ? (long)TimeTradeServer() : (long)TimeCurrent());
   NC5Session session=NC5_OUTSIDE_SESSION;
   long session_start=0,session_end=0;
   const bool active=NC5CurrentSessionWindow(now_server,session,session_start,session_end);
   string symbols[];
   ArrayResize(symbols,0);
   if(active) NC5CollectCurrentSessionSymbols(session_start,session_end,symbols);
   const string path=NC5_LOCAL_FORWARD_DIR+"look_"+NC5LocalProfileKey(profile)+"_"+IntegerToString(login)+".json";
   const string json="{\"version\":1"
      +",\"snapshotType\":\"neotech_c5_look\""
      +",\"profile\":"+NC5JsonQuote(profile)
      +",\"providerAccountId\":"+NC5JsonQuote(provider_account_id)
      +",\"login\":"+IntegerToString(login)
      +",\"server\":"+NC5JsonQuote(AccountInfoString(ACCOUNT_SERVER))
      +",\"at\":"+IntegerToString((long)TimeGMT()*1000L)
      +",\"session\":"+NC5JsonQuote(NC5SessionName(session))
      +",\"sessionStartServerEpoch\":"+IntegerToString(session_start)
      +",\"sessionEndServerEpoch\":"+IntegerToString(session_end)
      +",\"sessionStartVietnam\":"+NC5JsonQuote(active?NC5VietnamTimeText(session_start):"")
      +",\"sessionEndVietnam\":"+NC5JsonQuote(active?NC5VietnamTimeText(session_end):"")
      +",\"symbols\":"+NC5SymbolsJson(symbols)+"}";
   return NC5ReplaceCommonAtomic(path,json);
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
   g_reminder_queue[n].local_text=NC5LocalReminderText(canonical_symbol,opened_server_seconds);
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
      string profile="",provider_account_id="";
      if(NC5LocalForwardIdentity(profile,provider_account_id))
        {
         if(!NC5EmitReminder(g_reminder_queue[0].deal_ticket,g_reminder_queue[0].symbol,g_reminder_queue[0].text)) return;
         NC5RemoveFirstReminder();
         continue;
        }
      if(InpLocalPopup && g_reminder_queue[0].local_text!="") Alert(g_reminder_queue[0].local_text);
      Print("[NEOTECH-C5] standalone reminder: "+g_reminder_queue[0].local_text);
      NC5RemoveFirstReminder();
     }
  }

string NC5BuildLocalLookText()
  {
   const long now_server=((long)TimeTradeServer()>0 ? (long)TimeTradeServer() : (long)TimeCurrent());
   NC5Session session=NC5_OUTSIDE_SESSION;
   long session_start=0,session_end=0;
   string symbols[];
   ArrayResize(symbols,0);
   if(NC5CurrentSessionWindow(now_server,session,session_start,session_end))
      NC5CollectCurrentSessionSymbols(session_start,session_end,symbols);
   return NC5LocalLookText(session,symbols,session_end);
  }

void NC5LayoutLookButton()
  {
   if(!InpLookButton || ObjectFind(0,NC5_LOOK_BUTTON_NAME)<0) return;
   // Keep the control away from MT5's EA/status chrome on the upper-right.
   // Fixed upper-left offsets are stable on desktop, phone remote sessions and chart resizes.
   ObjectSetInteger(0,NC5_LOOK_BUTTON_NAME,OBJPROP_CORNER,CORNER_LEFT_UPPER);
   ObjectSetInteger(0,NC5_LOOK_BUTTON_NAME,OBJPROP_XDISTANCE,12);
   ObjectSetInteger(0,NC5_LOOK_BUTTON_NAME,OBJPROP_YDISTANCE,18);
   ObjectSetInteger(0,NC5_LOOK_BUTTON_NAME,OBJPROP_XSIZE,92);
   ObjectSetInteger(0,NC5_LOOK_BUTTON_NAME,OBJPROP_YSIZE,28);
   ObjectSetInteger(0,NC5_LOOK_BUTTON_NAME,OBJPROP_ZORDER,1000);
  }

bool NC5EnsureLookButton()
  {
   if(!InpLookButton) return true;
   if(ObjectFind(0,NC5_LOOK_BUTTON_NAME)<0 && !ObjectCreate(0,NC5_LOOK_BUTTON_NAME,OBJ_BUTTON,0,0,0)) return false;
   NC5LayoutLookButton();
   ObjectSetInteger(0,NC5_LOOK_BUTTON_NAME,OBJPROP_BGCOLOR,C'22,38,35');
   ObjectSetInteger(0,NC5_LOOK_BUTTON_NAME,OBJPROP_BORDER_COLOR,C'57,170,132');
   ObjectSetInteger(0,NC5_LOOK_BUTTON_NAME,OBJPROP_COLOR,clrWhite);
   ObjectSetInteger(0,NC5_LOOK_BUTTON_NAME,OBJPROP_FONTSIZE,9);
   ObjectSetInteger(0,NC5_LOOK_BUTTON_NAME,OBJPROP_HIDDEN,false);
   ObjectSetInteger(0,NC5_LOOK_BUTTON_NAME,OBJPROP_SELECTABLE,false);
   ObjectSetInteger(0,NC5_LOOK_BUTTON_NAME,OBJPROP_BACK,false);
   ObjectSetString(0,NC5_LOOK_BUTTON_NAME,OBJPROP_TEXT,"C5 LOOK");
   ChartRedraw(0);
   return true;
  }

bool NC5RefreshAccountIdentity(const bool force=false)
  {
   const long current_login=(long)AccountInfoInteger(ACCOUNT_LOGIN);
   const string current_server=NC5NormalizeServerIdentity(AccountInfoString(ACCOUNT_SERVER));
   if(current_login<=0 || current_server=="") return false;
   if(!force && current_login==g_bound_login && current_server==g_bound_server) return false;
   const long previous_login=g_bound_login;
   g_bound_login=current_login;
   g_bound_server=current_server;
   ArrayResize(g_reminder_queue,0);
   ArrayResize(g_seen_deals,0);
   NC5QueueRecentOpenPositions();
   PrintFormat("[NEOTECH-C5] auto-bound account previous=%I64d current=%I64d server=%s",previous_login,current_login,AccountInfoString(ACCOUNT_SERVER));
   return true;
  }

int OnInit()
  {
   if(InpTimerSeconds<1 || InpTimerSeconds>60 || InpStartupCatchupMinutes<0 || InpStartupCatchupMinutes>120)
     {
      Print("[NEOTECH-C5] Timer must be 1..60s and startup catch-up 0..120 minutes.");
      return INIT_PARAMETERS_INCORRECT;
     }
   FolderCreate(NC5_LOCAL_FORWARD_DIR,FILE_COMMON);
   NC5RefreshAccountIdentity(true);
   NC5PublishLookSnapshot();
   NC5EnsureLookButton();
   if(!EventSetTimer(InpTimerSeconds)) return INIT_FAILED;
   PrintFormat("[NEOTECH-C5] v1.10 initialized auto-bind=true standalone=true login=%I64d timer=%ds catchup=%dm",(long)AccountInfoInteger(ACCOUNT_LOGIN),InpTimerSeconds,InpStartupCatchupMinutes);
   return INIT_SUCCEEDED;
  }

void OnDeinit(const int reason)
  {
   EventKillTimer();
   ObjectDelete(0,NC5_LOOK_BUTTON_NAME);
  }

void OnChartEvent(const int id,const long &lparam,const double &dparam,const string &sparam)
  {
   if(id==CHARTEVENT_CHART_CHANGE)
     {
      NC5EnsureLookButton();
      return;
     }
   if(id!=CHARTEVENT_OBJECT_CLICK || sparam!=NC5_LOOK_BUTTON_NAME) return;
   ObjectSetInteger(0,NC5_LOOK_BUTTON_NAME,OBJPROP_STATE,false);
   const string text=NC5BuildLocalLookText();
   Alert(text);
   Print("[NEOTECH-C5] "+text);
   ChartRedraw(0);
  }

void OnTimer()
  {
   NC5RefreshAccountIdentity();
   NC5PublishLookSnapshot();
   NC5EnsureLookButton();
   NC5FlushReminders();
  }

void OnTradeTransaction(const MqlTradeTransaction &trans,const MqlTradeRequest &request,const MqlTradeResult &result)
  {
   if(trans.deal>0) NC5QueueOpeningDeal(trans.deal);
  }
