#ifndef OAK_NEOTECH_COMPLIANCE_JSON_MQH
#define OAK_NEOTECH_COMPLIANCE_JSON_MQH

string NTJsonEscape(const string value)
  {
   string out="";
   for(int i=0;i<StringLen(value);i++)
     {
      const ushort c=StringGetCharacter(value,i);
      if(c=='\\') out+="\\\\";
      else if(c=='\"') out+="\\\"";
      else if(c==8) out+="\\b";
      else if(c==12) out+="\\f";
      else if(c==10) out+="\\n";
      else if(c==13) out+="\\r";
      else if(c==9) out+="\\t";
      else if(c<32) out+=StringFormat("\\u%04x",(int)c);
      else out+=ShortToString(c);
     }
   return out;
  }

string NTJsonQuote(const string value)
  {
   return "\""+NTJsonEscape(value)+"\"";
  }

string NTJsonBool(const bool value)
  {
   return value ? "true" : "false";
  }

string NTJsonNumber(const double value,const int digits=8)
  {
   if(!MathIsValidNumber(value)) return "null";
   string text=DoubleToString(value,digits);
   while(StringFind(text,".")>=0 && StringSubstr(text,StringLen(text)-1)=="0") text=StringSubstr(text,0,StringLen(text)-1);
   if(StringSubstr(text,StringLen(text)-1)==".") text=StringSubstr(text,0,StringLen(text)-1);
   return text;
  }

string NTJsonLongOrNull(const long value)
  {
   return value>0 ? IntegerToString(value) : "null";
  }

string NTHex(const uchar &bytes[])
  {
   string out="";
   for(int i=0;i<ArraySize(bytes);i++) out+=StringFormat("%02x",(int)bytes[i]);
   return out;
  }

string NTSha256Hex(const string text)
  {
   uchar bytes[],key[],hash[];
   const int chars=StringLen(text);
   if(StringToCharArray(text,bytes,0,chars,CP_UTF8)<=0) return "";
   if(CryptEncode(CRYPT_HASH_SHA256,bytes,key,hash)<=0) return "";
   return NTHex(hash);
  }

string NTDateTimeText(const long epoch_seconds)
  {
   if(epoch_seconds<=0) return "";
   MqlDateTime dt;
   TimeToStruct((datetime)epoch_seconds,dt);
   return StringFormat("%04d-%02d-%02d %02d:%02d:%02d",dt.year,dt.mon,dt.day,dt.hour,dt.min,dt.sec);
  }

int NTServerUtcOffsetMinutes(const long server_seconds)
  {
   return NTIsSummer(server_seconds) ? 180 : 120;
  }

long NTUtcSecondsFromNeoTechServer(const long server_seconds)
  {
   if(server_seconds<=0) return 0;
   return server_seconds-(long)NTServerUtcOffsetMinutes(server_seconds)*60L;
  }

long NTVietnamSecondsFromNeoTechServer(const long server_seconds)
  {
   const long utc=NTUtcSecondsFromNeoTechServer(server_seconds);
   return utc>0 ? utc+7L*3600L : 0;
  }

string NTUtcTimeTextFromNeoTechServer(const long server_seconds)
  {
   return NTDateTimeText(NTUtcSecondsFromNeoTechServer(server_seconds));
  }

string NTVietnamTimeText(const long server_seconds)
  {
   return NTDateTimeText(NTVietnamSecondsFromNeoTechServer(server_seconds));
  }

string NTTimePointJson(const long server_seconds)
  {
   if(server_seconds<=0) return "null";
   return "{\"serverLocal\":"+NTJsonQuote(NTDateTimeText(server_seconds))
      +",\"serverUtcOffsetMinutes\":"+IntegerToString(NTServerUtcOffsetMinutes(server_seconds))
      +",\"utcEpoch\":"+IntegerToString(NTUtcSecondsFromNeoTechServer(server_seconds))
      +",\"utc\":"+NTJsonQuote(NTUtcTimeTextFromNeoTechServer(server_seconds))
      +",\"vietnam\":"+NTJsonQuote(NTVietnamTimeText(server_seconds))+"}";
  }

string NTMaskedAccount(const long login)
  {
   string raw=IntegerToString(login);
   const int n=StringLen(raw);
   const int keep=MathMin(4,n);
   string mask="";
   for(int i=0;i<MathMax(2,n-keep);i++) mask+="*";
   return mask+StringSubstr(raw,n-keep,keep);
  }

string NTJsonStringArray(const string &values[])
  {
   string out="[";
   for(int i=0;i<ArraySize(values);i++)
     {
      if(i>0) out+=",";
      out+=NTJsonQuote(values[i]);
     }
   return out+"]";
  }

string NTJsonUlongArray(const ulong &values[])
  {
   string out="[";
   for(int i=0;i<ArraySize(values);i++)
     {
      if(i>0) out+=",";
      out+=NTJsonQuote(StringFormat("%I64u",values[i]));
     }
   return out+"]";
  }

string NTHedgingEvidenceJson(const NTHedgingEvidence &value)
  {
   return "{\"overlapStartMsc\":"+IntegerToString(value.overlap_start_msc)
      +",\"overlapEndMsc\":"+IntegerToString(value.overlap_end_msc)
      +",\"canonicalSymbol\":"+NTJsonQuote(value.canonical_symbol)
      +",\"brokerSymbol\":"+NTJsonQuote(value.broker_symbol)
      +",\"positionIds\":["+NTJsonQuote(StringFormat("%I64u",value.first_position_id))+","+NTJsonQuote(StringFormat("%I64u",value.second_position_id))+"]"
      +",\"orderTickets\":["+NTJsonQuote(StringFormat("%I64u",value.first_order_ticket))+","+NTJsonQuote(StringFormat("%I64u",value.second_order_ticket))+"]"
      +",\"dealTickets\":["+NTJsonQuote(StringFormat("%I64u",value.first_deal_ticket))+","+NTJsonQuote(StringFormat("%I64u",value.second_deal_ticket))+"]"
      +",\"directions\":["+NTJsonQuote(value.first_direction>0?"BUY":"SELL")+","+NTJsonQuote(value.second_direction>0?"BUY":"SELL")+"]}";
  }

string NTAdditionalEntryEvidenceJson(const NTAdditionalEntryEvidence &value)
  {
   return "{\"timeMsc\":"+IntegerToString(value.time_msc)
      +",\"orderTicket\":"+NTJsonQuote(StringFormat("%I64u",value.order_ticket))
      +",\"dealTicket\":"+NTJsonQuote(StringFormat("%I64u",value.deal_ticket))
      +",\"volume\":"+NTJsonNumber(value.volume,8)
      +",\"price\":"+NTJsonNumber(value.price,8)
      +",\"previousWeightedPrice\":"+NTJsonNumber(value.previous_weighted_price,8)
      +",\"newWeightedPrice\":"+NTJsonNumber(value.new_weighted_price,8)
      +",\"adverse\":"+NTJsonBool(value.adverse)+"}";
  }

#endif // OAK_NEOTECH_COMPLIANCE_JSON_MQH
