# -*- coding: utf-8 -*-
import os
import json
import time
import urllib.request
import ssl
from datetime import datetime, timedelta, timezone
import calendar
import xml.etree.ElementTree as ET
import MetaTrader5 as mt5
import threading
import sys
import hashlib
import glob
import winsound # For PC Alarm
import re
import random
from oak_response_dict import get_random_response # Import new response module

# --- CONFIG ---
CONFIG_FILE = "profiles.json"
SETTINGS_FILE = "settings.json"
CHECK_INTERVAL = 60  # Check every 60 seconds
LOCK_DIR = "sent_locks"

PAIR_MAP = {
    "AUDUSD": "AU",
    "USDCAD": "UC",
    "GBPAUD": "GA",
    "GBPJPY": "GJ",
    "USDJPY": "UJ",
    "GBPNZD": "GN",
    "GBPCHF": "GF",
    "GBPUSD": "GU",
    "GBPCAD": "GC",
    "XAUUSD": "Gold",
    "GOLD": "Gold"
}

# Global credentials (optional override)
CURRENT_TOKEN = None
CURRENT_CHAT_ID = None

def set_credentials(token, chat_id):
    global CURRENT_TOKEN, CURRENT_CHAT_ID
    CURRENT_TOKEN = token
    CURRENT_CHAT_ID = chat_id

def is_winter_time():
    """Check if we are in Winter time (Standard Time) - Using US DST Schedule (NYC)"""
    # US DST: 2nd Sunday of March to 1st Sunday of November
    now = datetime.now()
    month = now.month
    year = now.year
    
    # April to October -> Summer (DST)
    if 4 <= month <= 10:
        return False
    # Dec to Feb -> Winter (Standard)
    if month == 12 or 1 <= month <= 2:
        return True
        
    # March check (Starts on 2nd Sunday)
    if month == 3:
        # Get all Sundays in March
        c = calendar.monthcalendar(year, 3)
        sundays = [week[6] for week in c if week[6] != 0]
        second_sunday = sundays[1]
        return now.day < second_sunday
        
    # November check (Ends on 1st Sunday)
    if month == 11:
        # Get all Sundays in November
        c = calendar.monthcalendar(year, 11)
        sundays = [week[6] for week in c if week[6] != 0]
        first_sunday = sundays[0]
        return now.day >= first_sunday
        
    return False

def load_json_file(path, default):
    try:
        if not os.path.exists(path):
            return default
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        return default

def send_ntfy(message):
    """Send notification to ntfy.sh (Free, Unlimited, No Login)"""
    try:
        if not os.path.exists(SETTINGS_FILE): return
        with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
            settings = json.load(f)
        
        topic = settings.get("ntfy_topic")
        if not topic: return

        # ntfy.sh URL
        url = f"https://ntfy.sh/{topic}"
        
        # Encode message
        data = message.encode("utf-8")
        
        req = urllib.request.Request(
            url, 
            data=data, 
            headers={
                "Title": "OAK Trading Alert",
                "Priority": "5", # 5 = Urgent (High priority, can override silent switch on some devices)
                "Tags": "warning,chart_with_upwards_trend"
            }
        )
        
        with urllib.request.urlopen(req, timeout=10) as response:
            pass # Success
            
    except Exception as e:
        print(f"Error sending ntfy: {e}")

def get_last_friday(year, month):
    """Return the date (int) of the last Friday of the given month"""
    c = calendar.monthcalendar(year, month)
    last_week = c[-1]
    if last_week[calendar.FRIDAY] != 0:
        return last_week[calendar.FRIDAY]
    else:
        return c[-2][calendar.FRIDAY]

def get_last_thursday(year, month):
    """Return the date (int) of the last Thursday of the given month"""
    c = calendar.monthcalendar(year, month)
    last_week = c[-1]
    if last_week[calendar.THURSDAY] != 0:
        return last_week[calendar.THURSDAY]
    else:
        return c[-2][calendar.THURSDAY]

def get_economic_news(lang="VN"):
    # 1. Check Cache
    cache_file = f"news_cache_{lang}.json"
    today = datetime.now().date()
    try:
        if os.path.exists(cache_file):
            with open(cache_file, "r", encoding="utf-8") as f:
                cache = json.load(f)
            if cache.get("date") == str(today) and cache.get("news"):
                return cache["news"]
    except: pass

    # 2. Fetch Fresh
    try:
        news_list = _fetch_news_fresh(lang=lang)
    except Exception as e:
        print(f"CRITICAL NEWS ERROR: {e}")
        news_list = [f"⚠️ Lỗi hệ thống tin tức: {e}"] if lang == "VN" else [f"⚠️ Critical News System Error: {e}"]
    
    # 3. Save Cache
    if news_list and not any(("Lỗi" in x or "Error" in x) for x in news_list):
        try:
            with open(cache_file, "w", encoding="utf-8") as f:
                json.dump({"date": str(today), "news": news_list}, f)
        except: pass
        
    return news_list

def _fetch_news_fresh(lang="VN"):
    # Cấu hình SSL linh hoạt để xử lý các lỗi handshake và EOF
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    
    # Hỗ trợ các giao thức cũ hơn và giải quyết lỗi UNEXPECTED_EOF
    # Sử dụng try-except vì không phải mọi phiên bản Python đều hỗ trợ các options này
    try:
        # Cho phép các phiên bản TLS thấp hơn nếu server yêu cầu
        ctx.minimum_version = ssl.TLSVersion.TLSv1
    except: pass
    
    try:
        # OP_LEGACY_SERVER_CONNECT (0x4) giúp kết nối với các server có cấu hình cũ
        ctx.options |= 0x4 
    except: pass

    # Attempt 1: MyFxBook RSS (with retry)
    errs = []
    success_but_empty = False
    for i in range(2):
        try:
            res = fetch_myfxbook_rss(lang=lang, context=ctx)
            if res: return res
            success_but_empty = True
        except Exception as e:
            errs.append(f"MyFxBook_{i}:{e}")
            time.sleep(2)
            
    # Attempt 2: ForexFactory XML (Official Feed, less blocking)
    try:
        res = fetch_forexfactory_xml(lang=lang, context=ctx)
        if res: return res
        success_but_empty = True
    except Exception as e:
        errs.append(f"FF:{e}")

    # Attempt 3: LiteFinance RSS (New Backup)
    try:
        res = fetch_litefinance_rss(lang=lang, context=ctx)
        if res: return res
        success_but_empty = True
    except Exception as e:
        errs.append(f"LiteFinance:{e}")

    # Attempt 4: Investing.com RSS (Backup)
    try:
        res = fetch_investing_rss(lang=lang, context=ctx)
        if res: return res
        success_but_empty = True
    except Exception as e:
        errs.append(f"Investing:{e}")

    # If we reached here, either all failed or all were empty
    if success_but_empty:
        empty_msg = "Không có tin tức quan trọng (High Impact) hôm nay." if lang == "VN" else "No important news (High Impact) today."
        return [empty_msg]

    if any(e for e in errs):
        # Rút gọn thông báo lỗi để tránh quá dài trên Telegram
        unique_errs = list(set([str(e).split(":")[0] for e in errs]))
        err_msg = f"⚠️ Lỗi kết nối nguồn tin ({', '.join(unique_errs)}). Vui lòng thử lại sau." if lang == "VN" else f"⚠️ News Connection Error ({', '.join(unique_errs)}). Please try again later."
        # Vẫn in lỗi chi tiết ra console để debug
        print(f"DEBUG NEWS ERRORS: {'; '.join(errs)}")
        return [err_msg]
    
    empty_msg = "Không có tin tức quan trọng (High Impact) hôm nay." if lang == "VN" else "No important news (High Impact) today."
    return [empty_msg]

def fetch_investing_rss(lang="VN", context=None):
    url = "https://www.investing.com/rss/news_285.rss" # Economic News RSS
    today = datetime.now().date()
    
    if context is None:
        context = ssl.create_default_context()
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE
    
    req = urllib.request.Request(
        url, 
        headers={
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': '*/*'
        }
    )
    
    with urllib.request.urlopen(req, timeout=20, context=context) as response:
        data = response.read()
        
    root = ET.fromstring(data)
    out = []
    found_events = False
    
    channel = root.find("channel")
    items = channel.findall("item") if channel else root.findall("item")
    
    for item in items:
        title = (item.findtext("title") or "").strip()
        pub_date_str = item.findtext("pubDate")
        
        # Parse Date
        if pub_date_str:
            try:
                dt_obj = datetime.strptime(pub_date_str, "%a, %d %b %Y %H:%M:%S %z")
                dt_local = dt_obj.astimezone()
                if dt_local.date() != today: continue
                event_time_str = dt_local.strftime("%H:%M")
            except:
                continue
        else: continue
        
        # INVESTING.COM RSS doesn't always have impact tags, but we filter by high keywords
        title_lower = title.lower()
        if any(kw in title_lower for kw in ["high impact", "fed", "cpi", "nfp", "gdp", "rate", "powell", "ecb", "fomc"]):
            found_events = True
            icon = "<c=#e74c3c>🔴</c>"
            out.append(f"• {event_time_str} {icon} {title}")
            
    if not found_events:
        return [] # Don't return empty msg here, let _fetch_news_fresh handle it
    
    out.sort()
    return out

def fetch_myfxbook_rss(lang="VN", context=None):
    url = "https://www.myfxbook.com/rss/forex-economic-calendar-events"
    today = datetime.now().date()
    
    # SSL Context to avoid handshake errors
    if context is None:
        context = ssl.create_default_context()
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE
        try:
            context.options |= 0x4 # OP_LEGACY_SERVER_CONNECT
        except: pass
    
    req = urllib.request.Request(
        url, 
        data=None, 
        headers={
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9',
            'Connection': 'keep-alive'
        }
    )
    
    with urllib.request.urlopen(req, timeout=30, context=context) as response:
        data = response.read()
    
    if not data:
        raise Exception("Empty Response")

    root = ET.fromstring(data)
    
    out = []
    found_events = False
    
    channel = root.find("channel")
    if not channel:
        items = root.findall("item") # Sometimes root is channel-like
    else:
        items = channel.findall("item")
        
    for item in items:
        title = (item.findtext("title") or "").strip()
        pub_date_str = item.findtext("pubDate")
        
        # Parse Date & Convert to Local Time
        event_time_str = ""
        if pub_date_str:
            try:
                # MyFxBook Example: Tue, 17 Feb 2026 13:30:00 GMT
                # Parse as naive first if %Z is tricky, but GMT is usually handled
                dt_obj = None
                if "GMT" in pub_date_str:
                    dt_obj = datetime.strptime(pub_date_str.replace("GMT", "").strip(), "%a, %d %b %Y %H:%M:%S")
                    dt_obj = dt_obj.replace(tzinfo=timezone.utc) # Set as UTC
                else:
                    # Try with %Z
                    dt_obj = datetime.strptime(pub_date_str, "%a, %d %b %Y %H:%M:%S %Z")
                
                # Convert to Local Time
                dt_local = dt_obj.astimezone() # Local system time
                
                # FIX: Filter by LOCAL date, not GMT date
                if dt_local.date() != today: continue
                event_time_str = dt_local.strftime("%H:%M")
            except:
                continue
        else:
            continue
            
        # Parse Impact
        impact = "Low"
        title_lower = title.lower()
        if "high impact" in title_lower or "high" in title_lower: 
            impact = "High"
        elif "medium impact" in title_lower or "medium" in title_lower: 
            impact = "Medium"
        elif "low impact" in title_lower or "low" in title_lower: 
            impact = "Low"
            
        # FILTER: Only show High Impact (Red) news as requested
        if impact != "High":
            continue
        
        # Parse Currency
        currency = ""
        try:
            parts = title.split(":")
            if len(parts) > 1:
                sub_parts = parts[1].strip().split("-")
                if len(sub_parts) > 0:
                    currency = sub_parts[0].strip()
        except:
            pass
            
        clean_title = title.split(":", 1)[1].strip() if ":" in title else title
        
        found_events = True
        icon = "<c=#e74c3c>🔴</c>"
        out.append(f"• {event_time_str} {currency} {icon} {clean_title}")

    if not found_events:
         return []
         
    out.sort()
    return out

def fetch_litefinance_rss(lang="VN", context=None):
    # https://www.litefinance.org/rss/economic-calendar-feed/
    url = "https://www.litefinance.org/rss/economic-calendar-feed/"
    today = datetime.now().date()
    
    if context is None:
        context = ssl.create_default_context()
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE
        try:
            context.options |= 0x4 # OP_LEGACY_SERVER_CONNECT
        except: pass
    
    req = urllib.request.Request(
        url, 
        headers={
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9'
        }
    )
    
    with urllib.request.urlopen(req, timeout=30, context=context) as response:
        data = response.read()
        
    root = ET.fromstring(data)
    out = []
    found_events = False
    
    channel = root.find("channel")
    if not channel: items = root.findall("item")
    else: items = channel.findall("item")
    
    for item in items:
        title = (item.findtext("title") or "").strip()
        pub_date_str = item.findtext("pubDate")
        category = (item.findtext("category") or "").lower() # Often contains impact
        
        # Parse Date
        event_time_str = ""
        if pub_date_str:
            try:
                dt_obj = datetime.strptime(pub_date_str, "%a, %d %b %Y %H:%M:%S %z")
                dt_local = dt_obj.astimezone()
                if dt_local.date() != today: continue
                event_time_str = dt_local.strftime("%H:%M")
            except:
                try:
                    dt_obj = datetime.strptime(pub_date_str, "%a, %d %b %Y %H:%M:%S GMT")
                    dt_obj = dt_obj.replace(tzinfo=timezone.utc)
                    dt_local = dt_obj.astimezone()
                    if dt_local.date() != today: continue
                    event_time_str = dt_local.strftime("%H:%M")
                except:
                    continue
        else: continue
        
        # Check Impact
        is_high = False
        if "high" in title.lower() or "high" in category: is_high = True
        
        if not is_high: continue
        
        found_events = True
        icon = "<c=#e74c3c>🔴</c>"
        out.append(f"• {event_time_str} {icon} {title}")
        
    if not found_events:
        return []
    
    out.sort()
    return out


def fetch_forexfactory_xml(lang="VN", context=None):
    url = "https://nfs.faireconomy.media/ff_calendar_thisweek.xml"
    today = datetime.now().date()
    
    if context is None:
        context = ssl.create_default_context()
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE
    
    req = urllib.request.Request(
        url, 
        headers={'User-Agent': 'Mozilla/5.0'}
    )
    
    with urllib.request.urlopen(req, timeout=30, context=context) as response:
        data = response.read()
        
    root = ET.fromstring(data)
    # Structure: <weeklyevents><event><title>...</title><country>USD</country><date>02-17-2026</date><time>1:30pm</time><impact>High</impact>...</event>...
    
    impact_icon = {
        "High": "<c=#e74c3c>🔴</c>",
        "Medium": "<c=#e67e22>🟠</c>",
        "Low": "<c=#f1c40f>🟡</c>"
    }
    
    out = []
    found_events = False
    
    for event in root.findall("event"):
        event_date_str = event.findtext("date") # MM-DD-YYYY
        event_time_str = event.findtext("time") # 1:30pm
        
        # Format Time to 24h & Convert to Local Time
        try:
            # FF XML usually uses GMT/UTC for the public feed (or EST, need verification, but standard feed is often UTC)
            # Actually FF XML date is usually just date. Time is time.
            # Best effort: Assume GMT, convert to local, then check date.
            
            t_obj = datetime.strptime(event_time_str, "%I:%M%p")
            dt_src = datetime.strptime(event_date_str, "%m-%d-%Y").date()
            dt_full_src = datetime.combine(dt_src, t_obj.time())
            dt_full_src = dt_full_src.replace(tzinfo=timezone.utc) # Assume Source is UTC
            
            # Convert to Local
            dt_local = dt_full_src.astimezone()
            
            # FIX: Check LOCAL date match
            if dt_local.date() != today:
                continue
                
            time_24 = dt_local.strftime("%H:%M")
        except:
            # Fallback if parsing fails (use raw date check)
            try:
                dt_obj = datetime.strptime(event_date_str, "%m-%d-%Y").date()
                if dt_obj != today: continue
                time_24 = event_time_str
            except:
                continue
            
        title = event.findtext("title")
        country = event.findtext("country")
        impact_str = event.findtext("impact") # High, Medium, Low
        
        # FILTER: Only show High Impact
        if impact_str != "High":
            continue
            
        icon = "<c=#e74c3c>🔴</c>"
        
        found_events = True
        out.append(f"• {time_24} {country} {icon} {title}")
        
    if not found_events:
        return []
        
    out.sort()
    return out

def get_daily_schedule(now, lang="VN"):
    """Get the trading schedule for the given time"""
    return []

def get_rule_reminders(now, lang="VN"):
    day = now.day
    month = now.month
    year = now.year
    weekday = now.weekday()  # 0=Mon..6=Sun

    out = []

    def _is_first_friday_week_member(date_obj):
        if date_obj.weekday() != 0:
            return False
        first_friday_of_week = date_obj + timedelta(days=(4 - date_obj.weekday()))
        return first_friday_of_week.weekday() == 4 and 1 <= first_friday_of_week.day <= 7

    prev_day = now - timedelta(days=1)

    if weekday == 3 and prev_day.weekday() == 2 and prev_day.day in [30, 1]:
        if lang == "VN":
            out.append("• Hôm nay là Thứ 5, hôm qua Thứ 4 rơi vào ngày 30/1: đánh mốc 2/9.")
        else:
            out.append("• Today is Thursday and yesterday's Wednesday fell on day 30/1: trade the 2/9 slots.")

    if weekday == 4 and day == get_last_friday(year, month):
        if month in (2, 7):
            if lang == "VN":
                out.append("• Hôm nay là Thứ 6 cuối tháng: vẫn tính mốc 18:00, nhưng đi ngược chiều vì rơi vào tháng 2 hoặc tháng 7.")
            else:
                out.append("• Today is the last Friday of the month: still include the 18:00 slot, but reverse direction because it falls in February or July.")
        else:
            if lang == "VN":
                out.append("• Hôm nay là Thứ 6 cuối tháng: tính thêm mốc 18:00.")
            else:
                out.append("• Today is the last Friday of the month: include the 18:00 slot.")

    if _is_first_friday_week_member(now):
        if lang == "VN":
            out.append("• Hôm nay là Thứ 2 thuộc tuần đầu tháng (tính theo tuần chứa Thứ 6 đầu tiên của tháng).")
        else:
            out.append("• Today is Monday in the first week of the month (based on the week containing the first Friday of the month).")

    return out


def generate_daily_reminder(now, lang="VN"):
    weekday = now.weekday()
    day = now.day
    month = now.month
    year = now.year
    prev_day = now - timedelta(days=1)

    weekday_names_vn = {
        0: "Thứ 2",
        1: "Thứ 3",
        2: "Thứ 4",
        3: "Thứ 5",
        4: "Thứ 6",
        5: "Thứ 7",
        6: "Chủ nhật",
    }
    weekday_names_en = {
        0: "Monday",
        1: "Tuesday",
        2: "Wednesday",
        3: "Thursday",
        4: "Friday",
        5: "Saturday",
        6: "Sunday",
    }

    def _fmt_slots(slots):
        return ", ".join(slots) if slots else "-"

    def _is_first_friday_week_monday(date_obj):
        if date_obj.weekday() != 0:
            return False
        first_friday_of_week = date_obj + timedelta(days=(4 - date_obj.weekday()))
        return first_friday_of_week.weekday() == 4 and 1 <= first_friday_of_week.day <= 7

    if weekday >= 5:
        if lang == "VN":
            return (
                f"📌 REMINDER ĐẦU NGÀY - {weekday_names_vn[weekday]} {now.strftime('%d/%m/%Y')}\n\n"
                f"• Phân loại ngày: Ngoài lịch giao dịch\n"
                f"• Override chính: Không có\n\n"
                f"• Cùng chiều (C): -\n"
                f"• Ngược chiều (N): -\n\n"
                f"• Mốc đặc biệt: Không có\n"
                f"• Lưu ý: Hôm nay không có rule reminder giao dịch.\n"
                f"• Ưu tiên hôm nay: -"
            )
        return (
            f"📌 DAILY REMINDER - {weekday_names_en[weekday]} {now.strftime('%m/%d/%Y')}\n\n"
            f"• Day Type: Outside trading schedule\n"
            f"• Main Override: None\n\n"
            f"• Same Direction (C): -\n"
            f"• Reverse Direction (N): -\n\n"
            f"• Special Slot: None\n"
            f"• Note: No trading reminder rule applies today.\n"
            f"• Priority Today: -"
        )

    rule = {
        "day_type_vn": "Ngày thường",
        "day_type_en": "Normal day",
        "override_vn": "Không có",
        "override_en": "None",
        "c_slots": [],
        "n_slots": [],
        "special_vn": "Không có",
        "special_en": "None",
        "note_vn": "",
        "note_en": "",
        "priority_vn": "",
        "priority_en": "",
    }

    if weekday == 0:
        rule.update({
            "c_slots": ["02:00", "12:00"],
            "n_slots": ["02:00", "06:00"],
            "special_vn": "02:00 là mốc ưu tiên, lấy cùng chiều theo Thứ 6",
            "special_en": "02:00 is the priority slot, aligned with Friday direction",
            "note_vn": "Thực chiến ưu tiên mốc 02:00.",
            "note_en": "In practice, prioritize the 02:00 slot.",
            "priority_vn": "02:00",
            "priority_en": "02:00",
        })
    elif weekday == 1:
        rule.update({
            "c_slots": ["02:00", "12:00"],
            "n_slots": ["02:00", "15:00"],
            "special_vn": "Không có",
            "special_en": "None",
            "note_vn": "Không còn thông báo Thứ 3 tuần đầu tháng.",
            "note_en": "There is no more first-week Tuesday reminder.",
            "priority_vn": "02:00",
            "priority_en": "02:00",
        })
    elif weekday == 2:
        rule.update({
            "c_slots": ["02:00", "06:00", "15:00", "18:00"],
            "n_slots": ["02:00"],
            "special_vn": "06:00 là sw nhưng close; 18:00 là mốc chuyển tiếp cho sáng Thứ 5",
            "special_en": "06:00 is sideway/close; 18:00 carries into Thursday morning",
            "note_vn": "Thứ 4 bình thường, không có rule chặn riêng.",
            "note_en": "Wednesday is normal, with no special block rule.",
            "priority_vn": "02:00, 15:00",
            "priority_en": "02:00, 15:00",
        })
    elif weekday == 3:
        rule.update({
            "c_slots": ["02:00", "12:00"],
            "n_slots": ["02:00", "09:00"],
            "special_vn": "Không có",
            "special_en": "None",
            "note_vn": "Theo dõi ảnh hưởng carry từ 18:00 Thứ 4 nếu có.",
            "note_en": "Watch any carry-over effect from Wednesday 18:00.",
            "priority_vn": "02:00, 09:00",
            "priority_en": "02:00, 09:00",
        })
    elif weekday == 4:
        rule.update({
            "c_slots": ["06:00", "12:00"],
            "n_slots": ["06:00", "15:00"],
            "special_vn": "06:00 là mốc làm mồi",
            "special_en": "06:00 is a bait/probe slot",
            "note_vn": "12:00 và 15:00 là các mốc chính của ngày.",
            "note_en": "12:00 and 15:00 are the main slots of the day.",
            "priority_vn": "12:00 hoặc 15:00",
            "priority_en": "12:00 or 15:00",
        })

    if weekday == 3 and prev_day.weekday() == 2 and prev_day.day in (30, 1):
        rule.update({
            "day_type_vn": "Thứ 5 sau Thứ 4 ngày 30/1",
            "day_type_en": "Thursday after Wednesday 30/1",
            "override_vn": "Đánh mốc 02:00 và 09:00",
            "override_en": "Trade the 02:00 and 09:00 slots",
            "c_slots": [],
            "n_slots": ["02:00", "09:00"],
            "special_vn": "Override đặc biệt theo ngày hôm trước",
            "special_en": "Special override based on the previous day",
            "note_vn": "Rule này đè lên lịch nền Thứ 5.",
            "note_en": "This rule overrides the normal Thursday schedule.",
            "priority_vn": "02:00, 09:00",
            "priority_en": "02:00, 09:00",
        })
    elif weekday == 4 and day == get_last_friday(year, month):
        if month in (2, 7):
            rule.update({
                "day_type_vn": "Thứ 6 cuối tháng đặc biệt",
                "day_type_en": "Special last Friday of the month",
                "override_vn": "Vẫn có mốc 18:00 nhưng đi ngược chiều",
                "override_en": "18:00 still applies but in reverse direction",
                "c_slots": ["06:00", "12:00"],
                "n_slots": ["06:00", "15:00", "18:00"],
                "special_vn": "06:00 làm mồi; 18:00 đi ngược chiều",
                "special_en": "06:00 is bait; 18:00 is reversed",
                "note_vn": "Ngoại lệ áp cho Thứ 6 cuối cùng của tháng 2 và tháng 7.",
                "note_en": "This exception applies to the last Friday of February and July.",
                "priority_vn": "12:00, 15:00, 18:00 N",
                "priority_en": "12:00, 15:00, 18:00 N",
            })
        else:
            rule.update({
                "day_type_vn": "Thứ 6 cuối tháng",
                "day_type_en": "Last Friday of the month",
                "override_vn": "Tính thêm mốc 18:00",
                "override_en": "Add the 18:00 slot",
                "c_slots": ["06:00", "12:00", "18:00"],
                "n_slots": ["06:00", "15:00"],
                "special_vn": "06:00 làm mồi; 18:00 là mốc bổ sung cuối tháng",
                "special_en": "06:00 is bait; 18:00 is the added month-end slot",
                "note_vn": "18:00 đi cùng chiều trong tháng thường.",
                "note_en": "18:00 stays in the same direction in normal months.",
                "priority_vn": "12:00, 15:00, 18:00",
                "priority_en": "12:00, 15:00, 18:00",
            })
    elif _is_first_friday_week_monday(now):
        rule.update({
            "day_type_vn": "Thứ 2 tuần đầu tháng",
            "day_type_en": "First-week Monday",
            "override_vn": "Tính theo tuần chứa Thứ 6 đầu tiên của tháng",
            "override_en": "Based on the week containing the first Friday of the month",
            "c_slots": ["02:00", "12:00"],
            "n_slots": ["02:00", "06:00"],
            "special_vn": "02:00 là mốc ưu tiên, vẫn được tính kể cả khi tuần bắt đầu từ tháng trước",
            "special_en": "02:00 stays priority even if the week starts in the previous month",
            "note_vn": "Chỉ áp cho Thứ 2 tuần đầu tháng.",
            "note_en": "Applies only to the first-week Monday.",
            "priority_vn": "02:00",
            "priority_en": "02:00",
        })

    if lang == "VN":
        return (
            f"📌 REMINDER ĐẦU NGÀY - {weekday_names_vn[weekday]} {now.strftime('%d/%m/%Y')}\n\n"
            f"• Phân loại ngày: {rule['day_type_vn']}\n"
            f"• Override chính: {rule['override_vn']}\n\n"
            f"• Cùng chiều (C): {_fmt_slots(rule['c_slots'])}\n"
            f"• Ngược chiều (N): {_fmt_slots(rule['n_slots'])}\n\n"
            f"• Mốc đặc biệt: {rule['special_vn']}\n"
            f"• Lưu ý: {rule['note_vn']}\n"
            f"• Ưu tiên hôm nay: {rule['priority_vn']}"
        )

    return (
        f"📌 DAILY REMINDER - {weekday_names_en[weekday]} {now.strftime('%m/%d/%Y')}\n\n"
        f"• Day Type: {rule['day_type_en']}\n"
        f"• Main Override: {rule['override_en']}\n\n"
        f"• Same Direction (C): {_fmt_slots(rule['c_slots'])}\n"
        f"• Reverse Direction (N): {_fmt_slots(rule['n_slots'])}\n\n"
        f"• Special Slot: {rule['special_en']}\n"
        f"• Note: {rule['note_en']}\n"
        f"• Priority Today: {rule['priority_en']}"
    )

class OakTradingReminder:
    def __init__(self, token=None, chat_id=None):
        self.token = token
        self.chat_id = chat_id
        self.running = False
        self._stop_event = threading.Event()
        self.alerted_events = set()
        self.last_briefing_date = None
        self._ensure_lock_dir()
        self._cleanup_old_locks()

    def _ensure_lock_dir(self):
        if not os.path.exists(LOCK_DIR):
            try:
                os.makedirs(LOCK_DIR)
            except: pass

    def _cleanup_old_locks(self):
        """Delete locks older than 24 hours"""
        try:
            now_ts = time.time()
            cutoff = now_ts - 86400 # 24 hours
            for f in glob.glob(os.path.join(LOCK_DIR, "*.lock")):
                try:
                    if os.path.getmtime(f) < cutoff:
                        os.remove(f)
                except: pass
        except: pass

    def _is_event_locked(self, unique_key):
        """
        Check if event is locked (already sent).
        If not, create lock file and return False (allow send).
        If yes, return True (block send).
        Uses atomic file creation for thread/process safety.
        """
        self._ensure_lock_dir()
        
        # Hash key to get safe filename
        safe_name = hashlib.md5(unique_key.encode('utf-8')).hexdigest() + ".lock"
        lock_path = os.path.join(LOCK_DIR, safe_name)
        
        if os.path.exists(lock_path):
            return True
            
        try:
            # Atomic creation (fails if file exists)
            fd = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            os.close(fd)
            return False # Successfully locked, proceed to send
        except FileExistsError:
            return True # Already locked by another process
        except Exception as e:
            print(f"Lock error: {e}")
            return True # Fail safe (don't spam if error)

    def load_config(self):
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                    return json.load(f)
            except:
                return {}
        return {}

    def send_telegram(self, message):
        token = self.token or CURRENT_TOKEN
        chat_id = self.chat_id or CURRENT_CHAT_ID
        
        # Fallback to loading from file if not set
        if not token or not chat_id:
            config = self.load_config()
            for p_name in config:
                p = config[p_name]
                if p.get("tele_token") and p.get("tele_chat"):
                    token = p["tele_token"]
                    chat_id = p["tele_chat"]
                    break
        
        if not token or not chat_id:
            print(f"DEBUG (No Telegram Config): {message}")
            return

        # Strip color tags for Telegram (they don't support custom HTML tags like <c=...>)
        clean_message = re.sub(r"<c=#[A-Fa-f0-9]{6}>", "", message)
        clean_message = clean_message.replace("</c>", "")

        log_file = "tele_sent_log.json"
        lock_file = "tele_sent_log.lock"
        lock_fd = None
        try:
            start_ts = time.time()
            # WAIT LONGER FOR LOCK (5 seconds) to handle simultaneous send from multiple instances
            while True:
                try:
                    lock_fd = os.open(lock_file, os.O_CREAT | os.O_EXCL | os.O_RDWR)
                    break
                except FileExistsError:
                    if time.time() - start_ts > 5:
                        break # Timeout after 5 seconds
                    time.sleep(0.1) # Wait longer between retries
                except:
                    break

            sent_log = []
            if lock_fd:
                try:
                    if os.path.exists(log_file):
                        with open(log_file, "r", encoding="utf-8") as f:
                            sent_log = json.load(f)
                except:
                    sent_log = []

                now_ts = time.time()
                cutoff = now_ts - 120
                filtered = []
                duplicate = False
                for item in sent_log:
                    ts = item.get("ts", 0)
                    msg_text = item.get("msg", "")
                    if ts >= cutoff:
                        if msg_text == clean_message:
                            duplicate = True
                        filtered.append(item)
                if duplicate:
                    os.close(lock_fd)
                    try: os.remove(lock_file)
                    except: pass
                    return
            else:
                # If we still don't have the lock after timeout, 
                # we assume it might be a duplicate being processed by another instance.
                # To be safe and avoid double briefing, we'll wait one more second and re-check main log
                time.sleep(1)
                if not self._should_send_daily_briefing():
                    return # Skip if main briefing log was updated in the meantime
                
                filtered = []
                now_ts = time.time()
        except:
            filtered = []
            now_ts = time.time()
        finally:
            # Only close/remove if we got the lock here.
            # If we didn't get it, the other instance is responsible for cleanup.
            if lock_fd and duplicate: # We already closed and removed above for duplicate
                pass 
            elif lock_fd:
                os.close(lock_fd)
                try: os.remove(lock_file)
                except: pass

        try:
            msg = urllib.parse.quote(clean_message)
            url = f"https://api.telegram.org/bot{token}/sendMessage?chat_id={chat_id}&text={msg}"
            with urllib.request.urlopen(url, timeout=10) as response:
                result = response.read()
            
            # Re-acquire lock to update log after send
            # (Similar logic but brief, as we just want to update)
            try:
                # We skip update if lock is still busy, sending the message is more important
                l_fd = os.open(lock_file, os.O_CREAT | os.O_EXCL | os.O_RDWR)
                if filtered is not None:
                    filtered.append({"msg": clean_message, "ts": now_ts})
                    with open(log_file, "w", encoding="utf-8") as f:
                        json.dump(filtered[-200:], f)
                os.close(l_fd)
                os.remove(lock_file)
            except: pass
                
            return result
        except Exception as e:
            print(f"Error sending Telegram: {e}")

    # _should_send_action_now and _should_send_pre_alert_now replaced by _is_event_locked

    def get_performance_report(self, profile):
        """Connect to MT5 and calculate weekly performance for a profile"""
        path = profile.get("path", "")
        if not path or not os.path.exists(path):
            return None
            
        if not mt5.initialize(path=path):
            return None
            
        # Get history for last 7 days
        from_date = datetime.now() - timedelta(days=7)
        to_date = datetime.now()
        
        history = mt5.history_deals_get(from_date, to_date)
        if history is None:
            mt5.shutdown()
            return None
            
        total_profit = 0
        wins = 0
        losses = 0
        sym_performance = {}
        
        if len(history) > 0:
            for deal in history:
                if deal.entry == mt5.DEAL_ENTRY_OUT: # Closing deal
                    profit = deal.profit + deal.swap + deal.commission
                    total_profit += profit
                    if profit > 0: wins += 1
                    else: losses += 1
                    
                    sym = deal.symbol
                    if sym not in sym_performance: sym_performance[sym] = 0.0
                    sym_performance[sym] += profit
                
        win_rate = (wins / (wins + losses) * 100) if (wins + losses) > 0 else 0
        best_pair = max(sym_performance, key=sym_performance.get) if sym_performance else "N/A"
        
        acc = mt5.account_info()
        drawdown = 0
        if acc:
            drawdown = ((acc.balance - acc.equity) / acc.balance * 100) if acc.balance > 0 else 0

        report = {
            "profit": total_profit,
            "win_rate": win_rate,
            "best_pair": best_pair,
            "drawdown": drawdown,
            "total_trades": wins + losses
        }
        
        suggestion = ""
        if win_rate < 40 and total_profit < 0:
            suggestion = "⚠️ [Suggestion]: Tỉ lệ thắng thấp, hãy thử nới rộng SL hoặc kiểm tra lại điểm vào lệnh."
        elif win_rate > 70 and total_profit > 0:
            suggestion = "🚀 [Suggestion]: Phong độ tốt! Có thể cân nhắc tăng mục tiêu TP hoặc giữ Runner dài hơn."
        
        report["suggestion"] = suggestion
        
        mt5.shutdown()
        return report

    def _should_send_daily_briefing(self):
        """Check file-based lock for daily briefing with atomic lock to prevent race condition"""
        log_file = "daily_briefing.log"
        now = datetime.now()
        today_str = now.strftime("%Y-%m-%d")
        
        # 1. Quick check main log
        try:
            if os.path.exists(log_file):
                with open(log_file, "r", encoding="utf-8") as f:
                    if f.read().strip() == today_str:
                        return False
        except: pass
            
        # 2. Atomic lock check for today
        self._ensure_lock_dir()
        lock_path = os.path.join(LOCK_DIR, f"briefing_{today_str}.lock")
        if os.path.exists(lock_path):
            return False
            
        try:
            # Atomic creation (fails if file exists)
            fd = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            os.close(fd)
            return True # Successfully locked, proceed to send
        except FileExistsError:
            return False # Already locked by another instance
        except Exception as e:
            # Fallback for folder errors, but risky for doubles
            return True 

    def _mark_daily_briefing_sent(self):
        """Update file-based lock after successful send"""
        log_file = "daily_briefing.log"
        now = datetime.now()
        today_str = now.strftime("%Y-%m-%d")
        try:
            with open(log_file, "w", encoding="utf-8") as f:
                f.write(today_str)
        except:
            pass

    def _is_event_locked(self, event_key):
        """Check and set atomic lock for a specific event alert"""
        self._ensure_lock_dir()
        lock_path = os.path.join(LOCK_DIR, f"{event_key}.lock")
        
        # 1. Quick check
        if os.path.exists(lock_path):
            # If lock is older than 24 hours, it's stale (though keys are date-specific)
            if (time.time() - os.path.getmtime(lock_path)) > 86400:
                try: os.remove(lock_path)
                except: pass
            else:
                return True
                
        # 2. Atomic creation
        try:
            fd = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            os.close(fd)
            return False # Successfully locked (first time)
        except FileExistsError:
            return True # Already locked
        except:
            return True

    def send_daily_briefing(self):
        """Send the daily report (News + Season Info)"""
        print(f"--- Sending Daily Briefing at {datetime.now()} ---")
        today_str = datetime.now().strftime("%Y-%m-%d")
        lock_path = os.path.join(LOCK_DIR, f"briefing_{today_str}.lock")
        
        try:
            # Detect Language from settings
            settings = load_json_file(SETTINGS_FILE, {})
            lang = settings.get("lang", "VN")
            
            # 1. Economic News
            news = get_economic_news(lang=lang)
            
            # Construct Message
            header = f"🤖 OPENCLAW AI - DAILY BRIEFING ({datetime.now().strftime('%d/%m/%Y')})\n"
            if lang == "EN":
                header = f"🤖 OPENCLAW AI - DAILY BRIEFING ({datetime.now().strftime('%m/%d/%Y')})\n"
            
            full_msg = header
            
            # Season info
            is_winter = is_winter_time()
            if lang == "VN":
                season_str = "MÙA ĐÔNG (GMT+2)" if is_winter else "MÙA HÈ (GMT+3)"
                full_msg += f"🗓️ Chế độ giờ: {season_str}\n\n"
            else:
                season_str = "WINTER TIME (GMT+2)" if is_winter else "SUMMER TIME (GMT+3)"
                full_msg += f"🗓️ Time Mode: {season_str}\n\n"
            
            if news:
                news_header = "🌍 TIN TỨC KINH TẾ:\n" if lang == "VN" else "🌍 ECONOMIC NEWS:\n"
                full_msg += news_header + "\n".join(news) + "\n\n"
                    
            if self.send_telegram(full_msg):
                self._mark_daily_briefing_sent()
                return True
            return False
        finally:
            # Cleanup atomic lock for today
            try:
                if os.path.exists(lock_path):
                    os.remove(lock_path)
            except: pass

    def send_rule_reminders(self, now, lang="VN"):
        today_str = now.strftime("%Y-%m-%d")
        key = f"rule_reminders_{today_str}"
        msg = generate_daily_reminder(now, lang=lang)
        if not msg:
            return False
        if self._is_event_locked(key):
            return False
        self.send_telegram(msg)
        return True

    def get_projected_pnl(self, symbol, target_price, profile_name=None):
        """
        Calculate projected PnL for all open positions of a symbol if price hits target_price.
        Returns a natural language message with random styles.
        """
        config = self.load_config()
        if not config:
            return "❌ Lỗi: Không tìm thấy cấu hình Profile."
            
        token = self.token or CURRENT_TOKEN
        
        profiles_to_try = []
        
        # 1. If profile_name is provided, try to find it first (Case Insensitive Partial Match)
        if profile_name:
            # print(f"🔍 Searching for profile matching: '{profile_name}'")
            for p_name, p_data in config.items():
                if profile_name.lower() in p_name.lower():
                    profiles_to_try.append(p_data)
                    # print(f"✅ Found matching profile: {p_name}")
            
            if not profiles_to_try:
                return f"❌ Lỗi: Không tìm thấy sàn nào có tên chứa '{profile_name}'."
        else:
            # 2. If no name provided, try Token Match
            target_profile = None
            for p_name, p_data in config.items():
                if p_data.get("tele_token") == token:
                    target_profile = p_data
                    break
            profiles_to_try = [target_profile] if target_profile else list(config.values())
        
        positions = None
        used_path = ""
        
        for profile in profiles_to_try:
            path = profile.get("path", "")
            if not path or not os.path.exists(path): continue
            
            # Try to initialize MT5 with this path
            if not mt5.initialize(path=path):
                # print(f"⚠️ Failed to init MT5 at: {path}")
                continue
            
            # Check if this MT5 instance actually has the positions we want
            positions = mt5.positions_get(symbol=symbol)
            
            if (positions is None or len(positions) == 0):
                base_symbol = re.sub(r"[^A-Z]", "", symbol)
                if base_symbol != symbol:
                    positions = mt5.positions_get(symbol=base_symbol)
                    if positions and len(positions) > 0:
                        symbol = base_symbol
            
            if positions is None or len(positions) == 0:
                 # Search all positions
                all_pos = mt5.positions_get()
                if all_pos:
                    for p in all_pos:
                        if symbol in p.symbol or p.symbol in symbol:
                            positions = mt5.positions_get(symbol=p.symbol)
                            symbol = p.symbol
                            break
                            
            if positions and len(positions) > 0:
                used_path = path
                # print(f"✅ Found {len(positions)} positions for {symbol} in {path}")
                break # Found valid positions, stop searching
            else:
                mt5.shutdown() # Close connection if this profile has no relevant positions
        
        if not positions or len(positions) == 0:
            return get_random_response("pnl_error_no_pos", symbol=symbol, count=len(profiles_to_try))

        symbol_info = mt5.symbol_info(symbol)
        if not symbol_info:
            mt5.shutdown()
            return f"❌ Lỗi: Không lấy được thông tin symbol {symbol}."

        total_pnl = 0.0
        total_lots = 0.0
        
        tick_value = symbol_info.trade_tick_value
        tick_size = symbol_info.trade_tick_size
        
        if tick_value == 0 or tick_size == 0:
            mt5.shutdown()
            return f"❌ Lỗi: Thông số symbol {symbol} không hợp lệ (TickValue/Size = 0)."

        for pos in positions:
            lots = pos.volume
            open_price = pos.price_open
            pos_type = pos.type # 0 for Buy, 1 for Sell
            
            if pos_type == mt5.POSITION_TYPE_BUY:
                pnl = (target_price - open_price) / tick_size * tick_value * lots
            else: # Sell
                pnl = (open_price - target_price) / tick_size * tick_value * lots
                
            total_pnl += pnl
            total_lots += lots

        mt5.shutdown()
        
        # Natural Language Response (Random Fun Style from Dictionary)
        acc_info = ""
        if profile_name:
            acc_info = f" ({profile_name.title()})"
            
        if total_pnl >= 0:
            msg = get_random_response("pnl_profit", symbol=symbol, acc=acc_info, price=target_price, pnl=total_pnl, lots=total_lots)
        else:
            msg = get_random_response("pnl_loss", symbol=symbol, acc=acc_info, price=target_price, pnl=abs(total_pnl), lots=total_lots)
            
        return msg

    def process_commands(self):
        """Check for commands via Telegram (Simple Polling + Natural Language)"""
        token = self.token or CURRENT_TOKEN
        chat_id_target = self.chat_id or CURRENT_CHAT_ID
        
        # Fallback to config if globals not set
        if not token or not chat_id_target:
            config = self.load_config()
            for p_name in config:
                p = config[p_name]
                if p.get("tele_token") and p.get("tele_chat"):
                    token = p["tele_token"]
                    chat_id_target = p["tele_chat"]
                    break
        
        if not token: return
        
        id_file = os.path.join(LOCK_DIR, "last_update_id.txt")
        last_id = 0
        if os.path.exists(id_file):
            try:
                with open(id_file, "r") as f:
                    last_id = int(f.read().strip())
            except: pass
            
        try:
            # Short timeout to keep loop responsive
            url = f"https://api.telegram.org/bot{token}/getUpdates?offset={last_id + 1}&timeout=1"
            with urllib.request.urlopen(url, timeout=5) as response:
                data = json.load(response)
                if not data.get("ok"): return
                
                new_last_id = last_id
                for update in data.get("result", []):
                    new_last_id = update["update_id"]
                    
                    # Support both Message (Private/Group) and Channel Post
                    msg_obj = update.get("message") or update.get("channel_post")
                    if not msg_obj: continue
                    
                    text = (msg_obj.get("text") or "").strip()
                    chat_obj = msg_obj.get("chat", {})
                    chat_id = chat_obj.get("id")
                    
                    if not text: continue
                    
                    # LOG TO CONSOLE (Visible for user debug)
                    print(f"📩 [{datetime.now().strftime('%H:%M:%S')}] Received: '{text}' (Chat: {chat_id})")
                    
                    # Identify PnL request (Command or Natural Language)
                    is_pnl_command = False
                    if text.startswith("/pnl"): is_pnl_command = True
                    else:
                        triggers = ["tính", "pnl", "lãi", "lỗ", "dự báo", "chạm", "mức"]
                        if any(t in text.lower() for t in triggers):
                            is_pnl_command = True
                    
                    if not is_pnl_command: continue

                    # 1. Standard Command: /pnl SYMBOL PRICE
                    if text.startswith("/pnl"):
                        parts = text.split()
                        if len(parts) >= 3:
                            symbol = parts[1].upper()
                            try:
                                target_price = float(parts[2])
                                result_msg = self.get_projected_pnl(symbol, target_price)
                                self.send_telegram_to_chat(result_msg, chat_id)
                            except:
                                self.send_telegram_to_chat("❌ Cú pháp: /pnl SYMBOL PRICE", chat_id)
                        continue

                    # 2. Natural Language Parsing
                    text_lower = text.lower()
                    # Symbol: 2-12 Uppercase + optional suffixes
                    symbol_match = re.search(r"([A-Z]{2,12}(?:\+)?(?:\.m)?)", text.upper())
                    # Price: Any number (with or without decimal)
                    price_match = re.search(r"(\d+(?:\.\d+)?)", text)
                    
                    # Profile: Optional match for words like "Vantage", "Th5ers", "Exness"
                    # Assumption: Profile name usually starts with Uppercase or is specific keyword
                    # We will try to capture potential profile name if it exists
                    profile_name = None
                    potential_profiles = ["vantage", "th5ers", "exness", "icmarkets", "fbs", "xm", "pepperstone"]
                    for p in potential_profiles:
                        if p in text_lower:
                            profile_name = p
                            break
                    
                    if symbol_match and price_match:
                        symbol = symbol_match.group(1)
                        try:
                            target_price = float(price_match.group(1))
                            if not symbol.isdigit():
                                print(f"🤖 Processing NLP Match: {symbol} at {target_price} (Profile: {profile_name})")
                                result_msg = self.get_projected_pnl(symbol, target_price, profile_name)
                                self.send_telegram_to_chat(result_msg, chat_id)
                        except Exception as e:
                            print(f"⚠️ Error: {e}")
                            
                    # 3. Check for other commands (Placeholder for future implementation)
                    # if "/list" in text_lower:
                    #     msg = get_random_response("list_header") + get_random_response("list_empty")
                    #     self.send_telegram_to_chat(msg, chat_id)

                if new_last_id != last_id:
                    with open(id_file, "w") as f:
                        f.write(str(new_last_id))
        except Exception as e:
            # Silent for connection errors, but print major ones
            if "HTTP Error 409" in str(e):
                print("⚠️ [Error 409] Bot is competing with another polling/webhook script. Close other bots!")
            elif "timeout" not in str(e).lower():
                pass # print(f"⚠️ [Polling Error]: {e}")

    def send_telegram_to_chat(self, message, chat_id):
        """Send telegram message to a specific chat ID"""
        token = self.token or CURRENT_TOKEN
        if not token: return
        try:
            msg = urllib.parse.quote(message)
            url = f"https://api.telegram.org/bot{token}/sendMessage?chat_id={chat_id}&text={msg}"
            with urllib.request.urlopen(url, timeout=10) as response:
                print(f"✅ Sent response to {chat_id}")
                return response.read()
        except Exception as e:
            print(f"❌ Error sending to {chat_id}: {e}")

    def monitor_loop(self):
        # Fix unicode for Windows console
        try:
            if sys.stdout.encoding != 'utf-8':
                sys.stdout.reconfigure(encoding='utf-8')
        except:
            pass

        def safe_print(msg):
            try:
                print(msg)
            except UnicodeEncodeError:
                try:
                    # Fallback for systems that don't support emoji in console
                    print(msg.encode('ascii', 'ignore').decode('ascii'))
                except:
                    pass

        safe_print("🌍 OAK Trading Reminder Service is running...")
        safe_print("   - Mode: News + Trading Reminders")
        safe_print("   - Output: Telegram Only")
        
        self.running = True
        
        # Initialize last_briefing_date from file if it exists to prevent double on restart
        log_file = "daily_briefing.log"
        if os.path.exists(log_file):
            try:
                with open(log_file, "r", encoding="utf-8") as f:
                    date_str = f.read().strip()
                self.last_briefing_date = datetime.strptime(date_str, "%Y-%m-%d").date()
            except: pass

        # Detect Language from settings for monitor loop
        settings = load_json_file(SETTINGS_FILE, {})
        lang = settings.get("lang", "VN")
        
        # Startup check: Send briefing if not yet sent today
        if self._should_send_daily_briefing():
            if self.send_daily_briefing():
                self.last_briefing_date = datetime.now().date()

        while self.running and not self._stop_event.is_set():
            # 0. Check for Telegram commands removed to avoid polling conflicts with Manager
            # self.process_commands()

            now = datetime.now()
            
            # 1. Daily Briefing (once a day at 06:00)
            if now.hour == 6 and now.minute == 0:
                if self.last_briefing_date != now.date():
                    # Check file lock
                    if self._should_send_daily_briefing():
                        self.send_daily_briefing()
                    self.last_briefing_date = now.date()
                    self.alerted_events.clear() # Reset alerts for new day
                self.send_rule_reminders(now, lang=lang)
            
            # 2. Check Schedule for Alerts
            schedule = get_daily_schedule(now, lang=lang)

            for event in schedule:
                event_h = event["hour"]
                event_m = event["minute"]
                syms = event["syms"]
                note = event["note"]
                
                # Unique keys for locks
                date_str = now.strftime("%Y-%m-%d")
                action_key = f"alert_action_{date_str}_{event_h:02d}{event_m:02d}"
                pre_key = f"alert_pre_{date_str}_{event_h:02d}{event_m:02d}"
                
                # A. Action Now Alert (Exact time)
                if now.hour == event_h and now.minute == event_m:
                    if not self._is_event_locked(action_key):
                        msg = f"🔔 [OAK ALERT] ACTION NOW!\n• Time: {event_h:02d}:{event_m:02d}\n• Pair: {syms}\n• Note: {note}"
                        if lang == "EN":
                            msg = f"🔔 [OAK ALERT] ACTION NOW!\n• Time: {event_h:02d}:{event_m:02d}\n• Pair: {syms}\n• Note: {note}"
                        self.send_telegram(msg)
                        winsound.Beep(1000, 500) # PC Alert

                # B. Pre-Alert (30 mins before)
                # Calculate pre-alert time
                target_dt = now.replace(hour=event_h, minute=event_m, second=0, microsecond=0)
                pre_dt = target_dt - timedelta(minutes=30)
                
                if now.hour == pre_dt.hour and now.minute == pre_dt.minute:
                    if not self._is_event_locked(pre_key):
                        msg = f"⏰ [OAK REMINDER] In 30 mins:\n• Time: {event_h:02d}:{event_m:02d}\n• Pair: {syms}\n• Note: {note}"
                        if lang == "VN":
                            msg = f"⏰ [OAK NHẮC NHỞ] Còn 30 phút nữa:\n• Giờ: {event_h:02d}:{event_m:02d}\n• Cặp: {syms}\n• Ghi chú: {note}"
                        self.send_telegram(msg)
            
            # Sleep in chunks to allow faster stopping
            for _ in range(CHECK_INTERVAL):
                if not self.running or self._stop_event.is_set(): break
                time.sleep(1)

    def start(self):
        t = threading.Thread(target=self.monitor_loop, daemon=True)
        t.start()
        return t

    def stop(self):
        self.running = False
        self._stop_event.set()

# Wrapper for backward compatibility
def load_config():
    return OakTradingReminder().load_config()

def send_telegram(message):
    OakTradingReminder().send_telegram(message)

def get_performance_report(profile):
    return OakTradingReminder().get_performance_report(profile)

def send_daily_briefing():
    OakTradingReminder().send_daily_briefing()

def monitor_loop():
    OakTradingReminder().monitor_loop()

_active_reminders = {}  # {(token, chat_id): instance}

def start_reminder_thread():
    """Start the reminder loop in a background thread"""
    # Use global CURRENT_TOKEN/CHAT_ID if set
    token = CURRENT_TOKEN
    chat_id = CURRENT_CHAT_ID
    
    if not token or not chat_id:
        # Try to load from config if globals are not set
        # But this function is usually called after set_credentials
        return None

    key = (token, chat_id)
    
    # Check if already running for this Token+ChatID
    if key in _active_reminders:
        existing_instance = _active_reminders[key]
        if existing_instance.running:
            print(f"⚠️ Reminder thread already running for this Token/ChatID. Skipping new thread to avoid spam.")
            return existing_instance
        else:
            # If it exists but stopped, remove it and start new
            del _active_reminders[key]

    reminder = OakTradingReminder(token, chat_id)
    t = reminder.start()
    _active_reminders[key] = reminder
    return t


if __name__ == "__main__":
    monitor_loop()
