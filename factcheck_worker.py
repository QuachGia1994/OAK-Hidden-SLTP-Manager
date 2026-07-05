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
import unicodedata
import urllib.request
import urllib.parse
import html as html_mod

# Redis config (Upstash REST API)
# Try loading from .env file first
try:
    _env_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
    if os.path.exists(_env_file):
        with open(_env_file, "r") as _f:
            for _line in _f:
                _line = _line.strip()
                if _line and not _line.startswith("#") and "=" in _line:
                    _k, _v = _line.split("=", 1)
                    os.environ.setdefault(_k.strip(), _v.strip())
except Exception as e:
    print(f"[WARN] Could not load .env: {e}")

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

GOOGLE_FC_RATINGS_TRUE = {"true", "mostly true", "correct", "accurate", "supported"}
GOOGLE_FC_RATINGS_FALSE = {"false", "mostly false", "pants on fire", "incorrect", "misleading", "unproven", "refuted", "fake", "hoax", "scam"}
GOOGLE_FC_RATINGS_NEUTRAL = {"half true", "mixed", "partly true", "partly false", "outdated", "missing context", "unverified"}

def normalize_domain(url):
    """Normalize a URL into a compact domain key."""
    try:
        domain = urllib.parse.urlparse(url).netloc.lower()
    except Exception:
        return ""
    return domain[4:] if domain.startswith("www.") else domain


def normalize_text(text):
    """Normalize text for loose keyword matching."""
    if not text:
        return ""
    normalized = unicodedata.normalize("NFKD", text)
    stripped = "".join(ch for ch in normalized if not unicodedata.combining(ch))
    return stripped.lower()


def token_set(text):
    """Tokenize text into a compact keyword set."""
    return {token for token in re.findall(r"[a-z0-9]+", normalize_text(text)) if len(token) > 2}


def source_match_hits(query, source):
    """Count keyword overlaps between a query and a source."""
    query_tokens = token_set(query)
    if not query_tokens:
        return 0

    source_text = " ".join([
        source.get("title", ""),
        source.get("snippet", ""),
        normalize_domain(source.get("url", "")),
    ])
    source_norm = normalize_text(source_text)
    return sum(1 for token in query_tokens if token in source_norm)


def source_relevance(query, source):
    """Score how closely a source matches the current query."""
    query_tokens = token_set(query)
    if not query_tokens:
        return 0.0

    hits = source_match_hits(query, source)
    source_text = " ".join([
        source.get("title", ""),
        source.get("snippet", ""),
        normalize_domain(source.get("url", "")),
    ])
    source_norm = normalize_text(source_text)

    score = hits / max(3, min(len(query_tokens), 6))
    if normalize_text(query[:120]) in source_norm:
        score += 0.2
    if normalize_domain(source.get("url", "")) in HIGH_RELIABILITY:
        score += 0.1
    if source.get("engine") == "google_factcheck":
        score = max(score, 0.75)
    return max(0.0, min(1.0, score))


def should_keep_source(source):
    """Reject clearly off-topic hits before they affect the result set."""
    engine = source.get("engine", "web")
    reliability = source.get("reliability", "low")
    relevance = float(source.get("relevance", 0.0) or 0.0)
    hits = int(source.get("match_hits", 0) or 0)

    thresholds = {
        "google": 0.18,
        "duckduckgo": 0.15,
        "web": 0.2,
        "google_factcheck": 0.0,
    }
    threshold = thresholds.get(engine, 0.2)
    if engine == "google_factcheck":
        return True
    if hits >= 2:
        return True
    if reliability in {"high", "medium"} and hits >= 1 and relevance >= 0.12:
        return True
    return relevance >= threshold and hits >= 1


def redis_request(method, key, value=None):
    """Make a request to Upstash Redis REST API."""
    if not REDIS_URL or not REDIS_TOKEN:
        print("[ERROR] REDIS not configured")
        return None
    # Upstash REST API uses /get/{key} and /set/{key} paths
    if method == "GET":
        url = f"{REDIS_URL}/get/{key}"
    elif method == "SET":
        url = f"{REDIS_URL}/set/{key}"
    else:
        url = f"{REDIS_URL}/{method.lower()}/{key}"
    headers = {
        "Authorization": f"Bearer {REDIS_TOKEN}",
        "Content-Type": "application/json",
    }
    data = json.dumps(value).encode() if value is not None else None
    req = urllib.request.Request(url, data=data, headers=headers, method="POST" if method == "SET" else "GET")
    try:
        resp = urllib.request.urlopen(req, timeout=15)
        raw = resp.read()
        result = json.loads(raw)
        # Upstash returns {"result": <value>} - value might be a JSON string
        val = result.get("result")
        if isinstance(val, str):
            try:
                val = json.loads(val)
            except (json.JSONDecodeError, TypeError):
                pass
        return val
    except Exception as e:
        print(f"[ERROR] Redis {method} failed: {e}")
        return None


def extract_claims(text):
    """Extract key claims from text. Handles Vietnamese and English."""
    text = html_mod.unescape(text or "")
    text = re.sub(r"\s+", " ", text).strip()
    if not text:
        return []

    claims = []
    for sentence in re.split(r"[.!?]+|\n", text):
        sentence = re.sub(r"^[\-*??]+\s*", "", sentence.strip())
        if len(sentence) < 15:
            continue
        claims.append(sentence[:150])
        if len(claims) >= 5:
            break

    if not claims and len(text) >= 15:
        return [text[:150]]
    return claims


def simplify_query(claim):
    """Simplify a claim into a shorter search query."""
    stopwords = {
        "la", "cua", "va", "co", "duoc", "nay", "da", "dang", "se",
        "khong", "nhung", "cac", "mot", "voi", "cho", "tu", "trong",
        "the", "a", "an", "is", "are", "was", "were", "has", "have",
    }
    words = re.findall(r"[a-z0-9]+", normalize_text(claim))
    filtered = [w for w in words if w not in stopwords]
    query = " ".join(filtered[:8])
    if query:
        return query
    return " ".join(words[:8]) if words else claim[:100]


def search_google_web(query):
    """Search web using Google Custom Search JSON API."""
    results = []
    api_key = os.environ.get("GOOGLE_CSE_API_KEY", "") or os.environ.get("GOOGLE_SEARCH_API_KEY", "")
    cse_id = os.environ.get("GOOGLE_CSE_ID", "") or os.environ.get("GOOGLE_SEARCH_ENGINE_ID", "")
    if not api_key or not cse_id:
        return results

    try:
        encoded = urllib.parse.quote(query)
        url = (
            "https://www.googleapis.com/customsearch/v1"
            f"?key={urllib.parse.quote(api_key)}"
            f"&cx={urllib.parse.quote(cse_id)}"
            f"&q={encoded}&num=5&hl=en&safe=active"
        )
        req = urllib.request.Request(url, headers={
            "Accept": "application/json",
        })
        resp = urllib.request.urlopen(req, timeout=10)
        data = json.loads(resp.read())
        for item in data.get("items", [])[:5]:
            link = item.get("link", "")
            if not link:
                continue
            results.append({
                "title": item.get("title", ""),
                "url": link,
                "snippet": item.get("snippet", ""),
                "engine": "google",
                "reliability": classify_reliability(link),
            })
    except Exception as e:
        print(f"[WARN] Google web search failed: {e}")
    return results


def search_duckduckgo(query):
    """Search DuckDuckGo HTML fallback."""
    results = []

    try:
        data = urllib.parse.urlencode({'q': query, 'b': ''}).encode()
        req = urllib.request.Request('https://html.duckduckgo.com/html/', data=data, headers={
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Content-Type': 'application/x-www-form-urlencoded',
        })
        resp = urllib.request.urlopen(req, timeout=10)
        html = resp.read().decode('utf-8', errors='ignore')
        # Extract results using regex
        # URLs are in href of result__a tags
        result_links = re.findall(r'<a[^>]+class="result__a"[^>]+href="([^"]+)"[^>]*>(.*?)</a>', html, re.DOTALL)
        snippets = re.findall(r'class="result__snippet"[^>]*>(.*?)</td>', html, re.DOTALL)
        for i in range(min(5, len(result_links))):
            clean_url = result_links[i][0].strip()
            clean_title = re.sub(r'<[^>]+>', '', result_links[i][1]).strip()
            clean_title = html_mod.unescape(clean_title)
            clean_snippet = re.sub(r'<[^>]+>', '', snippets[i]).strip() if i < len(snippets) else ""
            clean_snippet = html_mod.unescape(clean_snippet)
            if clean_title and clean_url and 'duckduckgo' not in clean_url:
                results.append({
                    "title": clean_title,
                    "url": clean_url,
                    "snippet": clean_snippet,
                    "engine": "duckduckgo",
                })
    except Exception as e:
        print(f"[WARN] DuckDuckGo search failed: {e}")
    return results


def search_web(query):
    """Search web using multiple engines and merge the hits."""
    results = []
    results.extend(search_google_web(query))
    results.extend(search_duckduckgo(query))
    return results


def search_google_factcheck(query, api_key):
    """Search Google Fact Check Tools API for verified claims from IFCN-certified orgs."""
    results = []
    if not api_key:
        return results
    try:
        encoded = urllib.parse.quote(query)
        url = f"https://factchecktools.googleapis.com/v1alpha1/claims:search?query={encoded}&languageCode=en&maxAgeDays=90&pageSize=5&key={api_key}"
        req = urllib.request.Request(url, headers={"Accept": "application/json"})
        resp = urllib.request.urlopen(req, timeout=10)
        data = json.loads(resp.read())

        for claim in data.get("claims", []):
            claim_text = claim.get("text", "")
            reviews = claim.get("claimReview", [])
            if not reviews:
                continue
            review = reviews[0]
            rating_text = review.get("textualRating", "").lower()

            # Determine agreement from rating
            if any(r in rating_text for r in GOOGLE_FC_RATINGS_TRUE):
                agrees = True
            elif any(r in rating_text for r in GOOGLE_FC_RATINGS_FALSE):
                agrees = False
            else:
                agrees = None

            publisher = review.get("publisher", {})
            publisher_name = publisher.get("name", "Unknown")
            publisher_site = publisher.get("site", "")
            review_url = review.get("url", "")
            review_title = review.get("title", "")

            results.append({
                "title": f"[IFCN] {publisher_name}: {review_title}",
                "url": review_url or f"https://{publisher_site}",
                "snippet": f"Claim: {claim_text[:120]}... Rating: {review.get('textualRating', 'N/A')}",
                "agrees": agrees,
                "reliability": "high",  # IFCN certified = always high
                "publisher": publisher_name,
                "date": review.get("reviewDate", ""),
                "rating": review.get("textualRating", "N/A"),
                "engine": "google_factcheck",
            })
    except Exception as e:
        print(f"[WARN] Google Fact Check search failed: {e}")
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
    claim_lower = normalize_text(claim)
    snippet_lower = normalize_text(snippet)

    contradict_words = ["khong", "false", "fake", "misleading", "debunked",
                        "hoax", "disputed", "refuted", "incorrect", "wrong"]
    confirm_words = ["xac nhan", "confirm", "reported", "announced", "confirmed",
                     "thuc te", "fact", "official", "according to"]

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
        query = simplify_query(claim)
        query_variants = [query]
        if claim != query:
            query_variants.append(claim[:140])
        if len(query.split()) >= 4:
            query_variants.append(f"site:reuters.com {query}")
            query_variants.append(f"site:apnews.com {query}")
            query_variants.append(f"site:bbc.com {query}")

        claim_sources = 0
        for q in query_variants[:5]:
            print(f"  [SEARCH] {q[:60]}...")
            search_results = search_web(q)
            for sr in search_results:
                if sr["url"] in seen_urls:
                    continue
                seen_urls.add(sr["url"])
                reliability = classify_reliability(sr["url"])
                agrees = check_agreement(claim, sr["snippet"])
                source = {
                    "title": sr["title"],
                    "url": sr["url"],
                    "snippet": sr["snippet"],
                    "agrees": agrees,
                    "reliability": reliability,
                    "engine": sr.get("engine", "web"),
                }
                source["match_hits"] = source_match_hits(query, source)
                source["relevance"] = source_relevance(query, source)
                if not should_keep_source(source):
                    continue
                all_sources.append(source)
                claim_sources += 1

        # Google Fact Check Tools API (IFCN certified sources)
        # Use broader query for Google FC (it works better with general topics)
        google_fc_key = os.environ.get("GOOGLE_FACTCHECK_API_KEY", "")
        if google_fc_key:
            broad_query = ' '.join(query.split()[:5])  # Shorter, broader query
            print(f"  [GOOGLE-FC] Searching: {broad_query[:40]}...")
            google_results = search_google_factcheck(broad_query, google_fc_key)
            for gr in google_results:
                if gr["url"] in seen_urls:
                    continue
                seen_urls.add(gr["url"])
                gr["match_hits"] = source_match_hits(query, gr)
                gr["relevance"] = source_relevance(query, gr)
                all_sources.append(gr)
                claim_sources += 1

        # Second-pass authority search if the claim is still under-sourced.
        if claim_sources < 4:
            authority_queries = [
                f"site:reuters.com {query}",
                f"site:apnews.com {query}",
                f"site:bbc.com {query}",
                f"site:bloomberg.com {query}",
            ]
            for q in authority_queries:
                print(f"  [AUTH] {q[:60]}...")
                for sr in search_web(q):
                    if sr["url"] in seen_urls:
                        continue
                    seen_urls.add(sr["url"])
                    reliability = classify_reliability(sr["url"])
                    agrees = check_agreement(claim, sr["snippet"])
                    source = {
                        "title": sr["title"],
                        "url": sr["url"],
                        "snippet": sr["snippet"],
                        "agrees": agrees,
                        "reliability": reliability,
                        "engine": sr.get("engine", "web"),
                    }
                    source["match_hits"] = source_match_hits(query, source)
                    source["relevance"] = source_relevance(query, source)
                    if not should_keep_source(source):
                        continue
                    all_sources.append(source)
                    claim_sources += 1
                if claim_sources >= 6:
                    break

    # Sort: confirming high-reliability first
    def sort_key(s):
        agree_score = 1 if s["agrees"] is True else (-1 if s["agrees"] is False else 0)
        rel_score = {"high": 3, "medium": 2, "low": 1}.get(s["reliability"], 0)
        return (-agree_score, -rel_score)

    all_sources.sort(key=sort_key)

    # Calculate score
    score = 35
    scoring_sources = [s for s in all_sources if s.get("match_hits", 0) >= 2 or s.get("engine") == "google_factcheck"]
    if not scoring_sources:
        scoring_sources = [s for s in all_sources if s.get("match_hits", 0) >= 1]
    if not scoring_sources:
        scoring_sources = all_sources
    confirming_high = sum(1 for s in scoring_sources if s["agrees"] is True and s["reliability"] == "high")
    confirming_med = sum(1 for s in scoring_sources if s["agrees"] is True and s["reliability"] == "medium")
    contradicting = sum(1 for s in scoring_sources if s["agrees"] is False)
    unique_domains = {normalize_domain(s["url"]) for s in scoring_sources if s.get("url")}
    unique_engines = {s.get("engine", "web") for s in scoring_sources if s.get("engine")}
    google_confirm = any(s.get("engine") == "google_factcheck" and s["agrees"] is True for s in scoring_sources)

    score += min(confirming_high * 9, 27)
    score += min(confirming_med * 4, 12)
    score += min(len(unique_domains), 8) * 2
    score += min(max(len(unique_engines) - 1, 0), 3) * 4
    if google_confirm:
        score += 10
    score -= contradicting * 12
    if any(s["agrees"] is False and s["reliability"] == "high" for s in scoring_sources):
        score -= 8
    if not scoring_sources:
        score = 10
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
    confirming = sum(1 for s in scoring_sources if s["agrees"] is True)
    neutral = sum(1 for s in scoring_sources if s["agrees"] is None)
    summary_parts = [
        f"Tìm thấy {len(scoring_sources)} nguồn liên quan.",
        f"{confirming} nguồn xác nhận, {contradicting} nguồn phản bác, {neutral} trung lập.",
    ]
    if scoring_sources:
        summary_parts.append(f"Cross-check: {len(unique_domains)} domain, {len(unique_engines)} engine.")
    if confirming_high > 0:
        summary_parts.append(f"{confirming_high} nguồn uy tín (Reuters, BBC, AP...) xác nhận.")
    if contradicting > 0:
        summary_parts.append(f"Có {contradicting} nguồn phản bác - cần thận trọng.")
    if len(scoring_sources) == 0:
        summary_parts.append("Không tìm thấy nguồn tin nào liên quan trên web.")

    return {
        "score": score,
        "verdict": verdict,
        "sources": scoring_sources[:15],
        "summary": " ".join(summary_parts),
        "key_claims": claims,
    }


def main():
    global REDIS_URL, REDIS_TOKEN
    print("=" * 50)
    print("  Fact-Check Worker")
    print(f"  Redis: {'configured' if REDIS_URL else 'NOT configured - waiting...'}")
    print("=" * 50)

    if not REDIS_URL:
        print("[WARN] UPSTASH_REDIS_REST_URL not found.")
        print("[WARN] Create .env file in project root with:")
        print("  UPSTASH_REDIS_REST_URL=https://xxx.upstash.io")
        print("  UPSTASH_REDIS_REST_TOKEN=AXxx...")
        print("[WARN] Retrying in 10s... (or set env vars and restart)")
        while not REDIS_URL:
            time.sleep(10)
            # Re-check env vars (user might set them while script runs)
            REDIS_URL = os.environ.get("UPSTASH_REDIS_REST_URL", "")
            REDIS_TOKEN = os.environ.get("UPSTASH_REDIS_REST_TOKEN", "")
            if REDIS_URL:
                print("[OK] Redis configured! Starting...")
                break
            print(".", end="", flush=True)

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
    try:
        main()
    except KeyboardInterrupt:
        print("\nStopped.")
    except Exception as e:
        print(f"\nFATAL ERROR: {e}")
        import traceback
        traceback.print_exc()
    finally:
        input("\nPress Enter to exit...")
