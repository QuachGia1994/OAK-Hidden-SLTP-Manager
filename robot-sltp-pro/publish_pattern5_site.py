import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import Request, urlopen

APP = Path(__file__).resolve().parent
ROOT = APP.parent
PROFILE = os.environ.get("ROBOT_PATTERN5_PROFILE", "VantageDemo")
KEY_PREFIX = "robot-sltp:public:pattern5:"

sys.path.insert(0, str(APP))
from pattern5_engine import render_profile_cached


def load_dotenv():
    env_path = ROOT / ".env"
    if not env_path.exists():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def publish_to_redis(feed, profile):
    load_dotenv()
    url = os.environ.get("UPSTASH_REDIS_REST_URL")
    token = os.environ.get("UPSTASH_REDIS_REST_TOKEN")
    if not url or not token:
        raise RuntimeError("UPSTASH_REDIS_REST_URL/TOKEN are required for public publishing")
    value = json.dumps(feed, ensure_ascii=False, separators=(",", ":"))
    for key in (KEY_PREFIX + profile, KEY_PREFIX + "latest"):
        payload = json.dumps(["SET", key, value]).encode()
        request = Request(url, data=payload, headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"}, method="POST")
        with urlopen(request, timeout=15) as response:
            result = json.loads(response.read().decode("utf-8"))
        if result.get("result") != "OK":
            raise RuntimeError(f"Upstash publish failed for {key}: {result}")


def publish_profile(profile, force=False):
    feed = {
        **render_profile_cached(profile, force=force),
        "publishedAt": datetime.now(timezone.utc).isoformat(),
    }
    publish_to_redis(feed, profile)
    print(f"Published Pattern5 feed: {profile} -> Upstash", file=sys.stderr)
    print(f"Week: {feed['weekStart']} | tables: {len(feed['tables'])}", file=sys.stderr)
    return feed


if __name__ == "__main__":
    publish_profile(PROFILE)
