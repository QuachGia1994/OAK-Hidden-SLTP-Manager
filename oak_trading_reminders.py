# -*- coding: utf-8 -*-
import os
import json
import time
import urllib.request
import urllib.parse
import ssl
from datetime import datetime, timedelta, timezone
import xml.etree.ElementTree as ET
import MetaTrader5 as mt5
import threading
import sys
import glob
import winsound # For PC Alarm
import re
from oak_response_dict import get_random_response # Import new response module
from utils import load_json_file
from oak_logger import setup_logger

try:
    from zoneinfo import ZoneInfo
except ImportError:
    ZoneInfo = None  # type: ignore

log = setup_logger("reminder")


def _get_display_tz():
    """Display timezone from the local system, including current DST offset."""
    return datetime.now().astimezone().tzinfo or timezone.utc


def _get_display_tz_name():
    """Human-readable local display timezone label."""
    tz = _get_display_tz()
    return tz.tzname(datetime.now(tz)) or str(tz)


NEWS_DAY_ROLLOVER_HOUR = 6


def _get_news_day(now=None):
    """Economic-news day rolls over at 06:00 in the local system timezone."""
    display_tz = _get_display_tz()
    current = now or datetime.now(display_tz)
    if current.tzinfo is None:
        current = current.replace(tzinfo=display_tz)
    else:
        current = current.astimezone(display_tz)
    if current.hour < NEWS_DAY_ROLLOVER_HOUR:
        current -= timedelta(days=1)
    return current.date()


def _get_news_day_str(now=None):
    return _get_news_day(now).isoformat()


def _get_vn_tz():
    """Backward-compatible alias for the auto display timezone."""
    return _get_display_tz()


# Highlight these high-stakes events on desktop + dashboard
CRITICAL_NEWS_KEYWORDS = (
    "federal funds rate",
    "fed interest rate decision",
    "federal fund rate",
    "interest rate decision",
    "fomc statement",
    "fomc press conference",
    "fomc economic projections",
    "non-farm payrolls",
    "nonfarm payrolls",
    "non farm payrolls",
)


def is_critical_news_title(title: str) -> bool:
    t = (title or "").lower()
    return any(kw in t for kw in CRITICAL_NEWS_KEYWORDS)


def format_news_line(time_24, country, title, *, critical=None, impact_icon="🔴"):
    """Build display line. Critical events get a loud prefix for UI scan.

    Use ASCII tags [HIGH]/[NỔI BẬT] so CTkTextbox (poor emoji fonts) still shows impact.
    """
    if critical is None:
        critical = is_critical_news_title(title)
    if critical:
        return f"• {time_24} {country} {impact_icon} [NỔI BẬT] {title}"
    return f"• {time_24} {country} {impact_icon} [HIGH] {title}"

# --- CONFIG ---
CONFIG_FILE = "profiles.json"
SETTINGS_FILE = "settings.json"
CHECK_INTERVAL = 60  # Check every 60 seconds
LOCK_DIR = "sent_locks"

# Global credentials (optional override)
CURRENT_TOKEN = None
CURRENT_CHAT_ID = None

def set_credentials(token, chat_id):
    global CURRENT_TOKEN, CURRENT_CHAT_ID
    CURRENT_TOKEN = token
    CURRENT_CHAT_ID = chat_id

def load_json_file(path, default):
    try:
        if not os.path.exists(path):
            return default
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except json.JSONDecodeError as e:
        print(f"[WARN] Corrupt JSON {path}: {e}")
        return default
    except Exception:
        return default

# Bump when parse/timezone rules change so stale wrong-time cache is discarded.
_NEWS_CACHE_VERSION = 6


def get_economic_news(lang="VN"):
    # 1. Check Cache (versioned — force re-fetch after timezone/highlight fix)
    cache_file = f"news_cache_{lang}.json"
    today = _get_news_day()
    try:
        if os.path.exists(cache_file):
            with open(cache_file, "r", encoding="utf-8") as f:
                cache = json.load(f)
            if (
                cache.get("date") == str(today)
                and cache.get("v") == _NEWS_CACHE_VERSION
                and cache.get("news")
            ):
                return cache["news"]
    except Exception:
        pass

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
                json.dump(
                    {"date": str(today), "v": _NEWS_CACHE_VERSION, "news": news_list},
                    f,
                    ensure_ascii=False,
                )
        except Exception:
            pass
        
    return news_list


def _news_lines_to_dashboard_items(news_lines, source_date):
    """Convert Telegram news lines into Dashboard API news objects."""
    items = []
    timezone_label = _get_display_tz_name()
    for raw in news_lines or []:
        line = str(raw).lstrip("•- ").strip()
        line = re.sub(r"^⚠️\s*", "", line)
        match = re.match(r"(\d{1,2}:\d{2})\s+(\w+)\s+(.+)", line)
        if not match:
            continue
        time_str, currency, rest = match.group(1), match.group(2), match.group(3)
        title = rest
        for token in ("🔴", "🟠", "🟢", "[HIGH]", "[high]", "[NỔI BẬT]", "[NOI BAT]", "⚠️"):
            title = title.replace(token, "")
        title = re.sub(r"\s+", " ", title).strip()
        critical = is_critical_news_title(title) or "NỔI BẬT" in raw or "NOI BAT" in raw.upper()
        items.append({
            "date": source_date,
            "time": time_str,
            "local_time": time_str,
            "time_zone": timezone_label,
            "currency": currency,
            "title": title,
            "impact": "high",
            "critical": critical,
        })
    items.sort(key=lambda item: (0 if item.get("critical") else 1, item.get("time") or "99:99"))
    return items


def _push_news_to_dashboard(news_lines, source_date):
    """Push Daily Briefing news to the web dashboard, including [] to clear stale news."""
    dashboard_url = (os.environ.get("DASHBOARD_API_URL") or "").rstrip("/")
    api_key = os.environ.get("DASHBOARD_API_KEY") or ""
    if not dashboard_url:
        config = load_json_file("config.json", {})
        dashboard_url = (config.get("dashboard_url") or "").rstrip("/")
        api_key = api_key or config.get("dashboard_api_key", "")
    if not dashboard_url:
        return
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["X-API-Key"] = api_key
    payload = json.dumps(_news_lines_to_dashboard_items(news_lines, source_date)).encode("utf-8")
    request = urllib.request.Request(
        f"{dashboard_url}/api/news",
        data=payload,
        headers=headers,
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=15) as response:
        response.read()

def _make_ssl_context():
    """Try verified SSL first; fallback to unverified for legacy servers."""
    try:
        ctx = ssl.create_default_context()
        ctx.options |= 0x4  # OP_LEGACY_SERVER_CONNECT
        return ctx
    except Exception:
        pass
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    return ctx

def _fetch_news_fresh(lang="VN"):
    ctx = _make_ssl_context()

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
    display_tz = _get_display_tz()
    today = _get_news_day()
    
    if context is None:
        context = _make_ssl_context()
    
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
                dt_local = dt_obj.astimezone(display_tz)
                if dt_local.date() != today: continue
                event_time_str = dt_local.strftime("%H:%M")
            except:
                continue
        else: continue
        
        # INVESTING.COM RSS doesn't always have impact tags, but we filter by high keywords
        title_lower = title.lower()
        if any(kw in title_lower for kw in ["high impact", "fed", "cpi", "nfp", "gdp", "rate", "powell", "ecb", "fomc"]):
            found_events = True
            icon = "🔴"
            out.append(format_news_line(event_time_str, "USD", title, impact_icon=icon))
            
    if not found_events:
        return [] # Don't return empty msg here, let _fetch_news_fresh handle it
    
    out.sort(key=lambda line: (0 if "TIN NỔI BẬT" in line else 1, line))
    return out

def fetch_myfxbook_rss(lang="VN", context=None):
    url = "https://www.myfxbook.com/rss/forex-economic-calendar-events"
    display_tz = _get_display_tz()
    today = _get_news_day()
    
    # SSL Context to avoid handshake errors
    if context is None:
        context = _make_ssl_context()
    
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
                dt_local = dt_obj.astimezone(display_tz)
                
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
        icon = "🔴"
        out.append(format_news_line(event_time_str, currency or "???", clean_title, impact_icon=icon))

    if not found_events:
         return []

    out.sort()
    return out

def fetch_litefinance_rss(lang="VN", context=None):
    # https://www.litefinance.org/rss/economic-calendar-feed/
    url = "https://www.litefinance.org/rss/economic-calendar-feed/"
    display_tz = _get_display_tz()
    today = _get_news_day()
    
    if context is None:
        context = _make_ssl_context()
    
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
                dt_local = dt_obj.astimezone(display_tz)
                if dt_local.date() != today: continue
                event_time_str = dt_local.strftime("%H:%M")
            except:
                try:
                    dt_obj = datetime.strptime(pub_date_str, "%a, %d %b %Y %H:%M:%S GMT")
                    dt_obj = dt_obj.replace(tzinfo=timezone.utc)
                    dt_local = dt_obj.astimezone(display_tz)
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
        icon = "🔴"
        out.append(f"• {event_time_str} {icon} {title}")
        
    if not found_events:
        return []
    
    out.sort()
    return out


def fetch_forexfactory_xml(lang="VN", context=None):
    url = "https://nfs.faireconomy.media/ff_calendar_thisweek.xml"
    display_tz = _get_display_tz()
    today = _get_news_day()
    
    if context is None:
        context = _make_ssl_context()
    
    req = urllib.request.Request(
        url, 
        headers={'User-Agent': 'Mozilla/5.0'}
    )
    
    with urllib.request.urlopen(req, timeout=30, context=context) as response:
        data = response.read()
        
    root = ET.fromstring(data)
    # Structure: <weeklyevents><event><title>...</title><country>USD</country><date>02-17-2026</date><time>1:30pm</time><impact>High</impact>...</event>...
    
    out = []
    found_events = False
    
    for event in root.findall("event"):
        event_date_str = event.findtext("date")  # MM-DD-YYYY
        event_time_str = (event.findtext("time") or "").strip()  # 1:30pm | All Day | Tentative

        title = (event.findtext("title") or "").strip()
        country = (event.findtext("country") or "").strip()
        impact_str = event.findtext("impact")  # High, Medium, Low

        # FILTER: Only show High Impact
        if impact_str != "High":
            continue

        # Format time to the local system display timezone. The weekly XML
        # feed exposes event times in UTC; the OS timezone handles DST.
        try:
            if not event_time_str or event_time_str.lower() in ("all day", "tentative", "day"):
                # All-day: keep on calendar date, show as 00:00 local of that UTC day
                dt_src = datetime.strptime(event_date_str, "%m-%d-%Y")
                dt_full_src = dt_src.replace(hour=0, minute=0, tzinfo=timezone.utc)
            else:
                t_obj = datetime.strptime(event_time_str.replace(" ", ""), "%I:%M%p")
                dt_src = datetime.strptime(event_date_str, "%m-%d-%Y").date()
                dt_full_src = datetime.combine(dt_src, t_obj.time()).replace(tzinfo=timezone.utc)

            dt_local = dt_full_src.astimezone(display_tz)

            if dt_local.date() != today:
                continue

            time_24 = dt_local.strftime("%H:%M")
        except Exception:
            try:
                dt_obj = datetime.strptime(event_date_str, "%m-%d-%Y").date()
                if dt_obj != today:
                    continue
                time_24 = event_time_str or "??:??"
            except Exception:
                continue

        icon = "🔴"
        found_events = True
        out.append(format_news_line(time_24, country, title, impact_icon=icon))

    if not found_events:
        return []

    # Critical (FFR etc.) first, then by time
    def _sort_key(line):
        crit = 0 if "TIN NỔI BẬT" in line else 1
        m = re.search(r"(\d{1,2}:\d{2})", line)
        return (crit, m.group(1) if m else "99:99")

    out.sort(key=_sort_key)
    return out


def _friday_of_same_week(date_obj):
    return date_obj + timedelta(days=(4 - date_obj.weekday()))


def _is_first_week_rule(date_obj):
    friday = _friday_of_same_week(date_obj)
    return friday.weekday() == 4 and 1 <= friday.day <= 7


def _format_group_slots(slots):
    if not slots:
        return "-"
    return ", ".join(f"{slot_time} {action}" for slot_time, action in slots)


def get_day_notes(now, lang="VN"):
    """Daily notes synced with the Dashboard "Rules today" matrix."""
    weekday = now.weekday()
    today = now.date() if hasattr(now, "date") and callable(now.date) else now

    if weekday >= 5:
        if lang == "VN":
            return ["Cuối tuần: không trade theo schedule bot."]
        return ["Weekend: no bot trade schedule."]

    day_rules_vn = {
        0: ["Slots: H=2-5,7-9,11-15", "H=2,3: XAUUSD đảo từ H=5 hôm qua; GBPAUD cùng chiều H=5 hôm qua.", "H=7,8: XAUUSD đảo từ H=5 hôm nay.", "H=9: GBP đảo từ H=5 hôm qua.", "H=11: Phân nhóm H1 XAUUSD (SW/BT) từ H=10,9,8,7.", "H=14: GBP cùng chiều H=5 hôm nay."],
        1: ["Slots: H=2-5,7-9,11-15", "H=2,3: XAUUSD đảo từ H=5 hôm qua; GBPAUD cùng chiều H=5 hôm qua.", "H=7,8: XAUUSD đảo từ H=5 hôm nay.", "H=9: GBP đảo từ H=5 hôm qua.", "H=11: Phân nhóm H1 XAUUSD (SW/BT) từ H=10,9,8,7.", "H=14: GBP cùng chiều H=5 hôm nay."],
        2: ["Slots: H=2-5,7-9,11-15", "H=2,3: XAUUSD đảo từ H=5 hôm qua.", "H=7,8: XAUUSD đảo từ H=5 hôm nay.", "H=9: XAUUSD đảo từ H=5 hôm nay.", "H=11: Phân nhóm H1 XAUUSD (SW/BT) từ H=10,9,8,7.", "H=14: Tắt nhóm GBP (Thứ 4)."],
        3: ["Slots: H=2-5,7-9,11-15", "H=2,3: XAUUSD & GBPAUD dùng lại lịch sử của Thứ 2.", "H=7,8: XAUUSD đảo từ H=5 hôm nay.", "H=9: GBP đảo từ H=5 hôm qua.", "H=11: Phân nhóm H1 XAUUSD (SW/BT) từ H=10,9,8,7.", "H=14: GBP cùng chiều H=5 hôm nay."],
        4: ["Slots: H=2-5,7-9,11-15", "H=2,3: XAUUSD đảo từ H=5 hôm qua; GBPAUD cùng chiều H=5 hôm qua.", "H=7,8: XAUUSD đảo từ H=5 hôm nay.", "H=9: GBP cùng chiều H=5 hôm qua (Thứ 6).", "H=11: Phân nhóm H1 XAUUSD (SW/BT) từ H=10,9,8,7.", "H=14: GBP đảo từ H=5 hôm nay (Thứ 6)."],
    }
    day_rules_en = {
        0: ["Slots: H=2-5,7-9,11-15", "H=2,3: XAUUSD reverses from H=5 yesterday; GBPAUD follows H=5 yesterday.", "H=7,8: XAUUSD reverses from H=5 today.", "H=9: GBP reverses from H=5 yesterday.", "H=11: Classify H1 XAUUSD group (SW/BT) from H=10,9,8,7.", "H=14: GBP follows H=5 today."],
        1: ["Slots: H=2-5,7-9,11-15", "H=2,3: XAUUSD reverses from H=5 yesterday; GBPAUD follows H=5 yesterday.", "H=7,8: XAUUSD reverses from H=5 today.", "H=9: GBP reverses from H=5 yesterday.", "H=11: Classify H1 XAUUSD group (SW/BT) from H=10,9,8,7.", "H=14: GBP follows H=5 today."],
        2: ["Slots: H=2-5,7-9,11-15", "H=2,3: XAUUSD reverses from H=5 yesterday.", "H=7,8: XAUUSD reverses from H=5 today.", "H=9: XAUUSD reverses from H=5 today.", "H=11: Classify H1 XAUUSD group (SW/BT) from H=10,9,8,7.", "H=14: GBP group disabled (Wed)."],
        3: ["Slots: H=2-5,7-9,11-15", "H=2,3: XAUUSD and GBPAUD reuse Monday's history.", "H=7,8: XAUUSD reverses from H=5 today.", "H=9: GBP reverses from H=5 yesterday.", "H=11: Classify H1 XAUUSD group (SW/BT) from H=10,9,8,7.", "H=14: GBP follows H=5 today."],
        4: ["Slots: H=2-5,7-9,11-15", "H=2,3: XAUUSD reverses from H=5 yesterday; GBPAUD follows H=5 yesterday.", "H=7,8: XAUUSD reverses from H=5 today.", "H=9: GBP follows H=5 yesterday (Fri).", "H=11: Classify H1 XAUUSD group (SW/BT) from H=10,9,8,7.", "H=14: GBP reverses from H=5 today (Fri)."],
    }

    notes_vn = list(day_rules_vn.get(weekday, []))
    notes_en = list(day_rules_en.get(weekday, []))

    try:
        from mt5_signal_bot import get_h11_priority_and_nogold_rules
        dt = now if isinstance(now, datetime) else datetime.combine(now, datetime.min.time())
        rules = get_h11_priority_and_nogold_rules(dt)
        p_label = rules["priority_label"]
        prev_group = rules["prev_h11_group"]
        priority_line = f"★ H=11 hôm qua ({prev_group}) ➔ {p_label}"
        notes_vn.insert(1, priority_line)
        notes_en.insert(1, priority_line)
        has_ng = rules["has_nogold_label"]
        if has_ng:
            today_group = rules.get("today_h11_group", "")
            ng_line = f"⚠️ H=11 hôm nay ({today_group}) ➔ H=12,13,15: gắn nhãn no-gold label"
            notes_vn.insert(2, ng_line)
            notes_en.insert(2, ng_line)
    except Exception:
        pass

    if lang == "VN":
        return notes_vn
    return notes_en

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

    def load_config(self):
        return load_json_file(CONFIG_FILE, {})

    def send_telegram(self, message):
        token = self.token or CURRENT_TOKEN
        chat_id = self.chat_id or CURRENT_CHAT_ID
        
        # Fallback to loading from file if not set
        if not token or not chat_id:
            from secret_store import resolve_telegram_token
            config = self.load_config()
            for p_name in config:
                p = config[p_name]
                if p.get("tele_chat"):
                    resolved = resolve_telegram_token(p_name, p.get("tele_token", ""))
                    if resolved:
                        token = resolved
                        chat_id = p["tele_chat"]
                        break
        
        if not token or not chat_id:
            print(f"DEBUG (No Telegram Config): {message}")
            return

        # Strip color tags for Telegram (they don't support custom HTML tags like <c=...>)
        clean_message = re.sub(r"<c=#[A-Fa-f0-9]{6}>", "", message)
        clean_message = clean_message.replace("", "")

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
                    except Exception: pass  # Lock file cleanup best-effort
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
        except Exception as e:
            log.warning("Reminder dedup log error: %s", e)
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
                except Exception: pass  # Lock file cleanup best-effort

        try:
            msg = urllib.parse.quote(clean_message, safe="*")
            url = f"https://api.telegram.org/bot{token}/sendMessage?chat_id={chat_id}&text={msg}&parse_mode=Markdown"
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
        now = datetime.now(_get_display_tz())
        if now.hour < NEWS_DAY_ROLLOVER_HOUR:
            return False
        today_str = _get_news_day_str(now)
        
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
        now = datetime.now(_get_display_tz())
        today_str = _get_news_day_str(now)
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
        now_display = datetime.now(_get_display_tz())
        print(f"--- Sending Daily Briefing at {now_display} ---")
        today_str = _get_news_day_str(now_display)
        lock_path = os.path.join(LOCK_DIR, f"briefing_{today_str}.lock")
        
        try:
            # Detect Language from settings
            settings = load_json_file(SETTINGS_FILE, {})
            lang = settings.get("lang", "VN")
            
            # 1. Economic News
            news = get_economic_news(lang=lang)
            try:
                _push_news_to_dashboard(news, today_str)
            except Exception as exc:
                print(f"[DASHBOARD] Daily briefing news push skipped: {exc}")
            
            # Construct Message
            briefing_day = _get_news_day(now_display)
            header = f"🤖 OPENCLAW AI - DAILY BRIEFING ({briefing_day.strftime('%d/%m/%Y')})\n"
            if lang == "EN":
                header = f"🤖 OPENCLAW AI - DAILY BRIEFING ({briefing_day.strftime('%m/%d/%Y')})\n"
            
            full_msg = header
            
            if lang == "VN":
                full_msg += f"🗓️ Giờ hiển thị: tự động theo hệ thống ({_get_display_tz_name()})\n\n"
            else:
                full_msg += f"🗓️ Display Time: system timezone ({_get_display_tz_name()})\n\n"
            
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
        """Check for commands via shared inbox (written by mimo_bot.py)."""
        chat_id_target = self.chat_id or CURRENT_CHAT_ID

        # Fallback to config if globals not set
        token = self.token or CURRENT_TOKEN
        if not token or not chat_id_target:
            from secret_store import resolve_telegram_token
            config = self.load_config()
            for p_name in config:
                p = config[p_name]
                if p.get("tele_chat"):
                    resolved = resolve_telegram_token(p_name, p.get("tele_token", ""))
                    if resolved:
                        token = resolved
                        chat_id_target = p["tele_chat"]
                        break

        if not chat_id_target: return

        # Read from shared inbox (mimo_bot.py writes here)
        inbox_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "tele_inbox.json")
        if not os.path.exists(inbox_file): return

        try:
            with open(inbox_file, "r", encoding="utf-8") as f:
                inbox = json.load(f)
            if not isinstance(inbox, list) or not inbox: return

            # Process and clear inbox
            processed_ids = set()
            for update in inbox:
                msg_obj = update.get("message") or update.get("channel_post")
                if not msg_obj: continue

                text = (msg_obj.get("text") or "").strip()
                chat_obj = msg_obj.get("chat", {})
                chat_id = chat_obj.get("id")
                update_id = update.get("update_id", 0)

                if not text or update_id in processed_ids: continue
                processed_ids.add(update_id)

                # LOG TO CONSOLE
                print(f"[{datetime.now().strftime('%H:%M:%S')}] Inbox: '{text}' (Chat: {chat_id})")

                # Identify PnL request
                is_pnl_command = False
                if text.startswith("/pnl"): is_pnl_command = True
                else:
                    triggers = ["tinh", "pnl", "lai", "lo", "du bao", "cham", "muc"]
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
                symbol_match = re.search(r"([A-Z]{2,12}(?:\+)?(?:\.m)?)", text.upper())
                price_match = re.search(r"(\d+(?:\.\d+)?)", text)

                # Profile match
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
                            print(f"Processing NLP Match: {symbol} at {target_price} (Profile: {profile_name})")
                            result_msg = self.get_projected_pnl(symbol, target_price, profile_name)
                            self.send_telegram_to_chat(result_msg, chat_id)
                    except Exception as e:
                        print(f"Error: {e}")

        except Exception as e:
            pass  # Silent for connection errors

    def send_telegram_to_chat(self, message, chat_id):
        """Send telegram message to a specific chat ID"""
        token = self.token or CURRENT_TOKEN
        if not token: return
        try:
            msg = urllib.parse.quote(message, safe="*")
            url = f"https://api.telegram.org/bot{token}/sendMessage?chat_id={chat_id}&text={msg}&parse_mode=Markdown"
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
                self.last_briefing_date = _get_news_day()

        while self.running and not self._stop_event.is_set():
            # 0. Check for Telegram commands removed to avoid polling conflicts with Manager
            # self.process_commands()

            now = datetime.now(_get_display_tz())

            # Skip weekends (Saturday=5, Sunday=6) - no trading
            if now.weekday() in (5, 6):
                for _ in range(CHECK_INTERVAL):
                    if not self.running or self._stop_event.is_set(): break
                    time.sleep(1)
                continue

            # 1. Daily Briefing (once a day at 06:00 local)
            if now.hour == 6 and now.minute == 0:
                news_day = _get_news_day(now)
                if self.last_briefing_date != news_day:
                    # Check file lock
                    if self._should_send_daily_briefing():
                        self.send_daily_briefing()
                    self.last_briefing_date = news_day
                    self.alerted_events.clear() # Reset alerts for new day

            # 2. Action Now alerts removed — use MT5 signal bot for Telegram alerts

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
