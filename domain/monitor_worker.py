# -*- coding: utf-8 -*-
"""MonitorWorker — per-profile MT5 monitor thread."""
from __future__ import annotations

import json
import os
import re
import time
import threading
import subprocess
import winsound
import urllib.error
import urllib.request
from datetime import datetime, timedelta

import MetaTrader5 as mt5

from oak_logger import setup_logger
from domain.telegram_backoff import compute_telegram_backoff

from domain.constants import SETTINGS_FILE, _oak_enginecore_token, _oak_enginecore_chat_id
from domain.json_io import load_json, save_json
from domain import i18n as _i18n
from domain.i18n import T, LANG
from domain.mt5_orders import get_filling_type, send_mutation_idempotent
from domain.ticket_manager import TicketManager
from domain.copy_trade_manager import CopyTradeManager
from domain.balance import get_start_day_balance
from domain.file_lock import FileLock
from domain.xau_h1_pattern_scanner import MultiSymbolH1PatternScanner
from services.mt5_terminal_service import (
    bind_live_mt5_account_identity,
    ensure_mt5_profile_connected,
)

log = setup_logger("monitor_worker")

class MonitorWorker(threading.Thread):
    def __init__(self, config, log_callback, stop_event):
        super().__init__()
        self.config = config
        self.log = log_callback
        self.stop_event = stop_event
        self.daemon = True
        self._be_retry_state = {}
        self.launch_failed = False

        # Telegram backoff/circuit breaker state.
        self._telegram_fail_count = 0
        self._telegram_backoff_until = 0.0
        self._telegram_degraded_logged = False
        self.h1_pattern_scanner = None

    def _clear_be_retry_state_for_tickets(self, tickets):
        """Forget retry state once a monitored position is no longer open."""
        if not tickets:
            return
        profile = str(self.config.get("profile_name", "") or "default")
        for retry_key in list(self._be_retry_state):
            if (
                isinstance(retry_key, tuple)
                and len(retry_key) >= 2
                and retry_key[0] == profile
                and retry_key[1] in tickets
            ):
                self._be_retry_state.pop(retry_key, None)

    def notify(self, message, telegram=True):
        """Unified logging and telegram notification."""
        self.log(message)
        if telegram:
            self.send_telegram(message)

    def send_telegram(self, message):
        from secret_store import resolve_telegram_token
        profile_name = self.config.get("profile_name", "")
        token = resolve_telegram_token(profile_name, self.config.get("tele_token", ""), global_fallback=_oak_enginecore_token)
        chat_id = str(_oak_enginecore_chat_id) if _oak_enginecore_chat_id else self.config.get("tele_chat", "")
        if not token or not chat_id:
            return False

        if time.time() < self._telegram_backoff_until:
            # Still cooling down from recent repeated failures; skip silently
            # so a Telegram outage doesn't spam the log every call.
            return False

        # Strip color tags for Telegram (they don't support custom HTML tags like <c=...>)
        clean_message = re.sub(r"<c=#[A-Fa-f0-9]{6}>", "", message)
        clean_message = clean_message.replace("</c>", "")
        
        try:
            log_file = "tele_sent_log.json"
            lock_file = "tele_sent_log.lock"
            lock_fd = None
            try:
                start_ts = time.time()
                while True:
                    try:
                        lock_fd = os.open(lock_file, os.O_CREAT | os.O_EXCL | os.O_RDWR)
                        break
                    except FileExistsError:
                        if time.time() - start_ts > 2:
                            break
                        time.sleep(0.05)
                    except Exception as e:
                        log.warning("Telegram dedup lock error: %s", e)
                        break

                sent_log = []
                if lock_fd:
                    try:
                        if os.path.exists(log_file):
                            with open(log_file, "r", encoding="utf-8") as f:
                                sent_log = json.load(f)
                    except Exception as e:
                        log.warning("Telegram dedup log read error: %s", e)
                        sent_log = []

                    now_ts = time.time()
                    cutoff = now_ts - 10
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
                        return False
                else:
                    filtered = []
                    now_ts = time.time()
            finally:
                if lock_fd:
                    os.close(lock_fd)
                    try:
                        os.remove(lock_file)
                    except:
                        pass

            url = f"https://api.telegram.org/bot{token}/sendMessage"
            data = {"chat_id": chat_id, "text": clean_message}
            encoded_data = urllib.parse.urlencode(data).encode('utf-8')
            req = urllib.request.Request(url, data=encoded_data)
            with urllib.request.urlopen(req, timeout=10) as response:
                response.read()

            self._telegram_fail_count = 0
            self._telegram_backoff_until = 0.0
            self._telegram_degraded_logged = False

            if filtered is not None:
                filtered.append({"msg": clean_message, "ts": now_ts})
                try:
                    lock_fd = os.open(lock_file, os.O_CREAT | os.O_EXCL | os.O_RDWR)
                except Exception:
                    lock_fd = None
                try:
                    if lock_fd:
                        with open(log_file, "w", encoding="utf-8") as f:
                            json.dump(filtered[-500:], f)
                except Exception as e:
                    log.warning("Telegram dedup log write error: %s", e)
                finally:
                    if lock_fd:
                        os.close(lock_fd)
                        try:
                            os.remove(lock_file)
                        except:
                            pass
            return True
        except Exception as e:
            self._telegram_fail_count += 1
            count = self._telegram_fail_count
            sleep_s, is_new_degraded = compute_telegram_backoff(count)
            self._telegram_backoff_until = time.time() + sleep_s
            if is_new_degraded:
                self.log(f"⚠️ Telegram degraded: {count}+ lỗi liên tiếp, tạm nghỉ {sleep_s}s, ngừng spam log.")
                self._telegram_degraded_logged = True
            elif count >= 10:
                pass  # already in degraded/backoff state, stay quiet
            elif count >= 3:
                self.log(f"Telegram Error: {e} (lỗi liên tiếp #{count}, nghỉ {sleep_s}s)")
            else:
                self.log(f"Telegram Error: {e} (retry sau {sleep_s}s)")
            return False

    def close_position(self, pos, reason, volume=None):
        tick = mt5.symbol_info_tick(pos.symbol)
        if not tick: return
        
        req = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": pos.symbol,
            "volume": volume if volume else pos.volume,
            "type": mt5.ORDER_TYPE_SELL if pos.type == mt5.POSITION_TYPE_BUY else mt5.ORDER_TYPE_BUY,
            "position": pos.ticket,
            "price": tick.bid if pos.type == mt5.POSITION_TYPE_BUY else tick.ask,
            "deviation": 20,
            "magic": pos.magic,
            "comment": "OAK_SLTP " + reason,
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": get_filling_type(pos.symbol),
        }
        
        exec_mode = "[API]"

        def reconcile_close():
            rows = mt5.positions_get(ticket=pos.ticket) or []
            if not rows:
                return pos.ticket
            if volume is not None and float(getattr(rows[0], "volume", 0)) < float(pos.volume) - 1e-9:
                return pos.ticket
            return None

        result = send_mutation_idempotent(
            req,
            f"monitor-close:{self.config.get('profile_name', 'Unknown')}:{pos.ticket}:{reason}:{volume or pos.volume}",
            mt5_module=mt5,
            reconcile=reconcile_close,
            profile_config=self.config,
        )
        
        msg = ""
        if result["status"] in ("DONE", "EXISTING"):
            msg = f"✅ {exec_mode} {T('log_closed')} {pos.ticket} | {pos.symbol} | Vol: {volume if volume else pos.volume} | {reason}"
            self.notify(msg)
            winsound.Beep(1000, 200)
        else:
            error_text = result.get("error", result["status"])
            msg = f"❌ {exec_mode} {T('log_fail')} {pos.ticket} | {pos.symbol} | {error_text}"
            self.notify(msg)
            for _ in range(3): winsound.Beep(2000, 200); time.sleep(0.1)
        
    def move_sl_to_entry(self, pos):
        """Move SL to entry once, with retcode-aware retry/backoff."""
        if not bool(self.config.get("visible_sltp", False)):
            return True
        profile = str(self.config.get("profile_name", "default"))
        key = (profile, int(getattr(pos, "ticket", 0)), "MOVE_BE")
        state = self._be_retry_state.setdefault(key, {
            "attempt_count": 0, "last_retcode": None, "last_attempt_at": 0.0,
            "next_retry_at": 0.0, "last_logged_at": 0.0, "last_target_sl": None,
            "last_position_update_time": None,
        })
        state["last_position_update_time"] = getattr(
            pos, "time_update_msc", getattr(pos, "time_update", None)
        )
        now = time.time()
        current_sl = float(getattr(pos, "sl", 0.0) or 0.0)
        entry_price = float(getattr(pos, "price_open", 0.0) or 0.0)
        if entry_price <= 0:
            return False
        is_buy = int(getattr(pos, "type", -1)) == getattr(mt5, "POSITION_TYPE_BUY", 0)
        should_move = current_sl == 0.0 or (is_buy and current_sl < entry_price) or (not is_buy and current_sl > entry_price)
        if not should_move:
            self._be_retry_state.pop(key, None)
            return True
        if now < float(state.get("next_retry_at", 0.0) or 0.0):
            return False
        target_sl, invalid_reason = self._normalize_be_target(pos, entry_price)
        if target_sl is None:
            signature = (invalid_reason, round(entry_price, 10), getattr(pos, "price_current", None))
            if state.get("invalid_signature") != signature:
                state["invalid_signature"] = signature
                self._be_log_once(state, f"[BE] {pos.ticket} hoãn SL: {invalid_reason}")
            state["next_retry_at"] = now + 30.0
            return False
        if state.get("last_target_sl") != target_sl:
            state["attempt_count"] = 0
            state["last_target_sl"] = target_sl
            state["next_retry_at"] = 0.0
        state["last_attempt_at"] = now
        state["attempt_count"] = int(state.get("attempt_count", 0)) + 1
        req = {"action": mt5.TRADE_ACTION_SLTP, "position": pos.ticket, "symbol": pos.symbol,
               "sl": target_sl, "tp": getattr(pos, "tp", 0.0)}
        def reconcile_be():
            refreshed = mt5.positions_get(ticket=pos.ticket) or []
            if not refreshed:
                return None
            current = refreshed[0]
            if abs(float(getattr(current, "sl", 0.0) or 0.0) - target_sl) <= max(1e-8, abs(target_sl) * 1e-7):
                return pos.ticket
            return None

        result = send_mutation_idempotent(
            req,
            f"move-be:{profile}:{pos.ticket}:{target_sl}",
            mt5_module=mt5,
            reconcile=reconcile_be,
            profile_config=self.config,
        )
        response = result.get("response")
        retcode = int(getattr(response, "retcode", -1)) if response is not None else -1
        state["last_retcode"] = retcode
        if result["status"] in ("DONE", "EXISTING"):
            self._be_retry_state.pop(key, None)
            self.notify(f"{T('log_move_be_ok')} {pos.ticket} | {pos.symbol} -> {target_sl}")
            return True
        if retcode == 10025:
            refreshed = mt5.positions_get(ticket=pos.ticket)
            if refreshed and abs(float(getattr(refreshed[0], "sl", 0.0) or 0.0) - target_sl) <= max(1e-8, abs(target_sl) * 1e-7):
                self._be_retry_state.pop(key, None)
                return True
            state["next_retry_at"] = now + 60.0
            self._be_log_once(state, f"[BE] {pos.ticket} NO_CHANGES; đang xác minh SL")
            return False
        if retcode == 10018:
            state["next_retry_at"] = now + 900.0
            self._be_log_once(state, f"[BE] {pos.ticket} hoãn SL: thị trường đóng cửa.")
            return False
        if retcode == 10024:
            state["next_retry_at"] = now + min(900.0, 15.0 * (2 ** min(state["attempt_count"], 6)))
            self._be_log_once(state, f"[BE] {pos.ticket} bị giới hạn request; sẽ retry có backoff.")
            return False
        if retcode == 10016:
            state["next_retry_at"] = now + 30.0
            self._be_log_once(state, f"[BE] {pos.ticket} hoãn SL: khoảng cách stop chưa hợp lệ.")
            return False
        if retcode == 10027:
            state["next_retry_at"] = now + 300.0
            self._be_log_once(state, f"[BE] {pos.ticket} chờ bật Algo Trading.")
            return False
        if retcode == 10031:
            state["next_retry_at"] = now + 30.0
            self._be_log_once(state, f"[BE] {pos.ticket} chờ MT5 reconnect.")
            return False
        if result["status"] == "UNKNOWN":
            state["next_retry_at"] = now + min(300.0, 30.0 * (2 ** min(state["attempt_count"], 4)))
            self._be_log_once(state, f"[BE] {pos.ticket} UNKNOWN; broker state requires reconciliation before retry")
            return False
        state["next_retry_at"] = now + min(300.0, 15.0 * (2 ** min(state["attempt_count"], 4)))
        self._be_log_once(state, f"[BE] {pos.ticket} deferred; Err {retcode}")
        return False

    def _be_log_once(self, state, message):
        now = time.time()
        if now - float(state.get("last_logged_at", 0.0) or 0.0) >= 60.0:
            self.log(message)
            state["last_logged_at"] = now

    def _normalize_be_target(self, pos, entry_price):
        try:
            info = mt5.symbol_info(pos.symbol)
            tick = mt5.symbol_info_tick(pos.symbol)
            if info is None or tick is None:
                return None, "thiếu symbol/tick"
            digits = int(getattr(info, "digits", 5) or 5)
            tick_size = float(getattr(info, "trade_tick_size", 0.0) or getattr(info, "point", 0.0) or 0.0)
            if tick_size <= 0:
                return None, "thiếu tick size"
            target = round(round(entry_price / tick_size) * tick_size, digits)
            min_distance = max(float(getattr(info, "trade_stops_level", 0) or 0), float(getattr(info, "trade_freeze_level", 0) or 0)) * float(getattr(info, "point", tick_size) or tick_size)
            is_buy = int(getattr(pos, "type", -1)) == getattr(mt5, "POSITION_TYPE_BUY", 0)
            market_price = float(getattr(tick, "bid" if is_buy else "ask", 0.0) or 0.0)
            if market_price <= 0:
                return None, "thiếu giá thị trường"
            if is_buy and target > market_price - min_distance:
                return None, "stop buy vượt stops/freeze level"
            if not is_buy and target < market_price + min_distance:
                return None, "stop sell vượt stops/freeze level"
            return target, None
        except Exception as error:
            return None, f"không đọc được constraint ({error})"

    def run(self):
        try:
            self.log("Worker thread started...") # Debug log
            
            # Helper for safe conversion
            def safe_int(val, default=0):
                try:
                    if not val: return default
                    return int(float(val))
                except:
                    return default

            def safe_float(val, default=0.0):
                try:
                    if not val: return default
                    return float(val)
                except:
                    return default

            # Init Ticket Manager (per-profile file — multi-process safe)
            self.ticket_manager = TicketManager(
                profile_name=self.config.get("profile_name")
            )
            
            # Init Copy Manager
            self.copy_manager = CopyTradeManager(self.config, self.notify)
            
            path = self.config.get("path", "")
            magic = safe_int(self.config.get("magic"), 0)
            symbol_str = self.config.get("symbol", "")
            sl = safe_int(self.config.get("sl"), 0)
            tp = safe_int(self.config.get("tp"), 0)
            gold_sl = safe_int(self.config.get("gold_sl"), 1000)
            gold_tp = safe_int(self.config.get("gold_tp"), 20000)
            
            # Balance SL/TP Config
            use_balance_sltp = bool(self.config.get("use_balance_sltp", False))
            visible_sltp = bool(self.config.get("visible_sltp", False))
            balance_sl_pct = safe_float(self.config.get("balance_sl_pct"), 0.0)
            balance_tp_pct = safe_float(self.config.get("balance_tp_pct"), 0.0)

            # Partial Close & BE Config
            partial_r_str = self.config.get("partial_r", "")
            
            # Parse Partial PCT (Single Value or List)
            partial_pct_list = []
            try:
                p_pct_raw = str(self.config.get("partial_pct", "50.0")).strip()
                if "," in p_pct_raw:
                    partial_pct_list = [float(x.strip()) for x in p_pct_raw.split(",") if x.strip()]
                else:
                    val = float(p_pct_raw) if p_pct_raw else 0.0
                    if val > 0:
                        partial_pct_list = [val]
            except:
                partial_pct_list = []
                
            try:
                be_str = str(self.config.get("auto_be", "0.0")).strip()
                auto_be_r = float(be_str) if be_str else 0.0
            except:
                auto_be_r = 0.0
            
            partial_r_levels = []
            if partial_r_str:
                try:
                    partial_r_levels = sorted([float(x.strip()) for x in partial_r_str.split(",") if x.strip()])
                except:
                    self.log(T("err_parse_r"))

            # Parse monitored symbols
            monitored_symbols = []
            if symbol_str:
                monitored_symbols = [s.strip().upper() for s in symbol_str.split(",") if s.strip()]

            # Attach only to a terminal the user has already opened. Selecting
            # a profile or keeping the worker alive must never launch MT5.
            # Stay resident while the terminal is closed so a later manual
            # open can be attached without restarting the OAK runtime.
            profile_name = self.config.get("profile_name", "") or "default"
            launch = ensure_mt5_profile_connected(
                self.config,
                mt5_module=mt5,
                timeout_seconds=5,
                allow_process_start=False,
            )
            waiting_logged = False
            fatal_launch_codes = {
                "TERMINAL_PATH_NOT_FOUND",
                "TERMINAL_PATH_MISMATCH",
                "ACCOUNT_MISMATCH",
            }
            while not launch.ok and not self.stop_event.is_set():
                if launch.failure_code in fatal_launch_codes:
                    self.launch_failed = True
                    failure = f"{launch.failure_code or 'IPC_FAILED'}: {launch.message}"
                    self.notify(
                        f"[MT5-ATTACH] Profile={profile_name} "
                        f"status={launch.failure_code or 'IPC_FAILED'} path={launch.terminal_path} "
                        f"message={failure}"
                    )
                    return
                if not waiting_logged:
                    self.log(
                        f"[MT5-ATTACH] Profile={profile_name} waiting for manual terminal open"
                    )
                    waiting_logged = True
                self.stop_event.wait(2.0)
                if self.stop_event.is_set():
                    return
                launch = ensure_mt5_profile_connected(
                    self.config,
                    mt5_module=mt5,
                    timeout_seconds=5,
                    allow_process_start=False,
                )
            self.log(
                f"[MT5-LAUNCH] Profile={self.config.get('profile_name', 'unknown')} "
                f"CONNECTED path={launch.terminal_path} attempts={launch.initialize_attempts}"
            )

            # Check Info
            account = mt5.account_info()
            terminal = mt5.terminal_info()
            
            connect_msg = ""
            algo_msg = ""
            
            if account:
                # Bind live login/server into the in-memory profile so
                # send_mutation_idempotent / validate_mt5_mutation_session
                # receive the same identity this worker just connected to.
                # Does not invent values and does not overwrite configured ones.
                bind_live_mt5_account_identity(self.config, account)
                connect_msg = f"{T('log_connected')} {account.name} ({account.login}) | Broker: {account.company}"
                self.log(connect_msg)
                
                algo_msg = f"{T('log_algo_on') if terminal.trade_allowed else T('log_algo_off')}"
                self.log(algo_msg)
                
                if not terminal.trade_allowed:
                    self.notify(T("err_algo"))
                    winsound.Beep(2000, 1000)

            start_msg = T("log_monitor_start")
            self.log(start_msg)

            # Log Configuration details as requested
            from secret_store import resolve_telegram_token
            tele_token_resolved = resolve_telegram_token(
                self.config.get("profile_name", ""),
                self.config.get("tele_token", ""),
                global_fallback=_oak_enginecore_token
            )
            tele_status = "ON" if (tele_token_resolved and self.config.get("tele_chat", "")) else "OFF"
            config_log = (
                f"{T('log_config_title')}\n"
                f"{T('log_config_symbol')}   {symbol_str if symbol_str else 'ALL'}\n"
                f"{T('log_config_magic')}    {magic}\n"
                f"{T('log_config_sltp')}    {sl}/{tp} points\n"
                f"{T('log_config_gold')} {gold_sl}/{gold_tp} points\n"
                f"{T('log_config_visible')} {'ON' if visible_sltp else 'OFF'}\n"
                f"{T('log_config_bal')} {'ON' if use_balance_sltp else 'OFF'} (SL: {balance_sl_pct}%, TP: {balance_tp_pct}%)\n"
                f"{T('log_config_partial')} {partial_r_levels} R (Vol: {partial_pct_list}%)\n"
                f"{T('log_config_be')} {auto_be_r if auto_be_r > 0 else 'OFF'} R\n"
                f"{T('log_config_tele')} {tele_status}\n"
            )

            # Append Copy Config to Log
            copy_role = self.config.get("copy_role", "none")
            if copy_role.lower() != "none":
                config_log += f"COPY TRADE: {copy_role.upper()}\n"
                if copy_role.lower() == "slave":
                     mode = self.config.get("copy_lot_mode", "Fixed")
                     val = self.config.get("copy_lot_value", 0.01)
                     stealth = self.config.get("copy_stealth", False)
                     max_one = self.config.get("copy_max_one", False)
                     ignore_list = self.config.get("copy_ignore_list", "")
                     
                     if mode == "Risk %":
                         mode_str = f"Risk per trade ({val}%)"
                     else:
                         mode_str = f"{mode} ({val})"

                     config_log += f" - Lot Mode: {mode_str}\n"
                     config_log += f" - Stealth Mode: {'ON' if stealth else 'OFF'}\n"
                     config_log += f" - Max 1 Trade/Sym: {'ON' if max_one else 'OFF'}\n"
                     if ignore_list:
                         config_log += f" - Ignored Symbols: {ignore_list}\n"

            self.log(config_log)

            # Construct full telegram message
            full_tele_msg = f"{connect_msg}\n{algo_msg}\n{start_msg}\n{config_log}"
            self.send_telegram(full_tele_msg)

            # Multi-symbol H1 scanner is passive/read-only. Across all profile
            # workers, exactly one process owns the scanner lock at any point.
            self.h1_pattern_scanner = MultiSymbolH1PatternScanner(
                mt5,
                notify=self.send_telegram,
                log=self.log,
                profile_name=profile_name,
            )
            
            if copy_role != "none":
                self.log(T("log_copy_start").format(role=copy_role.upper()))

            last_lang_check = 0
            last_reconnect_check = 0
            last_h1_pattern_scan_check = 0
            # TRACKING: Initialize known tickets for closure detection
            self.known_tickets = set()
            first_run = True
            
            while not self.stop_event.is_set():
                try:
                    # Loop throttling to save CPU
                    time.sleep(0.2)

                    # Auto Reconnect MT5 (Every 10s if needed)
                    if time.time() - last_reconnect_check > 10.0:
                        last_reconnect_check = time.time()
                        if not mt5.terminal_info():
                            self.log("⚠️ Connection lost. Attempting reconnect...")
                            launch = ensure_mt5_profile_connected(
                                self.config,
                                mt5_module=mt5,
                                timeout_seconds=10,
                                allow_process_start=False,
                            )
                            if launch.ok:
                                # Refresh missing identity from the live session after
                                # reconnect so SL/TP mutations are not stuck unbound
                                # when the initial account_info() was empty.
                                acc = mt5.account_info()
                                if acc:
                                    bind_live_mt5_account_identity(self.config, acc)
                                self.log("✅ Reconnected.")
                            else:
                                self.log(
                                    f"⚠️ Still disconnected ({launch.failure_code}); "
                                    "waiting for manual MT5 open."
                                )
                                continue

                    # Passive multi-symbol H1 scan: XAU starts H04 with H03→H02;
                    # EUR/AUD/CAD/JPY start H03 with H02→H01, then use 3 H1s.
                    if time.time() - last_h1_pattern_scan_check > 15.0:
                        last_h1_pattern_scan_check = time.time()
                        self.h1_pattern_scanner.scan_once()

                    # Check Language Change (Every 2s)
                    if time.time() - last_lang_check > 2.0:
                        last_lang_check = time.time()
                        try:
                            if os.path.exists(SETTINGS_FILE):
                                with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                                    st = json.load(f)
                                    new_lang = st.get("lang", _i18n.CURRENT_LANG)
                                    if new_lang != _i18n.CURRENT_LANG:
                                        _i18n.CURRENT_LANG = new_lang
                        except Exception as e:
                            log.warning("CopyTrade state parse error: %s", e)

                    # Process Copy Trade
                    self.copy_manager.process()
                    
                    positions = mt5.positions_get()
                    # 1. Filter Monitored Positions & Build Current Ticket Set
                    monitored_pos = []
                    current_tickets = set()
                    
                    # Only proceed if positions is not None (None = Error)
                    if positions is not None:
                        for pos in positions:
                            # Filters
                            if magic != -1 and pos.magic != magic: continue
                            
                            # Symbol Match Logic (Contains check for suffix/prefix)
                            is_monitored = False
                            if not monitored_symbols:
                                is_monitored = True # No list = Monitor all
                            else:
                                pos_sym = pos.symbol.upper()
                                for mon_sym in monitored_symbols:
                                    if mon_sym in pos_sym:
                                        is_monitored = True
                                        break
                            
                            if is_monitored:
                                monitored_pos.append(pos)
                                current_tickets.add(pos.ticket)

                        # ---------------------------------------------------------
                        # DETECT CLOSED TRADES (Manual, SL, TP, Broker)
                        # ---------------------------------------------------------
                        if not first_run:
                            closed_tickets = self.known_tickets - current_tickets
                            self._clear_be_retry_state_for_tickets(closed_tickets)
                            for ticket in closed_tickets:
                                # Fetch Deal History
                                try:
                                    deals = mt5.history_deals_get(position=ticket)
                                    if deals:
                                        # Summarize Deals (Entry + Exit + Partials)
                                        total_profit = sum(d.profit for d in deals)
                                        total_swap = sum(d.swap for d in deals)
                                        total_comm = sum(d.commission for d in deals)
                                        net_profit = total_profit + total_swap + total_comm
                                        
                                        # Get last deal (Exit)
                                        last_deal = deals[-1]
                                        symbol = last_deal.symbol
                                        reason = last_deal.reason
                                        
                                        # Decode Reason
                                        reason_str = "Manual/Unknown"
                                        if reason == mt5.DEAL_REASON_SL: reason_str = "Stop Loss"
                                        elif reason == mt5.DEAL_REASON_TP: reason_str = "Take Profit"
                                        elif reason == mt5.DEAL_REASON_CLIENT: reason_str = "Manual Close"
                                        elif reason == mt5.DEAL_REASON_EXPERT: reason_str = "Robot/Expert"
                                        
                                        # Icon
                                        icon = "✅" if net_profit >= 0 else "🔻"
                                        
                                        msg = (
                                            f"{icon} [{self.config.get('profile_name', 'Unknown')}] Trade Closed\n"
                                            f"• {symbol} (Ticket: {ticket})\n"
                                            f"• P/L: {net_profit:+.2f} (Swap: {total_swap:.2f})\n"
                                            f"• Reason: {reason_str}"
                                        )
                                        self.notify(msg)
                                    else:
                                        pass
                                except Exception as e:
                                    self.log(f"Error checking closed trade {ticket}: {e}")

                        self.known_tickets = current_tickets
                        first_run = False
                        # ---------------------------------------------------------

                    if positions:
                        # 2. Balance SL/TP Check
                        balance_triggered = False
                        if use_balance_sltp and monitored_pos:
                            start_balance = get_start_day_balance()
                            if start_balance > 0:
                                total_pnl = sum(p.profit + p.swap for p in monitored_pos)
                                pnl_pct = (total_pnl / start_balance) * 100
                                
                                close_all_reason = ""
                                if balance_sl_pct > 0 and pnl_pct <= -balance_sl_pct:
                                    close_all_reason = f"Balance SL ({pnl_pct:.2f}% / -{balance_sl_pct}%) [Base: {start_balance:.2f}]"
                                elif balance_tp_pct > 0 and pnl_pct >= balance_tp_pct:
                                    close_all_reason = f"Balance TP ({pnl_pct:.2f}% / {balance_tp_pct}%) [Base: {start_balance:.2f}]"
                                
                                if close_all_reason:
                                    self.log(f"{T('log_signal')} {close_all_reason}")
                                    balance_triggered = True
                                    for pos in monitored_pos:
                                        self.close_position(pos, close_all_reason)
                        
                        # 3. Individual SL/TP & R Logic
                        if not balance_triggered:
                            for pos in monitored_pos:
                                if True: # try block wrapper
                                    tick = mt5.symbol_info_tick(pos.symbol)
                                    if not tick: continue

                                    # Determine SL/TP settings for this pos
                                    current_sl = sl
                                    current_tp = tp
                                    
                                    pos_sym_upper = pos.symbol.upper()
                                    is_gold = "XAU" in pos_sym_upper or "GOLD" in pos_sym_upper
                                    if is_gold:
                                        current_sl = gold_sl
                                        current_tp = gold_tp

                                    # SYNC: If Manual SL/TP exists, override Hidden SL/TP
                                    sym_info = mt5.symbol_info(pos.symbol)
                                    if sym_info:
                                        point = sym_info.point
                                        if pos.sl > 0:
                                            current_sl = round(abs(pos.price_open - pos.sl) / point)
                                        if pos.tp > 0:
                                            current_tp = round(abs(pos.price_open - pos.tp) / point)

                                    # --- R LOGIC (Partial & BE) ---
                                    # Get Ticket Data
                                    t_data = self.ticket_manager.get_ticket(pos.ticket)
                                    
                                    # Determine Risk Points (1R)
                                    risk_points = t_data.get("risk_points", 0)
                                    if risk_points == 0:
                                        # Lần đầu thấy lệnh, tính từ SL
                                        if pos.sl > 0:
                                            risk_points = abs(pos.price_open - pos.sl) / mt5.symbol_info(pos.symbol).point
                                        else:
                                            risk_points = current_sl
                                        if risk_points > 0:
                                            self.ticket_manager.update_ticket(pos.ticket, risk_points=risk_points, symbol=pos.symbol)
                                    elif pos.sl > 0:
                                        calculated_risk = abs(pos.price_open - pos.sl) / mt5.symbol_info(pos.symbol).point
                                        if calculated_risk > 0 and abs(calculated_risk - risk_points) > 1:
                                            risk_points = calculated_risk
                                            self.ticket_manager.update_ticket(pos.ticket, risk_points=risk_points, symbol=pos.symbol)
                                    
                                    # Determine Original Volume (For Partial Close % of Original)
                                    orig_vol = t_data.get("original_volume", 0.0)
                                    if orig_vol == 0.0:
                                        orig_vol = pos.volume
                                        self.ticket_manager.update_ticket(pos.ticket, original_volume=orig_vol)

                                    # Calculate Current R
                                    point = mt5.symbol_info(pos.symbol).point
                                    price_current = tick.bid if pos.type == mt5.POSITION_TYPE_BUY else tick.ask
                                    
                                    diff_points = 0.0
                                    if pos.type == mt5.POSITION_TYPE_BUY:
                                        diff_points = (price_current - pos.price_open) / point
                                    else:
                                        diff_points = (pos.price_open - price_current) / point
                                        
                                    current_r = 0
                                    if risk_points > 0:
                                        current_r = diff_points / risk_points

                                    # CHECK PARTIAL CLOSE
                                    if partial_r_levels and partial_pct_list and risk_points > 0:
                                        closed_levels = t_data.get("closed_levels", [])
                                        
                                        # Determine Mode: 
                                        # If len(pct) > 1 -> Use List Mode (% of ORIGINAL Volume)
                                        # If len(pct) == 1 -> Use Legacy Mode (% of CURRENT Volume)
                                        use_orig_vol_mode = len(partial_pct_list) > 1
                                        
                                        for i, target_r in enumerate(partial_r_levels):
                                            if current_r >= target_r and target_r not in closed_levels:
                                                # Get Percentage to close
                                                pct_to_close = 0.0
                                                if use_orig_vol_mode:
                                                    # Match index, fallback to last if index out of range
                                                    idx = i if i < len(partial_pct_list) else -1
                                                    pct_to_close = partial_pct_list[idx]
                                                else:
                                                    pct_to_close = partial_pct_list[0]

                                                # Execute Partial Close
                                                if use_orig_vol_mode:
                                                    # Calculate based on ORIGINAL Volume
                                                    vol_to_close = orig_vol * (pct_to_close / 100.0)
                                                else:
                                                    # Calculate based on CURRENT Volume (Legacy)
                                                    vol_to_close = pos.volume * (pct_to_close / 100.0)
                                                
                                                # Normalize Volume
                                                symbol_info = mt5.symbol_info(pos.symbol)
                                                if not symbol_info: continue

                                                step = symbol_info.volume_step
                                                min_vol = symbol_info.volume_min
                                                
                                                if step > 0:
                                                    vol_to_close = round(vol_to_close / step) * step
                                                    vol_to_close = round(vol_to_close, 2)

                                                # Limit check: Cannot close more than current volume
                                                if vol_to_close > pos.volume:
                                                    vol_to_close = pos.volume
                                                
                                                # Safety Runner: If user did NOT request 100% close, prevent Full Close
                                                if pct_to_close < 99.9 and vol_to_close >= pos.volume:
                                                    # Try to keep min_vol
                                                    if pos.volume > min_vol:
                                                        vol_to_close = pos.volume - min_vol
                                                        # Re-normalize
                                                        if step > 0:
                                                            vol_to_close = round(vol_to_close / step) * step
                                                            vol_to_close = round(vol_to_close, 2)
                                                    else:
                                                        # If pos.volume == min_vol, we cannot split.
                                                        self.log(T("log_partial_skip_min").format(vol=pos.volume, min=min_vol))
                                                        closed_levels.append(target_r)
                                                        self.ticket_manager.update_ticket(pos.ticket, closed_levels=closed_levels)
                                                        
                                                        # Force Auto BE here if not already moved
                                                        # This is the "Min Lot Protection" feature
                                                        is_be_moved = t_data.get("be_moved", False)
                                                        if not is_be_moved:
                                                            if self.move_sl_to_entry(pos):
                                                                self.ticket_manager.update_ticket(pos.ticket, be_moved=True)
                                                        continue

                                                # Check Min Vol Requirement
                                                if vol_to_close < min_vol:
                                                    # Try forcing to min_vol if possible
                                                    if pos.volume > min_vol:
                                                        vol_to_close = min_vol
                                                    else:
                                                        # Cannot split
                                                        self.log(T("log_partial_skip_min").format(vol=pos.volume, min=min_vol))
                                                        closed_levels.append(target_r)
                                                        self.ticket_manager.update_ticket(pos.ticket, closed_levels=closed_levels)
                                                        
                                                        # Force Auto BE here if not already moved
                                                        # This is the "Min Lot Protection" feature
                                                        is_be_moved = t_data.get("be_moved", False)
                                                        if not is_be_moved:
                                                            if self.move_sl_to_entry(pos):
                                                                self.ticket_manager.update_ticket(pos.ticket, be_moved=True)
                                                        continue

                                                # Verify position still exists before closing
                                                verify_pos = mt5.positions_get(ticket=pos.ticket)
                                                if not verify_pos:
                                                    self.log(f"⚠️ Position {pos.ticket} already closed, skipping partial")
                                                    closed_levels.append(target_r)
                                                    self.ticket_manager.update_ticket(pos.ticket, closed_levels=closed_levels)
                                                    continue
                                                self.close_position(pos, f"Partial {pct_to_close}% @ {target_r}R", volume=vol_to_close)
                                                
                                                # Update Persistence
                                                closed_levels.append(target_r)
                                                self.ticket_manager.update_ticket(pos.ticket, closed_levels=closed_levels)

                                    # CHECK AUTO BE
                                    if auto_be_r > 0 and risk_points > 0:
                                        is_be_moved = t_data.get("be_moved", False)
                                        if not is_be_moved and current_r >= auto_be_r:
                                            if self.move_sl_to_entry(pos):
                                                self.ticket_manager.update_ticket(pos.ticket, be_moved=True)

                                    # --- END R LOGIC ---

                                    # --- SYNC VISIBLE SL/TP (+- 10 points) ---
                                    if visible_sltp:
                                        try:
                                            target_visible_sl = 0.0
                                            target_visible_tp = 0.0
                                            
                                            # --- SYNC HIDDEN FROM VISIBLE (User Manual Change) ---
                                            # Check if user manually changed SL on MT5
                                            # If current SL is different from 0 and different from our last known state, update Hidden
                                            # But here we simplify: If SL exists, we update our "Hidden" SL tracking to match it if it's tighter.
                                            # Actually, if user sets SL, that IS the SL. Hidden SL is just a backup or for stealth.
                                            # If Visible SL is set, we use IT as the reference for R calculation and closing.
                                            
                                            # Update Ticket Data with new SL if changed
                                            if pos.sl > 0:
                                                current_sl_points = 0
                                                if pos.type == mt5.POSITION_TYPE_BUY:
                                                    current_sl_points = (pos.price_open - pos.sl) / point
                                                else:
                                                    current_sl_points = (pos.sl - pos.price_open) / point
                                                
                                                # If this SL is significantly different (e.g. > 1 point)
                                                # We consider it a manual update.
                                                # Note: We don't overwrite 'risk_points' (initial risk) to preserve R calc based on entry.
                                                # But we should respect this SL for closing.

                                            # Calculate buffer in price
                                            buffer_price = 10 * point
                                            
                                            # Target Hidden SL/TP in price
                                            # Use risk_points if available, else current_sl
                                            sl_pts = risk_points if risk_points > 0 else current_sl
                                            tp_pts = current_tp
                                            
                                            # Determine the robot's CURRENT target SL price
                                            is_be_moved = t_data.get("be_moved", False)
                                            if is_be_moved:
                                                # If BE moved, the robot's target is entry price
                                                current_target_sl_price = pos.price_open
                                            else:
                                                # Otherwise it's entry +/- sl_pts
                                                if pos.type == mt5.POSITION_TYPE_BUY:
                                                    current_target_sl_price = pos.price_open - (sl_pts * point)
                                                else:
                                                    current_target_sl_price = pos.price_open + (sl_pts * point)
                                                    
                                            if pos.type == mt5.POSITION_TYPE_BUY:
                                                # Visible SL should be at Hidden SL - 10 points
                                                if sl_pts > 0 or is_be_moved:
                                                    target_visible_sl = current_target_sl_price - buffer_price
                                                if tp_pts > 0:
                                                    target_visible_tp = pos.price_open + (tp_pts * point) + buffer_price
                                            else:
                                                # SELL
                                                if sl_pts > 0 or is_be_moved:
                                                    target_visible_sl = current_target_sl_price + buffer_price
                                                if tp_pts > 0:
                                                    target_visible_tp = pos.price_open - (tp_pts * point) - buffer_price
                                            
                                            # Round to symbol digits
                                            symbol_info = mt5.symbol_info(pos.symbol)
                                            if symbol_info:
                                                if target_visible_sl > 0: target_visible_sl = round(target_visible_sl, symbol_info.digits)
                                                if target_visible_tp > 0: target_visible_tp = round(target_visible_tp, symbol_info.digits)
                                                
                                                # CHỈ ĐẶT LẠI KHI SL/TP BỊ XOÁ (BẰNG 0)
                                                # Tôn trọng việc người dùng tự dời SL/TP thủ công
                                                final_sl = pos.sl
                                                final_tp = pos.tp
                                                update_needed = False
                                                
                                                # Kiểm tra SL
                                                if target_visible_sl > 0 and pos.sl == 0:
                                                    # Kiểm tra xem giá đã qua mức SL này chưa
                                                    is_passed = False
                                                    if pos.type == mt5.POSITION_TYPE_BUY:
                                                        if pos.price_current <= target_visible_sl: is_passed = True
                                                    else:
                                                        if pos.price_current >= target_visible_sl: is_passed = True
                                                    
                                                    if not is_passed:
                                                        final_sl = target_visible_sl
                                                        update_needed = True
                                                
                                                # Kiểm tra TP
                                                if target_visible_tp > 0 and pos.tp == 0:
                                                    # Kiểm tra xem giá đã qua mức TP này chưa
                                                    is_passed = False
                                                    if pos.type == mt5.POSITION_TYPE_BUY:
                                                        if pos.price_current >= target_visible_tp: is_passed = True
                                                    else:
                                                        if pos.price_current <= target_visible_tp: is_passed = True
                                                        
                                                    if not is_passed:
                                                        final_tp = target_visible_tp
                                                        update_needed = True
                                                    
                                                if update_needed:
                                                    req = {
                                                        "action": mt5.TRADE_ACTION_SLTP,
                                                        "position": pos.ticket,
                                                        "symbol": pos.symbol,
                                                        "sl": final_sl,
                                                        "tp": final_tp
                                                    }
                                                    def reconcile_visible_sltp():
                                                        rows = mt5.positions_get(ticket=pos.ticket) or []
                                                        if not rows:
                                                            return None
                                                        current = rows[0]
                                                        sl_ok = final_sl <= 0 or abs(float(getattr(current, "sl", 0.0) or 0.0) - final_sl) <= max(1e-8, abs(final_sl) * 1e-7)
                                                        tp_ok = final_tp <= 0 or abs(float(getattr(current, "tp", 0.0) or 0.0) - final_tp) <= max(1e-8, abs(final_tp) * 1e-7)
                                                        return pos.ticket if sl_ok and tp_ok else None

                                                    result = send_mutation_idempotent(
                                                        req,
                                                        f"visible-sltp:{self.config.get('profile_name', 'Unknown')}:{pos.ticket}:{final_sl}:{final_tp}",
                                                        mt5_module=mt5,
                                                        reconcile=reconcile_visible_sltp,
                                                        profile_config=self.config,
                                                    )
                                                    if result["status"] not in ("DONE", "EXISTING"):
                                                        # Unknown/rejected mutations are intentionally not retried blindly.
                                                        pass
                                        except Exception as e:
                                            # self.log(f"Visible SLTP Sync Exception: {e}")
                                            pass

                                    # Check Hidden SL/TP Conditions
                                    close = False
                                    reason = ""
                                    
                                    # If BE was moved, adjust Hidden SL to Entry Price
                                    is_be_moved = t_data.get("be_moved", False)
                                    
                                    if is_be_moved:
                                        # Hidden SL is now effectively 0 points (Entry Price)
                                        # diff_points calculates distance from Entry.
                                        # If diff_points is negative (Loss), we close.
                                        if diff_points < 0:
                                            close = True; reason = f"Hidden BE (Entry)"
                                    else:
                                        # Normal Hidden SL
                                        if current_sl > 0 and diff_points <= -current_sl:
                                            close = True; reason = f"SL ({diff_points:.1f}/{current_sl})"
                                            
                                    if current_tp > 0 and diff_points >= current_tp:
                                        close = True; reason = f"TP ({diff_points:.1f}/{current_tp})"

                                    if close:
                                        self.close_position(pos, reason)
                                    
                                    pass
                                
                                # except block wrapper
                                if False:
                                    pos_e = None
                                    self.log(f"Position Error ({pos.symbol}): {pos_e}")
                                    self.send_telegram(f"⚠️ Position Error ({pos.symbol}): {pos_e}")
                    
                    # Check stop event more frequently to avoid freezing
                    for _ in range(10):
                        if self.stop_event.is_set(): break
                        time.sleep(0.1)
                except Exception as loop_e:
                     self.log(f"Loop Error: {loop_e}")
                     self.send_telegram(f"⚠️ Loop Error: {loop_e}")
                     time.sleep(1.0) # Prevent tight loop on error
        except Exception as e:
            self.log(f"Runtime Error: {e}")
            self.send_telegram(f"⚠️ Runtime Error: {e}")
        finally:
            if self.h1_pattern_scanner is not None:
                self.h1_pattern_scanner.close()
            self._close_account_audit()
            mt5.shutdown()
            self.log(T("log_monitor_stop"))
