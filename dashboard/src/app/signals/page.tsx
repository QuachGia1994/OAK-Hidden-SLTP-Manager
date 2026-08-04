import { getSignalsResult } from "@/lib/data";
import { HistoryList } from "@/components/HistoryList";
import { maskSignalForPublic } from "@/lib/signal-display";
import { resolveHistorySignals } from "@/lib/constants";
import { countIncompleteSignals } from "@/lib/signal-integrity";
import { TradeLedger } from "@/components/TradeAuditDashboard";
import { getTradeAuditAll } from "@/lib/trade-audit";
import type { HistorySignal } from "@/lib/types";
import { hasVipAccess } from "@/lib/vip";
import { headers } from "next/headers";
import { detectServerLocaleFromCookie, getLocaleTexts } from "@/lib/i18n";

export const dynamic = "force-dynamic";

export default async function SignalsPage({ searchParams }: { searchParams: Promise<{ vip?: string }> }) {
  let signalsResult: { data: any[]; ok: boolean; error?: string } = { data: [], ok: true };
  try {
    signalsResult = await getSignalsResult();
  } catch (e) {
    console.error("Signals fetch error:", e);
  }

  const params = await searchParams;
  const isVIP = await hasVipAccess(params);
  const headerList = await headers();
  const locale = detectServerLocaleFromCookie(headerList.get("cookie"), headerList.get("accept-language"));
  const t = getLocaleTexts(locale);

  // History page: v88 first, v87 fallback with legacy metadata
  const signals = signalsResult.ok ? resolveHistorySignals(signalsResult.data as unknown as Array<Record<string, unknown> & { date: string; hour: number; logic_version?: unknown; pair_dirs?: unknown; signal?: unknown }>) : [];
  const visibleSignals: HistorySignal[] = isVIP ? signals : signals.map((s) => maskSignalForPublic(s as Record<string, unknown>) as unknown as HistorySignal);
  const accessText = isVIP
    ? locale === "EN" ? "Unlocked" : "Đã mở"
    : locale === "EN" ? "Locked" : "Đã khóa";
  const incompleteCount = isVIP ? countIncompleteSignals(visibleSignals) : 0;

  // Fetch trade audit ledger for main content
  const auditData = await getTradeAuditAll();
  const ledgerCurrency = (auditData.overview as Record<string, unknown> | null)?.currency as string | undefined ?? "USD";

  return (
    <div className="page-shell terminal-page space-y-5">
      <section className="terminal-hero history-hero rounded-xl px-5 py-5 sm:px-6 sm:py-6">
        <div className="relative grid gap-5 lg:grid-cols-[minmax(0,1fr)_minmax(19rem,0.8fr)] lg:items-end">
          <div>
            <div className="terminal-kicker mb-3">{locale === "EN" ? "Verified account ledger" : "Sổ giao dịch đã xác thực"}</div>
            <h1 className="text-4xl font-black tracking-tight text-zinc-950 dark:text-white sm:text-5xl">
              {locale === "EN" ? "Trade history" : "Lịch sử giao dịch"}
            </h1>
            <p className="mt-2 text-sm text-zinc-500 dark:text-zinc-400">
              {locale === "EN" ? "Verified trade activity from the live account" : "Hoạt động giao dịch đã xác thực từ tài khoản live"}
            </p>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <HistoryStat label={locale === "EN" ? "Ledger" : "Sổ lệnh"} value={(() => {
              const ledger = auditData.ledger;
              return Array.isArray(ledger) ? ledger.length.toString() : "0";
            })()} />
            <HistoryStat label={t.vip} value={accessText} />
          </div>
        </div>
      </section>

      {/* Main content: Trade Ledger */}
      <section className="terminal-panel rounded-2xl p-5 sm:p-6">
        <h2 className="terminal-section-heading mb-4 text-xs font-mono font-bold uppercase tracking-[0.22em] text-[var(--muted)]">
          {locale === "EN" ? "Trade Ledger" : "Sổ giao dịch"}
        </h2>
        <TradeLedger
          data={auditData.ledger}
          locale={locale}
          currency={ledgerCurrency}
          emptyText={locale === "EN" ? "No trade activity yet" : "Chưa có hoạt động giao dịch"}
        />
      </section>

      {/* Hidden legacy archive */}
      <details className="terminal-panel rounded-2xl">
        <summary className="cursor-pointer px-5 py-4 text-[11px] font-semibold uppercase tracking-[0.18em] text-[var(--muted)] hover:text-[var(--foreground)] transition-colors">
          {locale === "EN" ? "Old signal archive" : "Kho tín hiệu cũ"}
        </summary>
        <div className="space-y-4 border-t border-[var(--panel-border)] px-5 py-5">
          <p className="rounded-xl border border-dashed border-[var(--panel-border)] bg-[var(--surface-raised)] px-4 py-3 text-[11px] font-medium text-[var(--muted)]">
            {locale === "EN"
              ? "Legacy candle-signal archive — not part of verified trade performance"
              : "Kho tín hiệu cũ (candle) — không thuộc hiệu quả giao dịch đã xác thực"}
          </p>

          {incompleteCount > 0 && (
            <div
              className="terminal-panel rounded-xl border border-[var(--terminal-danger)]/40 bg-[var(--terminal-danger)]/[0.06] px-5 py-4"
              role="status"
            >
              <div className="flex flex-wrap items-center justify-between gap-2">
                <div>
                  <div className="font-mono text-xs font-black uppercase tracking-[0.18em] text-[var(--terminal-danger)]">
                    {locale === "EN" ? "History rebuild is incomplete" : "History rebuild chưa toàn vẹn"}
                  </div>
                  <p className="mt-1 text-xs font-medium text-[var(--muted)]">
                    {locale === "EN"
                      ? `${incompleteCount} session record${incompleteCount === 1 ? "" : "s"} is missing required inputs. WAIT states there are not valid conclusions.`
                      : `${incompleteCount} record phiên thiếu input bắt buộc. WAIT tại đó không phải kết luận hợp lệ.`}
                  </p>
                </div>
                <span className="rounded-md border border-[var(--terminal-danger)]/40 bg-[var(--terminal-danger)]/10 px-2.5 py-1 font-mono text-[10px] font-black text-[var(--terminal-danger)]">
                  {locale === "EN" ? "INCOMPLETE" : "CHƯA TOÀN VẸN"}
                </span>
              </div>
            </div>
          )}

          <HistoryList signals={visibleSignals} isVIP={isVIP} />
        </div>
      </details>
    </div>
  );
}

function HistoryStat({ label, value }: { label: string; value: string }) {
  return (
    <div className="terminal-stat rounded-lg px-4 py-3">
      <div className="terminal-kicker mb-1">{label}</div>
      <div className="terminal-stat-value font-mono text-xl font-black">{value}</div>
    </div>
  );
}
