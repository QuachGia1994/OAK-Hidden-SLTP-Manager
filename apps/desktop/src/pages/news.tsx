import { useCallback, useEffect, useRef, useState } from "react";
import { request, IpcError } from "../ipc/bridge";
import type { LocalNewsItem, LocalNewsResult } from "../ipc/types";
import { useLocale } from "../contexts";

/**
 * Read-only economic-news page — the desktop counterpart of the website
 * briefing. oak-core parses the local `news_cache_<locale>.json` written by
 * the signal stack; this page never fetches a feed, never writes storage and
 * never shows a workstation date as the broker day. When the broker clock is
 * unverified the freshness is reported as unknown instead of being guessed.
 */
/** The cache is refreshed at most once per briefing; poll gently. */
const REFRESH_MS = 60000;
/** Columns: time · currency · impact · headline. */
const NEWS_COLUMNS = "78px 72px 132px 1fr";

type Notice = Record<"EN" | "VN", string>;

/** Machine codes from oak-core, rendered as human text (unknown codes pass through). */
const WARNING_TEXT: Record<string, Notice> = {
  news_cache_unavailable: {
    EN: "No local news cache found — run the Signal Bot briefing to create one.",
    VN: "Không tìm thấy bộ nhớ đệm tin tức cục bộ — chạy bản tin của Signal Bot để tạo.",
  },
  news_cache_malformed: {
    EN: "The news cache file is malformed; nothing was read from it.",
    VN: "Tệp bộ nhớ đệm tin tức bị hỏng; không đọc được nội dung.",
  },
  news_cache_empty: {
    EN: "The cache holds no usable events for this language.",
    VN: "Bộ nhớ đệm không có sự kiện hợp lệ cho ngôn ngữ này.",
  },
  malformed_lines_dropped: {
    EN: "Some cached lines could not be parsed and were dropped.",
    VN: "Một số dòng trong bộ nhớ đệm không đọc được và đã bị bỏ qua.",
  },
  item_limit_reached: {
    EN: "Only the first 100 events are shown.",
    VN: "Chỉ hiển thị 100 sự kiện đầu tiên.",
  },
  cache_date_unknown: {
    EN: "The cache has no date, so its freshness cannot be checked.",
    VN: "Bộ nhớ đệm không có ngày nên không kiểm tra được độ mới.",
  },
};

/** The clock notice owns its own block, so it is not repeated in the list. */
const HIDDEN_WARNINGS = new Set(["broker_clock_unverified"]);

function impactTone(impact: LocalNewsItem["impact"]): string {
  if (impact === "high") return "error";
  if (impact === "medium") return "warn";
  return "neutral";
}

function impactLabel(impact: LocalNewsItem["impact"], vn: boolean): string {
  if (impact === "high") return vn ? "CAO" : "HIGH";
  if (impact === "medium") return vn ? "TRUNG BÌNH" : "MEDIUM";
  return vn ? "THẤP" : "LOW";
}

function freshness(news: LocalNewsResult | null, vn: boolean): { tone: string; label: string } {
  if (!news || news.stale === null) {
    return { tone: "warn", label: vn ? "ĐỘ MỚI CHƯA RÕ" : "FRESHNESS UNKNOWN" };
  }
  return news.stale
    ? { tone: "error", label: vn ? "DỮ LIỆU CŨ" : "STALE" }
    : { tone: "ok", label: vn ? "ĐÚNG NGÀY BROKER" : "CURRENT BROKER DAY" };
}

export function NewsPage() {
  const { locale } = useLocale();
  const vn = locale === "VN";
  const [news, setNews] = useState<LocalNewsResult | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [updatedAt, setUpdatedAt] = useState<number | null>(null);
  const inFlight = useRef(false);

  // A silent poll keeps the rendered rows and the refresh button untouched so
  // the page never blanks between ticks.
  const load = useCallback(async (silent = false) => {
    if (inFlight.current) return;
    inFlight.current = true;
    if (!silent) {
      setLoading(true);
      setError(null);
    }
    try {
      const result = await request<LocalNewsResult>("news.local", { locale });
      setNews(result);
      setUpdatedAt(Date.now());
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

  // One interval per locale — cleared on change and on unmount.
  useEffect(() => {
    const timer = window.setInterval(() => void load(true), REFRESH_MS);
    return () => window.clearInterval(timer);
  }, [load]);

  const fresh = freshness(news, vn);
  const clockVerified = news?.broker_clock_verified === true;
  const notices = (news?.warnings ?? []).filter((code) => !HIDDEN_WARNINGS.has(code));
  const items = news?.items ?? [];

  return (
    <main className="content">
      <div className="page-heading">
        <div>
          <p className="eyebrow">{vn ? "BỘ NHỚ ĐỆM TIN TỨC CỤC BỘ" : "LOCAL NEWS CACHE"}</p>
          <h1>{vn ? "Tin tức" : "News"}</h1>
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
          <h2>{vn ? "Nguồn và độ mới" : "Source and freshness"}</h2>
          <span className={`badge ${fresh.tone}`}>{fresh.label}</span>
        </div>
        <dl className="kv">
          <dt>{vn ? "ngày bộ nhớ đệm" : "cache date"}</dt>
          <dd className="mono">{news?.cache_date ?? "—"}</dd>
          <dt>{vn ? "phiên bản" : "cache version"}</dt>
          <dd className="mono">{news?.cache_version != null ? `v${news.cache_version}` : "—"}</dd>
          <dt>{vn ? "ngày broker" : "broker date"}</dt>
          <dd className="mono">{news?.broker_date ?? "—"}</dd>
          <dt>{vn ? "nguồn" : "source"}</dt>
          <dd className="mono">{news?.source ?? "—"}</dd>
          <dt>{vn ? "ngôn ngữ" : "language"}</dt>
          <dd className="mono">{news?.locale ?? locale}</dd>
          <dt>{vn ? "cập nhật lúc" : "read at"}</dt>
          <dd className="mono">
            {updatedAt ? new Date(updatedAt).toLocaleTimeString() : vn ? "chưa có" : "none"}
          </dd>
        </dl>
        {!clockVerified && (
          <p className="hint">
            {vn
              ? "Bot chưa đóng dấu đồng hồ Broker đã xác minh, nên không thể kết luận tin tức còn mới hay đã cũ. Giờ máy trạm không được dùng thay thế."
              : "The bot has not stamped a verified broker clock, so freshness cannot be judged. Workstation time is never substituted."}
          </p>
        )}
        {news?.stale === true && (
          <p className="hint">
            {vn
              ? "Ngày của bộ nhớ đệm không khớp ngày broker đã xác minh gần nhất; danh sách có thể không phải phiên hôm nay."
              : "The cache date does not match the last verified broker day; this list may not describe today's session."}
          </p>
        )}
        {notices.length > 0 && (
          <ul className="muted small">
            {notices.map((code) => (
              <li key={code}>{WARNING_TEXT[code]?.[locale] ?? code}</li>
            ))}
          </ul>
        )}
        <p className="muted small">
          {vn
            ? "Chỉ đọc: trang này đọc tệp bộ nhớ đệm cục bộ, không tải tin mới và không cần khóa API."
            : "Read-only: this page reads the local cache file; it never fetches a feed and needs no API key."}
        </p>
      </section>

      <section className="panel">
        <div className="panel-heading">
          <h2>{vn ? "SỰ KIỆN KINH TẾ" : "ECONOMIC EVENTS"}</h2>
          <span className="muted mono">{news ? news.count : "—"}</span>
        </div>
        {items.length === 0 ? (
          <div className="empty-state">
            <p>
              {loading && !news
                ? (vn ? "Đang tải…" : "Loading…")
                : news?.available === false
                  ? (vn
                    ? "Chưa có tệp bộ nhớ đệm tin tức cho ngôn ngữ này."
                    : "No news cache file for this language yet.")
                  : vn
                    ? "Không có sự kiện quan trọng nào trong bộ nhớ đệm."
                    : "No important events in the cache."}
            </p>
          </div>
        ) : (
          <div className="table">
            <div className="table-head" style={{ gridTemplateColumns: NEWS_COLUMNS }}>
              <span>{vn ? "Giờ" : "Time"}</span>
              <span>{vn ? "Tiền tệ" : "Currency"}</span>
              <span>{vn ? "Mức độ" : "Impact"}</span>
              <span>{vn ? "Sự kiện" : "Event"}</span>
            </div>
            {items.map((item, index) => (
              <div
                key={`${item.date ?? "?"}-${item.time}-${item.currency}-${index}`}
                className="trade-row neutral"
                style={{ gridTemplateColumns: NEWS_COLUMNS }}
              >
                <span className="mono">{item.time}</span>
                <span className="mono">{item.currency}</span>
                <span>
                  <span className={`badge ${impactTone(item.impact)}`}>{impactLabel(item.impact, vn)}</span>
                </span>
                <span className="truncate" title={item.title}>
                  {item.critical && (
                    <span className="badge error">{vn ? "NỔI BẬT" : "CRITICAL"}</span>
                  )}{" "}
                  {item.title}
                </span>
              </div>
            ))}
          </div>
        )}
      </section>
    </main>
  );
}
