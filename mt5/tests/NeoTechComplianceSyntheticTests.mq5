#property strict

#include "..\\neotech\\NeoTechComplianceCore.mqh"
#include "..\\neotech\\NeoTechComplianceJson.mqh"

int g_total=0;
int g_pass=0;
int g_fail=0;
string g_failed_names[];
string g_failed_expected[];
string g_failed_actual[];

void NTCheck(const string name,const bool condition,const string expected="true",const string actual="")
  {
   g_total++;
   const string resolved_actual=(actual!="" ? actual : (condition ? "true" : "false"));
   if(condition)
     {
      g_pass++;
      Print("[PASS] ",name);
      return;
     }
   g_fail++;
   const int n=ArraySize(g_failed_names);
   ArrayResize(g_failed_names,n+1);
   ArrayResize(g_failed_expected,n+1);
   ArrayResize(g_failed_actual,n+1);
   g_failed_names[n]=name;
   g_failed_expected[n]=expected;
   g_failed_actual[n]=resolved_actual;
   PrintFormat("[FAIL] %s expected=%s actual=%s",name,expected,resolved_actual);
  }

long T(const string value)
  {
   string text=value;
   StringReplace(text,"-",".");
   return (long)StringToTime(text);
  }

NTDealRecord D(const ulong ticket,const ulong order,const ulong position,const string symbol,const long seconds,const int entry,const int type,const double volume,const double price)
  {
   NTDealRecord row;
   row.ticket=ticket;
   row.order_ticket=order;
   row.position_id=position;
   row.broker_symbol=symbol;
   row.canonical_symbol=symbol;
   row.time_msc=seconds*1000L;
   row.entry=entry;
   row.deal_type=type;
   row.deal_reason=DEAL_REASON_CLIENT;
   row.order_reason=ORDER_REASON_CLIENT;
   row.magic=0;
   row.comment="";
   row.volume=volume;
   row.price=price;
   row.profit=0.0;
   row.commission=0.0;
   row.swap=0.0;
   row.fee=0.0;
   row.sl=0.0;
   row.tp=0.0;
   row.pip_size=0.0001;
   row.product_eligible=true;
   row.product_classification_reliable=true;
   row.opening_reason_reliable=true;
   row.sltp_snapshot_reliable=true;
   row.sltp_timeline_complete=true;
   return row;
  }

NTSignalEpisode E(const int index,const long open_seconds,const long close_seconds,const double net_profit=0.0)
  {
   NTSignalEpisode ep;
   ep.episode_id="E"+IntegerToString(index);
   ep.position_id=(ulong)(1000+index);
   ep.broker_symbol="GBPUSD";
   ep.canonical_symbol="GBPUSD";
   ep.product_eligible=true;
   ep.product_classification_reliable=true;
   ep.direction=1;
   ep.first_entry_msc=open_seconds*1000L;
   ep.final_close_msc=close_seconds>0?close_seconds*1000L:0;
   ep.holding_seconds=close_seconds>0?close_seconds-open_seconds:0;
   ep.opening_order_ticket=(ulong)(2000+index);
   ep.opening_deal_ticket=(ulong)(3000+index);
   ArrayResize(ep.entry_tickets,1); ep.entry_tickets[0]=ep.opening_deal_ticket;
   ArrayResize(ep.exit_tickets,0);
   ArrayResize(ep.additional_entries,0);
   ep.initial_volume=1.0;
   ep.max_volume=1.0;
   ep.current_volume=close_seconds>0?0.0:1.0;
   ep.entry_price=1.1000;
   ep.weighted_price=1.1000;
   ep.gross_profit=net_profit;
   ep.commission=0.0;
   ep.swap=0.0;
   ep.fee=0.0;
   ep.net_profit=net_profit;
   ep.opening_deal_reason=DEAL_REASON_CLIENT;
   ep.opening_order_reason=ORDER_REASON_CLIENT;
   ep.opening_magic=0;
   ep.opening_comment="";
   ep.opening_reason_reliable=true;
   ep.expert_open_violation=false;
   ep.opening_reason_unknown=false;
   ep.open=(close_seconds<=0);
   ep.scale_in_candidate=false;
   ep.dca_candidate=false;
   ep.sltp_observed=false;
   ep.sltp_evidence_complete=true;
   ep.max_sltp_distance_pips=0.0;
   ep.pip_size=0.0001;
   ep.pip_size_source="SYNTHETIC";
   ep.session=NTAssignSession(open_seconds);
   ep.trading_month_index=-1;
   ep.trading_week_start=0;
   ep.evidence_quality=NT_EVIDENCE_EXACT;
   return ep;
  }

void Fixture01_PartialClosesOneSignal()
  {
   NTDealRecord d[]; ArrayResize(d,3);
   d[0]=D(1,10,100,"GBPUSD",T("2026-08-03 10:00:00"),DEAL_ENTRY_IN,DEAL_TYPE_BUY,1.0,1.1000);
   d[1]=D(2,11,100,"GBPUSD",T("2026-08-03 10:10:00"),DEAL_ENTRY_OUT,DEAL_TYPE_SELL,0.4,1.1010);
   d[2]=D(3,12,100,"GBPUSD",T("2026-08-03 10:20:00"),DEAL_ENTRY_OUT,DEAL_TYPE_SELL,0.6,1.1020);
   NTSignalEpisode e[]; NTNormalizeDeals(d,e);
   NTCheck("01 one entry + partial closes = one signal",ArraySize(e)==1 && !e[0].open && ArraySize(e[0].exit_tickets)==2);
  }

void Fixture02_PartialFillsOneSignal()
  {
   NTDealRecord d[]; ArrayResize(d,3);
   d[0]=D(1,10,100,"GBPUSD",T("2026-08-03 10:00:00"),DEAL_ENTRY_IN,DEAL_TYPE_BUY,0.4,1.1000);
   d[1]=D(2,10,100,"GBPUSD",T("2026-08-03 10:00:01"),DEAL_ENTRY_IN,DEAL_TYPE_BUY,0.6,1.1001);
   d[2]=D(3,11,100,"GBPUSD",T("2026-08-03 10:20:00"),DEAL_ENTRY_OUT,DEAL_TYPE_SELL,1.0,1.1020);
   NTSignalEpisode e[]; NTNormalizeDeals(d,e);
   NTCheck("02 one order partial fills = one signal",ArraySize(e)==1 && !e[0].scale_in_candidate && ArraySize(e[0].entry_tickets)==2);
  }

void Fixture03_ReopenTwoSignals()
  {
   NTDealRecord d[]; ArrayResize(d,4);
   d[0]=D(1,10,100,"GBPUSD",T("2026-08-03 10:00:00"),DEAL_ENTRY_IN,DEAL_TYPE_BUY,1.0,1.1000);
   d[1]=D(2,11,100,"GBPUSD",T("2026-08-03 10:20:00"),DEAL_ENTRY_OUT,DEAL_TYPE_SELL,1.0,1.1010);
   d[2]=D(3,12,100,"GBPUSD",T("2026-08-03 12:00:00"),DEAL_ENTRY_IN,DEAL_TYPE_BUY,1.0,1.1020);
   d[3]=D(4,13,100,"GBPUSD",T("2026-08-03 12:20:00"),DEAL_ENTRY_OUT,DEAL_TYPE_SELL,1.0,1.1030);
   NTSignalEpisode e[]; NTNormalizeDeals(d,e);
   NTCheck("03 fully close then reopen = two signals",ArraySize(e)==2);
  }

void Fixture04_NettingLifecycle()
  {
   NTDealRecord d[]; ArrayResize(d,3);
   d[0]=D(1,10,100,"GBPUSD",T("2026-08-03 10:00:00"),DEAL_ENTRY_IN,DEAL_TYPE_BUY,0.5,1.1000);
   d[1]=D(2,11,100,"GBPUSD",T("2026-08-03 10:05:00"),DEAL_ENTRY_IN,DEAL_TYPE_BUY,0.5,1.1010);
   d[2]=D(3,12,100,"GBPUSD",T("2026-08-03 10:30:00"),DEAL_ENTRY_OUT,DEAL_TYPE_SELL,1.0,1.1020);
   NTSignalEpisode e[]; NTNormalizeDeals(d,e);
   NTCheck("04 netting account lifecycle",ArraySize(e)==1 && e[0].max_volume==1.0 && !e[0].open);
  }

void Fixture05_HedgingOppositeExposure()
  {
   NTSignalEpisode e[]; ArrayResize(e,2);
   e[0]=E(1,T("2026-08-03 10:00:00"),T("2026-08-03 11:00:00"));
   e[1]=E(2,T("2026-08-03 10:15:00"),T("2026-08-03 10:45:00")); e[1].direction=-1;
   NTCheck("05 hedging simultaneous opposite exposure",NTHasConfirmedHedging(e,T("2026-08-03 12:00:00")*1000L));
  }

void Fixture06_ManualOpenEaCloseAllowed()
  {
   NTDealRecord d[]; ArrayResize(d,2);
   d[0]=D(1,10,100,"GBPUSD",T("2026-08-03 10:00:00"),DEAL_ENTRY_IN,DEAL_TYPE_BUY,1.0,1.1000);
   d[1]=D(2,11,100,"GBPUSD",T("2026-08-03 10:20:00"),DEAL_ENTRY_OUT,DEAL_TYPE_SELL,1.0,1.1010); d[1].deal_reason=DEAL_REASON_EXPERT; d[1].order_reason=ORDER_REASON_EXPERT;
   NTSignalEpisode e[]; NTNormalizeDeals(d,e);
   NTCheck("06 manual opening + EA closure allowed",NTEvaluateE1(e,true)==NT_PASS);
  }

void Fixture07_ExpertOpenFails()
  {
   NTDealRecord d[]; ArrayResize(d,1); d[0]=D(1,10,100,"GBPUSD",T("2026-08-03 10:00:00"),DEAL_ENTRY_IN,DEAL_TYPE_BUY,1.0,1.1000); d[0].deal_reason=DEAL_REASON_EXPERT; d[0].order_reason=ORDER_REASON_EXPERT;
   NTSignalEpisode e[]; NTNormalizeDeals(d,e);
   NTCheck("07 expert opening violates E1",NTEvaluateE1(e,true)==NT_FAIL);
  }

void Fixture08_UnknownReasonNotVerifiable()
  {
   NTDealRecord d[]; ArrayResize(d,1); d[0]=D(1,10,100,"GBPUSD",T("2026-08-03 10:00:00"),DEAL_ENTRY_IN,DEAL_TYPE_BUY,1.0,1.1000); d[0].opening_reason_reliable=false; d[0].deal_reason=-1; d[0].order_reason=-1;
   NTSignalEpisode e[]; NTNormalizeDeals(d,e);
   NTCheck("08 broker reason unavailable = not verifiable",NTEvaluateE1(e,true)==NT_NOT_VERIFIABLE);
  }

void Fixture09_C5Duplicate()
  {
   NTSignalEpisode e[]; ArrayResize(e,2);
   e[0]=E(1,T("2026-11-02 10:10:00"),T("2026-11-02 11:00:00"));
   e[1]=E(2,T("2026-11-02 10:40:00"),T("2026-11-02 11:20:00"));
   NTCheck("09 second concurrent order on one symbol triggers C5",NTCountC5ConfirmedViolations(e,-1)==1);
  }

void Fixture10_OverlapPreviousSession()
  {
   NTCheck("10 overlap assigned to previous session",NTAssignSession(T("2026-11-02 10:30:00"))==NT_ASIA && NTAssignSession(T("2026-08-03 14:30:00"))==NT_EUROPE);
  }

void Fixture11_SeasonBoundary()
  {
   NTCheck("11 summer/winter session boundary",NTAssignSession(T("2026-04-01 11:00:00"))==NT_EUROPE && NTAssignSession(T("2026-11-01 11:00:00"))==NT_EUROPE && NTAssignSession(T("2026-10-31 22:59:59"))==NT_US && NTAssignSession(T("2026-11-01 23:30:00"))==NT_US);
  }

void Fixture12_OutsideSession()
  {
   NTCheck("12 outside-session trade",NTAssignSession(T("2026-08-03 01:59:59"))==NT_OUTSIDE_SESSION && NTAssignSession(T("2026-08-03 23:00:00"))==NT_OUTSIDE_SESSION);
  }

void Fixture13_C6ShortWithSlPasses()
  {
   NTSignalEpisode e=E(1,T("2026-08-03 10:00:00"),T("2026-08-03 10:14:59")); e.max_sltp_distance_pips=31.0; e.sltp_evidence_complete=true;
   NTCheck("13 hold 14:59 with qualifying SL passes C6",NTEvaluateC6Episode(e)==NT_PASS);
  }

void Fixture14_C6ShortNoSlFails()
  {
   NTSignalEpisode e=E(1,T("2026-08-03 10:00:00"),T("2026-08-03 10:14:59")); e.max_sltp_distance_pips=30.0; e.sltp_evidence_complete=true;
   NTCheck("14 hold 14:59 without >30pip SL/TP fails C6",NTEvaluateC6Episode(e)==NT_FAIL);
  }

void Fixture15_C6MissingEvidenceUnknown()
  {
   NTSignalEpisode e=E(1,T("2026-08-03 10:00:00"),T("2026-08-03 10:14:59")); e.sltp_evidence_complete=false;
   NTCheck("15 missing historical SL/TP not falsely failed",NTEvaluateC6Episode(e)==NT_NOT_VERIFIABLE);
  }

void Fixture16_ForexPips()
  {
   NTCheck("16 three/five digit Forex pip conversion",MathAbs(NTPipSize(0.00001,5,true,0)-0.0001)<1e-10 && MathAbs(NTPipSize(0.001,3,true,0)-0.01)<1e-10);
  }

void Fixture17_GoldOverride()
  {
   NTCheck("17 Gold custom pip override",MathAbs(NTPipSize(0.01,2,false,0.10)-0.10)<1e-10 && NTPipSize(0.01,2,false,0)==0.0);
  }

void Fixture18_DcaVsPartialFill()
  {
   NTDealRecord d[]; ArrayResize(d,4);
   d[0]=D(1,10,100,"GBPUSD",T("2026-08-03 10:00:00"),DEAL_ENTRY_IN,DEAL_TYPE_BUY,0.4,1.1000);
   d[1]=D(2,10,100,"GBPUSD",T("2026-08-03 10:00:01"),DEAL_ENTRY_IN,DEAL_TYPE_BUY,0.2,1.1001);
   d[2]=D(3,11,100,"GBPUSD",T("2026-08-03 10:05:00"),DEAL_ENTRY_IN,DEAL_TYPE_BUY,0.4,1.0990);
   d[3]=D(4,12,100,"GBPUSD",T("2026-08-03 10:30:00"),DEAL_ENTRY_OUT,DEAL_TYPE_SELL,1.0,1.1010);
   NTSignalEpisode e[]; NTNormalizeDeals(d,e);
   NTCheck("18 DCA versus partial fill",ArraySize(e)==1 && e[0].scale_in_candidate && e[0].dca_candidate);
  }

void Fixture19_DepositWithdrawal()
  {
   NTCashFlow f[]; ArrayResize(f,2); f[0].kind=1; f[1].kind=-1;
   NTCheck("19 deposit and withdrawal detection",NTCountDepositsWithdrawals(f)==2 && NTEvaluateC9(f,true,true)==NT_FAIL);
  }

void Fixture20_BonusCorrectionNotDeposit()
  {
   NTCashFlow f[]; ArrayResize(f,2); f[0].kind=3; f[1].kind=4;
   NTCheck("20 bonus/correction not automatically deposit",NTCountDepositsWithdrawals(f)==0 && NTEvaluateC9(f,true,true)==NT_PASS);
  }

void Fixture21_FirstWednesdayNextMonday()
  {
   NTCheck("21 first Wednesday weekly count starts next Monday",NTWeeklyCountingStart(T("2026-08-05 12:00:00"))==T("2026-08-10 00:00:00"));
  }

void Fixture22_FirstMondaySameMonday()
  {
   NTCheck("22 first Monday weekly count starts same Monday",NTWeeklyCountingStart(T("2026-08-03 12:00:00"))==T("2026-08-03 00:00:00"));
  }

void Fixture23_CompletedWeekTwoFails()
  {
   NTSignalEpisode e[]; ArrayResize(e,3);
   e[0]=E(1,T("2026-08-03 09:00:00"),T("2026-08-03 09:20:00"));
   e[1]=E(2,T("2026-08-04 09:00:00"),T("2026-08-04 09:20:00"));
   e[2]=E(3,T("2026-08-10 09:00:00"),T("2026-08-10 09:20:00"));
   NTWeekResult w[]; NTBuildWeeks(e,T("2026-08-11 00:00:00"),w);
   NTCheck("23 completed week with two signals fails",ArraySize(w)>=2 && w[0].status==NT_FAIL && w[0].signal_count==2);
  }

void Fixture24_CurrentWeekInProgress()
  {
   NTSignalEpisode e[]; ArrayResize(e,1); e[0]=E(1,T("2026-08-03 09:00:00"),T("2026-08-03 09:20:00"));
   NTWeekResult w[]; NTBuildWeeks(e,T("2026-08-05 00:00:00"),w);
   NTCheck("24 current incomplete week stays in progress",ArraySize(w)==1 && w[0].status==NT_IN_PROGRESS);
  }

void Fixture25_TwelveIndependentMonths()
  {
   const long start=T("2025-08-01 00:00:00");
   NTSignalEpisode e[]; ArrayResize(e,12);
   for(int i=0;i<12;i++) e[i]=E(i,start+(long)i*NT_MONTH_SECONDS+3600,start+(long)i*NT_MONTH_SECONDS+7200,2.0);
   NTCashFlow f[]; NTMonthResult m[];
   NTBuildMonths(e,f,start,start+12L*NT_MONTH_SECONDS,100.0,m);
   bool ok=ArraySize(m)>=12;
   for(int i=0;i<12 && ok;i++) ok=(m[i].status==NT_PASS);
   NTCheck("25 twelve independent 30-day return windows",ok && NTEvaluateC2(m,true)==NT_PASS);
  }

void Fixture26_OneBadMonthFailsDespiteAverage()
  {
   const long start=T("2025-08-01 00:00:00");
   NTSignalEpisode e[]; ArrayResize(e,12);
   for(int i=0;i<12;i++) e[i]=E(i,start+(long)i*NT_MONTH_SECONDS+3600,start+(long)i*NT_MONTH_SECONDS+7200,i==5?0.2:5.0);
   NTCashFlow f[]; NTMonthResult m[];
   NTBuildMonths(e,f,start,start+12L*NT_MONTH_SECONDS,100.0,m);
   NTCheck("26 one month below 1% fails despite yearly average",m[5].status==NT_FAIL && NTEvaluateC2(m,true)==NT_FAIL);
  }

void Fixture27_PartialHistoryPreventsPass()
  {
   const long now=T("2026-08-24 00:00:00");
   NTCheck("27 partial history prevents full PASS",!NTHistorySupportsFullYear(now-200L*NT_DAY_SECONDS,now) && NTEvaluateC1(now-400L*NT_DAY_SECONDS,now,false)==NT_DATA_GAP);
  }

void Fixture32_DisqualificationRisk()
  {
   NTCheck("32 C5/C6 monthly counters + risk banner",NTDisqualificationRisk(3,0,true)==1 && NTDisqualificationRisk(0,3,true)==1 && NTDisqualificationRisk(2,1,true)==1 && NTDisqualificationRisk(1,1,true)==0 && NTDisqualificationRisk(1,1,false)==-1);
  }

void Fixture33_AggregateFdd()
  {
   double unrealized[]; ArrayResize(unrealized,2); unrealized[0]=-1.2; unrealized[1]=-1.1;
   const double equity=NTAggregateEquity(100.0,unrealized);
   NTCheck("33 aggregate simultaneous-position FDD exceeds individual FDD",NTFloatingLossPct(100.0,98.8)<2.0 && NTFloatingLossPct(100.0,98.9)<2.0 && MathAbs(equity-97.7)<1e-9 && NTFloatingLossPct(100.0,equity)>2.0);
  }

void Fixture34_C4PassHorizonComplete()
  {
   NTWeekResult weeks[]; ArrayResize(weeks,52);
   for(int i=0;i<ArraySize(weeks);i++)
     {
      weeks[i].signal_count=3;
      weeks[i].target=3;
      weeks[i].missing=0;
      weeks[i].manual_pause=false;
      weeks[i].status=NT_PASS;
     }
   NTCheck("34 C4 reaches PASS after completed qualification horizon",NTEvaluateC4(weeks,true,true)==NT_PASS);
  }

void Fixture35_PartialHistoryAbsenceNeverPasses()
  {
   NTSignalEpisode episodes[]; ArrayResize(episodes,1); episodes[0]=E(1,T("2025-08-24 10:00:00"),T("2025-08-24 10:20:00"));
   NTWeekResult weeks[]; ArrayResize(weeks,1); weeks[0].signal_count=3; weeks[0].target=3; weeks[0].missing=0; weeks[0].status=NT_PASS; weeks[0].manual_pause=false;
   NTCheck("35 partial history prevents C5/C6/E5/C4 absence-based PASS",NTEvaluateC5(episodes,false,true)==NT_DATA_GAP && NTEvaluateC6(episodes,false,true)==NT_DATA_GAP && NTEvaluateE5(episodes,NTFirstEpisodeStart(episodes),false)==NT_DATA_GAP && NTEvaluateC4(weeks,false,true)==NT_DATA_GAP && NTEvaluateE1(episodes,false)==NT_DATA_GAP);
  }

void Fixture36_ExcludedFirstTradeStartsProgram()
  {
   NTSignalEpisode episodes[]; ArrayResize(episodes,2);
   episodes[0]=E(1,T("2025-08-20 09:00:00"),T("2025-08-20 09:30:00"));
   episodes[0].product_eligible=false; episodes[0].product_classification_reliable=true; episodes[0].broker_symbol="US30"; episodes[0].canonical_symbol="EXCLUDED:US30";
   episodes[1]=E(2,T("2025-08-21 09:00:00"),T("2025-08-21 09:30:00"));
   const long start=NTFirstEpisodeStart(episodes);
   NTCheck("36 first excluded product establishes program start and fails E5",start==T("2025-08-20 09:00:00") && NTEvaluateE5(episodes,start,true)==NT_FAIL);
  }

void Fixture37_InoutResidualVolume()
  {
   NTDealRecord equal[]; ArrayResize(equal,2);
   equal[0]=D(1,10,100,"GBPUSD",T("2026-08-03 10:00:00"),DEAL_ENTRY_IN,DEAL_TYPE_BUY,1.0,1.1000);
   equal[1]=D(2,11,100,"GBPUSD",T("2026-08-03 10:10:00"),DEAL_ENTRY_INOUT,DEAL_TYPE_SELL,1.0,1.0990);
   NTSignalEpisode flat[]; NTNormalizeDeals(equal,flat);

   NTDealRecord reverse[]; ArrayResize(reverse,2);
   reverse[0]=D(3,20,200,"GBPUSD",T("2026-08-03 11:00:00"),DEAL_ENTRY_IN,DEAL_TYPE_BUY,1.0,1.1000);
   reverse[1]=D(4,21,200,"GBPUSD",T("2026-08-03 11:10:00"),DEAL_ENTRY_INOUT,DEAL_TYPE_SELL,1.5,1.0990);
   NTSignalEpisode reversed[]; NTNormalizeDeals(reverse,reversed);
   const bool flat_ok=ArraySize(flat)==1 && !flat[0].open && MathAbs(flat[0].max_volume-1.0)<1e-9;
   const bool reverse_ok=ArraySize(reversed)==2 && !reversed[0].open && reversed[1].open && reversed[1].direction==-1 && MathAbs(reversed[1].initial_volume-0.5)<1e-9 && reversed[1].opening_deal_ticket==4;
   NTCheck("37 INOUT reversal creates only residual new volume",flat_ok && reverse_ok);
  }

void Fixture38_HedgingExactEvidence()
  {
   NTSignalEpisode episodes[]; ArrayResize(episodes,2);
   episodes[0]=E(1,T("2026-08-03 10:00:00"),T("2026-08-03 11:00:00"));
   episodes[1]=E(2,T("2026-08-03 10:15:00"),T("2026-08-03 10:45:00")); episodes[1].direction=-1;
   NTHedgingEvidence evidence_rows[]; NTBuildHedgingEvidence(episodes,T("2026-08-03 12:00:00")*1000L,evidence_rows);
   const string json=ArraySize(evidence_rows)==1 ? NTHedgingEvidenceJson(evidence_rows[0]) : "";
   NTCheck("38 confirmed hedging emits exact timestamp/symbol/IDs",ArraySize(evidence_rows)==1 && evidence_rows[0].overlap_start_msc==episodes[1].first_entry_msc && evidence_rows[0].overlap_end_msc==episodes[1].final_close_msc && evidence_rows[0].first_position_id==episodes[0].position_id && evidence_rows[0].second_position_id==episodes[1].position_id && StringFind(json,"\"positionIds\"")>=0 && StringFind(json,"BUY")>=0 && StringFind(json,"SELL")>=0 && StringFind(json,"GBPUSD")>=0);
  }

void Fixture39_AdditionalEntryExactEvidence()
  {
   NTDealRecord deals[]; ArrayResize(deals,4);
   deals[0]=D(1,10,100,"GBPUSD",T("2026-08-03 10:00:00"),DEAL_ENTRY_IN,DEAL_TYPE_BUY,0.4,1.1000);
   deals[1]=D(2,10,100,"GBPUSD",T("2026-08-03 10:00:01"),DEAL_ENTRY_IN,DEAL_TYPE_BUY,0.2,1.1001);
   deals[2]=D(3,11,100,"GBPUSD",T("2026-08-03 10:05:00"),DEAL_ENTRY_IN,DEAL_TYPE_BUY,0.4,1.0990);
   deals[3]=D(4,12,100,"GBPUSD",T("2026-08-03 10:30:00"),DEAL_ENTRY_OUT,DEAL_TYPE_SELL,1.0,1.1010);
   NTSignalEpisode episodes[]; NTNormalizeDeals(deals,episodes);
   if(ArraySize(episodes)!=1 || ArraySize(episodes[0].additional_entries)!=1)
     {
      NTCheck("39 scale-in/DCA emits added-entry timestamp and tickets",false,"one episode with one additional-entry evidence record",StringFormat("episodes=%d additional=%d",ArraySize(episodes),ArraySize(episodes)>0?ArraySize(episodes[0].additional_entries):-1));
      return;
     }
   const NTAdditionalEntryEvidence added=episodes[0].additional_entries[0];
   const string json=NTAdditionalEntryEvidenceJson(added);
   NTCheck("39 scale-in/DCA emits added-entry timestamp and tickets",added.time_msc==deals[2].time_msc && added.order_ticket==11 && added.deal_ticket==3 && added.adverse && StringFind(json,"\"orderTicket\":\"11\"")>=0 && StringFind(json,"\"dealTicket\":\"3\"")>=0 && StringFind(json,"\"adverse\":true")>=0);
  }

void Fixture40_ProspectiveCompleteC6Fail()
  {
   NTSignalEpisode episodes[]; ArrayResize(episodes,1); episodes[0]=E(1,T("2026-08-03 10:00:00"),T("2026-08-03 10:14:59")); episodes[0].sltp_evidence_complete=true; episodes[0].max_sltp_distance_pips=30.0;
   NTCheck("40 prospective complete SL/TP evidence can confirm C6 FAIL",NTEvaluateC6(episodes,true,true)==NT_FAIL && NTEvaluateC6Episode(episodes[0])==NT_FAIL);
  }

void Fixture44_ServerUtcVietnamTime()
  {
   const long winter=T("2026-03-31 10:00:00");
   const long summer=T("2026-04-01 10:00:00");
   const long winter_again=T("2026-11-01 10:00:00");
   NTCheck("44 server/UTC/Vietnam conversion summer-winter",NTServerUtcOffsetMinutes(winter)==120 && NTServerUtcOffsetMinutes(summer)==180 && NTServerUtcOffsetMinutes(winter_again)==120 && NTVietnamSecondsFromNeoTechServer(winter)-winter==5L*3600L && NTVietnamSecondsFromNeoTechServer(summer)-summer==4L*3600L && NTVietnamSecondsFromNeoTechServer(winter_again)-winter_again==5L*3600L);
  }

void Fixture45_TelegramCheckSyntaxes()
  {
   NTTelegramCheckCommand a,b,c,d;
   const bool ok=NTTelegramParseCheckCommand("/check @oakdemo","oakdemo",a)
      && NTTelegramParseCheckCommand("/check @oakdemo 2","oakdemo",b)
      && NTTelegramParseCheckCommand("/check @oakdemo C5","oakdemo",c)
      && NTTelegramParseCheckCommand("/check @oakdemo violations 2","oakdemo",d);
   NTCheck("45 Telegram parses four /check syntaxes",ok && a.slug_matches && a.view==NT_TG_VIEW_SUMMARY && a.page==1 && b.view==NT_TG_VIEW_SUMMARY && b.page==2 && c.view==NT_TG_VIEW_CRITERION && c.criterion=="C5" && c.page==1 && d.view==NT_TG_VIEW_VIOLATIONS && d.page==2);
  }

void Fixture46_TelegramGroupCommand()
  {
   NTTelegramCheckCommand cmd;
   NTCheck("46 group /check@BotUsername is accepted",NTTelegramParseCheckCommand("/check@NeoTechAuditBot @oakdemo C5","oakdemo",cmd) && cmd.slug_matches && cmd.view==NT_TG_VIEW_CRITERION && cmd.criterion=="C5");
  }

void Fixture47_TelegramSlugMismatch()
  {
   NTTelegramCheckCommand cmd;
   NTCheck("47 Telegram slug mismatch is recognized but not authorized for profile",NTTelegramParseCheckCommand("/check @other 2","oakdemo",cmd) && !cmd.slug_matches);
  }

void Fixture48_TelegramAcl()
  {
   NTCheck("48 Telegram ACL requires both chat and user",NTTelegramAclAllowed("-100123,55","77,88",-100123,77) && !NTTelegramAclAllowed("-100123,55","77,88",-100999,77) && !NTTelegramAclAllowed("-100123,55","77,88",-100123,99));
  }

void Fixture49_TelegramReplayOffset()
  {
   NTCheck("49 Telegram replay offset is monotonic",!NTTelegramUpdateProcessable(99,100) && NTTelegramUpdateProcessable(100,100) && NTTelegramNextOffset(100,100)==101 && NTTelegramNextOffset(105,100)==105);
  }

void Fixture50_TelegramJsonResponse()
  {
   const string success="{\"ok\":true,\"result\":[]}";
   const string error="{\"ok\":false,\"error_code\":409,\"description\":\"Conflict\"}";
   NTCheck("50 Telegram JSON success and error are distinguished",NTTelegramApiOk(success) && !NTTelegramApiOk(error));
  }

void Fixture51_TelegramUtf8UrlEncoding()
  {
   NTCheck("51 UTF-8 form encoding is byte-correct",NTUrlEncodeUtf8("Xin chào ✓")=="Xin%20ch%C3%A0o%20%E2%9C%93");
  }

void Fixture52_TelegramPaginationLimit()
  {
   string chunk="";
   for(int i=0;i<1300;i++) chunk+="x";
   string items[]; ArrayResize(items,7);
   for(int i=0;i<ArraySize(items);i++) items[i]=IntegerToString(i+1)+" "+chunk;
   string pages[];
   const int count=NTTelegramPaginateItems("NeoTech synthetic",items,3,3800,pages);
   bool bounded=(count>1);
   for(int i=0;i<ArraySize(pages);i++) if(StringLen(pages[i])>3800) bounded=false;
   NTCheck("52 Telegram pagination stays below message budget",bounded);
  }

void Fixture53_TelegramC5Filter()
  {
   NTCheck("53 criterion filter isolates C5",NTTelegramCriterionMatches("C5","c5") && !NTTelegramCriterionMatches("C6","c5") && NTTelegramCriterionMatches("C5","C5"));
  }

void Fixture54_TelegramWebhookConflict()
  {
   const string empty="{\"ok\":true,\"result\":{\"url\":\"\"}}";
   const string occupied="{\"ok\":true,\"result\":{\"url\":\"https://example.invalid/hook\"}}";
   NTCheck("54 webhook conflict never deletes without opt-in",NTTelegramWebhookDecision(empty,false)==NT_TG_WEBHOOK_READY && NTTelegramWebhookDecision(occupied,false)==NT_TG_WEBHOOK_BLOCK && NTTelegramWebhookDecision(occupied,true)==NT_TG_WEBHOOK_DELETE);
  }

void Fixture55_TelegramRedaction()
  {
   const string safe=NTTelegramRedact("login=12345678 broker=Neo Broker server=Neo-Live token=secret-token","12345678","Neo Broker","Neo-Live","secret-token");
   NTCheck("55 Telegram output redacts sensitive account and bot data",StringFind(safe,"12345678")<0 && StringFind(safe,"Neo Broker")<0 && StringFind(safe,"Neo-Live")<0 && StringFind(safe,"secret-token")<0);
  }

void Fixture56_EligibleProducts()
  {
   const bool forex=NTIsEligibleProduct("GBP","USD",true);
   const bool xauusd=NTIsEligibleProduct("XAU","USD",false);
   const bool rejects= !NTIsEligibleProduct("XAU","EUR",false) && !NTIsEligibleProduct("XAG","USD",false) && !NTIsEligibleProduct("US30","USD",false);
   NTCheck("56 E5 accepts only Forex and XAUUSD",forex && xauusd && rejects);
  }

void Fixture57_C5ClosedThenReopenAllowed()
  {
   NTSignalEpisode episodes[]; ArrayResize(episodes,2);
   episodes[0]=E(1,T("2026-11-02 10:10:00"),T("2026-11-02 10:30:00"));
   episodes[1]=E(2,T("2026-11-02 10:40:00"),T("2026-11-02 11:20:00"));
   NTCheck("57 C5 allows reopening a symbol after the first order closes",NTCountC5ConfirmedViolations(episodes,-1)==0);
  }

void Fixture58_C5OwnsAddEntryC7OnlyHedging()
  {
   NTDealRecord deals[]; ArrayResize(deals,3);
   deals[0]=D(1,10,100,"GBPUSD",T("2026-08-03 10:00:00"),DEAL_ENTRY_IN,DEAL_TYPE_BUY,0.5,1.1000);
   deals[1]=D(2,11,100,"GBPUSD",T("2026-08-03 10:05:00"),DEAL_ENTRY_IN,DEAL_TYPE_BUY,0.5,1.0990);
   deals[2]=D(3,12,100,"GBPUSD",T("2026-08-03 10:30:00"),DEAL_ENTRY_OUT,DEAL_TYPE_SELL,1.0,1.1010);
   NTSignalEpisode episodes[]; NTNormalizeDeals(deals,episodes);
   const long now=T("2026-08-03 11:00:00")*1000L;
   NTCheck("58 add-entry violates C5 while C7 checks only hedging",NTCountC5ConfirmedViolations(episodes,-1)==1 && NTEvaluateC7(episodes,now,true,true)==NT_PASS);
  }

void Fixture59_VietnameseLabelsAndRemovedCriteria()
  {
   const bool removed=!NTTelegramCriterionToken("E4") && !NTTelegramCriterionToken("C3") && NTTelegramCriterionToken("E5") && NTTelegramCriterionToken("C5");
   const bool labels=NTTelegramStatusVi("FAIL")=="VI PHẠM" && NTTelegramStatusVi("DATA_GAP")=="THIẾU DỮ LIỆU" && NTTelegramRiskVi("YES")=="CÓ" && NTTelegramRiskVi("UNKNOWN")=="CHƯA RÕ" && NTTelegramFddMethodVi("M1")=="Phục dựng từ nến M1";
   NTCheck("59 removed criteria and Vietnamese Telegram labels",removed && labels);
  }

void OnStart()
  {
   Fixture01_PartialClosesOneSignal();
   Fixture02_PartialFillsOneSignal();
   Fixture03_ReopenTwoSignals();
   Fixture04_NettingLifecycle();
   Fixture05_HedgingOppositeExposure();
   Fixture06_ManualOpenEaCloseAllowed();
   Fixture07_ExpertOpenFails();
   Fixture08_UnknownReasonNotVerifiable();
   Fixture09_C5Duplicate();
   Fixture10_OverlapPreviousSession();
   Fixture11_SeasonBoundary();
   Fixture12_OutsideSession();
   Fixture13_C6ShortWithSlPasses();
   Fixture14_C6ShortNoSlFails();
   Fixture15_C6MissingEvidenceUnknown();
   Fixture16_ForexPips();
   Fixture17_GoldOverride();
   Fixture18_DcaVsPartialFill();
   Fixture19_DepositWithdrawal();
   Fixture20_BonusCorrectionNotDeposit();
   Fixture21_FirstWednesdayNextMonday();
   Fixture22_FirstMondaySameMonday();
   Fixture23_CompletedWeekTwoFails();
   Fixture24_CurrentWeekInProgress();
   Fixture25_TwelveIndependentMonths();
   Fixture26_OneBadMonthFailsDespiteAverage();
   Fixture27_PartialHistoryPreventsPass();
   Fixture32_DisqualificationRisk();
   Fixture33_AggregateFdd();
   Fixture34_C4PassHorizonComplete();
   Fixture35_PartialHistoryAbsenceNeverPasses();
   Fixture36_ExcludedFirstTradeStartsProgram();
   Fixture37_InoutResidualVolume();
   Fixture38_HedgingExactEvidence();
   Fixture39_AdditionalEntryExactEvidence();
   Fixture40_ProspectiveCompleteC6Fail();
   Fixture44_ServerUtcVietnamTime();
   Fixture45_TelegramCheckSyntaxes();
   Fixture46_TelegramGroupCommand();
   Fixture47_TelegramSlugMismatch();
   Fixture48_TelegramAcl();
   Fixture49_TelegramReplayOffset();
   Fixture50_TelegramJsonResponse();
   Fixture51_TelegramUtf8UrlEncoding();
   Fixture52_TelegramPaginationLimit();
   Fixture53_TelegramC5Filter();
   Fixture54_TelegramWebhookConflict();
   Fixture55_TelegramRedaction();
   Fixture56_EligibleProducts();
   Fixture57_C5ClosedThenReopenAllowed();
   Fixture58_C5OwnsAddEntryC7OnlyHedging();
   Fixture59_VietnameseLabelsAndRemovedCriteria();
   for(int i=0;i<ArraySize(g_failed_names);i++) PrintFormat("[NEOTECH SYNTHETIC] FAILURE fixture=%s expected=%s actual=%s",g_failed_names[i],g_failed_expected[i],g_failed_actual[i]);
   PrintFormat("[NEOTECH SYNTHETIC] TOTAL=%d PASS=%d FAIL=%d RESULT=%s",g_total,g_pass,g_fail,g_fail==0?"PASS":"FAIL");
  }
