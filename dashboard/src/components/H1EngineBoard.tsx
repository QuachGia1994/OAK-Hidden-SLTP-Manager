"use client";

import { useState } from "react";
import { H1SignalBoard } from "@/components/H1SignalBoard";
import { useDialogFocusTrap } from "@/hooks/useDialogFocusTrap";
import type { H1SignalPayload } from "@/lib/h1-signals";

type Locale = "EN" | "VN";
type VipAccessView = {
  unlocked: boolean;
  freeAccess: boolean;
  weekendFree: boolean;
  vipAuthenticated: boolean;
  weekday: string;
  mode: "free" | "vip" | "weekend" | "locked";
};

const ACCESS_WEEKDAY_LABELS: Record<Locale, Record<string, string>> = {
  EN: { Mon: "Mon", Tue: "Tue", Wed: "Wed", Thu: "Thu", Fri: "Fri", Sat: "Sat", Sun: "Sun" },
  VN: { Mon: "T2", Tue: "T3", Wed: "T4", Thu: "T5", Fri: "T6", Sat: "T7", Sun: "CN" },
};

function formatPublished(value: string | undefined, locale: Locale) {
  if (!value) return locale === "EN" ? "Awaiting feed" : "Đang chờ feed";
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return value;
  return parsed.toLocaleString(locale === "EN" ? "en-GB" : "vi-VN", {
    timeZone: "Asia/Ho_Chi_Minh",
    day: "2-digit",
    month: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function VipGate({ access, locale }: { access: VipAccessView; locale: Locale }) {
  const [open, setOpen] = useState(false);
  const [token, setToken] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const isEn = locale === "EN";
  const dialogRef = useDialogFocusTrap(open, () => setOpen(false));

  const openDialog = () => {
    setError("");
    setOpen(true);
  };

  const parseJson = async (response: Response): Promise<{ ok?: boolean; error?: string }> => {
    const text = await response.text();
    if (!text) return {};
    try {
      return JSON.parse(text) as { ok?: boolean; error?: string };
    } catch {
      return {};
    }
  };

  const unlock = async () => {
    if (!token.trim() || loading) return;
    setLoading(true);
    setError("");
    try {
      const response = await fetch("/api/vip", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ token: token.trim() }),
      });
      const payload = await parseJson(response);
      if (!response.ok || !payload.ok) throw new Error(payload.error || (isEn ? "VIP unlock failed. Try again." : "Không mở được VIP. Thử lại."));
      window.location.reload();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : (isEn ? "VIP unlock failed. Try again." : "Không mở được VIP. Thử lại."));
      setLoading(false);
    }
  };

  const logout = async () => {
    if (loading) return;
    setLoading(true);
    setError("");
    try {
      const response = await fetch("/api/vip", { method: "DELETE" });
      const payload = await parseJson(response);
      if (!response.ok || !payload.ok) throw new Error(payload.error || (isEn ? "VIP logout failed. Try again." : "Thoát VIP thất bại. Thử lại."));
      window.location.reload();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : (isEn ? "VIP logout failed. Try again." : "Thoát VIP thất bại. Thử lại."));
      setLoading(false);
    }
  };

  const modeCopy = access.mode === "free"
    ? { title: isEn ? "FREE ACCESS" : "FREE ACCESS", detail: isEn ? "FX BUY/SELL is open for everyone" : "BUY/SELL các cặp FX mở cho mọi user", action: "" }
    : access.mode === "vip"
      ? { title: "VIP UNLOCKED", detail: isEn ? "XAUUSD BUY/SELL signals unlocked" : "Đã mở BUY/SELL XAUUSD", action: isEn ? "Exit VIP" : "Thoát VIP" }
      : access.mode === "weekend"
        ? { title: isEn ? "FREE WEEKEND" : "CUỐI TUẦN FREE", detail: isEn ? "Weekend XAUUSD BUY/SELL is open" : "BUY/SELL XAUUSD cuối tuần đang mở", action: "" }
        : { title: "VIP LOCKED", detail: isEn ? "XAUUSD BUY/SELL signals require VIP" : "BUY/SELL XAUUSD cần VIP", action: isEn ? "Unlock" : "Mở VIP" };

  return <>
    <section className="oak-access-panel" data-mode={access.mode}>
      <div className="oak-access-symbol"><span>{access.mode === "vip" ? "◆" : access.mode === "free" || access.mode === "weekend" ? "◇" : "◈"}</span></div>
      <div className="oak-access-copy"><small>ACCESS</small><b>{modeCopy.title}</b><p>{modeCopy.detail}</p></div>
      <div className="oak-access-state"><span>{ACCESS_WEEKDAY_LABELS[locale][access.weekday] ?? access.weekday}</span><i /></div>
      {access.mode === "vip" && <button type="button" disabled={loading} onClick={() => void logout()}>{loading ? "…" : modeCopy.action}</button>}
      {access.mode === "locked" && <button type="button" onClick={openDialog}>{modeCopy.action}</button>}
    </section>
    {!open && error && <p className="oak-form-error" role="alert">{error}</p>}
    {open && <div className="oak-modal-backdrop" onMouseDown={(event) => event.target === event.currentTarget && setOpen(false)}>
      <section ref={dialogRef} className="oak-vip-modal" role="dialog" aria-modal="true" aria-label="VIP Unlock">
        <header className="oak-modal-header"><div><span className="oak-eyebrow">PRIVATE ACCESS</span><h2>VIP UNLOCK</h2><p>{isEn ? "Enter your access code to reveal XAUUSD BUY/SELL signals." : "Nhập mã truy cập để mở BUY/SELL XAUUSD."}</p></div><button type="button" onClick={() => setOpen(false)} aria-label="Close">×</button></header>
        <label className="oak-vip-field"><span>{isEn ? "ACCESS CODE" : "MÃ VIP"}</span><input type="password" value={token} onChange={(event) => setToken(event.target.value)} onKeyDown={(event) => event.key === "Enter" && void unlock()} autoFocus autoComplete="current-password" /></label>
        {error && <p className="oak-form-error">{error}</p>}
        <button className="oak-primary-action" type="button" disabled={loading || !token.trim()} onClick={() => void unlock()}>{loading ? (isEn ? "UNLOCKING" : "ĐANG MỞ") : "UNLOCK BLOCKS"}</button>
      </section>
    </div>}
  </>;
}

export function H1EngineBoard({ h1Data, degraded, locale, access }: { h1Data: H1SignalPayload | null; degraded?: boolean; locale: Locale; access: VipAccessView }) {
  const dates = h1Data ? Object.keys(h1Data.days).sort() : [];
  const brokerDay = dates.at(-1) ?? "—";
  const copy = locale === "EN"
    ? { title: "H1 Cloud Scanner", subtitle: "cTrader Live", day: "Broker day", updated: "Updated" }
    : { title: "Scanner H1 Cloud", subtitle: "cTrader Live", day: "Ngày broker", updated: "Cập nhật" };

  return <div className="oak-engine-screen">
    <header className="oak-command-strip">
      <div className="oak-command-title"><span className="oak-eyebrow">TRADING / H1 CLOUD</span><div><h1>{copy.title}</h1><b>{copy.subtitle}</b></div></div>
      <div className="oak-command-meta">
        <span><small>{copy.day.toUpperCase()}</small><b>{brokerDay}</b></span>
        <span><small>{copy.updated.toUpperCase()}</small><b>{formatPublished(h1Data?.publishedAt, locale)}</b></span>
      </div>
    </header>

    <VipGate access={access} locale={locale} />
    <H1SignalBoard data={h1Data} degraded={degraded} locale={locale} unlocked={access.unlocked} />
  </div>;
}
