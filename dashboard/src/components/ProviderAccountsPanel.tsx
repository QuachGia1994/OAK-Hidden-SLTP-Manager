"use client";

import { FormEvent, useCallback, useEffect, useState } from "react";
import { useLocale } from "@/components/LocaleProvider";

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
  manager: {
    managerEnabled: boolean;
    autoAttachSlTp: boolean;
    netCloseOpposite: boolean;
    netSkipSameDirection: boolean;
    netRemoveOppositePending: boolean;
    breakEvenAtR: number;
    breakEvenOffsetPoints: number;
    closeAtR: number;
    partialRLevels: number[];
    partialPercents: number[];
    maxLotPerTrade: number;
    maxExposurePerSymbol: number;
  } | null;
  bridgeOnline?: boolean;
  bridgeLastSeenAt?: number | null;
  bridgeRuntime?: "mql5-ea" | null;
  bridgeVersion?: string | null;
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
  const { locale } = useLocale();
  const tr = (en: string, vi: string) => locale === "EN" ? en : vi;
  const [state, setState] = useState<"loading" | "locked" | "error" | "ready">("loading");
  const [payload, setPayload] = useState<AccountPayload | null>(null);
  const [providerTab, setProviderTab] = useState<Provider>("ctrader");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState("");

  const load = useCallback(async () => {
    setError("");
    const response = await fetch("/api/accounts", { cache: "no-store" });
    if (response.status === 401) {
      setPayload(null);
      setState("locked");
      return;
    }
    const body = await response.json().catch(() => null) as AccountPayload | { error?: string } | null;
    if (!response.ok || !body || !("accounts" in body)) throw new Error((body && "error" in body && body.error) || (locale === "EN" ? "Cannot load provider accounts" : "Không thể tải tài khoản provider"));
    setPayload(body);
    setState("ready");
  }, [locale]);

  useEffect(() => {
    load().catch((reason) => {
      setError(reason instanceof Error ? reason.message : String(reason));
      setState("error");
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
      if (!response.ok) throw new Error(tr("Invalid admin key", "Admin key không đúng"));
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
      if (!response.ok || !body?.authorizeUrl) throw new Error(body?.error || tr("Cannot start cTrader OAuth", "Không thể bắt đầu cTrader OAuth"));
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
      if (!response.ok || !body || !("accounts" in body)) throw new Error((body && "error" in body && body.error) || tr("cTrader sync failed", "Đồng bộ cTrader thất bại"));
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
      if (!response.ok || !body?.payload) throw new Error(body?.error || tr("Cannot register MT5 account", "Không thể đăng ký tài khoản MT5"));
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
          manager: account.provider === "ctrader" ? {
            managerEnabled: form.get("managerEnabled") === "on",
            autoAttachSlTp: form.get("autoAttachSlTp") === "on",
            netCloseOpposite: form.get("netCloseOpposite") === "on",
            netSkipSameDirection: form.get("netSkipSameDirection") === "on",
            netRemoveOppositePending: form.get("netRemoveOppositePending") === "on",
            breakEvenAtR: Number(form.get("breakEvenAtR")),
            breakEvenOffsetPoints: Number(form.get("breakEvenOffsetPoints")),
            closeAtR: Number(form.get("closeAtR")),
            partialRLevels: String(form.get("partialRLevels") || ""),
            partialPercents: String(form.get("partialPercents") || ""),
            maxLotPerTrade: Number(form.get("maxLotPerTrade")),
            maxExposurePerSymbol: Number(form.get("maxExposurePerSymbol")),
          } : undefined,
        }),
      });
      const body = await response.json().catch(() => null) as { payload?: AccountPayload; error?: string } | null;
      if (!response.ok || !body?.payload) throw new Error(body?.error || tr("Save failed", "Lưu thất bại"));
      setPayload(body.payload);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : String(reason));
    } finally {
      setBusy("");
    }
  }

  async function removeMt5(account: Account) {
    if (account.provider !== "mt5") return;
    if (!window.confirm(tr(`Remove MT5 metadata for ${account.label}?`, `Xóa metadata MT5 ${account.label}?`))) return;
    setBusy(`delete:${account.id}`);
    setError("");
    try {
      const response = await fetch(`/api/accounts?id=${encodeURIComponent(account.id)}`, { method: "DELETE" });
      const body = await response.json().catch(() => null) as { payload?: AccountPayload; error?: string } | null;
      if (!response.ok || !body?.payload) throw new Error(body?.error || tr("Delete failed", "Xóa thất bại"));
      setPayload(body.payload);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : String(reason));
    } finally {
      setBusy("");
    }
  }

  if (state === "loading") return <section className="oak-account-panel"><p>{tr("Loading provider accounts…", "Đang tải tài khoản provider…")}</p></section>;
  if (state === "locked") {
    return (
      <section className="oak-account-panel oak-account-login">
        <header><small>ADMIN</small><h1>{tr("Provider Account Manager", "Quản lý tài khoản Provider")}</h1><p>{tr("Sign in with the Dashboard API key. The session is stored in an HttpOnly cookie for 12 hours; broker secrets and tokens are never exposed to the browser.", "Đăng nhập bằng Dashboard API key. Session lưu HttpOnly 12 giờ; broker secret/token không được đưa vào browser.")}</p></header>
        <form onSubmit={login}>
          <label htmlFor="admin-api-key">Dashboard API key</label>
          <input id="admin-api-key" name="apiKey" type="password" autoComplete="current-password" required />
          <button type="submit" disabled={busy === "login"}>{busy === "login" ? tr("Signing in…", "Đang đăng nhập…") : tr("Sign in", "Đăng nhập")}</button>
        </form>
        {error && <p className="oak-account-error">{error}</p>}
      </section>
    );
  }
  if (state === "error") {
    return (
      <section className="oak-account-panel oak-account-login" role="alert">
        <header><small>ACCOUNT SERVICE</small><h1>{tr("Provider accounts unavailable", "Không thể truy cập tài khoản provider")}</h1><p>{error || tr("Cannot load provider accounts.", "Không thể tải tài khoản provider.")}</p></header>
        <button type="button" onClick={() => { setState("loading"); void load().catch((reason) => { setError(reason instanceof Error ? reason.message : String(reason)); setState("error"); }); }}>{tr("Retry", "Thử lại")}</button>
      </section>
    );
  }

  const accounts = payload?.accounts || [];
  const cTraderAccounts = accounts.filter((item) => item.provider === "ctrader");
  const mt5Accounts = accounts.filter((item) => item.provider === "mt5");
  const activeAccounts = providerTab === "ctrader" ? cTraderAccounts : mt5Accounts;
  const enabled = activeAccounts.filter((item) => item.enabled).length;
  return (
    <section className="oak-account-panel">
      <header className="oak-account-head">
        <div>
          <small>CLOUD / {providerTab === "ctrader" ? "CTRADER" : "MT5"}</small>
          <h1>{tr("Provider Account Manager", "Quản lý tài khoản Provider")}</h1>
          <p>{providerTab === "ctrader"
            ? tr("cTrader uses trading OAuth plus the cloud minute watchdog for Auto Manager.", "cTrader dùng OAuth trading + cloud minute watchdog cho Auto Manager.")
            : tr("MT5 uses the OAK MQL5 EA attached directly to the terminal and the Upstash outbound bridge; broker passwords and tokens never pass through the browser.", "MT5 dùng OAK MQL5 EA gắn trực tiếp vào terminal và Upstash outbound bridge; broker password/token không đi qua browser.")}</p>
        </div>
        {providerTab === "ctrader" && <div className="oak-account-actions">
          <button type="button" onClick={connectCTrader} disabled={Boolean(busy)}>{payload?.providers.ctrader.connected ? tr("Reconnect cTrader", "Kết nối lại cTrader") : tr("Connect cTrader", "Kết nối cTrader")}</button>
          <button type="button" onClick={syncCTrader} disabled={Boolean(busy) || !payload?.providers.ctrader.connected}>{busy === "sync-ctrader" ? tr("Syncing…", "Đang đồng bộ…") : tr("Sync cTrader", "Đồng bộ cTrader")}</button>
        </div>}
      </header>

      <div className="oak-account-tabs" role="tablist" aria-label={tr("Provider account type", "Loại tài khoản provider")}>
        <button type="button" role="tab" aria-selected={providerTab === "ctrader"} data-active={providerTab === "ctrader"} onClick={() => setProviderTab("ctrader")}>cTrader <span>{cTraderAccounts.length}</span></button>
        <button type="button" role="tab" aria-selected={providerTab === "mt5"} data-active={providerTab === "mt5"} onClick={() => setProviderTab("mt5")}>MT5 <span>{mt5Accounts.length}</span></button>
      </div>

      <div className="oak-account-status">
        {providerTab === "ctrader" ? <>
          <span>cTrader <b>{payload?.providers.ctrader.connected ? "CONNECTED" : "OFF"}</b></span>
          <span>Scope <b>{payload?.providers.ctrader.scope || "—"}</b></span>
        </> : <>
          <span>MT5 <b>{payload?.providers.mt5.connected ? "BRIDGE ONLINE" : "BRIDGE OFFLINE"}</b></span>
          <span>Runtime <b>OAK EA</b></span>
        </>}
        <span>{tr("Enabled", "Đang bật")} <b>{enabled}/{activeAccounts.length}</b></span>
      </div>

      {error && <p className="oak-account-error">{error}</p>}

      {providerTab === "mt5" && <form className="oak-account-card" onSubmit={createMt5}>
        <header><div><b>{tr("Add MT5 account", "Thêm tài khoản MT5")}</b><span>{tr("Metadata only · no broker password stored", "Chỉ lưu metadata · không lưu broker password")}</span></div></header>
        <div className="oak-account-fields">
          <label>Broker<input name="broker" placeholder="Vantage / ICMarkets / Darwinex" required /></label>
          <label>{tr("Login", "Tài khoản")}<input name="login" type="number" min="1" step="1" required /></label>
          <label>{tr("Environment", "Môi trường")}<select name="environment" defaultValue="live"><option value="live">LIVE</option><option value="demo">DEMO</option></select></label>
          <label>{tr("Label", "Nhãn")}<input name="label" placeholder="Main Vantage" /></label>
          <label>{tr("Bridge profile", "Profile bridge")}<input name="bridgeProfile" placeholder="Vantage" /></label>
        </div>
        <footer><button type="submit" disabled={busy === "create-mt5"}>{busy === "create-mt5" ? tr("Adding…", "Đang thêm…") : tr("Add MT5 account", "Thêm tài khoản MT5")}</button></footer>
      </form>}

      <div className="oak-account-list" role="tabpanel" aria-label={tr(`${providerTab} accounts`, `Tài khoản ${providerTab}`)}>
        {activeAccounts.map((account) => (
          <form key={account.id} className="oak-account-card" onSubmit={(event) => saveAccount(event, account)}>
            <header>
              <div><b>{account.label}</b><span>{account.provider.toUpperCase()} · {account.broker} · {account.environment.toUpperCase()} · #{account.externalAccountId}{account.provider === "mt5" ? ` · ${account.bridgeOnline ? "BRIDGE ONLINE" : "BRIDGE OFFLINE"}${account.bridgeRuntime ? " · OAK EA" : ""}` : ""}</span></div>
              <label><input name="enabled" type="checkbox" defaultChecked={account.enabled} /> {tr("Enable control", "Bật điều khiển")}</label>
            </header>
            <div className="oak-account-fields">
              <label>{tr("Account label", "Nhãn tài khoản")}<input name="label" defaultValue={account.label} /></label>
              {account.provider === "mt5" && <label>{tr("Bridge profile", "Profile bridge")}<input name="bridgeProfile" defaultValue={account.bridgeProfile || ""} placeholder="Vantage" /></label>}
              <label>{tr("FX SL points", "Điểm SL FX")}<input name="fxSlPoints" type="number" min="1" step="1" defaultValue={account.fxSlPoints} /></label>
              <label>{tr("FX TP points", "Điểm TP FX")}<input name="fxTpPoints" type="number" min="1" step="1" defaultValue={account.fxTpPoints} /></label>
              <label>{tr("Gold SL points", "Điểm SL Gold")}<input name="goldSlPoints" type="number" min="1" step="1" defaultValue={account.goldSlPoints} /></label>
              <label>{tr("Gold TP points", "Điểm TP Gold")}<input name="goldTpPoints" type="number" min="1" step="1" defaultValue={account.goldTpPoints} /></label>
              {account.provider === "ctrader" && account.manager && <>
                <label><input name="managerEnabled" type="checkbox" defaultChecked={account.manager.managerEnabled} /> cTrader Auto Manager</label>
                <label><input name="autoAttachSlTp" type="checkbox" defaultChecked={account.manager.autoAttachSlTp} /> {tr("Auto attach missing SL/TP", "Tự gắn SL/TP còn thiếu")}</label>
                <label><input name="netSkipSameDirection" type="checkbox" defaultChecked={account.manager.netSkipSameDirection} /> {tr("Net: skip same direction", "Net: bỏ qua cùng hướng")}</label>
                <label><input name="netCloseOpposite" type="checkbox" defaultChecked={account.manager.netCloseOpposite} /> {tr("Net: close opposite", "Net: đóng ngược hướng")}</label>
                <label><input name="netRemoveOppositePending" type="checkbox" defaultChecked={account.manager.netRemoveOppositePending} /> {tr("Net: remove opposite pending", "Net: xóa pending ngược hướng")}</label>
                <label>{tr("BE at R", "BE tại R")}<input name="breakEvenAtR" type="number" min="0" step="0.1" defaultValue={account.manager.breakEvenAtR} /></label>
                <label>{tr("BE offset points", "Điểm bù BE")}<input name="breakEvenOffsetPoints" type="number" min="0" step="1" defaultValue={account.manager.breakEvenOffsetPoints} /></label>
                <label>{tr("Full close at R", "Đóng toàn bộ tại R")}<input name="closeAtR" type="number" min="0" step="0.1" defaultValue={account.manager.closeAtR} /></label>
                <label>{tr("Partial R levels", "Các mức R partial")}<input name="partialRLevels" defaultValue={account.manager.partialRLevels.join(",")} placeholder="1,2" /></label>
                <label>{tr("Partial %", "% partial")}<input name="partialPercents" defaultValue={account.manager.partialPercents.join(",")} placeholder={tr("50 or 50,25", "50 hoặc 50,25")} /></label>
                <label>{tr("Max lot / entry", "Lot tối đa / lệnh")}<input name="maxLotPerTrade" type="number" min="0.01" step="0.01" defaultValue={account.manager.maxLotPerTrade} /></label>
                <label>{tr("Max exposure / symbol", "Exposure tối đa / symbol")}<input name="maxExposurePerSymbol" type="number" min="0.01" step="0.01" defaultValue={account.manager.maxExposurePerSymbol} /></label>
              </>}
              <label><input name="makeDefault" type="checkbox" defaultChecked={account.isDefault} disabled={!account.enabled} /> {tr("Default account", "Tài khoản mặc định")}</label>
            </div>
            <footer>
              <button type="submit" disabled={busy === account.id}>{busy === account.id ? tr("Saving…", "Đang lưu…") : tr("Save account", "Lưu tài khoản")}</button>
              {account.provider === "mt5" && <button type="button" onClick={() => removeMt5(account)} disabled={Boolean(busy)}>{tr("Remove MT5 metadata", "Xóa metadata MT5")}</button>}
            </footer>
          </form>
        ))}
        {!activeAccounts.length && <p className="oak-account-empty">{providerTab === "ctrader"
          ? tr("No cTrader accounts yet. Connect or sync cTrader to load the account list.", "Chưa có cTrader account. Connect/sync cTrader để tải danh sách account.")
          : tr("No MT5 accounts yet. Add an account above, then attach the OAK EA to the terminal.", "Chưa có MT5 account. Thêm account ở form phía trên rồi gắn OAK EA vào terminal.")}</p>}
      </div>
    </section>
  );
}
