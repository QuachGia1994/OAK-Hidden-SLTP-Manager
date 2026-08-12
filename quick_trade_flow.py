# -*- coding: utf-8 -*-
"""
Quick Trade Flow — Multi-step Telegram order entry state machine.
Handles per-profile symbol/lot configuration, preflight position check,
mandatory netting behavior (opposite position close before open), and idempotency.
"""

from __future__ import annotations

import os
import re
import time
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Tuple


class QuickTradeState(str, Enum):
    IDLE = "IDLE"
    SYMBOL_SELECTION = "SYMBOL_SELECTION"
    SYMBOL_CUSTOM_INPUT = "SYMBOL_CUSTOM_INPUT"
    DIRECTION_SELECTION = "DIRECTION_SELECTION"
    ENTRY_TIME_SELECTION = "ENTRY_TIME_SELECTION"
    ENTRY_TIME_CUSTOM_INPUT = "ENTRY_TIME_CUSTOM_INPUT"
    PROFILE_SELECTION = "PROFILE_SELECTION"
    PROFILE_SYMBOL_CONFIGURATION = "PROFILE_SYMBOL_CONFIGURATION"
    PROFILE_SYMBOL_CUSTOM_INPUT = "PROFILE_SYMBOL_CUSTOM_INPUT"
    PROFILE_LOT_CONFIGURATION = "PROFILE_LOT_CONFIGURATION"
    PROFILE_LOT_CUSTOM_INPUT = "PROFILE_LOT_CUSTOM_INPUT"
    REVIEW = "REVIEW"
    PRECHECK = "PRECHECK"
    NETTING_CLOSE = "NETTING_CLOSE"
    EXECUTION = "EXECUTION"
    RESULT = "RESULT"


class QuickTradeSession:
    def __init__(self, chat_id: int, user_id: int):
        self.chat_id = chat_id
        self.user_id = user_id
        self.state = QuickTradeState.SYMBOL_SELECTION
        self.symbol: str = "XAUUSD"
        self.direction: str = ""  # BUY or SELL
        self.hour: str = "3"
        self.entry_time: str = ""  # HH:MM
        self.selected_profiles: List[str] = []
        self.profile_configs: Dict[str, Dict[str, Any]] = {}  # {name: {"symbol": str, "lot": float|None}}
        self.editing_profile: Optional[str] = None
        self.confirm_lock: bool = False
        self.created_at: float = time.time()
        self.last_activity_at: float = time.time()
        self.precheck_report: List[Dict[str, Any]] = []
        self.execution_results: List[Dict[str, Any]] = []

    def touch(self) -> None:
        self.last_activity_at = time.time()

    def is_expired(self, timeout_seconds: float = 300.0) -> bool:
        return (time.time() - self.last_activity_at) > timeout_seconds


def validate_lot(lot_val: Any, min_vol: float = 0.01, max_vol: float = 100.0) -> Tuple[bool, float, str]:
    try:
        val = float(lot_val)
    except (TypeError, ValueError):
        return False, 0.0, "Lot phải là số thực hợp lệ (ví dụ: 0.01)"
    if val <= 0:
        return False, 0.0, "Lot phải lớn hơn 0"
    if val < min_vol:
        return False, 0.0, f"Lot phải >= {min_vol}"
    if val > max_vol:
        return False, 0.0, f"Lot phải <= {max_vol}"
    return True, round(val, 2), "OK"


def validate_entry_time(time_str: str) -> Tuple[bool, str, str]:
    clean = time_str.strip()
    match = re.fullmatch(r"(\d{1,2}):([0-5]\d)", clean)
    if match:
        h, m = int(match.group(1)), int(match.group(2))
        if 0 <= h <= 23:
            return True, f"{h:02d}:{m:02d}", "OK"
    return False, "", "Giờ entry phải theo định dạng HH:MM (ví dụ 09:15)"


def validate_symbol(sym_str: str) -> Tuple[bool, str, str]:
    clean = sym_str.strip().upper()
    if re.fullmatch(r"[A-Z0-9]{2,12}", clean):
        return True, clean, "OK"
    return False, "", "Symbol phải từ 2-12 ký tự chữ/số (ví dụ: XAUUSD, EURUSD)"


# Default MT5/Profile providers (overridable for tests)
def _default_get_all_profiles() -> List[str]:
    try:
        from mimo_bot import get_all_profiles
        profs = get_all_profiles()
        if profs:
            return profs
    except Exception:
        pass
    return ["Profile A", "Profile B", "Profile C"]


def _default_position_provider(profile_name: str, symbol: str) -> List[Dict[str, Any]]:
    """Query open positions via MT5 for profile."""
    try:
        import MetaTrader5 as mt5
        from mimo_bot import CONFIG_FILE, load_json

        config = load_json(CONFIG_FILE, {})
        prof_cfg = config.get(profile_name, {})
        path = prof_cfg.get("path", "")
        if path and os.path.exists(path):
            mt5.initialize(path=path)
        else:
            mt5.initialize()

        positions = mt5.positions_get(symbol=symbol) if symbol else mt5.positions_get()
        res = []
        if positions:
            for pos in positions:
                pos_type = "BUY" if getattr(pos, "type", 0) == 0 else "SELL"
                res.append({
                    "ticket": getattr(pos, "ticket", 0),
                    "symbol": getattr(pos, "symbol", symbol),
                    "type": pos_type,
                    "volume": float(getattr(pos, "volume", 0.0)),
                    "price_open": float(getattr(pos, "price_open", 0.0)),
                    "profit": float(getattr(pos, "profit", 0.0)),
                })
        return res
    except Exception:
        return []


def _default_position_closer(profile_name: str, symbol: str, opp_type: str) -> Tuple[bool, str]:
    """Close existing opposite position for netting compliance."""
    try:
        import MetaTrader5 as mt5
        from mimo_bot import CONFIG_FILE, load_json

        config = load_json(CONFIG_FILE, {})
        prof_cfg = config.get(profile_name, {})
        path = prof_cfg.get("path", "")
        if path and os.path.exists(path):
            mt5.initialize(path=path)
        else:
            mt5.initialize()

        positions = mt5.positions_get(symbol=symbol) or []
        target_pos = [p for p in positions if ("BUY" if getattr(p, "type", 0) == 0 else "SELL") == opp_type]
        if not target_pos:
            return True, "No open opposite position"

        close_type = mt5.ORDER_TYPE_SELL if opp_type == "BUY" else mt5.ORDER_TYPE_BUY
        for pos in target_pos:
            tick_info = mt5.symbol_info_tick(symbol)
            price = tick_info.bid if opp_type == "BUY" else (tick_info.ask if tick_info else 0.0)
            req = {
                "action": mt5.TRADE_ACTION_DEAL,
                "symbol": symbol,
                "volume": getattr(pos, "volume", 0.01),
                "type": close_type,
                "position": getattr(pos, "ticket", 0),
                "price": price,
                "deviation": 20,
                "magic": 888888,
                "comment": "QuickTrade Netting Close",
            }
            res = mt5.order_send(req)
            if not res or getattr(res, "retcode", -1) != getattr(mt5, "TRADE_RETCODE_DONE", 10009):
                return False, f"Position close failed retcode={getattr(res, 'retcode', 'ERR')}"

        return True, "All opposite positions closed"
    except Exception as e:
        return False, f"Exception closing position: {e}"


def _default_order_executor(profile_name: str, symbol: str, direction: str, lot: float, entry_time: str) -> Tuple[bool, str, Optional[int]]:
    """Execute order or pending trade for profile."""
    try:
        from mimo_bot import _inject_to_oak_inbox
        cmd = f"/pending {direction} {symbol} {lot} @{entry_time} {profile_name}"
        _inject_to_oak_inbox(cmd, chat_id=0)
        synthetic_id = int(time.time() * 1000) % 1000000
        return True, f"Placed {direction} {symbol} {lot} @{entry_time}", synthetic_id
    except Exception as e:
        return False, f"Order execution failed: {e}", None


class QuickTradeManager:
    def __init__(self):
        self._sessions: Dict[Tuple[int, int], QuickTradeSession] = {}
        # Provider hooks (can be mocked in tests)
        self.get_all_profiles_fn: Callable[[], List[str]] = _default_get_all_profiles
        self.position_provider_fn: Callable[[str, str], List[Dict[str, Any]]] = _default_position_provider
        self.position_closer_fn: Callable[[str, str, str], Tuple[bool, str]] = _default_position_closer
        self.order_executor_fn: Callable[[str, str, str, float, str], Tuple[bool, str, Optional[int]]] = _default_order_executor

    def get_session(self, chat_id: int, user_id: int) -> Optional[QuickTradeSession]:
        session = self.get_session_by_chat(chat_id)
        if session and session.user_id == user_id:
            return session
        return None

    def get_session_by_chat(self, chat_id: int) -> Optional[QuickTradeSession]:
        keys_to_del = []
        target = None
        for key, session in self._sessions.items():
            if session.chat_id == chat_id:
                if session.is_expired():
                    keys_to_del.append(key)
                else:
                    session.touch()
                    target = session
        for k in keys_to_del:
            del self._sessions[k]
        return target

    def start_session(self, chat_id: int, user_id: int, initial_symbol: str = "XAUUSD", initial_direction: str = "", initial_hour: str = "3") -> QuickTradeSession:
        self.cleanup_stale_sessions()
        self.cancel_session(chat_id, user_id)
        session = QuickTradeSession(chat_id, user_id)
        session.symbol = initial_symbol.upper()
        session.direction = initial_direction.upper()
        session.hour = str(initial_hour)
        session.state = QuickTradeState.SYMBOL_SELECTION
        self._sessions[(chat_id, user_id)] = session
        return session

    def cancel_session(self, chat_id: int, user_id: int) -> bool:
        keys_to_del = [k for k, s in self._sessions.items() if s.chat_id == chat_id]
        for k in keys_to_del:
            del self._sessions[k]
        return len(keys_to_del) > 0

    def cleanup_stale_sessions(self, timeout_seconds: float = 300.0) -> int:
        keys_to_del = [k for k, s in self._sessions.items() if s.is_expired(timeout_seconds)]
        for k in keys_to_del:
            del self._sessions[k]
        return len(keys_to_del)

    # -------------------------------------------------------------------------
    # RENDER HELPER MESSAGES & INLINE KEYBOARDS
    # -------------------------------------------------------------------------
    def render_step_symbol(self, session: QuickTradeSession) -> Tuple[str, Any]:
        text = "🤖 *QUICK TRADE — Bước 1/6: Chọn Symbol*\n\nVui lòng chọn hoặc nhập Symbol cần giao dịch:"
        buttons = [
            [{"text": "XAUUSD", "callback_data": "qt:sym:XAUUSD"},
             {"text": "EURUSD", "callback_data": "qt:sym:EURUSD"},
             {"text": "GBPUSD", "callback_data": "qt:sym:GBPUSD"}],
            [{"text": "BTCUSD", "callback_data": "qt:sym:BTCUSD"},
             {"text": "USDJPY", "callback_data": "qt:sym:USDJPY"},
             {"text": "✏️ Nhập Symbol khác", "callback_data": "qt:sym_input"}],
            [{"text": "❌ HỦY", "callback_data": "qt:cancel"}]
        ]
        return text, {"inline_keyboard": buttons}

    def render_step_direction(self, session: QuickTradeSession) -> Tuple[str, Any]:
        hour_info = f" (H={session.hour})" if session.hour else ""
        text = (
            f"🤖 *QUICK TRADE — Bước 2/6: Chọn hướng vào lệnh*{hour_info}\n\n"
            f"Symbol: *{session.symbol}*\n"
            f"Vui lòng chọn hướng giao dịch:"
        )
        buttons = [
            [{"text": "🟢 BUY", "callback_data": "qt:dir:BUY"},
             {"text": "🔴 SELL", "callback_data": "qt:dir:SELL"}],
            [{"text": "❌ HỦY", "callback_data": "qt:cancel"}]
        ]
        return text, {"inline_keyboard": buttons}

    def render_step_entry_time(self, session: QuickTradeSession) -> Tuple[str, Any]:
        text = (
            f"🤖 *QUICK TRADE — Bước 3/6: Chọn giờ Entry*\n\n"
            f"Symbol: *{session.symbol}* | Hướng: *{session.direction}*\n"
            f"Vui lòng chọn hoặc nhập giờ Entry (định dạng HH:MM broker clock):"
        )
        presets = ["03:49", "05:00", "09:15", "14:49"]
        preset_row = [{"text": t, "callback_data": f"qt:time:{t}"} for t in presets[:3]]
        buttons = [
            preset_row,
            [{"text": "✏️ Nhập giờ khác", "callback_data": "qt:time_input"}],
            [{"text": "❌ HỦY", "callback_data": "qt:cancel"}]
        ]
        return text, {"inline_keyboard": buttons}

    def render_step_profile_selection(self, session: QuickTradeSession) -> Tuple[str, Any]:
        all_profiles = self.get_all_profiles_fn()
        text = (
            f"🤖 *QUICK TRADE — Bước 4/6: Chọn Profile thực thi*\n\n"
            f"Symbol: *{session.symbol}* | Hướng: *{session.direction}* | Entry: *{session.entry_time}*\n\n"
            f"Chọn một hoặc nhiều profile (nhấn để chọn/bỏ chọn):"
        )
        buttons = []
        for prof in all_profiles:
            is_sel = prof in session.selected_profiles
            mark = "✓ " if is_sel else "  "
            buttons.append([{"text": f"{mark}{prof}", "callback_data": f"qt:prof_toggle:{prof}"}])
        buttons.append([{"text": "➡️ TIẾP TỤC", "callback_data": "qt:prof_next"}])
        buttons.append([{"text": "❌ HỦY", "callback_data": "qt:cancel"}])
        return text, {"inline_keyboard": buttons}

    def render_step_per_profile_symbol(self, session: QuickTradeSession) -> Tuple[str, Any]:
        lines = [
            "🤖 *QUICK TRADE — Bước 5/6: Cấu hình Symbol cho từng Profile*\n",
            f"Hướng: *{session.direction}* | Entry: *{session.entry_time}*\n",
            "*Danh sách Profile & Symbol:*"
        ]
        buttons = []
        for prof in session.selected_profiles:
            cfg = session.profile_configs.get(prof, {})
            sym = cfg.get("symbol", session.symbol)
            lines.append(f"• *{prof}*: Symbol = `{sym}`")
            buttons.append([{"text": f"✏️ Đổi Symbol cho {prof}", "callback_data": f"qt:psym_edit:{prof}"}])
        lines.append("\nNhấn *TIẾP TỤC* khi đã cấu hình xong Symbol.")
        buttons.append([{"text": "➡️ TIẾP TỤC", "callback_data": "qt:psym_next"}])
        buttons.append([{"text": "❌ HỦY", "callback_data": "qt:cancel"}])
        return "\n".join(lines), {"inline_keyboard": buttons}

    def render_step_per_profile_lot(self, session: QuickTradeSession) -> Tuple[str, Any]:
        lines = [
            "🤖 *QUICK TRADE — Bước 6/6: Cấu hình Lot cho từng Profile*\n",
            "*Danh sách Profile, Symbol & Lot:*"
        ]
        buttons = []
        for prof in session.selected_profiles:
            cfg = session.profile_configs.get(prof, {})
            sym = cfg.get("symbol", session.symbol)
            lot = cfg.get("lot")
            lot_str = f"`{lot}`" if lot is not None else "⚠️ *Chưa nhập*"
            lines.append(f"• *{prof}* ({sym}): Lot = {lot_str}")
            buttons.append([{"text": f"✏️ Nhập Lot cho {prof}", "callback_data": f"qt:plot_edit:{prof}"}])
        lines.append("\nTất cả lot phải hợp lệ (> 0). Nhấn *XÁC NHẬN* để chuyển sang Review.")
        buttons.append([{"text": "📋 XÁC NHẬN & XEM REVIEW", "callback_data": "qt:plot_next"}])
        buttons.append([{"text": "❌ HỦY", "callback_data": "qt:cancel"}])
        return "\n".join(lines), {"inline_keyboard": buttons}

    def render_step_review(self, session: QuickTradeSession) -> Tuple[str, Any]:
        lines = [
            "📋 *TRADE REVIEW — XÁC NHẬN GIAO DỊCH*\n",
            f"• *Hướng:* {session.direction}",
            f"• *Giờ Entry:* {session.entry_time}\n",
            "*Cấu hình chi tiết từng Profile:*"
        ]
        for i, prof in enumerate(session.selected_profiles, 1):
            cfg = session.profile_configs.get(prof, {})
            sym = cfg.get("symbol", session.symbol)
            lot = cfg.get("lot", 0.01)
            lines.append(f"{i}. *{prof}* — Symbol: `{sym}` | Lot: `{lot}`")

        lines.append("\n⚠️ *Vui lòng kiểm tra kỹ trước khi nhấn CONFIRM!*")
        buttons = [
            [{"text": "✅ CONFIRM EXECUTION", "callback_data": "qt:confirm"},
             {"text": "❌ CANCEL", "callback_data": "qt:cancel"}]
        ]
        return "\n".join(lines), {"inline_keyboard": buttons}

    # -------------------------------------------------------------------------
    # PRECHECK & NETTING EXECUTION LOGIC
    # -------------------------------------------------------------------------
    def run_precheck(self, session: QuickTradeSession) -> List[Dict[str, Any]]:
        session.state = QuickTradeState.PRECHECK
        report = []
        for prof in session.selected_profiles:
            cfg = session.profile_configs.get(prof, {})
            sym = cfg.get("symbol", session.symbol)
            lot = cfg.get("lot", 0.01)

            positions = self.position_provider_fn(prof, sym)
            buy_vol = sum(p.get("volume", 0.0) for p in positions if p.get("type") == "BUY")
            sell_vol = sum(p.get("volume", 0.0) for p in positions if p.get("type") == "SELL")

            item = {
                "profile": prof,
                "symbol": sym,
                "requested_direction": session.direction,
                "requested_lot": lot,
                "existing_buy_vol": buy_vol,
                "existing_sell_vol": sell_vol,
                "positions": positions,
                "netting_needed": False,
                "opp_type": None,
                "action_desc": "",
            }

            if session.direction == "BUY" and sell_vol > 0:
                item["netting_needed"] = True
                item["opp_type"] = "SELL"
                item["action_desc"] = f"NETTING: CLOSE SELL ({sell_vol}) → OPEN BUY ({lot})"
            elif session.direction == "SELL" and buy_vol > 0:
                item["netting_needed"] = True
                item["opp_type"] = "BUY"
                item["action_desc"] = f"NETTING: CLOSE BUY ({buy_vol}) → OPEN SELL ({lot})"
            elif session.direction == "BUY" and buy_vol > 0:
                item["action_desc"] = f"EXISTING BUY ({buy_vol}) → OPEN ADDITIONAL BUY ({lot})"
            elif session.direction == "SELL" and sell_vol > 0:
                item["action_desc"] = f"EXISTING SELL ({sell_vol}) → OPEN ADDITIONAL SELL ({lot})"
            else:
                item["action_desc"] = f"OPEN {session.direction} ({lot})"

            report.append(item)

        session.precheck_report = report
        return report

    def render_precheck_report(self, session: QuickTradeSession) -> str:
        lines = ["⚡ *EXECUTION PRECHECK*\n"]
        for i, item in enumerate(session.precheck_report, 1):
            prof = item["profile"]
            sym = item["symbol"]
            desc = item["action_desc"]
            buy_v = item["existing_buy_vol"]
            sell_v = item["existing_sell_vol"]
            pos_str = f"BUY {buy_v}" if buy_v > 0 else (f"SELL {sell_v}" if sell_v > 0 else "NONE")
            lines.append(f"{i}. *{prof}* ({sym})")
            lines.append(f"   • Vị thế hiện tại: `{pos_str}`")
            lines.append(f"   • Yêu cầu: `{item['requested_direction']} {item['requested_lot']}`")
            lines.append(f"   • Hành động: `{desc}`\n")
        lines.append("⏳ *Đang tiến hành thực thi...*")
        return "\n".join(lines)

    def execute_trade(self, session: QuickTradeSession) -> List[Dict[str, Any]]:
        session.state = QuickTradeState.EXECUTION
        results = []

        for item in session.precheck_report:
            prof = item["profile"]
            sym = item["symbol"]
            req_dir = item["requested_direction"]
            lot = item["requested_lot"]
            opp_type = item["opp_type"]

            res_item = {
                "profile": prof,
                "symbol": sym,
                "direction": req_dir,
                "lot": lot,
                "close_success": True,
                "close_message": "N/A",
                "open_success": False,
                "open_message": "",
                "ticket": None,
            }

            # Mandatory Netting Stage: Close opposite position first if needed
            if item["netting_needed"] and opp_type:
                session.state = QuickTradeState.NETTING_CLOSE
                close_ok, close_msg = self.position_closer_fn(prof, sym, opp_type)
                res_item["close_success"] = close_ok
                res_item["close_message"] = close_msg
                if not close_ok:
                    res_item["open_success"] = False
                    res_item["open_message"] = f"SKIPPED: Đóng vị thế {opp_type} thất bại ({close_msg})"
                    results.append(res_item)
                    continue  # DO NOT OPEN NEW OPPOSITE TRADE

            # New Order Execution Stage
            session.state = QuickTradeState.EXECUTION
            open_ok, open_msg, ticket = self.order_executor_fn(prof, sym, req_dir, lot, session.entry_time)
            res_item["open_success"] = open_ok
            res_item["open_message"] = open_msg
            res_item["ticket"] = ticket
            results.append(res_item)

        session.execution_results = results
        session.state = QuickTradeState.RESULT
        return results

    def render_execution_results(self, session: QuickTradeSession) -> str:
        lines = ["📊 *TRADE RESULT*\n"]
        success_count = sum(1 for r in session.execution_results if r["open_success"] and r["close_success"])
        total_count = len(session.execution_results)

        for r in session.execution_results:
            prof = r["profile"]
            sym = r["symbol"]
            is_ok = r["open_success"] and r["close_success"]
            icon = "✓" if is_ok else "✗"
            lines.append(f"{icon} *{prof}* ({sym})")
            lines.append(f"   • Lệnh: `{r['direction']} {r['lot']} @ {session.entry_time}`")
            if r["close_message"] != "N/A":
                c_mark = "SUCCESS" if r["close_success"] else "FAILED"
                lines.append(f"   • Đóng vị thế cũ: *{c_mark}* ({r['close_message']})")
            o_mark = "SUCCESS" if r["open_success"] else "FAILED"
            ticket_str = f" (Ticket: #{r['ticket']})" if r["ticket"] else ""
            lines.append(f"   • Mở lệnh mới: *{o_mark}*{ticket_str}")
            if not is_ok and r["open_message"]:
                lines.append(f"   • Chi tiết: {r['open_message']}")
            lines.append("")

        lines.append(f"📌 *Tổng kết:* {success_count}/{total_count} profiles thực thi thành công.")
        return "\n".join(lines)

    # -------------------------------------------------------------------------
    # CALLBACK & MESSAGE HANDLERS
    # -------------------------------------------------------------------------
    def handle_callback(self, call: Any, bot: Any) -> None:
        chat_id = call.message.chat.id
        user_id = call.from_user.id
        data = call.data

        session = self.get_session_by_chat(chat_id)
        if not session and data != "qt:start":
            try:
                bot.answer_callback_query(call.id, "⚠️ Session đã hết hạn. Hãy bắt đầu lại với /quicktrade")
            except Exception:
                pass
            return

        if session and session.user_id != user_id:
            try:
                bot.answer_callback_query(call.id, "⚠️ Phiên làm việc thuộc về người dùng khác!")
            except Exception:
                pass
            return

        if data == "qt:cancel":
            self.cancel_session(chat_id, user_id)
            try:
                bot.answer_callback_query(call.id, "Đã hủy Quick Trade.")
                bot.edit_message_text(chat_id=chat_id, message_id=call.message.message_id, text="❌ *Đã hủy Quick Trade.*")
            except Exception:
                pass
            return

        if data == "qt:start":
            session = self.start_session(chat_id, user_id)

        assert session is not None
        session.touch()

        # STEP 1: SYMBOL SELECTION
        if data.startswith("qt:sym:"):
            symbol = data.split(":", 2)[2]
            ok, sym_clean, err = validate_symbol(symbol)
            if ok:
                session.symbol = sym_clean
                session.state = QuickTradeState.DIRECTION_SELECTION
                msg, kb = self.render_step_direction(session)
                bot.edit_message_text(chat_id=chat_id, message_id=call.message.message_id, text=msg, reply_markup=kb)
                bot.answer_callback_query(call.id, f"Symbol: {sym_clean}")
            else:
                bot.answer_callback_query(call.id, f"⚠️ {err}")
            return

        elif data == "qt:sym_input":
            session.state = QuickTradeState.SYMBOL_CUSTOM_INPUT
            bot.edit_message_text(
                chat_id=chat_id, message_id=call.message.message_id,
                text="✏️ *Vui lòng nhập Symbol vào chat (ví dụ: BTCUSD, XAUUSD):*"
            )
            bot.answer_callback_query(call.id, "Nhập symbol...")
            return

        # STEP 2: DIRECTION SELECTION
        elif data.startswith("qt:dir:"):
            direction = data.split(":", 2)[2].upper()
            if direction in ("BUY", "SELL"):
                session.direction = direction
                session.state = QuickTradeState.ENTRY_TIME_SELECTION
                msg, kb = self.render_step_entry_time(session)
                bot.edit_message_text(chat_id=chat_id, message_id=call.message.message_id, text=msg, reply_markup=kb)
                bot.answer_callback_query(call.id, f"Hướng: {direction}")
            return

        # STEP 3: ENTRY TIME SELECTION
        elif data.startswith("qt:time:"):
            t_str = data.split(":", 2)[2]
            ok, t_clean, err = validate_entry_time(t_str)
            if ok:
                session.entry_time = t_clean
                session.state = QuickTradeState.PROFILE_SELECTION
                msg, kb = self.render_step_profile_selection(session)
                bot.edit_message_text(chat_id=chat_id, message_id=call.message.message_id, text=msg, reply_markup=kb)
                bot.answer_callback_query(call.id, f"Entry: {t_clean}")
            else:
                bot.answer_callback_query(call.id, f"⚠️ {err}")
            return

        elif data == "qt:time_input":
            session.state = QuickTradeState.ENTRY_TIME_CUSTOM_INPUT
            bot.edit_message_text(
                chat_id=chat_id, message_id=call.message.message_id,
                text="✏️ *Vui lòng nhập giờ Entry vào chat (định dạng HH:MM broker clock, ví dụ 09:15):*"
            )
            bot.answer_callback_query(call.id, "Nhập giờ entry...")
            return

        # STEP 4: PROFILE SELECTION
        elif data.startswith("qt:prof_toggle:"):
            prof_name = data.split(":", 2)[2]
            if prof_name in session.selected_profiles:
                session.selected_profiles.remove(prof_name)
            else:
                session.selected_profiles.append(prof_name)
            msg, kb = self.render_step_profile_selection(session)
            bot.edit_message_text(chat_id=chat_id, message_id=call.message.message_id, text=msg, reply_markup=kb)
            bot.answer_callback_query(call.id, f"Profile: {prof_name}")
            return

        elif data == "qt:prof_next":
            if not session.selected_profiles:
                bot.answer_callback_query(call.id, "⚠️ Bạn phải chọn ít nhất 1 profile!")
                return
            # Initialize configs with default symbol
            for p in session.selected_profiles:
                if p not in session.profile_configs:
                    session.profile_configs[p] = {"symbol": session.symbol, "lot": None}
            session.state = QuickTradeState.PROFILE_SYMBOL_CONFIGURATION
            msg, kb = self.render_step_per_profile_symbol(session)
            bot.edit_message_text(chat_id=chat_id, message_id=call.message.message_id, text=msg, reply_markup=kb)
            bot.answer_callback_query(call.id, "Cấu hình symbol từng profile")
            return

        # STEP 5: PER-PROFILE SYMBOL
        elif data.startswith("qt:psym_edit:"):
            prof_name = data.split(":", 2)[2]
            session.editing_profile = prof_name
            session.state = QuickTradeState.PROFILE_SYMBOL_CUSTOM_INPUT
            bot.edit_message_text(
                chat_id=chat_id, message_id=call.message.message_id,
                text=f"✏️ *Nhập Symbol riêng cho [{prof_name}] vào chat (ví dụ: EURUSD, XAUUSD):*"
            )
            bot.answer_callback_query(call.id, f"Nhập symbol cho {prof_name}...")
            return

        elif data == "qt:psym_next":
            session.state = QuickTradeState.PROFILE_LOT_CONFIGURATION
            msg, kb = self.render_step_per_profile_lot(session)
            bot.edit_message_text(chat_id=chat_id, message_id=call.message.message_id, text=msg, reply_markup=kb)
            bot.answer_callback_query(call.id, "Cấu hình lot từng profile")
            return

        # STEP 6: PER-PROFILE LOT
        elif data.startswith("qt:plot_edit:"):
            prof_name = data.split(":", 2)[2]
            session.editing_profile = prof_name
            session.state = QuickTradeState.PROFILE_LOT_CUSTOM_INPUT
            bot.edit_message_text(
                chat_id=chat_id, message_id=call.message.message_id,
                text=f"✏️ *Nhập số Lot riêng cho [{prof_name}] vào chat (ví dụ: 0.01, 0.05):*"
            )
            bot.answer_callback_query(call.id, f"Nhập lot cho {prof_name}...")
            return

        elif data == "qt:plot_next":
            # Validate all profile lots
            missing_lots = [p for p in session.selected_profiles if session.profile_configs.get(p, {}).get("lot") is None]
            if missing_lots:
                bot.answer_callback_query(call.id, f"⚠️ Chưa nhập lot cho: {', '.join(missing_lots)}")
                return
            session.state = QuickTradeState.REVIEW
            msg, kb = self.render_step_review(session)
            bot.edit_message_text(chat_id=chat_id, message_id=call.message.message_id, text=msg, reply_markup=kb)
            bot.answer_callback_query(call.id, "Chuyển sang Review")
            return

        # STEP 7 -> PRECHECK -> EXECUTION -> RESULT
        elif data == "qt:confirm":
            if session.confirm_lock:
                bot.answer_callback_query(call.id, "⚠️ Lệnh đang được xử lý, không nhấn lặp lại!")
                return
            session.confirm_lock = True
            bot.answer_callback_query(call.id, "Đã xác nhận! Đang thực thi...")

            # Run Precheck
            self.run_precheck(session)
            pre_text = self.render_precheck_report(session)
            bot.edit_message_text(chat_id=chat_id, message_id=call.message.message_id, text=pre_text)

            # Run Execution
            self.execute_trade(session)
            res_text = self.render_execution_results(session)
            bot.send_message(chat_id=chat_id, text=res_text)

            # Clear session
            self.cancel_session(chat_id, user_id)
            return

    def handle_text_input(self, message: Any, bot: Any) -> bool:
        chat_id = message.chat.id
        user_id = message.from_user.id
        session = self.get_session(chat_id, user_id)

        if not session:
            return False

        txt = message.text.strip()

        if session.state == QuickTradeState.SYMBOL_CUSTOM_INPUT:
            ok, sym_clean, err = validate_symbol(txt)
            if not ok:
                bot.reply_to(message, f"❌ {err}")
                return True
            session.symbol = sym_clean
            session.state = QuickTradeState.DIRECTION_SELECTION
            msg, kb = self.render_step_direction(session)
            bot.send_message(chat_id=chat_id, text=msg, reply_markup=kb)
            return True

        elif session.state == QuickTradeState.ENTRY_TIME_CUSTOM_INPUT:
            ok, t_clean, err = validate_entry_time(txt)
            if not ok:
                bot.reply_to(message, f"❌ {err}")
                return True
            session.entry_time = t_clean
            session.state = QuickTradeState.PROFILE_SELECTION
            msg, kb = self.render_step_profile_selection(session)
            bot.send_message(chat_id=chat_id, text=msg, reply_markup=kb)
            return True

        elif session.state == QuickTradeState.PROFILE_SYMBOL_CUSTOM_INPUT:
            prof_name = session.editing_profile
            if not prof_name:
                return False
            ok, sym_clean, err = validate_symbol(txt)
            if not ok:
                bot.reply_to(message, f"❌ {err}")
                return True
            if prof_name not in session.profile_configs:
                session.profile_configs[prof_name] = {"symbol": sym_clean, "lot": None}
            else:
                session.profile_configs[prof_name]["symbol"] = sym_clean
            session.editing_profile = None
            session.state = QuickTradeState.PROFILE_SYMBOL_CONFIGURATION
            msg, kb = self.render_step_per_profile_symbol(session)
            bot.send_message(chat_id=chat_id, text=msg, reply_markup=kb)
            return True

        elif session.state == QuickTradeState.PROFILE_LOT_CUSTOM_INPUT:
            prof_name = session.editing_profile
            if not prof_name:
                return False
            ok, lot_clean, err = validate_lot(txt)
            if not ok:
                bot.reply_to(message, f"❌ {err}")
                return True
            if prof_name not in session.profile_configs:
                session.profile_configs[prof_name] = {"symbol": session.symbol, "lot": lot_clean}
            else:
                session.profile_configs[prof_name]["lot"] = lot_clean
            session.editing_profile = None
            session.state = QuickTradeState.PROFILE_LOT_CONFIGURATION
            msg, kb = self.render_step_per_profile_lot(session)
            bot.send_message(chat_id=chat_id, text=msg, reply_markup=kb)
            return True

        return False


# Global singleton instance
quick_trade_manager = QuickTradeManager()
