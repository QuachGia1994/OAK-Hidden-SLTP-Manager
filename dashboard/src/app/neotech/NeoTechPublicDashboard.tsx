"use client";

import { useCallback, useEffect, useMemo, useRef, useState, type CSSProperties } from "react";
import { useLocale } from "@/components/LocaleProvider";
import { useDialogFocusTrap } from "@/hooks/useDialogFocusTrap";
import type { NeoTechPublicProfile, NeoTechPublicRule, NeoTechPublicStatus } from "@/lib/neotech-public-domain";
import styles from "./neotech.module.css";

type PublicAccount = {
  id: string;
  maskedLogin: string;
  broker: string;
  server: string;
  currency: string;
  mode: string;
  readOnlyVerified: boolean;
  connectorVersion: string;
  createdAt: number;
  lastSeenAt: number;
};

type AccountRow = { account: PublicAccount; profile: NeoTechPublicProfile | null };
type PairingState = { code: string; expiresAt: number; baselineCount: number };

type Locale = "EN" | "VN";

const STATUS_LABEL: Record<Locale, Record<NeoTechPublicStatus, string>> = {
  EN: { PASS: "Pass", FAIL: "Violation", IN_PROGRESS: "Tracking", INSUFFICIENT_DATA: "Insufficient data", NOT_VERIFIABLE: "Not verifiable" },
  VN: { PASS: "Đạt", FAIL: "Vi phạm", IN_PROGRESS: "Đang theo dõi", INSUFFICIENT_DATA: "Thiếu dữ liệu", NOT_VERIFIABLE: "Không thể xác minh" },
};

const OVERALL_LABEL: Record<Locale, Record<NeoTechPublicProfile["overall"], string>> = {
  EN: { CLEAR: "Clear", TRACKING: "Tracking", INSUFFICIENT_DATA: "Insufficient data", VIOLATION: "Violation" },
  VN: { CLEAR: "Đang đạt", TRACKING: "Đang theo dõi", INSUFFICIENT_DATA: "Thiếu dữ liệu", VIOLATION: "Có vi phạm" },
};

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
      <svg className={styles.radar} viewBox={`0 0 ${size} ${size}`} role="img" aria-label={locale === "EN" ? `NeoTech rule profile score ${average} out of 100` : `Điểm hồ sơ rule NeoTech ${average} trên 100`}>
        {[.25, .5, .75, 1].map((scale) => <polygon key={scale} points={polygon(scale)} className={styles.radarGrid} />)}
        {rules.map((row, index) => {
          const [x, y] = point(index, 1);
          return <line key={`axis-${row.code}`} x1={center} y1={center} x2={x} y2={y} className={styles.radarAxis} />;
        })}
        <polygon points={scorePolygon} className={styles.radarShape} />
        {rules.map((row, index) => {
          const [x, y] = point(index, row.score / 100);
          return <circle key={`point-${row.code}`} cx={x} cy={y} r="4" className={styles.radarPoint} data-status={row.status} />;
        })}
        {rules.map((row, index) => {
          const [x, y] = point(index, 1.14);
          const anchor = x < center - 8 ? "end" : x > center + 8 ? "start" : "middle";
          return <text key={row.code} x={x} y={y} textAnchor={anchor} dominantBaseline="middle" className={styles.radarLabel}>{row.code}</text>;
        })}
      </svg>
      <div className={styles.radarCenter}><strong>{average}</strong><small>PROFILE / 100</small></div>
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
  const [copyStatus, setCopyStatus] = useState("");
  const [pairing, setPairing] = useState<PairingState | null>(null);
  const [nowMs, setNowMs] = useState(Date.now());
  const pairingDialogRef = useDialogFocusTrap<HTMLDivElement>(Boolean(pairing), () => setPairing(null));
  const selectedRef = useRef(selectedId);
  selectedRef.current = selectedId;

  const refreshAccounts = useCallback(async (silent = false) => {
    try {
      const response = await fetch("/api/neotech/public/accounts", { cache: "no-store" });
      const body = await readJson(response);
      if (!response.ok || body.ok !== true) {
        if (!silent) setError(String(body.error || (locale === "EN" ? "Cannot load NeoTech accounts." : "Không đọc được tài khoản NeoTech.")));
        return;
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
    } catch {
      if (!silent) setError(locale === "EN" ? "Cannot connect to the NeoTech workspace." : "Không thể kết nối NeoTech workspace.");
    }
  }, [locale]);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const response = await fetch("/api/neotech/public/session", { cache: "no-store" });
        const body = await readJson(response);
        if (!response.ok || body.ok !== true) throw new Error(String(body.error || "workspace unavailable"));
        if (!cancelled) setWorkspaceRef(String(body.workspaceRef || "private"));
        await refreshAccounts(true);
      } catch (cause) {
        if (!cancelled) setError(cause instanceof Error ? cause.message : (locale === "EN" ? "Cannot create the private workspace." : "Không thể tạo private workspace."));
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => { cancelled = true; };
  }, [refreshAccounts]);

  useEffect(() => {
    const timer = window.setInterval(() => {
      setNowMs(Date.now());
      void refreshAccounts(true);
    }, pairing ? 4000 : 15000);
    return () => window.clearInterval(timer);
  }, [pairing, refreshAccounts]);

  const selected = useMemo(() => accounts.find((row) => row.account.id === selectedId) || accounts[0] || null, [accounts, selectedId]);
  const profile = selected?.profile || null;

  const createPairing = async () => {
    setBusy(true); setError("");
    try {
      const response = await fetch("/api/neotech/public/pairing", { method: "POST", headers: { "Content-Type": "application/json" }, body: "{}" });
      const body = await readJson(response);
      if (!response.ok || body.ok !== true) throw new Error(String(body.error || (locale === "EN" ? "Cannot create pairing code." : "Không tạo được pairing code.")));
      setPairing({ code: String(body.pairingCode), expiresAt: Number(body.expiresAt), baselineCount: accounts.length });
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : (locale === "EN" ? "Cannot create pairing code." : "Không tạo được pairing code."));
    } finally { setBusy(false); }
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

  const copy = async (value: string) => {
    try {
      if (!navigator.clipboard) throw new Error("clipboard unavailable");
      await navigator.clipboard.writeText(value);
      setCopyStatus(locale === "EN" ? "Copied" : "Đã copy");
    } catch {
      setCopyStatus(locale === "EN" ? "Copy failed" : "Copy thất bại");
    }
    window.setTimeout(() => setCopyStatus(""), 1800);
  };
  const secondsLeft = pairing ? Math.max(0, Math.floor((pairing.expiresAt - nowMs) / 1000)) : 0;

  return (
    <div className={styles.page}>
      <section className={styles.hero}>
        <div className={styles.heroCopy}>
          <span className={styles.eyebrow}>◉ NeoTech · Read-only intelligence</span>
          <h1>{tr("Visual profile for", "Visual profile cho")} <span>{tr("account discipline.", "kỷ luật tài khoản.")}</span></h1>
          <p>{tr("Connect MT5 with an Investor Password. OAK receives only the required telemetry, calculates NeoTech rules on the server, and never asks for the Master Trading Password.", "Kết nối MT5 bằng Investor Password. OAK chỉ nhận telemetry cần thiết, tự tính rule NeoTech trên server và không bao giờ yêu cầu Master Trading Password.")}</p>
          <div className={styles.heroActions}>
            <button className={styles.primaryButton} onClick={createPairing} disabled={busy}>{accounts.length ? tr("+ Connect account", "+ Kết nối tài khoản") : tr("Connect MT5 read-only", "Kết nối MT5 read-only")}</button>
            <a className={styles.secondaryButton} href="/downloads/OAK_NeoTech_ReadOnly_Connector.ex5" download>{tr("Download connector", "Tải connector")}</a>
            <a className={styles.secondaryButton} href="/downloads/OAK_NeoTech_ReadOnly_Connector.mq5" download>{tr("Source for audit", "Source để audit")}</a>
          </div>
        </div>
        <div className={styles.heroPanel}>
          <div className={styles.trustRow}><span className={styles.trustIcon}>R/O</span><span><b>Broker-level read only</b><small>{tr("Pairing is rejected while MT5 still has trading permission.", "Pairing bị từ chối nếu MT5 còn quyền trade.")}</small></span></div>
          <div className={styles.trustRow}><span className={styles.trustIcon}>0×</span><span><b>{tr("No password stored", "Không lưu password")}</b><small>{tr("The Investor Password stays inside the user's MT5 terminal.", "Investor Password chỉ nằm trong terminal MT5 của khách.")}</small></span></div>
          <div className={styles.trustRow}><span className={styles.trustIcon}>↯</span><span><b>{tr("Instant revoke", "Revoke tức thì")}</b><small>{tr("Each connector has its own token; only the hash is stored on the server.", "Mỗi connector có token riêng, chỉ lưu hash ở server.")}</small></span></div>
        </div>
      </section>

      <section className={styles.securityStrip} aria-label="Security guarantees">
        <div className={styles.securityItem} data-good="true"><small>MT5 credential</small><b>{tr("Stays in terminal", "Không rời terminal")}</b></div>
        <div className={styles.securityItem} data-good="true"><small>Trading capability</small><b>{tr("Rejected by server", "Server từ chối")}</b></div>
        <div className={styles.securityItem}><small>Private workspace</small><b>{workspaceRef ? `#${workspaceRef}` : tr("Creating…", "Đang tạo…")}</b></div>
        <div className={styles.securityItem}><small>Rule authority</small><b>Server-side only</b></div>
      </section>

      {error && <div className={styles.error}>{error}</div>}
      {copyStatus && <div className={styles.copyStatus} role="status" aria-live="polite">{copyStatus}</div>}

      {loading ? <div className={styles.loading}><span className={styles.waiting}><span className={styles.spinner} /> {tr("Opening private workspace…", "Đang mở private workspace…")}</span></div> : accounts.length === 0 ? (
        <section className={styles.emptyState}>
          <strong>{tr("No read-only account yet.", "Chưa có tài khoản read-only.")}</strong>
          <p>{tr("No registration and no broker password on the website. Create a pairing code and attach the connector to an MT5 terminal logged in with the Investor Password.", "Không cần đăng ký, không cần nhập broker password trên web. Tạo pairing code và gắn connector vào một MT5 đang đăng nhập bằng Investor Password.")}</p>
          <button className={styles.primaryButton} onClick={createPairing} disabled={busy}>{tr("Create pairing code", "Tạo pairing code")}</button>
        </section>
      ) : (
        <section className={styles.workspace}>
          <aside className={styles.sidebar}>
            <div className={styles.sidebarHeader}><small>READ-ONLY ACCOUNTS</small><button className={styles.ghostButton} onClick={createPairing}>＋</button></div>
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
                      {selected.account.readOnlyVerified && <span className={styles.statusPill} data-status="PASS">READ ONLY VERIFIED</span>}
                    </div>
                    <div className={styles.accountDetails}>
                      <span>{selected.account.broker}</span><span>{selected.account.server}</span><span>{selected.account.mode}</span><span>Connector {selected.account.connectorVersion}</span><span>Sync {relativeTime(selected.account.lastSeenAt, nowMs, locale)}</span>
                    </div>
                  </div>
                  <div className={styles.heroActions}><button className={styles.dangerButton} onClick={revoke} disabled={busy}>Revoke</button><button className={styles.dangerButton} onClick={purge} disabled={busy}>{tr("Delete data", "Xóa dữ liệu")}</button></div>
                </div>
              </section>
            )}

            {!profile ? (
              <section className={styles.emptyState}><strong>{tr("Connector paired — waiting for the first snapshot.", "Connector đã pair — đang chờ snapshot đầu tiên.")}</strong><p>{tr("Keep MT5 online. The visual profile appears as soon as the connector sends its first history/equity snapshot.", "Giữ MT5 online. Visual profile sẽ xuất hiện ngay khi connector gửi history/equity lần đầu.")}</p><span className={styles.waiting}><span className={styles.spinner} /> {tr("Waiting for read-only telemetry…", "Đang chờ telemetry read-only…")}</span></section>
            ) : (
              <>
                <section className={styles.metricGrid}>
                  <div className={styles.metric}><small>{tr("Rules passed", "Rule đạt")}</small><strong>{profile.counts.pass}/{profile.rules.length}</strong><span>{profile.counts.fail} {tr("violations", "vi phạm")} · {profile.counts.insufficient + profile.counts.notVerifiable} {tr("without enough evidence", "chưa đủ evidence")}</span></div>
                  <div className={styles.metric}><small>History coverage</small><strong>{profile.coverage.percent.toFixed(1)}%</strong><span>{profile.coverage.historyDays.toFixed(0)} {tr("observed days", "ngày quan sát")}</span></div>
                  <div className={styles.metric}><small>{tr("Largest FDD", "FDD lớn nhất")}</small><strong>{fmtPercent(profile.fdd.maxFloatingLossPct)}</strong><span>Peak-to-trough {fmtPercent(profile.fdd.maxPeakToTroughPct)}</span></div>
                  <div className={styles.metric}><small>{tr("C5 + C6 this month", "C5 + C6 tháng này")}</small><strong>{profile.risk.combinedCurrentMonth}/3</strong><span>{tr("Disqualification risk", "Nguy cơ loại")}: {profile.risk.disqualificationRisk === "YES" ? tr("YES", "CÓ") : profile.risk.disqualificationRisk === "NO" ? tr("NO", "KHÔNG") : tr("UNCLEAR", "CHƯA RÕ")}</span></div>
                </section>

                <section className={styles.visualGrid}>
                  <div className={styles.panel}>
                    <div className={styles.panelHeader}><div><h3>Rule orbit</h3><p>{tr("12 technical rules tracked by the engine.", "12 rule kỹ thuật đang được engine theo dõi.")}</p></div><StatusPill overall={profile.overall} locale={locale} /></div>
                    <RuleRadar rules={profile.rules} locale={locale} />
                  </div>
                  <div className={styles.panel}>
                    <div className={styles.panelHeader}><div><h3>Profile snapshot</h3><p>{tr("Rules are recalculated on the server from raw MT5 facts.", "Rule được tính lại trên server từ raw MT5 facts.")}</p></div><span className={styles.statusPill}>UTC {fmtDate(profile.generatedAtUtc, locale)}</span></div>
                    <div className={styles.ruleSummary}>
                      <div className={styles.ruleGroupTitle}><span>Eligibility</span><span>{profile.rules.filter((row) => row.group === "ELIGIBILITY" && row.status === "PASS").length}/4 {tr("passed", "đạt")}</span></div>
                      <div className={styles.ruleMiniGrid}>{profile.rules.filter((row) => row.group === "ELIGIBILITY").map((row) => <RuleMini key={row.code} rule={row} locale={locale} />)}</div>
                      <div className={styles.ruleGroupTitle}><span>Consistency</span><span>{profile.rules.filter((row) => row.group === "CONSISTENCY" && row.status === "PASS").length}/8 {tr("passed", "đạt")}</span></div>
                      <div className={styles.ruleMiniGrid}>{profile.rules.filter((row) => row.group === "CONSISTENCY").map((row) => <RuleMini key={row.code} rule={row} locale={locale} />)}</div>
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

      {pairing && (
        <div className={styles.pairingOverlay} onMouseDown={(event) => event.target === event.currentTarget && setPairing(null)}>
          <div ref={pairingDialogRef} className={styles.pairingModal} role="dialog" aria-modal="true" aria-label={tr("Connect MT5 read-only", "Kết nối MT5 read-only")} tabIndex={-1}>
            <div className={styles.pairingHeader}><div><h3>{tr("Connect MT5 in 3 steps", "Kết nối MT5 trong 3 bước")}</h3><p>{tr("The pairing code is single-use and expires automatically after 10 minutes.", "Pairing code dùng một lần và tự hết hạn sau 10 phút.")}</p></div><button className={styles.ghostButton} onClick={() => setPairing(null)}>{tr("Close", "Đóng")}</button></div>
            <div className={styles.pairingBody}>
              <div className={styles.codeBox}><div><code>{pairing.code}</code><small>{tr("Remaining", "Còn")} {Math.floor(secondsLeft / 60)}:{String(secondsLeft % 60).padStart(2, "0")}</small></div><button className={styles.secondaryButton} onClick={() => void copy(pairing.code)}>Copy</button></div>
              <div className={styles.steps}>
                <div className={styles.step}><div><b>{tr("Log in to MT5 with the Investor Password", "Đăng nhập MT5 bằng Investor Password")}</b><p>{tr("Do not enter the password on the website. OAK rejects pairing while the terminal reports", "Không nhập password lên website. OAK sẽ từ chối pairing nếu terminal còn")} <code>ACCOUNT_TRADE_ALLOWED=true</code>.</p></div></div>
                <div className={styles.step}><div><b>{tr("Download the connector and allow WebRequest", "Tải connector và cho phép WebRequest")}</b><p>{tr("Place the .ex5 file in MQL5/Experts, refresh Navigator, then add this URL in Tools → Options → Expert Advisors. The .mq5 source is public for independent audit.", "Đặt file .ex5 vào MQL5/Experts, refresh Navigator, rồi thêm URL này trong Tools → Options → Expert Advisors. Source .mq5 được công khai để tự audit.")}</p><span className={styles.urlBox}>https://www.oakgatekeeper.uk <button className={styles.ghostButton} onClick={() => void copy("https://www.oakgatekeeper.uk")}>Copy</button></span><div className={styles.heroActions}><a className={styles.secondaryButton} href="/downloads/OAK_NeoTech_ReadOnly_Connector.ex5" download>{tr("Download .ex5", "Tải .ex5")}</a><a className={styles.secondaryButton} href="/downloads/OAK_NeoTech_ReadOnly_Connector.mq5" download>{tr("View source", "Xem source")}</a><a className={styles.secondaryButton} href="/downloads/OAK_NeoTech_ReadOnly_Connector.sha256.txt" download>SHA-256</a></div></div></div>
                <div className={styles.step}><div><b>{tr("Attach the EA and enter the pairing code", "Attach EA và nhập pairing code")}</b><p>{tr("Attach OAK_NeoTech_ReadOnly_Connector to any chart and enter the code above. The connector pairs itself, stores the ingest token locally, and sends read-only snapshots.", "Gắn OAK_NeoTech_ReadOnly_Connector vào chart bất kỳ, nhập code phía trên. Connector tự pair, lưu token ingest cục bộ và gửi snapshot read-only.")}</p></div></div>
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
