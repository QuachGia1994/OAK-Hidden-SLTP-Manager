import { getSignals } from "@/lib/data";
import { HistoryList } from "@/components/HistoryList";
import { cookies } from "next/headers";

export const dynamic = "force-dynamic";

export default async function SignalsPage({ searchParams }: { searchParams: Promise<{ vip?: string }> }) {
  let signals: any[] = [];
  try {
    signals = await getSignals();
  } catch (e) {
    console.error("Signals fetch error:", e);
  }

  const VIP_TOKEN = process.env.VIP_TOKEN || "";
  const params = await searchParams;
  const cookieStore = await cookies();
  const vipCookie = cookieStore.get("vip_access")?.value;
  const isVIP = vipCookie === "1" || !!(params.vip && VIP_TOKEN && params.vip === VIP_TOKEN);

  return (
    <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 py-8 sm:py-12">
      <div className="mb-10">
        <h1 className="text-4xl sm:text-5xl font-bold text-zinc-900 dark:text-zinc-50 tracking-tight leading-tight">Lịch sử Signal</h1>
        <p className="text-base text-zinc-500 dark:text-zinc-400 mt-2">7 ngày gần nhất</p>
      </div>

      <HistoryList signals={signals} isVIP={isVIP} />
    </div>
  );
}
