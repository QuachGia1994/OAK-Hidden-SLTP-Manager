import { useCallback, useEffect, useRef, useState } from "react";
import { request, IpcError } from "../ipc/bridge";
import type { TodayRulesResult } from "../ipc/types";
import { useLocale } from "../contexts";

/**
 * Read-only rule contract for the current broker day. The payload comes from
 * the published contract plus the bot's broker-clock stamp — the workstation
 * clock is never used to invent a broker date, so an unverified clock is
 * reported as such instead of being silently replaced.
 */
/** The contract changes at most once per deployment; poll gently. */
const REFRESH_MS = 60000;

export function RulesPage() {
  const { locale } = useLocale();
  const vn = locale === "VN";
  const [rules, setRules] = useState<TodayRulesResult | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const inFlight = useRef(false);

  const load = useCallback(async (silent = false) => {
    if (inFlight.current) return;
    inFlight.current = true;
    if (!silent) {
      setLoading(true);
      setError(null);
    }
    try {
      const result = await request<TodayRulesResult>("rules.today", { locale });
      setRules(result);
      setError(null);
    } catch (e) {
      setError(e instanceof IpcError ? `${e.code}: ${e.message}` : String(e));
    } finally {
      inFlight.current = false;
      if (!silent) setLoading(false);
    }
  }, [locale]);

  useEffect(() => {
    void load();
  }, [load]);

  useEffect(() => {
    const timer = window.setInterval(() => void load(true), REFRESH_MS);
    return () => window.clearInterval(timer);
  }, [load]);

  const verified = rules?.broker_clock_verified === true;
  const offset = rules?.broker_utc_offset;

  return (
    <main className="content">
      <div className="page-heading">
        <div>
          <p className="eyebrow">{vn ? "HỢP ĐỒNG QUY TẮC ĐÃ CÔNG BỐ" : "PUBLISHED RULE CONTRACT"}</p>
          <h1>{vn ? "Quy tắc hôm nay" : "Rules today"}</h1>
        </div>
        <button type="button" className="btn" onClick={() => void load()} disabled={loading}>
          {loading ? "…" : vn ? "Làm mới" : "Refresh"}
        </button>
      </div>

      {error && (
        <section className="panel error">
          <span className="badge error">ERROR</span>
          <p>{error}</p>
        </section>
      )}

      <section className="panel">
        <div className="panel-heading">
          <h2>{vn ? "Ngày giao dịch của Broker" : "Broker trading day"}</h2>
          <span className={`badge ${verified ? "ok" : "warn"}`}>
            {verified
              ? (vn ? "ĐỒNG HỒ ĐÃ XÁC MINH" : "CLOCK VERIFIED")
              : (vn ? "ĐỒNG HỒ CHƯA XÁC MINH" : "CLOCK UNVERIFIED")}
          </span>
        </div>
        <dl className="kv">
          <dt>{vn ? "ngày broker" : "broker date"}</dt>
          <dd className="mono">{rules?.broker_date ?? "—"}</dd>
          <dt>{vn ? "giờ broker" : "broker time"}</dt>
          <dd className="mono">{rules?.broker_time ?? "—"}</dd>
          <dt>{vn ? "lệch UTC" : "utc offset"}</dt>
          <dd className="mono">{offset === null || offset === undefined ? "—" : `UTC${offset >= 0 ? "+" : ""}${offset}`}</dd>
          <dt>logic</dt>
          <dd className="mono">{rules?.logic_version != null ? `v${rules.logic_version}` : "—"}</dd>
        </dl>
        {!verified && (
          <p className="hint">
            {vn
              ? "Bot chưa đóng dấu đồng hồ Broker đã xác minh. Không dùng giờ máy trạm thay thế — hãy chạy Signal Bot và kiểm tra kết nối MT5."
              : "The bot has not stamped a verified broker clock. Workstation time is never substituted — start the Signal Bot and check the MT5 connection."}
          </p>
        )}
      </section>

      <section className="panel">
        <div className="panel-heading">
          <h2>{vn ? "Khung giờ công bố" : "Published slots"}</h2>
          <span className="muted mono">{rules?.source ?? "—"}</span>
        </div>
        {rules && rules.public_slots.length > 0 ? (
          <div className="ckpt-row">
            {rules.public_slots.map((slot) => (
              <span key={slot} className="checkpoint-badge">H{slot}</span>
            ))}
          </div>
        ) : (
          <p className="muted small">{vn ? "Chưa có khung giờ nào được công bố." : "No published slots."}</p>
        )}
        {rules?.startup_summary && <p className="muted small">{rules.startup_summary}</p>}
      </section>

      <section className="panel">
        <div className="panel-heading">
          <h2>{vn ? "Quy tắc áp dụng" : "Applicable rules"}</h2>
          <span className="muted mono">{rules ? rules.rules.length : "—"}</span>
        </div>
        {rules && rules.rules.length > 0 ? (
          <div className="ckpt-list">
            {rules.rules.map((rule, index) => (
              <div key={`${index}-${rule.slice(0, 24)}`} className="ckpt-row">
                <span className="checkpoint-badge">{index + 1}</span>
                <span>{rule}</span>
              </div>
            ))}
          </div>
        ) : (
          <div className="empty-state">
            <p>
              {loading && !rules
                ? (vn ? "Đang tải…" : "Loading…")
                : rules?.reason === "no_rules_for_locale"
                  ? (vn ? "Hợp đồng quy tắc chưa có bản dịch cho ngôn ngữ này." : "The rule contract has no text for this language.")
                  : vn
                    ? "Không đọc được signal_rule_contract.json — không hiển thị quy tắc suy đoán."
                    : "signal_rule_contract.json is unavailable — no guessed rules are shown."}
            </p>
          </div>
        )}
      </section>
    </main>
  );
}
