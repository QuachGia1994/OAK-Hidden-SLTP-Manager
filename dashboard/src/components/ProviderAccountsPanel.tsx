"use client";

import { FormEvent, useCallback, useEffect, useState } from "react";

type Provider = "ctrader" | "mt5";
type Account = {
  id: string;
  provider: Provider;
  broker: string;
  environment: "live" | "demo";
  externalAccountId: string;
  traderLogin: number | null;
  label: string;
  enabled: boolean;
  isDefault: boolean;
  connectionMode: "oauth" | "bridge";
  bridgeProfile: string | null;
  fxSlPoints: number;
  fxTpPoints: number;
  goldSlPoints: number;
  goldTpPoints: number;
  bridgeOnline?: boolean;
  bridgeLastSeenAt?: number | null;
};

type AccountPayload = {
  ok: boolean;
  providers: {
    ctrader: { connected: boolean; scope: "accounts" | "trading" | null };
    mt5: { connected: boolean; mode: "outbound-bridge" };
  };
  defaultAccountId: string;
  accounts: Account[];
};

export function ProviderAccountsPanel() {
  const [state, setState] = useState<"loading" | "locked" | "ready">("loading");
  const [payload, setPayload] = useState<AccountPayload | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState("");

  const load = useCallback(async () => {
    const response = await fetch("/api/accounts", { cache: "no-store" });
    if (response.status === 401) {
      setState("locked");
      return;
    }
    const body = await response.json().catch(() => null) as AccountPayload | { error?: string } | null;
    if (!response.ok || !body || !("accounts" in body)) throw new Error((body && "error" in body && body.error) || "Cannot load provider accounts");
    setPayload(body);
    setState("ready");
  }, []);

  useEffect(() => {
    load().catch((reason) => {
      setError(reason instanceof Error ? reason.message : String(reason));
      setState("locked");
    });
  }, [load]);

  async function login(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    setBusy("login");
    setError("");
    try {
      const response = await fetch("/api/admin/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ apiKey: String(form.get("apiKey") || "") }),
      });
      if (!response.ok) throw new Error("Admin key không đúng");
      await load();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : String(reason));
    } finally {
      setBusy("");
    }
  }

  async function connectCTrader() {
    setBusy("connect-ctrader");
    setError("");
    try {
      const response = await fetch("/api/ctrader/oauth", { method: "POST" });
      const body = await response.json().catch(() => null) as { authorizeUrl?: string; error?: string } | null;
      if (!response.ok || !body?.authorizeUrl) throw new Error(body?.error || "Cannot start cTrader OAuth");
      window.location.assign(body.authorizeUrl);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : String(reason));
      setBusy("");
    }
  }

  async function syncCTrader() {
    setBusy("sync-ctrader");
    setError("");
    try {
      const response = await fetch("/api/accounts", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ action: "sync-ctrader" }),
      });
      const body = await response.json().catch(() => null) as AccountPayload | { error?: string } | null;
      if (!response.ok || !body || !("accounts" in body)) throw new Error((body && "error" in body && body.error) || "cTrader sync failed");
      setPayload(body);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : String(reason));
    } finally {
      setBusy("");
    }
  }

  async function createMt5(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const formElement = event.currentTarget;
    const form = new FormData(formElement);
    setBusy("create-mt5");
    setError("");
    try {
      const response = await fetch("/api/accounts", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          action: "create-mt5",
          broker: String(form.get("broker") || ""),
          environment: String(form.get("environment") || "live"),
          login: Number(form.get("login")),
          label: String(form.get("label") || ""),
          bridgeProfile: String(form.get("bridgeProfile") || ""),
        }),
      });
      const body = await response.json().catch(() => null) as { payload?: AccountPayload; error?: string } | null;
      if (!response.ok || !body?.payload) throw new Error(body?.error || "Cannot register MT5 account");
      setPayload(body.payload);
      formElement.reset();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : String(reason));
    } finally {
      setBusy("");
    }
  }

  async function saveAccount(event: FormEvent<HTMLFormElement>, account: Account) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    setBusy(account.id);
    setError("");
    try {
      const response = await fetch("/api/accounts", {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          id: account.id,
          label: String(form.get("label") || ""),
          enabled: form.get("enabled") === "on",
          makeDefault: form.get("makeDefault") === "on",
          bridgeProfile: account.provider === "mt5" ? String(form.get("bridgeProfile") || "") : undefined,
          fxSlPoints: Number(form.get("fxSlPoints")),
          fxTpPoints: Number(form.get("fxTpPoints")),
          goldSlPoints: Number(form.get("goldSlPoints")),
          goldTpPoints: Number(form.get("goldTpPoints")),
        }),
      });
      const body = await response.json().catch(() => null) as { payload?: AccountPayload; error?: string } | null;
      if (!response.ok || !body?.payload) throw new Error(body?.error || "Save failed");
      setPayload(body.payload);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : String(reason));
    } finally {
      setBusy("");
    }
  }

  async function removeMt5(account: Account) {
    if (account.provider !== "mt5") return;
    if (!window.confirm(`Xóa metadata MT5 ${account.label}?`)) return;
    setBusy(`delete:${account.id}`);
    setError("");
    try {
      const response = await fetch(`/api/accounts?id=${encodeURIComponent(account.id)}`, { method: "DELETE" });
      const body = await response.json().catch(() => null) as { payload?: AccountPayload; error?: string } | null;
      if (!response.ok || !body?.payload) throw new Error(body?.error || "Delete failed");
      setPayload(body.payload);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : String(reason));
    } finally {
      setBusy("");
    }
  }

  if (state === "loading") return <section className="oak-account-panel"><p>Loading provider accounts…</p></section>;
  if (state === "locked") {
    return (
      <section className="oak-account-panel oak-account-login">
        <header><small>ADMIN</small><h1>Provider Account Manager</h1><p>Đăng nhập bằng Dashboard API key. Session lưu HttpOnly 12 giờ; broker secret/token không được đưa vào browser.</p></header>
        <form onSubmit={login}>
          <label htmlFor="admin-api-key">Dashboard API key</label>
          <input id="admin-api-key" name="apiKey" type="password" autoComplete="current-password" required />
          <button type="submit" disabled={busy === "login"}>{busy === "login" ? "Signing in…" : "Sign in"}</button>
        </form>
        {error && <p className="oak-account-error">{error}</p>}
      </section>
    );
  }

  const accounts = payload?.accounts || [];
  const enabled = accounts.filter((item) => item.enabled).length;
  return (
    <section className="oak-account-panel">
      <header className="oak-account-head">
        <div><small>CLOUD / MULTI-PROVIDER</small><h1>Provider Account Manager</h1><p>cTrader dùng OAuth server-side. MT5 dùng outbound bridge từ worker đang giữ terminal/profile; password vẫn ở local và không được đưa vào browser hay public payload.</p></div>
        <div className="oak-account-actions">
          <button type="button" onClick={connectCTrader} disabled={Boolean(busy)}>{payload?.providers.ctrader.connected ? "Reconnect cTrader" : "Connect cTrader"}</button>
          <button type="button" onClick={syncCTrader} disabled={Boolean(busy) || !payload?.providers.ctrader.connected}>{busy === "sync-ctrader" ? "Syncing…" : "Sync cTrader"}</button>
        </div>
      </header>

      <div className="oak-account-status">
        <span>cTrader <b>{payload?.providers.ctrader.connected ? "CONNECTED" : "OFF"}</b></span>
        <span>Scope <b>{payload?.providers.ctrader.scope || "—"}</b></span>
        <span>MT5 <b>{payload?.providers.mt5.connected ? "BRIDGE ONLINE" : "BRIDGE OFFLINE"}</b></span>
        <span>Enabled <b>{enabled}/{accounts.length}</b></span>
      </div>

      {error && <p className="oak-account-error">{error}</p>}

      <form className="oak-account-card" onSubmit={createMt5}>
        <header><div><b>Add MT5 account</b><span>Metadata only · no broker password stored</span></div></header>
        <div className="oak-account-fields">
          <label>Broker<input name="broker" placeholder="Vantage / ICMarkets / Darwinex" required /></label>
          <label>Login<input name="login" type="number" min="1" step="1" required /></label>
          <label>Environment<select name="environment" defaultValue="live"><option value="live">LIVE</option><option value="demo">DEMO</option></select></label>
          <label>Label<input name="label" placeholder="Main Vantage" /></label>
          <label>Bridge profile<input name="bridgeProfile" placeholder="Vantage" /></label>
        </div>
        <footer><button type="submit" disabled={busy === "create-mt5"}>{busy === "create-mt5" ? "Adding…" : "Add MT5 account"}</button></footer>
      </form>

      <div className="oak-account-list">
        {accounts.map((account) => (
          <form key={account.id} className="oak-account-card" onSubmit={(event) => saveAccount(event, account)}>
            <header>
              <div><b>{account.label}</b><span>{account.provider.toUpperCase()} · {account.broker} · {account.environment.toUpperCase()} · #{account.externalAccountId}{account.provider === "mt5" ? ` · ${account.bridgeOnline ? "BRIDGE ONLINE" : "BRIDGE OFFLINE"}` : ""}</span></div>
              <label><input name="enabled" type="checkbox" defaultChecked={account.enabled} /> Enable control</label>
            </header>
            <div className="oak-account-fields">
              <label>Account label<input name="label" defaultValue={account.label} /></label>
              {account.provider === "mt5" && <label>Bridge profile<input name="bridgeProfile" defaultValue={account.bridgeProfile || ""} placeholder="Vantage" /></label>}
              <label>FX SL points<input name="fxSlPoints" type="number" min="1" step="1" defaultValue={account.fxSlPoints} /></label>
              <label>FX TP points<input name="fxTpPoints" type="number" min="1" step="1" defaultValue={account.fxTpPoints} /></label>
              <label>Gold SL points<input name="goldSlPoints" type="number" min="1" step="1" defaultValue={account.goldSlPoints} /></label>
              <label>Gold TP points<input name="goldTpPoints" type="number" min="1" step="1" defaultValue={account.goldTpPoints} /></label>
              <label><input name="makeDefault" type="checkbox" defaultChecked={account.isDefault} disabled={!account.enabled} /> Default account</label>
            </div>
            <footer>
              <button type="submit" disabled={busy === account.id}>{busy === account.id ? "Saving…" : "Save account"}</button>
              {account.provider === "mt5" && <button type="button" onClick={() => removeMt5(account)} disabled={Boolean(busy)}>Remove MT5 metadata</button>}
            </footer>
          </form>
        ))}
        {!accounts.length && <p className="oak-account-empty">Chưa có account. Connect/sync cTrader hoặc thêm MT5 account ở form phía trên.</p>}
      </div>
    </section>
  );
}
