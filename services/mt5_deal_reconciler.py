# -*- coding: utf-8 -*-
"""MT5 deal reconciler for the OAK trade audit ledger.

Every checkpoint and every startup calls history_deals_get(last_reconciled_utc, now_utc)
and upserts deals by unique(account_id, deal_ticket). Idempotent.

CRITICAL: close reason is mapped ONLY from the MT5 deal reason enum. It is never
inferred from profit/loss (a losing trade is NOT assumed to be an SL, a winning
trade is NOT assumed to be a TP).
"""
from datetime import datetime, timedelta, timezone

from oak_logger import setup_logger

log = setup_logger("mt5_deal_reconciler")

# MT5 DEAL_REASON_* enum values.
DEAL_REASON_CLIENT = 4        # manual (desktop)
DEAL_REASON_MOBILE = 12
DEAL_REASON_WEB = 13
DEAL_REASON_EXPERT = 7
DEAL_REASON_SL = 1
DEAL_REASON_TP = 2
DEAL_REASON_SO = 3

DEAL_REASON_NAMES = {
    DEAL_REASON_SL: "CLOSED_SL",
    DEAL_REASON_TP: "CLOSED_TP",
    DEAL_REASON_SO: "CLOSED_STOP_OUT",
    DEAL_REASON_CLIENT: "CLOSED_MANUAL_DESKTOP",
    DEAL_REASON_MOBILE: "CLOSED_MANUAL_MOBILE",
    DEAL_REASON_WEB: "CLOSED_MANUAL_WEB",
    DEAL_REASON_EXPERT: "CLOSED_EXPERT",
}

# DEAL_ENTRY_* enum values (MT5).
DEAL_ENTRY_IN = 0
DEAL_ENTRY_OUT = 1
DEAL_ENTRY_INOUT = 2
DEAL_ENTRY_OUT_BY = 3
DEAL_ENTRY_CLOSEBY = 4

DEAL_ENTRY_NAMES = {
    DEAL_ENTRY_IN: "IN",
    DEAL_ENTRY_OUT: "OUT",
    DEAL_ENTRY_INOUT: "INOUT",
    DEAL_ENTRY_OUT_BY: "OUT_BY",
    DEAL_ENTRY_CLOSEBY: "CLOSEBY",
}

# MT5 DEAL_TYPE_* enum values (names only, mapped defensively).
DEAL_TYPE_NAMES = {
    0: "BUY",
    1: "SELL",
    2: "BALANCE",
    3: "CREDIT",
    4: "CHARGES",
    5: "CORRECTION",
    6: "BONUS",
    7: "COMMISSION",
    8: "COMMISSION_DAILY",
    9: "COMMISSION_MONTHLY",
    10: "COMMISSION_AGENT_DAILY",
    11: "COMMISSION_AGENT_MONTHLY",
    12: "INTEREST",
    13: "BUY_CANCELED",
    14: "SELL_CANCELED",
    15: "DIVIDEND",
    16: "DIVIDEND_TAX",
    17: "FEE",
    18: "REBATE",
}

# Settings keys persisted in trade_audit.db app_settings.
_CURSOR_KEY_PREFIX = "reconciler.last_reconciled_utc."


def classify_reason(reason_int):
    """Map an MT5 deal reason int to a CLOSED_* category.

    Returns None for non-close reasons (e.g. entry deals with no close reason)
    or unknown ints (mapped to CLOSED_UNKNOWN only when it is a genuine close).
    """
    if reason_int in DEAL_REASON_NAMES:
        return DEAL_REASON_NAMES[reason_int]
    return None


class MT5DealReconciler:
    """Reconciles MT5 deal history into the append-only trade ledger."""

    def __init__(self, store, mt5_module, default_window_days=7):
        self.store = store
        self.mt5 = mt5_module
        self.default_window_days = default_window_days

    # ------------------------------------------------------------------ #
    # Cursor persistence
    # ------------------------------------------------------------------ #
    def _cursor_key(self, account_uid):
        return f"{_CURSOR_KEY_PREFIX}{account_uid}"

    def get_last_reconciled_utc(self, account_uid):
        raw = self.store.get_setting(self._cursor_key(account_uid))
        if not raw:
            return None
        try:
            return datetime.fromisoformat(raw)
        except (TypeError, ValueError):
            return None

    def _set_last_reconciled_utc(self, account_uid, dt):
        self.store.set_setting(self._cursor_key(account_uid), dt.isoformat())

    # ------------------------------------------------------------------ #
    # Core reconciliation
    # ------------------------------------------------------------------ #
    def reconcile(self, account_uid, account_info, now_utc=None,
                  profile_name="", broker="", currency=""):
        """Upsert all deals in [last_reconciled_utc, now_utc].

        - account_uid: stable identity, e.g. f"{login}@{server}".
        - account_info: dict-like with login/server (used only to upsert the account row).
        - Returns {"account_id": int, "deals_upserted": int, "window_start": iso|None,
                   "window_end": iso, "restart_recovery": bool}.
        """
        if now_utc is None:
            now_utc = datetime.now(timezone.utc)

        account_id = self.store.upsert_account(
            account_uid=account_uid,
            profile_name=profile_name,
            broker=broker,
            server=(account_info or {}).get("server", ""),
            currency=currency,
            account_type=(account_info or {}).get("account_type", ""),
        )

        last = self.get_last_reconciled_utc(account_uid)
        restart_recovery = last is None
        if last is None:
            last = now_utc - timedelta(days=self.default_window_days)

        window_start = last.replace(tzinfo=timezone.utc) if last.tzinfo is None else last

        deals = self._fetch_deals(window_start, now_utc)
        upserted = 0
        if deals:
            for deal in deals:
                normalized = self._normalize_deal(account_id, deal)
                if normalized is not None:
                    self.store.upsert_deal(account_id, normalized)
                    upserted += 1

        self._set_last_reconciled_utc(account_uid, now_utc)
        log.info(
            "Reconciled deals for %s: %d upserted (window %s -> %s)",
            account_uid, upserted, window_start.isoformat(), now_utc.isoformat(),
        )
        return {
            "account_id": account_id,
            "deals_upserted": upserted,
            "window_start": window_start.isoformat(),
            "window_end": now_utc.isoformat(),
            "restart_recovery": restart_recovery,
        }

    def _fetch_deals(self, from_dt, to_dt):
        """Call mt5.history_deals_get; tolerate None/empty/exception."""
        try:
            deals = self.mt5.history_deals_get(from_dt, to_dt)
        except Exception as exc:  # pragma: no cover - defensive against broker API
            log.warning("history_deals_get raised: %s", exc)
            return []
        if not deals:
            return []
        return deals

    # ------------------------------------------------------------------ #
    # Normalization
    # ------------------------------------------------------------------ #
    def _normalize_deal(self, account_id, deal):
        """Convert an MT5 deal object (or dict) into a store row dict.

        Returns None for balance/credit/correction deals that have no ticket.
        """
        try:
            ticket = getattr(deal, "ticket", None)
            if ticket is None and isinstance(deal, dict):
                ticket = deal.get("ticket")
            if ticket is None:
                return None
            reason_raw_int = _deal_attr(deal, "reason")
            reason_category = classify_reason(reason_raw_int)
            # Never assign a CLOSED_* category to an entry deal.
            entry_int = _deal_attr(deal, "entry")
            if entry_int is not None and entry_int in (DEAL_ENTRY_IN,):
                reason_category = None
            deal_type_int = _deal_attr(deal, "type")
            return {
                "account_id": account_id,
                "deal_ticket": str(ticket),
                "position_id": str(_deal_attr(deal, "position_id") or ""),
                "order_ticket": str(_deal_attr(deal, "order") or ""),
                "symbol": _deal_attr(deal, "symbol") or "",
                "deal_type": DEAL_TYPE_NAMES.get(deal_type_int, f"TYPE_{deal_type_int}" if deal_type_int is not None else ""),
                "entry_type": DEAL_ENTRY_NAMES.get(entry_int, ""),
                "reason_raw": _reason_raw_str(deal),
                "reason_category": reason_category or "",
                "volume": _deal_attr(deal, "volume"),
                "price": _deal_attr(deal, "price"),
                "profit": _deal_attr(deal, "profit"),
                "commission": _deal_attr(deal, "commission") or 0,
                "swap": _deal_attr(deal, "swap") or 0,
                "fee": _deal_attr(deal, "fee") or 0,
                "deal_time_utc": _deal_time_utc(deal),
                "deal_time_broker": _deal_attr(deal, "time") or "",
                "magic": str(_deal_attr(deal, "magic") or ""),
                "comment": _deal_attr(deal, "comment") or "",
            }
        except Exception as exc:  # pragma: no cover - never break reconciliation
            log.warning("Skipping malformed deal: %s", exc)
            return None


def _deal_attr(deal, name):
    """Read an attribute from an MT5 namedtuple deal or a dict."""
    if isinstance(deal, dict):
        return deal.get(name)
    return getattr(deal, name, None)


def _deal_time_utc(deal):
    """MT5 'time' is a unix timestamp in the broker's local timezone? No —
    MT5 deal time is a unix epoch (UTC). Keep both raw int and ISO UTC."""
    raw = _deal_attr(deal, "time")
    if raw is None:
        return None
    try:
        return datetime.fromtimestamp(int(raw), tz=timezone.utc).isoformat()
    except (TypeError, ValueError, OSError):
        return None


def _reason_raw_str(deal):
    """Persist the raw enum as 'int:NAME' plus any available name."""
    raw_int = _deal_attr(deal, "reason")
    name = None
    if raw_int is not None and isinstance(deal, dict):
        name = deal.get("reason_name") or deal.get("reason_description")
    if raw_int is None:
        return ""
    if name is None:
        name = DEAL_REASON_NAMES.get(int(raw_int), "DEAL_REASON_UNKNOWN")
    return f"{int(raw_int)}:{name}"
