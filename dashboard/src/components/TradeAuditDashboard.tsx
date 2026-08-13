import { getTradeAuditAll } from "@/lib/trade-audit";
import { AnalysisPortal } from "@/components/AnalysisPortal";

interface Props {
  locale: "EN" | "VN";
}

/* ── tiny helpers ─────────────────────────────────────────────── */

function fmtCur(v: unknown, currency = "USD"): string {
  const n = Number(v);
  if (!Number.isFinite(n)) return "—";
  return `${currency} ${n.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}

function fmtPct(v: unknown): string {
  const n = Number(v);
  if (!Number.isFinite(n)) return "—";
  return `${n.toFixed(2)}%`;
}

function fmtDec(v: unknown, digits = 2): string {
  const n = Number(v);
  if (!Number.isFinite(n)) return "—";
  return n.toFixed(digits);
}

function fmtTime(v: unknown): string {
  if (typeof v !== "string") return "—";
  try {
    return new Date(v).toLocaleString("en-GB", { timeZone: "UTC", year: "numeric", month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit" });
  } catch {
    return v;
  }
}

function Empty({ text }: { text: string }) {
  return (
    <p className="rounded-xl border border-dashed border-[var(--panel-border)] bg-[var(--surface-raised)] px-4 py-6 text-center text-sm font-medium text-[var(--muted)]">
      {text}
    </p>
  );
}

function StatGrid({ children }: { children: React.ReactNode }) {
  return <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-4">{children}</div>;
}

const KPI_HINTS: Record<string, string> = {
  "Net P&L": "Realized P/L from closed positions. External deposits/withdrawals and floating P/L are tracked separately.",
  "Trading return": "Trading return (%) removes net external cash flow from balance change, then divides by starting balance.",
  "Win rate": "Winning closed positions divided by winning + losing closed positions. Entry deals and scratch trades are excluded.",
  "Profit factor": "Gross profit divided by gross loss across closed positions. Above 1 means gross wins exceed gross losses.",
  "Expectancy": "Average realized outcome per decided closed position: (gross profit − gross loss) / decided positions.",
  "Current drawdown": "Latest equity peak minus current equity on the available equity/checkpoint curve.",
  "Max drawdown": "Largest peak-to-trough equity drawdown observed in the available curve.",
  "Avg win": "Average realized profit of winning closed positions.",
  "Avg loss": "Average absolute loss of losing closed positions.",
  "Account growth": "Balance growth (%) including net external cash flow; trading return excludes that cash-flow effect.",
  "Tỷ lệ thắng": "Tỷ lệ thắng = vị thế đóng có lãi / (vị thế đóng có lãi + vị thế đóng có lỗ). Deal vào lệnh và lệnh hòa vốn được loại khỏi mẫu thắng/thua.",
  "Lãi TB": "Lãi trung bình của các vị thế đóng có kết quả dương.",
  "Lỗ TB": "Mức lỗ trung bình theo trị tuyệt đối của các vị thế đóng có kết quả âm.",
  "Hệ số lợi nhuận": "Profit factor = tổng lãi gộp / tổng lỗ gộp của các vị thế đóng.",
  "Lợi nhuận giao dịch": "Trading return (%) loại dòng tiền ngoài ròng khỏi thay đổi số dư trước khi chia cho số dư đầu.",
  "Tăng trưởng tài khoản": "Tăng trưởng tài khoản (%) = thay đổi số dư / số dư đầu và bao gồm tác động dòng tiền ngoài.",
};

function StatCard({ label, value, hint, tone }: { label: string; value: string; hint?: string; tone?: "buy" | "sell" | "warn" | "idle" }) {
  const toneClass = {
    buy: "text-[var(--terminal-accent)]",
    sell: "text-[var(--terminal-danger)]",
    warn: "text-[var(--terminal-warning)]",
    idle: "text-[var(--foreground)]",
  }[tone ?? "idle"];
  const explanation = hint || KPI_HINTS[label] || Object.entries(KPI_HINTS).find(([key]) => key.toLowerCase() === label.toLowerCase())?.[1];
  return (
    <div className="terminal-panel rounded-xl px-4 py-3">
      <div className="flex items-start justify-between gap-2">
        <div className="terminal-kicker mb-1 text-[10px] font-semibold uppercase tracking-[0.18em] text-[var(--muted)]">{label}</div>
        {explanation && (
          <details className="relative shrink-0">
            <summary className="grid h-5 w-5 cursor-pointer list-none place-items-center rounded-full border border-[var(--panel-border)] text-[10px] font-black text-[var(--muted)] hover:border-[var(--terminal-accent)] hover:text-[var(--terminal-accent)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--terminal-accent)]" aria-label={`Explain ${label}`}>
              i
            </summary>
            <div className="absolute right-0 top-7 z-20 w-64 rounded-lg border border-[var(--panel-border)] bg-[var(--surface)] p-3 text-[11px] font-medium leading-5 text-[var(--foreground)] shadow-lg">
              {explanation}
            </div>
          </details>
        )}
      </div>
      <div className={`font-mono text-lg font-black tabular-nums ${toneClass}`}>{value}</div>
    </div>
  );
}

function Badge({ children, tone }: { children: React.ReactNode; tone?: "green" | "red" | "amber" | "neutral" }) {
  const cls = {
    green: "bg-[var(--terminal-accent)]/12 text-[var(--terminal-accent)] border-[var(--terminal-accent)]/30",
    red: "bg-[var(--terminal-danger)]/12 text-[var(--terminal-danger)] border-[var(--terminal-danger)]/30",
    amber: "bg-[var(--terminal-warning)]/12 text-[var(--terminal-warning)] border-[var(--terminal-warning)]/30",
    neutral: "bg-[var(--surface-raised)] text-[var(--muted)] border-[var(--panel-border)]",
  }[tone ?? "neutral"];
  return (
    <span className={`inline-flex items-center rounded-md border px-2.5 py-1 font-mono text-[10px] font-semibold uppercase ${cls}`}>
      {children}
    </span>
  );
}

/* ── main component ───────────────────────────────────────────── */

export async function TradeAuditDashboard({ locale }: Props) {
  const data = await getTradeAuditAll();

  return (
    <AnalysisPortal
      locale={locale}
      overview={(data.overview as Record<string, unknown> | null) ?? null}
      positions={data.positions}
      checkpoints={data.checkpoints}
      ledger={data.ledger}
      performance={(data.performance as Record<string, unknown> | null) ?? null}
      risk={(data.risk as Record<string, unknown> | null) ?? null}
      audit={(data.audit as Record<string, unknown> | null) ?? null}
      equity={data.equity}
    />
  );
}

/* ── Section 1: Account Overview ─────────────────────────────── */

function AccountOverview({ data, locale, currency }: { data: unknown; locale: "EN" | "VN"; currency: string }) {
  const d = data as Record<string, unknown>;
  const ddSrc = d.drawdown_source as string | undefined;
  const ddHint = ddSrc === "CHECKPOINT"
    ? (locale === "EN" ? "(Checkpoint Drawdown)" : "(Drawdown Checkpoint)")
    : ddSrc === "EQUITY_SAMPLES"
      ? (locale === "EN" ? "(Max Equity Drawdown)" : "(Drawdown Equity Cao Nhất)")
      : undefined;

  return (
    <StatGrid>
      <StatCard label={locale === "EN" ? "Alias" : "Tên alias"} value={String(d.alias ?? "—")} />
      <StatCard label={locale === "EN" ? "Broker" : "Broker"} value={String(d.broker ?? "—")} />
      <StatCard label={locale === "EN" ? "Currency" : "Tiền tệ"} value={currency} />
      <StatCard label={locale === "EN" ? "Balance" : "Số dư"} value={fmtCur(d.balance, currency)} />
      <StatCard label={locale === "EN" ? "Equity" : "Vốn"} value={fmtCur(d.equity, currency)} />
      <StatCard label={locale === "EN" ? "Floating P/L" : "Lỗ/lãi nổi"} value={fmtCur(d.floating_pl, currency)} tone={Number(d.floating_pl) >= 0 ? "buy" : "sell"} />
      <StatCard label={locale === "EN" ? "Margin" : "Ký quỹ"} value={fmtCur(d.margin, currency)} />
      <StatCard label={locale === "EN" ? "Free Margin" : "Ký quỹ trống"} value={fmtCur(d.free_margin, currency)} />
      <StatCard label="Margin Level" value={fmtPct(d.margin_level)} />
      <StatCard label={locale === "EN" ? "Current Drawdown" : "Drawdown hiện tại"} value={fmtCur(d.current_drawdown, currency)} tone={Number(d.current_drawdown) > 0 ? "warn" : "idle"} hint={ddHint} />
      <StatCard label={locale === "EN" ? "Updated" : "Cập nhật"} value={fmtTime(d.updated_at_utc)} />
    </StatGrid>
  );
}

/* ── Section 2: Live Positions ───────────────────────────────── */

function LivePositions({ data, locale, currency, emptyText }: { data: unknown; locale: "EN" | "VN"; currency: string; emptyText: string }) {
  const positions = Array.isArray(data) ? data : [];
  if (positions.length === 0) return <Empty text={emptyText} />;

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-left text-sm">
        <thead>
          <tr className="border-b border-[var(--panel-border)] text-[10px] font-semibold uppercase tracking-[0.16em] text-[var(--muted)]">
            <th className="px-3 py-2">ID</th>
            <th className="px-3 py-2">{locale === "EN" ? "Symbol" : "Cặp"}</th>
            <th className="px-3 py-2">{locale === "EN" ? "Dir" : "Hướng"}</th>
            <th className="px-3 py-2">Vol</th>
            <th className="px-3 py-2">{locale === "EN" ? "Open" : "Giá vào"}</th>
            <th className="px-3 py-2">{locale === "EN" ? "P/L" : "Lãi/lỗ"}</th>
            <th className="px-3 py-2">{locale === "EN" ? "Source" : "Nguồn"}</th>
          </tr>
        </thead>
        <tbody>
          {positions.map((p: Record<string, unknown>, i: number) => {
            const dir = String(p.direction ?? "");
            const fp = Number(p.floating_profit);
            return (
              <tr key={String(p.public_trade_id ?? i)} className="border-b border-[var(--panel-border)]/50 hover:bg-[var(--surface-raised)]/50">
                <td className="px-3 py-2 font-mono text-[11px] tabular-nums text-[var(--muted)]">{String(p.public_trade_id ?? "—")}</td>
                <td className="px-3 py-2 font-mono text-xs font-bold">{String(p.symbol ?? "—")}</td>
                <td className="px-3 py-2">
                  <Badge tone={dir === "BUY" ? "green" : dir === "SELL" ? "red" : "neutral"}>{dir}</Badge>
                </td>
                <td className="px-3 py-2 font-mono text-xs tabular-nums">{String(p.volume ?? "—")}</td>
                <td className="px-3 py-2 font-mono text-xs tabular-nums">{String(p.open_price ?? "—")}</td>
                <td className={`px-3 py-2 font-mono text-xs font-bold tabular-nums ${fp >= 0 ? "text-[var(--terminal-accent)]" : "text-[var(--terminal-danger)]"}`}>
                  {fmtCur(fp, currency)}
                </td>
                <td className="px-3 py-2 text-[10px] text-[var(--muted)]">{String(p.source_type ?? "—")}</td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

/* ── Section 3: Checkpoint Timeline ──────────────────────────── */

function CheckpointTimeline({ data, locale, emptyText }: { data: unknown; locale: "EN" | "VN"; emptyText: string }) {
  const checkpoints = Array.isArray(data) ? data : [];
  if (checkpoints.length === 0) return <Empty text={emptyText} />;

  const sorted = [...checkpoints].sort((a: Record<string, unknown>, b: Record<string, unknown>) => {
    const da = String(a.broker_date ?? "") + String(a.checkpoint_hour ?? "").padStart(2, "0");
    const db = String(b.broker_date ?? "") + String(b.checkpoint_hour ?? "").padStart(2, "0");
    return da.localeCompare(db);
  });

  const statusTone = (s: string): "green" | "red" | "amber" | "neutral" => {
    if (s === "STILL_OPEN") return "green";
    if (s?.startsWith("CLOSED")) return "amber";
    if (s === "PARTIALLY_CLOSED") return "amber";
    if (s === "NO_OPEN_POSITIONS") return "neutral";
    if (s === "PARTIAL_RECONSTRUCTED") return "amber";
    return "neutral";
  };

  return (
    <div className="space-y-2">
      {sorted.map((cp: Record<string, unknown>, i: number) => {
        const status = String(cp.status ?? "—");
        const mode = String(cp.capture_mode ?? "—");
        const isReconstructed = mode === "RECONSTRUCTED";
        return (
          <div key={i} className="rounded-xl border border-[var(--panel-border)] bg-[var(--surface-raised)] px-4 py-3">
            <div className="flex flex-wrap items-center gap-2">
              <span className="font-mono text-xs font-bold tabular-nums text-[var(--foreground)]">
                {String(cp.broker_date ?? "—")} H{String(cp.checkpoint_hour ?? "—")}
              </span>
              <Badge tone={statusTone(status)}>{status}</Badge>
              <Badge tone={isReconstructed ? "amber" : "green"}>{mode}</Badge>
            </div>
            <div className="mt-1 flex flex-wrap gap-x-4 text-[10px] text-[var(--muted)]">
              {typeof cp.interval_start === "string" && <span>{locale === "EN" ? "From" : "Từ"}: {fmtTime(cp.interval_start)}</span>}
              {typeof cp.interval_end === "string" && <span>{locale === "EN" ? "To" : "Đến"}: {fmtTime(cp.interval_end)}</span>}
              {typeof cp.captured_at_utc === "string" && <span>{locale === "EN" ? "Captured" : "Ghi nhận"}: {fmtTime(cp.captured_at_utc)}</span>}
            </div>
            {typeof cp.error === "string" && cp.error && (
              <div className="mt-1 text-[10px] font-medium text-[var(--terminal-danger)]">{cp.error}</div>
            )}
          </div>
        );
      })}
    </div>
  );
}

/* ── Section 4: Trade Ledger (also exported for signals page) ── */

export function TradeLedger({ data, locale, currency, emptyText }: { data: unknown; locale: "EN" | "VN"; currency: string; emptyText: string }) {
  const entries = Array.isArray(data) ? data : [];
  if (entries.length === 0) return <Empty text={emptyText} />;

  const dealTone = (dt: string): "green" | "red" | "neutral" => {
    if (dt === "BUY" || dt === "DEAL_TYPE_BUY") return "green";
    if (dt === "SELL" || dt === "DEAL_TYPE_SELL") return "red";
    return "neutral";
  };

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-left text-sm">
        <thead>
          <tr className="border-b border-[var(--panel-border)] text-[10px] font-semibold uppercase tracking-[0.16em] text-[var(--muted)]">
            <th className="px-3 py-2">{locale === "EN" ? "Time" : "Thời gian"}</th>
            <th className="px-3 py-2">{locale === "EN" ? "Symbol" : "Cặp"}</th>
            <th className="px-3 py-2">{locale === "EN" ? "Type" : "Loại"}</th>
            <th className="px-3 py-2">{locale === "EN" ? "Reason" : "Lý do"}</th>
            <th className="px-3 py-2">Vol</th>
            <th className="px-3 py-2">{locale === "EN" ? "Profit" : "Lãi/lỗ"}</th>
            <th className="px-3 py-2">{locale === "EN" ? "Commission" : "Phí GD"}</th>
            <th className="px-3 py-2">Swap</th>
          </tr>
        </thead>
        <tbody>
          {entries.map((e: Record<string, unknown>, i: number) => {
            const profit = Number(e.profit);
            const dealType = String(e.deal_type ?? "");
            return (
              <tr key={String(e.public_trade_id ?? i)} className="border-b border-[var(--panel-border)]/50 hover:bg-[var(--surface-raised)]/50">
                <td className="px-3 py-2 font-mono text-[11px] tabular-nums text-[var(--muted)]">{fmtTime(e.deal_time_utc)}</td>
                <td className="px-3 py-2 font-mono text-xs font-bold">{String(e.symbol ?? "—")}</td>
                <td className="px-3 py-2"><Badge tone={dealTone(dealType)}>{dealType}</Badge></td>
                <td className="px-3 py-2">
                  {e.reason_category ? (
                    <Badge tone="neutral">{String(e.reason_category)}</Badge>
                  ) : (
                    <span className="text-[var(--muted)]">—</span>
                  )}
                </td>
                <td className="px-3 py-2 font-mono text-xs tabular-nums">{String(e.volume ?? "—")}</td>
                <td className={`px-3 py-2 font-mono text-xs font-bold tabular-nums ${profit >= 0 ? "text-[var(--terminal-accent)]" : "text-[var(--terminal-danger)]"}`}>
                  {fmtCur(profit, currency)}
                </td>
                <td className="px-3 py-2 font-mono text-[11px] tabular-nums text-[var(--muted)]">{fmtCur(e.commission, currency)}</td>
                <td className="px-3 py-2 font-mono text-[11px] tabular-nums text-[var(--muted)]">{fmtCur(e.swap, currency)}</td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

/* ── Section 5: Performance ──────────────────────────────────── */

function Performance({ data, locale, currency }: { data: unknown; locale: "EN" | "VN"; currency: string }) {
  const d = data as Record<string, unknown>;
  const wr = Number(d.win_rate);
  const pf = Number(d.profit_factor);

  return (
    <StatGrid>
      <StatCard label={locale === "EN" ? "Current Balance" : "Số dư hiện tại"} value={fmtCur(d.current_balance, currency)} />
      <StatCard label={locale === "EN" ? "Current Equity" : "Vốn hiện tại"} value={fmtCur(d.current_equity, currency)} />
      <StatCard label={locale === "EN" ? "Net Profit" : "Lợi nhuận ròng"} value={fmtCur(d.net_profit, currency)} tone={Number(d.net_profit) >= 0 ? "buy" : "sell"} />
      <StatCard label={locale === "EN" ? "Realized P/L" : "Lãi/lỗ đã thực hiện"} value={fmtCur(d.realized_pl, currency)} tone={Number(d.realized_pl) >= 0 ? "buy" : "sell"} />
      <StatCard label={locale === "EN" ? "Unrealized P/L" : "Lãi/lỗ chưa thực hiện"} value={fmtCur(d.unrealized_pl, currency)} tone={Number(d.unrealized_pl) >= 0 ? "buy" : "sell"} />
      <StatCard label={locale === "EN" ? "Profit factor" : "Profit factor"} value={Number.isFinite(pf) ? fmtDec(pf) : "—"} />
      <StatCard label={locale === "EN" ? "Win rate" : "Tỷ lệ thắng"} value={Number.isFinite(wr) ? fmtPct(wr) : "—"} tone={wr > 0.5 ? "buy" : wr > 0 ? "sell" : "idle"} />
      <StatCard label={locale === "EN" ? "Avg Win" : "Lãi TB"} value={fmtCur(d.average_win, currency)} />
      <StatCard label={locale === "EN" ? "Avg Loss" : "Lỗ TB"} value={fmtCur(d.average_loss, currency)} />
      <StatCard label="Expectancy" value={fmtCur(d.expectancy, currency)} />
      <StatCard label={locale === "EN" ? "Max Drawdown" : "Drawdown cao nhất"} value={fmtCur(d.max_equity_drawdown, currency)} tone="warn" />
      <StatCard label={locale === "EN" ? "Current Drawdown" : "Drawdown hiện tại"} value={fmtCur(d.current_drawdown, currency)} tone="warn" />
      <StatCard label={locale === "EN" ? "Trading return" : "Trading return"} value={d.trading_return_pct != null ? fmtPct(Number(d.trading_return_pct) * 100) : "—"} />
      <StatCard label={locale === "EN" ? "Account growth" : "Tăng trưởng tài khoản"} value={d.account_growth_pct != null ? fmtPct(Number(d.account_growth_pct) * 100) : "—"} />
      <StatCard label={locale === "EN" ? "Net Cash Flow" : "Dòng tiền ròng"} value={fmtCur(d.net_cash_flow, currency)} />
      <StatCard label={locale === "EN" ? "Total Commission" : "Tổng phí GD"} value={fmtCur(d.total_commission, currency)} />
      <StatCard label={locale === "EN" ? "Total Swap" : "Tổng swap"} value={fmtCur(d.total_swap, currency)} />
      <StatCard label={locale === "EN" ? "Total Fees" : "Tổng phí"} value={fmtCur(d.total_fees, currency)} />
    </StatGrid>
  );
}

/* ── Section 6: Risk ─────────────────────────────────────────── */

function Risk({ data, locale, currency }: { data: unknown; locale: "EN" | "VN"; currency: string }) {
  const d = data as Record<string, unknown>;
  const exposureBySymbol = d.exposure_by_symbol as Record<string, unknown> | undefined;
  const exposureByDirection = d.exposure_by_direction as Record<string, unknown> | undefined;

  return (
    <div className="space-y-4">
      {/* Exposure by symbol chips */}
      {exposureBySymbol && typeof exposureBySymbol === "object" && Object.keys(exposureBySymbol).length > 0 && (
        <div>
          <div className="terminal-kicker mb-2 text-[10px] font-semibold uppercase tracking-[0.18em] text-[var(--muted)]">
            {locale === "EN" ? "Exposure by Symbol" : "Phơi nhiễm theo cặp"}
          </div>
          <div className="flex flex-wrap gap-2">
            {Object.entries(exposureBySymbol).map(([sym, val]) => (
              <div key={sym} className="rounded-xl border border-[var(--panel-border)] bg-[var(--surface-raised)] px-3 py-2 text-center">
                <div className="font-mono text-xs font-bold">{sym}</div>
                <div className="font-mono text-[11px] tabular-nums text-[var(--muted)]">{fmtCur(val)}</div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Exposure by direction */}
      {exposureByDirection && typeof exposureByDirection === "object" && Object.keys(exposureByDirection).length > 0 && (
        <div>
          <div className="terminal-kicker mb-2 text-[10px] font-semibold uppercase tracking-[0.18em] text-[var(--muted)]">
            {locale === "EN" ? "Exposure by Direction" : "Phơi nhiễm theo hướng"}
          </div>
          <div className="flex flex-wrap gap-2">
            {Object.entries(exposureByDirection).map(([dir, val]) => (
              <Badge key={dir} tone={dir === "BUY" ? "green" : dir === "SELL" ? "red" : "neutral"}>
                {dir}: {fmtCur(val)}
              </Badge>
            ))}
          </div>
        </div>
      )}

      <StatGrid>
        <StatCard label={locale === "EN" ? "Max Consec. Wins" : "Thắng liên tiếp max"} value={String(d.max_consecutive_wins ?? "—")} />
        <StatCard label={locale === "EN" ? "Max Consec. Losses" : "Thua liên tiếp max"} value={String(d.max_consecutive_losses ?? "—")} />
        <StatCard label={locale === "EN" ? "Max Balance Drawdown" : "Drawdown số dư max"} value={fmtCur(d.max_balance_drawdown, currency)} tone="warn" />
        <StatCard label="Recovery Factor" value={fmtDec(d.recovery_factor)} />
        <StatCard label={locale === "EN" ? "Margin Usage" : "Sử dụng ký quỹ"} value={fmtPct(d.margin_usage_pct)} />
        <StatCard label={locale === "EN" ? "Largest Single Loss" : "Lỗ đơn lớn nhất"} value={fmtCur(d.largest_single_loss)} tone="sell" />
        <StatCard label={locale === "EN" ? "Open Positions" : "Vị thế đang mở"} value={String(d.open_position_count ?? "—")} />
      </StatGrid>
    </div>
  );
}

/* ── Section 7: Audit ────────────────────────────────────────── */

function Audit({ data, locale }: { data: unknown; locale: "EN" | "VN" }) {
  const d = data as Record<string, unknown>;
  const captureModes = d.capture_modes as Record<string, unknown> | undefined;
  const missing = Array.isArray(d.missing_intervals) ? d.missing_intervals as unknown[] : [];
  const reconStatus = String(d.reconciliation_status ?? "—");
  const isOk = reconStatus === "OK" || reconStatus === "RECONCILED";

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
        <StatCard label={locale === "EN" ? "Alias" : "Tên alias"} value={String(d.alias ?? "—")} />
        <StatCard
          label={locale === "EN" ? "Reconciliation" : "Đối soát"}
          value={reconStatus}
          tone={isOk ? "buy" : "warn"}
        />
        <StatCard label={locale === "EN" ? "Last Checkpoint" : "Checkpoint cuối"} value={fmtTime(d.last_checkpoint_at_utc)} />
      </div>

      {/* Capture mode badges */}
      {captureModes && typeof captureModes === "object" && Object.keys(captureModes).length > 0 && (
        <div>
          <div className="terminal-kicker mb-2 text-[10px] font-semibold uppercase tracking-[0.18em] text-[var(--muted)]">
            {locale === "EN" ? "Capture Modes" : "Chế độ ghi nhận"}
          </div>
          <div className="flex flex-wrap gap-2">
            {Object.entries(captureModes).map(([mode, count]) => (
              <Badge key={mode} tone={mode === "RECONSTRUCTED" ? "amber" : "green"}>
                {mode}: {String(count)}
              </Badge>
            ))}
          </div>
        </div>
      )}

      {/* Missing intervals */}
      {missing.length > 0 && (
        <div>
          <div className="terminal-kicker mb-2 text-[10px] font-semibold uppercase tracking-[0.18em] text-[var(--terminal-warning)]">
            {locale === "EN" ? `Missing Intervals (${missing.length})` : `Khoảng thiếu (${missing.length})`}
          </div>
          <div className="flex flex-wrap gap-1.5">
            {missing.map((m, i) => (
              <span key={i} className="rounded-md border border-[var(--terminal-warning)]/30 bg-[var(--terminal-warning)]/10 px-2 py-0.5 font-mono text-[10px] text-[var(--terminal-warning)]">
                {String(m)}
              </span>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
