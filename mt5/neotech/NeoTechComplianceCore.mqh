#ifndef OAK_NEOTECH_COMPLIANCE_CORE_MQH
#define OAK_NEOTECH_COMPLIANCE_CORE_MQH

#define NT_RULESET_ID              "neotech-signal-provider-2024-10-03-v1"
#define NT_SOURCE_URL              "https://blog.neotechltd.com/vi/post/chuong-trinh-dac-biet-danh-cho-nha-cung-cap-tin-hieu_66fe1311ffc2ca0001f68ab0"
#define NT_ARTICLE_DATE            "2024-10-03"
#define NT_RETRIEVAL_DATE          "2026-08-24"
#define NT_SCHEMA_VERSION          "oak-neotech-compliance-report-v3"
#define NT_DAY_SECONDS             86400
#define NT_MONTH_SECONDS           (30*NT_DAY_SECONDS)
#define NT_WEEK_SECONDS            (7*NT_DAY_SECONDS)
#define NT_C1_STRICT_POLICY        "CALENDAR_365_AND_12X30"

// This module is pure evaluation logic. It performs no network calls and no trade mutations.
enum NTStatus
  {
   NT_PASS=0,
   NT_FAIL=1,
   NT_IN_PROGRESS=2,
   NT_NOT_VERIFIABLE=3,
   NT_DATA_GAP=4,
   NT_RECONSTRUCTED=5
  };

enum NTSession
  {
   NT_OUTSIDE_SESSION=0,
   NT_ASIA=1,
   NT_EUROPE=2,
   NT_US=3
  };

enum NTEvidenceQuality
  {
   NT_EVIDENCE_EXACT=0,
   NT_EVIDENCE_RECONSTRUCTED=1,
   NT_EVIDENCE_M1=2,
   NT_EVIDENCE_GAP=3
  };

struct NTDealRecord
  {
   ulong             ticket;
   ulong             order_ticket;
   ulong             position_id;
   string            broker_symbol;
   string            canonical_symbol;
   long              time_msc;
   int               entry;
   int               deal_type;
   int               deal_reason;
   int               order_reason;
   long              magic;
   string            comment;
   double            volume;
   double            price;
   double            profit;
   double            commission;
   double            swap;
   double            fee;
   double            sl;
   double            tp;
   double            pip_size;
   bool              product_eligible;
   bool              product_classification_reliable;
   bool              opening_reason_reliable;
   bool              sltp_snapshot_reliable;
   bool              sltp_timeline_complete;
  };

struct NTAdditionalEntryEvidence
  {
   long              time_msc;
   ulong             order_ticket;
   ulong             deal_ticket;
   double            volume;
   double            price;
   double            previous_weighted_price;
   double            new_weighted_price;
   bool              adverse;
  };

struct NTC5Occurrence
  {
   int               month_index;
   long              time_msc;
   string            canonical_symbol;
   string            broker_symbol;
   NTSession         session;
   string            episode_id;
   ulong             position_id;
   ulong             order_ticket;
   ulong             deal_ticket;
   int               occurrence_number;
  };

struct NTHedgingEvidence
  {
   long              overlap_start_msc;
   long              overlap_end_msc;
   string            canonical_symbol;
   string            broker_symbol;
   ulong             first_position_id;
   ulong             second_position_id;
   ulong             first_order_ticket;
   ulong             second_order_ticket;
   ulong             first_deal_ticket;
   ulong             second_deal_ticket;
   int               first_direction;
   int               second_direction;
  };

struct NTSignalEpisode
  {
   string            episode_id;
   ulong             position_id;
   string            broker_symbol;
   string            canonical_symbol;
   bool              product_eligible;
   bool              product_classification_reliable;
   int               direction;
   long              first_entry_msc;
   long              final_close_msc;
   long              holding_seconds;
   ulong             opening_order_ticket;
   ulong             opening_deal_ticket;
   ulong             entry_tickets[];
   ulong             exit_tickets[];
   NTAdditionalEntryEvidence additional_entries[];
   double            initial_volume;
   double            max_volume;
   double            current_volume;
   double            entry_price;
   double            weighted_price;
   double            gross_profit;
   double            commission;
   double            swap;
   double            fee;
   double            net_profit;
   int               opening_deal_reason;
   int               opening_order_reason;
   long              opening_magic;
   string            opening_comment;
   bool              opening_reason_reliable;
   bool              expert_open_violation;
   bool              opening_reason_unknown;
   bool              open;
   bool              scale_in_candidate;
   bool              dca_candidate;
   bool              sltp_observed;
   bool              sltp_evidence_complete;
   double            max_sltp_distance_pips;
   double            pip_size;
   string            pip_size_source;
   NTSession         session;
   int               trading_month_index;
   long              trading_week_start;
   NTEvidenceQuality evidence_quality;
  };

struct NTWeekResult
  {
   long              start_time;
   long              end_time;
   int               signal_count;
   int               target;
   int               missing;
   bool              manual_pause;
   NTStatus          status;
  };

struct NTMonthResult
  {
   long              start_time;
   long              end_time;
   double            opening_balance;
   double            trading_net_pl;
   double            deposits;
   double            withdrawals;
   double            other_cash_flow;
   double            raw_return_pct;
   double            adjusted_return_pct;
   NTStatus          status;
  };

struct NTCashFlow
  {
   long              time_msc;
   double            amount;
   int               kind; // 1 deposit, -1 withdrawal, 2 fee/charge, 3 credit/bonus, 4 correction, 0 unknown
   ulong             ticket;
   string            comment;
  };

struct NTCriterionState
  {
   string            id;
   NTStatus          status;
   string            reason_code;
   string            explanation_vi;
  };

string NTStatusName(const NTStatus status)
  {
   switch(status)
     {
      case NT_PASS: return "PASS";
      case NT_FAIL: return "FAIL";
      case NT_IN_PROGRESS: return "IN_PROGRESS";
      case NT_NOT_VERIFIABLE: return "NOT_VERIFIABLE";
      case NT_DATA_GAP: return "DATA_GAP";
      case NT_RECONSTRUCTED: return "RECONSTRUCTED";
     }
   return "DATA_GAP";
  }

string NTSessionName(const NTSession session)
  {
   switch(session)
     {
      case NT_ASIA: return "ASIA";
      case NT_EUROPE: return "EUROPE";
      case NT_US: return "US";
     }
   return "OUTSIDE_SESSION";
  }

long NTSeconds(const long msc)
  {
   return msc/1000;
  }

long NTDayStart(const long epoch_seconds)
  {
   MqlDateTime dt;
   TimeToStruct((datetime)epoch_seconds,dt);
   dt.hour=0; dt.min=0; dt.sec=0;
   return (long)StructToTime(dt);
  }

bool NTIsSummer(const long epoch_seconds)
  {
   MqlDateTime dt;
   TimeToStruct((datetime)epoch_seconds,dt);
   return dt.mon>=4 && dt.mon<=10;
  }

int NTMinuteOfDay(const long epoch_seconds)
  {
   MqlDateTime dt;
   TimeToStruct((datetime)epoch_seconds,dt);
   return dt.hour*60+dt.min;
  }

bool NTHalfOpen(const int minute,const int start_minute,const int end_minute)
  {
   return minute>=start_minute && minute<end_minute;
  }

// Overlap priority is deliberately Asia -> Europe -> US, which assigns overlap to the previous session.
NTSession NTAssignSession(const long epoch_seconds)
  {
   const int minute=NTMinuteOfDay(epoch_seconds);
   const bool summer=NTIsSummer(epoch_seconds);
   if(NTHalfOpen(minute,2*60,11*60)) return NT_ASIA;
   if(summer)
     {
      if(NTHalfOpen(minute,9*60,18*60)) return NT_EUROPE;
      if(NTHalfOpen(minute,14*60,23*60)) return NT_US;
     }
   else
     {
      if(NTHalfOpen(minute,10*60,19*60)) return NT_EUROPE;
      if(NTHalfOpen(minute,15*60,24*60)) return NT_US;
     }
   return NT_OUTSIDE_SESSION;
  }

long NTWeeklyCountingStart(const long first_signal_seconds)
  {
   MqlDateTime dt;
   TimeToStruct((datetime)first_signal_seconds,dt);
   const long day_start=NTDayStart(first_signal_seconds);
   if(dt.day_of_week==1) return day_start; // Monday
   const int days_until_monday=(8-dt.day_of_week)%7;
   return day_start+(long)days_until_monday*NT_DAY_SECONDS;
  }

int NTTradingMonthIndex(const long signal_seconds,const long program_start_seconds)
  {
   if(program_start_seconds<=0 || signal_seconds<program_start_seconds) return -1;
   return (int)((signal_seconds-program_start_seconds)/NT_MONTH_SECONDS);
  }

long NTTradingMonthStart(const long program_start_seconds,const int index)
  {
   return program_start_seconds+(long)index*NT_MONTH_SECONDS;
  }

double NTPipSize(const double point,const int digits,const bool is_forex,const double override_pip_size)
  {
   if(override_pip_size>0.0) return override_pip_size;
   if(!is_forex || point<=0.0) return 0.0;
   return (digits==3 || digits==5) ? point*10.0 : point;
  }

double NTPipDistance(const double from_price,const double to_price,const double pip_size)
  {
   if(pip_size<=0.0) return 0.0;
   return MathAbs(to_price-from_price)/pip_size;
  }

bool NTIsForexProduct(const string base,const string profit,const bool forex_calc)
  {
   return forex_calc && StringLen(base)==3 && StringLen(profit)==3;
  }

bool NTIsEligibleProduct(const string base,const string profit,const bool forex_calc)
  {
   return NTIsForexProduct(base,profit,forex_calc) || (base=="XAU" && profit=="USD");
  }

bool NTDealIsTrading(const NTDealRecord &deal)
  {
   return deal.deal_type==DEAL_TYPE_BUY || deal.deal_type==DEAL_TYPE_SELL;
  }

int NTDealDirection(const NTDealRecord &deal)
  {
   if(deal.deal_type==DEAL_TYPE_BUY) return 1;
   if(deal.deal_type==DEAL_TYPE_SELL) return -1;
   return 0;
  }

bool NTIsOpeningEntry(const int entry)
  {
   return entry==DEAL_ENTRY_IN || entry==DEAL_ENTRY_INOUT;
  }

bool NTIsClosingEntry(const int entry)
  {
   return entry==DEAL_ENTRY_OUT || entry==DEAL_ENTRY_OUT_BY || entry==DEAL_ENTRY_INOUT;
  }

void NTAppendUlong(ulong &values[],const ulong value)
  {
   const int n=ArraySize(values);
   ArrayResize(values,n+1);
   values[n]=value;
  }

void NTAppendString(string &values[],const string value)
  {
   const int n=ArraySize(values);
   ArrayResize(values,n+1);
   values[n]=value;
  }

int NTFindOpenEpisode(NTSignalEpisode &episodes[],const ulong position_id,const string canonical_symbol)
  {
   for(int i=ArraySize(episodes)-1;i>=0;i--)
      if(episodes[i].open && episodes[i].position_id==position_id && episodes[i].canonical_symbol==canonical_symbol)
         return i;
   return -1;
  }

bool NTReasonManual(const int deal_reason,const int order_reason,const bool reliable)
  {
   if(!reliable) return false;
   const bool deal_manual=(deal_reason==DEAL_REASON_CLIENT || deal_reason==DEAL_REASON_MOBILE || deal_reason==DEAL_REASON_WEB);
   const bool order_manual=(order_reason==ORDER_REASON_CLIENT || order_reason==ORDER_REASON_MOBILE || order_reason==ORDER_REASON_WEB);
   return deal_manual || order_manual;
  }

bool NTReasonExpert(const int deal_reason,const int order_reason,const bool reliable)
  {
   if(!reliable) return false;
   return deal_reason==DEAL_REASON_EXPERT || order_reason==ORDER_REASON_EXPERT;
  }

void NTObserveSltp(NTSignalEpisode &episode,const NTDealRecord &deal)
  {
   if(!deal.sltp_snapshot_reliable || deal.pip_size<=0.0) return;
   if(deal.sl>0.0)
     {
      episode.sltp_observed=true;
      episode.max_sltp_distance_pips=MathMax(episode.max_sltp_distance_pips,NTPipDistance(deal.price,deal.sl,deal.pip_size));
     }
   if(deal.tp>0.0)
     {
      episode.sltp_observed=true;
      episode.max_sltp_distance_pips=MathMax(episode.max_sltp_distance_pips,NTPipDistance(deal.price,deal.tp,deal.pip_size));
     }
  }

int NTCreateEpisode(NTSignalEpisode &episodes[],const NTDealRecord &deal,const int sequence)
  {
   const int n=ArraySize(episodes);
   ArrayResize(episodes,n+1);
   NTSignalEpisode ep;
   ep.episode_id=StringFormat("%I64u-%d",deal.position_id,sequence);
   ep.position_id=deal.position_id;
   ep.broker_symbol=deal.broker_symbol;
   ep.canonical_symbol=deal.canonical_symbol;
   ep.product_eligible=deal.product_eligible;
   ep.product_classification_reliable=deal.product_classification_reliable;
   ep.direction=NTDealDirection(deal);
   ep.first_entry_msc=deal.time_msc;
   ep.final_close_msc=0;
   ep.holding_seconds=0;
   ep.opening_order_ticket=deal.order_ticket;
   ep.opening_deal_ticket=deal.ticket;
   ArrayResize(ep.entry_tickets,0);
   ArrayResize(ep.exit_tickets,0);
   ArrayResize(ep.additional_entries,0);
   NTAppendUlong(ep.entry_tickets,deal.ticket);
   ep.initial_volume=deal.volume;
   ep.max_volume=deal.volume;
   ep.current_volume=deal.volume;
   ep.entry_price=deal.price;
   ep.weighted_price=deal.price;
   ep.gross_profit=deal.profit;
   ep.commission=deal.commission;
   ep.swap=deal.swap;
   ep.fee=deal.fee;
   ep.net_profit=deal.profit+deal.commission+deal.swap+deal.fee;
   ep.opening_deal_reason=deal.deal_reason;
   ep.opening_order_reason=deal.order_reason;
   ep.opening_magic=deal.magic;
   ep.opening_comment=deal.comment;
   ep.opening_reason_reliable=deal.opening_reason_reliable;
   ep.expert_open_violation=NTReasonExpert(deal.deal_reason,deal.order_reason,deal.opening_reason_reliable);
   ep.opening_reason_unknown=!ep.expert_open_violation && !NTReasonManual(deal.deal_reason,deal.order_reason,deal.opening_reason_reliable);
   ep.open=true;
   ep.scale_in_candidate=false;
   ep.dca_candidate=false;
   ep.sltp_observed=false;
   ep.sltp_evidence_complete=deal.sltp_timeline_complete;
   ep.max_sltp_distance_pips=0.0;
   ep.pip_size=deal.pip_size;
   ep.pip_size_source=(deal.pip_size>0.0 ? "SYMBOL_METADATA_OR_OVERRIDE" : "MISSING");
   ep.session=NTAssignSession(NTSeconds(deal.time_msc));
   ep.trading_month_index=-1;
   ep.trading_week_start=0;
   ep.evidence_quality=NT_EVIDENCE_EXACT;
   NTObserveSltp(ep,deal);
   episodes[n]=ep;
   return n;
  }

void NTAddEntryToEpisode(NTSignalEpisode &ep,const NTDealRecord &deal)
  {
   const double old_volume=ep.current_volume;
   const double old_weighted=ep.weighted_price;
   const bool same_order=(deal.order_ticket!=0 && deal.order_ticket==ep.opening_order_ticket);
   const bool adverse=((ep.direction>0 && deal.price<old_weighted) || (ep.direction<0 && deal.price>old_weighted));
   const double new_volume=old_volume+deal.volume;
   const double new_weighted=(new_volume>0.0 ? (old_weighted*old_volume+deal.price*deal.volume)/new_volume : old_weighted);
   if(!same_order)
     {
      ep.scale_in_candidate=true;
      if(adverse) ep.dca_candidate=true;
      const int n=ArraySize(ep.additional_entries);
      ArrayResize(ep.additional_entries,n+1);
      ep.additional_entries[n].time_msc=deal.time_msc;
      ep.additional_entries[n].order_ticket=deal.order_ticket;
      ep.additional_entries[n].deal_ticket=deal.ticket;
      ep.additional_entries[n].volume=deal.volume;
      ep.additional_entries[n].price=deal.price;
      ep.additional_entries[n].previous_weighted_price=old_weighted;
      ep.additional_entries[n].new_weighted_price=new_weighted;
      ep.additional_entries[n].adverse=adverse;
     }
   ep.weighted_price=new_weighted;
   ep.current_volume=new_volume;
   ep.max_volume=MathMax(ep.max_volume,new_volume);
   NTAppendUlong(ep.entry_tickets,deal.ticket);
   ep.gross_profit+=deal.profit;
   ep.commission+=deal.commission;
   ep.swap+=deal.swap;
   ep.fee+=deal.fee;
   ep.net_profit=ep.gross_profit+ep.commission+ep.swap+ep.fee;
   ep.sltp_evidence_complete=ep.sltp_evidence_complete && deal.sltp_timeline_complete;
   NTObserveSltp(ep,deal);
  }

void NTCloseFromEpisode(NTSignalEpisode &ep,const NTDealRecord &deal)
  {
   NTAppendUlong(ep.exit_tickets,deal.ticket);
   ep.gross_profit+=deal.profit;
   ep.commission+=deal.commission;
   ep.swap+=deal.swap;
   ep.fee+=deal.fee;
   ep.net_profit=ep.gross_profit+ep.commission+ep.swap+ep.fee;
   ep.sltp_evidence_complete=ep.sltp_evidence_complete && deal.sltp_timeline_complete;
   NTObserveSltp(ep,deal);
   ep.current_volume=MathMax(0.0,ep.current_volume-deal.volume);
   if(ep.current_volume<=0.00000001)
     {
      ep.current_volume=0.0;
      ep.open=false;
      ep.final_close_msc=deal.time_msc;
      ep.holding_seconds=(deal.time_msc-ep.first_entry_msc)/1000;
     }
  }

void NTSortDealIndexes(const NTDealRecord &deals[],int &indexes[])
  {
   const int n=ArraySize(deals);
   ArrayResize(indexes,n);
   for(int i=0;i<n;i++) indexes[i]=i;
   for(int i=1;i<n;i++)
     {
      const int value=indexes[i];
      int j=i-1;
      while(j>=0 && (deals[indexes[j]].time_msc>deals[value].time_msc || (deals[indexes[j]].time_msc==deals[value].time_msc && deals[indexes[j]].ticket>deals[value].ticket)))
        {
         indexes[j+1]=indexes[j];
         j--;
        }
      indexes[j+1]=value;
     }
  }

int NTNormalizeDeals(const NTDealRecord &deals[],NTSignalEpisode &episodes[])
  {
   ArrayResize(episodes,0);
   int indexes[];
   NTSortDealIndexes(deals,indexes);
   int sequence=0;
   for(int x=0;x<ArraySize(indexes);x++)
     {
      const NTDealRecord deal=deals[indexes[x]];
      if(!NTDealIsTrading(deal) || deal.position_id==0 || deal.canonical_symbol=="") continue;
      int current=NTFindOpenEpisode(episodes,deal.position_id,deal.canonical_symbol);
      if(deal.entry==DEAL_ENTRY_IN)
        {
         if(current<0) NTCreateEpisode(episodes,deal,++sequence);
         else NTAddEntryToEpisode(episodes[current],deal);
         continue;
        }
      if(deal.entry==DEAL_ENTRY_OUT || deal.entry==DEAL_ENTRY_OUT_BY)
        {
         if(current>=0) NTCloseFromEpisode(episodes[current],deal);
         continue;
        }
      if(deal.entry==DEAL_ENTRY_INOUT)
        {
         double residual=deal.volume;
         if(current>=0)
           {
            const double old_volume=episodes[current].current_volume;
            residual=MathMax(0.0,deal.volume-old_volume);
            NTDealRecord closing=deal;
            closing.volume=MathMin(old_volume,deal.volume);
            NTCloseFromEpisode(episodes[current],closing);
            episodes[current].current_volume=0.0;
            episodes[current].open=false;
            episodes[current].final_close_msc=deal.time_msc;
            episodes[current].holding_seconds=(deal.time_msc-episodes[current].first_entry_msc)/1000;
           }
         if(residual>0.00000001)
           {
            NTDealRecord opening=deal;
            opening.volume=residual;
            opening.profit=0.0;
            opening.commission=0.0;
            opening.swap=0.0;
            opening.fee=0.0;
            NTCreateEpisode(episodes,opening,++sequence);
           }
        }
     }
   return ArraySize(episodes);
  }

void NTFinalizeOpenDurations(NTSignalEpisode &episodes[],const long now_msc,const long program_start_seconds)
  {
   const long week_anchor=(ArraySize(episodes)>0 ? NTWeeklyCountingStart(NTSeconds(episodes[0].first_entry_msc)) : 0);
   for(int i=0;i<ArraySize(episodes);i++)
     {
      if(episodes[i].open) episodes[i].holding_seconds=MathMax(0,(now_msc-episodes[i].first_entry_msc)/1000);
      episodes[i].trading_month_index=NTTradingMonthIndex(NTSeconds(episodes[i].first_entry_msc),program_start_seconds);
      if(week_anchor>0 && NTSeconds(episodes[i].first_entry_msc)>=week_anchor)
         episodes[i].trading_week_start=week_anchor+((NTSeconds(episodes[i].first_entry_msc)-week_anchor)/NT_WEEK_SECONDS)*NT_WEEK_SECONDS;
     }
  }

long NTFirstEpisodeStart(const NTSignalEpisode &episodes[])
  {
   if(ArraySize(episodes)==0) return 0;
   long earliest=NTSeconds(episodes[0].first_entry_msc);
   for(int i=1;i<ArraySize(episodes);i++) earliest=MathMin(earliest,NTSeconds(episodes[i].first_entry_msc));
   return earliest;
  }

bool NTQualificationHorizonComplete(const long program_start_seconds,const long now_seconds)
  {
   if(program_start_seconds<=0 || now_seconds<=program_start_seconds) return false;
   return now_seconds-program_start_seconds>=365L*NT_DAY_SECONDS && NTCompletedMonthCount(program_start_seconds,now_seconds)>=12;
  }

NTStatus NTEvaluateE1(const NTSignalEpisode &episodes[],const bool opening_reason_coverage_complete)
  {
   bool unknown=false;
   for(int i=0;i<ArraySize(episodes);i++)
     {
      if(episodes[i].expert_open_violation) return NT_FAIL;
      if(episodes[i].opening_reason_unknown) unknown=true;
     }
   if(ArraySize(episodes)==0) return NT_IN_PROGRESS;
   if(unknown) return NT_NOT_VERIFIABLE;
   return opening_reason_coverage_complete ? NT_PASS : NT_DATA_GAP;
  }

NTStatus NTEvaluateE5(const NTSignalEpisode &all_episodes[],const long program_start_seconds,const bool product_coverage_complete)
  {
   bool any_during_program=false;
   bool unknown_product=false;
   for(int i=0;i<ArraySize(all_episodes);i++)
     {
      const long opened=NTSeconds(all_episodes[i].first_entry_msc);
      if(program_start_seconds>0 && opened<program_start_seconds) continue;
      any_during_program=true;
      if(!all_episodes[i].product_classification_reliable) unknown_product=true;
      else if(!all_episodes[i].product_eligible) return NT_FAIL;
     }
   if(!any_during_program) return NT_IN_PROGRESS;
   if(unknown_product) return NT_DATA_GAP;
   return product_coverage_complete ? NT_PASS : NT_DATA_GAP;
  }

NTStatus NTEvaluateC6Episode(const NTSignalEpisode &episode)
  {
   if(episode.open)
     {
      if(episode.holding_seconds>=15*60) return NT_PASS;
      return NT_IN_PROGRESS;
     }
   if(episode.holding_seconds>=15*60) return NT_PASS;
   if(episode.max_sltp_distance_pips>30.0) return NT_PASS;
   return episode.sltp_evidence_complete ? NT_FAIL : NT_NOT_VERIFIABLE;
  }

int NTCountC6ConfirmedViolations(const NTSignalEpisode &episodes[],const int month_index)
  {
   int count=0;
   for(int i=0;i<ArraySize(episodes);i++)
      if(episodes[i].trading_month_index==month_index && NTEvaluateC6Episode(episodes[i])==NT_FAIL) count++;
   return count;
  }

bool NTC5EpisodeActiveAt(const NTSignalEpisode &episode,const long time_msc)
  {
   return episode.first_entry_msc<=time_msc && (episode.open || episode.final_close_msc>time_msc);
  }

void NTAppendC5Occurrence(NTC5Occurrence &occurrences[],const NTSignalEpisode &episode,const long time_msc,const ulong order_ticket,const ulong deal_ticket,const int occurrence_number)
  {
   const int n=ArraySize(occurrences);
   ArrayResize(occurrences,n+1);
   occurrences[n].month_index=episode.trading_month_index;
   occurrences[n].time_msc=time_msc;
   occurrences[n].canonical_symbol=episode.canonical_symbol;
   occurrences[n].broker_symbol=episode.broker_symbol;
   occurrences[n].session=NTAssignSession(NTSeconds(time_msc));
   occurrences[n].episode_id=episode.episode_id;
   occurrences[n].position_id=episode.position_id;
   occurrences[n].order_ticket=order_ticket;
   occurrences[n].deal_ticket=deal_ticket;
   occurrences[n].occurrence_number=occurrence_number;
  }

int NTBuildC5Occurrences(const NTSignalEpisode &episodes[],const int month_index,NTC5Occurrence &occurrences[])
  {
   ArrayResize(occurrences,0);
   for(int i=0;i<ArraySize(episodes);i++)
     {
      if(month_index>=0 && episodes[i].trading_month_index!=month_index) continue;
      int active_before=0;
      for(int j=0;j<ArraySize(episodes);j++)
        {
         if(i==j || episodes[j].canonical_symbol!=episodes[i].canonical_symbol) continue;
         const bool earlier=episodes[j].first_entry_msc<episodes[i].first_entry_msc
            || (episodes[j].first_entry_msc==episodes[i].first_entry_msc && episodes[j].opening_deal_ticket<episodes[i].opening_deal_ticket);
         if(earlier && NTC5EpisodeActiveAt(episodes[j],episodes[i].first_entry_msc)) active_before++;
        }
      if(active_before>0) NTAppendC5Occurrence(occurrences,episodes[i],episodes[i].first_entry_msc,episodes[i].opening_order_ticket,episodes[i].opening_deal_ticket,active_before+1);
      for(int a=0;a<ArraySize(episodes[i].additional_entries);a++)
        {
         const NTAdditionalEntryEvidence added=episodes[i].additional_entries[a];
         NTAppendC5Occurrence(occurrences,episodes[i],added.time_msc,added.order_ticket,added.deal_ticket,2+a);
        }
     }
   return ArraySize(occurrences);
  }

int NTCountC5ConfirmedViolations(const NTSignalEpisode &episodes[],const int month_index)
  {
   NTC5Occurrence occurrences[];
   return NTBuildC5Occurrences(episodes,month_index,occurrences);
  }

NTStatus NTEvaluateC5(const NTSignalEpisode &episodes[],const bool history_coverage_complete,const bool qualification_horizon_complete)
  {
   NTC5Occurrence occurrences[];
   if(NTBuildC5Occurrences(episodes,-1,occurrences)>0) return NT_FAIL;
   if(ArraySize(episodes)==0) return NT_IN_PROGRESS;
   if(!history_coverage_complete) return NT_DATA_GAP;
   return qualification_horizon_complete ? NT_PASS : NT_IN_PROGRESS;
  }

bool NTIntervalsOverlap(const NTSignalEpisode &a,const NTSignalEpisode &b,const long now_msc)
  {
   const long a_end=a.open ? now_msc : a.final_close_msc;
   const long b_end=b.open ? now_msc : b.final_close_msc;
   return a.first_entry_msc<b_end && b.first_entry_msc<a_end;
  }

int NTBuildHedgingEvidence(const NTSignalEpisode &episodes[],const long now_msc,NTHedgingEvidence &evidence[])
  {
   ArrayResize(evidence,0);
   for(int i=0;i<ArraySize(episodes);i++)
      for(int j=i+1;j<ArraySize(episodes);j++)
        {
         if(episodes[i].canonical_symbol!=episodes[j].canonical_symbol || episodes[i].direction==episodes[j].direction || episodes[i].position_id==episodes[j].position_id || !NTIntervalsOverlap(episodes[i],episodes[j],now_msc)) continue;
         const int n=ArraySize(evidence);
         ArrayResize(evidence,n+1);
         const long first_end=(episodes[i].open ? now_msc : episodes[i].final_close_msc);
         const long second_end=(episodes[j].open ? now_msc : episodes[j].final_close_msc);
         evidence[n].overlap_start_msc=MathMax(episodes[i].first_entry_msc,episodes[j].first_entry_msc);
         evidence[n].overlap_end_msc=MathMin(first_end,second_end);
         evidence[n].canonical_symbol=episodes[i].canonical_symbol;
         evidence[n].broker_symbol=episodes[j].broker_symbol;
         evidence[n].first_position_id=episodes[i].position_id;
         evidence[n].second_position_id=episodes[j].position_id;
         evidence[n].first_order_ticket=episodes[i].opening_order_ticket;
         evidence[n].second_order_ticket=episodes[j].opening_order_ticket;
         evidence[n].first_deal_ticket=episodes[i].opening_deal_ticket;
         evidence[n].second_deal_ticket=episodes[j].opening_deal_ticket;
         evidence[n].first_direction=episodes[i].direction;
         evidence[n].second_direction=episodes[j].direction;
        }
   return ArraySize(evidence);
  }

bool NTHasConfirmedHedging(const NTSignalEpisode &episodes[],const long now_msc)
  {
   NTHedgingEvidence evidence[];
   return NTBuildHedgingEvidence(episodes,now_msc,evidence)>0;
  }

NTStatus NTEvaluateC6(const NTSignalEpisode &episodes[],const bool sltp_coverage_complete,const bool qualification_horizon_complete)
  {
   bool unknown=false;
   bool open_in_progress=false;
   for(int i=0;i<ArraySize(episodes);i++)
     {
      const NTStatus status=NTEvaluateC6Episode(episodes[i]);
      if(status==NT_FAIL) return NT_FAIL;
      if(status==NT_NOT_VERIFIABLE) unknown=true;
      if(status==NT_IN_PROGRESS) open_in_progress=true;
     }
   if(ArraySize(episodes)==0) return NT_IN_PROGRESS;
   if(unknown) return NT_NOT_VERIFIABLE;
   if(!sltp_coverage_complete) return NT_DATA_GAP;
   if(open_in_progress || !qualification_horizon_complete) return NT_IN_PROGRESS;
   return NT_PASS;
  }

NTStatus NTEvaluateC7(const NTSignalEpisode &episodes[],const long now_msc,const bool history_coverage_complete,const bool qualification_horizon_complete)
  {
   if(NTHasConfirmedHedging(episodes,now_msc)) return NT_FAIL;
   if(ArraySize(episodes)==0) return NT_IN_PROGRESS;
   if(!history_coverage_complete) return NT_DATA_GAP;
   return qualification_horizon_complete ? NT_PASS : NT_IN_PROGRESS;
  }

int NTBuildWeeks(const NTSignalEpisode &episodes[],const long now_seconds,NTWeekResult &weeks[])
  {
   ArrayResize(weeks,0);
   if(ArraySize(episodes)==0) return 0;
   const long start=NTWeeklyCountingStart(NTSeconds(episodes[0].first_entry_msc));
   if(now_seconds<start) return 0;
   const int total=(int)((now_seconds-start)/NT_WEEK_SECONDS)+1;
   ArrayResize(weeks,total);
   for(int i=0;i<total;i++)
     {
      weeks[i].start_time=start+(long)i*NT_WEEK_SECONDS;
      weeks[i].end_time=weeks[i].start_time+NT_WEEK_SECONDS;
      weeks[i].signal_count=0;
      weeks[i].target=3;
      weeks[i].missing=3;
      weeks[i].manual_pause=false;
      weeks[i].status=(now_seconds>=weeks[i].end_time ? NT_FAIL : NT_IN_PROGRESS);
     }
   for(int e=0;e<ArraySize(episodes);e++)
     {
      const long t=NTSeconds(episodes[e].first_entry_msc);
      if(t<start) continue;
      const int index=(int)((t-start)/NT_WEEK_SECONDS);
      if(index>=0 && index<total) weeks[index].signal_count++;
     }
   for(int i=0;i<total;i++)
     {
      weeks[i].missing=MathMax(0,3-weeks[i].signal_count);
      if(now_seconds<weeks[i].end_time) weeks[i].status=NT_IN_PROGRESS;
      else weeks[i].status=(weeks[i].signal_count>=3 ? NT_PASS : NT_FAIL);
     }
   return total;
  }

NTStatus NTEvaluateC4(const NTWeekResult &weeks[],const bool history_coverage_complete,const bool qualification_horizon_complete)
  {
   bool manual_unknown=false;
   for(int i=0;i<ArraySize(weeks);i++)
     {
      if(weeks[i].status==NT_FAIL) return NT_FAIL;
      if(weeks[i].manual_pause && weeks[i].status==NT_NOT_VERIFIABLE) manual_unknown=true;
      if(weeks[i].status==NT_DATA_GAP) return NT_DATA_GAP;
     }
   if(manual_unknown) return NT_NOT_VERIFIABLE;
   if(!history_coverage_complete) return NT_DATA_GAP;
   if(!qualification_horizon_complete) return NT_IN_PROGRESS;
   return NT_PASS;
  }

int NTCompletedMonthCount(const long program_start_seconds,const long now_seconds)
  {
   if(program_start_seconds<=0 || now_seconds<=program_start_seconds) return 0;
   return (int)((now_seconds-program_start_seconds)/NT_MONTH_SECONDS);
  }

NTStatus NTEvaluateC1(const long program_start_seconds,const long now_seconds,const bool full_history)
  {
   if(program_start_seconds<=0) return NT_IN_PROGRESS;
   if(!full_history) return NT_DATA_GAP;
   const long elapsed=now_seconds-program_start_seconds;
   const int windows=NTCompletedMonthCount(program_start_seconds,now_seconds);
   if(elapsed>=365L*NT_DAY_SECONDS && windows>=12) return NT_PASS;
   return NT_IN_PROGRESS;
  }

int NTBuildMonths(const NTSignalEpisode &episodes[],const NTCashFlow &cashflows[],const long program_start_seconds,const long now_seconds,const double starting_balance,NTMonthResult &months[])
  {
   ArrayResize(months,0);
   if(program_start_seconds<=0 || starting_balance<=0.0) return 0;
   const int count=NTCompletedMonthCount(program_start_seconds,now_seconds)+1;
   ArrayResize(months,count);
   double balance=starting_balance;
   for(int i=0;i<count;i++)
     {
      NTMonthResult row;
      row.start_time=NTTradingMonthStart(program_start_seconds,i);
      row.end_time=row.start_time+NT_MONTH_SECONDS;
      row.opening_balance=balance;
      row.trading_net_pl=0.0;
      row.deposits=0.0;
      row.withdrawals=0.0;
      row.other_cash_flow=0.0;
      for(int e=0;e<ArraySize(episodes);e++)
        {
         if(episodes[e].open || episodes[e].final_close_msc<=0) continue;
         const long close_time=NTSeconds(episodes[e].final_close_msc);
         if(close_time>=row.start_time && close_time<row.end_time) row.trading_net_pl+=episodes[e].net_profit;
        }
      for(int c=0;c<ArraySize(cashflows);c++)
        {
         const long t=NTSeconds(cashflows[c].time_msc);
         if(t<row.start_time || t>=row.end_time) continue;
         if(cashflows[c].kind==1) row.deposits+=MathMax(0.0,cashflows[c].amount);
         else if(cashflows[c].kind==-1) row.withdrawals+=MathAbs(MathMin(0.0,cashflows[c].amount));
         else row.other_cash_flow+=cashflows[c].amount;
        }
      const double net_cash=row.deposits-row.withdrawals+row.other_cash_flow;
      const double closing=balance+row.trading_net_pl+net_cash;
      row.raw_return_pct=(balance>0.0 ? (closing-balance)/balance*100.0 : 0.0);
      row.adjusted_return_pct=(balance>0.0 ? row.trading_net_pl/balance*100.0 : 0.0);
      if(now_seconds<row.end_time) row.status=NT_IN_PROGRESS;
      else row.status=(row.adjusted_return_pct>=1.0 ? NT_PASS : NT_FAIL);
      months[i]=row;
      balance=closing;
     }
   return count;
  }

NTStatus NTEvaluateC2(const NTMonthResult &months[],const bool full_history)
  {
   if(!full_history) return NT_DATA_GAP;
   int completed=0;
   for(int i=0;i<ArraySize(months);i++)
     {
      if(months[i].status==NT_FAIL) return NT_FAIL;
      if(months[i].status==NT_PASS) completed++;
     }
   return completed>=12 ? NT_PASS : NT_IN_PROGRESS;
  }

int NTCountDepositsWithdrawals(const NTCashFlow &cashflows[])
  {
   int count=0;
   for(int i=0;i<ArraySize(cashflows);i++) if(cashflows[i].kind==1 || cashflows[i].kind==-1) count++;
   return count;
  }

NTStatus NTEvaluateC9(const NTCashFlow &cashflows[],const bool history_coverage_complete,const bool qualification_horizon_complete)
  {
   if(NTCountDepositsWithdrawals(cashflows)>0) return NT_FAIL;
   if(!history_coverage_complete) return NT_DATA_GAP;
   return qualification_horizon_complete ? NT_PASS : NT_IN_PROGRESS;
  }

 double NTAggregateEquity(const double balance,const double &unrealized_profit[])
  {
   double equity=balance;
   for(int i=0;i<ArraySize(unrealized_profit);i++) equity+=unrealized_profit[i];
   return equity;
  }

double NTFloatingLossPct(const double balance,const double equity)
  {
   if(balance<=0.0) return 0.0;
   return MathMax(0.0,(balance-equity)/balance*100.0);
  }

double NTPeakToTroughPct(const double peak_equity,const double equity)
  {
   if(peak_equity<=0.0) return 0.0;
   return MathMax(0.0,(peak_equity-equity)/peak_equity*100.0);
  }

int NTDisqualificationRisk(const int c5_count,const int c6_count,const bool counters_complete)
  {
   if(c5_count>=3 || c6_count>=3 || c5_count+c6_count>=3) return 1;
   return counters_complete ? 0 : -1;
  }

bool NTHistorySupportsFullYear(const long earliest_available_seconds,const long now_seconds)
  {
   return earliest_available_seconds>0 && now_seconds-earliest_available_seconds>=365L*NT_DAY_SECONDS;
  }

double NTHistoryCoveragePct(const long earliest_available_seconds,const long now_seconds)
  {
   if(earliest_available_seconds<=0 || now_seconds<=earliest_available_seconds) return 0.0;
   return MathMin(100.0,(double)(now_seconds-earliest_available_seconds)/(365.0*NT_DAY_SECONDS)*100.0);
  }

void NTSetCriterion(NTCriterionState &row,const string id,const NTStatus status,const string reason,const string vi)
  {
   row.id=id;
   row.status=status;
   row.reason_code=reason;
   row.explanation_vi=vi;
  }

#endif // OAK_NEOTECH_COMPLIANCE_CORE_MQH
