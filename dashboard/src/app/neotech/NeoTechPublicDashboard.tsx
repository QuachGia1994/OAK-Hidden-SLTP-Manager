"use client";

import { useCallback, useEffect, useMemo, useRef, useState, type CSSProperties } from "react";
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

const STATUS_LABEL: Record<NeoTechPublicStatus, string> = {
  PASS: "Đạt",
  FAIL: "Vi phạm",
  IN_PROGRESS: "Đang theo dõi",
  INSUFFICIENT_DATA: "Thiếu dữ liệu",
  NOT_VERIFIABLE: "Không thể xác minh",
};

const OVERALL_LABEL: Record<NeoTechPublicProfile["overall"], string> = {
  CLEAR: "Đang đạt",
  TRACKING: "Đang theo dõi",
  INSUFFICIENT_DATA: "Thiếu dữ liệu",
  VIOLATION: "Có vi phạm",
};

async function readJson(response: Response): Promise<Record<string, unknown>> {
  return response.json().catch(() => ({})) as Promise<Record<string, unknown>>;
}

function fmtPercent(value: number | null, digits = 2): string {
  return value === null || !Number.isFinite(value) ? "—" : `${value.toFixed(digits)}%`;
}

function fmtDate(epochSeconds: number): string {
  if (!epochSeconds) return "—";
  return new Intl.DateTimeFormat("vi-VN", { day: "2-digit", month: "2-digit", year: "2-digit" }).format(new Date(epochSeconds * 1000));
}

function relativeTime(epochMs: number, nowMs: number): string {
  const seconds = Math.max(0, Math.floor((nowMs - epochMs) / 1000));
  if (seconds < 10) return "vừa xong";
  if (seconds < 60) return `${seconds} giây trước`;
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `${minutes} phút trước`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours} giờ trước`;
  return `${Math.floor(hours / 24)} ngày trước`;
}

function StatusPill({ status, overall }: { status?: NeoTechPublicStatus; overall?: NeoTechPublicProfile["overall"] }) {
  const label = status ? STATUS_LABEL[status] : overall ? OVERALL_LABEL[overall] : "—";
  return <span className={styles.statusPill} data-status={status} data-overall={overall}>{label}</span>;
}

function RuleRadar({ rules }: { rules: NeoTechPublicRule[] }) {
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
      <svg className={styles.radar} viewBox={`0 0 ${size} ${size}`} role="img" aria-label={`NeoTech rule profile score ${average} trên 100`}>
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

function RuleMini({ rule }: { rule: NeoTechPublicRule }) {
  return (
    <div className={styles.ruleMini}>
      <div className={styles.ruleMiniTop}><span className={styles.ruleCode}>{rule.code}</span><StatusPill status={rule.status} /></div>
      <b>{rule.title}</b>
      <small>{rule.measured}</small>
    </div>
  );
}

function RuleDetails({ rules }: { rules: NeoTechPublicRule[] }) {
  return (
    <div className={styles.ruleList}>
      {rules.map((rule) => (
        <details key={rule.code} className={styles.ruleCard}>
          <summary>
            <span className={styles.ruleBadge}>{rule.code}</span>
            <span><h4>{rule.title}</h4><p>{rule.summary}</p></span>
            <StatusPill status={rule.status} />
          </summary>
          <div className={styles.ruleDetail}>
            <div className={styles.ruleFacts}>
              <div className={styles.ruleFact}><small>Đo được</small><b>{rule.measured}</b></div>
              <div className={styles.ruleFact}><small>Ngưỡng NeoTech</small><b>{rule.threshold}</b></div>
            </div>
            {rule.evidence.length > 0 && <ul className={styles.evidence}>{rule.evidence.map((item, index) => <li key={`${rule.code}-${index}`}>{item}</li>)}</ul>}
          </div>
        </details>
      ))}
    </div>
  );
}

export function NeoTechPublicDashboard() {
  const [workspaceRef, setWorkspaceRef] = useState("");
  const [accounts, setAccounts] = useState<AccountRow[]>([]);
  const [selectedId, setSelectedId] = useState("");
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [pairing, setPairing] = useState<PairingState | null>(null);
  const [nowMs, setNowMs] = useState(Date.now());
  const selectedRef = useRef(selectedId);
  selectedRef.current = selectedId;

  const refreshAccounts = useCallback(async (silent = false) => {
    try {
      const response = await fetch("/api/neotech/public/accounts", { cache: "no-store" });
      const body = await readJson(response);
      if (!response.ok || body.ok !== true) {
        if (!silent) setError(String(body.error || "Không đọc được tài khoản NeoTech."));
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
      if (!silent) setError("Không thể kết nối NeoTech workspace.");
    }
  }, []);

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
        if (!cancelled) setError(cause instanceof Error ? cause.message : "Không thể tạo private workspace.");
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
      if (!response.ok || body.ok !== true) throw new Error(String(body.error || "Không tạo được pairing code."));
      setPairing({ code: String(body.pairingCode), expiresAt: Number(body.expiresAt), baselineCount: accounts.length });
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Không tạo được pairing code.");
    } finally { setBusy(false); }
  };

  const revoke = async () => {
    if (!selected || !window.confirm(`Thu hồi quyền đọc của ${selected.account.maskedLogin}? Connector cũ sẽ bị vô hiệu ngay.`)) return;
    setBusy(true); setError("");
    try {
      const response = await fetch(`/api/neotech/public/accounts?accountId=${encodeURIComponent(selected.account.id)}`, { method: "DELETE" });
      const body = await readJson(response);
      if (!response.ok || body.ok !== true) throw new Error(String(body.error || "Không revoke được connector."));
      setSelectedId("");
      await refreshAccounts();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Không revoke được connector.");
    } finally { setBusy(false); }
  };

  const purge = async () => {
    if (!selected || !window.confirm(`Xóa dữ liệu OAK của ${selected.account.maskedLogin}? Account, visual profile, equity samples và connector sẽ bị xóa khỏi server. Hành động này không thể hoàn tác.`)) return;
    setBusy(true); setError("");
    try {
      const response = await fetch(`/api/neotech/public/accounts?accountId=${encodeURIComponent(selected.account.id)}&purge=1`, { method: "DELETE" });
      const body = await readJson(response);
      if (!response.ok || body.ok !== true) throw new Error(String(body.error || "Không xóa được dữ liệu."));
      setSelectedId("");
      await refreshAccounts();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Không xóa được dữ liệu.");
    } finally { setBusy(false); }
  };

  const copy = (value: string) => { void navigator.clipboard?.writeText(value); };
  const secondsLeft = pairing ? Math.max(0, Math.floor((pairing.expiresAt - nowMs) / 1000)) : 0;

  return (
    <div className={styles.page}>
      <section className={styles.hero}>
        <div className={styles.heroCopy}>
          <span className={styles.eyebrow}>◉ NeoTech · Read-only intelligence</span>
          <h1>Visual profile cho <span>kỷ luật tài khoản.</span></h1>
          <p>Kết nối MT5 bằng Investor Password. OAK chỉ nhận telemetry cần thiết, tự tính rule NeoTech trên server và không bao giờ yêu cầu Master Trading Password.</p>
          <div className={styles.heroActions}>
            <button className={styles.primaryButton} onClick={createPairing} disabled={busy}>{accounts.length ? "+ Kết nối tài khoản" : "Kết nối MT5 read-only"}</button>
            <a className={styles.secondaryButton} href="/downloads/OAK_NeoTech_ReadOnly_Connector.ex5" download>Tải connector</a>
            <a className={styles.secondaryButton} href="/downloads/OAK_NeoTech_ReadOnly_Connector.mq5" download>Source để audit</a>
          </div>
        </div>
        <div className={styles.heroPanel}>
          <div className={styles.trustRow}><span className={styles.trustIcon}>R/O</span><span><b>Broker-level read only</b><small>Pairing bị từ chối nếu MT5 còn quyền trade.</small></span></div>
          <div className={styles.trustRow}><span className={styles.trustIcon}>0×</span><span><b>Không lưu password</b><small>Investor Password chỉ nằm trong terminal MT5 của khách.</small></span></div>
          <div className={styles.trustRow}><span className={styles.trustIcon}>↯</span><span><b>Revoke tức thì</b><small>Mỗi connector có token riêng, chỉ lưu hash ở server.</small></span></div>
        </div>
      </section>

      <section className={styles.securityStrip} aria-label="Security guarantees">
        <div className={styles.securityItem} data-good="true"><small>MT5 credential</small><b>Không rời terminal</b></div>
        <div className={styles.securityItem} data-good="true"><small>Trading capability</small><b>Server từ chối</b></div>
        <div className={styles.securityItem}><small>Private workspace</small><b>{workspaceRef ? `#${workspaceRef}` : "Đang tạo…"}</b></div>
        <div className={styles.securityItem}><small>Rule authority</small><b>Server-side only</b></div>
      </section>

      {error && <div className={styles.error}>{error}</div>}

      {loading ? <div className={styles.loading}><span className={styles.waiting}><span className={styles.spinner} /> Đang mở private workspace…</span></div> : accounts.length === 0 ? (
        <section className={styles.emptyState}>
          <strong>Chưa có tài khoản read-only.</strong>
          <p>Không cần đăng ký, không cần nhập broker password trên web. Tạo pairing code và gắn connector vào một MT5 đang đăng nhập bằng Investor Password.</p>
          <button className={styles.primaryButton} onClick={createPairing} disabled={busy}>Tạo pairing code</button>
        </section>
      ) : (
        <section className={styles.workspace}>
          <aside className={styles.sidebar}>
            <div className={styles.sidebarHeader}><small>READ-ONLY ACCOUNTS</small><button className={styles.ghostButton} onClick={createPairing}>＋</button></div>
            {accounts.map((row) => (
              <button key={row.account.id} className={styles.accountButton} data-active={selected?.account.id === row.account.id ? "true" : undefined} onClick={() => setSelectedId(row.account.id)}>
                <b>{row.account.maskedLogin} · {row.account.currency}</b>
                <span>{row.account.broker}</span>
                <span className={styles.accountMeta}><i className={styles.dot} /> {relativeTime(row.account.lastSeenAt, nowMs)}</span>
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
                      {profile ? <StatusPill overall={profile.overall} /> : <StatusPill status="IN_PROGRESS" />}
                      {selected.account.readOnlyVerified && <span className={styles.statusPill} data-status="PASS">READ ONLY VERIFIED</span>}
                    </div>
                    <div className={styles.accountDetails}>
                      <span>{selected.account.broker}</span><span>{selected.account.server}</span><span>{selected.account.mode}</span><span>Connector {selected.account.connectorVersion}</span><span>Sync {relativeTime(selected.account.lastSeenAt, nowMs)}</span>
                    </div>
                  </div>
                  <div className={styles.heroActions}><button className={styles.dangerButton} onClick={revoke} disabled={busy}>Revoke</button><button className={styles.dangerButton} onClick={purge} disabled={busy}>Xóa dữ liệu</button></div>
                </div>
              </section>
            )}

            {!profile ? (
              <section className={styles.emptyState}><strong>Connector đã pair — đang chờ snapshot đầu tiên.</strong><p>Giữ MT5 online. Visual profile sẽ xuất hiện ngay khi connector gửi history/equity lần đầu.</p><span className={styles.waiting}><span className={styles.spinner} /> Waiting for read-only telemetry…</span></section>
            ) : (
              <>
                <section className={styles.metricGrid}>
                  <div className={styles.metric}><small>Rule đạt</small><strong>{profile.counts.pass}/{profile.rules.length}</strong><span>{profile.counts.fail} vi phạm · {profile.counts.insufficient + profile.counts.notVerifiable} chưa đủ evidence</span></div>
                  <div className={styles.metric}><small>History coverage</small><strong>{profile.coverage.percent.toFixed(1)}%</strong><span>{profile.coverage.historyDays.toFixed(0)} ngày quan sát</span></div>
                  <div className={styles.metric}><small>FDD lớn nhất</small><strong>{fmtPercent(profile.fdd.maxFloatingLossPct)}</strong><span>Peak-to-trough {fmtPercent(profile.fdd.maxPeakToTroughPct)}</span></div>
                  <div className={styles.metric}><small>C5 + C6 tháng này</small><strong>{profile.risk.combinedCurrentMonth}/3</strong><span>Nguy cơ loại: {profile.risk.disqualificationRisk === "YES" ? "CÓ" : profile.risk.disqualificationRisk === "NO" ? "KHÔNG" : "CHƯA RÕ"}</span></div>
                </section>

                <section className={styles.visualGrid}>
                  <div className={styles.panel}>
                    <div className={styles.panelHeader}><div><h3>Rule orbit</h3><p>12 rule kỹ thuật đang được engine theo dõi.</p></div><StatusPill overall={profile.overall} /></div>
                    <RuleRadar rules={profile.rules} />
                  </div>
                  <div className={styles.panel}>
                    <div className={styles.panelHeader}><div><h3>Profile snapshot</h3><p>Rule được tính lại trên server từ raw MT5 facts.</p></div><span className={styles.statusPill}>UTC {fmtDate(profile.generatedAtUtc)}</span></div>
                    <div className={styles.ruleSummary}>
                      <div className={styles.ruleGroupTitle}><span>Eligibility</span><span>{profile.rules.filter((row) => row.group === "ELIGIBILITY" && row.status === "PASS").length}/4 đạt</span></div>
                      <div className={styles.ruleMiniGrid}>{profile.rules.filter((row) => row.group === "ELIGIBILITY").map((row) => <RuleMini key={row.code} rule={row} />)}</div>
                      <div className={styles.ruleGroupTitle}><span>Consistency</span><span>{profile.rules.filter((row) => row.group === "CONSISTENCY" && row.status === "PASS").length}/8 đạt</span></div>
                      <div className={styles.ruleMiniGrid}>{profile.rules.filter((row) => row.group === "CONSISTENCY").map((row) => <RuleMini key={row.code} rule={row} />)}</div>
                    </div>
                  </div>
                </section>

                <section className={styles.trendGrid}>
                  <div className={styles.panel}>
                    <div className={styles.panelHeader}><div><h3>30-day return</h3><p>C2 dùng từng cửa sổ 30 ngày, không dùng average năm.</p></div><span className={styles.statusPill}>{profile.months.filter((row) => row.status === "PASS").length} tháng đạt</span></div>
                    <div className={styles.panelBody}>
                      <div className={styles.monthBars}>
                        {profile.months.slice(-12).map((row) => {
                          const height = Math.min(100, Math.max(7, 18 + Math.abs(row.adjustedReturnPct) * 25));
                          return <div key={row.index} className={styles.monthBarWrap} title={`Tháng ${row.index + 1}: ${row.adjustedReturnPct.toFixed(2)}%`}><div className={styles.monthBar} data-status={row.status} style={{ height: `${height}%` }} /><small>M{row.index + 1}</small></div>;
                        })}
                      </div>
                    </div>
                  </div>
                  <div className={styles.panel}>
                    <div className={styles.panelHeader}><div><h3>Evidence coverage</h3><p>Không đủ dữ liệu sẽ không bao giờ được suy đoán thành PASS.</p></div></div>
                    <div className={styles.coverageBox}>
                      <div className={styles.coverageRing} style={{ background: `conic-gradient(var(--oak-accent-command) ${Math.min(100, profile.coverage.percent)}%, var(--oak-bg-raised) 0)` } as CSSProperties}><span><strong>{profile.coverage.percent.toFixed(0)}%</strong><small>HISTORY</small></span></div>
                      <div>{profile.coverage.missingReasons.length ? <ul className={styles.missingList}>{profile.coverage.missingReasons.map((reason) => <li key={reason}>{reason}</li>)}</ul> : <span className={styles.statusPill} data-status="PASS">Coverage đầy đủ</span>}</div>
                    </div>
                  </div>
                </section>

                <section className={styles.panel}>
                  <div className={styles.panelHeader}><div><h3>Rule breakdown</h3><p>Mở từng rule để xem giá trị đo, threshold và evidence kỹ thuật.</p></div></div>
                  <div className={styles.panelBody}><RuleDetails rules={profile.rules} /></div>
                </section>
              </>
            )}
          </div>
        </section>
      )}

      {pairing && (
        <div className={styles.pairingOverlay} role="dialog" aria-modal="true" aria-label="Kết nối MT5 read-only">
          <div className={styles.pairingModal}>
            <div className={styles.pairingHeader}><div><h3>Kết nối MT5 trong 3 bước</h3><p>Pairing code dùng một lần và tự hết hạn sau 10 phút.</p></div><button className={styles.ghostButton} onClick={() => setPairing(null)}>Đóng</button></div>
            <div className={styles.pairingBody}>
              <div className={styles.codeBox}><div><code>{pairing.code}</code><small>Còn {Math.floor(secondsLeft / 60)}:{String(secondsLeft % 60).padStart(2, "0")}</small></div><button className={styles.secondaryButton} onClick={() => copy(pairing.code)}>Copy</button></div>
              <div className={styles.steps}>
                <div className={styles.step}><div><b>Đăng nhập MT5 bằng Investor Password</b><p>Không nhập password lên website. OAK sẽ từ chối pairing nếu terminal còn <code>ACCOUNT_TRADE_ALLOWED=true</code>.</p></div></div>
                <div className={styles.step}><div><b>Tải connector và cho phép WebRequest</b><p>Đặt file <code>.ex5</code> vào <code>MQL5/Experts</code>, refresh Navigator, rồi thêm URL này trong Tools → Options → Expert Advisors. Source <code>.mq5</code> được công khai để tự audit.</p><span className={styles.urlBox}>https://www.oakgatekeeper.uk <button className={styles.ghostButton} onClick={() => copy("https://www.oakgatekeeper.uk")}>Copy</button></span><div className={styles.heroActions}><a className={styles.secondaryButton} href="/downloads/OAK_NeoTech_ReadOnly_Connector.ex5" download>Tải .ex5</a><a className={styles.secondaryButton} href="/downloads/OAK_NeoTech_ReadOnly_Connector.mq5" download>Xem source</a><a className={styles.secondaryButton} href="/downloads/OAK_NeoTech_ReadOnly_Connector.sha256.txt" download>SHA-256</a></div></div></div>
                <div className={styles.step}><div><b>Attach EA và nhập pairing code</b><p>Gắn <code>OAK_NeoTech_ReadOnly_Connector</code> vào chart bất kỳ, nhập code phía trên. Connector tự pair, lưu token ingest cục bộ và gửi snapshot read-only.</p></div></div>
              </div>
              <div className={styles.waiting}><span className={styles.spinner} /> Đang chờ connector… profile sẽ mở tự động khi account xuất hiện.</div>
              {secondsLeft <= 0 && <div className={styles.error}>Pairing code đã hết hạn. Đóng cửa sổ và tạo code mới.</div>}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
