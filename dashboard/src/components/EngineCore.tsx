import type { H1SignalPayload } from "@/lib/h1-signals";
import { H1_SCAN_HOURS } from "@/lib/h1-cloud-scanner";
import { OrbitBrandMark } from "@/components/OrbitBrandMark";

type Locale = "EN" | "VN";

function formatPublished(value: string | undefined, locale: Locale) {
  if (!value) return "—";
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return value;
  return parsed.toLocaleString(locale === "EN" ? "en-GB" : "vi-VN", {
    timeZone: "Asia/Ho_Chi_Minh",
    day: "2-digit",
    month: "short",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function hourRange(hours: number[] | undefined) {
  const monitoredHours = hours?.length ? hours : H1_SCAN_HOURS;
  return `H${String(monitoredHours[0]).padStart(2, "0")}–H${String(monitoredHours.at(-1)).padStart(2, "0")}`;
}

export function EngineCore({ data, degraded = false, locale }: { data: H1SignalPayload | null; degraded?: boolean; locale: Locale }) {
  const copy = locale === "EN"
    ? {
        eyebrow: "OAK / ALGORITHMIC INTELLIGENCE",
        title: "H1 LIVE",
        tagline: "Track signals. Trade with discipline.",
        snapshot: data ? "RETAINED DATA" : degraded ? "DATA RECOVERY" : "AWAITING FEED",
        snapshotDetail: data ? "Published" : degraded ? "Storage temporarily unavailable" : "No retained feed loaded",
        source: "DATA SOURCE",
        cadence: "CADENCE",
        retained: "RETAINED DAYS",
        latest: "LATEST BROKER DATE",
        retainedValue: data ? `${Object.keys(data.days).length} days` : "0 days",
        core: "SIGNAL CORE",
        local: "LOCAL M15 → H1",
      }
    : {
        eyebrow: "OAK / TRÍ TUỆ THUẬT TOÁN",
        title: "H1 LIVE",
        tagline: "Bám sát tín hiệu. Giao dịch có kỷ luật.",
        snapshot: data ? "DỮ LIỆU ĐÃ LƯU" : degraded ? "ĐANG KHÔI PHỤC DỮ LIỆU" : "ĐANG CHỜ FEED",
        snapshotDetail: data ? "Đã phát hành" : degraded ? "Kho dữ liệu tạm thời không khả dụng" : "Chưa có feed đã lưu",
        source: "NGUỒN DỮ LIỆU",
        cadence: "NHỊP DỮ LIỆU",
        retained: "NGÀY ĐÃ LƯU",
        latest: "NGÀY MỚI NHẤT",
        retainedValue: data ? `${Object.keys(data.days).length} ngày` : "0 ngày",
        core: "LÕI TÍN HIỆU",
        local: "M15 LOCAL → H1",
      };
  const state = data ? "ready" : degraded ? "degraded" : "waiting";

  return (
    <>
      <section className="engine-command-hero" aria-labelledby="engine-command-title">
        <div className="engine-command-copy">
          <span className="engine-command-eyebrow"><i aria-hidden="true" />{copy.eyebrow}</span>
          <div className="engine-command-title-row">
            <span className="engine-command-index" aria-hidden="true">01</span>
            <h1 id="engine-command-title">{copy.title}</h1>
          </div>
          <p className="engine-command-tagline">{copy.tagline}</p>
          <div className="engine-command-state" data-state={state} aria-live="polite">
            <span className="engine-command-state-pill"><i aria-hidden="true" />{copy.snapshot}</span>
            <span>{copy.snapshotDetail}</span>
            {data?.publishedAt && <time dateTime={data.publishedAt}>{formatPublished(data.publishedAt, locale)} ICT</time>}
          </div>
        </div>
        <div className="engine-core-hero-mark" data-state={state} aria-hidden="true">
          <OrbitBrandMark label="H1" showGrid />
          <span className="engine-core-caption">{copy.core} / {copy.local}</span>
        </div>
      </section>

      <dl className="engine-command-metadata" aria-label={locale === "EN" ? "H1 feed metadata" : "Thông tin feed H1"}>
        <div><dt>{copy.source}</dt><dd>{data?.profile || "MT5 ICMarkets Local"}</dd></div>
        <div><dt>{copy.cadence}</dt><dd>{hourRange(data?.hours)} <span>· M15 → H1</span></dd></div>
        <div><dt>{copy.retained}</dt><dd>{copy.retainedValue}</dd></div>
        <div><dt>{copy.latest}</dt><dd>{data ? Object.keys(data.days).sort().at(-1) || "—" : "—"}</dd></div>
      </dl>
    </>
  );
}
