"use client";

import { FormEvent, useCallback, useEffect, useState } from "react";

type Account = {
  accountId: number;
  traderLogin: number | null;
  broker: string;
  environment: "live" | "demo";
  label: string;
  enabled: boolean;
  fxSlPoints: number;
  fxTpPoints: number;
  goldSlPoints: number;
  goldTpPoints: number;
};

type AccountPayload = {
  ok: boolean;
  oauth: { connected: boolean; scope: "accounts" | "trading" | null };
  accounts: Account[];
};

export function CTraderAccountsPanel() {
  const [state, setState] = useState<"loading" | "locked" | "ready">("loading");
  const [payload, setPayload] = useState<AccountPayload | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState("");

  const load = useCallback(async () => {
    const response = await fetch("/api/ctrader/accounts", { cache: "no-store" });
    if (response.status === 401) {
      setState("locked");
      return;
    }
    const body = await response.json().catch(() => null) as AccountPayload | { error?: string } | null;
    if (!response.ok || !body || !("accounts" in body)) throw new Error((body && "error" in body && body.error) || "Cannot load cTrader accounts");
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

  async function connect() {
    setBusy("connect");
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

  async function sync() {
    setBusy("sync");
    setError("");
    try {
      const response = await fetch("/api/ctrader/accounts", { method: "POST" });
      const body = await response.json().catch(() => null) as AccountPayload | { error?: string } | null;
      if (!response.ok || !body || !("accounts" in body)) throw new Error((body && "error" in body && body.error) || "Sync failed");
      setPayload(body);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : String(reason));
    } finally {
      setBusy("");
    }
  }

  async function saveAccount(event: FormEvent<HTMLFormElement>, accountId: number) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    setBusy(String(accountId));
    setError("");
    try {
      const response = await fetch("/api/ctrader/accounts", {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          accountId,
          label: String(form.get("label") || ""),
          enabled: form.get("enabled") === "on",
          fxSlPoints: Number(form.get("fxSlPoints")),
          fxTpPoints: Number(form.get("fxTpPoints")),
          goldSlPoints: Number(form.get("goldSlPoints")),
          goldTpPoints: Number(form.get("goldTpPoints")),
        }),
      });
      const body = await response.json().catch(() => null) as { account?: Account; error?: string } | null;
      if (!response.ok || !body?.account) throw new Error(body?.error || "Save failed");
      setPayload((current) => current ? { ...current, accounts: current.accounts.map((item) => item.accountId === accountId ? body.account! : item) } : current);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : String(reason));
    } finally {
      setBusy("");
    }
  }

  if (state === "loading") return <section className="oak-account-panel"><p>Loading account manager…</p></section>;
  if (state === "locked") {
    return (
      <section className="oak-account-panel oak-account-login">
        <header><small>ADMIN</small><h1>cTrader Account Manager</h1><p>Đăng nhập bằng Dashboard API key. Key chỉ được gửi tới server để tạo session HttpOnly 12 giờ.</p></header>
        <form onSubmit={login}>
          <label htmlFor="admin-api-key">Dashboard API key</label>
          <input id="admin-api-key" name="apiKey" type="password" autoComplete="current-password" required />
          <button type="submit" disabled={busy === "login"}>{busy === "login" ? "Signing in…" : "Sign in"}</button>
        </form>
        {error && <p className="oak-account-error">{error}</p>}
      </section>
    );
  }

  const enabled = payload?.accounts.filter((item) => item.enabled).length || 0;
  return (
    <section className="oak-account-panel">
      <header className="oak-account-head">
        <div><small>CLOUD / ACCOUNTS</small><h1>cTrader Account Manager</h1><p>Bật account nào thì Telegram intent có thể nhắm tới account đó. `@label` chọn một account; không ghi label sẽ nhắm tất cả account đang bật. SL/TP mặc định được snapshot vào intent trước bước xác nhận, nên thay đổi cấu hình sau đó không làm lệch lệnh đang chờ.</p></div>
        <div className="oak-account-actions">
          <button type="button" onClick={connect} disabled={Boolean(busy)}>{payload?.oauth.connected ? "Reconnect cTrader" : "Connect cTrader"}</button>
          <button type="button" onClick={sync} disabled={Boolean(busy) || !payload?.oauth.connected}>{busy === "sync" ? "Syncing…" : "Sync accounts"}</button>
        </div>
      </header>
      <div className="oak-account-status">
        <span>OAuth <b>{payload?.oauth.connected ? "CONNECTED" : "OFF"}</b></span>
        <span>Scope <b>{payload?.oauth.scope || "—"}</b></span>
        <span>Enabled <b>{enabled}/{payload?.accounts.length || 0}</b></span>
      </div>
      {!payload?.oauth.connected && <p className="oak-account-warning">Kết nối cTrader để discover/sync các account được cấp quyền. Dashboard không nhận hoặc hiển thị broker credentials.</p>}
      {payload?.oauth.connected && payload.oauth.scope !== "trading" && <p className="oak-account-warning">OAuth hiện chỉ có quyền xem. Chọn Reconnect cTrader và cấp scope trading trước khi /approve có thể gửi lệnh.</p>}
      {error && <p className="oak-account-error">{error}</p>}
      <div className="oak-account-list">
        {(payload?.accounts || []).map((account) => (
          <form key={account.accountId} className="oak-account-card" onSubmit={(event) => saveAccount(event, account.accountId)}>
            <header><div><b>{account.broker}</b><span>{account.environment.toUpperCase()} · login {account.traderLogin || "—"} · #{account.accountId}</span></div><label><input name="enabled" type="checkbox" defaultChecked={account.enabled} /> Enable control</label></header>
            <div className="oak-account-fields">
              <label>Telegram label<input name="label" defaultValue={account.label} /></label>
              <label>FX SL points<input name="fxSlPoints" type="number" min="1" step="1" defaultValue={account.fxSlPoints} /></label>
              <label>FX TP points<input name="fxTpPoints" type="number" min="1" step="1" defaultValue={account.fxTpPoints} /></label>
              <label>Gold SL points<input name="goldSlPoints" type="number" min="1" step="1" defaultValue={account.goldSlPoints} /></label>
              <label>Gold TP points<input name="goldTpPoints" type="number" min="1" step="1" defaultValue={account.goldTpPoints} /></label>
            </div>
            <footer><button type="submit" disabled={busy === String(account.accountId)}>{busy === String(account.accountId) ? "Saving…" : "Save account"}</button></footer>
          </form>
        ))}
        {!payload?.accounts.length && <p className="oak-account-empty">Chưa có account. Chọn Connect cTrader, cấp quyền trading cho các account cần quản lý, rồi Sync accounts.</p>}
      </div>
    </section>
  );
}
