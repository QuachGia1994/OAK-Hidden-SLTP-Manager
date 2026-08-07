# -*- coding: utf-8 -*-
"""Supervisor mode of oak-core — Phase 1 (Edit prompt.txt §9).

Phase 1 scope: Tauri shell + sidecar handshake + health + log streaming +
clean shutdown.  No business logic is moved here yet (acceptance #16:
"Không thay đổi business logic trong Phase 1"); profile workers, MT5
integration and the trade-audit stack arrive in later phases.
"""
import time

from ..ipc.protocol import error_payload
from ..ipc.server import IpcServer
from ..version import APP_NAME, APP_VERSION, PROTOCOL_VERSION
from .profiles import ProfileManager
from .accounts import AccountQueries
from .services import ServiceManager
from . import settings as settings_module
from . import orders as orders_module
from . import pending as pending_module
from . import diagnostics as diagnostics_module
from . import history as history_module
from . import news as news_module


def _monotonic_now() -> float:
    """Monotonic clock source — patchable in tests for deterministic uptime."""
    return time.monotonic()


def _format_uptime(elapsed_seconds: float) -> str:
    """Format an elapsed duration as ``HH:MM:SS`` or ``Nd HH:MM:SS``.

    Uses integer seconds so the value never drifts backwards and is immune
    to wall-clock adjustments.
    """
    total = int(elapsed_seconds)
    days, rem = divmod(total, 86400)
    hours, rem = divmod(rem, 3600)
    minutes, seconds = divmod(rem, 60)
    if days > 0:
        return f"{days}d {hours:02d}:{minutes:02d}:{seconds:02d}"
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}"


class SupervisorApp:
    """Handles the Phase-1/2/3 control surface of the supervisor sidecar."""

    def __init__(self, *, server: IpcServer | None = None, started_at=None,
                 profile_manager: ProfileManager | None = None,
                 account_queries: AccountQueries | None = None,
                 services: "ServiceManager" | None = None):
        self._server = server if server is not None else IpcServer()
        from datetime import datetime, timezone
        self._started_at = started_at or datetime.now(timezone.utc).isoformat()
        self._monotonic_start = _monotonic_now()
        self._healthy = True
        self._profiles = profile_manager if profile_manager is not None else ProfileManager()
        self._accounts = account_queries if account_queries is not None else AccountQueries(emit_event=self._server.emit_event)
        self._services = services if services is not None else ServiceManager(emit_event=self._server.emit_event)
        self._register()

    def _register(self) -> None:
        self._server.register("app.handshake", self._on_handshake)
        self._server.register("app.health", self._on_health)
        self._server.register("app.shutdown", self._on_shutdown)
        self._server.register("logs.tail", self._on_logs_tail)
        self._server.register("diagnostics.summary", self._on_diagnostics_summary)
        self._server.register("diagnostics.export_bundle", self._on_diagnostics_export_bundle)
        # Phase 2 — profile supervision (§9).
        self._server.register("profiles.list", self._on_profiles_list)
        self._server.register("profile.start", self._on_profile_start)
        self._server.register("profile.stop", self._on_profile_stop)
        self._server.register("profile.status", self._on_profile_status)
        self._server.register("profile.add", self._on_profile_add)
        self._server.register("profile.update", self._on_profile_update)
        self._server.register("profile.duplicate", self._on_profile_duplicate)
        self._server.register("profile.delete", self._on_profile_delete)
        # Telegram bot token — write-only; the value never crosses back.
        self._server.register("profile.secrets.status", self._on_profile_secret_status)
        self._server.register("profile.secrets.set_token", self._on_profile_secret_set_token)
        self._server.register("profile.secrets.clear_token", self._on_profile_secret_clear_token)
        # Phase 3 — account audit queries (§9).
        self._server.register("account.get", self._on_account_get)
        self._server.register("positions.list", self._on_positions_list)
        self._server.register("deals.list", self._on_deals_list)
        self._server.register("checkpoints.list", self._on_checkpoints_list)
        self._server.register("performance.summary", self._on_performance_summary)
        # Phase 4 — equity curve / drawdown / risk (§9).
        self._server.register("performance.equity_curve", self._on_equity_curve)
        self._server.register("performance.drawdown_curve", self._on_drawdown_curve)
        self._server.register("risk.summary", self._on_risk_summary)
        # Phase 5 — hidden SL/TP + copy trading config (§9).
        self._server.register("hidden_sltp.get", self._on_hidden_sltp_get)
        self._server.register("hidden_sltp.update", self._on_hidden_sltp_update)
        self._server.register("copy.get", self._on_copy_get)
        self._server.register("copy.update", self._on_copy_update)
        # Phase 6 — settings + services (§9).
        self._server.register("settings.get", self._on_settings_get)
        self._server.register("settings.update", self._on_settings_update)
        self._server.register("services.list", self._on_services_list)
        self._server.register("service.start", self._on_service_start)
        self._server.register("service.stop", self._on_service_stop)
        self._server.register("service.status", self._on_service_status)
        # Phase 6 — stock screener (local EOD).
        self._server.register("screener.list", self._on_screener_list)
        self._server.register("screener.update_eod", self._on_screener_update_eod)
        self._server.register("screener.run_filter", self._on_screener_run_filter)
        # Phase 4/5 — order management (pending / scheduled / close).
        self._server.register("orders.summary", self._on_orders_summary)
        self._server.register("orders.add_scheduled_trade", self._on_add_scheduled_trade)
        self._server.register("orders.delete_scheduled_trade", self._on_delete_scheduled_trade)
        self._server.register("orders.add_scheduled_close", self._on_add_scheduled_close)
        self._server.register("orders.delete_scheduled_close", self._on_delete_scheduled_close)
        self._server.register("orders.clear_scheduled_closes", self._on_clear_scheduled_closes)
        self._server.register("pending.summary", self._on_pending_summary)
        self._server.register("pending.item.delete", self._on_pending_item_delete)
        self._server.register("pending.clear_done", self._on_pending_clear_done)
        # Read-only local history + published rule contract (website parity).
        # Account-scoped trade history stays on ``deals.list``.
        self._server.register("history.signals", self._on_history_signals)
        self._server.register("rules.today", self._on_rules_today)
        # Read-only local economic-news cache (no fetch, no Redis, no API key).
        self._server.register("news.local", self._on_news_local)

    # ------------------------------------------------------------------ #
    # Handlers (return dict -> ok response; raise -> error response)
    # ------------------------------------------------------------------ #
    def _on_handshake(self, request) -> dict:
        return {
            "app": APP_NAME,
            "version": APP_VERSION,
            "protocol": PROTOCOL_VERSION,
            "role": "supervisor",
            "started_at": self._started_at,
        }

    def _on_health(self, request) -> dict:
        elapsed = _monotonic_now() - self._monotonic_start
        return {
            "status": "ok" if self._healthy else "degraded",
            "uptime": _format_uptime(elapsed),
            "workers": self._profiles.running_workers(),
            "protocol": PROTOCOL_VERSION,
        }

    def _on_shutdown(self, request) -> dict:
        self._healthy = False
        self._profiles.stop_all(timeout_seconds=5.0)
        self._services.stop_all(timeout_seconds=5.0)
        self._server.request_shutdown()
        return {"ack": True}

    def _on_logs_tail(self, request) -> dict:
        lines = request.params.get("lines", 100)
        return diagnostics_module.tail(
            lines=int(lines),
            query=str(request.params.get("query") or ""),
            level=str(request.params.get("level") or "ALL"),
        )

    def _on_diagnostics_summary(self, request) -> dict:
        return diagnostics_module.summary(
            selected=str(request.params.get("profile") or ""),
            query=str(request.params.get("query") or ""),
            level=str(request.params.get("level") or "ALL"),
        )

    def _on_diagnostics_export_bundle(self, request) -> dict:
        return diagnostics_module.export_bundle()

    # ------------------------------------------------------------------ #
    # Phase 2 — profile handlers
    # ------------------------------------------------------------------ #
    def _on_profiles_list(self, request) -> dict:
        return self._profiles.list_profiles()

    def _on_profile_start(self, request) -> dict:
        name = str(request.params.get("profile") or "")
        if not name:
            raise ValueError("profile param required")
        return self._profiles.start_profile(name)

    def _on_profile_stop(self, request) -> dict:
        name = str(request.params.get("profile") or "")
        if not name:
            raise ValueError("profile param required")
        return self._profiles.stop_profile(name)

    def _on_profile_status(self, request) -> dict:
        name = str(request.params.get("profile") or "")
        if not name:
            raise ValueError("profile param required")
        return self._profiles.profile_status(name)

    def _on_profile_add(self, request) -> dict:
        name = str(request.params.get("profile_name") or "").strip()
        if not name:
            raise ValueError("profile_name param required")
        path = str(request.params.get("path") or "")
        magic = request.params.get("magic", -1)
        return self._profiles.add_profile(name, path=path, magic=magic)

    def _on_profile_update(self, request) -> dict:
        name = str(request.params.get("profile") or "")
        updates = request.params.get("updates") or {}
        if not name:
            raise ValueError("profile param required")
        if not isinstance(updates, dict):
            raise ValueError("updates must be an object")
        return self._profiles.update_profile(name, updates)

    def _on_profile_duplicate(self, request) -> dict:
        name = str(request.params.get("profile") or "")
        new_name = str(request.params.get("new_name") or "")
        if not name:
            raise ValueError("profile param required")
        return self._profiles.duplicate_profile(name, new_name)

    def _on_profile_delete(self, request) -> dict:
        name = str(request.params.get("profile") or "")
        if not name:
            raise ValueError("profile param required")
        return self._profiles.delete_profile(name)

    def _on_profile_secret_status(self, request) -> dict:
        name = str(request.params.get("profile") or "")
        if not name:
            raise ValueError("profile param required")
        return self._profiles.secret_status(name)

    def _on_profile_secret_set_token(self, request) -> dict:
        name = str(request.params.get("profile") or "")
        token = str(request.params.get("token") or "")
        if not name:
            raise ValueError("profile param required")
        if not token.strip():
            raise ValueError("token param required")
        return self._profiles.set_tele_token(name, token)

    def _on_profile_secret_clear_token(self, request) -> dict:
        name = str(request.params.get("profile") or "")
        if not name:
            raise ValueError("profile param required")
        return self._profiles.clear_tele_token(name)

    # ------------------------------------------------------------------ #
    # Phase 3 — account audit handlers
    # ------------------------------------------------------------------ #
    def _on_account_get(self, request) -> dict:
        profile = str(request.params.get("profile") or "")
        if not profile:
            raise ValueError("profile param required")
        return self._accounts.account_get(profile)

    def _on_positions_list(self, request) -> dict:
        profile = str(request.params.get("profile") or "")
        if not profile:
            raise ValueError("profile param required")
        return {"positions": self._accounts.positions_list(profile)}

    def _on_deals_list(self, request) -> dict:
        profile = str(request.params.get("profile") or "")
        limit = int(request.params.get("limit", 200))
        if not profile:
            raise ValueError("profile param required")
        return {"deals": self._accounts.deals_list(profile, limit=limit)}

    def _on_checkpoints_list(self, request) -> dict:
        profile = str(request.params.get("profile") or "")
        limit = int(request.params.get("limit", 30))
        if not profile:
            raise ValueError("profile param required")
        return {"checkpoints": self._accounts.checkpoints_list(profile, limit=limit)}

    def _on_performance_summary(self, request) -> dict:
        profile = str(request.params.get("profile") or "")
        if not profile:
            raise ValueError("profile param required")
        return self._accounts.performance_summary(profile)

    def _on_equity_curve(self, request) -> dict:
        profile = str(request.params.get("profile") or "")
        limit = int(request.params.get("limit", 500))
        if not profile:
            raise ValueError("profile param required")
        return {"curve": self._accounts.equity_curve(profile, limit=limit)}

    def _on_drawdown_curve(self, request) -> dict:
        profile = str(request.params.get("profile") or "")
        limit = int(request.params.get("limit", 500))
        if not profile:
            raise ValueError("profile param required")
        return {"curve": self._accounts.drawdown_curve(profile, limit=limit)}

    def _on_risk_summary(self, request) -> dict:
        profile = str(request.params.get("profile") or "")
        if not profile:
            raise ValueError("profile param required")
        return self._accounts.risk_summary(profile)

    # ------------------------------------------------------------------ #
    # Phase 5 — hidden SL/TP + copy trading config
    # ------------------------------------------------------------------ #
    def _on_hidden_sltp_get(self, request) -> dict:
        profile = str(request.params.get("profile") or "")
        if not profile:
            raise ValueError("profile param required")
        return self._profiles.read_sltp(profile)

    def _on_hidden_sltp_update(self, request) -> dict:
        profile = str(request.params.get("profile") or "")
        updates = request.params.get("updates") or {}
        if not profile:
            raise ValueError("profile param required")
        return self._profiles.update_sltp(profile, updates)

    def _on_copy_get(self, request) -> dict:
        profile = str(request.params.get("profile") or "")
        if not profile:
            raise ValueError("profile param required")
        return self._profiles.read_copy(profile)

    def _on_copy_update(self, request) -> dict:
        profile = str(request.params.get("profile") or "")
        updates = request.params.get("updates") or {}
        if not profile:
            raise ValueError("profile param required")
        return self._profiles.update_copy(profile, updates)

    # ------------------------------------------------------------------ #
    # Phase 6 — settings + services
    # ------------------------------------------------------------------ #
    def _on_settings_get(self, request) -> dict:
        return settings_module.public_settings()

    def _on_settings_update(self, request) -> dict:
        updates = request.params.get("updates") or {}
        return settings_module.update_settings(updates)

    def _on_services_list(self, request) -> dict:
        return self._services.list_services()

    def _on_service_start(self, request) -> dict:
        service = str(request.params.get("service") or "")
        profile = str(request.params.get("profile") or "")
        confirm = bool(request.params.get("confirm", False))
        return self._services.start_service(service, profile=profile, confirm=confirm)

    def _on_service_stop(self, request) -> dict:
        service = str(request.params.get("service") or "")
        return self._services.stop_service(service)

    def _on_service_status(self, request) -> dict:
        service = str(request.params.get("service") or "")
        return self._services.service_status(service)

    def _on_screener_list(self, request) -> dict:
        limit = int(request.params.get("limit", 10))
        return {"stocks": self._accounts.screener_list(limit=limit)}

    def _on_screener_update_eod(self, request) -> dict:
        target_date = str(request.params.get("date", ""))
        return self._accounts.update_eod(target_date=target_date)

    def _on_screener_run_filter(self, request) -> dict:
        limit = int(request.params.get("limit", 10))
        return self._accounts.run_filter(limit=limit)

    # ------------------------------------------------------------------ #
    # Order management (pending / scheduled / close)
    # ------------------------------------------------------------------ #
    def _on_orders_summary(self, request) -> dict:
        return orders_module.orders_summary()

    def _on_add_scheduled_trade(self, request) -> dict:
        p = request.params
        for key in ("symbol", "order_type", "lot", "time", "date"):
            if key not in p:
                raise ValueError(f"{key} param required")
        return orders_module.add_scheduled_trade(
            symbol=p["symbol"], order_type=int(p["order_type"]), lot=str(p["lot"]),
            time=str(p["time"]), date=str(p["date"]),
            sl=str(p.get("sl", "0")), tp=str(p.get("tp", "0")),
        )

    def _on_delete_scheduled_trade(self, request) -> dict:
        trade_id = request.params.get("id")
        if trade_id is None:
            raise ValueError("id param required")
        return orders_module.delete_scheduled_trade(int(trade_id))

    def _on_add_scheduled_close(self, request) -> dict:
        p = request.params
        if "time" not in p or "date" not in p:
            raise ValueError("time/date params required")
        return orders_module.add_scheduled_close(
            time=str(p["time"]), date=str(p["date"]),
            filter=str(p.get("filter", "all")), sym=str(p.get("sym", "")),
        )

    def _on_delete_scheduled_close(self, request) -> dict:
        rowid = request.params.get("id")
        if rowid is None:
            raise ValueError("id param required")
        return orders_module.delete_scheduled_close(int(rowid))

    def _on_clear_scheduled_closes(self, request) -> dict:
        return orders_module.clear_scheduled_closes()

    def _on_pending_summary(self, request) -> dict:
        profile = str(request.params.get("profile") or "")
        if not profile:
            raise ValueError("profile param required")
        return pending_module.summary(profile)

    def _on_pending_item_delete(self, request) -> dict:
        profile = str(request.params.get("profile") or "")
        item_id = str(request.params.get("item_id") or "")
        if not profile or not item_id:
            raise ValueError("profile and item_id params required")
        return pending_module.delete_item(profile, item_id)

    def _on_pending_clear_done(self, request) -> dict:
        profile = str(request.params.get("profile") or "")
        if not profile:
            raise ValueError("profile param required")
        return pending_module.clear_done(profile)

    # ------------------------------------------------------------------ #
    # Read-only history + rule contract
    # ------------------------------------------------------------------ #
    def _on_history_signals(self, request) -> dict:
        # The limit is clamped inside the module (1..MAX_RECORDS).
        return history_module.signal_history(
            limit=request.params.get("limit", history_module.DEFAULT_LIMIT),
        )

    def _on_rules_today(self, request) -> dict:
        return history_module.today_rules(locale=request.params.get("locale", "VN"))

    def _on_news_local(self, request) -> dict:
        # Locale is the only input; the cache path is resolved internally.
        return news_module.local_news(locale=request.params.get("locale", "VN"))

    # ------------------------------------------------------------------ #
    # Run
    # ------------------------------------------------------------------ #
    def run(self, *, max_lines: int | None = None) -> int:
        return self._server.run(max_lines=max_lines)
