"use client";

import { useCallback, useEffect, useState, type CSSProperties } from "react";
import { useLocale } from "@/components/LocaleProvider";
import type { NeoTechPublicStatus, NeoTechSharedProfile } from "@/lib/neotech-public-domain";
import styles from "../neotech.module.css";

type Locale = "EN" | "VN";
type SharedRule = NeoTechSharedProfile["rules"][number];
type ShareMetadata = { id: string; createdAt: number; expiresAt: number; revokedAt: number | null };

const STATUS_LABEL: Record<Locale, Record<NeoTechPublicStatus, string>> = {
  EN: { PASS: "Pass", FAIL: "Violation", IN_PROGRESS: "Tracking", INSUFFICIENT_DATA: "Insufficient data", NOT_VERIFIABLE: "Not verifiable" },
  VN: { PASS: "Đạt", FAIL: "Vi phạm", IN_PROGRESS: "Đang theo dõi", INSUFFICIENT_DATA: "Thiếu dữ liệu", NOT_VERIFIABLE: "Không thể xác minh" },
};

const OVERALL_LABEL: Record<Locale, Record<NeoTechSharedProfile["overall"], string>> = {
  EN: { CLEAR: "Clear", TRACKING: "Tracking", INSUFFICIENT_DATA: "Insufficient data", VIOLATION: "Violation" },
  VN: { CLEAR: "Đang đạt", TRACKING: "Đang theo dõi", INSUFFICIENT_DATA: "Thiếu dữ liệu", VIOLATION: "Có vi phạm" },
};

async function readJson(response: Response): Promise<Record<string, unknown>> {
  return response.json().catch(() => ({})) as Promise<Record<string, unknown>>;
}

function relativeTime(epochMs: number, nowMs: number, locale: Locale): string {
  const seconds = Math.max(0, Math.floor((nowMs - epochMs) / 1000));
  if (seconds < 10) return locale === "EN" ? "just now" : "vừa xong";
  if (seconds < 60) return locale === "EN" ? `${seconds}s ago` : `${seconds} giây trước`;
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return locale === "EN" ? `${minutes}m ago` : `${minutes} phút trước`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return locale === "EN" ? `${hours}h ago` : `${hours} giờ trước`;
  return locale === "EN" ? `${Math.floor(hours / 24)}d ago` : `${Math.floor(hours / 24)} ngày trước`;
}

function fmtDate(epochMs: number, locale: Locale): string {
  return new Intl.DateTimeFormat(locale === "EN" ? "en-GB" : "vi-VN", { day: "2-digit", month: "2-digit", year: "numeric", hour: "2-digit", minute: "2-digit" }).format(new Date(epochMs));
}

function fmtPercent(value: number | null, digits = 2): string {
  return value === null || !Number.isFinite(value) ? "—" : `${value.toFixed(digits)}%`;
}

function StatusPill({ status, overall, locale }: { status?: NeoTechPublicStatus; overall?: NeoTechSharedProfile["overall"]; locale: Locale }) {
  const label = status ? STATUS_LABEL[locale][status] : overall ? OVERALL_LABEL[locale][overall] : "—";
  return <span className={styles.statusPill} data-status={status} data-overall={overall}>{label}</span>;
}

function RuleRadar({ rules, locale }: { rules: SharedRule[]; locale: Locale }) {
  const size = 340;
  const center = size / 2;
  const radius = 118;
  const count = Math.max(1, rules.length);
  const point = (index: number, scale: number) => {
    const angle = -Math.PI / 2 + index * Math.PI * 2 / count;
    return [center + Math.cos(angle) * radius * scale, center + Math.sin(angle) * radius * scale] as const;
  };
  const polygon = (scale: number) => rules.map((_, index) => point(index, scale).join(",")).join(" ");
  const scorePolygon = rules.map((row, index) => point(index, row.score / 100).join(",")).join(" ");
  const average = rules.length ? Math.round(rules.reduce((sum, row) => sum + row.score, 0) / rules.length) : 0;
  return (
    <div className={styles.radarWrap}>
      <svg className={styles.radar} viewBox={`0 0 ${size} ${size}`} role="img" aria-label={locale === "EN" ? `NeoTech profile score ${average} out of 100` : `Điểm profile NeoTech ${average} trên 100`}>
        {[.25, .5, .75, 1].map((scale) => <polygon key={scale} points={polygon(scale)} className={styles.radarGrid} />)}
        {rules.map((row, index) => { const [x, y] = point(index, 1); return <line key={`axis-${row.code}`} x1={center} y1={center} x2={x} y2={y} className={styles.radarAxis} />; })}
        <polygon points={scorePolygon} className={styles.radarShape} />
        {rules.map((row, index) => { const [x, y] = point(index, row.score / 100); return <circle key={`point-${row.code}`} cx={x} cy={y} r="4" className={styles.radarPoint} data-status={row.status} />; })}
        {rules.map((row, index) => { const [x, y] = point(index, 1.14); const anchor = x < center - 8 ? "end" : x > center + 8 ? "start" : "middle"; return <text key={row.code} x={x} y={y} textAnchor={anchor} dominantBaseline="middle" className={styles.radarLabel}>{row.code}</text>; })}
      </svg>
      <div className={styles.radarCenter}><strong>{average}</strong><small>PROFILE / 100</small></div>
    </div>
  );
}

export function NeoTechSharedDashboard() {
  const { locale } = useLocale();
  const tr = (en: string, vi: string) => locale === "EN" ? en : vi;
  const [profile, setProfile] = useState<NeoTechSharedProfile | null>(null);
  const [share, setShare] = useState<ShareMetadata | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [nowMs, setNowMs] = useState(Date.now());
  const [token, setToken] = useState<string | null>(null);

  useEffect(() => { setToken(window.location.hash.replace(/^#/, "")); }, []);

  const refresh = useCallback(async (silent = false) => {
    if (token === null) return;
    if (!token) {
      if (!silent) setError(tr("This share link is incomplete.", "Link chia sẻ không đầy đủ."));
      setLoading(false);
      return;
    }
    try {
      const response = await fetch("/api/neotech/public/shared-profile", { cache: "no-store", headers: { Authorization: `Bearer ${token}` } });
      const body = await readJson(response);
      if (!response.ok || body.ok !== true) {
        const message = tr("This share link is expired, revoked, or unavailable.", "Link chia sẻ đã hết hạn, bị revoke hoặc không còn khả dụng.");
        if (response.status === 404) {
          setProfile(null);
          setShare(null);
          setError(message);
        } else if (!silent) setError(message);
        return;
      }
      setProfile(body.profile as NeoTechSharedProfile);
      setShare(body.share as ShareMetadata);
      setError("");
    } catch (cause) {
      if (!silent) setError(cause instanceof Error ? cause.message : tr("Cannot open shared profile.", "Không mở được shared profile."));
    } finally {
      setLoading(false);
    }
  }, [token, locale]);

  useEffect(() => { if (token !== null) void refresh(); }, [refresh, token]);
  useEffect(() => {
    if (token === null) return;
    const timer = window.setInterval(() => { setNowMs(Date.now()); void refresh(true); }, 20_000);
    return () => window.clearInterval(timer);
  }, [refresh]);

  if (loading) return <div className={styles.page}><div className={styles.loading}><span className={styles.waiting}><span className={styles.spinner} /> {tr("Opening shared NeoTech profile…", "Đang mở NeoTech profile được chia sẻ…")}</span></div></div>;

  if (!profile || !share || error) {
    return <div className={styles.page}><section className={styles.emptyState}><strong>{tr("Shared profile unavailable", "Shared profile không khả dụng")}</strong><p>{error || tr("The owner may have revoked this link.", "Chủ profile có thể đã revoke link này.")}</p><a className={styles.secondaryButton} href="/neotech">NeoTech</a></section></div>;
  }

  return (
    <div className={styles.page}>
      <section className={styles.sharedHero}>
        <div>
          <span className={styles.eyebrow}>◉ NeoTech · Shared read-only profile</span>
          <h1>{profile.account.maskedLogin} <span>· {profile.account.currency}</span></h1>
          <p>{profile.account.broker} · {profile.account.server} · {profile.account.mode}</p>
        </div>
        <div className={styles.sharedTrust}><b>{tr("READ-ONLY SHARED VIEW", "CHẾ ĐỘ CHIA SẺ CHỈ ĐỌC")}</b><span>{tr("No workspace access, MT5 credential, connector token, raw trades, or trading controls are exposed.", "Không lộ workspace, MT5 credential, connector token, raw trade hay bất kỳ trading control nào.")}</span></div>
      </section>

      <section className={styles.securityStrip} aria-label="Shared profile status">
        <div className={styles.securityItem}><small>{tr("Overall", "Tổng quan")}</small><StatusPill overall={profile.overall} locale={locale} /></div>
        <div className={styles.securityItem}><small>{tr("Last MT5 sync", "MT5 sync gần nhất")}</small><b>{relativeTime(profile.account.lastSeenAt, nowMs, locale)}</b></div>
        <div className={styles.securityItem}><small>{tr("Link expires", "Link hết hạn")}</small><b>{fmtDate(share.expiresAt, locale)}</b></div>
        <div className={styles.securityItem}><small>{tr("Refresh", "Cập nhật")}</small><b>{tr("Live · 20s", "Live · 20 giây")}</b></div>
      </section>

      <section className={styles.metricGrid}>
        <div className={styles.metric}><small>{tr("Rules passed", "Rule đạt")}</small><strong>{profile.counts.pass}/{profile.rules.length}</strong><span>{profile.counts.fail} {tr("violations", "vi phạm")}</span></div>
        <div className={styles.metric}><small>History coverage</small><strong>{profile.coverage.percent.toFixed(1)}%</strong><span>{profile.coverage.historyDays.toFixed(0)} {tr("observed days", "ngày quan sát")}</span></div>
        <div className={styles.metric}><small>{tr("Largest FDD", "FDD lớn nhất")}</small><strong>{fmtPercent(profile.fdd.maxFloatingLossPct)}</strong><span>Peak-to-trough {fmtPercent(profile.fdd.maxPeakToTroughPct)}</span></div>
        <div className={styles.metric}><small>{tr("C5 + C6 this month", "C5 + C6 tháng này")}</small><strong>{profile.risk.combinedCurrentMonth}/3</strong><span>{tr("Risk", "Nguy cơ")}: {profile.risk.disqualificationRisk}</span></div>
      </section>

      <section className={styles.visualGrid}>
        <div className={styles.panel}>
          <div className={styles.panelHeader}><div><h3>Rule orbit</h3><p>{tr("Server-authoritative NeoTech rule state.", "Trạng thái rule NeoTech do server tính.")}</p></div><StatusPill overall={profile.overall} locale={locale} /></div>
          <RuleRadar rules={profile.rules} locale={locale} />
        </div>
        <div className={styles.panel}>
          <div className={styles.panelHeader}><div><h3>{tr("Rule snapshot", "Rule snapshot")}</h3><p>{tr("Detailed trade identifiers and raw evidence are intentionally hidden in shared mode.", "Ticket và raw evidence được chủ động ẩn trong chế độ share.")}</p></div></div>
          <div className={styles.ruleMiniGrid}>{profile.rules.map((rule) => <div key={rule.code} className={styles.ruleMini}><div className={styles.ruleMiniTop}><span className={styles.ruleCode}>{rule.code}</span><StatusPill status={rule.status} locale={locale} /></div><b>{rule.title}</b><small>{rule.measured}</small></div>)}</div>
        </div>
      </section>

      <section className={styles.trendGrid}>
        <div className={styles.panel}>
          <div className={styles.panelHeader}><div><h3>30-day return</h3><p>{tr("Only percentage aggregates are shared; capital and cash-flow amounts stay private.", "Chỉ share tỷ lệ tổng hợp; vốn và số tiền nạp/rút vẫn riêng tư.")}</p></div></div>
          <div className={styles.panelBody}><div className={styles.monthBars}>{profile.months.slice(-12).map((row) => { const height = Math.min(100, Math.max(7, 18 + Math.abs(row.adjustedReturnPct) * 25)); return <div key={row.index} className={styles.monthBarWrap} title={`M${row.index + 1}: ${row.adjustedReturnPct.toFixed(2)}%`}><div className={styles.monthBar} data-status={row.status} style={{ height: `${height}%` }} /><small>M{row.index + 1}</small></div>; })}</div></div>
        </div>
        <div className={styles.panel}>
          <div className={styles.panelHeader}><div><h3>Evidence coverage</h3><p>{tr("Missing evidence is never displayed as PASS.", "Thiếu evidence không bao giờ được hiển thị thành PASS.")}</p></div></div>
          <div className={styles.coverageBox}><div className={styles.coverageRing} style={{ background: `conic-gradient(var(--oak-accent-command) ${Math.min(100, profile.coverage.percent)}%, var(--oak-bg-raised) 0)` } as CSSProperties}><span><strong>{profile.coverage.percent.toFixed(0)}%</strong><small>HISTORY</small></span></div><div>{profile.coverage.missingReasons.length ? <ul className={styles.missingList}>{profile.coverage.missingReasons.map((reason) => <li key={reason}>{reason}</li>)}</ul> : <span className={styles.statusPill} data-status="PASS">{tr("Full coverage", "Coverage đầy đủ")}</span>}</div></div>
        </div>
      </section>

      <section className={styles.panel}>
        <div className={styles.panelHeader}><div><h3>{tr("Rule breakdown", "Chi tiết rule")}</h3><p>{tr("Measured values and thresholds only; sensitive evidence remains private to the owner.", "Chỉ hiển thị measured value và threshold; evidence nhạy cảm chỉ owner được xem.")}</p></div></div>
        <div className={styles.panelBody}><div className={styles.ruleList}>{profile.rules.map((rule) => <details key={rule.code} className={styles.ruleCard}><summary><span className={styles.ruleBadge}>{rule.code}</span><span><h4>{rule.title}</h4><p>{rule.summary}</p></span><StatusPill status={rule.status} locale={locale} /></summary><div className={styles.ruleDetail}><div className={styles.ruleFacts}><div className={styles.ruleFact}><small>{tr("Measured", "Đo được")}</small><b>{rule.measured}</b></div><div className={styles.ruleFact}><small>{tr("NeoTech threshold", "Ngưỡng NeoTech")}</small><b>{rule.threshold}</b></div></div></div></details>)}</div></div>
      </section>
    </div>
  );
}
