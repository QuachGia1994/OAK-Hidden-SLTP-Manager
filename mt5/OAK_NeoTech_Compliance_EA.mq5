#property strict
#property version   "1.01"
#property description "OAK read-only NeoTech compliance auditor with direct Telegram reporting. Never sends, modifies or closes trades."

#include "neotech\\NeoTechComplianceCore.mqh"
#include "neotech\\NeoTechComplianceJson.mqh"

input group "1. BAT BUOC - TAI KHOAN"
input string InpProfileSlug                 = ""; // 1. Profile slug tu dat (VD: neotech_main)
input long   InpExpectedLogin               = 0;  // 2. So tai khoan MT5 (Login)

input group "2. BAT BUOC - TELEGRAM"
input string InpTelegramBotToken            = ""; // 3. Bot token tu @BotFather
input string InpTelegramAllowedChatIds      = ""; // 4. Chat ID duoc phep (group: -100...)
input string InpTelegramAllowedUserIds      = ""; // 5. User ID Telegram duoc phep

input group "3. TUY CHON TELEGRAM"
input int    InpTelegramPollSeconds         = 15;    // Chu ky doc lenh (giay)
input bool   InpTelegramDeleteWebhookOnInit = false; // Xoa webhook cu khi khoi dong (chi bat 1 lan)
input bool   InpTelegramSendOnChange        = false; // Tu gui khi bao cao thay doi
input int    InpTelegramPageSize            = 6;     // So muc moi trang

input group "4. KIEM TRA - GIU MAC DINH NEU KHONG RO"
input double InpGoldPipSizeOverride         = 0.0; // Gold pip size (0 = tu dong)
input string InpManualPausePeriods          = "";  // Khoang tam dung: YYYY-MM-DD/YYYY-MM-DD;...
input int    InpHistoryLookbackDays         = 370; // So ngay lich su can kiem tra
input int    InpReconstructionChunkMinutes  = 60;  // Khoang tai du lieu (phut)
input int    InpReconstructionSliceSeconds  = 30;  // Moi lan xu ly toi da (giay)
input int    InpReconstructionBudgetMs      = 250; // Ngan sach moi lan xu ly (ms)

#define NT_LOCAL_DIR "OAKNeoTechCompliance\\"
#define NT_TELEGRAM_API_BASE "https://api.telegram.org"
#define NT_TELEGRAM_HTTP_TIMEOUT_MS 5000
#define NT_TELEGRAM_MESSAGE_BUDGET 3800
#define NT_RECON_MAX_TICKS_PER_SYMBOL_SLICE 50000
#define NT_RECON_MAX_EVENTS_PER_SLICE       120000
#define NT_SLTP_JOURNAL_MAX_ROWS            256

struct NTHistoryCoverage
  {
   long requested_start;
   long requested_end;
   long earliest_deal;
   long earliest_order;
   long usable_start;
   double deal_coverage_pct;
   double order_coverage_pct;
   double coverage_pct;
   bool deal_coverage_complete;
   bool order_coverage_complete;
   bool joint_history_complete;
   string missing_ranges[];
  };

struct NTFddResult
  {
   double max_floating_loss_pct;
   double max_peak_to_trough_pct;
   long event_server_time;
   double balance_at_event;
   double equity_at_event;
   string method;
   NTStatus status;
   double tick_coverage_pct;
   double bar_coverage_pct;
   string contributing_position_ids[];
   string contributing_symbols[];
   string missing_intervals[];
  };

struct NTExposureState
  {
   ulong position_id;
   string broker_symbol;
   string canonical_symbol;
   int direction;
   double volume;
   double weighted_price;
  };

struct NTQuoteState
  {
   string broker_symbol;
   double bid;
   double ask;
   long time_msc;
   bool valid;
  };

struct NTFddTimelineEvent
  {
   long time_msc;
   int kind; // 0 deal, 1 cash flow, 2 quote
   int source_index;
   string broker_symbol;
   double bid;
   double ask;
  };

struct NTFddJobState
  {
   bool initialized;
   long program_start;
   long cursor_seconds;
   double balance;
   double peak_equity;
   double max_floating_loss_pct;
   double max_peak_to_trough_pct;
   long event_server_time;
   double balance_at_event;
   double equity_at_event;
   long processed_tick_slices;
   long processed_m1_slices;
   long gap_slices;
   string method;
   string worst_position_ids[];
   string worst_symbols[];
   string gap_intervals[];
   NTExposureState exposures[];
   NTQuoteState quotes[];
  };

struct NTSltpJournalRow
  {
   ulong position_id;
   string broker_symbol;
   string canonical_symbol;
   long first_entry_msc;
   long final_close_msc;
   ulong opening_order_ticket;
   ulong opening_deal_ticket;
   ulong closing_deal_ticket;
   double max_distance_pips;
   double pip_size;
   string pip_size_source;
   long max_snapshot_msc;
   double snapshot_reference_price;
   double snapshot_sl;
   double snapshot_tp;
   bool timeline_complete;
   bool active;
  };

struct NTProspectiveExtrema
  {
   long attached_server_time;
   long event_server_time;
   double peak_equity;
   double max_floating_loss_pct;
   double max_peak_to_trough_pct;
   double balance_at_event;
   double equity_at_event;
  };

struct NTJsonEvent
  {
   long time;
   string json;
  };

bool g_history_dirty=true;
long g_last_deals=-1;
long g_last_orders=-1;
long g_last_reconcile_day=0;
string g_last_report_hash="";
string g_cached_report_json="";
long g_telegram_next_update_id=0;
bool g_telegram_polling_enabled=false;
bool g_telegram_webhook_blocked=false;
int g_telegram_failure_count=0;
long g_telegram_next_attempt=0;
string g_telegram_last_notified_hash="";
NTProspectiveExtrema g_exact;
NTFddJobState g_fdd_job;
NTSltpJournalRow g_sltp_journal[];
bool g_sltp_dirty=false;
NTDealRecord g_cached_deals[];
NTCashFlow g_cached_cashflows[];
long g_cached_program_start=0;
double g_cached_opening_balance=0.0;

string NTTrim(string value)
  {
   StringTrimLeft(value);
   StringTrimRight(value);
   return value;
  }

string NTLower(string value)
  {
   StringToLower(value);
   return value;
  }

bool NTValidProfileSlug(const string value)
  {
   const int n=StringLen(value);
   if(n<6 || n>32) return false;
   for(int i=0;i<n;i++)
     {
      const ushort c=StringGetCharacter(value,i);
      const bool ok=(c>='a' && c<='z') || (c>='0' && c<='9') || c=='_' || c=='-';
      if(!ok || (i==0 && (c=='_' || c=='-'))) return false;
     }
   return true;
  }

string NTProfileKey()
  {
   return NTLower(NTTrim(InpProfileSlug));
  }

string NTAccountFingerprint()
  {
   return NTSha256Hex(IntegerToString((long)AccountInfoInteger(ACCOUNT_LOGIN))+"|"+AccountInfoString(ACCOUNT_COMPANY)+"|"+AccountInfoString(ACCOUNT_SERVER));
  }

string NTStateKey()
  {
   return NTProfileKey()+"_"+NTAccountFingerprint();
  }

string NTReportPath()
  {
   return NT_LOCAL_DIR+"report_"+NTStateKey()+".json";
  }

string NTTelegramOffsetPath()
  {
   return NT_LOCAL_DIR+"telegram_offset_"+NTStateKey()+".txt";
  }

string NTTelegramNotifyPath()
  {
   return NT_LOCAL_DIR+"telegram_notify_"+NTStateKey()+".txt";
  }

string NTExtremaPath()
  {
   return NT_LOCAL_DIR+"extrema_"+NTStateKey()+".csv";
  }

string NTFddStatePath()
  {
   return NT_LOCAL_DIR+"fdd_"+NTStateKey()+".csv";
  }

string NTSltpJournalPath()
  {
   return NT_LOCAL_DIR+"sltp_"+NTStateKey()+".csv";
  }

bool NTWriteCommonText(const string path,const string text)
  {
   int handle=FileOpen(path,FILE_WRITE|FILE_TXT|FILE_ANSI|FILE_COMMON,0,CP_UTF8);
   if(handle==INVALID_HANDLE)
     {
      PrintFormat("[NEOTECH] FileOpen write failed path=%s err=%d",path,GetLastError());
      return false;
     }
   FileWriteString(handle,text);
   FileFlush(handle);
   FileClose(handle);
   return true;
  }

bool NTReadCommonText(const string path,string &text)
  {
   text="";
   int handle=FileOpen(path,FILE_READ|FILE_TXT|FILE_ANSI|FILE_COMMON,0,CP_UTF8);
   if(handle==INVALID_HANDLE) return false;
   while(!FileIsEnding(handle)) text+=FileReadString(handle);
   FileClose(handle);
   return true;
  }

void NTDeleteCommon(const string path)
  {
   if(FileIsExist(path,FILE_COMMON)) FileDelete(path,FILE_COMMON);
  }

void NTSaveProspectiveExtrema()
  {
   int handle=FileOpen(NTExtremaPath(),FILE_WRITE|FILE_CSV|FILE_ANSI|FILE_COMMON,';');
   if(handle==INVALID_HANDLE) return;
   FileWrite(handle,g_exact.attached_server_time,g_exact.event_server_time,g_exact.peak_equity,g_exact.max_floating_loss_pct,g_exact.max_peak_to_trough_pct,g_exact.balance_at_event,g_exact.equity_at_event);
   FileFlush(handle);
   FileClose(handle);
  }

void NTLoadProspectiveExtrema()
  {
   g_exact.attached_server_time=(long)TimeTradeServer();
   if(g_exact.attached_server_time<=0) g_exact.attached_server_time=(long)TimeCurrent();
   g_exact.event_server_time=g_exact.attached_server_time;
   g_exact.peak_equity=AccountInfoDouble(ACCOUNT_EQUITY);
   g_exact.max_floating_loss_pct=0.0;
   g_exact.max_peak_to_trough_pct=0.0;
   g_exact.balance_at_event=AccountInfoDouble(ACCOUNT_BALANCE);
   g_exact.equity_at_event=AccountInfoDouble(ACCOUNT_EQUITY);
   int handle=FileOpen(NTExtremaPath(),FILE_READ|FILE_CSV|FILE_ANSI|FILE_COMMON,';');
   if(handle==INVALID_HANDLE) return;
   if(!FileIsEnding(handle))
     {
      g_exact.attached_server_time=(long)FileReadNumber(handle);
      g_exact.event_server_time=(long)FileReadNumber(handle);
      g_exact.peak_equity=FileReadNumber(handle);
      g_exact.max_floating_loss_pct=FileReadNumber(handle);
      g_exact.max_peak_to_trough_pct=FileReadNumber(handle);
      g_exact.balance_at_event=FileReadNumber(handle);
      g_exact.equity_at_event=FileReadNumber(handle);
     }
   FileClose(handle);
  }

void NTSampleProspectiveEquity()
  {
   const double balance=AccountInfoDouble(ACCOUNT_BALANCE);
   const double equity=AccountInfoDouble(ACCOUNT_EQUITY);
   if(balance<=0.0 || equity<=0.0) return;
   bool changed=false;
   if(equity>g_exact.peak_equity)
     {
      g_exact.peak_equity=equity;
      changed=true;
     }
   const double floating_loss_pct=NTFloatingLossPct(balance,equity);
   const double peak_dd_pct=NTPeakToTroughPct(g_exact.peak_equity,equity);
   if(floating_loss_pct>g_exact.max_floating_loss_pct || peak_dd_pct>g_exact.max_peak_to_trough_pct)
     {
      g_exact.max_floating_loss_pct=MathMax(g_exact.max_floating_loss_pct,floating_loss_pct);
      g_exact.max_peak_to_trough_pct=MathMax(g_exact.max_peak_to_trough_pct,peak_dd_pct);
      g_exact.event_server_time=(long)TimeTradeServer();
      if(g_exact.event_server_time<=0) g_exact.event_server_time=(long)TimeCurrent();
      g_exact.balance_at_event=balance;
      g_exact.equity_at_event=equity;
      changed=true;
     }
   if(changed) NTSaveProspectiveExtrema();
  }

int NTFindActiveSltpJournal(const ulong position_id)
  {
   for(int i=ArraySize(g_sltp_journal)-1;i>=0;i--) if(g_sltp_journal[i].position_id==position_id && g_sltp_journal[i].active) return i;
   return -1;
  }

void NTPruneSltpJournal()
  {
   const long cutoff=((long)TimeTradeServer()>0 ? (long)TimeTradeServer() : (long)TimeCurrent())-(long)MathMax(365,InpHistoryLookbackDays)*NT_DAY_SECONDS;
   NTSltpJournalRow kept[];
   ArrayResize(kept,0);
   for(int i=0;i<ArraySize(g_sltp_journal);i++)
     {
      if(!g_sltp_journal[i].active && g_sltp_journal[i].final_close_msc>0 && g_sltp_journal[i].final_close_msc/1000<cutoff) continue;
      const int n=ArraySize(kept);
      ArrayResize(kept,n+1);
      kept[n]=g_sltp_journal[i];
     }
   const int start=MathMax(0,ArraySize(kept)-NT_SLTP_JOURNAL_MAX_ROWS);
   ArrayResize(g_sltp_journal,ArraySize(kept)-start);
   for(int i=0;i<ArraySize(g_sltp_journal);i++) g_sltp_journal[i]=kept[start+i];
  }

void NTSaveSltpJournal()
  {
   NTPruneSltpJournal();
   int handle=FileOpen(NTSltpJournalPath(),FILE_WRITE|FILE_CSV|FILE_ANSI|FILE_COMMON,';');
   if(handle==INVALID_HANDLE) return;
   FileWrite(handle,"v1",NTAccountFingerprint());
   for(int i=0;i<ArraySize(g_sltp_journal);i++)
     {
      const NTSltpJournalRow row=g_sltp_journal[i];
      FileWrite(handle,row.position_id,row.broker_symbol,row.canonical_symbol,row.first_entry_msc,row.final_close_msc,row.opening_order_ticket,row.opening_deal_ticket,row.closing_deal_ticket,row.max_distance_pips,row.pip_size,row.pip_size_source,row.max_snapshot_msc,row.snapshot_reference_price,row.snapshot_sl,row.snapshot_tp,row.timeline_complete?1:0,row.active?1:0);
     }
   FileFlush(handle);
   FileClose(handle);
  }

void NTLoadSltpJournal()
  {
   ArrayResize(g_sltp_journal,0);
   int handle=FileOpen(NTSltpJournalPath(),FILE_READ|FILE_CSV|FILE_ANSI|FILE_COMMON,';');
   if(handle==INVALID_HANDLE) return;
   const string version=FileReadString(handle);
   const string fingerprint=FileReadString(handle);
   if(version!="v1" || fingerprint!=NTAccountFingerprint())
     {
      FileClose(handle);
      return;
     }
   while(!FileIsEnding(handle))
     {
      NTSltpJournalRow row;
      row.position_id=(ulong)FileReadNumber(handle);
      if(row.position_id==0) break;
      row.broker_symbol=FileReadString(handle);
      row.canonical_symbol=FileReadString(handle);
      row.first_entry_msc=(long)FileReadNumber(handle);
      row.final_close_msc=(long)FileReadNumber(handle);
      row.opening_order_ticket=(ulong)FileReadNumber(handle);
      row.opening_deal_ticket=(ulong)FileReadNumber(handle);
      row.closing_deal_ticket=(ulong)FileReadNumber(handle);
      row.max_distance_pips=FileReadNumber(handle);
      row.pip_size=FileReadNumber(handle);
      row.pip_size_source=FileReadString(handle);
      row.max_snapshot_msc=(long)FileReadNumber(handle);
      row.snapshot_reference_price=FileReadNumber(handle);
      row.snapshot_sl=FileReadNumber(handle);
      row.snapshot_tp=FileReadNumber(handle);
      row.timeline_complete=(FileReadNumber(handle)!=0);
      row.active=(FileReadNumber(handle)!=0);
      if(row.active) row.timeline_complete=false;
      const int n=ArraySize(g_sltp_journal);
      ArrayResize(g_sltp_journal,n+1);
      g_sltp_journal[n]=row;
     }
   FileClose(handle);
  }

bool NTPositionIdentifierOpen(const ulong position_id)
  {
   for(int i=0;i<PositionsTotal();i++)
     {
      const ulong ticket=PositionGetTicket(i);
      if(ticket>0 && (ulong)PositionGetInteger(POSITION_IDENTIFIER)==position_id) return true;
     }
   return false;
  }

void NTObserveJournalSnapshot(const int index,const long time_msc,const double reference_price,const double sl,const double tp)
  {
   if(index<0 || index>=ArraySize(g_sltp_journal) || g_sltp_journal[index].pip_size<=0.0 || reference_price<=0.0) return;
   double max_distance=0.0;
   if(sl>0.0) max_distance=MathMax(max_distance,NTPipDistance(reference_price,sl,g_sltp_journal[index].pip_size));
   if(tp>0.0) max_distance=MathMax(max_distance,NTPipDistance(reference_price,tp,g_sltp_journal[index].pip_size));
   if(max_distance>=g_sltp_journal[index].max_distance_pips)
     {
      g_sltp_journal[index].max_distance_pips=max_distance;
      g_sltp_journal[index].max_snapshot_msc=time_msc;
      g_sltp_journal[index].snapshot_reference_price=reference_price;
      g_sltp_journal[index].snapshot_sl=sl;
      g_sltp_journal[index].snapshot_tp=tp;
     }
  }

void NTObserveCurrentPositionSltp(const ulong position_ticket,const long time_msc)
  {
   if(position_ticket==0 || !PositionSelectByTicket(position_ticket)) return;
   const ulong position_id=(ulong)PositionGetInteger(POSITION_IDENTIFIER);
   const int index=NTFindActiveSltpJournal(position_id);
   if(index<0) return;
   NTObserveJournalSnapshot(index,time_msc,PositionGetDouble(POSITION_PRICE_OPEN),PositionGetDouble(POSITION_SL),PositionGetDouble(POSITION_TP));
  }

void NTRecordProspectiveTradeEvidence(const MqlTradeTransaction &trans)
  {
   bool changed=false;
   const long observed_msc=((long)TimeTradeServer()>0 ? (long)TimeTradeServer() : (long)TimeCurrent())*1000L;
   if(trans.deal>0 && HistoryDealSelect(trans.deal))
     {
      const int deal_type=(int)HistoryDealGetInteger(trans.deal,DEAL_TYPE);
      if(deal_type==DEAL_TYPE_BUY || deal_type==DEAL_TYPE_SELL)
        {
         const ulong position_id=(ulong)HistoryDealGetInteger(trans.deal,DEAL_POSITION_ID);
         const int entry=(int)HistoryDealGetInteger(trans.deal,DEAL_ENTRY);
         const long time_msc=(long)HistoryDealGetInteger(trans.deal,DEAL_TIME_MSC);
         const ulong order_ticket=(ulong)HistoryDealGetInteger(trans.deal,DEAL_ORDER);
         const string broker_symbol=HistoryDealGetString(trans.deal,DEAL_SYMBOL);
         string canonical="";
         bool is_forex=false,is_gold=false;
         double pip_size=0.0;
         bool classification_reliable=false;
         NTResolveProduct(broker_symbol,canonical,is_forex,is_gold,pip_size,classification_reliable);
         int active=NTFindActiveSltpJournal(position_id);
         if(entry==DEAL_ENTRY_IN || entry==DEAL_ENTRY_INOUT)
           {
            if(entry==DEAL_ENTRY_INOUT && active>=0)
              {
               g_sltp_journal[active].active=false;
               g_sltp_journal[active].final_close_msc=time_msc;
               g_sltp_journal[active].closing_deal_ticket=trans.deal;
               active=-1;
              }
            if(active<0)
              {
               const int n=ArraySize(g_sltp_journal);
               ArrayResize(g_sltp_journal,n+1);
               g_sltp_journal[n].position_id=position_id;
               g_sltp_journal[n].broker_symbol=broker_symbol;
               g_sltp_journal[n].canonical_symbol=canonical;
               g_sltp_journal[n].first_entry_msc=time_msc;
               g_sltp_journal[n].final_close_msc=0;
               g_sltp_journal[n].opening_order_ticket=order_ticket;
               g_sltp_journal[n].opening_deal_ticket=trans.deal;
               g_sltp_journal[n].closing_deal_ticket=0;
               g_sltp_journal[n].max_distance_pips=0.0;
               g_sltp_journal[n].pip_size=pip_size;
               g_sltp_journal[n].pip_size_source=(is_gold?"GOLD_OVERRIDE":"SYMBOL_METADATA");
               g_sltp_journal[n].max_snapshot_msc=time_msc;
               g_sltp_journal[n].snapshot_reference_price=HistoryDealGetDouble(trans.deal,DEAL_PRICE);
               g_sltp_journal[n].snapshot_sl=HistoryDealGetDouble(trans.deal,DEAL_SL);
               g_sltp_journal[n].snapshot_tp=HistoryDealGetDouble(trans.deal,DEAL_TP);
               g_sltp_journal[n].timeline_complete=(classification_reliable && pip_size>0.0);
               g_sltp_journal[n].active=true;
               active=n;
              }
            NTObserveJournalSnapshot(active,time_msc,HistoryDealGetDouble(trans.deal,DEAL_PRICE),HistoryDealGetDouble(trans.deal,DEAL_SL),HistoryDealGetDouble(trans.deal,DEAL_TP));
            changed=true;
           }
         if((entry==DEAL_ENTRY_OUT || entry==DEAL_ENTRY_OUT_BY) && active>=0)
           {
            NTObserveJournalSnapshot(active,time_msc,HistoryDealGetDouble(trans.deal,DEAL_PRICE),HistoryDealGetDouble(trans.deal,DEAL_SL),HistoryDealGetDouble(trans.deal,DEAL_TP));
            if(!NTPositionIdentifierOpen(position_id))
              {
               g_sltp_journal[active].active=false;
               g_sltp_journal[active].final_close_msc=time_msc;
               g_sltp_journal[active].closing_deal_ticket=trans.deal;
              }
            changed=true;
           }
        }
     }
   if(trans.position>0)
     {
      NTObserveCurrentPositionSltp(trans.position,observed_msc);
      changed=true;
     }
   if(changed) g_sltp_dirty=true;
  }

void NTMergeProspectiveSltp(NTSignalEpisode &episodes[])
  {
   for(int i=0;i<ArraySize(episodes);i++)
      for(int j=0;j<ArraySize(g_sltp_journal);j++)
        {
         if(episodes[i].position_id!=g_sltp_journal[j].position_id || episodes[i].first_entry_msc!=g_sltp_journal[j].first_entry_msc) continue;
         episodes[i].sltp_evidence_complete=g_sltp_journal[j].timeline_complete;
         episodes[i].max_sltp_distance_pips=MathMax(episodes[i].max_sltp_distance_pips,g_sltp_journal[j].max_distance_pips);
         episodes[i].pip_size=g_sltp_journal[j].pip_size;
         episodes[i].pip_size_source=g_sltp_journal[j].pip_size_source;
         break;
        }
  }

bool NTC6EvidenceCoverageComplete(const NTSignalEpisode &episodes[])
  {
   for(int i=0;i<ArraySize(episodes);i++) if(!episodes[i].open && episodes[i].holding_seconds<15*60 && !episodes[i].sltp_evidence_complete) return false;
   return true;
  }

bool NTResolveProduct(const string broker_symbol,string &canonical,bool &is_forex,bool &is_gold,double &pip_size,bool &classification_reliable)
  {
   canonical="";
   is_forex=false;
   is_gold=false;
   pip_size=0.0;
   classification_reliable=false;
   const string base=SymbolInfoString(broker_symbol,SYMBOL_CURRENCY_BASE);
   const string profit=SymbolInfoString(broker_symbol,SYMBOL_CURRENCY_PROFIT);
   long calc=0;
   classification_reliable=SymbolInfoInteger(broker_symbol,SYMBOL_TRADE_CALC_MODE,calc);
   const double point=SymbolInfoDouble(broker_symbol,SYMBOL_POINT);
   const int digits=(int)SymbolInfoInteger(broker_symbol,SYMBOL_DIGITS);
   is_forex=(calc==SYMBOL_CALC_MODE_FOREX || calc==SYMBOL_CALC_MODE_FOREX_NO_LEVERAGE) && StringLen(base)==3 && StringLen(profit)==3;
   is_gold=(base=="XAU");
   if(is_forex || is_gold) canonical=base+profit;
   else canonical=(classification_reliable?"EXCLUDED:":"UNKNOWN:")+broker_symbol;
   pip_size=NTPipSize(point,digits,is_forex,is_gold ? InpGoldPipSizeOverride : 0.0);
   return is_forex || is_gold;
  }

int NTClassifyCashFlow(const int deal_type,const double amount,const string comment)
  {
   const string lower=NTLower(comment);
   if(deal_type==DEAL_TYPE_CREDIT || deal_type==DEAL_TYPE_BONUS) return 3;
   if(deal_type==DEAL_TYPE_CORRECTION) return 4;
   if(deal_type==DEAL_TYPE_CHARGE || deal_type==DEAL_TYPE_COMMISSION || deal_type==DEAL_TYPE_COMMISSION_DAILY || deal_type==DEAL_TYPE_COMMISSION_MONTHLY) return 2;
   if(deal_type==DEAL_TYPE_BALANCE)
     {
      const bool deposit=(StringFind(lower,"deposit")>=0 || StringFind(lower,"fund")>=0 || StringFind(lower,"nạp")>=0);
      const bool withdraw=(StringFind(lower,"withdraw")>=0 || StringFind(lower,"payout")>=0 || StringFind(lower,"rút")>=0);
      if(deposit && amount>0.0) return 1;
      if(withdraw && amount<0.0) return -1;
      return 0; // a generic balance adjustment is not automatically called a deposit/withdrawal
     }
   return 0;
  }

bool NTLoadHistory(NTDealRecord &deals[],NTCashFlow &cashflows[],NTHistoryCoverage &coverage)
  {
   ArrayResize(deals,0);
   ArrayResize(cashflows,0);
   ArrayResize(coverage.missing_ranges,0);
   const long now=(long)TimeTradeServer();
   coverage.requested_end=(now>0 ? now : (long)TimeCurrent());
   coverage.requested_start=MathMax(0,coverage.requested_end-(long)MathMax(365,InpHistoryLookbackDays)*NT_DAY_SECONDS);
   coverage.earliest_deal=0;
   coverage.earliest_order=0;
   coverage.usable_start=0;
   coverage.deal_coverage_pct=0.0;
   coverage.order_coverage_pct=0.0;
   coverage.coverage_pct=0.0;
   coverage.deal_coverage_complete=false;
   coverage.order_coverage_complete=false;
   coverage.joint_history_complete=false;
   if(!HistorySelect(0,(datetime)coverage.requested_end))
     {
      NTAppendString(coverage.missing_ranges,"HistorySelect(0,now) failed");
      return false;
     }

   const int order_total=HistoryOrdersTotal();
   for(int i=0;i<order_total;i++)
     {
      const ulong ticket=HistoryOrderGetTicket(i);
      if(ticket==0) continue;
      const long t=(long)HistoryOrderGetInteger(ticket,ORDER_TIME_SETUP_MSC)/1000;
      if(t>0 && (coverage.earliest_order==0 || t<coverage.earliest_order)) coverage.earliest_order=t;
     }

   const int total=HistoryDealsTotal();
   for(int i=0;i<total;i++)
     {
      const ulong ticket=HistoryDealGetTicket(i);
      if(ticket==0) continue;
      const long time_msc=(long)HistoryDealGetInteger(ticket,DEAL_TIME_MSC);
      const long time_sec=time_msc/1000;
      if(time_sec>0 && (coverage.earliest_deal==0 || time_sec<coverage.earliest_deal)) coverage.earliest_deal=time_sec;
      const int type=(int)HistoryDealGetInteger(ticket,DEAL_TYPE);
      const double profit=HistoryDealGetDouble(ticket,DEAL_PROFIT);
      const string comment=HistoryDealGetString(ticket,DEAL_COMMENT);
      if(type!=DEAL_TYPE_BUY && type!=DEAL_TYPE_SELL)
        {
         NTCashFlow flow;
         flow.time_msc=time_msc;
         flow.amount=profit;
         flow.kind=NTClassifyCashFlow(type,profit,comment);
         flow.ticket=ticket;
         flow.comment=comment;
         const int c=ArraySize(cashflows);
         ArrayResize(cashflows,c+1);
         cashflows[c]=flow;
         continue;
        }

      NTDealRecord row;
      row.ticket=ticket;
      row.order_ticket=(ulong)HistoryDealGetInteger(ticket,DEAL_ORDER);
      row.position_id=(ulong)HistoryDealGetInteger(ticket,DEAL_POSITION_ID);
      row.broker_symbol=HistoryDealGetString(ticket,DEAL_SYMBOL);
      bool is_forex=false,is_gold=false;
      row.product_eligible=NTResolveProduct(row.broker_symbol,row.canonical_symbol,is_forex,is_gold,row.pip_size,row.product_classification_reliable);
      row.time_msc=time_msc;
      row.entry=(int)HistoryDealGetInteger(ticket,DEAL_ENTRY);
      row.deal_type=type;
      row.deal_reason=(int)HistoryDealGetInteger(ticket,DEAL_REASON);
      row.order_reason=-1;
      if(row.order_ticket>0 && (long)HistoryOrderGetInteger(row.order_ticket,ORDER_TIME_SETUP_MSC)>0) row.order_reason=(int)HistoryOrderGetInteger(row.order_ticket,ORDER_REASON);
      row.magic=(long)HistoryDealGetInteger(ticket,DEAL_MAGIC);
      row.comment=comment;
      row.volume=HistoryDealGetDouble(ticket,DEAL_VOLUME);
      row.price=HistoryDealGetDouble(ticket,DEAL_PRICE);
      row.profit=profit;
      row.commission=HistoryDealGetDouble(ticket,DEAL_COMMISSION);
      row.swap=HistoryDealGetDouble(ticket,DEAL_SWAP);
      row.fee=HistoryDealGetDouble(ticket,DEAL_FEE);
      row.sl=HistoryDealGetDouble(ticket,DEAL_SL);
      row.tp=HistoryDealGetDouble(ticket,DEAL_TP);
      if(row.order_ticket>0 && (row.sl<=0.0 || row.tp<=0.0))
        {
         if(row.sl<=0.0) row.sl=HistoryOrderGetDouble(row.order_ticket,ORDER_SL);
         if(row.tp<=0.0) row.tp=HistoryOrderGetDouble(row.order_ticket,ORDER_TP);
        }
      row.opening_reason_reliable=(row.deal_reason==DEAL_REASON_CLIENT || row.deal_reason==DEAL_REASON_MOBILE || row.deal_reason==DEAL_REASON_WEB || row.deal_reason==DEAL_REASON_EXPERT || row.order_reason>=0);
      row.sltp_snapshot_reliable=(row.pip_size>0.0);
      row.sltp_timeline_complete=false; // MT5 history does not prove every intermediate SL/TP modification
      const int n=ArraySize(deals);
      ArrayResize(deals,n+1);
      deals[n]=row;
     }

   coverage.deal_coverage_pct=NTHistoryCoveragePct(coverage.earliest_deal,coverage.requested_end);
   coverage.order_coverage_pct=NTHistoryCoveragePct(coverage.earliest_order,coverage.requested_end);
   coverage.deal_coverage_complete=(coverage.earliest_deal>0 && coverage.earliest_deal<=coverage.requested_start);
   coverage.order_coverage_complete=(coverage.earliest_order>0 && coverage.earliest_order<=coverage.requested_start);
   coverage.usable_start=(coverage.earliest_deal>0 && coverage.earliest_order>0 ? MathMax(coverage.earliest_deal,coverage.earliest_order) : 0);
   coverage.coverage_pct=NTHistoryCoveragePct(coverage.usable_start,coverage.requested_end);
   coverage.joint_history_complete=coverage.deal_coverage_complete && coverage.order_coverage_complete;
   if(coverage.earliest_deal==0) NTAppendString(coverage.missing_ranges,"No broker deal history returned");
   else if(!coverage.deal_coverage_complete) NTAppendString(coverage.missing_ranges,StringFormat("Deal history begins %s; requested compliance horizon begins %s",NTDateTimeText(coverage.earliest_deal),NTDateTimeText(coverage.requested_start)));
   if(coverage.earliest_order==0) NTAppendString(coverage.missing_ranges,"No broker order history returned");
   else if(!coverage.order_coverage_complete) NTAppendString(coverage.missing_ranges,StringFormat("Order history begins %s; requested compliance horizon begins %s",NTDateTimeText(coverage.earliest_order),NTDateTimeText(coverage.requested_start)));
   g_last_deals=total;
   g_last_orders=order_total;
   return true;
  }

void NTFilterEligibleEpisodes(const NTSignalEpisode &all[],NTSignalEpisode &eligible[])
  {
   ArrayResize(eligible,0);
   for(int i=0;i<ArraySize(all);i++)
     {
      if(!all[i].product_eligible) continue;
      const int n=ArraySize(eligible);
      ArrayResize(eligible,n+1);
      eligible[n]=all[i];
     }
  }

long NTProgramStart(const NTSignalEpisode &episodes[])
  {
   if(ArraySize(episodes)==0) return 0;
   long earliest=NTSeconds(episodes[0].first_entry_msc);
   for(int i=1;i<ArraySize(episodes);i++) earliest=MathMin(earliest,NTSeconds(episodes[i].first_entry_msc));
   return earliest;
  }

bool NTPauseOverlaps(const long start_time,const long end_time)
  {
   string spec=NTTrim(InpManualPausePeriods);
   if(spec=="") return false;
   string items[];
   const int count=StringSplit(spec,';',items);
   for(int i=0;i<count;i++)
     {
      string pair[];
      if(StringSplit(NTTrim(items[i]),'/',pair)!=2) continue;
      string a=NTTrim(pair[0]),b=NTTrim(pair[1]);
      StringReplace(a,"-",".");
      StringReplace(b,"-",".");
      const long from=(long)StringToTime(a+" 00:00:00");
      const long to=(long)StringToTime(b+" 23:59:59");
      if(from>0 && to>=from && start_time<=to && from<end_time) return true;
     }
   return false;
  }

void NTApplyManualPauses(NTWeekResult &weeks[])
  {
   for(int i=0;i<ArraySize(weeks);i++)
     {
      if(!NTPauseOverlaps(weeks[i].start_time,weeks[i].end_time)) continue;
      weeks[i].manual_pause=true;
      if(weeks[i].status==NT_FAIL) weeks[i].status=NT_NOT_VERIFIABLE;
     }
  }

double NTReconstructOpeningBalance(const NTDealRecord &deals[],const NTCashFlow &cashflows[],const long program_start_seconds)
  {
   double delta=0.0;
   for(int i=0;i<ArraySize(deals);i++)
      if(NTSeconds(deals[i].time_msc)>=program_start_seconds)
         delta+=deals[i].profit+deals[i].commission+deals[i].swap+deals[i].fee;
   for(int i=0;i<ArraySize(cashflows);i++) if(NTSeconds(cashflows[i].time_msc)>=program_start_seconds) delta+=cashflows[i].amount;
   return AccountInfoDouble(ACCOUNT_BALANCE)-delta;
  }

bool NTEpisodeProfitAt(const NTSignalEpisode &ep,const double price,double &profit)
  {
   profit=0.0;
   if(price<=0.0 || ep.weighted_price<=0.0 || ep.max_volume<=0.0) return false;
   const ENUM_ORDER_TYPE type=(ep.direction>0 ? ORDER_TYPE_BUY : ORDER_TYPE_SELL);
   return OrderCalcProfit(type,ep.broker_symbol,ep.max_volume,ep.weighted_price,price,profit);
  }

int NTFindExposure(const ulong position_id,const string broker_symbol)
  {
   for(int i=0;i<ArraySize(g_fdd_job.exposures);i++) if(g_fdd_job.exposures[i].position_id==position_id && g_fdd_job.exposures[i].broker_symbol==broker_symbol) return i;
   return -1;
  }

int NTFindQuote(const string broker_symbol)
  {
   for(int i=0;i<ArraySize(g_fdd_job.quotes);i++) if(g_fdd_job.quotes[i].broker_symbol==broker_symbol) return i;
   return -1;
  }

int NTEnsureQuote(const string broker_symbol)
  {
   int index=NTFindQuote(broker_symbol);
   if(index>=0) return index;
   index=ArraySize(g_fdd_job.quotes);
   ArrayResize(g_fdd_job.quotes,index+1);
   g_fdd_job.quotes[index].broker_symbol=broker_symbol;
   g_fdd_job.quotes[index].bid=0.0;
   g_fdd_job.quotes[index].ask=0.0;
   g_fdd_job.quotes[index].time_msc=0;
   g_fdd_job.quotes[index].valid=false;
   return index;
  }

void NTRemoveExposure(const int index)
  {
   const int n=ArraySize(g_fdd_job.exposures);
   if(index<0 || index>=n) return;
   for(int i=index;i<n-1;i++) g_fdd_job.exposures[i]=g_fdd_job.exposures[i+1];
   ArrayResize(g_fdd_job.exposures,n-1);
  }

void NTApplyDealExposure(const NTDealRecord &deal)
  {
   int index=NTFindExposure(deal.position_id,deal.broker_symbol);
   const int direction=NTDealDirection(deal);
   if(deal.entry==DEAL_ENTRY_IN)
     {
      if(index<0)
        {
         const int n=ArraySize(g_fdd_job.exposures);
         ArrayResize(g_fdd_job.exposures,n+1);
         g_fdd_job.exposures[n].position_id=deal.position_id;
         g_fdd_job.exposures[n].broker_symbol=deal.broker_symbol;
         g_fdd_job.exposures[n].canonical_symbol=deal.canonical_symbol;
         g_fdd_job.exposures[n].direction=direction;
         g_fdd_job.exposures[n].volume=deal.volume;
         g_fdd_job.exposures[n].weighted_price=deal.price;
        }
      else
        {
         const double old_volume=g_fdd_job.exposures[index].volume;
         const double next=old_volume+deal.volume;
         if(next>0.0) g_fdd_job.exposures[index].weighted_price=(g_fdd_job.exposures[index].weighted_price*old_volume+deal.price*deal.volume)/next;
         g_fdd_job.exposures[index].volume=next;
        }
      return;
     }
   if(deal.entry==DEAL_ENTRY_OUT || deal.entry==DEAL_ENTRY_OUT_BY)
     {
      if(index<0) return;
      g_fdd_job.exposures[index].volume=MathMax(0.0,g_fdd_job.exposures[index].volume-deal.volume);
      if(g_fdd_job.exposures[index].volume<=0.00000001) NTRemoveExposure(index);
      return;
     }
   if(deal.entry==DEAL_ENTRY_INOUT)
     {
      double residual=deal.volume;
      if(index>=0)
        {
         residual=MathMax(0.0,deal.volume-g_fdd_job.exposures[index].volume);
         NTRemoveExposure(index);
        }
      if(residual>0.00000001)
        {
         const int n=ArraySize(g_fdd_job.exposures);
         ArrayResize(g_fdd_job.exposures,n+1);
         g_fdd_job.exposures[n].position_id=deal.position_id;
         g_fdd_job.exposures[n].broker_symbol=deal.broker_symbol;
         g_fdd_job.exposures[n].canonical_symbol=deal.canonical_symbol;
         g_fdd_job.exposures[n].direction=direction;
         g_fdd_job.exposures[n].volume=residual;
         g_fdd_job.exposures[n].weighted_price=deal.price;
        }
     }
  }

bool NTAccountEquityFromQuotes(double &equity)
  {
   double unrealized[];
   ArrayResize(unrealized,ArraySize(g_fdd_job.exposures));
   for(int i=0;i<ArraySize(g_fdd_job.exposures);i++)
     {
      const int quote_index=NTFindQuote(g_fdd_job.exposures[i].broker_symbol);
      if(quote_index<0 || !g_fdd_job.quotes[quote_index].valid) return false;
      const double price=(g_fdd_job.exposures[i].direction>0 ? g_fdd_job.quotes[quote_index].bid : g_fdd_job.quotes[quote_index].ask);
      const ENUM_ORDER_TYPE type=(g_fdd_job.exposures[i].direction>0 ? ORDER_TYPE_BUY : ORDER_TYPE_SELL);
      if(price<=0.0 || !OrderCalcProfit(type,g_fdd_job.exposures[i].broker_symbol,g_fdd_job.exposures[i].volume,g_fdd_job.exposures[i].weighted_price,price,unrealized[i])) return false;
     }
   equity=NTAggregateEquity(g_fdd_job.balance,unrealized);
   return true;
  }

void NTCaptureFddContributors()
  {
   ArrayResize(g_fdd_job.worst_position_ids,ArraySize(g_fdd_job.exposures));
   ArrayResize(g_fdd_job.worst_symbols,ArraySize(g_fdd_job.exposures));
   for(int i=0;i<ArraySize(g_fdd_job.exposures);i++)
     {
      g_fdd_job.worst_position_ids[i]=StringFormat("%I64u",g_fdd_job.exposures[i].position_id);
      g_fdd_job.worst_symbols[i]=g_fdd_job.exposures[i].canonical_symbol;
     }
  }

bool NTObserveAggregateFdd(const long time_msc)
  {
   double equity=0.0;
   if(!NTAccountEquityFromQuotes(equity)) return false;
   if(g_fdd_job.peak_equity<=0.0 || equity>g_fdd_job.peak_equity) g_fdd_job.peak_equity=equity;
   const double floating=NTFloatingLossPct(g_fdd_job.balance,equity);
   const double peak_dd=NTPeakToTroughPct(g_fdd_job.peak_equity,equity);
   if(floating>g_fdd_job.max_floating_loss_pct || peak_dd>g_fdd_job.max_peak_to_trough_pct)
     {
      g_fdd_job.max_floating_loss_pct=MathMax(g_fdd_job.max_floating_loss_pct,floating);
      g_fdd_job.max_peak_to_trough_pct=MathMax(g_fdd_job.max_peak_to_trough_pct,peak_dd);
      g_fdd_job.event_server_time=time_msc/1000;
      g_fdd_job.balance_at_event=g_fdd_job.balance;
      g_fdd_job.equity_at_event=equity;
      NTCaptureFddContributors();
     }
   return true;
  }

void NTResetFddJob(const long program_start,const double opening_balance)
  {
   g_fdd_job.initialized=true;
   g_fdd_job.program_start=program_start;
   g_fdd_job.cursor_seconds=program_start;
   g_fdd_job.balance=opening_balance;
   g_fdd_job.peak_equity=opening_balance;
   g_fdd_job.max_floating_loss_pct=0.0;
   g_fdd_job.max_peak_to_trough_pct=0.0;
   g_fdd_job.event_server_time=program_start;
   g_fdd_job.balance_at_event=opening_balance;
   g_fdd_job.equity_at_event=opening_balance;
   g_fdd_job.processed_tick_slices=0;
   g_fdd_job.processed_m1_slices=0;
   g_fdd_job.gap_slices=0;
   g_fdd_job.method="RECONSTRUCTED";
   ArrayResize(g_fdd_job.worst_position_ids,0);
   ArrayResize(g_fdd_job.worst_symbols,0);
   ArrayResize(g_fdd_job.gap_intervals,0);
   ArrayResize(g_fdd_job.exposures,0);
   ArrayResize(g_fdd_job.quotes,0);
  }

void NTSaveFddJob()
  {
   if(!g_fdd_job.initialized) return;
   int handle=FileOpen(NTFddStatePath(),FILE_WRITE|FILE_CSV|FILE_ANSI|FILE_COMMON,';');
   if(handle==INVALID_HANDLE) return;
   FileWrite(handle,"v2",NTAccountFingerprint(),g_fdd_job.program_start,g_fdd_job.cursor_seconds,g_fdd_job.balance,g_fdd_job.peak_equity,g_fdd_job.max_floating_loss_pct,g_fdd_job.max_peak_to_trough_pct,g_fdd_job.event_server_time,g_fdd_job.balance_at_event,g_fdd_job.equity_at_event,g_fdd_job.processed_tick_slices,g_fdd_job.processed_m1_slices,g_fdd_job.gap_slices,g_fdd_job.method);
   for(int i=0;i<ArraySize(g_fdd_job.worst_position_ids) && i<ArraySize(g_fdd_job.worst_symbols);i++) FileWrite(handle,"W",g_fdd_job.worst_position_ids[i],g_fdd_job.worst_symbols[i]);
   for(int i=0;i<ArraySize(g_fdd_job.gap_intervals);i++) FileWrite(handle,"G",g_fdd_job.gap_intervals[i]);
   for(int i=0;i<ArraySize(g_fdd_job.exposures);i++) FileWrite(handle,"E",g_fdd_job.exposures[i].position_id,g_fdd_job.exposures[i].broker_symbol,g_fdd_job.exposures[i].canonical_symbol,g_fdd_job.exposures[i].direction,g_fdd_job.exposures[i].volume,g_fdd_job.exposures[i].weighted_price);
   for(int i=0;i<ArraySize(g_fdd_job.quotes);i++) FileWrite(handle,"Q",g_fdd_job.quotes[i].broker_symbol,g_fdd_job.quotes[i].bid,g_fdd_job.quotes[i].ask,g_fdd_job.quotes[i].time_msc,g_fdd_job.quotes[i].valid?1:0);
   FileFlush(handle);
   FileClose(handle);
  }

void NTLoadFddJob()
  {
   g_fdd_job.initialized=false;
   int handle=FileOpen(NTFddStatePath(),FILE_READ|FILE_CSV|FILE_ANSI|FILE_COMMON,';');
   if(handle==INVALID_HANDLE) return;
   const string version=FileReadString(handle);
   const string fingerprint=FileReadString(handle);
   if(version!="v2" || fingerprint!=NTAccountFingerprint())
     {
      FileClose(handle);
      return;
     }
   g_fdd_job.initialized=true;
   g_fdd_job.program_start=(long)FileReadNumber(handle);
   g_fdd_job.cursor_seconds=(long)FileReadNumber(handle);
   g_fdd_job.balance=FileReadNumber(handle);
   g_fdd_job.peak_equity=FileReadNumber(handle);
   g_fdd_job.max_floating_loss_pct=FileReadNumber(handle);
   g_fdd_job.max_peak_to_trough_pct=FileReadNumber(handle);
   g_fdd_job.event_server_time=(long)FileReadNumber(handle);
   g_fdd_job.balance_at_event=FileReadNumber(handle);
   g_fdd_job.equity_at_event=FileReadNumber(handle);
   g_fdd_job.processed_tick_slices=(long)FileReadNumber(handle);
   g_fdd_job.processed_m1_slices=(long)FileReadNumber(handle);
   g_fdd_job.gap_slices=(long)FileReadNumber(handle);
   g_fdd_job.method=FileReadString(handle);
   ArrayResize(g_fdd_job.worst_position_ids,0);
   ArrayResize(g_fdd_job.worst_symbols,0);
   ArrayResize(g_fdd_job.gap_intervals,0);
   ArrayResize(g_fdd_job.exposures,0);
   ArrayResize(g_fdd_job.quotes,0);
   while(!FileIsEnding(handle))
     {
      const string kind=FileReadString(handle);
      if(kind=="W")
        {
         const int n=ArraySize(g_fdd_job.worst_position_ids);
         ArrayResize(g_fdd_job.worst_position_ids,n+1);
         ArrayResize(g_fdd_job.worst_symbols,n+1);
         g_fdd_job.worst_position_ids[n]=FileReadString(handle);
         g_fdd_job.worst_symbols[n]=FileReadString(handle);
        }
      else if(kind=="G")
        {
         const int n=ArraySize(g_fdd_job.gap_intervals);
         ArrayResize(g_fdd_job.gap_intervals,n+1);
         g_fdd_job.gap_intervals[n]=FileReadString(handle);
        }
      else if(kind=="E")
        {
         const int n=ArraySize(g_fdd_job.exposures);
         ArrayResize(g_fdd_job.exposures,n+1);
         g_fdd_job.exposures[n].position_id=(ulong)FileReadNumber(handle);
         g_fdd_job.exposures[n].broker_symbol=FileReadString(handle);
         g_fdd_job.exposures[n].canonical_symbol=FileReadString(handle);
         g_fdd_job.exposures[n].direction=(int)FileReadNumber(handle);
         g_fdd_job.exposures[n].volume=FileReadNumber(handle);
         g_fdd_job.exposures[n].weighted_price=FileReadNumber(handle);
        }
      else if(kind=="Q")
        {
         const int n=ArraySize(g_fdd_job.quotes);
         ArrayResize(g_fdd_job.quotes,n+1);
         g_fdd_job.quotes[n].broker_symbol=FileReadString(handle);
         g_fdd_job.quotes[n].bid=FileReadNumber(handle);
         g_fdd_job.quotes[n].ask=FileReadNumber(handle);
         g_fdd_job.quotes[n].time_msc=(long)FileReadNumber(handle);
         g_fdd_job.quotes[n].valid=(FileReadNumber(handle)!=0);
        }
      else break;
     }
   FileClose(handle);
  }

bool NTAppendFddEvent(NTFddTimelineEvent &events[],const NTFddTimelineEvent &event)
  {
   const int n=ArraySize(events);
   if(n>=NT_RECON_MAX_EVENTS_PER_SLICE) return false;
   ArrayResize(events,n+1);
   events[n]=event;
   return true;
  }

int NTFddEventPriority(const int kind)
  {
   if(kind==2) return 0;
   if(kind==0) return 1;
   return 2;
  }

void NTSortFddEvents(NTFddTimelineEvent &events[])
  {
   for(int i=1;i<ArraySize(events);i++)
     {
      const NTFddTimelineEvent value=events[i];
      const int value_priority=NTFddEventPriority(value.kind);
      int j=i-1;
      while(j>=0 && (events[j].time_msc>value.time_msc || (events[j].time_msc==value.time_msc && NTFddEventPriority(events[j].kind)>value_priority)))
        {
         events[j+1]=events[j];
         j--;
        }
      events[j+1]=value;
     }
  }

void NTAppendUniqueSymbol(string &symbols[],const string symbol)
  {
   if(symbol=="") return;
   for(int i=0;i<ArraySize(symbols);i++) if(symbols[i]==symbol) return;
   const int n=ArraySize(symbols);
   ArrayResize(symbols,n+1);
   symbols[n]=symbol;
  }

bool NTBuildFddSliceEvents(const NTDealRecord &deals[],const NTCashFlow &cashflows[],const long from_seconds,const long to_seconds,NTFddTimelineEvent &events[],string &slice_method)
  {
   ArrayResize(events,0);
   slice_method="TICK";
   string symbols[];
   ArrayResize(symbols,0);
   for(int i=0;i<ArraySize(g_fdd_job.exposures);i++) NTAppendUniqueSymbol(symbols,g_fdd_job.exposures[i].broker_symbol);
   for(int i=0;i<ArraySize(deals);i++)
     {
      const long t=NTSeconds(deals[i].time_msc);
      if(t<from_seconds || t>=to_seconds) continue;
      NTFddTimelineEvent event;
      event.time_msc=deals[i].time_msc;
      event.kind=0;
      event.source_index=i;
      event.broker_symbol="";
      event.bid=0.0;
      event.ask=0.0;
      if(!NTAppendFddEvent(events,event)) return false;
      NTAppendUniqueSymbol(symbols,deals[i].broker_symbol);
     }
   for(int i=0;i<ArraySize(cashflows);i++)
     {
      const long t=NTSeconds(cashflows[i].time_msc);
      if(t<from_seconds || t>=to_seconds) continue;
      NTFddTimelineEvent event;
      event.time_msc=cashflows[i].time_msc;
      event.kind=1;
      event.source_index=i;
      event.broker_symbol="";
      event.bid=0.0;
      event.ask=0.0;
      if(!NTAppendFddEvent(events,event)) return false;
     }
   for(int s=0;s<ArraySize(symbols);s++)
     {
      MqlTick ticks[];
      const int before=ArraySize(events);
      const int copied=CopyTicks(symbols[s],ticks,COPY_TICKS_INFO,(ulong)from_seconds*1000ULL,NT_RECON_MAX_TICKS_PER_SYMBOL_SLICE);
      const long slice_end_msc=to_seconds*1000L-1L;
      const bool tick_window_complete=(copied>0 && (copied<NT_RECON_MAX_TICKS_PER_SYMBOL_SLICE || (long)ticks[copied-1].time_msc>=slice_end_msc));
      if(tick_window_complete)
        {
         for(int k=0;k<copied;k++)
           {
            if((long)ticks[k].time_msc>=to_seconds*1000L) break;
            if(ticks[k].bid<=0.0 || ticks[k].ask<=0.0) continue;
            NTFddTimelineEvent event;
            event.time_msc=(long)ticks[k].time_msc;
            event.kind=2;
            event.source_index=-1;
            event.broker_symbol=symbols[s];
            event.bid=ticks[k].bid;
            event.ask=ticks[k].ask;
            if(!NTAppendFddEvent(events,event)) return false;
           }
         g_fdd_job.processed_tick_slices++;
         continue;
        }
      ArrayResize(events,before);
      MqlRates bars[];
      const int rates=CopyRates(symbols[s],PERIOD_M1,(datetime)from_seconds,(datetime)(to_seconds-1),bars);
      if(rates<=0) return false;
      slice_method="M1";
      for(int k=0;k<rates;k++)
        {
         NTFddTimelineEvent event;
         event.time_msc=(long)bars[k].time*1000L;
         event.kind=2;
         event.source_index=-1;
         event.broker_symbol=symbols[s];
         event.bid=bars[k].low;
         event.ask=bars[k].high;
         if(!NTAppendFddEvent(events,event)) return false;
        }
      g_fdd_job.processed_m1_slices++;
     }
   NTSortFddEvents(events);
   return true;
  }

void NTRecordFddGap(const long from_seconds,const long to_seconds)
  {
   g_fdd_job.gap_slices++;
   g_fdd_job.method="DATA_GAP";
   if(ArraySize(g_fdd_job.gap_intervals)<256) NTAppendString(g_fdd_job.gap_intervals,NTDateTimeText(from_seconds)+" -> "+NTDateTimeText(to_seconds));
  }

void NTProcessFddSlice(const NTDealRecord &deals[],const NTCashFlow &cashflows[],const long from_seconds,const long to_seconds)
  {
   NTFddTimelineEvent events[];
   string slice_method="";
   if(!NTBuildFddSliceEvents(deals,cashflows,from_seconds,to_seconds,events,slice_method))
     {
      NTRecordFddGap(from_seconds,to_seconds);
      g_fdd_job.cursor_seconds=to_seconds;
      NTSaveFddJob();
      return;
     }
   if(slice_method=="M1" && g_fdd_job.method!="DATA_GAP") g_fdd_job.method="M1";
   bool valuation_gap=false;
   for(int i=0;i<ArraySize(events);i++)
     {
      const NTFddTimelineEvent event=events[i];
      if(event.kind==0)
        {
         const NTDealRecord deal=deals[event.source_index];
         g_fdd_job.balance+=deal.profit+deal.commission+deal.swap+deal.fee;
         NTApplyDealExposure(deal);
         if(!NTObserveAggregateFdd(event.time_msc) && ArraySize(g_fdd_job.exposures)>0) valuation_gap=true;
        }
      else if(event.kind==1)
        {
         g_fdd_job.balance+=cashflows[event.source_index].amount;
         if(!NTObserveAggregateFdd(event.time_msc) && ArraySize(g_fdd_job.exposures)>0) valuation_gap=true;
        }
      else
        {
         const int quote_index=NTEnsureQuote(event.broker_symbol);
         g_fdd_job.quotes[quote_index].bid=event.bid;
         g_fdd_job.quotes[quote_index].ask=event.ask;
         g_fdd_job.quotes[quote_index].time_msc=event.time_msc;
         g_fdd_job.quotes[quote_index].valid=true;
         if(!NTObserveAggregateFdd(event.time_msc) && ArraySize(g_fdd_job.exposures)>0) valuation_gap=true;
        }
     }
   if(valuation_gap) NTRecordFddGap(from_seconds,to_seconds);
   g_fdd_job.cursor_seconds=to_seconds;
   NTSaveFddJob();
  }

void NTAdvanceFddJob(const NTDealRecord &deals[],const NTCashFlow &cashflows[],const long program_start_seconds,const long now_seconds,const double opening_balance)
  {
   if(program_start_seconds<=0 || opening_balance<=0.0) return;
   if(!g_fdd_job.initialized || g_fdd_job.program_start!=program_start_seconds || g_fdd_job.cursor_seconds<program_start_seconds) NTResetFddJob(program_start_seconds,opening_balance);
   const ulong started=GetMicrosecondCount();
   const long max_slice=MathMax(1,(long)MathMax(1,InpReconstructionChunkMinutes)*60L);
   const long slice=MathMin(max_slice,(long)MathMax(5,InpReconstructionSliceSeconds));
   while(g_fdd_job.cursor_seconds<now_seconds)
     {
      const long end=MathMin(now_seconds,g_fdd_job.cursor_seconds+slice);
      NTProcessFddSlice(deals,cashflows,g_fdd_job.cursor_seconds,end);
      if((long)(GetMicrosecondCount()-started)>=MathMax(25,InpReconstructionBudgetMs)*1000L) break;
     }
  }

void NTReconstructFdd(const NTSignalEpisode &episodes[],const long program_start_seconds,const long now_seconds,const double denominator_balance,NTFddResult &out)
  {
   ArrayResize(out.contributing_position_ids,0);
   ArrayResize(out.contributing_symbols,0);
   ArrayResize(out.missing_intervals,0);
   out.max_floating_loss_pct=g_exact.max_floating_loss_pct;
   out.max_peak_to_trough_pct=g_exact.max_peak_to_trough_pct;
   out.event_server_time=g_exact.event_server_time;
   out.balance_at_event=g_exact.balance_at_event;
   out.equity_at_event=g_exact.equity_at_event;
   out.method="DATA_GAP";
   out.status=NT_IN_PROGRESS;
   out.tick_coverage_pct=0.0;
   out.bar_coverage_pct=0.0;
   if(program_start_seconds<=0 || !g_fdd_job.initialized || g_fdd_job.program_start!=program_start_seconds)
     {
      out.status=NT_DATA_GAP;
      NTAppendString(out.missing_intervals,"FDD reconstruction has not initialized for the current participation start");
      return;
     }
   const long total_slices=g_fdd_job.processed_tick_slices+g_fdd_job.processed_m1_slices+g_fdd_job.gap_slices;
   if(total_slices>0)
     {
      out.tick_coverage_pct=(double)g_fdd_job.processed_tick_slices/(double)total_slices*100.0;
      out.bar_coverage_pct=(double)g_fdd_job.processed_m1_slices/(double)total_slices*100.0;
     }
   if(g_fdd_job.max_floating_loss_pct>=out.max_floating_loss_pct)
     {
      out.max_floating_loss_pct=g_fdd_job.max_floating_loss_pct;
      out.max_peak_to_trough_pct=MathMax(out.max_peak_to_trough_pct,g_fdd_job.max_peak_to_trough_pct);
      out.event_server_time=g_fdd_job.event_server_time;
      out.balance_at_event=g_fdd_job.balance_at_event;
      out.equity_at_event=g_fdd_job.equity_at_event;
      ArrayResize(out.contributing_position_ids,ArraySize(g_fdd_job.worst_position_ids));
      ArrayResize(out.contributing_symbols,ArraySize(g_fdd_job.worst_symbols));
      for(int i=0;i<ArraySize(out.contributing_position_ids);i++) out.contributing_position_ids[i]=g_fdd_job.worst_position_ids[i];
      for(int i=0;i<ArraySize(out.contributing_symbols);i++) out.contributing_symbols[i]=g_fdd_job.worst_symbols[i];
     }
   if(g_fdd_job.gap_slices>0)
     {
      out.method="DATA_GAP";
      out.status=NT_DATA_GAP;
      for(int i=0;i<ArraySize(g_fdd_job.gap_intervals);i++) NTAppendString(out.missing_intervals,g_fdd_job.gap_intervals[i]);
      if(ArraySize(g_fdd_job.gap_intervals)<g_fdd_job.gap_slices) NTAppendString(out.missing_intervals,StringFormat("%I64d additional reconstruction gap slice(s) omitted from bounded gap list",g_fdd_job.gap_slices-ArraySize(g_fdd_job.gap_intervals)));
      return;
     }
   if(g_fdd_job.cursor_seconds<now_seconds)
     {
      out.method=(g_fdd_job.method=="M1" ? "M1" : "RECONSTRUCTED");
      out.status=NT_IN_PROGRESS;
      NTAppendString(out.missing_intervals,StringFormat("FDD reconstruction progress %s -> %s",NTDateTimeText(program_start_seconds),NTDateTimeText(g_fdd_job.cursor_seconds)));
      return;
     }
   out.method=(g_fdd_job.method=="M1" ? "M1" : "RECONSTRUCTED");
   out.status=NT_RECONSTRUCTED;
  }

string NTCriterionJson(const NTCriterionState &criterion,const string evidence_json="[]")
  {
   return "{\"id\":"+NTJsonQuote(criterion.id)
      +",\"status\":"+NTJsonQuote(NTStatusName(criterion.status))
      +",\"titleVi\":"+NTJsonQuote(criterion.id)
      +",\"summaryVi\":"+NTJsonQuote(criterion.explanation_vi)
      +",\"evidence\":"+evidence_json+"}";
  }

string NTEvidenceJson(const string criterion,const string severity,const NTStatus status,const string reason,const string explanation,const long server_time,const string broker_symbol,const string canonical_symbol,const string position_ids_json,const string order_tickets_json,const string deal_tickets_json,const string measured,const string threshold,const string source,const string confidence)
  {
   return "{\"criterionId\":"+NTJsonQuote(criterion)
      +",\"severity\":"+NTJsonQuote(severity)
      +",\"status\":"+NTJsonQuote(NTStatusName(status))
      +",\"reasonCode\":"+NTJsonQuote(reason)
      +",\"explanationVi\":"+NTJsonQuote(explanation)
      +",\"serverTime\":"+(server_time>0?NTJsonQuote(NTDateTimeText(server_time)):"null")
      +",\"serverUtcOffsetMinutes\":"+(server_time>0?IntegerToString(NTServerUtcOffsetMinutes(server_time)):"null")
      +",\"utcTime\":"+(server_time>0?NTJsonQuote(NTUtcTimeTextFromNeoTechServer(server_time)):"null")
      +",\"vietnamTime\":"+(server_time>0?NTJsonQuote(NTVietnamTimeText(server_time)):"null")
      +",\"season\":"+(server_time>0?NTJsonQuote(NTIsSummer(server_time)?"summer":"winter"):"null")
      +",\"session\":"+(server_time>0?NTJsonQuote(NTSessionName(NTAssignSession(server_time))):"null")
      +",\"brokerSymbol\":"+(broker_symbol!=""?NTJsonQuote(broker_symbol):"null")
      +",\"canonicalSymbol\":"+(canonical_symbol!=""?NTJsonQuote(canonical_symbol):"null")
      +",\"positionIds\":"+position_ids_json
      +",\"orderTickets\":"+order_tickets_json
      +",\"dealTickets\":"+deal_tickets_json
      +",\"measuredValue\":"+(measured!=""?NTJsonQuote(measured):"null")
      +",\"threshold\":"+(threshold!=""?NTJsonQuote(threshold):"null")
      +",\"evidenceSource\":"+NTJsonQuote(source)
      +",\"confidence\":"+NTJsonQuote(confidence)
      +",\"occurrenceCount\":1}";
  }

string NTEpisodeDealTicketsJson(const NTSignalEpisode &episode)
  {
   string out="[";
   for(int i=0;i<ArraySize(episode.entry_tickets);i++) NTAppendJsonItem(out,NTJsonQuote(StringFormat("%I64u",episode.entry_tickets[i])));
   for(int i=0;i<ArraySize(episode.exit_tickets);i++) NTAppendJsonItem(out,NTJsonQuote(StringFormat("%I64u",episode.exit_tickets[i])));
   return out+"]";
  }

void NTAppendJsonItem(string &json,const string item)
  {
   if(json!="[") json+=",";
   json+=item;
  }

void NTAddEvent(NTJsonEvent &events[],const long time,const string json)
  {
   const int n=ArraySize(events);
   ArrayResize(events,n+1);
   events[n].time=time;
   events[n].json=json;
  }

void NTSortEvents(NTJsonEvent &events[])
  {
   for(int i=1;i<ArraySize(events);i++)
     {
      const NTJsonEvent value=events[i];
      int j=i-1;
      while(j>=0 && (events[j].time>value.time || (events[j].time==value.time && StringCompare(events[j].json,value.json)>0)))
        {
         events[j+1]=events[j];
         j--;
        }
      events[j+1]=value;
     }
  }

string NTEventsJson(NTJsonEvent &events[])
  {
   NTSortEvents(events);
   string out="[";
   for(int i=0;i<ArraySize(events);i++) NTAppendJsonItem(out,events[i].json);
   return out+"]";
  }

string NTWeeksJson(const NTWeekResult &weeks[])
  {
   string out="[";
   for(int i=0;i<ArraySize(weeks);i++)
     {
      if(i>0) out+=",";
      out+="{\"startServerEpoch\":"+IntegerToString(weeks[i].start_time)+",\"endServerEpoch\":"+IntegerToString(weeks[i].end_time)+",\"startTime\":"+NTTimePointJson(weeks[i].start_time)+",\"endTime\":"+NTTimePointJson(weeks[i].end_time)+",\"count\":"+IntegerToString(weeks[i].signal_count)+",\"target\":3,\"missing\":"+IntegerToString(weeks[i].missing)+",\"status\":"+NTJsonQuote(NTStatusName(weeks[i].status))+",\"manualPause\":"+NTJsonBool(weeks[i].manual_pause)+",\"evidenceSource\":"+NTJsonQuote(weeks[i].manual_pause?"MANUAL_DECLARATION":"MT5_HISTORY")+"}";
     }
   return out+"]";
  }

string NTMonthsJson(const NTMonthResult &months[])
  {
   string out="[";
   for(int i=0;i<ArraySize(months);i++)
     {
      if(i>0) out+=",";
      out+="{\"startServerEpoch\":"+IntegerToString(months[i].start_time)+",\"endServerEpoch\":"+IntegerToString(months[i].end_time)+",\"startTime\":"+NTTimePointJson(months[i].start_time)+",\"endTime\":"+NTTimePointJson(months[i].end_time)+",\"openingBalance\":"+NTJsonNumber(months[i].opening_balance,2)+",\"tradingNetPL\":"+NTJsonNumber(months[i].trading_net_pl,2)+",\"deposits\":"+NTJsonNumber(months[i].deposits,2)+",\"withdrawals\":"+NTJsonNumber(months[i].withdrawals,2)+",\"otherCashFlow\":"+NTJsonNumber(months[i].other_cash_flow,2)+",\"rawReturnPct\":"+NTJsonNumber(months[i].raw_return_pct,5)+",\"cashFlowAdjustedReturnPct\":"+NTJsonNumber(months[i].adjusted_return_pct,5)+",\"status\":"+NTJsonQuote(NTStatusName(months[i].status))+"}";
     }
   return out+"]";
  }

string NTSessionCountsJson(const NTSignalEpisode &episodes[])
  {
   string out="[";
   for(int i=0;i<ArraySize(episodes);i++)
     {
      if(i>0) out+=",";
      const long opened=NTSeconds(episodes[i].first_entry_msc);
      out+="{\"episodeId\":"+NTJsonQuote(episodes[i].episode_id)+",\"serverTime\":"+NTJsonQuote(NTDateTimeText(opened))+",\"serverUtcOffsetMinutes\":"+IntegerToString(NTServerUtcOffsetMinutes(opened))+",\"utcTime\":"+NTJsonQuote(NTUtcTimeTextFromNeoTechServer(opened))+",\"vietnamTime\":"+NTJsonQuote(NTVietnamTimeText(opened))+",\"season\":"+NTJsonQuote(NTIsSummer(opened)?"summer":"winter")+",\"session\":"+NTJsonQuote(NTSessionName(episodes[i].session))+",\"canonicalSymbol\":"+NTJsonQuote(episodes[i].canonical_symbol)+",\"brokerSymbol\":"+NTJsonQuote(episodes[i].broker_symbol)+"}";
     }
   return out+"]";
  }

string NTStringArrayJson(const string &items[])
  {
   return NTJsonStringArray(items);
  }

int NTCountEligibility(const NTCriterionState &criteria[],const NTStatus target,const bool unknown=false)
  {
   int count=0;
   for(int i=0;i<ArraySize(criteria);i++)
     {
      if(StringGetCharacter(criteria[i].id,0)!='E') continue;
      if(unknown)
        {
         if(criteria[i].status==NT_NOT_VERIFIABLE || criteria[i].status==NT_DATA_GAP || criteria[i].status==NT_RECONSTRUCTED || criteria[i].status==NT_IN_PROGRESS) count++;
        }
      else if(criteria[i].status==target) count++;
     }
   return count;
  }

int NTCountAwards(const NTCriterionState &criteria[],const NTStatus target,const bool unknown=false)
  {
   int count=0;
   for(int i=0;i<ArraySize(criteria);i++)
     {
      if(StringGetCharacter(criteria[i].id,0)!='C') continue;
      if(unknown)
        {
         if(criteria[i].status==NT_NOT_VERIFIABLE || criteria[i].status==NT_DATA_GAP || criteria[i].status==NT_RECONSTRUCTED) count++;
        }
      else if(criteria[i].status==target) count++;
     }
   return count;
  }

void NTC5EvidenceDetails(const NTSessionViolation &group,const NTSignalEpisode &episodes[],long &event_time,string &broker_symbol,string &order_tickets,string &deal_tickets)
  {
   event_time=0;
   broker_symbol="";
   order_tickets="[";
   deal_tickets="[";
   long first=0,second=0;
   for(int i=0;i<ArraySize(episodes);i++)
     {
      const long t=NTSeconds(episodes[i].first_entry_msc);
      if(episodes[i].canonical_symbol!=group.canonical_symbol || episodes[i].session!=group.session || NTDayStart(t)!=group.session_date) continue;
      if(broker_symbol=="") broker_symbol=episodes[i].broker_symbol;
      NTAppendJsonItem(order_tickets,NTJsonQuote(StringFormat("%I64u",episodes[i].opening_order_ticket)));
      NTAppendJsonItem(deal_tickets,NTJsonQuote(StringFormat("%I64u",episodes[i].opening_deal_ticket)));
      if(first==0 || t<first)
        {
         second=first;
         first=t;
        }
      else if(second==0 || t<second) second=t;
     }
   order_tickets+="]";
   deal_tickets+="]";
   event_time=(second>0 ? second : first);
  }

bool NTHedgingEvidenceDetails(const NTSignalEpisode &episodes[],const long now_msc,long &event_time,string &broker_symbol,string &canonical_symbol,string &position_ids,string &order_tickets,string &deal_tickets)
  {
   for(int i=0;i<ArraySize(episodes);i++)
      for(int j=i+1;j<ArraySize(episodes);j++)
        {
         if(episodes[i].canonical_symbol!=episodes[j].canonical_symbol || episodes[i].direction==episodes[j].direction || episodes[i].position_id==episodes[j].position_id || !NTIntervalsOverlap(episodes[i],episodes[j],now_msc)) continue;
         event_time=MathMax(NTSeconds(episodes[i].first_entry_msc),NTSeconds(episodes[j].first_entry_msc));
         broker_symbol=episodes[j].broker_symbol;
         canonical_symbol=episodes[i].canonical_symbol;
         position_ids="["+NTJsonQuote(StringFormat("%I64u",episodes[i].position_id))+","+NTJsonQuote(StringFormat("%I64u",episodes[j].position_id))+"]";
         order_tickets="["+NTJsonQuote(StringFormat("%I64u",episodes[i].opening_order_ticket))+","+NTJsonQuote(StringFormat("%I64u",episodes[j].opening_order_ticket))+"]";
         deal_tickets="["+NTJsonQuote(StringFormat("%I64u",episodes[i].opening_deal_ticket))+","+NTJsonQuote(StringFormat("%I64u",episodes[j].opening_deal_ticket))+"]";
         return true;
        }
   return false;
  }

string NTBuildReport(string &report_hash)
  {
   NTDealRecord deals[];
   NTCashFlow cashflows[];
   NTHistoryCoverage coverage;
   const bool history_ok=NTLoadHistory(deals,cashflows,coverage);
   NTSignalEpisode all_episodes[];
   NTNormalizeDeals(deals,all_episodes);
   const long now_server=(long)TimeTradeServer()>0 ? (long)TimeTradeServer() : (long)TimeCurrent();
   const long now_utc=(long)TimeGMT();
   const long program_start=NTFirstEpisodeStart(all_episodes);
   NTFinalizeOpenDurations(all_episodes,now_server*1000L,program_start);
   NTMergeProspectiveSltp(all_episodes);
   NTSignalEpisode episodes[];
   NTFilterEligibleEpisodes(all_episodes,episodes);
   const bool history_complete=history_ok && coverage.joint_history_complete;
   const bool qualification_complete=NTQualificationHorizonComplete(program_start,now_server);

   NTWeekResult weeks[];
   NTBuildWeeks(episodes,now_server,weeks);
   NTApplyManualPauses(weeks);
   const double opening_balance=(program_start>0 ? NTReconstructOpeningBalance(deals,cashflows,program_start) : AccountInfoDouble(ACCOUNT_BALANCE));
   ArrayResize(g_cached_deals,ArraySize(deals));
   for(int i=0;i<ArraySize(deals);i++) g_cached_deals[i]=deals[i];
   ArrayResize(g_cached_cashflows,ArraySize(cashflows));
   for(int i=0;i<ArraySize(cashflows);i++) g_cached_cashflows[i]=cashflows[i];
   g_cached_program_start=program_start;
   g_cached_opening_balance=opening_balance;
   NTAdvanceFddJob(deals,cashflows,program_start,now_server,opening_balance);
   NTMonthResult months[];
   NTBuildMonths(episodes,cashflows,program_start,now_server,opening_balance,months);
   NTFddResult fdd;
   NTReconstructFdd(episodes,program_start,now_server,MathMax(0.01,opening_balance),fdd);

   NTCriterionState criteria[];
   ArrayResize(criteria,14);
   NTSetCriterion(criteria[0],"E1",NTEvaluateE1(all_episodes,history_complete),"OPEN_REASON","Lệnh mở phải được thao tác thủ công; EA đóng/SL/TP không làm hỏng E1. PASS do absence chỉ được phép khi order/deal coverage đầy đủ.");
   const int trade_mode=(int)AccountInfoInteger(ACCOUNT_TRADE_MODE);
   NTSetCriterion(criteria[1],"E2",(trade_mode==ACCOUNT_TRADE_MODE_REAL || trade_mode==ACCOUNT_TRADE_MODE_DEMO)?NT_PASS:NT_FAIL,"ACCOUNT_TRADE_MODE","MT5 xác nhận chế độ tài khoản Real/Demo; Cent không thể phân biệt riêng bằng trade mode.");
   NTSetCriterion(criteria[2],"E3",NT_PASS,"ANY_INITIAL_CAPITAL","NeoTech cho phép vốn ban đầu bất kỳ; số dư chỉ được ghi làm bằng chứng, không đặt ngưỡng.");
   NTSetCriterion(criteria[3],"E4",NT_NOT_VERIFIABLE,"NO_AUTHORITATIVE_ENROLLMENT_INTEGRATION","MT5 không chứng minh KYC/Public/tài khoản mới/một tài khoản mỗi người hay Direct/Demo Direct.");
   NTSetCriterion(criteria[4],"E5",NTEvaluateE5(all_episodes,program_start,history_complete),"PRODUCT_METADATA","Program start mặc định là trade episode đầu tiên, kể cả sản phẩm bị loại; symbol ngoài Forex/Gold không thể tự ẩn bằng eligible-only start.");
   NTSetCriterion(criteria[5],"C1",NTEvaluateC1(program_start,now_server,history_complete),"DURATION_POLICY","Policy nghiêm ngặt: cần cả 365 ngày lịch và 12 cửa sổ 30 ngày hoàn tất.");
   NTSetCriterion(criteria[6],"C2",NTEvaluateC2(months,history_complete),"MONTHLY_RETURN","Mỗi cửa sổ 30 ngày hoàn tất phải đạt cash-flow-adjusted return >= 1%; không dùng trung bình năm.");
   NTSetCriterion(criteria[7],"C3",fdd.status,"FDD_EVIDENCE","MT5 history không chứa equity lịch sử chính xác; historical result giữ nhãn RECONSTRUCTED/M1/DATA_GAP và không được nâng thành PASS.");
   const NTStatus c4=NTEvaluateC4(weeks,history_complete,qualification_complete);
   NTSetCriterion(criteria[8],"C4",c4,"WEEKLY_SIGNALS","Đếm signal start theo tuần 7 ngày từ thứ Hai kế tiếp (hoặc cùng ngày nếu signal đầu mở thứ Hai); deficient manual-pause week là NOT_VERIFIABLE; PASS chỉ khi horizon và coverage hoàn tất.");
   NTC5Occurrence c5_occurrences[];
   const int current_month=(program_start>0 ? NTTradingMonthIndex(now_server,program_start) : -1);
   NTBuildC5Occurrences(episodes,-1,c5_occurrences);
   NTSetCriterion(criteria[9],"C5",NTEvaluateC5(episodes,history_complete,qualification_complete),"PRODUCT_SESSION_LIMIT","Tối đa một signal cho mỗi canonical symbol trong một session occurrence; mỗi extra signal là một violation occurrence độc lập.");
   const bool c6_evidence_coverage=history_complete && NTC6EvidenceCoverageComplete(episodes);
   NTSetCriterion(criteria[10],"C6",NTEvaluateC6(episodes,c6_evidence_coverage,qualification_complete),"HOLD_OR_SLTP","C6 chỉ FAIL khi đóng dưới 15 phút VÀ complete observed timeline chứng minh không có SL/TP >30 pip; historical timeline thiếu => NOT_VERIFIABLE.");
   NTSetCriterion(criteria[11],"C7",NTEvaluateC7(episodes,now_server*1000L,history_complete,qualification_complete),"HEDGE_DCA","Opposite exposure đồng thời là CONFIRMED_HEDGING; mỗi additional entry khác opening order có evidence timestamp/ticket riêng.");
   NTSetCriterion(criteria[12],"C8",NT_NOT_VERIFIABLE,"COPY_NOT_PROVABLE","MT5 history không chứng minh tín hiệu có bị copy từ nguồn khác; magic/comment chỉ có thể tạo candidate.");
   NTSetCriterion(criteria[13],"C9",NTEvaluateC9(cashflows,history_complete,qualification_complete),"ACCOUNT_CASH_FLOW","Chỉ balance operation có evidence rõ deposit/withdrawal mới là vi phạm; absence chỉ PASS khi coverage và qualification horizon hoàn tất.");

   NTJsonEvent hard_events[],candidate_events[];
   for(int i=0;i<ArraySize(all_episodes);i++)
     {
      if(!all_episodes[i].expert_open_violation) continue;
      NTAddEvent(hard_events,NTSeconds(all_episodes[i].first_entry_msc),NTEvidenceJson("E1","HARD",NT_FAIL,"EXPERT_OPEN","Lệnh mở được ghi nhận từ MQL5 Expert/Script.",NTSeconds(all_episodes[i].first_entry_msc),all_episodes[i].broker_symbol,all_episodes[i].canonical_symbol,"["+NTJsonQuote(StringFormat("%I64u",all_episodes[i].position_id))+"]","["+NTJsonQuote(StringFormat("%I64u",all_episodes[i].opening_order_ticket))+"]","["+NTJsonQuote(StringFormat("%I64u",all_episodes[i].opening_deal_ticket))+"]","expert","manual","DEAL_REASON/ORDER_REASON","EXACT"));
     }
   for(int i=0;i<ArraySize(episodes);i++)
     {
      const NTStatus c6s=NTEvaluateC6Episode(episodes[i]);
      if(c6s==NT_FAIL)
        {
         NTAddEvent(hard_events,NTSeconds(episodes[i].final_close_msc),NTEvidenceJson("C6","HARD",NT_FAIL,"SHORT_NO_QUALIFYING_SLTP","Signal đóng dưới 15 phút và complete observed timeline không có SL/TP vượt 30 pip.",NTSeconds(episodes[i].final_close_msc),episodes[i].broker_symbol,episodes[i].canonical_symbol,"["+NTJsonQuote(StringFormat("%I64u",episodes[i].position_id))+"]","["+NTJsonQuote(StringFormat("%I64u",episodes[i].opening_order_ticket))+"]",NTEpisodeDealTicketsJson(episodes[i]),DoubleToString(episodes[i].holding_seconds,0)+"s; maxSLTP="+DoubleToString(episodes[i].max_sltp_distance_pips,2)+"pip; pipSize="+DoubleToString(episodes[i].pip_size,8)+"; pipSource="+episodes[i].pip_size_source,"900s OR >30pip","PROSPECTIVE_SLTP_JOURNAL","EXACT"));
        }
      else if(c6s==NT_NOT_VERIFIABLE)
        {
         NTAddEvent(candidate_events,NTSeconds(episodes[i].final_close_msc),NTEvidenceJson("C6","RISK",NT_NOT_VERIFIABLE,"SLTP_TIMELINE_MISSING","Signal ngắn nhưng MT5 history không chứng minh toàn bộ lịch sử sửa SL/TP; không được kết luận FAIL.",NTSeconds(episodes[i].final_close_msc),episodes[i].broker_symbol,episodes[i].canonical_symbol,"["+NTJsonQuote(StringFormat("%I64u",episodes[i].position_id))+"]","["+NTJsonQuote(StringFormat("%I64u",episodes[i].opening_order_ticket))+"]",NTEpisodeDealTicketsJson(episodes[i]),DoubleToString(episodes[i].holding_seconds,0)+"s; maxObserved="+DoubleToString(episodes[i].max_sltp_distance_pips,2)+"pip","900s OR >30pip","MT5_HISTORY","PARTIAL_SLTP_EVIDENCE"));
        }
      for(int a=0;a<ArraySize(episodes[i].additional_entries);a++)
        {
         const NTAdditionalEntryEvidence added=episodes[i].additional_entries[a];
         const string reason=added.adverse?"DCA_CANDIDATE":"SCALE_IN_CANDIDATE";
         const string measured="addedVolume="+DoubleToString(added.volume,2)+"; price="+DoubleToString(added.price,8)+"; previousWeighted="+DoubleToString(added.previous_weighted_price,8)+"; newWeighted="+DoubleToString(added.new_weighted_price,8)+"; adverse="+(added.adverse?"true":"false");
         NTAddEvent(candidate_events,NTSeconds(added.time_msc),NTEvidenceJson("C7","RISK",NT_NOT_VERIFIABLE,reason,added.adverse?"Entry cùng chiều mới trước khi flat tại mức giá bất lợi; đây là DCA candidate, không phải kết luận intent.":"Entry cùng chiều mới trước khi flat; đây là scale-in candidate và không phải partial fill cùng opening order.",NTSeconds(added.time_msc),episodes[i].broker_symbol,episodes[i].canonical_symbol,"["+NTJsonQuote(StringFormat("%I64u",episodes[i].position_id))+"]","["+NTJsonQuote(StringFormat("%I64u",added.order_ticket))+"]","["+NTJsonQuote(StringFormat("%I64u",added.deal_ticket))+"]",measured,"no DCA/hedging","MT5_POSITION_LIFECYCLE","CANDIDATE"));
        }
      if(episodes[i].session==NT_OUTSIDE_SESSION)
        {
         NTAddEvent(candidate_events,NTSeconds(episodes[i].first_entry_msc),NTEvidenceJson("C5","RISK",NT_NOT_VERIFIABLE,"OUTSIDE_SESSION","Signal mở ngoài mọi session NeoTech đã định nghĩa; hệ thống không gán vào session khác.",NTSeconds(episodes[i].first_entry_msc),episodes[i].broker_symbol,episodes[i].canonical_symbol,"["+NTJsonQuote(StringFormat("%I64u",episodes[i].position_id))+"]","["+NTJsonQuote(StringFormat("%I64u",episodes[i].opening_order_ticket))+"]",NTEpisodeDealTicketsJson(episodes[i]),"OUTSIDE_SESSION","Asia/Europe/US","RULESET_SESSION_MAP","EXACT"));
        }
      if(episodes[i].opening_magic!=0 || StringFind(NTLower(episodes[i].opening_comment),"copy")>=0)
        {
         NTAddEvent(candidate_events,NTSeconds(episodes[i].first_entry_msc),NTEvidenceJson("C8","RISK",NT_NOT_VERIFIABLE,"COPY_CANDIDATE","Magic/comment có dấu hiệu tự động hóa hoặc copy nhưng MT5 không chứng minh nguồn tín hiệu; C8 vẫn NOT_VERIFIABLE.",NTSeconds(episodes[i].first_entry_msc),episodes[i].broker_symbol,episodes[i].canonical_symbol,"["+NTJsonQuote(StringFormat("%I64u",episodes[i].position_id))+"]","["+NTJsonQuote(StringFormat("%I64u",episodes[i].opening_order_ticket))+"]",NTEpisodeDealTicketsJson(episodes[i]),StringFormat("magic=%I64d comment=%s",episodes[i].opening_magic,episodes[i].opening_comment),"external source proof","MT5_MAGIC_COMMENT","CANDIDATE"));
        }
     }

   for(int i=0;i<ArraySize(all_episodes);i++)
     {
      if(all_episodes[i].product_eligible) continue;
      const long t=NTSeconds(all_episodes[i].first_entry_msc);
      if(!all_episodes[i].product_classification_reliable)
        {
         NTAddEvent(candidate_events,t,NTEvidenceJson("E5","RISK",NT_DATA_GAP,"PRODUCT_METADATA_MISSING","Không đủ symbol metadata để xác minh sản phẩm là Forex/Gold hay ngoài phạm vi.",t,all_episodes[i].broker_symbol,all_episodes[i].canonical_symbol,"["+NTJsonQuote(StringFormat("%I64u",all_episodes[i].position_id))+"]","["+NTJsonQuote(StringFormat("%I64u",all_episodes[i].opening_order_ticket))+"]",NTEpisodeDealTicketsJson(all_episodes[i]),all_episodes[i].broker_symbol,"Forex or Gold","SYMBOL_METADATA","DATA_GAP"));
         continue;
        }
      NTAddEvent(hard_events,t,NTEvidenceJson("E5","HARD",NT_FAIL,"EXCLUDED_PRODUCT","Phát hiện giao dịch ngoài Forex/Gold trong thời gian tham gia; trade đầu tiên cũng có thể thiết lập program start.",t,all_episodes[i].broker_symbol,all_episodes[i].canonical_symbol,"["+NTJsonQuote(StringFormat("%I64u",all_episodes[i].position_id))+"]","["+NTJsonQuote(StringFormat("%I64u",all_episodes[i].opening_order_ticket))+"]",NTEpisodeDealTicketsJson(all_episodes[i]),all_episodes[i].broker_symbol,"Forex or Gold","SYMBOL_METADATA","EXACT"));
     }

   for(int i=0;i<ArraySize(c5_occurrences);i++)
     {
      const NTC5Occurrence occurrence=c5_occurrences[i];
      const long event_time=NTSeconds(occurrence.time_msc);
      const string measured="occurrence="+IntegerToString(occurrence.occurrence_number)+"; session="+NTSessionName(occurrence.session);
      NTAddEvent(hard_events,event_time,NTEvidenceJson("C5","HARD",NT_FAIL,"MULTIPLE_SIGNALS_PRODUCT_SESSION","Mở thêm tín hiệu cho cùng sản phẩm trong cùng phiên; mỗi tín hiệu vượt quá tín hiệu đầu tiên là một occurrence riêng.",event_time,occurrence.broker_symbol,occurrence.canonical_symbol,"["+NTJsonQuote(StringFormat("%I64u",occurrence.position_id))+"]","["+NTJsonQuote(StringFormat("%I64u",occurrence.order_ticket))+"]","["+NTJsonQuote(StringFormat("%I64u",occurrence.deal_ticket))+"]",measured,"max 1 signal/product/session","RULESET_SESSION_MAP","EXACT"));
     }

   NTHedgingEvidence hedge_events[];
   NTBuildHedgingEvidence(episodes,now_server*1000L,hedge_events);
   for(int i=0;i<ArraySize(hedge_events);i++)
     {
      const NTHedgingEvidence hedge=hedge_events[i];
      const long event_time=NTSeconds(hedge.overlap_start_msc);
      const string positions="["+NTJsonQuote(StringFormat("%I64u",hedge.first_position_id))+","+NTJsonQuote(StringFormat("%I64u",hedge.second_position_id))+"]";
      const string orders="["+NTJsonQuote(StringFormat("%I64u",hedge.first_order_ticket))+","+NTJsonQuote(StringFormat("%I64u",hedge.second_order_ticket))+"]";
      const string deals_json="["+NTJsonQuote(StringFormat("%I64u",hedge.first_deal_ticket))+","+NTJsonQuote(StringFormat("%I64u",hedge.second_deal_ticket))+"]";
      const string measured="directions="+(hedge.first_direction>0?"BUY":"SELL")+"/"+(hedge.second_direction>0?"BUY":"SELL")+"; overlap="+NTDateTimeText(NTSeconds(hedge.overlap_start_msc))+" -> "+NTDateTimeText(NTSeconds(hedge.overlap_end_msc));
      NTAddEvent(hard_events,event_time,NTEvidenceJson("C7","HARD",NT_FAIL,"CONFIRMED_HEDGING","Có exposure BUY và SELL đồng thời trên cùng canonical symbol với position ID khác nhau.",event_time,hedge.broker_symbol,hedge.canonical_symbol,positions,orders,deals_json,measured,"no simultaneous opposite exposure","MT5_POSITION_LIFECYCLE","EXACT"));
     }

   for(int i=0;i<ArraySize(cashflows);i++)
     {
      if(cashflows[i].kind!=1 && cashflows[i].kind!=-1) continue;
      NTAddEvent(hard_events,NTSeconds(cashflows[i].time_msc),NTEvidenceJson("C9","HARD",NT_FAIL,cashflows[i].kind==1?"DEPOSIT":"WITHDRAWAL",cashflows[i].kind==1?"Phát hiện khoản nạp tiền có evidence rõ trong balance operation.":"Phát hiện khoản rút tiền có evidence rõ trong balance operation.",NTSeconds(cashflows[i].time_msc),"","","[]","[]","["+NTJsonQuote(StringFormat("%I64u",cashflows[i].ticket))+"]",DoubleToString(cashflows[i].amount,2),"0",cashflows[i].comment,"EXACT"));
     }
   const int hard_count=ArraySize(hard_events);
   const int candidate_count=ArraySize(candidate_events);
   const string hard=NTEventsJson(hard_events);
   const string candidates=NTEventsJson(candidate_events);

   const int c5_current=(current_month>=0 ? NTCountC5ConfirmedViolations(episodes,current_month) : 0);
   const int c6_current=(current_month>=0 ? NTCountC6ConfirmedViolations(episodes,current_month) : 0);
   const int combined=c5_current+c6_current;
   const bool counters_complete=criteria[9].status!=NT_NOT_VERIFIABLE && criteria[10].status!=NT_NOT_VERIFIABLE && criteria[9].status!=NT_DATA_GAP && criteria[10].status!=NT_DATA_GAP;
   const int risk_code=NTDisqualificationRisk(c5_current,c6_current,counters_complete);
   const string risk=(risk_code>0?"YES":(risk_code==0?"NO":"UNKNOWN"));

   string criteria_json="[";
   for(int i=0;i<ArraySize(criteria);i++)
     {
      if(i>0) criteria_json+=",";
      criteria_json+=NTCriterionJson(criteria[i]);
     }
   criteria_json+="]";

   string assumptions[];
   ArrayResize(assumptions,8);
   assumptions[0]="C1 strict policy="+string(NT_C1_STRICT_POLICY)+": both 365 calendar days and 12 completed 30-day windows are required.";
   assumptions[1]="NeoTech server session season is April-October summer, November-March winter; overlaps use half-open ranges with Asia->Europe->US priority.";
   assumptions[2]="Configured C3 compliance interpretation is floating loss=(balance-equity)/balance; peak-to-trough equity drawdown is also reported separately.";
   assumptions[3]="Historical C3 is reconstructed from broker ticks in bounded chunks, with M1 fallback; it never becomes unconditional PASS.";
   assumptions[4]="Historical SL/TP modifications are not fully reconstructable from MT5 history; short signals without qualifying observed snapshots remain NOT_VERIFIABLE unless complete timeline evidence exists.";
   assumptions[5]="Gold pip size is not assumed. C6 distance for Gold requires InpGoldPipSizeOverride > 0.";
   assumptions[6]="E4 and C8 have no authoritative external integration in this repository and therefore default to NOT_VERIFIABLE.";
   assumptions[7]="Manual pause periods are MANUAL_DECLARATION; affected deficient weeks are shown and become NOT_VERIFIABLE rather than silently removed.";

   const string fdd_gaps=NTStringArrayJson(fdd.missing_intervals);
   const string margin_mode=(AccountInfoInteger(ACCOUNT_MARGIN_MODE)==ACCOUNT_MARGIN_MODE_RETAIL_HEDGING?"HEDGING":"NETTING");
   const string account_fingerprint=NTAccountFingerprint();
   string core="{\"schemaVersion\":"+NTJsonQuote(NT_SCHEMA_VERSION);
   core+=",\"ruleset\":{\"id\":"+NTJsonQuote(NT_RULESET_ID)+",\"sourceUrl\":"+NTJsonQuote(NT_SOURCE_URL)+",\"articleDate\":"+NTJsonQuote(NT_ARTICLE_DATE)+",\"retrievalDate\":"+NTJsonQuote(NT_RETRIEVAL_DATE)+"}";
   core+=",\"profileSlug\":"+NTJsonQuote(NTProfileKey());
   core+=",\"account\":{\"maskedId\":"+NTJsonQuote(NTMaskedAccount((long)AccountInfoInteger(ACCOUNT_LOGIN)));
   core+=",\"fingerprint\":"+NTJsonQuote(account_fingerprint);
   core+=",\"broker\":"+NTJsonQuote(AccountInfoString(ACCOUNT_COMPANY));
   core+=",\"server\":"+NTJsonQuote(AccountInfoString(ACCOUNT_SERVER));
   core+=",\"mode\":"+NTJsonQuote(margin_mode)+",\"currency\":"+NTJsonQuote(AccountInfoString(ACCOUNT_CURRENCY))+"}";
   core+=",\"generatedAtUtc\":"+IntegerToString(now_utc);
   core+=",\"programStartServerEpoch\":"+NTJsonLongOrNull(program_start)+",\"programStartTime\":"+NTTimePointJson(program_start);
   core+=",\"historyCoverage\":{\"requestedStartServerEpoch\":"+IntegerToString(coverage.requested_start)+",\"requestedEndServerEpoch\":"+IntegerToString(coverage.requested_end);
   core+=",\"requestedStartTime\":"+NTTimePointJson(coverage.requested_start)+",\"requestedEndTime\":"+NTTimePointJson(coverage.requested_end);
   core+=",\"earliestDealServerEpoch\":"+NTJsonLongOrNull(coverage.earliest_deal)+",\"earliestOrderServerEpoch\":"+NTJsonLongOrNull(coverage.earliest_order)+",\"usableStartServerEpoch\":"+NTJsonLongOrNull(coverage.usable_start);
   core+=",\"dealCoveragePct\":"+NTJsonNumber(coverage.deal_coverage_pct,3)+",\"orderCoveragePct\":"+NTJsonNumber(coverage.order_coverage_pct,3)+",\"coveragePct\":"+NTJsonNumber(coverage.coverage_pct,3);
   core+=",\"dealCoverageComplete\":"+NTJsonBool(coverage.deal_coverage_complete)+",\"orderCoverageComplete\":"+NTJsonBool(coverage.order_coverage_complete)+",\"jointHistoryComplete\":"+NTJsonBool(coverage.joint_history_complete)+",\"missingRanges\":"+NTStringArrayJson(coverage.missing_ranges)+"}";
   core+=",\"summary\":{\"eligibility\":{\"pass\":"+IntegerToString(NTCountEligibility(criteria,NT_PASS))+",\"fail\":"+IntegerToString(NTCountEligibility(criteria,NT_FAIL))+",\"unknown\":"+IntegerToString(NTCountEligibility(criteria,NT_PASS,true))+"}";
   core+=",\"awards\":{\"pass\":"+IntegerToString(NTCountAwards(criteria,NT_PASS))+",\"fail\":"+IntegerToString(NTCountAwards(criteria,NT_FAIL))+",\"inProgress\":"+IntegerToString(NTCountAwards(criteria,NT_IN_PROGRESS))+",\"unknown\":"+IntegerToString(NTCountAwards(criteria,NT_PASS,true))+"}";
   core+=",\"hardViolationCount\":"+IntegerToString(hard_count)+",\"candidateCount\":"+IntegerToString(candidate_count);
   core+=",\"currentMonth\":{\"c5\":"+IntegerToString(c5_current)+",\"c6\":"+IntegerToString(c6_current)+",\"combined\":"+IntegerToString(combined)+",\"risk\":"+NTJsonQuote(risk)+"}";
   core+=",\"fdd\":{\"maxFloatingLossPct\":"+NTJsonNumber(fdd.max_floating_loss_pct,6)+",\"maxPeakToTroughPct\":"+NTJsonNumber(fdd.max_peak_to_trough_pct,6)+",\"eventTime\":"+NTTimePointJson(fdd.event_server_time);
   core+=",\"balanceAtEvent\":"+NTJsonNumber(fdd.balance_at_event,2)+",\"equityAtEvent\":"+NTJsonNumber(fdd.equity_at_event,2)+",\"contributingPositionIds\":"+NTJsonStringArray(fdd.contributing_position_ids)+",\"contributingSymbols\":"+NTJsonStringArray(fdd.contributing_symbols);
   core+=",\"method\":"+NTJsonQuote(fdd.method)+",\"status\":"+NTJsonQuote(NTStatusName(fdd.status))+",\"tickCoveragePct\":"+NTJsonNumber(fdd.tick_coverage_pct,3)+",\"barCoveragePct\":"+NTJsonNumber(fdd.bar_coverage_pct,3)+"}}";
   core+=",\"criteria\":"+criteria_json;
   core+=",\"months\":"+NTMonthsJson(months)+",\"weeks\":"+NTWeeksJson(weeks)+",\"sessionSignalCounts\":"+NTSessionCountsJson(episodes);
   core+=",\"hardViolations\":"+hard+",\"candidates\":"+candidates;
   core+=",\"dataGaps\":[{\"history\":"+NTStringArrayJson(coverage.missing_ranges)+",\"fdd\":"+fdd_gaps+",\"tickCoveragePct\":"+NTJsonNumber(fdd.tick_coverage_pct,3)+",\"barCoveragePct\":"+NTJsonNumber(fdd.bar_coverage_pct,3)+"}]";
   core+=",\"assumptions\":"+NTJsonStringArray(assumptions)+"}";
   report_hash=NTSha256Hex(core);
   return report_hash=="" ? "" : core;
  }

bool NTTelegramHasConfiguredId(const string specification)
  {
   string normalized=specification;
   StringReplace(normalized,";",",");
   StringReplace(normalized,"\n",",");
   StringReplace(normalized,"\r",",");
   StringReplace(normalized,"\t",",");
   StringReplace(normalized," ",",");
   string parts[];
   const int count=StringSplit(normalized,',',parts);
   for(int i=0;i<count;i++) if(NTIsSignedIntegerText(NTTrim(parts[i]))) return true;
   return false;
  }

void NTTelegramLoadLocalState()
  {
   string text="";
   if(NTReadCommonText(NTTelegramOffsetPath(),text) && NTIsSignedIntegerText(NTTrim(text)))
     {
      const long value=StringToInteger(NTTrim(text));
      if(value>=0) g_telegram_next_update_id=value;
     }
   text="";
   if(NTReadCommonText(NTTelegramNotifyPath(),text)) g_telegram_last_notified_hash=NTTrim(text);
   g_cached_report_json="";
   if(NTReadCommonText(NTReportPath(),g_cached_report_json) && g_cached_report_json!="")
      g_last_report_hash=NTSha256Hex(g_cached_report_json);
  }

bool NTTelegramPersistOffset(const long processed_update_id)
  {
   const long next=NTTelegramNextOffset(g_telegram_next_update_id,processed_update_id);
   if(next==g_telegram_next_update_id) return true;
   if(!NTWriteCommonText(NTTelegramOffsetPath(),IntegerToString(next)))
     {
      Print("[NEOTECH] Telegram update handled but offset persistence failed; polling paused to avoid unsafe replay advancement.");
      g_telegram_polling_enabled=false;
      return false;
     }
   g_telegram_next_update_id=next;
   return true;
  }

int NTTelegramBackoffSeconds()
  {
   int delay=5;
   const int steps=MathMin(5,MathMax(0,g_telegram_failure_count-1));
   for(int i=0;i<steps;i++) delay*=2;
   return MathMin(300,delay);
  }

void NTTelegramRecordFailure(const string method,const int http_code,const int terminal_error)
  {
   g_telegram_failure_count++;
   const int delay=NTTelegramBackoffSeconds();
   g_telegram_next_attempt=(long)TimeLocal()+delay;
   if(http_code<0 && terminal_error==4014)
      PrintFormat("[NEOTECH] Telegram %s blocked by MT5 WebRequest policy (err=%d). Add https://api.telegram.org to Tools > Options > Expert Advisors > Allow WebRequest for listed URL; retry in %d seconds.",method,terminal_error,delay);
   else
      PrintFormat("[NEOTECH] Telegram %s failed HTTP=%d err=%d; retry in %d seconds.",method,http_code,terminal_error,delay);
  }

void NTTelegramRecordSuccess()
  {
   g_telegram_failure_count=0;
   g_telegram_next_attempt=0;
  }

bool NTTelegramBackoffActive()
  {
   return g_telegram_next_attempt>(long)TimeLocal();
  }

bool NTTelegramApiCall(const string method,const string fields,string &response_text,int &http_code)
  {
   response_text="";
   http_code=-1;
   if(NTTrim(InpTelegramBotToken)=="" || NTTelegramBackoffActive()) return false;
   const string url=NT_TELEGRAM_API_BASE+"/bot"+InpTelegramBotToken+"/"+method;
   const string headers="Content-Type: application/x-www-form-urlencoded\r\n";
   char body[],response[];
   if(fields!="")
     {
      StringToCharArray(fields,body,0,-1,CP_UTF8);
      if(ArraySize(body)>0 && body[ArraySize(body)-1]==0) ArrayResize(body,ArraySize(body)-1);
     }
   else ArrayResize(body,0);
   string response_headers="";
   ResetLastError();
   http_code=WebRequest("POST",url,headers,NT_TELEGRAM_HTTP_TIMEOUT_MS,body,response,response_headers);
   const int terminal_error=GetLastError();
   if(ArraySize(response)>0) response_text=CharArrayToString(response,0,-1,CP_UTF8);
   if(http_code!=200 || !NTTelegramApiOk(response_text))
     {
      NTTelegramRecordFailure(method,http_code,terminal_error);
      return false;
     }
   NTTelegramRecordSuccess();
   return true;
  }

bool NTTelegramConfigurePolling()
  {
   if(g_telegram_webhook_blocked) return false;
   string response="";
   int http_code=-1;
   if(!NTTelegramApiCall("getWebhookInfo","",response,http_code)) return false;
   NTTelegramWebhookAction action=NTTelegramWebhookDecision(response,InpTelegramDeleteWebhookOnInit);
   if(action==NT_TG_WEBHOOK_ERROR)
     {
      NTTelegramRecordFailure("getWebhookInfo-parse",http_code,0);
      return false;
     }
   if(action==NT_TG_WEBHOOK_BLOCK)
     {
      g_telegram_polling_enabled=false;
      g_telegram_webhook_blocked=true;
      Print("[NEOTECH] Telegram polling disabled: getWebhookInfo reports an active webhook. InpTelegramDeleteWebhookOnInit=false preserves it. To let this EA poll, set InpTelegramDeleteWebhookOnInit=true and reinitialize, or delete the webhook externally; this EA will not delete it automatically.");
      return false;
     }
   if(action==NT_TG_WEBHOOK_DELETE)
     {
      if(!NTTelegramApiCall("deleteWebhook","drop_pending_updates=false",response,http_code)) return false;
      if(!NTTelegramApiCall("getWebhookInfo","",response,http_code)) return false;
      if(NTTelegramWebhookDecision(response,false)!=NT_TG_WEBHOOK_READY)
        {
         NTTelegramRecordFailure("getWebhookInfo-confirm",http_code,0);
         Print("[NEOTECH] Telegram webhook deletion was requested but webhook state is not empty; polling remains disabled.");
         return false;
        }
      Print("[NEOTECH] Telegram webhook deleted with drop_pending_updates=false and confirmed empty; polling enabled.");
     }
   g_telegram_polling_enabled=true;
   return true;
  }

string NTTelegramJsonRaw(const string json,const string key)
  {
   string raw="";
   NTJsonReadRawValue(json,key,raw);
   return raw;
  }

void NTTelegramCriterionTotals(const string report,int &pass_count,int &fail_count,int &in_progress_count,int &not_verifiable_count,int &data_gap_count,int &reconstructed_count)
  {
   pass_count=0;
   fail_count=0;
   in_progress_count=0;
   not_verifiable_count=0;
   data_gap_count=0;
   reconstructed_count=0;
   string criteria_json="";
   string criteria[];
   if(!NTJsonGetArray(report,"criteria",criteria_json)) return;
   NTJsonArrayObjects(criteria_json,criteria);
   for(int i=0;i<ArraySize(criteria);i++)
     {
      string status="";
      if(!NTJsonGetString(criteria[i],"status",status)) continue;
      if(status=="PASS") pass_count++;
      else if(status=="FAIL") fail_count++;
      else if(status=="IN_PROGRESS") in_progress_count++;
      else if(status=="NOT_VERIFIABLE") not_verifiable_count++;
      else if(status=="DATA_GAP") data_gap_count++;
      else if(status=="RECONSTRUCTED") reconstructed_count++;
     }
  }

string NTTelegramSafeText(const string text)
  {
   return NTTelegramRedact(text,
      IntegerToString((long)AccountInfoInteger(ACCOUNT_LOGIN)),
      AccountInfoString(ACCOUNT_COMPANY),
      AccountInfoString(ACCOUNT_SERVER),
      InpTelegramBotToken);
  }

string NTTelegramSummaryHeader(const string report)
  {
   string account="",masked="unknown";
   if(NTJsonGetObject(report,"account",account)) NTJsonGetString(account,"maskedId",masked);

   string coverage="";
   long requested_start=0,requested_end=0;
   double coverage_pct=0.0;
   if(NTJsonGetObject(report,"historyCoverage",coverage))
     {
      NTJsonGetLong(coverage,"requestedStartServerEpoch",requested_start);
      NTJsonGetLong(coverage,"requestedEndServerEpoch",requested_end);
      NTJsonGetDouble(coverage,"coveragePct",coverage_pct);
     }

   int pass_count=0,fail_count=0,in_progress_count=0,not_verifiable_count=0,data_gap_count=0,reconstructed_count=0;
   NTTelegramCriterionTotals(report,pass_count,fail_count,in_progress_count,not_verifiable_count,data_gap_count,reconstructed_count);

   string summary="",current_month="",fdd="";
   long hard_count=0,candidate_count=0,c5=0,c6=0;
   string risk="UNKNOWN";
   double fdd_floating=0.0,fdd_peak=0.0,fdd_tick=0.0,fdd_bar=0.0;
   string fdd_method="unknown",fdd_status="NOT_VERIFIABLE";
   if(NTJsonGetObject(report,"summary",summary))
     {
      NTJsonGetLong(summary,"hardViolationCount",hard_count);
      NTJsonGetLong(summary,"candidateCount",candidate_count);
      if(NTJsonGetObject(summary,"currentMonth",current_month))
        {
         NTJsonGetLong(current_month,"c5",c5);
         NTJsonGetLong(current_month,"c6",c6);
         NTJsonGetString(current_month,"risk",risk);
        }
      if(NTJsonGetObject(summary,"fdd",fdd))
        {
         NTJsonGetDouble(fdd,"maxFloatingLossPct",fdd_floating);
         NTJsonGetDouble(fdd,"maxPeakToTroughPct",fdd_peak);
         NTJsonGetDouble(fdd,"tickCoveragePct",fdd_tick);
         NTJsonGetDouble(fdd,"barCoveragePct",fdd_bar);
         NTJsonGetString(fdd,"method",fdd_method);
         NTJsonGetString(fdd,"status",fdd_status);
        }
     }

   string history_text="n/a";
   if(requested_start>0 && requested_end>0) history_text=NTDateTimeText(requested_start)+" -> "+NTDateTimeText(requested_end)+" (server time)";
   string text="NeoTech compliance @"+NTProfileKey();
   text+="\nAccount: "+masked;
   text+="\nHistory: "+history_text;
   text+="\nCoverage: "+DoubleToString(coverage_pct,1)+"%";
   text+="\nCriteria: PASS="+IntegerToString(pass_count)+" FAIL="+IntegerToString(fail_count)+" IN_PROGRESS="+IntegerToString(in_progress_count)+" NOT_VERIFIABLE="+IntegerToString(not_verifiable_count)+" DATA_GAP="+IntegerToString(data_gap_count);
   if(reconstructed_count>0) text+=" RECONSTRUCTED="+IntegerToString(reconstructed_count);
   text+="\nViolations: confirmed="+IntegerToString(hard_count)+" candidates="+IntegerToString(candidate_count);
   text+="\nCurrent month: C5="+IntegerToString(c5)+" C6="+IntegerToString(c6)+" eliminationRisk="+risk;
   text+="\nFDD: floating="+DoubleToString(fdd_floating,3)+"% peakToTrough="+DoubleToString(fdd_peak,3)+"% status="+fdd_status;
   text+="\nFDD method/coverage: "+fdd_method+"; ticks="+DoubleToString(fdd_tick,1)+"% M1="+DoubleToString(fdd_bar,1)+"%";
   return NTTelegramSafeText(text);
  }

string NTTelegramCriterionItem(const string criterion)
  {
   string id="?",status="?",summary="";
   NTJsonGetString(criterion,"id",id);
   NTJsonGetString(criterion,"status",status);
   NTJsonGetString(criterion,"summaryVi",summary);
   return NTTelegramSafeText(id+" · "+status+(summary!=""?"\n"+summary:""));
  }

string NTTelegramEvidenceItem(const string event_json,const bool candidate)
  {
   string criterion="?",status="?",reason="?",explanation="",server_time="n/a",utc_time="n/a",symbol="n/a",measured="n/a",threshold="n/a";
   NTJsonGetString(event_json,"criterionId",criterion);
   NTJsonGetString(event_json,"status",status);
   NTJsonGetString(event_json,"reasonCode",reason);
   NTJsonGetString(event_json,"explanationVi",explanation);
   NTJsonGetString(event_json,"serverTime",server_time);
   NTJsonGetString(event_json,"utcTime",utc_time);
   NTJsonGetString(event_json,"canonicalSymbol",symbol);
   NTJsonGetString(event_json,"measuredValue",measured);
   NTJsonGetString(event_json,"threshold",threshold);
   const string positions=NTTelegramJsonRaw(event_json,"positionIds");
   const string orders=NTTelegramJsonRaw(event_json,"orderTickets");
   const string deals=NTTelegramJsonRaw(event_json,"dealTickets");
   string text=(candidate?"CANDIDATE ":"VIOLATION ")+criterion+" · "+status+" · "+reason;
   text+="\nServer: "+server_time+" | UTC: "+utc_time;
   text+="\nSymbol: "+symbol;
   if(explanation!="") text+="\nReason: "+explanation;
   text+="\nMeasured: "+measured+" | Threshold: "+threshold;
   text+="\nPosition: "+(positions!=""?positions:"[]")+" | Order: "+(orders!=""?orders:"[]")+" | Deal: "+(deals!=""?deals:"[]");
   return NTTelegramSafeText(text);
  }

void NTTelegramAppendItem(string &items[],const string item)
  {
   const int n=ArraySize(items);
   ArrayResize(items,n+1);
   items[n]=item;
  }

void NTTelegramAppendEvidenceItems(const string report,const string array_key,const string criterion_filter,const bool candidate,string &items[])
  {
   string array_json="";
   string events[];
   if(!NTJsonGetArray(report,array_key,array_json)) return;
   NTJsonArrayObjects(array_json,events);
   for(int i=0;i<ArraySize(events);i++)
     {
      string criterion="";
      if(!NTJsonGetString(events[i],"criterionId",criterion)) continue;
      if(criterion_filter!="" && !NTTelegramCriterionMatches(criterion,criterion_filter)) continue;
      NTTelegramAppendItem(items,NTTelegramEvidenceItem(events[i],candidate));
     }
  }

int NTTelegramBuildReportPages(const string report,const NTTelegramCheckCommand &command,string &pages[])
  {
   ArrayResize(pages,0);
   if(report=="") return 0;
   string items[];
   ArrayResize(items,0);

   if(command.view==NT_TG_VIEW_VIOLATIONS)
     {
      NTTelegramAppendEvidenceItems(report,"hardViolations","",false,items);
      NTTelegramAppendEvidenceItems(report,"candidates","",true,items);
      if(ArraySize(items)==0) NTTelegramAppendItem(items,"No confirmed violations or candidates in the current report.");
     }
   else
     {
      string criteria_json="";
      string criteria[];
      if(NTJsonGetArray(report,"criteria",criteria_json)) NTJsonArrayObjects(criteria_json,criteria);
      for(int i=0;i<ArraySize(criteria);i++)
        {
         string id="";
         if(!NTJsonGetString(criteria[i],"id",id)) continue;
         if(command.view==NT_TG_VIEW_CRITERION && !NTTelegramCriterionMatches(id,command.criterion)) continue;
         NTTelegramAppendItem(items,NTTelegramCriterionItem(criteria[i]));
        }
      if(command.view==NT_TG_VIEW_CRITERION)
        {
         NTTelegramAppendEvidenceItems(report,"hardViolations",command.criterion,false,items);
         NTTelegramAppendEvidenceItems(report,"candidates",command.criterion,true,items);
         if(ArraySize(items)==0) NTTelegramAppendItem(items,"Criterion not found in the current report.");
        }
     }

   const string header=NTTelegramSummaryHeader(report);
   NTTelegramPaginateItems(header,items,MathMax(1,InpTelegramPageSize),NT_TELEGRAM_MESSAGE_BUDGET,pages);
   const int total=ArraySize(pages);
   for(int i=0;i<total;i++) pages[i]+="\n\nPage "+IntegerToString(i+1)+"/"+IntegerToString(total);
   return total;
  }

string NTTelegramInlineKeyboard(const NTTelegramCheckCommand &command,const int current_page,const int total_pages)
  {
   if(total_pages<=1) return "";
   string buttons="";
   if(current_page>1)
     {
      const string data=NTTelegramCallbackData(NTProfileKey(),command.view,command.criterion,current_page-1);
      buttons+="{\"text\":\"Prev\",\"callback_data\":"+NTJsonQuote(data)+"}";
     }
   if(current_page<total_pages)
     {
      if(buttons!="") buttons+=",";
      const string data=NTTelegramCallbackData(NTProfileKey(),command.view,command.criterion,current_page+1);
      buttons+="{\"text\":\"Next\",\"callback_data\":"+NTJsonQuote(data)+"}";
     }
   if(buttons=="") return "";
   return "{\"inline_keyboard\":[["+buttons+"]]}";
  }

bool NTTelegramSendMessage(const long chat_id,const string text,const string reply_markup="")
  {
   if(text=="" || StringLen(text)>4096) return false;
   string fields="chat_id="+NTUrlEncodeUtf8(IntegerToString(chat_id))+"&text="+NTUrlEncodeUtf8(text);
   if(reply_markup!="") fields+="&reply_markup="+NTUrlEncodeUtf8(reply_markup);
   string response="";
   int http_code=-1;
   return NTTelegramApiCall("sendMessage",fields,response,http_code);
  }

bool NTTelegramAnswerCallback(const string callback_id,const string text="")
  {
   if(callback_id=="") return false;
   string fields="callback_query_id="+NTUrlEncodeUtf8(callback_id);
   if(text!="") fields+="&text="+NTUrlEncodeUtf8(text);
   string response="";
   int http_code=-1;
   return NTTelegramApiCall("answerCallbackQuery",fields,response,http_code);
  }

bool NTTelegramSendReport(const long chat_id,NTTelegramCheckCommand &command)
  {
   if(g_cached_report_json=="") return false;
   string pages[];
   const int total=NTTelegramBuildReportPages(g_cached_report_json,command,pages);
   if(total<=0) return false;
   int page=command.page;
   if(page<1) page=1;
   if(page>total) page=total;
   const string keyboard=NTTelegramInlineKeyboard(command,page,total);
   return NTTelegramSendMessage(chat_id,pages[page-1],keyboard);
  }

bool NTTelegramHandleMessage(const string update_json)
  {
   string message="";
   if(!NTJsonGetObject(update_json,"message",message)) return true;
   string text="";
   if(!NTJsonGetString(message,"text",text)) return true;
   const string lowered=NTLower(NTTrim(text));
   if(StringFind(lowered,"/check")!=0) return true;

   string chat="",from="";
   long chat_id=0,user_id=0;
   if(!NTJsonGetObject(message,"chat",chat) || !NTJsonGetLong(chat,"id",chat_id)) return true;
   if(!NTJsonGetObject(message,"from",from) || !NTJsonGetLong(from,"id",user_id)) return true;
   if(!NTTelegramAclAllowed(InpTelegramAllowedChatIds,InpTelegramAllowedUserIds,chat_id,user_id)) return true;

   NTTelegramCheckCommand command;
   if(!NTTelegramParseCheckCommand(text,NTProfileKey(),command)) return true;
   if(!command.slug_matches) return true;
   return NTTelegramSendReport(chat_id,command);
  }

bool NTTelegramHandleCallback(const string update_json)
  {
   string callback="";
   if(!NTJsonGetObject(update_json,"callback_query",callback)) return true;
   string callback_id="",data="";
   NTJsonGetString(callback,"id",callback_id);
   if(!NTJsonGetString(callback,"data",data)) return true;
   NTTelegramCheckCommand command;
   if(!NTTelegramParseCallbackData(data,NTProfileKey(),command) || !command.slug_matches) return true;

   string from="",message="",chat="";
   long user_id=0,chat_id=0;
   if(!NTJsonGetObject(callback,"from",from) || !NTJsonGetLong(from,"id",user_id)) return true;
   if(!NTJsonGetObject(callback,"message",message) || !NTJsonGetObject(message,"chat",chat) || !NTJsonGetLong(chat,"id",chat_id)) return true;
   if(!NTTelegramAclAllowed(InpTelegramAllowedChatIds,InpTelegramAllowedUserIds,chat_id,user_id))
     {
      NTTelegramAnswerCallback(callback_id,"Unauthorized");
      return true;
     }

   if(!NTTelegramSendReport(chat_id,command)) return false;
   if(!NTTelegramAnswerCallback(callback_id,"Page updated"))
      Print("[NEOTECH] Telegram callback page was delivered but answerCallbackQuery failed; update will not be replayed to avoid duplicate account reports.");
   return true;
  }

bool NTTelegramHandleUpdate(const string update_json)
  {
   string object="";
   if(NTJsonGetObject(update_json,"callback_query",object)) return NTTelegramHandleCallback(update_json);
   if(NTJsonGetObject(update_json,"message",object)) return NTTelegramHandleMessage(update_json);
   return true;
  }

void NTTelegramPollUpdates()
  {
   if(!g_telegram_polling_enabled || NTTelegramBackoffActive()) return;
   const string allowed_updates="[\"message\",\"callback_query\"]";
   string fields="offset="+NTUrlEncodeUtf8(IntegerToString(g_telegram_next_update_id))
      +"&limit=20&timeout=0&allowed_updates="+NTUrlEncodeUtf8(allowed_updates);
   string response="";
   int http_code=-1;
   if(!NTTelegramApiCall("getUpdates",fields,response,http_code)) return;
   string result="";
   string updates[];
   if(!NTJsonGetArray(response,"result",result))
     {
      NTTelegramRecordFailure("getUpdates-parse",http_code,0);
      return;
     }
   NTJsonArrayObjects(result,updates);
   for(int i=0;i<ArraySize(updates);i++)
     {
      long update_id=-1;
      if(!NTJsonGetLong(updates[i],"update_id",update_id) || update_id<0) continue;
      if(!NTTelegramUpdateProcessable(update_id,g_telegram_next_update_id)) continue;
      if(!NTTelegramHandleUpdate(updates[i])) return;
      if(!NTTelegramPersistOffset(update_id)) return;
     }
  }

int NTTelegramAllowedChats(long &ids[])
  {
   ArrayResize(ids,0);
   string normalized=InpTelegramAllowedChatIds;
   StringReplace(normalized,";",",");
   StringReplace(normalized,"\n",",");
   StringReplace(normalized,"\r",",");
   StringReplace(normalized,"\t",",");
   StringReplace(normalized," ",",");
   string parts[];
   const int count=StringSplit(normalized,',',parts);
   for(int i=0;i<count;i++)
     {
      const string part=NTTrim(parts[i]);
      if(!NTIsSignedIntegerText(part)) continue;
      const long id=StringToInteger(part);
      bool duplicate=false;
      for(int j=0;j<ArraySize(ids);j++) if(ids[j]==id) { duplicate=true; break; }
      if(duplicate) continue;
      const int n=ArraySize(ids);
      ArrayResize(ids,n+1);
      ids[n]=id;
     }
   return ArraySize(ids);
  }

void NTTelegramMaybeSendOnChange()
  {
   if(!InpTelegramSendOnChange || g_cached_report_json=="" || g_last_report_hash=="" || g_last_report_hash==g_telegram_last_notified_hash || NTTelegramBackoffActive()) return;
   long chats[];
   if(NTTelegramAllowedChats(chats)<=0) return;
   NTTelegramCheckCommand command;
   command.slug_matches=true;
   command.view=NT_TG_VIEW_SUMMARY;
   command.page=1;
   command.criterion="";
   for(int i=0;i<ArraySize(chats);i++)
      if(!NTTelegramSendReport(chats[i],command)) return;
   if(NTWriteCommonText(NTTelegramNotifyPath(),g_last_report_hash)) g_telegram_last_notified_hash=g_last_report_hash;
  }

bool NTCacheReport(const string report,const string hash)
  {
   if(report=="" || hash=="") return false;
   if(!NTWriteCommonText(NTReportPath(),report)) return false;
   g_cached_report_json=report;
   g_last_report_hash=hash;
   return true;
  }

void NTRefreshReportIfNeeded()
  {
   if(!HistorySelect(0,TimeCurrent())) return;
   const long deals=HistoryDealsTotal();
   const long orders=HistoryOrdersTotal();
   if(g_last_deals>=0 && (deals!=g_last_deals || orders!=g_last_orders)) g_history_dirty=true;
   const long today=NTDayStart((long)TimeCurrent());
   const bool daily=(g_last_reconcile_day==0 || today!=g_last_reconcile_day);
   if(!g_history_dirty && !daily) return;
   string hash="";
   const string report=NTBuildReport(hash);
   if(report=="" || hash=="")
     {
      Print("[NEOTECH] Report generation failed; local cache unchanged.");
      return;
     }
   if(hash!=g_last_report_hash || daily) NTCacheReport(report,hash);
   g_history_dirty=false;
   g_last_reconcile_day=today;
  }

int OnInit()
  {
   const string profile=NTProfileKey();
   if(!NTValidProfileSlug(profile))
     {
      Print("[NEOTECH] InpProfileSlug must be an opaque 6-32 char lowercase slug [a-z0-9_-]");
      return INIT_PARAMETERS_INCORRECT;
     }
   const long current_login=(long)AccountInfoInteger(ACCOUNT_LOGIN);
   if(InpExpectedLogin<=0 || current_login!=InpExpectedLogin)
     {
      Print("[NEOTECH] InpExpectedLogin is required and must match the attached MT5 account; initialization stopped.");
      return INIT_PARAMETERS_INCORRECT;
     }
   if(NTAccountFingerprint()=="")
     {
      Print("[NEOTECH] Account fingerprint generation failed; initialization stopped.");
      return INIT_FAILED;
     }
   if(NTTrim(InpTelegramBotToken)=="" || !NTTelegramHasConfiguredId(InpTelegramAllowedChatIds) || !NTTelegramHasConfiguredId(InpTelegramAllowedUserIds))
     {
      Print("[NEOTECH] Telegram token, allowed chat IDs and allowed user IDs are required; no values are hard-coded.");
      return INIT_PARAMETERS_INCORRECT;
     }
   if(InpTelegramPollSeconds<1 || InpTelegramPollSeconds>300 || InpTelegramPageSize<1 || InpTelegramPageSize>20)
     {
      Print("[NEOTECH] InpTelegramPollSeconds must be 1..300 and InpTelegramPageSize must be 1..20.");
      return INIT_PARAMETERS_INCORRECT;
     }
   FolderCreate(NT_LOCAL_DIR,FILE_COMMON);
   NTTelegramLoadLocalState();
   NTLoadProspectiveExtrema();
   NTLoadSltpJournal();
   NTLoadFddJob();
   NTRefreshReportIfNeeded();
   NTTelegramConfigurePolling();
   if(!EventSetTimer(InpTelegramPollSeconds)) return INIT_FAILED;
   PrintFormat("[NEOTECH] Read-only direct-Telegram compliance auditor initialized profile=@%s ruleset=%s polling=%s",profile,NT_RULESET_ID,g_telegram_polling_enabled?"enabled":"disabled");
   return INIT_SUCCEEDED;
  }

void OnDeinit(const int reason)
  {
   EventKillTimer();
   NTSaveProspectiveExtrema();
   NTSaveSltpJournal();
   NTSaveFddJob();
  }

void NTAdvanceCachedFdd()
  {
   if(g_cached_program_start<=0 || g_cached_opening_balance<=0.0 || ArraySize(g_cached_deals)==0) return;
   const long now_server=(long)TimeTradeServer()>0 ? (long)TimeTradeServer() : (long)TimeCurrent();
   const long before=g_fdd_job.cursor_seconds;
   NTAdvanceFddJob(g_cached_deals,g_cached_cashflows,g_cached_program_start,now_server,g_cached_opening_balance);
   if(before<now_server && g_fdd_job.cursor_seconds>=now_server) g_history_dirty=true;
  }

void OnTimer()
  {
   NTSampleProspectiveEquity();
   if(g_sltp_dirty)
     {
      NTSaveSltpJournal();
      g_sltp_dirty=false;
     }
   NTAdvanceCachedFdd();
   NTRefreshReportIfNeeded();
   if(!g_telegram_polling_enabled && !g_telegram_webhook_blocked && !NTTelegramBackoffActive()) NTTelegramConfigurePolling();
   if(!g_telegram_polling_enabled) return;
   NTTelegramPollUpdates();
   NTTelegramMaybeSendOnChange();
  }

void OnTradeTransaction(const MqlTradeTransaction &trans,const MqlTradeRequest &request,const MqlTradeResult &result)
  {
   NTRecordProspectiveTradeEvidence(trans);
   g_history_dirty=true;
  }
