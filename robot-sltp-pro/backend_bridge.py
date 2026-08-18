import json
import os
import re
import shlex
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

APP_ROOT = Path(__file__).resolve().parents[0]
BACKEND_ROOT = APP_ROOT.parent
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

PROFILE_CREATE_DEFAULTS = {
    "name": "",
    "path": "",
    "server": "",
    "sl": "500",
    "tp": "10000",
    "autoBeR": "2",
    "partialR": "2",
    "partialPct": "50",
    "teleChat": "",
}


def load_profiles():
    return json.loads((BACKEND_ROOT / "profiles.json").read_text(encoding="utf-8"))


def _load_global_config():
    path = BACKEND_ROOT / "config.json"
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, json.JSONDecodeError) as error:
        raise RuntimeError(f"Cannot read config.json: {type(error).__name__}") from error
    if not isinstance(data, dict):
        raise RuntimeError("config.json must contain a JSON object")
    return data


def _lock_pid(path):
    lock_path = Path(path)
    if not lock_path.exists():
        return 0
    try:
        return int((lock_path.read_text(encoding="utf-8") or "0").strip() or "0")
    except (OSError, TypeError, ValueError) as error:
        raise RuntimeError(f"Invalid runtime lock file: {lock_path.name}") from error


def _process_commandlines(pids):
    valid_pids = sorted({int(pid) for pid in pids if int(pid or 0) > 0})
    if os.name != "nt" or not valid_pids:
        return {}, None
    process_filter = " OR ".join(f"ProcessId = {pid}" for pid in valid_pids)
    script = (
        f"$rows = Get-CimInstance Win32_Process -Filter '{process_filter}' | "
        "Select-Object ProcessId,CommandLine; @($rows) | ConvertTo-Json -Compress"
    )
    try:
        result = subprocess.run(
            ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", script],
            capture_output=True,
            text=True,
            timeout=5,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
    except (OSError, subprocess.SubprocessError) as error:
        return {}, f"Process inspection unavailable: {type(error).__name__}"
    if result.returncode != 0:
        return {}, f"Process inspection failed with exit code {result.returncode}"
    raw = (result.stdout or "").strip()
    if not raw:
        return {}, None
    try:
        decoded = json.loads(raw)
    except json.JSONDecodeError:
        return {}, "Process inspection returned invalid JSON"
    rows = decoded if isinstance(decoded, list) else [decoded]
    commands = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        try:
            pid = int(row.get("ProcessId") or 0)
        except (TypeError, ValueError):
            continue
        command_line = str(row.get("CommandLine") or "").strip()
        if pid > 0 and command_line:
            commands[pid] = command_line
    return commands, None


def _cmdline_profile_exact(command_line, profile):
    if not command_line or not profile:
        return False
    try:
        parts = shlex.split(command_line, posix=False)
    except ValueError:
        parts = command_line.replace('"', "").split()
    target = str(profile)
    for index, part in enumerate(parts):
        token = part.strip().strip('"').strip("'")
        if token == "--profile":
            if index + 1 >= len(parts):
                return False
            value = parts[index + 1].strip().strip('"').strip("'")
            return value == target
        if token.startswith("--profile="):
            value = token.split("=", 1)[1].strip().strip('"').strip("'")
            return value == target
    return False


def _runtime_health(profile):
    safe_name = re.sub(r"[^\w\-]", "_", profile or "unknown")
    telegram_pid = _lock_pid(BACKEND_ROOT / "oak_enginecore.lock")
    legacy_pid = _lock_pid(BACKEND_ROOT / "mimo_bot.lock")
    worker_pid = _lock_pid(BACKEND_ROOT / f"worker_{safe_name}.lock")
    commands, inspection_issue = _process_commandlines([telegram_pid, legacy_pid, worker_pid])

    telegram_cmd = commands.get(telegram_pid, "")
    telegram_running = bool(telegram_pid and "oak_enginecore.py" in telegram_cmd)
    if not telegram_running:
        # Migration guard: an already-running pre-rename receiver must remain
        # authoritative until it exits, otherwise two Telegram pollers can race.
        legacy_cmd = commands.get(legacy_pid, "")
        if legacy_pid and "mimo_bot.py" in legacy_cmd:
            telegram_pid = legacy_pid
            telegram_running = True

    worker_cmd = commands.get(worker_pid, "")
    worker_running = bool(
        worker_pid
        and worker_cmd
        and "--worker" in worker_cmd
        and _cmdline_profile_exact(worker_cmd, profile)
    )

    global_cfg = _load_global_config()
    telegram_configured = bool(global_cfg.get("telegram_token") and global_cfg.get("telegram_chat_id"))
    return {
        "profile": profile,
        "telegram": {"configured": telegram_configured, "running": telegram_running, "pid": telegram_pid if telegram_running else 0},
        "worker": {"running": worker_running, "pid": worker_pid if worker_running else 0},
        "remoteReady": bool(telegram_configured and telegram_running and worker_running),
        "issues": [inspection_issue] if inspection_issue else [],
    }


def _spawn_detached(args):
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONUNBUFFERED"] = "1"
    kwargs = {
        "cwd": str(BACKEND_ROOT),
        "stdin": subprocess.DEVNULL,
        "stdout": subprocess.DEVNULL,
        "stderr": subprocess.DEVNULL,
        "env": env,
        "close_fds": True,
    }
    if os.name == "nt":
        kwargs["creationflags"] = (
            getattr(subprocess, "DETACHED_PROCESS", 0x00000008)
            | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0x00000200)
        )
    return subprocess.Popen(args, **kwargs)


def cmd_runtime_health(payload):
    profile = str(payload.get("profile") or "").strip()
    if profile not in load_profiles():
        raise RuntimeError(f"Unknown profile: {profile}")
    return _runtime_health(profile)


def cmd_runtime_ensure(payload):
    profile = str(payload.get("profile") or "").strip()
    profiles = load_profiles()
    if profile not in profiles:
        raise RuntimeError(f"Unknown profile: {profile}")

    before = _runtime_health(profile)
    requested = []
    issues = list(before.get("issues") or [])
    if before["telegram"]["configured"] and not before["telegram"]["running"]:
        _spawn_detached([sys.executable, str(BACKEND_ROOT / "oak_enginecore.py")])
        requested.append("telegram")
    elif not before["telegram"]["configured"]:
        issues.append("Telegram token/chat is not configured in config.json")

    if not before["worker"]["running"]:
        _spawn_detached([
            sys.executable,
            str(BACKEND_ROOT / "worker_runtime.py"),
            "--worker",
            "--profile",
            profile,
        ])
        requested.append("worker")

    health = before
    for _ in range(20):
        if health["worker"]["running"] and (health["telegram"]["running"] or not health["telegram"]["configured"]):
            break
        time.sleep(0.1)
        health = _runtime_health(profile)
    started = []
    if "telegram" in requested:
        if health["telegram"]["running"]:
            started.append("telegram")
        else:
            issues.append("Telegram receiver failed to start")
    if "worker" in requested:
        if health["worker"]["running"]:
            started.append("worker")
        else:
            issues.append(f"Profile worker failed to start: {profile}")
    health["started"] = started
    health["issues"] = list(dict.fromkeys([*(health.get("issues") or []), *issues]))
    return health


def safe_profile(name, cfg):
    return {
        "name": name,
        "server": str(cfg.get("server") or cfg.get("broker") or ""),
        "pathConfigured": bool(cfg.get("path")),
        "telegramConfigured": bool(cfg.get("tele_chat")),
        "autoBeR": float(cfg.get("auto_be") or 0),
        "partialR": str(cfg.get("partial_r") or ""),
        "visibleSltp": bool(cfg.get("visible_sltp", False)),
        "slPoints": float(cfg.get("sl") or 0),
        "tpPoints": float(cfg.get("tp") or 0),
        "copyRole": str(cfg.get("copy_role") or "none"),
    }


def cmd_profiles(_payload):
    raw = load_profiles()
    profiles = []
    seen = set()
    for name, cfg in raw.items():
        profile = safe_profile(name, cfg)
        key = profile["name"].strip().casefold()
        if not key or key in seen:
            continue
        seen.add(key)
        profiles.append(profile)
    return {"profiles": profiles, "profileDefaults": dict(PROFILE_CREATE_DEFAULTS)}


def cmd_profile_add(payload):
    name = str(payload.get("name") or "").strip()
    path = str(payload.get("path") or "").strip()
    server = str(payload.get("server") or "").strip()
    if not name:
        raise RuntimeError("Profile name is required")
    if not path:
        raise RuntimeError("MT5 terminal path is required")
    raw = load_profiles()
    if any(str(existing).strip().casefold() == name.casefold() for existing in raw):
        raise RuntimeError(f"Profile already exists: {name}")
    raw[name] = {
        "use_balance_sltp": False,
        "visible_sltp": True,
        "path": path,
        "mt5_portable": False,
        "magic": "0",
        "symbol": "",
        "sl": str(payload.get("sl") or PROFILE_CREATE_DEFAULTS["sl"]),
        "tp": str(payload.get("tp") or PROFILE_CREATE_DEFAULTS["tp"]),
        "gold_sl": "1000",
        "gold_tp": "20000",
        "balance_sl_pct": "",
        "balance_tp_pct": "",
        "partial_r": str(payload.get("partialR") or PROFILE_CREATE_DEFAULTS["partialR"]),
        "partial_pct": str(payload.get("partialPct") or PROFILE_CREATE_DEFAULTS["partialPct"]),
        "auto_be": str(payload.get("autoBeR") or PROFILE_CREATE_DEFAULTS["autoBeR"]),
        "tele_token": "__vault__",
        "tele_chat": str(payload.get("teleChat") or ""),
        "copy_role": "None",
        "profile_name": name,
    }
    if server:
        raw[name]["server"] = server
    (BACKEND_ROOT / "profiles.json").write_text(json.dumps(raw, indent=2, ensure_ascii=False), encoding="utf-8")
    return {"profile": safe_profile(name, raw[name]), "saved": True}


def serialize_position(pos):
    return {
        "ticket": int(getattr(pos, "ticket", 0) or 0),
        "symbol": str(getattr(pos, "symbol", "") or ""),
        "side": "BUY" if int(getattr(pos, "type", 0) or 0) == 0 else "SELL",
        "lots": float(getattr(pos, "volume", 0) or 0),
        "profit": float(getattr(pos, "profit", 0) or 0),
        "openPrice": float(getattr(pos, "price_open", 0) or 0),
        "currentPrice": float(getattr(pos, "price_current", 0) or 0),
        "sl": float(getattr(pos, "sl", 0) or 0),
        "tp": float(getattr(pos, "tp", 0) or 0),
    }


def cmd_snapshot(payload):
    from services.mt5_service import MT5Service

    name = str(payload.get("profile") or "")
    cfg = load_profiles().get(name)
    if not isinstance(cfg, dict):
        raise RuntimeError(f"Unknown profile: {name}")
    service = MT5Service(profile_config={**cfg, "profile_name": name})
    if not service.connect(allow_process_start=False):
        raise RuntimeError(f"MT5 terminal is not running or cannot be attached for profile {name}")
    try:
        account = service.account_info() or {}
        positions = service.positions_get()
        if positions is None:
            raise RuntimeError(f"MT5 positions_get failed for {name}: {service.last_error()}")
        return {
            "profile": safe_profile(name, cfg),
            "account": {
                "balance": float(account.get("balance", 0) or 0),
                "equity": float(account.get("equity", 0) or 0),
                "margin": float(account.get("margin", 0) or 0),
                "freeMargin": float(account.get("margin_free", 0) or 0),
                "profit": float(account.get("profit", 0) or 0),
                "server": str(account.get("server") or ""),
                "login": int(account.get("login", 0) or 0),
            },
            "positions": [serialize_position(p) for p in positions],
            "observedAt": datetime.now().isoformat(timespec="seconds"),
        }
    finally:
        service.disconnect()


def cmd_sltp_save(payload):
    profile = str(payload.get("profile") or "")
    raw = load_profiles()
    cfg = raw.get(profile)
    if not isinstance(cfg, dict):
        raise RuntimeError(f"Unknown profile: {profile}")
    auto_be = float(payload.get("beR") or 0)
    tp_r = float(payload.get("tpR") or 0)
    if auto_be < 0 or tp_r <= 0:
        raise RuntimeError("Invalid R:R values")
    cfg["auto_be"] = auto_be
    cfg["visible_sltp"] = bool(payload.get("enabled", True))
    sl_points = float(cfg.get("sl") or 0)
    if sl_points > 0:
        cfg["tp"] = round(sl_points * tp_r, 4)
    raw[profile] = cfg
    (BACKEND_ROOT / "profiles.json").write_text(json.dumps(raw, indent=2, ensure_ascii=False), encoding="utf-8")
    return {"profile": safe_profile(profile, cfg), "saved": True}


def cmd_telegram_send(payload):
    from domain.telegram_inbox import append_inbox_update

    profile = str(payload.get("profile") or "").strip()
    text = str(payload.get("text") or "").strip()
    if not text:
        raise RuntimeError("Telegram order is empty")
    profiles = load_profiles()
    cfg = profiles.get(profile)
    if not isinstance(cfg, dict):
        raise RuntimeError(f"Unknown profile: {profile}")

    first = text.split()[0].lower()
    if first in {"/buy", "/sell"}:
        text = text[1:]
    profile_names = {name.casefold() for name in profiles}
    tokens = text.split()
    scoped_text = text if tokens and tokens[-1].casefold() in profile_names else f"{text} {profile}"
    global_cfg = _load_global_config()
    sender_id = cfg.get("tele_admin") or global_cfg.get("telegram_chat_id") or cfg.get("tele_chat") or ""
    if not sender_id:
        raise RuntimeError("Telegram admin/chat is not configured")
    update = append_inbox_update(BACKEND_ROOT / "tele_inbox.json", scoped_text, sender_id, source="Tauri")
    return {"queued": True, "profile": profile, "text": scoped_text, "updateId": update["update_id"]}


def cmd_cloud_market_data_status(_payload):
    from ctrader_cloud_config import CTraderCloudConfig

    ic_status = CTraderCloudConfig.from_env().status()
    ic_status["controlPlaneConfigured"] = bool(
        os.environ.get("OAK_CTRADER_SESSION_URL") and os.environ.get("DASHBOARD_API_KEY")
    )
    return {
        "engineCore": "provider-v1",
        "productionSource": "mt5",
        "icMarkets": ic_status,
        "vantage": {
            "provider": "mt5-baseline",
            "configured": True,
            "cloudCandidate": "pending-official-api",
        },
        "parityRequired": True,
    }


def cmd_pattern5(payload):
    from pattern5_engine import render_profile_cached
    profile = str(payload.get("profile") or "")
    selected = payload.get("symbols")
    week_start = payload.get("weekStart")
    force = bool(payload.get("force", False))
    if selected is not None and not isinstance(selected, list):
        raise RuntimeError("symbols must be a list")
    return render_profile_cached(profile, selected=selected, week_start=week_start, force=force)


def cmd_pattern5_publish(payload):
    from publish_pattern5_site import publish_profile
    profile = str(payload.get("profile") or "")
    force = bool(payload.get("force", False))
    if not profile:
        raise RuntimeError("Pattern5 profile is required")
    return {"published": True, **publish_profile(profile, force=force)}


def cmd_schedule_netting(payload):
    from domain.copy_trade_manager import _scheduled_close_resolve_target

    profile = str(payload.get("profile") or "")
    time_text = str(payload.get("time") or "").strip()
    mode = str(payload.get("mode") or "all").strip().lower()
    symbol = str(payload.get("symbol") or "").strip().upper()
    if mode not in {"all", "symbol"}:
        raise RuntimeError("Invalid netting mode")
    if mode == "symbol" and not symbol:
        raise RuntimeError("Symbol is required for symbol netting")
    target = _scheduled_close_resolve_target(time_text)
    manager = _pending_manager(profile)
    task = manager._append_scheduled_close({
        "date": target.strftime("%Y-%m-%d"),
        "time": target.strftime("%H:%M:%S"),
        "filter": "all",
        "sym": symbol if mode == "symbol" else "",
        "ticket": "",
        "tz": "Asia/Ho_Chi_Minh",
        "status": "waiting",
        "attempts": 0,
    })
    return {"scheduled": True, "profile": profile, "task": task}


def _pending_manager(profile):
    from domain.copy_trade_manager import CopyTradeManager

    cfg = load_profiles().get(profile)
    if not isinstance(cfg, dict):
        raise RuntimeError(f"Unknown profile: {profile}")
    manager = CopyTradeManager({**cfg, "profile_name": profile}, lambda _msg: None)
    manager.scheduled_file = str(BACKEND_ROOT / Path(manager.scheduled_file).name)
    manager.scheduled_close_file = str(BACKEND_ROOT / Path(manager.scheduled_close_file).name)
    for attr, path in (("scheduled_trades", manager.scheduled_file), ("_scheduled_close", manager.scheduled_close_file)):
        state_path = Path(path)
        if not state_path.exists():
            data = []
        else:
            try:
                data = json.loads(state_path.read_text(encoding="utf-8"))
            except (OSError, ValueError, json.JSONDecodeError) as error:
                raise RuntimeError(f"Cannot read pending state: {state_path.name}") from error
            if not isinstance(data, list):
                raise RuntimeError(f"Pending state must be a JSON array: {state_path.name}")
        setattr(manager, attr, data)
    return manager


def cmd_pending_tasks(payload):
    profile = str(payload.get("profile") or "")
    manager = _pending_manager(profile)
    entries = manager._with_scheduled_file_lock(lambda rows: tuple(dict(row) for row in rows if isinstance(row, dict)))
    if entries is None:
        raise RuntimeError("Pending entry lock timed out")
    closes = manager._with_scheduled_close_file_lock(lambda rows: tuple(dict(row) for row in rows if isinstance(row, dict)))
    tasks = []
    terminal_statuses = {"done", "executed", "completed", "cancelled", "canceled", "failed", "error", "closed", "expired", "removed"}
    for row in entries:
        status = str(row.get("status") or "waiting").lower()
        if status in terminal_statuses:
            continue
        raw_type = row.get("type")
        side = str(raw_type).upper() if isinstance(raw_type, str) else ("BUY" if raw_type == 0 else "SELL")
        tasks.append({
            "id": int(row.get("id") or 0), "kind": "telegram", "status": status,
            "symbol": str(row.get("symbol") or ""), "side": side,
            "lot": float(row.get("lot") or 0), "date": str(row.get("date") or ""),
            "time": str(row.get("time") or ""), "scope": "Scheduled entry",
            "canDelete": status != "executing",
        })
    for row in closes:
        status = str(row.get("status") or "waiting").lower()
        if status in terminal_statuses:
            continue
        ticket = str(row.get("ticket") or "")
        symbol = str(row.get("sym") or "")
        scope = f"Ticket #{ticket}" if ticket else (symbol if symbol else "Đóng tất cả")
        tasks.append({
            "id": int(row.get("id") or 0), "kind": "netting", "status": status,
            "symbol": symbol, "date": str(row.get("date") or ""),
            "time": str(row.get("time") or ""), "scope": scope,
            "canDelete": status != "executing",
        })
    tasks.sort(key=lambda item: (item.get("date") or "", item.get("time") or "", item["kind"], item["id"]))
    return {"profile": profile, "tasks": tasks}


def cmd_pending_delete(payload):
    profile = str(payload.get("profile") or "")
    kind = str(payload.get("kind") or "").strip().lower()
    task_id = int(payload.get("id") or 0)
    if kind not in {"telegram", "netting"} or task_id <= 0:
        raise RuntimeError("Invalid pending task")
    manager = _pending_manager(profile)
    state = {"found": False, "blocked": False}

    def remove(rows):
        kept = []
        for row in rows:
            if not isinstance(row, dict) or int(row.get("id") or 0) != task_id:
                kept.append(row)
                continue
            state["found"] = True
            if str(row.get("status") or "waiting").lower() == "executing":
                state["blocked"] = True
                kept.append(row)
        return kept

    if kind == "telegram":
        result = manager._with_scheduled_file_lock(remove)
        if result is None:
            raise RuntimeError("Pending entry lock timed out")
    else:
        manager._with_scheduled_close_file_lock(remove)
    if state["blocked"]:
        raise RuntimeError(f"Task #{task_id} is executing and cannot be deleted safely")
    if not state["found"]:
        raise RuntimeError(f"Pending task #{task_id} not found")
    return {"deleted": True, "profile": profile, "kind": kind, "id": task_id}


COMMANDS = {
    "profiles": cmd_profiles,
    "profile_add": cmd_profile_add,
    "runtime_health": cmd_runtime_health,
    "runtime_ensure": cmd_runtime_ensure,
    "snapshot": cmd_snapshot,
    "sltp_save": cmd_sltp_save,
    "telegram_send": cmd_telegram_send,
    "schedule_netting": cmd_schedule_netting,
    "pending_tasks": cmd_pending_tasks,
    "pending_delete": cmd_pending_delete,
    "cloud_market_data_status": cmd_cloud_market_data_status,
    "pattern5": cmd_pattern5,
    "pattern5_publish": cmd_pattern5_publish,
}


def run_server():
    if hasattr(sys.stdin, "reconfigure"):
        sys.stdin.reconfigure(encoding="utf-8")
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    for line in sys.stdin:
        line = line.rstrip("\r\n")
        if not line:
            continue
        try:
            request_id, command, payload_text = line.split("\t", 2)
            payload = json.loads(payload_text) if payload_text else {}
            fn = COMMANDS.get(command)
            if fn is None:
                raise RuntimeError(f"unknown command: {command}")
            result = fn(payload)
            print(f"{request_id}\t{json.dumps(result, ensure_ascii=False)}", flush=True)
        except Exception as exc:
            print(f"{request_id}\t{json.dumps({'error': str(exc)}, ensure_ascii=False)}", flush=True)


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if len(sys.argv) < 2:
        raise SystemExit("missing command")
    command = sys.argv[1]
    payload = json.loads(sys.argv[2]) if len(sys.argv) > 2 else {}
    fn = COMMANDS.get(command)
    if fn is None:
        raise SystemExit(f"unknown command: {command}")
    print(json.dumps(fn(payload), ensure_ascii=False), flush=True)


if __name__ == "__main__":
    try:
        if len(sys.argv) > 1 and sys.argv[1] == "--server":
            run_server()
        else:
            main()
    except Exception as exc:
        print(json.dumps({"error": str(exc)}, ensure_ascii=False), flush=True)
        raise SystemExit(1)
