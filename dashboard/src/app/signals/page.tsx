import { getSignals, maskSignal } from "@/lib/data";
import { HistoryList } from "@/components/HistoryList";
import { hasVipAccess } from "@/lib/vip";
import { headers } from "next/headers";
import { detectServerLocaleFromCookie, getLocaleTexts } from "@/lib/i18n";

export const dynamic = "force-dynamic";

export default async function SignalsPage({ searchParams }: { searchParams: Promise<{ vip?: string }> }) {
  let signals: any[] = [];
  try {
    signals = await getSignals();
  } catch (e) {
    console.error("Signals fetch error:", e);
  }

  const params = await searchParams;
  const isVIP = await hasVipAccess(params);
  const headerList = await headers();
  const locale = detectServerLocaleFromCookie(headerList.get("cookie"), headerList.get("accept-language"));
  const t = getLocaleTexts(locale);
  const visibleSignals = isVIP ? signals : signals.map(maskSignal);
  const accessText = isVIP
    ? locale === "EN" ? "Unlocked" : "Đã mở"
    : locale === "EN" ? "Locked" : "Đã khóa";

  return (
    <div className="page-shell terminal-page space-y-5">
      <section className="terminal-hero history-hero rounded-xl px-5 py-5 sm:px-6 sm:py-6">
        <div className="relative grid gap-5 lg:grid-cols-[minmax(0,1fr)_minmax(19rem,0.8fr)] lg:items-end">
          <div>
            <div className="terminal-kicker mb-3">{locale === "EN" ? "Archive" : "Kho lưu"}</div>
            <h1 className="text-4xl font-black tracking-tight text-zinc-950 dark:text-white sm:text-5xl">
              {locale === "EN" ? "Signal history" : "Lịch sử tín hiệu"}
            </h1>
            <p className="mt-2 text-sm text-zinc-500 dark:text-zinc-400">
              {locale === "EN" ? "Last 7 days · broker-session archive" : "7 ngày gần nhất · kho phiên broker"}
            </p>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <HistoryStat label={locale === "EN" ? "Archive" : "Kho lưu"} value={visibleSignals.length.toString()} />
            <HistoryStat label={t.vip} value={accessText} />
          </div>
        </div>
      </section>

      <HistoryList signals={visibleSignals} isVIP={isVIP} />
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
