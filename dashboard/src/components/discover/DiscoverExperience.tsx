"use client";

import { FormEvent, useEffect, useMemo, useState } from "react";
import { WorkspaceHeading } from "@/components/WorkspaceHeading";
import { ToolArtwork, type ToolArtworkKind } from "@/components/ToolArtwork";
import { useLocale } from "@/components/LocaleProvider";
import type { CompatibilityReading, DreamReading } from "@/lib/discover/gemini";

type MoodEntry = { date: string; score: number; label: string; note: string };
type DailyState = { date: string; streak: number; lastDate: string; message: DailyMessage };
type DailyMessage = { energy: string; do: string; avoid: string; reminder: string };
type OracleResult = { answer: string; detail: string; question: string; at: string };

type Copy = {
  title: string; intro: string; streak: string; localNote: string;
  daily: { title: string; subtitle: string; open: string; opened: string; energy: string; do: string; avoid: string; reminder: string };
  dream: { title: string; subtitle: string; placeholder: string; action: string; loading: string; symbols: string; theme: string; reflection: string; next: string };
  oracle: { title: string; subtitle: string; placeholder: string; action: string };
  mood: { title: string; subtitle: string; note: string; save: string; history: string; labels: string[] };
  compatibility: { title: string; subtitle: string; a: string; b: string; context: string; action: string; loading: string; strengths: string; watchouts: string; starter: string; metrics: string[] };
  errors: { invalid: string; network: string; ai: string };
};

const COPY: Record<"EN" | "VN", Copy> = {
  EN: {
    title: "Discover", intro: "Five lightweight experiences for daily reflection, curiosity, and play.", streak: "day streak", localNote: "Daily, Oracle, and Mood stay on this device.",
    daily: { title: "OAK Daily", subtitle: "One message per day", open: "Reveal today", opened: "Come back tomorrow", energy: "Energy", do: "Do", avoid: "Avoid", reminder: "Reminder" },
    dream: { title: "Dream AI", subtitle: "Reflect on symbols and emotions", placeholder: "Describe the dream you remember...", action: "Decode dream", loading: "Interpreting", symbols: "Symbols", theme: "Emotional theme", reflection: "Reflection", next: "Next step" },
    oracle: { title: "Yes / No Oracle", subtitle: "A quick prompt, not a prediction", placeholder: "Ask a clear yes/no question...", action: "Ask Oracle" },
    mood: { title: "Mood Check", subtitle: "Track the last seven check-ins", note: "Optional note", save: "Save check-in", history: "7-day pulse", labels: ["Very low", "Low", "Okay", "Good", "Great"] },
    compatibility: { title: "Compatibility", subtitle: "A playful conversation prompt for two people", a: "Person A", b: "Person B", context: "Optional context or traits", action: "Read compatibility", loading: "Reading", strengths: "Strengths", watchouts: "Watch-outs", starter: "Conversation starter", metrics: ["Communication", "Trust", "Chemistry", "Long-term"] },
    errors: { invalid: "Please complete the required input.", network: "Network request failed.", ai: "AI response is unavailable right now." },
  },
  VN: {
    title: "Khám phá", intro: "Năm trải nghiệm nhẹ để quay lại mỗi ngày, chiêm nghiệm và giải trí.", streak: "ngày liên tiếp", localNote: "Daily, Oracle và Mood được lưu trên thiết bị này.",
    daily: { title: "OAK Daily", subtitle: "Một thông điệp mỗi ngày", open: "Mở thông điệp", opened: "Mai quay lại nhé", energy: "Năng lượng", do: "Nên làm", avoid: "Nên tránh", reminder: "Nhắc nhẹ" },
    dream: { title: "Dream AI", subtitle: "Giải mã biểu tượng và cảm xúc trong giấc mơ", placeholder: "Mô tả giấc mơ bạn còn nhớ...", action: "Giải mã", loading: "Đang luận giải", symbols: "Biểu tượng", theme: "Chủ đề cảm xúc", reflection: "Góc nhìn", next: "Bước tiếp theo" },
    oracle: { title: "Yes / No Oracle", subtitle: "Một gợi ý nhanh, không phải lời tiên tri", placeholder: "Đặt một câu hỏi Có / Không rõ ràng...", action: "Hỏi Oracle" },
    mood: { title: "Mood Check", subtitle: "Theo dõi 7 lần check-in gần nhất", note: "Ghi chú tùy chọn", save: "Lưu check-in", history: "Nhịp 7 ngày", labels: ["Rất thấp", "Thấp", "Ổn", "Tốt", "Rất tốt"] },
    compatibility: { title: "Compatibility", subtitle: "Gợi ý vui để hai người hiểu nhau hơn", a: "Người A", b: "Người B", context: "Bối cảnh hoặc tính cách (tùy chọn)", action: "Xem độ hợp", loading: "Đang phân tích", strengths: "Điểm mạnh", watchouts: "Điểm cần lưu ý", starter: "Câu hỏi để trò chuyện", metrics: ["Giao tiếp", "Tin cậy", "Hấp dẫn", "Dài hạn"] },
    errors: { invalid: "Hãy nhập đủ thông tin bắt buộc.", network: "Không kết nối được máy chủ.", ai: "AI tạm thời chưa trả kết quả." },
  },
};

const DAILY_EN = [
  ["Focused", "Finish one small thing completely.", "Overloading the day with too many goals.", "Clarity grows when you reduce noise."],
  ["Open", "Ask one better question before acting.", "Assuming you already know the answer.", "Curiosity is useful when it stays grounded."],
  ["Steady", "Protect a block of uninterrupted time.", "Reacting to every notification.", "Consistency beats intensity today."],
  ["Social", "Have one honest, low-pressure conversation.", "Reading too much into short messages.", "Leave room for other interpretations."],
  ["Reset", "Tidy one physical or digital space.", "Carrying yesterday into every decision.", "A small reset can change the tone of the day."],
];
const DAILY_VN = [
  ["Tập trung", "Hoàn thành trọn vẹn một việc nhỏ.", "Nhồi quá nhiều mục tiêu vào cùng một ngày.", "Rõ ràng hơn khi bạn giảm bớt nhiễu."],
  ["Cởi mở", "Hỏi thêm một câu hay trước khi hành động.", "Cho rằng mình đã biết sẵn câu trả lời.", "Tò mò có ích khi vẫn bám vào thực tế."],
  ["Ổn định", "Giữ một khoảng thời gian không bị gián đoạn.", "Phản ứng với mọi thông báo.", "Hôm nay đều đặn quan trọng hơn bùng nổ."],
  ["Kết nối", "Có một cuộc trò chuyện thẳng nhưng nhẹ nhàng.", "Suy diễn quá nhiều từ vài tin nhắn ngắn.", "Chừa chỗ cho những cách hiểu khác."],
  ["Làm mới", "Dọn một góc vật lý hoặc kỹ thuật số.", "Mang tâm trạng hôm qua vào mọi quyết định.", "Một lần reset nhỏ có thể đổi nhịp cả ngày."],
];

const ORACLE_EN = [
  ["YES", "The signal leans positive. Move with a small, reversible next step."],
  ["PROBABLY", "There is momentum, but one missing detail still matters."],
  ["UNCLEAR", "The question may need better timing or a sharper definition."],
  ["PROBABLY NOT", "Current conditions look resistant. Reframe before pushing harder."],
  ["NO", "Treat this as permission to protect your time and explore another route."],
];
const ORACLE_VN = [
  ["CÓ", "Tín hiệu nghiêng về tích cực. Hãy thử một bước nhỏ và dễ đảo ngược."],
  ["CÓ LẼ CÓ", "Đang có đà, nhưng vẫn còn một chi tiết quan trọng chưa rõ."],
  ["CHƯA RÕ", "Câu hỏi có thể cần đúng thời điểm hơn hoặc định nghĩa sắc hơn."],
  ["CÓ LẼ KHÔNG", "Điều kiện hiện tại khá cản trở. Nên đổi góc nhìn trước khi cố thêm."],
  ["KHÔNG", "Có thể xem đây là tín hiệu để giữ thời gian cho một hướng khác."],
];

function dateKey(date = new Date()) {
  return new Intl.DateTimeFormat("en-CA", { timeZone: "Asia/Ho_Chi_Minh", year: "numeric", month: "2-digit", day: "2-digit" }).format(date);
}
function hashText(value: string) {
  let hash = 2166136261;
  for (let index = 0; index < value.length; index += 1) { hash ^= value.charCodeAt(index); hash = Math.imul(hash, 16777619); }
  return Math.abs(hash >>> 0);
}
function dayDiff(a: string, b: string) {
  return Math.round((Date.parse(`${a}T00:00:00Z`) - Date.parse(`${b}T00:00:00Z`)) / 86400000);
}
function readJson<T>(key: string, fallback: T): T {
  try { const raw = localStorage.getItem(key); return raw ? JSON.parse(raw) as T : fallback; } catch { return fallback; }
}
function dailyMessage(locale: "EN" | "VN", key: string): DailyMessage {
  const source = locale === "EN" ? DAILY_EN : DAILY_VN;
  const row = source[hashText(key) % source.length];
  return { energy: row[0], do: row[1], avoid: row[2], reminder: row[3] };
}

function FeatureHeader({ index, title, subtitle }: { index: string; title: string; subtitle: string; glyph: string }) {
  const artwork: Record<string, ToolArtworkKind> = { "01": "daily", "02": "dream", "03": "oracle", "04": "mood", "05": "compatibility" };
  return <header className="discover-card-head" data-art={index === "04" ? "none" : undefined}>{index !== "04" && <ToolArtwork kind={artwork[index]} />}<div><h2>{title}</h2>{(index === "02" || index === "05") && <small className="discover-ai-badge">AI</small>}<p>{subtitle}</p></div></header>;
}

function Metric({ label, value }: { label: string; value: number }) {
  return <article className="discover-metric"><span>{label}</span><b>{value}</b><i><em style={{ width: `${value}%` }} /></i></article>;
}

export function DiscoverExperience() {
  const { locale } = useLocale();
  const copy = COPY[locale];
  const today = useMemo(() => dateKey(), []);
  const [daily, setDaily] = useState<DailyState | null>(null);
  const [oracleQuestion, setOracleQuestion] = useState("");
  const [oracleResult, setOracleResult] = useState<OracleResult | null>(null);
  const [moodScore, setMoodScore] = useState(3);
  const [moodNote, setMoodNote] = useState("");
  const [moods, setMoods] = useState<MoodEntry[]>([]);
  const [dream, setDream] = useState("");
  const [dreamReading, setDreamReading] = useState<DreamReading | null>(null);
  const [dreamLoading, setDreamLoading] = useState(false);
  const [compatA, setCompatA] = useState("");
  const [compatB, setCompatB] = useState("");
  const [compatContext, setCompatContext] = useState("");
  const [compatReading, setCompatReading] = useState<CompatibilityReading | null>(null);
  const [compatLoading, setCompatLoading] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    setDaily(readJson<DailyState | null>("oak-discover-daily", null));
    setMoods(readJson<MoodEntry[]>("oak-discover-moods", []).slice(-7));
  }, []);

  const revealDaily = () => {
    if (daily?.date === today) return;
    const previous = daily?.lastDate || daily?.date || "";
    const streak = previous && dayDiff(today, previous) === 1 ? (daily?.streak || 0) + 1 : 1;
    const next: DailyState = { date: today, lastDate: today, streak, message: dailyMessage(locale, today) };
    localStorage.setItem("oak-discover-daily", JSON.stringify(next));
    setDaily(next);
  };

  const askOracle = (event: FormEvent) => {
    event.preventDefault();
    const question = oracleQuestion.trim();
    if (question.length < 3) { setError(copy.errors.invalid); return; }
    setError("");
    const source = locale === "EN" ? ORACLE_EN : ORACLE_VN;
    const selected = source[hashText(`${question}|${today}|${new Date().getHours()}`) % source.length];
    const result: OracleResult = { answer: selected[0], detail: selected[1], question, at: new Date().toISOString() };
    const history = readJson<OracleResult[]>("oak-discover-oracle", []);
    localStorage.setItem("oak-discover-oracle", JSON.stringify([...history, result].slice(-10)));
    setOracleResult(result);
  };

  const saveMood = () => {
    const entry: MoodEntry = { date: today, score: moodScore, label: copy.mood.labels[moodScore - 1], note: moodNote.trim().slice(0, 240) };
    const withoutToday = moods.filter((item) => item.date !== today);
    const next = [...withoutToday, entry].slice(-7);
    localStorage.setItem("oak-discover-moods", JSON.stringify(next));
    setMoods(next);
    setMoodNote("");
  };

  const callAi = async (body: Record<string, unknown>) => {
    const response = await fetch("/api/discover", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ ...body, locale }) });
    const payload = await response.json() as { ok?: boolean; result?: DreamReading | CompatibilityReading; error?: string };
    if (!response.ok || !payload.ok || !payload.result) throw new Error(payload.error || "AI_RESPONSE_ERROR");
    return payload.result;
  };

  const submitDream = async (event: FormEvent) => {
    event.preventDefault();
    if (dream.trim().length < 10 || dreamLoading) { setError(copy.errors.invalid); return; }
    setError(""); setDreamLoading(true); setDreamReading(null);
    try { setDreamReading(await callAi({ mode: "dream", dream: dream.trim() }) as DreamReading); }
    catch { setError(copy.errors.ai); }
    finally { setDreamLoading(false); }
  };

  const submitCompatibility = async (event: FormEvent) => {
    event.preventDefault();
    if (!compatA.trim() || !compatB.trim() || compatLoading) { setError(copy.errors.invalid); return; }
    setError(""); setCompatLoading(true); setCompatReading(null);
    try { setCompatReading(await callAi({ mode: "compatibility", personA: compatA.trim(), personB: compatB.trim(), context: compatContext.trim() }) as CompatibilityReading); }
    catch { setError(copy.errors.ai); }
    finally { setCompatLoading(false); }
  };

  const streak = daily?.streak || 0;
  const activeDailyMessage = daily?.date === today ? dailyMessage(locale, today) : null;
  return (
    <div className="page-shell discover-screen">
      <WorkspaceHeading workspace="discover" locale={locale} />

      {error && <div className="oak-global-error" role="alert"><span>!</span><p>{error}</p></div>}

      <div className="discover-grid">
        <section id="daily" className="discover-card discover-daily">
          <FeatureHeader index="01" title={copy.daily.title} subtitle={copy.daily.subtitle} glyph="DAILY RITUAL" />
          <span className="discover-streak" title={copy.streak}>✦ {streak} {locale === "EN" ? "days" : "ngày"}</span>
          {daily?.date === today && activeDailyMessage ? (
            <div className="discover-daily-result">
              <article><small>{copy.daily.energy}</small><b>{activeDailyMessage.energy}</b></article>
              <article><small>{copy.daily.do}</small><p>{activeDailyMessage.do}</p></article>
              <article><small>{copy.daily.avoid}</small><p>{activeDailyMessage.avoid}</p></article>
              <blockquote>{activeDailyMessage.reminder}</blockquote>
              <span className="discover-complete">✓ {copy.daily.opened}</span>
            </div>
          ) : (
            <button className="discover-reveal" type="button" onClick={revealDaily}><span>✦</span><b>{copy.daily.open}</b><i>→</i></button>
          )}
        </section>

        <section id="dream" className="discover-card discover-dream">
          <FeatureHeader index="02" title={copy.dream.title} subtitle={copy.dream.subtitle} glyph="GEMINI REFLECTION" />
          <form className="discover-form" onSubmit={submitDream}>
            <textarea value={dream} onChange={(event) => setDream(event.target.value)} placeholder={copy.dream.placeholder} maxLength={3000} rows={2} disabled={dreamLoading} />
            <div className="discover-form-foot"><small>{[...dream].length}/3000</small><button type="submit" disabled={dreamLoading || dream.trim().length < 10}>{dreamLoading ? copy.dream.loading : copy.dream.action}</button></div>
          </form>
          {dreamReading && <div className="discover-ai-result"><p className="discover-summary">{dreamReading.summary}</p><div className="discover-symbols">{dreamReading.symbols.map((item) => <article key={item.symbol}><b>{item.symbol}</b><p>{item.interpretation}</p></article>)}</div><article className="discover-result-strip"><small>{copy.dream.theme}</small><p>{dreamReading.emotional_theme}</p></article><article className="discover-result-strip"><small>{copy.dream.reflection}</small><p>{dreamReading.reflection}</p></article><article className="discover-result-strip accent"><small>{copy.dream.next}</small><p>{dreamReading.next_step}</p></article></div>}
        </section>

        <section id="oracle" className="discover-card discover-oracle">
          <FeatureHeader index="03" title={copy.oracle.title} subtitle={copy.oracle.subtitle} glyph="QUICK ORACLE" />
          <form className="discover-form discover-oracle-form" onSubmit={askOracle}><input value={oracleQuestion} onChange={(event) => setOracleQuestion(event.target.value)} placeholder={copy.oracle.placeholder} maxLength={220} /><button type="submit">{copy.oracle.action}</button></form>
          {oracleResult && <div className="oracle-result"><span className="oracle-ring"><i /><b>{oracleResult.answer}</b></span><p>{oracleResult.detail}</p><small>“{oracleResult.question}”</small></div>}
        </section>

        <section id="mood" className="discover-card">
          <FeatureHeader index="04" title={copy.mood.title} subtitle={copy.mood.subtitle} glyph="LOCAL CHECK-IN" />
          <div className="mood-picker">{copy.mood.labels.map((label, index) => <button type="button" key={label} aria-label={label} aria-pressed={moodScore === index + 1} data-active={moodScore === index + 1 ? "true" : undefined} onClick={() => setMoodScore(index + 1)}><svg viewBox="0 0 32 32" aria-hidden="true"><circle cx="16" cy="16" r="13" /><circle cx="11" cy="12" r="1" /><circle cx="21" cy="12" r="1" /><path d={["M9 23Q16 12 23 23", "M10 22Q16 16 22 22", "M10 21H22", "M10 19Q16 26 22 19", "M9 18Q16 29 23 18"][index]} /></svg><span>{label}</span></button>)}</div>
          <div className="mood-note"><input value={moodNote} onChange={(event) => setMoodNote(event.target.value)} placeholder={copy.mood.note} maxLength={240} /><button type="button" onClick={saveMood}>{copy.mood.save}</button></div>
          <div className="mood-history"><small>{copy.mood.history}</small><div>{moods.length ? moods.map((entry) => <article key={entry.date} title={entry.note || entry.label}><i style={{ height: `${18 + entry.score * 14}%` }} /><b>{entry.score}</b><span>{entry.date.slice(5).replace("-", "/")}</span></article>) : <p>—</p>}</div></div>
        </section>

        <section id="compatibility" className="discover-card discover-compatibility">
          <FeatureHeader index="05" title={copy.compatibility.title} subtitle={copy.compatibility.subtitle} glyph="GEMINI PLAY" />
          <form className="discover-form" onSubmit={submitCompatibility}>
            <div className="compat-names"><input value={compatA} onChange={(event) => setCompatA(event.target.value)} placeholder={copy.compatibility.a} maxLength={80} /><span>×</span><input value={compatB} onChange={(event) => setCompatB(event.target.value)} placeholder={copy.compatibility.b} maxLength={80} /></div>
            <details className="discover-extra"><summary>{copy.compatibility.context}</summary><textarea value={compatContext} onChange={(event) => setCompatContext(event.target.value)} placeholder={copy.compatibility.context} maxLength={1200} rows={2} /></details>
            <div className="discover-form-foot"><small>{[...compatContext].length}/1200</small><button type="submit" disabled={compatLoading || !compatA.trim() || !compatB.trim()}>{compatLoading ? copy.compatibility.loading : copy.compatibility.action}</button></div>
          </form>
          {compatReading && <div className="discover-ai-result"><p className="discover-summary">{compatReading.summary}</p><div className="compat-metrics"><Metric label={copy.compatibility.metrics[0]} value={compatReading.communication} /><Metric label={copy.compatibility.metrics[1]} value={compatReading.trust} /><Metric label={copy.compatibility.metrics[2]} value={compatReading.chemistry} /><Metric label={copy.compatibility.metrics[3]} value={compatReading.long_term} /></div><div className="compat-lists"><article><small>{copy.compatibility.strengths}</small><ul>{compatReading.strengths.map((item) => <li key={item}>{item}</li>)}</ul></article><article><small>{copy.compatibility.watchouts}</small><ul>{compatReading.watchouts.map((item) => <li key={item}>{item}</li>)}</ul></article></div><article className="discover-result-strip accent"><small>{copy.compatibility.starter}</small><p>{compatReading.conversation_starter}</p></article></div>}
        </section>
      </div>

      <p className="discover-local-note">{copy.localNote}</p>
      <p className="discover-disclaimer">{locale === "EN" ? "Discover experiences are for entertainment and reflection, not professional or predictive advice." : "Các mục Khám phá phục vụ giải trí và chiêm nghiệm, không phải tư vấn chuyên môn hay dự đoán chắc chắn."}</p>
    </div>
  );
}
