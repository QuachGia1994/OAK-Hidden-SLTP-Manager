# -*- coding: utf-8 -*-
"""Supervisor mode of oak-core — Phase 1 (Edit prompt.txt §9).

Phase 1 scope: Tauri shell + sidecar handshake + health + log streaming +
clean shutdown.  No business logic is moved here yet (acceptance #16:
"Không thay đổi business logic trong Phase 1"); profile workers, MT5
integration and the trade-audit stack arrive in later phases.
"""
from ..ipc.protocol import error_payload
from ..ipc.server import IpcServer
from ..version import APP_NAME, APP_VERSION, PROTOCOL_VERSION
from .profiles import ProfileManager
from .accounts import AccountQueries
from . import settings as settings_module
from . import orders as orders_module


class SupervisorApp:
    """Handles the Phase-1/2/3 control surface of the supervisor sidecar."""

    def __init__(self, *, server: IpcServer | None = None, started_at=None,
                 profile_manager: ProfileManager | None = None,
                 account_queries: AccountQueries | None = None):
        self._server = server if server is not None else IpcServer()
        from datetime import datetime, timezone
        self._started_at = started_at or datetime.now(timezone.utc).isoformat()
        self._healthy = True
        self._profiles = profile_manager if profile_manager is not None else ProfileManager()
        self._accounts = account_queries if account_queries is not None else AccountQueries()
        self._register()

    def _register(self) -> None:
        self._server.register("app.handshake", self._on_handshake)
        self._server.register("app.health", self._on_health)
        self._server.register("app.shutdown", self._on_shutdown)
        self._server.register("logs.tail", self._on_logs_tail)
        # Phase 2 — profile supervision (§9).
        self._server.register("profiles.list", self._on_profiles_list)
        self._server.register("profile.start", self._on_profile_start)
        self._server.register("profile.stop", self._on_profile_stop)
        self._server.register("profile.status", self._on_profile_status)
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
        return {
            "status": "ok" if self._healthy else "degraded",
            "uptime": self._started_at,
            "workers": list(self._profiles._workers.keys()),
            "protocol": PROTOCOL_VERSION,
        }

    def _on_shutdown(self, request) -> dict:
        self._healthy = False
        self._profiles.stop_all(timeout_seconds=5.0)
        self._server.request_shutdown()
        return {"ack": True}

    def _on_logs_tail(self, request) -> dict:
        lines = request.params.get("lines", 100)
        return {"lines": [], "truncated": False, "requested": int(lines)}

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
        return {"services": settings_module.services_list()}

    def _on_screener_list(self, request) -> dict:
        limit = int(request.params.get("limit", 10))
        return {"stocks": self._accounts.screener_list(limit=limit)}

    def _on_screener_update_eod(self, request) -> dict:
        target_date = str(request.params.get("date", ""))
        return self._accounts.update_eod(target_date=target_date)

    def _on_screener_run_filter(self, request) -> dict:
        # Phase 6: local-EOD ranking is handled by the worker; the desktop
        # triggers a refresh of the top list (mirrors Native Qt "Run advisor").
        limit = int(request.params.get("limit", 10))
        return {"stocks": self._accounts.screener_list(limit=limit)}

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

    # ------------------------------------------------------------------ #
    # Run
    # ------------------------------------------------------------------ #
    def run(self, *, max_lines: int | None = None) -> int:
        return self._server.run(max_lines=max_lines)
