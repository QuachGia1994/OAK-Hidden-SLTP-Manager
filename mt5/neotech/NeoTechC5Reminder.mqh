#ifndef OAK_NEOTECH_C5_REMINDER_MQH
#define OAK_NEOTECH_C5_REMINDER_MQH

#define NC5_DAY_SECONDS 86400

enum NC5Session
  {
   NC5_OUTSIDE_SESSION=0,
   NC5_ASIA=1,
   NC5_EUROPE=2,
   NC5_US=3
  };

string NC5Trim(string value)
  {
   StringTrimLeft(value);
   StringTrimRight(value);
   return value;
  }

string NC5Lower(string value)
  {
   StringToLower(value);
   return value;
  }

bool NC5IsWhitespace(const ushort value)
  {
   return value==32 || value==9 || value==10 || value==13;
  }

bool NC5IsSignedIntegerText(const string value)
  {
   const string text=NC5Trim(value);
   if(text=="") return false;
   int start=0;
   const ushort first=StringGetCharacter(text,0);
   if(first=='-' || first=='+')
     {
      if(StringLen(text)==1) return false;
      start=1;
     }
   for(int i=start;i<StringLen(text);i++)
     {
      const ushort c=StringGetCharacter(text,i);
      if(c<'0' || c>'9') return false;
     }
   return true;
  }

string NC5JsonEscape(const string value)
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

string NC5JsonQuote(const string value)
  {
   return "\""+NC5JsonEscape(value)+"\"";
  }

string NC5Hex(const uchar &bytes[])
  {
   string out="";
   for(int i=0;i<ArraySize(bytes);i++) out+=StringFormat("%02x",(int)bytes[i]);
   return out;
  }

string NC5Sha256Hex(const string text)
  {
   uchar bytes[],key[],hash[];
   const int chars=StringLen(text);
   if(StringToCharArray(text,bytes,0,chars,CP_UTF8)<=0) return "";
   if(CryptEncode(CRYPT_HASH_SHA256,bytes,key,hash)<=0) return "";
   return NC5Hex(hash);
  }

string NC5DateTimeText(const long epoch_seconds)
  {
   if(epoch_seconds<=0) return "";
   MqlDateTime dt;
   TimeToStruct((datetime)epoch_seconds,dt);
   return StringFormat("%04d-%02d-%02d %02d:%02d:%02d",dt.year,dt.mon,dt.day,dt.hour,dt.min,dt.sec);
  }

bool NC5IsSummer(const long server_seconds)
  {
   MqlDateTime dt;
   TimeToStruct((datetime)server_seconds,dt);
   return dt.mon>=4 && dt.mon<=10;
  }

int NC5MinuteOfDay(const long server_seconds)
  {
   MqlDateTime dt;
   TimeToStruct((datetime)server_seconds,dt);
   return dt.hour*60+dt.min;
  }

bool NC5HalfOpen(const int minute,const int start_minute,const int end_minute)
  {
   return minute>=start_minute && minute<end_minute;
  }

// NeoTech overlap priority is Asia -> Europe -> US, so overlap stays in the earlier session.
NC5Session NC5AssignSession(const long server_seconds)
  {
   const int minute=NC5MinuteOfDay(server_seconds);
   const bool summer=NC5IsSummer(server_seconds);
   if(NC5HalfOpen(minute,2*60,11*60)) return NC5_ASIA;
   if(summer)
     {
      if(NC5HalfOpen(minute,9*60,18*60)) return NC5_EUROPE;
      if(NC5HalfOpen(minute,14*60,23*60)) return NC5_US;
     }
   else
     {
      if(NC5HalfOpen(minute,10*60,19*60)) return NC5_EUROPE;
      if(NC5HalfOpen(minute,15*60,24*60)) return NC5_US;
     }
   return NC5_OUTSIDE_SESSION;
  }

bool NC5NextReentry(const long opened_server_seconds,NC5Session &current_session,NC5Session &next_session,long &next_start_server_seconds)
  {
   current_session=NC5AssignSession(opened_server_seconds);
   next_session=NC5_OUTSIDE_SESSION;
   next_start_server_seconds=0;
   if(opened_server_seconds<=0 || current_session==NC5_OUTSIDE_SESSION) return false;
   long cursor=opened_server_seconds-(opened_server_seconds%60)+60;
   const long limit=opened_server_seconds+2L*NC5_DAY_SECONDS;
   while(cursor<=limit)
     {
      const NC5Session candidate=NC5AssignSession(cursor);
      if(candidate!=NC5_OUTSIDE_SESSION && candidate!=current_session)
        {
         next_session=candidate;
         next_start_server_seconds=cursor;
         return true;
        }
      cursor+=60;
     }
   return false;
  }

int NC5ServerUtcOffsetMinutes(const long server_seconds)
  {
   return NC5IsSummer(server_seconds) ? 180 : 120;
  }

long NC5VietnamSecondsFromServer(const long server_seconds)
  {
   if(server_seconds<=0) return 0;
   return server_seconds-(long)NC5ServerUtcOffsetMinutes(server_seconds)*60L+7L*3600L;
  }

string NC5VietnamTimeText(const long server_seconds)
  {
   return NC5DateTimeText(NC5VietnamSecondsFromServer(server_seconds));
  }

string NC5SessionVi(const NC5Session session)
  {
   if(session==NC5_ASIA) return "Á";
   if(session==NC5_EUROPE) return "ÂU";
   if(session==NC5_US) return "MỸ";
   return "NGOÀI PHIÊN";
  }

string NC5UtcOffsetText(const int minutes)
  {
   const int hours=minutes/60;
   return "UTC"+(hours>=0?"+":"")+IntegerToString(hours);
  }

string NC5ReminderText(const string canonical_symbol,const long opened_server_seconds)
  {
   const NC5Session opened_session=NC5AssignSession(opened_server_seconds);
   const string opened_vietnam=NC5VietnamTimeText(opened_server_seconds);
   if(opened_session==NC5_OUTSIDE_SESSION)
      return "⚠️ NeoTech C5 · "+canonical_symbol
         +"\nĐã mở: "+opened_vietnam+" VN · NGOÀI PHIÊN"
         +"\nC5: KHÔNG XÁC MINH. Không tự coi là được vào lại cho tới khi kiểm tra thủ công.";
   NC5Session current_session=NC5_OUTSIDE_SESSION;
   NC5Session next_session=NC5_OUTSIDE_SESSION;
   long next_start_server_seconds=0;
   if(!NC5NextReentry(opened_server_seconds,current_session,next_session,next_start_server_seconds))
      return "⚠️ NeoTech C5 · "+canonical_symbol+"\nC5: chưa xác định được mốc vào lại an toàn.";
   return "⏱ NeoTech C5 · "+canonical_symbol
      +"\nĐã mở: "+opened_vietnam+" VN · phiên "+NC5SessionVi(current_session)
      +"\nKhông vào lại "+canonical_symbol+" trong phiên "+NC5SessionVi(current_session)+"."
      +"\nĐược vào lại sớm nhất theo C5: phiên "+NC5SessionVi(next_session)+" · "+NC5VietnamTimeText(next_start_server_seconds)+" VN"
      +"\nServer: "+NC5DateTimeText(next_start_server_seconds)+" · "+NC5UtcOffsetText(NC5ServerUtcOffsetMinutes(next_start_server_seconds));
  }

bool NC5ResolveEligibleProduct(const string broker_symbol,string &canonical)
  {
   canonical="";
   const string base=SymbolInfoString(broker_symbol,SYMBOL_CURRENCY_BASE);
   const string profit=SymbolInfoString(broker_symbol,SYMBOL_CURRENCY_PROFIT);
   long calc=0;
   const bool calc_ok=SymbolInfoInteger(broker_symbol,SYMBOL_TRADE_CALC_MODE,calc);
   if(!calc_ok || base=="" || profit=="") return false;
   const bool forex_calc=(calc==SYMBOL_CALC_MODE_FOREX || calc==SYMBOL_CALC_MODE_FOREX_NO_LEVERAGE);
   const bool forex=forex_calc && StringLen(base)==3 && StringLen(profit)==3;
   const bool gold=(base=="XAU" && profit=="USD");
   if(!forex && !gold) return false;
   canonical=base+profit;
   return true;
  }

int NC5JsonSkipWhitespace(const string json,int position)
  {
   while(position<StringLen(json) && NC5IsWhitespace(StringGetCharacter(json,position))) position++;
   return position;
  }

int NC5JsonHexDigit(const ushort c)
  {
   if(c>='0' && c<='9') return (int)(c-'0');
   if(c>='a' && c<='f') return 10+(int)(c-'a');
   if(c>='A' && c<='F') return 10+(int)(c-'A');
   return -1;
  }

bool NC5JsonReadRawValue(const string json,const string key,string &raw)
  {
   raw="";
   const string needle=NC5JsonQuote(key);
   int search=0;
   while(search<StringLen(json))
     {
      const int found=StringFind(json,needle,search);
      if(found<0) return false;
      int position=NC5JsonSkipWhitespace(json,found+StringLen(needle));
      if(position>=StringLen(json) || StringGetCharacter(json,position)!=':')
        {
         search=found+StringLen(needle);
         continue;
        }
      position=NC5JsonSkipWhitespace(json,position+1);
      if(position>=StringLen(json)) return false;
      const int start=position;
      const ushort first=StringGetCharacter(json,position);
      if(first=='\"')
        {
         bool escaped=false;
         for(position=start+1;position<StringLen(json);position++)
           {
            const ushort c=StringGetCharacter(json,position);
            if(escaped) { escaped=false; continue; }
            if(c=='\\') { escaped=true; continue; }
            if(c=='\"')
              {
               raw=StringSubstr(json,start,position-start+1);
               return true;
              }
           }
         return false;
        }
      position=start;
      while(position<StringLen(json))
        {
         const ushort c=StringGetCharacter(json,position);
         if(c==',' || c=='}' || c==']') break;
         position++;
        }
      raw=NC5Trim(StringSubstr(json,start,position-start));
      return raw!="";
     }
   return false;
  }

string NC5JsonDecodeStringRaw(const string raw)
  {
   if(StringLen(raw)<2 || StringGetCharacter(raw,0)!='\"' || StringGetCharacter(raw,StringLen(raw)-1)!='\"') return raw;
   string out="";
   for(int i=1;i<StringLen(raw)-1;i++)
     {
      ushort c=StringGetCharacter(raw,i);
      if(c!='\\')
        {
         out+=ShortToString(c);
         continue;
        }
      if(i+1>=StringLen(raw)-1) break;
      c=StringGetCharacter(raw,++i);
      if(c=='\"' || c=='\\' || c=='/') out+=ShortToString(c);
      else if(c=='b') out+=ShortToString(8);
      else if(c=='f') out+=ShortToString(12);
      else if(c=='n') out+="\n";
      else if(c=='r') out+="\r";
      else if(c=='t') out+="\t";
      else if(c=='u' && i+4<StringLen(raw)-1)
        {
         int code=0;
         bool valid=true;
         for(int h=1;h<=4;h++)
           {
            const int digit=NC5JsonHexDigit(StringGetCharacter(raw,i+h));
            if(digit<0) { valid=false; break; }
            code=code*16+digit;
           }
         if(valid)
           {
            out+=ShortToString((ushort)code);
            i+=4;
           }
         else out+="u";
        }
      else out+=ShortToString(c);
     }
   return out;
  }

bool NC5JsonGetString(const string json,const string key,string &value)
  {
   string raw="";
   if(!NC5JsonReadRawValue(json,key,raw)) return false;
   if(StringLen(raw)<2 || StringGetCharacter(raw,0)!='\"') return false;
   value=NC5JsonDecodeStringRaw(raw);
   return true;
  }

bool NC5JsonGetLong(const string json,const string key,long &value)
  {
   string raw="";
   if(!NC5JsonReadRawValue(json,key,raw) || !NC5IsSignedIntegerText(raw)) return false;
   value=StringToInteger(raw);
   return true;
  }

#endif // OAK_NEOTECH_C5_REMINDER_MQH
