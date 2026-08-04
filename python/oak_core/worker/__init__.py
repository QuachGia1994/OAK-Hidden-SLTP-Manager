# -*- coding: utf-8 -*-
"""Profile worker — one MT5 connection per profile (Phase 2, §2/§9).

Each worker:
- loads its profile config from profiles.json (repo root);
- launches/attaches the correct terminal via ensure_mt5_profile_connected;
- verifies the connected account login/server match the profile;
- keeps the connection alive (reports account info every poll interval).

No candle API, no signal engine — account audit only.
"""
import json
import sys
import time
from pathlib import Path

from ..version import APP_VERSION

#: Poll interval for the worker keep-alive loop (seconds).
POLL_INTERVAL_SECONDS = 5.0


def _repo_root() -> Path:
    here = Path(__file__).resolve()
    # python/oak_core/worker/__init__.py -> repo root = 4 parents up
    return here.parents[3]


def _load_profile(profile_name: str) -> dict:
    try:
        data = json.loads((_repo_root() / "profiles.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return data.get(profile_name, {}) if isinstance(data, dict) else {}


def _account_matches(account, profile: dict) -> bool:
    """Account login/server must match the profile (best-effort, non-fatal)."""
    if account is None:
        return False
    login = getattr(account, "login", None)
    expected_login = profile.get("login_id") or profile.get("login")
    if expected_login is not None and login is not None and int(login) != int(expected_login):
        return False
    server = getattr(account, "server", "")
    expected_server = profile.get("server", "")
    if expected_server and server and expected_server.lower() not in server.lower():
        return False
    return True


def run_profile_worker(profile_name: str, *, once: bool = False) -> int:
    """Connect MT5 for one profile, verify the account, keep alive."""
    print(f"[worker:{profile_name}] oak-core v{APP_VERSION} starting", file=sys.stderr)

    profile = _load_profile(profile_name)
    if not profile:
        print(f"[worker:{profile_name}] profile not found in profiles.json", file=sys.stderr)
        return 3

    terminal_path = profile.get("path", "")
    if not terminal_path or not Path(terminal_path).is_file():
        print(f"[worker:{profile_name}] terminal path missing/invalid: {terminal_path!r}", file=sys.stderr)
        return 4

    try:
        import MetaTrader5 as mt5
        from services.mt5_terminal_service import ensure_mt5_profile_connected
    except ImportError as exc:
        print(f"[worker:{profile_name}] import failed: {exc}", file=sys.stderr)
        return 5

    # Import path: the worker runs from repo root context, so services/ is
    # importable when the sidecar is bundled; in dev we add the repo root.
    root = str(_repo_root())
    if root not in sys.path:
        sys.path.insert(0, root)

    result = ensure_mt5_profile_connected(profile, mt5_module=mt5, timeout_seconds=15)
    if not result.ok:
        print(f"[worker:{profile_name}] MT5 connect failed: {result.failure_code} {result.message}",
              file=sys.stderr)
        return 6

    account = mt5.account_info()
    if account is None:
        print(f"[worker:{profile_name}] connected but account_info unavailable", file=sys.stderr)
        return 7
    if not _account_matches(account, profile):
        print(f"[worker:{profile_name}] WARNING account login/server does not match profile", file=sys.stderr)

    print(f"[worker:{profile_name}] CONNECTED login={account.login} server={account.server} "
          f"balance={account.balance:.2f} {account.currency}", file=sys.stderr)

    if once:
        mt5.shutdown()
        print(f"[worker:{profile_name}] --once: verified, exiting", file=sys.stderr)
        return 0

    # Keep-alive loop — later phases attach SL/TP monitoring + deal reconciler.
    try:
        while True:
            time.sleep(POLL_INTERVAL_SECONDS)
            if mt5.terminal_info() is None:
                print(f"[worker:{profile_name}] terminal disconnected, reconnecting", file=sys.stderr)
                ensure_mt5_profile_connected(profile, mt5_module=mt5, timeout_seconds=15)
    except KeyboardInterrupt:
        print(f"[worker:{profile_name}] stopped by user", file=sys.stderr)
    finally:
        try:
            mt5.shutdown()
        except Exception:
            pass
    return 0
