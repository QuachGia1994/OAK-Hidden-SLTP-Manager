"use client";

import { useState, type FormEvent } from "react";
import { useLocale } from "@/components/LocaleProvider";
import type { NeoTechPublicStatus } from "@/lib/neotech-public-domain";
import type { NeoTechLinkedProfile } from "@/lib/neotech-profile-link";
import styles from "./neotech.module.css";

const STATUS_LABEL = {
  EN: { PASS: "Pass", FAIL: "Violation", IN_PROGRESS: "Tracking", INSUFFICIENT_DATA: "Insufficient data", NOT_VERIFIABLE: "Not verifiable" },
  VN: { PASS: "Đạt", FAIL: "Vi phạm", IN_PROGRESS: "Đang theo dõi", INSUFFICIENT_DATA: "Thiếu dữ liệu", NOT_VERIFIABLE: "Chưa xác minh" },
} as const;

function statusLabel(status: NeoTechPublicStatus, locale: "EN" | "VN"): string {
  return STATUS_LABEL[locale][status];
}

function statusColor(status: NeoTechPublicStatus): string {
  return status === "PASS" ? "good" : status === "FAIL" ? "bad" : status === "IN_PROGRESS" ? "pending" : "muted";
}

function overallLabel(profile: NeoTechLinkedProfile, locale: "EN" | "VN"): string {
  if (locale === "EN") return { CLEAR: "Clear", TRACKING: "Tracking", INSUFFICIENT_DATA: "Insufficient data", VIOLATION: "Violation" }[profile.overall];
  return { CLEAR: "Đang đạt", TRACKING: "Đang theo dõi", INSUFFICIENT_DATA: "Thiếu dữ liệu", VIOLATION: "Có vi phạm" }[profile.overall];
}

async function readJson(response: Response): Promise<Record<string, unknown>> {
  return response.json().catch(() => ({})) as Promise<Record<string, unknown>>;
}

export function NeoTechProfileLinkInspector() {
  const { locale } = useLocale();
  const tr = (en: string, vi: string) => locale === "EN" ? en : vi;
  const [url, setUrl] = useState("");
  const [profile, setProfile] = useState<NeoTechLinkedProfile | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const inspect = async (event?: FormEvent) => {
    event?.preventDefault();
    const value = url.trim();
    if (!value) {
      setError(tr("Paste a NeoTech share profile URL first.", "Hãy dán link profile NeoTech trước."));
      return;
    }
    setBusy(true);
    setError("");
    try {
      const response = await fetch("/api/neotech/public/profile-url?url=" + encodeURIComponent(value), { cache: "no-store" });
      const body = await readJson(response);
      if (body.profile && typeof body.profile === "object") setProfile(body.profile as NeoTechLinkedProfile);
      if (!response.ok || body.ok !== true) throw new Error(String(body.error || tr("Cannot inspect this profile.", "Không thể soi profile này.")));
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : tr("Cannot inspect this profile.", "Không thể soi profile này."));
    } finally {
      setBusy(false);
    }
  };

  const counts = profile?.counts;
  return (
    <section className={styles.linkInspector} aria-labelledby="neotech-link-inspector-title">
      <div className={styles.linkInspectorHeader}>
        <div>
          <span className={styles.eyebrow}>◌ NeoTech · Public share inspector</span>
          <h2 id="neotech-link-inspector-title">{tr("Inspect any shared profile", "Soi profile được share")}</h2>
          <p>{tr("Paste the link from NeoTech's analysis site to see the full rule set, visual status and violations.", "Dán link từ web analysis NeoTech để xem đủ bộ rule, trạng thái trực quan và các vi phạm.")}</p>
        </div>
        <span className={styles.linkInspectorBadge}>READ-ONLY</span>
      </div>

      <form className={styles.linkInspectorForm} onSubmit={inspect}>
        <label htmlFor="neotech-profile-url">{tr("NeoTech profile URL", "Link profile NeoTech")}</label>
        <div className={styles.linkInspectorInputRow}>
          <input
            id="neotech-profile-url"
            type="url"
            inputMode="url"
            autoComplete="url"
            value={url}
            onChange={(event) => setUrl(event.target.value)}
            placeholder="https://analysis.neotechltd.com/trader/fxce-mt5-demo/<uuid>?t=0"
            aria-describedby="neotech-profile-url-help"
          />
          <button className={styles.primaryButton} type="submit" disabled={busy}>{busy ? tr("Inspecting…", "Đang soi…") : tr("Inspect profile", "Soi profile")}</button>
        </div>
        <small id="neotech-profile-url-help">{tr("Only HTTPS links on analysis.neotechltd.com/trader/<provider>/<uuid> are accepted.", "Chỉ nhận link HTTPS dạng analysis.neotechltd.com/trader/<provider>/<uuid>.")}</small>
      </form>

      {error && <div className={styles.linkInspectorError} role="alert">{error}</div>}

      {profile && (
        <div className={styles.linkInspectorResult}>
          <div className={styles.linkInspectorIdentity}>
            <div>
              <span className={styles.eyebrow}>PROFILE / {profile.providerSlug}</span>
              <h3>{profile.title}</h3>
              <p>{profile.account.label} · {profile.account.broker} · {profile.account.server} · {profile.account.mode}</p>
            </div>
            <div className={styles.linkInspectorActions}>
              <span className={styles.linkOverall} data-status={statusColor(profile.overall === "CLEAR" ? "PASS" : profile.overall === "VIOLATION" ? "FAIL" : profile.overall === "TRACKING" ? "IN_PROGRESS" : "INSUFFICIENT_DATA")}>{overallLabel(profile, locale)}</span>
              <a href={profile.sourceUrl} target="_blank" rel="noreferrer">↗ {tr("Open source", "Mở link gốc")}</a>
            </div>
          </div>

          <div className={styles.linkMetrics}>
            <div><small>{tr("Rules passed", "Rule đạt")}</small><strong>{counts?.pass ?? 0}/{profile.rules.length}</strong><span>{counts?.fail ?? 0} {tr("violations", "vi phạm")}</span></div>
            <div><small>{tr("Need attention", "Cần lưu ý")}</small><strong>{(counts?.inProgress ?? 0) + (counts?.insufficient ?? 0) + (counts?.notVerifiable ?? 0)}</strong><span>{tr("tracking / missing evidence", "đang theo dõi / thiếu evidence")}</span></div>
            <div><small>Coverage</small><strong>{profile.coverage.percent === null ? "—" : profile.coverage.percent.toFixed(1) + "%"}</strong><span>{profile.coverage.historyDays === null ? tr("not published", "chưa công bố") : profile.coverage.historyDays.toFixed(0) + " " + tr("days", "ngày")}</span></div>
            <div><small>{tr("Data source", "Nguồn dữ liệu")}</small><strong>{profile.upstream.parser === "embedded-json" ? "JSON" : profile.upstream.parser === "visible-markup" ? "HTML" : "—"}</strong><span>{profile.upstream.status} · {profile.upstream.warning || tr("parsed", "đã phân tích")}</span></div>
          </div>

          <div className={styles.linkLegend} aria-label={tr("Rule status legend", "Chú giải trạng thái rule")}>
            {(["PASS", "FAIL", "IN_PROGRESS", "INSUFFICIENT_DATA", "NOT_VERIFIABLE"] as const).map((status) => <span key={status} data-status={statusColor(status)}><i />{statusLabel(status, locale)}</span>)}
          </div>

          <div className={styles.linkRuleGrid}>
            {profile.rules.map((rule) => (
              <details key={rule.code} className={styles.linkRuleCard}>
                <summary>
                  <span className={styles.linkRuleCode}>{rule.code}</span>
                  <span><b>{rule.title}</b><small>{rule.group === "ELIGIBILITY" ? tr("Eligibility", "Điều kiện") : tr("Consistency", "Tính nhất quán")}</small></span>
                  <strong data-status={statusColor(rule.status)}>{statusLabel(rule.status, locale)}</strong>
                </summary>
                <div className={styles.linkRuleDetail}>
                  <p>{rule.summary || tr("No summary published.", "Profile chưa công bố mô tả.")}</p>
                  <div><span><small>{tr("Measured", "Đo được")}</small><b>{rule.measured}</b></span><span><small>{tr("Threshold", "Ngưỡng")}</small><b>{rule.threshold}</b></span></div>
                  {rule.evidence.length > 0 && <ul>{rule.evidence.map((item, index) => <li key={rule.code + "-" + index}>{item}</li>)}</ul>}
                </div>
              </details>
            ))}
          </div>
          <small className={styles.linkInspectorFootnote}>{tr("The complete 12-rule set is always shown. A rule without upstream evidence is marked Not verifiable, never Pass.", "Luôn hiển thị đủ 12 rule. Rule không có evidence từ upstream sẽ là Chưa xác minh, không tự gán Đạt.")}</small>
        </div>
      )}
    </section>
  );
}
