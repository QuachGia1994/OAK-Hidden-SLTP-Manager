# -*- coding: utf-8 -*-
"""
Fact-Check Worker - polls Redis for pending requests, searches web, stores results.
Run standalone or integrate into mt5_signal_bot.py main loop.
"""
import os
import sys
import json
import time
import re
import urllib.request
import urllib.parse

# Redis config (Upstash REST API)
REDIS_URL = os.environ.get("UPSTASH_REDIS_REST_URL", "")
REDIS_TOKEN = os.environ.get("UPSTASH_REDIS_REST_TOKEN", "")
FACTCHECK_KEY = "sltp:factcheck"

# High-reliability news domains
HIGH_RELIABILITY = {
    "reuters.com", "apnews.com", "bbc.com", "bbc.co.uk", "cnn.com",
    "nytimes.com", "washingtonpost.com", "theguardian.com", "aljazeera.com",
    "bloomberg.com", "ft.com", "wsj.com", "economist.com", "nature.com",
    "sciencedaily.com", "who.int", "imf.org", "worldbank.org",
}
MEDIUM_RELIABILITY = {
    "cnbc.com", "foxnews.com", "nbcnews.com", "cbsnews.com", "abcnews.go.com",
    "usatoday.com", "latimes.com", "chicagotribune.com", "nypost.com",
    "dailymail.co.uk", "mirror.co.uk", "independent.co.uk",
    "vnexpress.net", "tuoitre.vn", "thanhnien.vn", "vnexpress.net",
    "cafef.vn", "vietstock.vn", "cafebiz.vn",
}


def redis_request(method, key, value=None):
    """Make a request to Upstash Redis REST API."""
    if not REDIS_URL or not REDIS_TOKEN:
        print("[ERROR] REDIS not configured")
        return None
    url = f"{REDIS_URL}/{key}"
    headers = {
        "Authorization": f"Bearer {REDIS_TOKEN}",
        "Content-Type": "application/json",
    }
    data = json.dumps(value).encode() if value is not None else None
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        resp = urllib.request.urlopen(req, timeout=15)
        result = json.loads(resp.read())
        return result.get("result")
    except Exception as e:
        print(f"[ERROR] Redis {method} failed: {e}")
        return None


def extract_claims(text):
    """Extract key claims from text. Simple sentence-based approach."""
    sentences = re.split(r'[.!?]+', text)
    claims = []
    for s in sentences:
        s = s.strip()
        if len(s) > 20 and len(s) < 200:
            claims.append(s)
    return claims[:5]


def search_web(query):
    """Search web using Brave Search API (free tier) or DuckDuckGo fallback."""
    results = []
    brave_key = os.environ.get("BRAVE_API_KEY", "")
    if brave_key:
        try:
            encoded = urllib.parse.quote(query)
            url = f"https://api.search.brave.com/res/v1/web/search?q={encoded}&count=5"
            req = urllib.request.Request(url, headers={
                "Accept": "application/json",
                "Accept-Encoding": "gzip",
                "X-Subscription-Token": brave_key,
            })
            resp = urllib.request.urlopen(req, timeout=10)
            data = json.loads(resp.read())
            for r in data.get("web", {}).get("results", []):
                results.append({
                    "title": r.get("title", ""),
                    "url": r.get("url", ""),
                    "snippet": r.get("description", ""),
                })
            return results
        except Exception as e:
            print(f"[WARN] Brave search failed: {e}")

    # DuckDuckGo HTML fallback
    try:
        encoded = urllib.parse.quote(query)
        url = f"https://html.duckduckgo.com/html/?q={encoded}"
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        resp = urllib.request.urlopen(req, timeout=10)
        html = resp.read().decode("utf-8", errors="ignore")
        # Simple regex extraction
        titles = re.findall(r'class="result__a"[^>]*>(.*?)</a>', html)
        urls = re.findall(r'class="result__url"[^>]*>(.*?)</a>', html)
        snippets = re.findall(r'class="result__snippet"[^>]*>(.*?)</td>', html, re.DOTALL)
        for i in range(min(5, len(titles))):
            clean_title = re.sub(r'<[^>]+>', '', titles[i]).strip() if i < len(titles) else ""
            clean_url = urls[i].strip() if i < len(urls) else ""
            clean_snippet = re.sub(r'<[^>]+>', '', snippets[i]).strip() if i < len(snippets) else ""
            if clean_title and clean_url:
                results.append({
                    "title": clean_title,
                    "url": clean_url,
                    "snippet": clean_snippet,
                })
    except Exception as e:
        print(f"[WARN] DuckDuckGo search failed: {e}")
    return results


def classify_reliability(url):
    """Classify source reliability based on domain."""
    try:
        domain = urllib.parse.urlparse(url).netloc.lower()
        for d in HIGH_RELIABILITY:
            if d in domain:
                return "high"
        for d in MEDIUM_RELIABILITY:
            if d in domain:
                return "medium"
    except:
        pass
    return "low"


def check_agreement(claim, snippet):
    """Check if a source agrees with, contradicts, or is neutral to a claim."""
    claim_lower = claim.lower()
    snippet_lower = snippet.lower()

    contradict_words = ["không", "否认", "false", "fake", "misleading", "debunked",
                        "hoax", "disputed", "refuted", "incorrect", "wrong"]
    confirm_words = ["xác nhận", "confirm", "reported", "announced", "confirmed",
                     "thực tế", "fact", "official", "according to"]

    has_contradict = any(w in snippet_lower for w in contradict_words)
    has_confirm = any(w in snippet_lower for w in confirm_words)

    if has_contradict and not has_confirm:
        return False
    if has_confirm and not has_contradict:
        return True
    return None


def process_factcheck(item):
    """Process a single fact-check request."""
    text = item.get("text", "")
    claims = extract_claims(text)
    all_sources = []
    seen_urls = set()

    for claim in claims:
        search_results = search_web(claim)
        for sr in search_results:
            if sr["url"] in seen_urls:
                continue
            seen_urls.add(sr["url"])
            reliability = classify_reliability(sr["url"])
            agrees = check_agreement(claim, sr["snippet"])
            all_sources.append({
                "title": sr["title"],
                "url": sr["url"],
                "snippet": sr["snippet"],
                "agrees": agrees,
                "reliability": reliability,
            })

    # Sort: confirming high-reliability first
    def sort_key(s):
        agree_score = 1 if s["agrees"] is True else (-1 if s["agrees"] is False else 0)
        rel_score = {"high": 3, "medium": 2, "low": 1}.get(s["reliability"], 0)
        return (-agree_score, -rel_score)

    all_sources.sort(key=sort_key)

    # Calculate score
    score = 50
    confirming_high = sum(1 for s in all_sources if s["agrees"] is True and s["reliability"] == "high")
    confirming_med = sum(1 for s in all_sources if s["agrees"] is True and s["reliability"] == "medium")
    contradicting = sum(1 for s in all_sources if s["agrees"] is False)

    score += min(confirming_high * 10, 30)
    score += min(confirming_med * 5, 15)
    score -= contradicting * 15
    score = max(0, min(100, score))

    # Verdict
    if score >= 80:
        verdict = "credible"
    elif score >= 50:
        verdict = "mixed"
    elif score >= 20:
        verdict = "unreliable"
    else:
        verdict = "unverifiable"

    # Summary
    confirming = sum(1 for s in all_sources if s["agrees"] is True)
    neutral = sum(1 for s in all_sources if s["agrees"] is None)
    summary_parts = [
        f"Tìm thấy {len(all_sources)} nguồn liên quan.",
        f"{confirming} nguồn xác nhận, {contradicting} nguồn phản bác, {neutral} trung lập.",
    ]
    if confirming_high > 0:
        summary_parts.append(f"{confirming_high} nguồn uy tín (Reuters, BBC, AP...) xác nhận.")
    if contradicting > 0:
        summary_parts.append(f"Có {contradicting} nguồn phản bác - cần thận trọng.")
    if len(all_sources) == 0:
        summary_parts.append("Không tìm thấy nguồn tin nào liên quan trên web.")

    return {
        "score": score,
        "verdict": verdict,
        "sources": all_sources[:15],
        "summary": " ".join(summary_parts),
        "key_claims": claims,
    }


def main():
    print("=" * 50)
    print("  Fact-Check Worker")
    print(f"  Redis: {'configured' if REDIS_URL else 'NOT configured'}")
    print("=" * 50)

    if not REDIS_URL:
        print("[ERROR] Set UPSTASH_REDIS_REST_URL and UPSTASH_REDIS_REST_TOKEN")
        sys.exit(1)

    while True:
        try:
            items = redis_request("GET", FACTCHECK_KEY) or []
            pending = [i for i in items if i.get("status") == "pending"]

            if pending:
                for item in pending[:3]:  # Process max 3 per cycle
                    item_id = item["id"]
                    print(f"\n[CHECK] Processing: {item['text'][:50]}...")

                    # Mark as processing
                    item["status"] = "processing"
                    redis_request("SET", FACTCHECK_KEY, items)

                    try:
                        result = process_factcheck(item)
                        item["status"] = "done"
                        item["result"] = result
                        print(f"[DONE] Score: {result['score']}, Verdict: {result['verdict']}")
                    except Exception as e:
                        item["status"] = "error"
                        item["result"] = {"score": 0, "verdict": "error", "sources": [], "summary": str(e), "key_claims": []}
                        print(f"[ERROR] {e}")

                    redis_request("SET", FACTCHECK_KEY, items)
            else:
                print(".", end="", flush=True)

        except Exception as e:
            print(f"\n[ERROR] {e}")

        time.sleep(5)


if __name__ == "__main__":
    main()
