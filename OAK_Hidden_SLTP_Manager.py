# -*- coding: utf-8 -*-
"""OAK Hidden SLTP Manager — entry / re-exports.

Domain logic lives in ``domain/`` (CopyTradeManager, MonitorWorker, i18n, …).
GUI lives in ``app.py`` + ``controllers/``.
This module remains the worker/frozen entrypoint and public import surface.
"""
from __future__ import annotations

import argparse
import atexit
import os
import re
import signal
import subprocess
import sys
import threading
import time
import json
from datetime import datetime

import customtkinter as ctk
import MetaTrader5 as mt5

# --- Domain re-exports (back-compat for tests & workers) ---
from domain.constants import (  # noqa: F401
    APP_NAME,
    VERSION,
    BUILD,
    CONFIG_FILE,
    SETTINGS_FILE,
    TRADES_FILE,
    SESSION_RECOVERY_FILE,
    DEFAULT_TELEGRAM_TOKEN,
    MANUAL_TRENDS_FILE,
    MONDAY_SNAPSHOT_FILE,
    TUESDAY_SNAPSHOT_FILE,
    WEDNESDAY_SNAPSHOT_FILE,
    THURSDAY_SNAPSHOT_FILE,
    FRIDAY_SNAPSHOT_FILE,
    MIMO_BOT_CONFIG,
    MIMO_QUEUE_FILE,
    MIMO_RESULT_FILE,
    _mimo_bot_token,
    _mimo_bot_chat_id,
)
from domain.json_io import load_json, save_json, resource_path  # noqa: F401
from domain import i18n as _i18n
from domain.i18n import LANG, T  # noqa: F401

# Mutable lang alias — writes go to domain.i18n
def _get_CURRENT_LANG():
    return _i18n.CURRENT_LANG

def _set_CURRENT_LANG(v):
    _i18n.CURRENT_LANG = v

# Module-level CURRENT_LANG for `from OAK... import CURRENT_LANG` and `global CURRENT_LANG`
CURRENT_LANG = _i18n.CURRENT_LANG

from domain.mt5_orders import get_filling_type, send_order_with_retry  # noqa: F401
from domain.ticket_manager import TicketManager  # noqa: F401
from domain.file_lock import FileLock  # noqa: F401
from domain.balance import get_start_day_balance  # noqa: F401
from domain.ghost_operator import GhostOperator, show_ghost_consent, GHOST_LIB_AVAILABLE  # noqa: F401
from domain.copy_trade_manager import CopyTradeManager  # noqa: F401
from domain.monitor_worker import MonitorWorker  # noqa: F401

from oak_response_dict import get_random_response
from oak_logger import setup_logger
from repositories.sqlite_store import SQLiteStore  # noqa: F401
from repositories.profile_store import ProfileStore  # noqa: F401
from models.app_state import AppState  # noqa: F401
from services.signal_process_supervisor import SignalProcessSupervisor  # noqa: F401
from ui.base_tab import BaseTab  # noqa: F401
from ui.signals_tab import SignalsTab  # noqa: F401
from ui.profiles_tab import ProfilesTab  # noqa: F401
from utils import (  # noqa: F401
    build_signal_process_cmd,
    SIGNAL_SCRIPT_MAP,
    UnsupportedFrozenProcessError,
    compute_telegram_backoff,
    get_latest_display_signal,
)

log = setup_logger("oak")

# --- PROCESS CLEANUP ---
_running_processes = []

def _cleanup_processes():
    """Kill all spawned child processes on exit."""
    for proc in _running_processes:
        try:
            if proc.poll() is None:
                proc.kill()
        except:
            pass

atexit.register(_cleanup_processes)

def _signal_handler(signum, frame):
    """Handle SIGINT/SIGTERM to cleanup processes."""
    _cleanup_processes()
    sys.exit(0)

signal.signal(signal.SIGINT, _signal_handler)
signal.signal(signal.SIGTERM, _signal_handler)


class ToolTip:
    def __init__(self, widget, text_key):
        self.widget = widget
        self.text_key = text_key # Store the key for translation
        self.tip_window = None
        self.widget.bind("<Enter>", self.show_tip)
        self.widget.bind("<Leave>", self.hide_tip)

    def show_tip(self, event=None):
        if self.tip_window:
            return
        text = T(self.text_key) # Get translated text on show
        if not text: return
        
        x, y, cx, cy = self.widget.bbox("insert")
        x = x + self.widget.winfo_rootx() + 25
        y = y + cy + self.widget.winfo_rooty() + 25
        self.tip_window = tw = tkinter.Toplevel(self.widget)
        tw.wm_overrideredirect(1)
        tw.wm_geometry("+%d+%d" % (x, y))
        label = tkinter.Label(tw, text=text, justify=tkinter.LEFT,
                      background="#ffffe0", relief=tkinter.SOLID, borderwidth=1,
                      font=("tahoma", "9", "normal"))
        label.pack(ipadx=1)

    def hide_tip(self, event=None):
        tw = self.tip_window
        self.tip_window = None
        if tw:
            tw.destroy()

def add_help_icon(parent, row, column, text_key, padx=5, pady=0, sticky="w"):
    """Helper to add a (?) icon with tooltip using translation key"""
    help_lbl = ctk.CTkLabel(parent, text=" ⓘ", font=ctk.CTkFont(size=14, weight="bold"), text_color="#3498db", cursor="hand2")
    help_lbl.grid(row=row, column=column, padx=padx, pady=pady, sticky=sticky)
    ToolTip(help_lbl, text_key)
    return help_lbl

# --- END TOOLTIP ---

def get_natural_response(category, **kwargs):
    """Wrapper to use the centralized response dictionary with existing categories"""
    # Map old categories to new keys if needed
    category_map = {
        "order_placed": "order_placed",
        "order_deleted": "del_success",
        "all_deleted": "del_all_success",
        "all_ticket_close_deleted": "all_ticket_close_deleted", # New key
        "modify_success": "modify_success",
        "close_all_success": "close_all_success",
        "partial_task_added": "partial_task_added",
        "status_header": "list_header",
        "list_header": "list_header",
        "error": "error_general"
    }
    key = category_map.get(category, category)
    return get_random_response(key, **kwargs)

# --- CONSTANTS & CONFIG ---


def get_natural_response(category, **kwargs):
    try:
        return get_random_response(category, **kwargs)
    except Exception:
        return ""


# --- GUI APP (lazy) ---
def __getattr__(name):
    if name == "App":
        from app import App as _App
        return _App
    if name == "CURRENT_LANG":
        return _i18n.CURRENT_LANG
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


# --- WORKER PROCESS ---
def run_worker(profile_name):
    """
    Worker process entry point.
    Loads profile from CONFIG_FILE and runs MonitorWorker.
    """
    lock_fd = None
    safe = re.sub(r"[^\w\-]", "_", profile_name or "unknown")
    lock_path = f"worker_{safe}.lock"

    def _acquire_worker_lock():
        """Only one worker process per profile may run (prevents double schedule fire)."""
        nonlocal lock_fd
        try:
            if os.path.exists(lock_path):
                try:
                    with open(lock_path, "r", encoding="utf-8") as f:
                        old_pid = int((f.read() or "0").strip() or "0")
                except Exception:
                    old_pid = 0
                if old_pid and old_pid != os.getpid():
                    try:
                        r = subprocess.run(
                            ["tasklist", "/FI", f"PID eq {old_pid}", "/NH"],
                            capture_output=True, text=True,
                            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
                        )
                        out = (r.stdout or "").lower()
                        if str(old_pid) in out and "python" in out:
                            print(
                                f"[{datetime.now().strftime('%H:%M:%S')}] "
                                f"EXIT: worker for '{profile_name}' already running (PID {old_pid}). "
                                f"Avoid multi-worker schedule double-fire.",
                                flush=True,
                            )
                            return False
                    except Exception:
                        pass
            # Exclusive create when possible; always write our pid
            try:
                lock_fd = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_RDWR)
                os.write(lock_fd, str(os.getpid()).encode("utf-8"))
            except FileExistsError:
                # Stale or race — overwrite if process dead
                with open(lock_path, "w", encoding="utf-8") as f:
                    f.write(str(os.getpid()))
            return True
        except Exception as e:
            print(f"Worker lock warning: {e}", flush=True)
            return True

    def _release_worker_lock():
        nonlocal lock_fd
        try:
            if lock_fd is not None:
                try:
                    os.close(lock_fd)
                except Exception:
                    pass
                lock_fd = None
            if os.path.exists(lock_path):
                try:
                    with open(lock_path, "r", encoding="utf-8") as f:
                        pid = (f.read() or "").strip()
                    if pid == str(os.getpid()):
                        os.remove(lock_path)
                except Exception:
                    pass
        except Exception:
            pass

    try:
        if not _acquire_worker_lock():
            return

        # Load Config
        if not os.path.exists(CONFIG_FILE):
            print(f"Error: {CONFIG_FILE} not found.")
            return

        # Load Settings (Lang)
        global CURRENT_LANG
        try:
            if os.path.exists(SETTINGS_FILE):
                with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                    settings = json.load(f)
                    _i18n.CURRENT_LANG = settings.get("lang", "VN")
                    CURRENT_LANG = _i18n.CURRENT_LANG
        except: pass

        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            profiles = json.load(f)
            
        if profile_name not in profiles:
            print(f"Error: Profile '{profile_name}' not found.")
            return
            
        config = profiles[profile_name]
        config["profile_name"] = profile_name
        
        # Setup Logging
        def worker_log(msg):
            # Print with timestamp for Parent to parse if needed, or just raw
            # We use a special prefix to distinguish log from other output if needed
            # But simple print is fine for now.
            try:
                timestamp = datetime.now().strftime("%H:%M:%S")
                final_msg = f"[{timestamp}] {msg}"
                # Force flush to ensure Parent gets it immediately
                print(final_msg, flush=True)
            except: pass

        # Stop Event
        stop_event = threading.Event()
        
        # Signal Handling for Graceful Exit
        import signal
        def signal_handler(sig, frame):
            worker_log("Stopping worker...")
            stop_event.set()
            
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
        
        # Start Worker
        worker = MonitorWorker(config, worker_log, stop_event)
        worker.log(f"Worker Process Started: {profile_name} (PID {os.getpid()}, single-instance)")
        
        # Run logic inline (since we are in a dedicated process)
        # But MonitorWorker is a Thread. We can just start it and join.
        worker.start()
        
        # Keep main thread alive until worker stops
        while worker.is_alive():
            try:
                time.sleep(0.5)
            except KeyboardInterrupt:
                stop_event.set()
                break
                
        worker.join()
        print("Worker Process Exited.")
        
    except Exception as e:
        print(f"Worker Error: {e}", flush=True)
    finally:
        _release_worker_lock()


if __name__ == "__main__":
    # Argument Parsing
    parser = argparse.ArgumentParser()
    parser.add_argument("--worker", action="store_true", help="Run in worker mode")
    parser.add_argument("--signal-bot", action="store_true", help="Run signal bot mode")
    parser.add_argument("--factcheck-worker", action="store_true", help="Run fact-check worker mode")
    parser.add_argument("--profile", type=str, help="Profile name to run")
    args, unknown = parser.parse_known_args()

    if args.factcheck_worker:
        import factcheck_worker
        factcheck_worker.main()
    elif args.signal_bot and args.profile:
        # Frozen exe: run signal bot directly
        import mt5_signal_bot
        mt5_signal_bot.main(profile_name=args.profile)
    elif args.worker and args.profile:
        run_worker(args.profile)
    else:
        try:
            # Critical: when this file is run as __main__, a later
            # `import OAK_Hidden_SLTP_Manager` would load a *second* copy of
            # the module (split state, broken Signals tab, etc.). Alias first.
            sys.modules["OAK_Hidden_SLTP_Manager"] = sys.modules[__name__]
            from app import App, main as app_main
            app_main()
        except Exception as startup_e:
            with open("app_error.log", "w", encoding="utf-8") as f:
                import traceback
                f.write(f"Startup Error: {startup_e}\n")
                f.write(traceback.format_exc())
            # Also print to stderr
            print(f"Startup Error: {startup_e}", file=sys.stderr)
            sys.exit(1)
