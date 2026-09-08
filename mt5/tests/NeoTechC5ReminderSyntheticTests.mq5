#property strict
#property script_show_inputs

#include "..\\neotech\\NeoTechC5Reminder.mqh"

int g_pass=0;
int g_fail=0;

long T(const string value)
  {
   return (long)StringToTime(value);
  }

void Expect(const bool condition,const string name)
  {
   if(condition)
     {
      g_pass++;
      Print("[NEOTECH C5 TEST] PASS "+name);
      return;
     }
   g_fail++;
   Print("[NEOTECH C5 TEST] FAIL "+name);
  }

void OnStart()
  {
   NC5Session current=NC5_OUTSIDE_SESSION;
   NC5Session next=NC5_OUTSIDE_SESSION;
   long start=0;
   long end=0;

   Expect(NC5CurrentSessionWindow(T("2026-08-03 12:46:15"),current,start,end)
      && current==NC5_EUROPE
      && NC5DateTimeText(start)=="2026-08-03 11:00:00"
      && NC5DateTimeText(end)=="2026-08-03 18:00:00","summer Europe current-session window");

   Expect(NC5CurrentSessionWindow(T("2026-11-02 20:30:00"),current,start,end)
      && current==NC5_US
      && NC5DateTimeText(start)=="2026-11-02 19:00:00"
      && NC5DateTimeText(end)=="2026-11-03 00:00:00","winter US current-session window");

   Expect(!NC5CurrentSessionWindow(T("2026-08-03 01:30:00"),current,start,end)
      && current==NC5_OUTSIDE_SESSION && start==0 && end==0,"outside has no current-session window");

   Expect(NC5NextReentry(T("2026-08-03 10:10:00"),current,next,start)
      && current==NC5_ASIA && next==NC5_EUROPE
      && NC5DateTimeText(start)=="2026-08-03 11:00:00","summer Asia -> Europe");

   Expect(NC5NextReentry(T("2026-08-03 14:30:00"),current,next,start)
      && current==NC5_EUROPE && next==NC5_US
      && NC5DateTimeText(start)=="2026-08-03 18:00:00","summer Europe -> US");

   Expect(NC5NextReentry(T("2026-11-02 12:00:00"),current,next,start)
      && current==NC5_EUROPE && next==NC5_US
      && NC5DateTimeText(start)=="2026-11-02 19:00:00","winter Europe -> US");

   Expect(NC5NextReentry(T("2026-08-03 22:30:00"),current,next,start)
      && current==NC5_US && next==NC5_ASIA
      && NC5DateTimeText(start)=="2026-08-04 02:00:00","US -> next-day Asia");

   Expect(!NC5NextReentry(T("2026-08-03 01:30:00"),current,next,start),"outside session refuses permission");
   Expect(NC5VietnamTimeText(T("2026-08-03 11:00:00"))=="2026-08-03 15:00:00","summer server -> Vietnam");
   Expect(NC5VietnamTimeText(T("2026-11-02 19:00:00"))=="2026-11-03 00:00:00","winter server -> Vietnam");

   const string message=NC5ReminderText("EURUSD",T("2026-08-03 10:10:00"));
   Expect(StringFind(message,"NeoTech C5 · EURUSD")>=0
      && StringFind(message,"15:00:00 VN")>=0
      && StringFind(message,"E5")<0,"C5-only Telegram wording");

   const string outside=NC5ReminderText("EURUSD",T("2026-08-03 01:30:00"));
   Expect(StringFind(outside,"KHÔNG XÁC MINH")>=0 && StringFind(outside,"Được vào lại")<0,"outside-session fail closed wording");

   const string json="{\"login\":182001,\"server\":\"NeotechFinancialServices-Demo\",\"profile\":\"FXCE\"}";
   long login=0;
   string server="",profile="";
   Expect(NC5JsonGetLong(json,"login",login) && login==182001
      && NC5JsonGetString(json,"server",server) && server=="NeotechFinancialServices-Demo"
      && NC5JsonGetString(json,"profile",profile) && profile=="FXCE","local heartbeat JSON parsing");

   PrintFormat("[NEOTECH C5 TEST] TOTAL=%d PASS=%d FAIL=%d RESULT=%s",g_pass+g_fail,g_pass,g_fail,g_fail==0?"PASS":"FAIL");
  }
