"use client";

import { useCallback, useEffect, useMemo, useRef, useState, type CSSProperties } from "react";
import { createPortal } from "react-dom";
import { useLocale } from "@/components/LocaleProvider";
import { useDialogFocusTrap } from "@/hooks/useDialogFocusTrap";
import type { NeoTechPublicProfile, NeoTechPublicRule, NeoTechPublicRuleCode, NeoTechPublicStatus } from "@/lib/neotech-public-domain";
import styles from "./neotech.module.css";

type PublicAccount = {
  id: string;
  maskedLogin: string;
  broker: string;
  server: string;
  currency: string;
  mode: string;
  readOnlyVerified: boolean;
  accessMode: "READ_ONLY" | "TRADING_CAPABLE_ACCEPTED";
  connectorVersion: string;
  createdAt: number;
  lastSeenAt: number;
};

type AccountRow = { account: PublicAccount; profile: NeoTechPublicProfile | null };
type PairingState = { code: string; expiresAt: number; baselineCount: number; accessMode: "READ_ONLY" | "TRADING_CAPABLE_ACCEPTED" };
type ShareLink = { id: string; createdAt: number; expiresAt: number; revokedAt: number | null };
type ToastState = { message: string; kind: "success" | "error" };

type Locale = "EN" | "VN";

const STATUS_LABEL: Record<Locale, Record<NeoTechPublicStatus, string>> = {
  EN: { PASS: "Pass", FAIL: "Violation", IN_PROGRESS: "Tracking", INSUFFICIENT_DATA: "Insufficient data", NOT_VERIFIABLE: "Not verifiable" },
  VN: { PASS: "Đạt", FAIL: "Vi phạm", IN_PROGRESS: "Đang theo dõi", INSUFFICIENT_DATA: "Thiếu dữ liệu", NOT_VERIFIABLE: "Không thể xác minh" },
};

const OVERALL_LABEL: Record<Locale, Record<NeoTechPublicProfile["overall"], string>> = {
  EN: { CLEAR: "Clear", TRACKING: "Tracking", INSUFFICIENT_DATA: "Insufficient data", VIOLATION: "Violation" },
  VN: { CLEAR: "Đang đạt", TRACKING: "Đang theo dõi", INSUFFICIENT_DATA: "Thiếu dữ liệu", VIOLATION: "Có vi phạm" },
};

type RuleConcept = {
  code: NeoTechPublicRuleCode;
  icon: string;
  en: string;
  vi: string;
  thresholdEn: string;
  thresholdVi: string;
  verification: "AUTO" | "EXTERNAL";
};

const RULE_CONCEPTS: RuleConcept[] = [
  { code: "E1", icon: "M", en: "Manual only", vi: "Chỉ mở lệnh thủ công", thresholdEn: "No Expert-opened positions", thresholdVi: "0 lệnh mở bởi Expert", verification: "AUTO" },
  { code: "E2", icon: "A", en: "NeoTech account", vi: "Loại tài khoản NeoTech", thresholdEn: "REAL / DEMO", thresholdVi: "REAL / DEMO", verification: "AUTO" },
  { code: "E3", icon: "$", en: "Any starting capital", vi: "Vốn ban đầu bất kỳ", thresholdEn: "No minimum capital", thresholdVi: "Không giới hạn vốn", verification: "AUTO" },
  { code: "E4", icon: "ID", en: "Enrollment conditions", vi: "Điều kiện tham gia", thresholdEn: "KYC · Public · new account · non-Direct", thresholdVi: "KYC · Public · tài khoản mới · không Direct", verification: "EXTERNAL" },
  { code: "E5", icon: "FX", en: "Forex + Gold", vi: "Forex + Vàng", thresholdEn: "Forex / XAUUSD only", thresholdVi: "Chỉ Forex / XAUUSD", verification: "AUTO" },
  { code: "C1", icon: "365", en: "Tracking horizon", vi: "Thời gian theo dõi", thresholdEn: "≥365d and ≥12 × 30d", thresholdVi: "≥365 ngày và ≥12 × 30 ngày", verification: "AUTO" },
  { code: "C2", icon: "+1", en: "Monthly return", vi: "Hiệu suất 30 ngày", thresholdEn: "≥1% in every 30-day window", thresholdVi: "≥1% mỗi cửa sổ 30 ngày", verification: "AUTO" },
  { code: "C3", icon: "DD", en: "Floating drawdown", vi: "Floating Drawdown", thresholdEn: "FDD < 2%", thresholdVi: "FDD < 2%", verification: "AUTO" },
  { code: "C4", icon: "3×", en: "Signal frequency", vi: "Tần suất tín hiệu", thresholdEn: "≥3 signals / completed week", thresholdVi: "≥3 tín hiệu / tuần hoàn tất", verification: "AUTO" },
  { code: "C5", icon: "1×", en: "One per product/session", vi: "Một tín hiệu / sản phẩm / phiên", thresholdEn: "≤1 signal per symbol per session", thresholdVi: "≤1 tín hiệu / symbol / phiên", verification: "AUTO" },
  { code: "C6", icon: "15", en: "Hold or SL/TP", vi: "Giữ lệnh hoặc SL/TP", thresholdEn: "≥15m or SL/TP >30 pips", thresholdVi: "≥15 phút hoặc SL/TP >30 pip", verification: "AUTO" },
  { code: "C7", icon: "↔", en: "No Hedge / DCA", vi: "Không Hedge / DCA", thresholdEn: "0 confirmed Hedge / DCA", thresholdVi: "0 Hedge / DCA xác nhận", verification: "AUTO" },
  { code: "C8", icon: "CP", en: "No copy signals", vi: "Không copy tín hiệu", thresholdEn: "External-source verification", thresholdVi: "Xác minh nguồn bên ngoài", verification: "EXTERNAL" },
  { code: "C9", icon: "CF", en: "No deposits / withdrawals", vi: "Không nạp / rút trong kỳ", thresholdEn: "0 cash flow after program start", thresholdVi: "0 nạp/rút sau program start", verification: "AUTO" },
];

const SESSION_CONCEPTS = [
  { code: "ASIA", summer: "02:00–11:00", winter: "02:00–11:00" },
  { code: "EUROPE", summer: "09:00–18:00", winter: "10:00–19:00" },
  { code: "US", summer: "14:00–23:00", winter: "15:00–24:00" },
] as const;

async function readJson(response: Response): Promise<Record<string, unknown>> {
  return response.json().catch(() => ({})) as Promise<Record<string, unknown>>;
}

function fmtPercent(value: number | null, digits = 2): string {
  return value === null || !Number.isFinite(value) ? "—" : `${value.toFixed(digits)}%`;
}

function fmtDate(epochSeconds: number, locale: Locale): string {
  if (!epochSeconds) return "—";
  return new Intl.DateTimeFormat(locale === "EN" ? "en-GB" : "vi-VN", { day: "2-digit", month: "2-digit", year: "2-digit" }).format(new Date(epochSeconds * 1000));
}

function fmtDateTimeMs(epochMs: number, locale: Locale): string {
  return new Intl.DateTimeFormat(locale === "EN" ? "en-GB" : "vi-VN", { day: "2-digit", month: "2-digit", year: "numeric", hour: "2-digit", minute: "2-digit" }).format(new Date(epochMs));
}

function relativeTime(epochMs: number, nowMs: number, locale: Locale): string {
  const seconds = Math.max(0, Math.floor((nowMs - epochMs) / 1000));
  if (seconds < 10) return locale === "EN" ? "just now" : "vừa xong";
  if (seconds < 60) return locale === "EN" ? `${seconds}s ago` : `${seconds} giây trước`;
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return locale === "EN" ? `${minutes}m ago` : `${minutes} phút trước`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return locale === "EN" ? `${hours}h ago` : `${hours} giờ trước`;
  const days = Math.floor(hours / 24);
  return locale === "EN" ? `${days}d ago` : `${days} ngày trước`;
}

function StatusPill({ status, overall, locale }: { status?: NeoTechPublicStatus; overall?: NeoTechPublicProfile["overall"]; locale: Locale }) {
  const label = status ? STATUS_LABEL[locale][status] : overall ? OVERALL_LABEL[locale][overall] : "—";
  return <span className={styles.statusPill} data-status={status} data-overall={overall}>{label}</span>;
}

function RuleRadar({ rules, locale }: { rules: NeoTechPublicRule[]; locale: Locale }) {
  const pass = rules.filter((row) => row.status === "PASS").length;
  const fail = rules.filter((row) => row.status === "FAIL").length;
  const pending = Math.max(0, rules.length - pass - fail);
  const passAngle = rules.length ? pass / rules.length * 360 : 0;
  const failAngle = rules.length ? fail / rules.length * 360 : 0;
  const ringStyle = { background: `conic-gradient(var(--oak-status-online) 0deg ${passAngle}deg, var(--oak-status-danger) ${passAngle}deg ${passAngle + failAngle}deg, var(--oak-fg-muted) ${passAngle + failAngle}deg 360deg)` } as CSSProperties;

  return (
    <div className={styles.radarWrap}>
      <div className={styles.ruleDonut} style={ringStyle} role="img" aria-label={locale === "EN" ? `${pass} passed, ${fail} failed, ${pending} pending out of ${rules.length}` : `${pass} đạt, ${fail} vi phạm, ${pending} đang chờ trên ${rules.length} rule`}>
        <span><strong>{pass}/{rules.length}</strong><small>{locale === "EN" ? "RULES PASS" : "RULE ĐẠT"}</small></span>
      </div>
      <div className={styles.ruleDonutLegend}>
        <span data-kind="pass"><i />{pass} PASS</span>
        <span data-kind="fail"><i />{fail} FAIL</span>
        <span data-kind="pending"><i />{pending} {locale === "EN" ? "TRACKING / EVIDENCE" : "THEO DÕI / EVIDENCE"}</span>
      </div>
    </div>
  );
}

function RuleMini({ rule, locale }: { rule: NeoTechPublicRule; locale: Locale }) {
  return (
    <div className={styles.ruleMini}>
      <div className={styles.ruleMiniTop}><span className={styles.ruleCode}>{rule.code}</span><StatusPill status={rule.status} locale={locale} /></div>
      <b>{rule.title}</b>
      <small>{rule.measured}</small>
    </div>
  );
}

function RuleDetails({ rules, locale }: { rules: NeoTechPublicRule[]; locale: Locale }) {
  return (
    <div className={styles.ruleList}>
      {rules.map((rule) => (
        <details key={rule.code} className={styles.ruleCard}>
          <summary>
            <span className={styles.ruleBadge}>{rule.code}</span>
            <span><h4>{rule.title}</h4><p>{rule.summary}</p></span>
            <StatusPill status={rule.status} locale={locale} />
          </summary>
          <div className={styles.ruleDetail}>
            <div className={styles.ruleFacts}>
              <div className={styles.ruleFact}><small>{locale === "EN" ? "Measured" : "Đo được"}</small><b>{rule.measured}</b></div>
              <div className={styles.ruleFact}><small>{locale === "EN" ? "NeoTech threshold" : "Ngưỡng NeoTech"}</small><b>{rule.threshold}</b></div>
            </div>
            {rule.evidence.length > 0 && <ul className={styles.evidence}>{rule.evidence.map((item, index) => <li key={`${rule.code}-${index}`}>{item}</li>)}</ul>}
          </div>
        </details>
      ))}
    </div>
  );
}

export function NeoTechPublicDashboard() {
  const { locale } = useLocale();
  const tr = (en: string, vi: string) => locale === "EN" ? en : vi;
  const [workspaceRef, setWorkspaceRef] = useState("");
  const [accounts, setAccounts] = useState<AccountRow[]>([]);
  const [selectedId, setSelectedId] = useState("");
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [toast, setToast] = useState<ToastState | null>(null);
  const [pairing, setPairing] = useState<PairingState | null>(null);
  const [masterConsentOpen, setMasterConsentOpen] = useState(false);
  const [shareOpen, setShareOpen] = useState(false);
  const [shareLinks, setShareLinks] = useState<ShareLink[]>([]);
  const [shareUrl, setShareUrl] = useState("");
  const [shareBusy, setShareBusy] = useState(false);
  const [nowMs, setNowMs] = useState(Date.now());
  const [bootRetryIn, setBootRetryIn] = useState(0);
  const bootAttemptRef = useRef(0);
  const bootSucceededRef = useRef(false);
  const pairingDialogRef = useDialogFocusTrap<HTMLDivElement>(Boolean(pairing), () => setPairing(null));
  const masterConsentDialogRef = useDialogFocusTrap<HTMLDivElement>(masterConsentOpen, () => setMasterConsentOpen(false));
  const shareDialogRef = useDialogFocusTrap<HTMLDivElement>(shareOpen, () => setShareOpen(false));
  const selectedRef = useRef(selectedId);
  selectedRef.current = selectedId;

  const refreshAccounts = useCallback(async (silent = false): Promise<boolean> => {
    try {
      const response = await fetch("/api/neotech/public/accounts", { cache: "no-store" });
      const body = await readJson(response);
      if (!response.ok || body.ok !== true) {
        if (!silent) setError(String(body.error || (locale === "EN" ? "Cannot load NeoTech accounts." : "Không đọc được tài khoản NeoTech.")));
        return false;
      }
      const rows = Array.isArray(body.accounts) ? body.accounts as AccountRow[] : [];
      setAccounts(rows);
      if (!selectedRef.current && rows[0]) setSelectedId(rows[0].account.id);
      else if (selectedRef.current && !rows.some((row) => row.account.id === selectedRef.current) && rows[0]) setSelectedId(rows[0].account.id);
      setPairing((current) => {
        if (current && rows.length > current.baselineCount) {
          const newest = [...rows].sort((a, b) => b.account.createdAt - a.account.createdAt)[0];
          if (newest) setSelectedId(newest.account.id);
          return null;
        }
        return current;
      });
      return true;
    } catch {
      if (!silent) setError(locale === "EN" ? "Cannot connect to the NeoTech workspace." : "Không thể kết nối NeoTech workspace.");
      return false;
    }
  }, [locale]);

  const bootstrap = useCallback(async () => {
    try {
      const response = await fetch("/api/neotech/public/session", { cache: "no-store" });
      const body = await readJson(response);
      if (!response.ok || body.ok !== true) throw new Error(String(body.error || "workspace unavailable"));
      const recovered = bootAttemptRef.current > 0;
      bootAttemptRef.current = 0;
      setWorkspaceRef(String(body.workspaceRef || "private"));
      setBootRetryIn(0);
      if (recovered) setError("");
      bootSucceededRef.current = true;
      await refreshAccounts(true);
    } catch {
      bootAttemptRef.current += 1;
      const delay = Math.min(60, 15 * 2 ** Math.min(2, bootAttemptRef.current - 1));
      setBootRetryIn(delay);
      if (!bootSucceededRef.current) {
        setError(locale === "EN" ? "NeoTech data storage is temporarily unavailable. Retrying automatically…" : "Kho dữ liệu NeoTech tạm không khả dụng. Đang tự động thử lại…");
      }
    }
  }, [locale, refreshAccounts]);

  useEffect(() => {
    let cancelled = false;
    void (async () => {
      await bootstrap();
      if (!cancelled) setLoading(false);
    })();
    return () => { cancelled = true; };
  }, [bootstrap]);

  useEffect(() => {
    if (bootRetryIn <= 0) return;
    const timer = window.setInterval(() => {
      if (document.visibilityState === "visible") {
        setBootRetryIn((seconds) => Math.max(0, seconds - 1));
      }
    }, 1000);
    return () => window.clearInterval(timer);
  }, [bootRetryIn > 0]);

  useEffect(() => {
    if (bootRetryIn === 0 && bootAttemptRef.current > 0 && !bootSucceededRef.current) {
      void bootstrap();
    }
  }, [bootRetryIn, bootstrap]);

  useEffect(() => {
    let cancelled = false;
    let timer: number | undefined;
    const loop = async () => {
      if (cancelled) return;
      let ok = true;
      if (document.visibilityState === "visible") {
        ok = await refreshAccounts(true);
        if (cancelled) return;
        setNowMs(Date.now());
      }
      const delay = pairing ? 4000 : ok ? 30000 : 60000;
      timer = window.setTimeout(() => void loop(), delay);
    };
    void loop();
    return () => {
      cancelled = true;
      if (timer) window.clearTimeout(timer);
    };
  }, [pairing, refreshAccounts]);

  const selected = useMemo(() => accounts.find((row) => row.account.id === selectedId) || accounts[0] || null, [accounts, selectedId]);
  const profile = selected?.profile || null;
  const ruleByCode = useMemo(() => new Map((profile?.rules || []).map((row) => [row.code, row])), [profile]);
  const eligibilityRules = profile?.rules.filter((row) => row.group === "ELIGIBILITY") || [];
  const consistencyRules = profile?.rules.filter((row) => row.group === "CONSISTENCY") || [];

  const createPairing = async (accessMode: "READ_ONLY" | "TRADING_CAPABLE_ACCEPTED" = "READ_ONLY") => {
    setBusy(true); setError("");
    try {
      const response = await fetch("/api/neotech/public/pairing", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ accessMode, riskAccepted: accessMode === "TRADING_CAPABLE_ACCEPTED" }) });
      const body = await readJson(response);
      if (!response.ok || body.ok !== true) throw new Error(String(body.error || (locale === "EN" ? "Cannot create pairing code." : "Không tạo được pairing code.")));
      setPairing({ code: String(body.pairingCode), expiresAt: Number(body.expiresAt), baselineCount: accounts.length, accessMode: String(body.accessMode) === "TRADING_CAPABLE_ACCEPTED" ? "TRADING_CAPABLE_ACCEPTED" : "READ_ONLY" });
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : (locale === "EN" ? "Cannot create pairing code." : "Không tạo được pairing code."));
    } finally { setBusy(false); }
  };

  const createMasterPairing = () => setMasterConsentOpen(true);

  const confirmMasterPairing = async () => {
    setMasterConsentOpen(false);
    await createPairing("TRADING_CAPABLE_ACCEPTED");
  };

  const revoke = async () => {
    if (!selected || !window.confirm(locale === "EN" ? `Revoke read access for ${selected.account.maskedLogin}? The current connector will be disabled immediately.` : `Thu hồi quyền đọc của ${selected.account.maskedLogin}? Connector cũ sẽ bị vô hiệu ngay.`)) return;
    setBusy(true); setError("");
    try {
      const response = await fetch(`/api/neotech/public/accounts?accountId=${encodeURIComponent(selected.account.id)}`, { method: "DELETE" });
      const body = await readJson(response);
      if (!response.ok || body.ok !== true) throw new Error(String(body.error || (locale === "EN" ? "Cannot revoke connector." : "Không revoke được connector.")));
      setSelectedId("");
      await refreshAccounts();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : (locale === "EN" ? "Cannot revoke connector." : "Không revoke được connector."));
    } finally { setBusy(false); }
  };

  const purge = async () => {
    if (!selected || !window.confirm(locale === "EN" ? `Delete OAK data for ${selected.account.maskedLogin}? The account, visual profile, equity samples, and connector will be removed from the server. This cannot be undone.` : `Xóa dữ liệu OAK của ${selected.account.maskedLogin}? Account, visual profile, equity samples và connector sẽ bị xóa khỏi server. Hành động này không thể hoàn tác.`)) return;
    setBusy(true); setError("");
    try {
      const response = await fetch(`/api/neotech/public/accounts?accountId=${encodeURIComponent(selected.account.id)}&purge=1`, { method: "DELETE" });
      const body = await readJson(response);
      if (!response.ok || body.ok !== true) throw new Error(String(body.error || (locale === "EN" ? "Cannot delete data." : "Không xóa được dữ liệu.")));
      setSelectedId("");
      await refreshAccounts();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : (locale === "EN" ? "Cannot delete data." : "Không xóa được dữ liệu."));
    } finally { setBusy(false); }
  };

  const loadShareLinks = useCallback(async (accountId: string) => {
    const response = await fetch(`/api/neotech/public/shares?accountId=${encodeURIComponent(accountId)}`, { cache: "no-store" });
    const body = await readJson(response);
    if (!response.ok || body.ok !== true) throw new Error(String(body.error || tr("Cannot load share links.", "Không đọc được share link.")));
    setShareLinks(Array.isArray(body.shares) ? body.shares as ShareLink[] : []);
  }, [locale]);

  const openShare = async () => {
    if (!selected?.profile) return;
    setShareOpen(true);
    setShareUrl("");
    setShareBusy(true);
    try {
      await loadShareLinks(selected.account.id);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : tr("Cannot load share links.", "Không đọc được share link."));
    } finally {
      setShareBusy(false);
    }
  };

  const createShare = async () => {
    if (!selected?.profile) return;
    setShareBusy(true); setError("");
    try {
      const response = await fetch("/api/neotech/public/shares", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ accountId: selected.account.id }) });
      const body = await readJson(response);
      if (!response.ok || body.ok !== true || typeof body.shareUrl !== "string") throw new Error(String(body.error || tr("Cannot create share link.", "Không tạo được share link.")));
      setShareUrl(body.shareUrl);
      await loadShareLinks(selected.account.id);
      setToast({ message: tr("Share link created — copy it now", "Đã tạo share link — hãy copy ngay"), kind: "success" });
      window.setTimeout(() => setToast(null), 2600);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : tr("Cannot create share link.", "Không tạo được share link."));
    } finally { setShareBusy(false); }
  };

  const revokeShareLink = async (shareId: string) => {
    if (!selected) return;
    setShareBusy(true); setError("");
    try {
      const response = await fetch(`/api/neotech/public/shares?accountId=${encodeURIComponent(selected.account.id)}&shareId=${encodeURIComponent(shareId)}`, { method: "DELETE" });
      const body = await readJson(response);
      if (!response.ok || body.ok !== true) throw new Error(String(body.error || tr("Cannot revoke share link.", "Không revoke được share link.")));
      setShareUrl("");
      await loadShareLinks(selected.account.id);
      setToast({ message: tr("Share link revoked", "Đã revoke share link"), kind: "success" });
      window.setTimeout(() => setToast(null), 2200);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : tr("Cannot revoke share link.", "Không revoke được share link."));
    } finally { setShareBusy(false); }
  };

  const revokeAllShareLinks = async () => {
    if (!selected || !shareLinks.length || !window.confirm(tr("Revoke every active share link for this profile?", "Revoke toàn bộ share link đang hoạt động của profile này?"))) return;
    setShareBusy(true); setError("");
    try {
      const response = await fetch(`/api/neotech/public/shares?accountId=${encodeURIComponent(selected.account.id)}&all=1`, { method: "DELETE" });
      const body = await readJson(response);
      if (!response.ok || body.ok !== true) throw new Error(String(body.error || tr("Cannot revoke share links.", "Không revoke được share link.")));
      setShareUrl("");
      await loadShareLinks(selected.account.id);
      setToast({ message: tr("All share links revoked", "Đã revoke toàn bộ share link"), kind: "success" });
      window.setTimeout(() => setToast(null), 2200);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : tr("Cannot revoke share links.", "Không revoke được share link."));
    } finally { setShareBusy(false); }
  };

  const copy = async (value: string, label?: string) => {
    try {
      if (!navigator.clipboard?.writeText) throw new Error("clipboard unavailable");
      await navigator.clipboard.writeText(value);
      setToast({ message: label || tr("Copied to clipboard", "Đã copy vào clipboard"), kind: "success" });
    } catch {
      setToast({ message: tr("Copy failed — please copy manually", "Copy thất bại — hãy copy thủ công"), kind: "error" });
    }
    window.setTimeout(() => setToast(null), 2200);
  };
  const secondsLeft = pairing ? Math.max(0, Math.floor((pairing.expiresAt - nowMs) / 1000)) : 0;
  const toastPortal = toast && typeof document !== "undefined" ? createPortal(
    <div className={styles.toast} data-kind={toast.kind} role="status" aria-live="polite"><b>{toast.kind === "success" ? "✓" : "!"}</b><span>{toast.message}</span></div>,
    document.body,
  ) : null;

  return (
    <div className={styles.page}>
      <section className={styles.heroV2}>
        <div className={styles.brandRail}>
          <div className={styles.neoBrand} aria-label="NeoTech Rule Ver 2">
            <span className={styles.neoMark}>N</span>
            <span><b>NeoTech</b><small>TRADERS EMPOWER TRADERS</small></span>
          </div>
          <span className={styles.heroMotto}>DISCIPLINE · TRANSPARENCY · LONG-TERM GROWTH</span>
          <span className={styles.rulesetBadge}><b>RULESET v2</b><small>2024-10-03</small></span>
        </div>
        <div className={styles.heroV2Grid}>
          <div className={styles.heroCopyV2}>
            <span className={styles.heroKicker}>{tr("Same rules. Stronger clarity.", "Cùng bộ rule. Minh bạch hơn.")}</span>
            <h1>NeoTech <span>Rule Ver 2</span></h1>
            <h2>{tr("Standardized · Transparent · Observable", "Chuẩn hóa · Minh bạch · Dễ theo dõi")}</h2>
            <p>{tr("The official NeoTech signal-provider rules are reconstructed from MT5 facts by OAK Gatekeeper, with automatic checks, explicit evidence gaps and a visual profile that never guesses PASS.", "Bộ quy tắc chính thức dành cho Nhà cung cấp tín hiệu NeoTech được OAK Gatekeeper tái dựng từ dữ liệu MT5, kiểm tra tự động, nêu rõ khoảng trống evidence và tuyệt đối không suy đoán PASS.")}</p>
            <div className={styles.heroFeatureRow}>
              <span><i>⚡</i>{tr("Automatic checks", "Tự động kiểm tra")}</span>
              <span><i>▥</i>{tr("Official thresholds", "Bám sát rule chính thức")}</span>
              <span><i>◇</i>{tr("Evidence first", "Evidence minh bạch")}</span>
              <span><i>↗</i>{tr("Web · MT5 · Telegram", "Web · MT5 · Telegram")}</span>
            </div>
            <div className={styles.heroActions}>
              <button className={styles.primaryButton} onClick={() => void createPairing("READ_ONLY")} disabled={busy}>{accounts.length > 0 ? tr("+ Connect another account", "+ Kết nối tài khoản khác") : tr("Connect NeoTech account", "Kết nối tài khoản NeoTech")}</button>
              <a className={styles.secondaryButton} href="/downloads/OAK_NeoTech_ReadOnly_Connector.ex5" download>{tr("Download connector", "Tải connector")}</a>
              <a className={styles.secondaryButton} href="/downloads/OAK_NeoTech_ReadOnly_Connector.mq5" download>{tr("Audit source", "Source để audit")}</a>
            </div>
          </div>
          <div className={styles.heroVisualV2} aria-hidden="true">
            <div className={styles.heroChartGrid} />
            <div className={`${styles.heroCandle} ${styles.heroCandleA}`} />
            <div className={`${styles.heroCandle} ${styles.heroCandleB}`} />
            <div className={`${styles.heroCandle} ${styles.heroCandleC}`} />
            <div className={styles.neoMonogram}>N</div>
            <div className={styles.heroQuote}>TRADE<br />DISCIPLINE<br />BUILD<br />OPPORTUNITY</div>
            <div className={styles.liveReady}><span>✓</span><div><b>LIVE READY</b><small>EA v1.03 · Connector v1.0.5 · Web v2</small></div></div>
          </div>
        </div>
      </section>

      <section className={styles.securityStripV2} aria-label="NeoTech Rule Ver 2 capabilities">
        <div className={styles.securityItemV2} data-good="true"><small>{tr("MT5 credential", "Credential MT5")}</small><b>{tr("Stays inside terminal", "Không rời terminal")}</b></div>
        <div className={styles.securityItemV2} data-good="true"><small>{tr("Access model", "Mô hình truy cập")}</small><b>{tr("Read-only recommended", "Khuyến nghị read-only")}</b></div>
        <div className={styles.securityItemV2}><small>{tr("Private workspace", "Workspace riêng")}</small><b>{workspaceRef ? `#${workspaceRef}` : bootRetryIn > 0 ? tr("Unavailable", "Không khả dụng") : tr("Creating…", "Đang tạo…")}</b></div>
        <div className={styles.securityItemV2}><small>{tr("Rule authority", "Nguồn rule")}</small><b>NeoTech · 2024-10-03</b></div>
      </section>

      <section className={styles.rulesetV2}>
        <div className={styles.rulesetV2Header}>
          <div><span className={styles.sectionEyebrow}>RULE ENGINE</span><h2>{tr("14 evaluation criteria", "14 tiêu chí đánh giá")}</h2><p>{tr("E1–E5 eligibility + C1–C9 consistency. Live status appears as soon as an account profile is available.", "E1–E5 điều kiện tham gia + C1–C9 tính nhất quán. Khi có profile, trạng thái live được đổ trực tiếp lên từng rule.")}</p></div>
          <div className={styles.rulesLiveBadge} data-live={profile ? "true" : undefined}><span>{profile ? "✓" : "○"}</span><div><b>{profile ? tr("LIVE PROFILE", "PROFILE LIVE") : tr("RULE PREVIEW", "PREVIEW RULE")}</b><small>{profile ? `${profile.counts.pass} PASS · ${profile.counts.fail} FAIL` : "14 / 14 MAPPED"}</small></div></div>
        </div>
        <div className={styles.ruleConceptGrid}>
          {RULE_CONCEPTS.map((item) => {
            const liveRule = ruleByCode.get(item.code);
            return (
              <article key={item.code} className={styles.ruleConceptCard} data-status={liveRule?.status} data-manual={item.verification === "EXTERNAL" ? "true" : undefined}>
                <div className={styles.ruleConceptTop}><span className={styles.ruleConceptCode}>{item.code}</span><span className={styles.ruleConceptIcon}>{item.icon}</span></div>
                <h3>{locale === "EN" ? item.en : item.vi}</h3>
                <p>{locale === "EN" ? item.thresholdEn : item.thresholdVi}</p>
                <div className={styles.ruleConceptFooter}>
                  {liveRule ? <StatusPill status={liveRule.status} locale={locale} /> : <span className={styles.autoBadge} data-external={item.verification === "EXTERNAL" ? "true" : undefined}>{item.verification === "AUTO" ? "AUTO CHECK" : "EXTERNAL CHECK"}</span>}
                  {liveRule && <small title={liveRule.measured}>{liveRule.measured}</small>}
                </div>
              </article>
            );
          })}
        </div>
        <div className={styles.sessionPanelV2}>
          <div className={styles.sessionCopy}><span className={styles.sectionEyebrow}>C5 SESSION MAP</span><h3>{tr("NeoTech trading sessions", "Quy ước phiên giao dịch NeoTech")}</h3><p>{tr("Server-local session windows. Summer = Apr–Oct; Winter = Nov–Mar. If a signal falls inside an overlap, it belongs to the previous session.", "Cửa sổ tính theo giờ server. Mùa Hè = Tháng 4–10; Mùa Đông = Tháng 11–3. Nếu tín hiệu nằm trong vùng giao hai phiên, tín hiệu được tính vào phiên trước.")}</p></div>
          <div className={styles.sessionTracks}>
            {SESSION_CONCEPTS.map((session) => <div key={session.code} className={styles.sessionTrack} data-session={session.code}><b>{session.code}</b><span>{tr("Summer", "Hè")} {session.summer}</span><span>{tr("Winter", "Đông")} {session.winter}</span></div>)}
          </div>
        </div>
      </section>

      {error && <div className={styles.error} role="alert">{error}{bootRetryIn > 0 && ` · ${tr("retrying in", "thử lại sau")} ${bootRetryIn}s`}</div>}
      {toastPortal}

      {loading ? <div className={styles.loading}><span className={styles.waiting}><span className={styles.spinner} /> {tr("Opening private workspace…", "Đang mở private workspace…")}</span></div> : accounts.length === 0 ? (
        <section className={styles.emptyState}>
          <strong>{tr("No NeoTech account connected yet.", "Chưa có tài khoản NeoTech nào được kết nối.")}</strong>
          <p>{tr("No registration and no broker password on the website. Investor Password is recommended; Master Password is optional with an explicit warning.", "Không cần đăng ký, không nhập broker password trên web. Investor Password được khuyến nghị; Master Password là tùy chọn có cảnh báo rõ ràng.")}</p>
          <div className={styles.heroActions}><button className={styles.primaryButton} onClick={() => void createPairing("READ_ONLY")} disabled={busy}>{tr("Investor pairing", "Pair bằng Investor")}</button><button className={styles.secondaryButton} onClick={() => void createMasterPairing()} disabled={busy}>{tr("Master pairing", "Pair bằng Master")}</button></div>
        </section>
      ) : (
        <section className={styles.workspace}>
          <aside className={styles.sidebar}>
            <div className={styles.sidebarHeader}><small>NEOTECH ACCOUNTS</small><button className={styles.ghostButton} onClick={() => void createPairing("READ_ONLY")}>＋</button></div>
            {accounts.map((row) => (
              <button key={row.account.id} className={styles.accountButton} data-active={selected?.account.id === row.account.id ? "true" : undefined} onClick={() => setSelectedId(row.account.id)}>
                <b>{row.account.maskedLogin} · {row.account.currency}</b>
                <span>{row.account.broker}</span>
                <span className={styles.accountMeta}><i className={styles.dot} /> {relativeTime(row.account.lastSeenAt, nowMs, locale)}</span>
              </button>
            ))}
          </aside>

          <div className={styles.content}>
            {selected && (
              <section className={styles.panel}>
                <div className={styles.accountHero}>
                  <div>
                    <div className={styles.accountTitle}>
                      <h2>{selected.account.maskedLogin}</h2>
                      {profile ? <StatusPill overall={profile.overall} locale={locale} /> : <StatusPill status="IN_PROGRESS" locale={locale} />}
                      {selected.account.readOnlyVerified ? <span className={styles.statusPill} data-status="PASS">READ ONLY VERIFIED</span> : selected.account.accessMode === "TRADING_CAPABLE_ACCEPTED" ? <span className={styles.statusPill} data-status="IN_PROGRESS">MASTER RISK ACCEPTED</span> : null}
                    </div>
                    <div className={styles.accountDetails}>
                      <span>{selected.account.broker}</span><span>{selected.account.server}</span><span>{selected.account.mode}</span><span>Connector {selected.account.connectorVersion}</span><span>Sync {relativeTime(selected.account.lastSeenAt, nowMs, locale)}</span>
                    </div>
                  </div>
                  <div className={styles.heroActions}><button className={styles.secondaryButton} onClick={() => void openShare()} disabled={busy || !profile}>{tr("Share profile", "Chia sẻ profile")}</button><button className={styles.dangerButton} onClick={revoke} disabled={busy}>Revoke</button><button className={styles.dangerButton} onClick={purge} disabled={busy}>{tr("Delete data", "Xóa dữ liệu")}</button></div>
                </div>
              </section>
            )}

            {!profile ? (
              <section className={styles.emptyState}><strong>{tr("Connector paired — waiting for the first snapshot.", "Connector đã pair — đang chờ snapshot đầu tiên.")}</strong><p>{tr("Keep MT5 online. The visual profile appears as soon as the connector sends its first history/equity snapshot.", "Giữ MT5 online. Visual profile sẽ xuất hiện ngay khi connector gửi history/equity lần đầu.")}</p><span className={styles.waiting}><span className={styles.spinner} /> {tr("Waiting for read-only telemetry…", "Đang chờ telemetry read-only…")}</span></section>
            ) : (
              <>
                <div className={styles.dashboardSectionTitle}><div><span className={styles.sectionEyebrow}>LIVE DASHBOARD</span><h2>{tr("Account discipline preview", "Bảng điều khiển kỷ luật tài khoản")}</h2></div><small>{profile.ruleset}</small></div>
                <section className={styles.metricGrid}>
                  <div className={styles.metric}><small>{tr("Rules passed", "Rule đạt")}</small><strong>{profile.counts.pass}/{profile.rules.length}</strong><span>{profile.counts.fail} {tr("violations", "vi phạm")} · {profile.counts.insufficient + profile.counts.notVerifiable} {tr("without enough evidence", "chưa đủ evidence")}</span></div>
                  <div className={styles.metric}><small>History coverage</small><strong>{profile.coverage.percent.toFixed(1)}%</strong><span>{profile.coverage.historyDays.toFixed(0)} {tr("observed days", "ngày quan sát")}</span></div>
                  <div className={styles.metric}><small>{tr("Largest FDD", "FDD lớn nhất")}</small><strong>{fmtPercent(profile.fdd.maxFloatingLossPct)}</strong><span>Peak-to-trough {fmtPercent(profile.fdd.maxPeakToTroughPct)}</span></div>
                  <div className={styles.metric}><small>{tr("C5 + C6 this month", "C5 + C6 tháng này")}</small><strong>{profile.risk.combinedCurrentMonth}/3</strong><span>{tr("Disqualification risk", "Nguy cơ loại")}: {profile.risk.disqualificationRisk === "YES" ? tr("YES", "CÓ") : profile.risk.disqualificationRisk === "NO" ? tr("NO", "KHÔNG") : tr("UNCLEAR", "CHƯA RÕ")}</span></div>
                </section>

                <section className={styles.visualGrid}>
                  <div className={styles.panel}>
                    <div className={styles.panelHeader}><div><h3>{tr("Rules overview", "Tổng quan rule")}</h3><p>{tr("All 14 NeoTech criteria, including external-verification rules.", "Đủ 14 tiêu chí NeoTech, bao gồm các rule cần xác minh ngoài MT5.")}</p></div><StatusPill overall={profile.overall} locale={locale} /></div>
                    <RuleRadar rules={profile.rules} locale={locale} />
                  </div>
                  <div className={styles.panel}>
                    <div className={styles.panelHeader}><div><h3>Profile snapshot</h3><p>{tr("Rules are recalculated on the server from raw MT5 facts.", "Rule được tính lại trên server từ raw MT5 facts.")}</p></div><span className={styles.statusPill}>UTC {fmtDate(profile.generatedAtUtc, locale)}</span></div>
                    <div className={styles.ruleSummary}>
                      <div className={styles.ruleGroupTitle}><span>Eligibility</span><span>{eligibilityRules.filter((row) => row.status === "PASS").length}/{eligibilityRules.length} {tr("passed", "đạt")}</span></div>
                      <div className={styles.ruleMiniGrid}>{eligibilityRules.map((row) => <RuleMini key={row.code} rule={row} locale={locale} />)}</div>
                      <div className={styles.ruleGroupTitle}><span>Consistency</span><span>{consistencyRules.filter((row) => row.status === "PASS").length}/{consistencyRules.length} {tr("passed", "đạt")}</span></div>
                      <div className={styles.ruleMiniGrid}>{consistencyRules.map((row) => <RuleMini key={row.code} rule={row} locale={locale} />)}</div>
                    </div>
                  </div>
                </section>

                <section className={styles.trendGrid}>
                  <div className={styles.panel}>
                    <div className={styles.panelHeader}><div><h3>30-day return</h3><p>{tr("C2 uses each 30-day window, not the annual average.", "C2 dùng từng cửa sổ 30 ngày, không dùng average năm.")}</p></div><span className={styles.statusPill}>{profile.months.filter((row) => row.status === "PASS").length} {tr("months passed", "tháng đạt")}</span></div>
                    <div className={styles.panelBody}>
                      <div className={styles.monthBars}>
                        {profile.months.slice(-12).map((row) => {
                          const height = Math.min(100, Math.max(7, 18 + Math.abs(row.adjustedReturnPct) * 25));
                          return <div key={row.index} className={styles.monthBarWrap} title={`${tr("Month", "Tháng")} ${row.index + 1}: ${row.adjustedReturnPct.toFixed(2)}%`}><div className={styles.monthBar} data-status={row.status} style={{ height: `${height}%` }} /><small>M{row.index + 1}</small></div>;
                        })}
                      </div>
                    </div>
                  </div>
                  <div className={styles.panel}>
                    <div className={styles.panelHeader}><div><h3>Evidence coverage</h3><p>{tr("Insufficient data is never inferred as PASS.", "Không đủ dữ liệu sẽ không bao giờ được suy đoán thành PASS.")}</p></div></div>
                    <div className={styles.coverageBox}>
                      <div className={styles.coverageRing} style={{ background: `conic-gradient(var(--oak-accent-command) ${Math.min(100, profile.coverage.percent)}%, var(--oak-bg-raised) 0)` } as CSSProperties}><span><strong>{profile.coverage.percent.toFixed(0)}%</strong><small>HISTORY</small></span></div>
                      <div>{profile.coverage.missingReasons.length ? <ul className={styles.missingList}>{profile.coverage.missingReasons.map((reason) => <li key={reason}>{reason}</li>)}</ul> : <span className={styles.statusPill} data-status="PASS">{tr("Full coverage", "Coverage đầy đủ")}</span>}</div>
                    </div>
                  </div>
                </section>

                <section className={styles.panel}>
                  <div className={styles.panelHeader}><div><h3>Rule breakdown</h3><p>{tr("Open each rule to inspect the measured value, threshold, and technical evidence.", "Mở từng rule để xem giá trị đo, threshold và evidence kỹ thuật.")}</p></div></div>
                  <div className={styles.panelBody}><RuleDetails rules={profile.rules} locale={locale} /></div>
                </section>
              </>
            )}
          </div>
        </section>
      )}

      {shareOpen && selected && (
        <div className={styles.pairingOverlay} onMouseDown={(event) => event.target === event.currentTarget && setShareOpen(false)}>
          <div ref={shareDialogRef} className={styles.pairingModal} role="dialog" aria-modal="true" aria-label={tr("Share NeoTech profile", "Chia sẻ NeoTech profile")} tabIndex={-1}>
            <div className={styles.pairingHeader}><div><h3>{tr("Share NeoTech profile", "Chia sẻ NeoTech profile")}</h3><p>{tr("Create revocable read-only links for this profile. Each link expires after 30 days.", "Tạo link chỉ đọc có thể revoke cho profile này. Mỗi link tự hết hạn sau 30 ngày.")}</p></div><button className={styles.ghostButton} onClick={() => setShareOpen(false)}>{tr("Close", "Đóng")}</button></div>
            <div className={styles.pairingBody}>
              <div className={styles.sharePrivacy}><b>{tr("Privacy boundary", "Giới hạn dữ liệu share")}</b><span>{tr("Shared viewers see masked account identity, rule status, coverage, FDD and percentage aggregates only. Workspace IDs, MT5 credentials, connector tokens, raw trades, ticket IDs and cash amounts remain private.", "Người xem chỉ thấy account đã mask, trạng thái rule, coverage, FDD và tỷ lệ tổng hợp. Workspace ID, MT5 credential, connector token, raw trade, ticket ID và số tiền vẫn riêng tư.")}</span></div>
              <div className={styles.heroActions}><button className={styles.primaryButton} onClick={() => void createShare()} disabled={shareBusy || !profile}>{shareBusy ? tr("Working…", "Đang xử lý…") : tr("Create 30-day share link", "Tạo share link 30 ngày")}</button>{shareLinks.length > 0 && <button className={styles.dangerButton} onClick={() => void revokeAllShareLinks()} disabled={shareBusy}>{tr("Revoke all", "Revoke tất cả")}</button>}</div>
              {shareUrl && <div className={styles.shareSecretBox}><small>{tr("This secret URL is shown only now. Copy it before closing; the server stores only its SHA-256 hash.", "URL bí mật này chỉ hiển thị lúc vừa tạo. Hãy copy trước khi đóng; server chỉ lưu SHA-256 hash.")}</small><div className={styles.codeBox}><div className={styles.shareUrlText}>{shareUrl}</div><button className={styles.secondaryButton} onClick={() => void copy(shareUrl, tr("Share link copied", "Đã copy share link"))}>Copy</button></div></div>}
              <div className={styles.shareListHeader}><b>{tr("Active share links", "Share link đang hoạt động")}</b><span>{shareLinks.length}</span></div>
              {shareBusy && shareLinks.length === 0 ? <div className={styles.waiting}><span className={styles.spinner} /> {tr("Loading links…", "Đang tải link…")}</div> : shareLinks.length === 0 ? <div className={styles.shareEmpty}>{tr("No active share links.", "Chưa có share link đang hoạt động.")}</div> : <div className={styles.shareList}>{shareLinks.map((link) => <div className={styles.shareRow} key={link.id}><div><b>#{link.id.slice(0, 8)}</b><span>{tr("Created", "Tạo")} {fmtDateTimeMs(link.createdAt, locale)} · {tr("Expires", "Hết hạn")} {fmtDateTimeMs(link.expiresAt, locale)}</span></div><button className={styles.dangerButton} onClick={() => void revokeShareLink(link.id)} disabled={shareBusy}>{tr("Revoke", "Revoke")}</button></div>)}</div>}
            </div>
          </div>
        </div>
      )}

      {masterConsentOpen && (
        <div className={styles.pairingOverlay} onMouseDown={(event) => event.target === event.currentTarget && setMasterConsentOpen(false)}>
          <div ref={masterConsentDialogRef} className={styles.pairingModal} role="alertdialog" aria-modal="true" aria-labelledby="master-pairing-title" aria-describedby="master-pairing-description" tabIndex={-1}>
            <div className={styles.pairingHeader}><div><h3 id="master-pairing-title">{tr("MASTER PASSWORD WARNING", "CẢNH BÁO MASTER PASSWORD")}</h3><p id="master-pairing-description">{tr("This MT5 session can trade. OAK never receives or stores your password and the connector has no trading functions, but Investor Password remains safer.", "Phiên MT5 này có quyền giao dịch. OAK không nhận hoặc lưu password và connector không có chức năng đặt lệnh, nhưng Investor Password vẫn an toàn hơn.")}</p></div><button type="button" className={styles.ghostButton} onClick={() => setMasterConsentOpen(false)}>{tr("Close", "Đóng")}</button></div>
            <div className={styles.pairingBody}>
              <div className={styles.masterWarning}><b>{tr("Explicit acceptance required", "Cần xác nhận rõ ràng")}</b><span>{tr("Continue only if you intentionally logged this terminal in with the Master Password.", "Chỉ tiếp tục nếu bạn chủ động đăng nhập terminal này bằng Master Password.")}</span></div>
              <div className={styles.heroActions}><button type="button" className={styles.primaryButton} onClick={() => void confirmMasterPairing()} disabled={busy}>{busy ? tr("Working…", "Đang xử lý…") : tr("Accept risk and create code", "Chấp nhận rủi ro và tạo code")}</button><button type="button" className={styles.secondaryButton} onClick={() => setMasterConsentOpen(false)} disabled={busy}>{tr("Cancel", "Hủy")}</button></div>
            </div>
          </div>
        </div>
      )}

      {pairing && (
        <div className={styles.pairingOverlay} onMouseDown={(event) => event.target === event.currentTarget && setPairing(null)}>
          <div ref={pairingDialogRef} className={styles.pairingModal} role="dialog" aria-modal="true" aria-label={tr("Connect MT5 NeoTech", "Kết nối MT5 NeoTech")} tabIndex={-1}>
            <div className={styles.pairingHeader}><div><h3>{tr("Connect MT5 in 3 steps", "Kết nối MT5 trong 3 bước")}</h3><p>{tr("The pairing code is single-use and expires automatically after 10 minutes.", "Pairing code dùng một lần và tự hết hạn sau 10 phút.")}</p></div><button className={styles.ghostButton} onClick={() => setPairing(null)}>{tr("Close", "Đóng")}</button></div>
            <div className={styles.pairingBody}>
              {pairing.accessMode === "TRADING_CAPABLE_ACCEPTED" && <div className={styles.masterWarning}><b>{tr("Master Password risk accepted", "Đã chấp nhận rủi ro Master Password")}</b><span>{tr("This terminal can trade. OAK does not receive the password and the connector has no trading functions, but Investor Password remains the safer mode.", "Terminal này có quyền giao dịch. OAK không nhận password và connector không có chức năng đặt lệnh, nhưng Investor Password vẫn là chế độ an toàn hơn.")}</span></div>}
              <div className={styles.codeBox}><div><code>{pairing.code}</code><small>{pairing.accessMode === "READ_ONLY" ? tr("Investor / read-only", "Investor / read-only") : tr("Master access accepted", "Master đã chấp nhận")} · {tr("Remaining", "Còn")} {Math.floor(secondsLeft / 60)}:{String(secondsLeft % 60).padStart(2, "0")}</small></div><button className={styles.secondaryButton} onClick={() => void copy(pairing.code, tr("Pairing code copied", "Đã copy pairing code"))}>Copy</button></div>
              <div className={styles.steps}>
                <div className={styles.step}><div><b>{pairing.accessMode === "READ_ONLY" ? tr("Log in to MT5 with the Investor Password", "Đăng nhập MT5 bằng Investor Password") : tr("Log in to MT5 with the Master Password", "Đăng nhập MT5 bằng Master Password")}</b><p>{tr("Never enter the password on this website. The pairing code itself records which capability mode you explicitly selected.", "Không bao giờ nhập password lên website. Pairing code ghi nhận đúng chế độ quyền mà bạn đã chủ động chọn.")}</p></div></div>
                <div className={styles.step}><div><b>{tr("Download the connector and allow WebRequest", "Tải connector và cho phép WebRequest")}</b><p>{tr("Place the .ex5 file in MQL5/Experts, refresh Navigator, then add this URL in Tools → Options → Expert Advisors. The .mq5 source is public for independent audit.", "Đặt file .ex5 vào MQL5/Experts, refresh Navigator, rồi thêm URL này trong Tools → Options → Expert Advisors. Source .mq5 được công khai để tự audit.")}</p><span className={styles.urlBox}>https://www.oakgatekeeper.uk <button className={styles.ghostButton} onClick={() => void copy("https://www.oakgatekeeper.uk", tr("WebRequest URL copied", "Đã copy URL WebRequest"))}>Copy</button></span><div className={styles.heroActions}><a className={styles.secondaryButton} href="/downloads/OAK_NeoTech_ReadOnly_Connector.ex5" download>{tr("Download .ex5", "Tải .ex5")}</a><a className={styles.secondaryButton} href="/downloads/OAK_NeoTech_ReadOnly_Connector.mq5" download>{tr("View source", "Xem source")}</a><a className={styles.secondaryButton} href="/downloads/OAK_NeoTech_ReadOnly_Connector.sha256.txt" download>SHA-256</a></div></div></div>
                <div className={styles.step}><div><b>{tr("Attach the EA and enter the pairing code", "Attach EA và nhập pairing code")}</b><p>{tr("Attach OAK_NeoTech_ReadOnly_Connector to any chart and enter the code above. The connector stores its ingest token locally and sends telemetry only; it contains no trading functions.", "Gắn OAK_NeoTech_ReadOnly_Connector vào chart bất kỳ, nhập code phía trên. Connector lưu token ingest cục bộ và chỉ gửi telemetry; source không có chức năng đặt lệnh.")}</p></div></div>
              </div>
              <div className={styles.waiting}><span className={styles.spinner} /> {tr("Waiting for connector… the profile opens automatically when the account appears.", "Đang chờ connector… profile sẽ mở tự động khi account xuất hiện.")}</div>
              {secondsLeft <= 0 && <div className={styles.error}>{tr("Pairing code expired. Close this dialog and create a new code.", "Pairing code đã hết hạn. Đóng cửa sổ và tạo code mới.")}</div>}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
