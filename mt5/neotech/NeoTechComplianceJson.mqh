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

enum NTTelegramView
  {
   NT_TG_VIEW_SUMMARY=0,
   NT_TG_VIEW_VIOLATIONS=1,
   NT_TG_VIEW_CRITERION=2
  };

enum NTTelegramWebhookAction
  {
   NT_TG_WEBHOOK_ERROR=-1,
   NT_TG_WEBHOOK_READY=0,
   NT_TG_WEBHOOK_BLOCK=1,
   NT_TG_WEBHOOK_DELETE=2
  };

struct NTTelegramCheckCommand
  {
   bool              slug_matches;
   NTTelegramView    view;
   int               page;
   string            criterion;
  };

string NTStringLower(const string value)
  {
   string out=value;
   StringToLower(out);
   return out;
  }

string NTStringUpper(const string value)
  {
   string out=value;
   StringToUpper(out);
   return out;
  }

string NTStringTrimmed(const string value)
  {
   string out=value;
   StringTrimLeft(out);
   StringTrimRight(out);
   return out;
  }

string NTTelegramStatusVi(const string status)
  {
   if(status=="PASS") return "ĐẠT";
   if(status=="FAIL") return "VI PHẠM";
   if(status=="IN_PROGRESS") return "ĐANG THEO DÕI";
   if(status=="NOT_VERIFIABLE") return "CHƯA XÁC MINH";
   if(status=="DATA_GAP") return "THIẾU DỮ LIỆU";
   if(status=="RECONSTRUCTED") return "DỮ LIỆU PHỤC DỰNG";
   return status;
  }

string NTTelegramRiskVi(const string risk)
  {
   if(risk=="YES") return "CÓ";
   if(risk=="NO") return "KHÔNG";
   return "CHƯA RÕ";
  }

string NTTelegramFddMethodVi(const string method)
  {
   if(method=="EXACT") return "Dữ liệu trực tiếp";
   if(method=="RECONSTRUCTED") return "Phục dựng từ tick";
   if(method=="M1") return "Phục dựng từ nến M1";
   if(method=="DATA_GAP") return "Thiếu dữ liệu giá";
   return method;
  }

bool NTIsWhitespace(const ushort c)
  {
   return c==32 || c==9 || c==10 || c==13;
  }

int NTSplitWhitespace(const string value,string &parts[])
  {
   ArrayResize(parts,0);
   string current="";
   for(int i=0;i<StringLen(value);i++)
     {
      const ushort c=StringGetCharacter(value,i);
      if(NTIsWhitespace(c))
        {
         if(current!="")
           {
            const int n=ArraySize(parts);
            ArrayResize(parts,n+1);
            parts[n]=current;
            current="";
           }
         continue;
        }
      current+=ShortToString(c);
     }
   if(current!="")
     {
      const int n=ArraySize(parts);
      ArrayResize(parts,n+1);
      parts[n]=current;
     }
   return ArraySize(parts);
  }

bool NTIsPositiveIntegerText(const string value)
  {
   if(value=="") return false;
   for(int i=0;i<StringLen(value);i++)
     {
      const ushort c=StringGetCharacter(value,i);
      if(c<'0' || c>'9') return false;
     }
   return StringToInteger(value)>0;
  }

bool NTIsSignedIntegerText(const string value)
  {
   const string text=NTStringTrimmed(value);
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

bool NTTelegramCriterionToken(const string value)
  {
   const string upper=NTStringUpper(value);
   if(StringLen(upper)!=2) return false;
   const ushort family=StringGetCharacter(upper,0);
   const ushort number=StringGetCharacter(upper,1);
   if(family!='C' && family!='E') return false;
   if(number<'1' || number>'9') return false;
   if(family=='E' && number>'5') return false;
   return true;
  }

bool NTTelegramParseCheckCommand(const string text,const string expected_profile,NTTelegramCheckCommand &cmd)
  {
   cmd.slug_matches=false;
   cmd.view=NT_TG_VIEW_SUMMARY;
   cmd.page=1;
   cmd.criterion="";

   string parts[];
   const int count=NTSplitWhitespace(text,parts);
   if(count<2 || count>4) return false;

   const string command=NTStringLower(parts[0]);
   if(command!="/check")
     {
      if(StringFind(command,"/check@")!=0 || StringLen(command)<=7) return false;
     }

   if(StringLen(parts[1])<2 || StringGetCharacter(parts[1],0)!='@') return false;
   const string requested_profile=NTStringLower(StringSubstr(parts[1],1));
   if(requested_profile=="") return false;
   cmd.slug_matches=(requested_profile==NTStringLower(expected_profile));

   if(count==2) return true;

   const string selector=parts[2];
   if(NTIsPositiveIntegerText(selector))
     {
      if(count!=3) return false;
      cmd.page=(int)StringToInteger(selector);
      return true;
     }

   if(NTStringLower(selector)=="violations")
     {
      cmd.view=NT_TG_VIEW_VIOLATIONS;
      if(count==4)
        {
         if(!NTIsPositiveIntegerText(parts[3])) return false;
         cmd.page=(int)StringToInteger(parts[3]);
        }
      return true;
     }

   if(NTTelegramCriterionToken(selector))
     {
      cmd.view=NT_TG_VIEW_CRITERION;
      cmd.criterion=NTStringUpper(selector);
      if(count==4)
        {
         if(!NTIsPositiveIntegerText(parts[3])) return false;
         cmd.page=(int)StringToInteger(parts[3]);
        }
      return true;
     }

   return false;
  }

bool NTTelegramIdAllowed(const string specification,const long id)
  {
   string normalized=specification;
   StringReplace(normalized,";",",");
   StringReplace(normalized,"\n",",");
   StringReplace(normalized,"\r",",");
   StringReplace(normalized,"\t",",");
   StringReplace(normalized," ",",");
   string parts[];
   const int count=StringSplit(normalized,',',parts);
   for(int i=0;i<count;i++)
     {
      const string part=NTStringTrimmed(parts[i]);
      if(!NTIsSignedIntegerText(part)) continue;
      if(StringToInteger(part)==id) return true;
     }
   return false;
  }

bool NTTelegramAclAllowed(const string allowed_chats,const string allowed_users,const long chat_id,const long user_id)
  {
   if(NTStringTrimmed(allowed_chats)=="" || NTStringTrimmed(allowed_users)=="") return false;
   return NTTelegramIdAllowed(allowed_chats,chat_id) && NTTelegramIdAllowed(allowed_users,user_id);
  }

bool NTTelegramUpdateProcessable(const long update_id,const long next_offset)
  {
   return update_id>=0 && update_id>=next_offset;
  }

long NTTelegramNextOffset(const long current_offset,const long processed_update_id)
  {
   if(processed_update_id<0) return current_offset;
   return MathMax(current_offset,processed_update_id+1);
  }

int NTJsonSkipWhitespace(const string json,int position)
  {
   while(position<StringLen(json) && NTIsWhitespace(StringGetCharacter(json,position))) position++;
   return position;
  }

int NTJsonHexDigit(const ushort c)
  {
   if(c>='0' && c<='9') return (int)(c-'0');
   if(c>='a' && c<='f') return 10+(int)(c-'a');
   if(c>='A' && c<='F') return 10+(int)(c-'A');
   return -1;
  }

bool NTJsonReadRawValue(const string json,const string key,string &raw)
  {
   raw="";
   const string needle=NTJsonQuote(key);
   int search=0;
   while(search<StringLen(json))
     {
      const int found=StringFind(json,needle,search);
      if(found<0) return false;
      int position=NTJsonSkipWhitespace(json,found+StringLen(needle));
      if(position>=StringLen(json) || StringGetCharacter(json,position)!=':')
        {
         search=found+StringLen(needle);
         continue;
        }
      position=NTJsonSkipWhitespace(json,position+1);
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
      if(first=='{' || first=='[')
        {
         const ushort open=first;
         const ushort close=(first=='{' ? '}' : ']');
         int depth=0;
         bool in_string=false;
         bool escaped=false;
         for(position=start;position<StringLen(json);position++)
           {
            const ushort c=StringGetCharacter(json,position);
            if(in_string)
              {
               if(escaped) { escaped=false; continue; }
               if(c=='\\') { escaped=true; continue; }
               if(c=='\"') in_string=false;
               continue;
              }
            if(c=='\"') { in_string=true; continue; }
            if(c==open) depth++;
            else if(c==close)
              {
               depth--;
               if(depth==0)
                 {
                  raw=StringSubstr(json,start,position-start+1);
                  return true;
                 }
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
      raw=NTStringTrimmed(StringSubstr(json,start,position-start));
      return raw!="";
     }
   return false;
  }

string NTJsonDecodeStringRaw(const string raw)
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
            const int digit=NTJsonHexDigit(StringGetCharacter(raw,i+h));
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

bool NTJsonGetString(const string json,const string key,string &value)
  {
   string raw;
   if(!NTJsonReadRawValue(json,key,raw)) return false;
   if(StringLen(raw)<2 || StringGetCharacter(raw,0)!='\"') return false;
   value=NTJsonDecodeStringRaw(raw);
   return true;
  }

bool NTJsonGetLong(const string json,const string key,long &value)
  {
   string raw;
   if(!NTJsonReadRawValue(json,key,raw) || !NTIsSignedIntegerText(raw)) return false;
   value=StringToInteger(raw);
   return true;
  }

bool NTJsonGetDouble(const string json,const string key,double &value)
  {
   string raw;
   if(!NTJsonReadRawValue(json,key,raw) || raw=="" || raw=="null") return false;
   value=StringToDouble(raw);
   return MathIsValidNumber(value);
  }

bool NTJsonGetBool(const string json,const string key,bool &value)
  {
   string raw;
   if(!NTJsonReadRawValue(json,key,raw)) return false;
   if(raw=="true") { value=true; return true; }
   if(raw=="false") { value=false; return true; }
   return false;
  }

bool NTJsonGetObject(const string json,const string key,string &value)
  {
   if(!NTJsonReadRawValue(json,key,value)) return false;
   return StringLen(value)>=2 && StringGetCharacter(value,0)=='{' && StringGetCharacter(value,StringLen(value)-1)=='}';
  }

bool NTJsonGetArray(const string json,const string key,string &value)
  {
   if(!NTJsonReadRawValue(json,key,value)) return false;
   return StringLen(value)>=2 && StringGetCharacter(value,0)=='[' && StringGetCharacter(value,StringLen(value)-1)==']';
  }

int NTJsonArrayObjects(const string array_json,string &items[])
  {
   ArrayResize(items,0);
   int start=-1;
   int depth=0;
   bool in_string=false;
   bool escaped=false;
   for(int i=0;i<StringLen(array_json);i++)
     {
      const ushort c=StringGetCharacter(array_json,i);
      if(in_string)
        {
         if(escaped) { escaped=false; continue; }
         if(c=='\\') { escaped=true; continue; }
         if(c=='\"') in_string=false;
         continue;
        }
      if(c=='\"') { in_string=true; continue; }
      if(c=='{')
        {
         if(depth==0) start=i;
         depth++;
        }
      else if(c=='}' && depth>0)
        {
         depth--;
         if(depth==0 && start>=0)
           {
            const int n=ArraySize(items);
            ArrayResize(items,n+1);
            items[n]=StringSubstr(array_json,start,i-start+1);
            start=-1;
           }
        }
     }
   return ArraySize(items);
  }

bool NTTelegramApiOk(const string json)
  {
   bool ok=false;
   return NTJsonGetBool(json,"ok",ok) && ok;
  }

NTTelegramWebhookAction NTTelegramWebhookDecision(const string get_webhook_info_json,const bool allow_delete)
  {
   if(!NTTelegramApiOk(get_webhook_info_json)) return NT_TG_WEBHOOK_ERROR;
   string result;
   string url;
   if(!NTJsonGetObject(get_webhook_info_json,"result",result)) return NT_TG_WEBHOOK_ERROR;
   if(!NTJsonGetString(result,"url",url)) return NT_TG_WEBHOOK_ERROR;
   if(url=="") return NT_TG_WEBHOOK_READY;
   return allow_delete ? NT_TG_WEBHOOK_DELETE : NT_TG_WEBHOOK_BLOCK;
  }

string NTUrlEncodeUtf8(const string value)
  {
   uchar bytes[];
   const int copied=StringToCharArray(value,bytes,0,-1,CP_UTF8);
   if(copied<=0) return "";
   int count=copied;
   if(count>0 && bytes[count-1]==0) count--;
   string out="";
   for(int i=0;i<count;i++)
     {
      const int b=(int)bytes[i];
      const bool unreserved=(b>='A' && b<='Z') || (b>='a' && b<='z') || (b>='0' && b<='9') || b=='-' || b=='_' || b=='.' || b=='~';
      if(unreserved) out+=CharToString((uchar)b);
      else out+=StringFormat("%%%02X",b);
     }
   return out;
  }

void NTTelegramAppendPage(string &pages[],const string page)
  {
   const int n=ArraySize(pages);
   ArrayResize(pages,n+1);
   pages[n]=page;
  }

int NTTelegramPaginateItems(const string header,const string &source_items[],const int requested_page_size,const int requested_max_chars,string &pages[])
  {
   ArrayResize(pages,0);
   const int page_size=MathMax(1,requested_page_size);
   const int max_chars=MathMax(128,MathMin(4096,requested_max_chars));
   string safe_header=header;
   if(StringLen(safe_header)>max_chars-16) safe_header=StringSubstr(safe_header,0,max_chars-16);
   string page=safe_header;
   int page_items=0;

   for(int i=0;i<ArraySize(source_items);i++)
     {
      string remaining=source_items[i];
      if(remaining=="") remaining="-";
      while(remaining!="")
        {
         const string separator=(page=="" ? "" : "\n\n");
         int available=max_chars-StringLen(page)-StringLen(separator);
         if(page_items>=page_size || available<=0)
           {
            NTTelegramAppendPage(pages,page);
            page=safe_header;
            page_items=0;
            continue;
           }
         if(StringLen(remaining)<=available)
           {
            page+=separator+remaining;
            remaining="";
            page_items++;
            continue;
           }
         if(page_items>0)
           {
            NTTelegramAppendPage(pages,page);
            page=safe_header;
            page_items=0;
            continue;
           }
         const int chunk_size=MathMax(1,available);
         page+=separator+StringSubstr(remaining,0,chunk_size);
         remaining=StringSubstr(remaining,chunk_size);
         NTTelegramAppendPage(pages,page);
         page=safe_header;
         page_items=0;
        }
     }

   if(page!="" || ArraySize(pages)==0) NTTelegramAppendPage(pages,page);
   return ArraySize(pages);
  }

bool NTTelegramCriterionMatches(const string criterion_id,const string filter)
  {
   return NTStringUpper(criterion_id)==NTStringUpper(filter);
  }

string NTTelegramRedact(const string text,const string raw_login,const string broker,const string server,const string bot_token)
  {
   string out=text;
   if(raw_login!="") StringReplace(out,raw_login,"[redacted-account]");
   if(broker!="") StringReplace(out,broker,"[redacted-broker]");
   if(server!="") StringReplace(out,server,"[redacted-server]");
   if(bot_token!="") StringReplace(out,bot_token,"[redacted-token]");
   return out;
  }

string NTTelegramCallbackViewCode(const NTTelegramView view,const string criterion)
  {
   if(view==NT_TG_VIEW_VIOLATIONS) return "v";
   if(view==NT_TG_VIEW_CRITERION) return NTStringLower(criterion);
   return "s";
  }

string NTTelegramCallbackData(const string profile,const NTTelegramView view,const string criterion,const int page)
  {
   return "nt|"+NTStringLower(profile)+"|"+NTTelegramCallbackViewCode(view,criterion)+"|"+IntegerToString(MathMax(1,page));
  }

bool NTTelegramParseCallbackData(const string data,const string expected_profile,NTTelegramCheckCommand &cmd)
  {
   cmd.slug_matches=false;
   cmd.view=NT_TG_VIEW_SUMMARY;
   cmd.page=1;
   cmd.criterion="";
   string parts[];
   if(StringSplit(data,'|',parts)!=4 || parts[0]!="nt") return false;
   cmd.slug_matches=(NTStringLower(parts[1])==NTStringLower(expected_profile));
   if(!NTIsPositiveIntegerText(parts[3])) return false;
   cmd.page=(int)StringToInteger(parts[3]);
   const string selector=NTStringLower(parts[2]);
   if(selector=="s") return true;
   if(selector=="v") { cmd.view=NT_TG_VIEW_VIOLATIONS; return true; }
   if(NTTelegramCriterionToken(selector))
     {
      cmd.view=NT_TG_VIEW_CRITERION;
      cmd.criterion=NTStringUpper(selector);
      return true;
     }
   return false;
  }

#endif // OAK_NEOTECH_COMPLIANCE_JSON_MQH
