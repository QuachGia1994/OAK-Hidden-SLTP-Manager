"use client";

import { useState } from "react";
import { ExpandableRow } from "@/components/ExpandableRow";

interface Props {
  data: unknown;
  locale: "EN" | "VN";
  currency: string;
  emptyText: string;
  maxRows?: number;
}

function fmt(value: unknown, currency?: string) {
  const n = Number(value);
  if (!Number.isFinite(n)) return "—";
  return currency ? `${currency} ${n.toFixed(2)}` : n.toFixed(2);
}

function time(value: unknown) {
  if (typeof value !== "string" || !value) return "—";
  const d = new Date(value);
  return Number.isNaN(d.getTime()) ? value : d.toLocaleString("en-GB", { timeZone: "UTC", day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit" });
}

export function TradeLedger({ data, locale, currency, emptyText, maxRows = 10 }: Props) {
  const rows = Array.isArray(data) ? (data as Record<string, unknown>[]).slice(0, maxRows) : [];
  const [openId, setOpenId] = useState<string | null>(null);
  if (!rows.length) return <p className="rounded-xl border border-dashed border-[var(--panel-border)] bg-[var(--surface-raised)] px-4 py-8 text-center text-sm text-[var(--muted)]">{emptyText}</p>;

  return (
    <div className="space-y-2">
      {rows.map((row, index) => {
        const id = String(row.public_trade_id ?? index);
        const profit = Number(row.profit);
        return (
          <ExpandableRow
            key={id}
            id={id}
            open={openId === id}
            onToggle={(value) => setOpenId((current) => current === value ? null : value)}
            ariaLabel={locale === "VN" ? `Mở chi tiết giao dịch ${index + 1}` : `Open trade ${index + 1} details`}
            summary={(
              <div className="grid grid-cols-[minmax(0,1fr)_auto_auto] items-center gap-2">
                <div className="min-w-0">
                  <div className="flex items-center gap-2">
                    <span className="font-mono text-sm font-black text-[var(--foreground)]">{String(row.symbol ?? "—")}</span>
                    <span className="rounded-md border border-[var(--panel-border)] px-1.5 py-0.5 font-mono text-[9px] font-bold text-[var(--muted)]">{String(row.deal_type ?? "—")}</span>
                  </div>
                  <div className="mt-1 font-mono text-[10px] text-[var(--muted)]">{time(row.deal_time_utc)} · {String(row.volume ?? "—")}</div>
                </div>
                <span className={`font-mono text-xs font-black tabular-nums ${profit >= 0 ? "text-[var(--terminal-accent)]" : "text-[var(--terminal-danger)]"}`}>{fmt(row.profit, currency)}</span>
                <span className="text-[10px] font-semibold text-[var(--muted)]">{locale === "VN" ? "Chi tiết" : "Details"}</span>
              </div>
            )}
            details={(
              <dl className="grid grid-cols-2 gap-2 text-[11px] sm:grid-cols-4">
                <Detail label="ID" value={id} />
                <Detail label={locale === "VN" ? "Thời gian" : "Time"} value={time(row.deal_time_utc)} />
                <Detail label={locale === "VN" ? "Symbol" : "Symbol"} value={String(row.symbol ?? "—")} />
                <Detail label={locale === "VN" ? "Loại" : "Type"} value={String(row.deal_type ?? "—")} />
                <Detail label="Volume" value={String(row.volume ?? "—")} />
                <Detail label={locale === "VN" ? "Giá" : "Price"} value={String(row.price ?? "—")} />
                <Detail label="P&L" value={fmt(row.profit, currency)} />
                <Detail label={locale === "VN" ? "Phí GD" : "Commission"} value={fmt(row.commission, currency)} />
                <Detail label="Swap" value={fmt(row.swap, currency)} />
                <Detail label={locale === "VN" ? "Lý do" : "Reason"} value={String(row.reason_category ?? "—")} />
                <Detail label={locale === "VN" ? "Entry" : "Entry"} value={String(row.entry_type ?? "—")} />
              </dl>
            )}
          />
        );
      })}
      {Array.isArray(data) && data.length > maxRows && <p className="pt-1 text-[11px] text-[var(--muted)]">{locale === "VN" ? `Hiển thị ${maxRows} giao dịch gần nhất. Mở từng dòng để xem chi tiết.` : `Showing the latest ${maxRows} trades. Open a row for details.`}</p>}
    </div>
  );
}

function Detail({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg border border-[var(--panel-border)] bg-[var(--surface-raised)] p-2">
      <dt className="text-[9px] font-bold uppercase tracking-[0.12em] text-[var(--muted)]">{label}</dt>
      <dd className="mt-1 break-words font-mono text-[10px] font-semibold text-[var(--foreground)]">{value}</dd>
    </div>
  );
}
