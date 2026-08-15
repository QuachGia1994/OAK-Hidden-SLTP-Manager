import type { Pattern5Payload, Pattern5Signal, Pattern5Table } from "@/lib/pattern5";

type Locale = "EN" | "VN";

function ictToday() {
  return new Intl.DateTimeFormat("en-CA", {
    timeZone: "Asia/Ho_Chi_Minh",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).format(new Date());
}

function formatPublished(value: string | undefined, locale: Locale) {
  if (!value) return locale === "EN" ? "Waiting for publisher" : "Đang chờ dữ liệu mới";
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
function Cell({ signal, detail }: { signal: Pattern5Signal | ""; detail?: string }) {
  if (!signal) return <span className="pattern5-web-empty">—</span>;
  return (
    <div className="pattern5-web-cell" title={detail || undefined}>
      <span className="pattern5-web-group">{signal.group}</span>
      <b data-side={signal.signal}>{signal.signal}</b>
      <small>{signal.pattern}</small>
    </div>
  );
}

function PairTable({ table, blocks, today }: { table: Pattern5Table; blocks: number[]; today: string }) {
  if (table.error) {
    return <section className="pattern5-web-card"><div className="pattern5-web-error"><b>{table.base}</b><span>{table.error}</span></div></section>;
  }
  const days = table.days ?? [];
  return (
    <section className="pattern5-web-card">
      <div className="pattern5-web-pair-head">
        <div><strong>{table.base}</strong>{table.symbol && table.symbol !== table.base && <span>→ {table.symbol}</span>}</div>
        <span>{blocks.length} blocks</span>
      </div>
      <div className="pattern5-web-scroll lux-scroll">
        <table className="pattern5-web-table">          <thead>
            <tr>
              <th className="pattern5-web-sticky">Block</th>
              {days.map((day) => <th key={day.date} data-today={day.date === today}><span>{day.name}</span><small>{day.display}</small></th>)}
            </tr>
          </thead>
          <tbody>
            {blocks.map((block) => (
              <tr key={block}>
                <th className="pattern5-web-sticky">H{block}</th>
                {(table.rows?.[String(block)] ?? []).map((signal, index) => (
                  <td key={`${block}-${index}`} data-today={days[index]?.date === today}>
                    <Cell signal={signal} detail={table.detail?.[String(block)]?.[index]} />
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}

export function Pattern5Board({ data, locale }: { data: Pattern5Payload | null; locale: Locale }) {
  const today = ictToday();
  const text = locale === "EN"
    ? { kicker: "REMOTE MONITOR", title: "Engine 5 Pattern", subtitle: "Look back 4 H4 candles · keep 3–4 candle Sw/Bt patterns · candle #4 is base: Sw reverses, Bt follows · auto refresh every 20 seconds", empty: "No Pattern5 feed has been published yet.", week: "Week", updated: "Updated" }
    : { kicker: "GIÁM SÁT TỪ XA", title: "Engine 5 Pattern", subtitle: "Lookback 4 nến H4 · giữ pattern Sw/Bt 3–4 cây · cây #4 là base: Sw đảo, Bt giữ chiều · tự làm mới mỗi 20 giây", empty: "Chưa có feed Pattern5 được publish.", week: "Tuần", updated: "Cập nhật" };

  return (
    <div className="pattern5-web-screen">
      <header className="pattern5-web-hero">
        <div>
          <p className="terminal-kicker">{text.kicker}</p>
          <h1>{text.title}</h1>
          <p>{text.subtitle}</p>
        </div>
        {data && <div className="pattern5-web-meta"><span><small>Profile</small><b>{data.profile}</b></span><span><small>{text.week}</small><b>{data.weekStart}</b></span><span><small>{text.updated}</small><b>{formatPublished(data.publishedAt, locale)}</b></span></div>}
      </header>

      {!data ? (
        <div className="pattern5-web-empty-state">{text.empty}</div>
      ) : (
        <div className="pattern5-web-grid">
          {data.tables.map((table) => <PairTable key={table.base} table={table} blocks={data.blocks} today={today} />)}
        </div>
      )}
    </div>
  );
}
