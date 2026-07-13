"use client";

import { useState, useRef, useCallback, useEffect } from "react";
import type { FactCheckResult } from "@/lib/types";
import { useLocale } from "@/components/LocaleProvider";

const TEXT = {
  VN: {
    studio: "Xưởng xác thực",
    title: "Xác thực tin tức",
    subtitle: "Paste text hoặc upload ảnh để cross-check qua nhiều engine, ưu tiên nguồn uy tín và đẩy score lên theo độ đa dạng thực tế.",
    realtime: "Thời gian thực",
    liveLabel: "Phân tích đa nguồn",
    parse: "1. Tách claim",
    parseDesc: "Tách câu, lọc claim bẩn, rồi rút ngắn query để search chính xác hơn.",
    crossCheck: "2. Đối chiếu web",
    crossCheckDesc: "Mỗi claim được bắn qua Google + DDG và authority domain để bắt điểm chéo.",
    scoreMix: "3. Chấm điểm tổng hợp",
    scoreMixDesc: "Nguồn uy tín, số domain, số engine và Google Fact Check cùng tạo verdict.",
    input: "Đầu vào",
    textOrImage: "Text hoặc ảnh",
    placeholder: "Paste nội dung tin tức cần xác thực...",
    uploadImage: "Upload ảnh",
    detectText: "Đang nhận diện text...",
    dragDrop: "Kéo thả ảnh vào đây hoặc bấm để chọn",
    submit: "Xác thực",
    submitting: "Đang xác thực...",
    summary: "Score không chỉ là số nguồn. Nó lấy thêm mix engine, mix domain và phản hồi Google Fact Check khi có.",
    previewTitle: "Khi có dữ liệu",
    previewDesc: "Khung kết quả sẽ bật thành score ring, verdict badge và stack nguồn rõ cấp độ uy tín.",
    useCase: "Nên dùng khi",
    useCaseDesc: "Tin tức tài chính, headline nóng, claim có nhiều nguồn đối chiếu. Càng nhiều mix, score càng có ý nghĩa.",
    result: "Kết quả",
    resultTitle: "Kết quả xác thực",
    summaryTitle: "Tóm tắt",
    crossStats: "Thống kê đối chiếu",
    noSources: "Chưa có nguồn",
    sources: "Nguồn",
    notFound: "Không tìm thấy nguồn liên quan",
    verdictLabels: {
      credible: "Đáng tin cậy",
      mixed: "Hỗn hợp",
      unreliable: "Không đáng tin",
      unverifiable: "Không thể xác minh",
    },
    verdictDesc: "score ring, verdict badge và stack nguồn",
    engineMix: "Google và DDG đối chiếu web; AI tùy chọn phản biện trên các nguồn đã thu thập.",
    authority: "Khi có dữ liệu IFCN, score được đẩy theo tín hiệu uy tín.",
    signalMix: "Tính thêm độ đa dạng domain và engine để score lên tự nhiên hơn.",
    sourceLabel: "Nguồn",
    signalLabel: "Tín hiệu",
    score: "Điểm",
    verdict: "Kết luận",
    sourcesCount: "Nguồn",
    noSourcesFound: "Không tìm thấy nguồn liên quan",
    ifcnCertified: "IFCN Certified",
    googleFactCheck: "Google Fact Check",
    scoreLogic: "Logic điểm",
    resultCard: "Kết quả xác thực",
    crossCheckStats: "Thống kê cross-check",
    keyClaims: "Claim chính",
    analysis: "Phân tích",
    linksLabel: "link",
    sitesLabel: "site",
    mixLabel: "mix",
    highLabel: "uy tín",
    reliabilityLabels: {
      high: "Cao",
      medium: "Trung bình",
      low: "Thấp",
    },
  },
  EN: {
    studio: "Fact check studio",
    title: "News verification",
    subtitle: "Paste text or upload an image to cross-check across multiple engines, prioritize trusted sources, and lift the score with real diversity.",
    realtime: "Realtime",
    liveLabel: "Multi-source analysis",
    parse: "1. Parse claims",
    parseDesc: "Split sentences, filter noisy claims, then trim the query for better search precision.",
    crossCheck: "2. Cross-check web",
    crossCheckDesc: "Each claim runs through Google + DDG plus authority domains to catch cross-signal support.",
    scoreMix: "3. Score with mix",
    scoreMixDesc: "Trusted sources, domain count, engine count, and Google Fact Check all shape the verdict.",
    input: "Input",
    textOrImage: "Text or image",
    placeholder: "Paste the news text you want to verify...",
    uploadImage: "Upload image",
    detectText: "Detecting text...",
    dragDrop: "Drop an image here or click to choose",
    submit: "Verify",
    submitting: "Verifying...",
    summary: "Score is more than source count. It also weights engine mix, domain mix, and Google Fact Check response when available.",
    previewTitle: "When data arrives",
    previewDesc: "The result panel lights up as a score ring, verdict badge, and source stack with clear trust levels.",
    useCase: "Best use case",
    useCaseDesc: "Financial news, hot headlines, and claims with multiple sources. More mix means more meaningful scores.",
    result: "Result",
    resultTitle: "Verification result",
    summaryTitle: "Summary",
    crossStats: "Cross-check stats",
    noSources: "No sources",
    sources: "Sources",
    notFound: "No related sources found",
    verdictLabels: {
      credible: "Credible",
      mixed: "Mixed",
      unreliable: "Unreliable",
      unverifiable: "Unverifiable",
    },
    verdictDesc: "score ring, verdict badge, and source stack",
    engineMix: "Google and DDG cross-check the web; optional AI challenges the collected evidence.",
    authority: "When IFCN data exists, the score leans into authority signals.",
    signalMix: "Domain diversity plus engine diversity lifts the score more naturally.",
    sourceLabel: "Sources",
    signalLabel: "Signal",
    score: "Score",
    verdict: "Verdict",
    sourcesCount: "Sources",
    noSourcesFound: "No related sources found",
    ifcnCertified: "IFCN Certified",
    googleFactCheck: "Google Fact Check",
    scoreLogic: "Score logic",
    resultCard: "Verification result",
    crossCheckStats: "Cross-check stats",
    keyClaims: "Key claims",
    analysis: "Analysis",
    linksLabel: "links",
    sitesLabel: "sites",
    mixLabel: "mix",
    highLabel: "high",
    reliabilityLabels: {
      high: "High",
      medium: "Medium",
      low: "Low",
    },
  },
} as const;

type LocaleText = (typeof TEXT)[keyof typeof TEXT];

const OCR_LANGS = "vie+eng";
const OCR_MAX_WIDTH = 2200;
const OCR_BOTTOM_CROP_RATIO = 0.58;

function ScoreBar({ score }: { score: number }) {
  const clamped = Math.max(0, Math.min(100, score || 0));
  const color = clamped >= 80 ? "bg-emerald-500" : clamped >= 50 ? "bg-amber-500" : "bg-red-500";
  return (
    <div className="flex items-center gap-4">
      <div className="flex-1 h-2.5 bg-zinc-200 dark:bg-zinc-700 rounded-full overflow-hidden">
        <div className={`h-full ${color} rounded-full transition-all duration-500`} style={{ width: `${clamped}%` }} />
      </div>
      <span className="font-mono text-xl font-bold tabular-nums text-zinc-900 dark:text-zinc-100 w-12 text-right">{clamped}</span>
    </div>
  );
}

function ScoreRing({ score, label }: { score: number; label: string }) {
  const clamped = Math.max(0, Math.min(100, score || 0));
  const tone = clamped >= 80 ? "from-emerald-400 via-emerald-500 to-lime-400" : clamped >= 50 ? "from-amber-400 via-amber-500 to-orange-400" : "from-red-400 via-red-500 to-rose-400";
  return (
    <div className="relative h-32 w-32 sm:h-36 sm:w-36">
      <div className={`absolute inset-0 rounded-full bg-gradient-to-br ${tone} p-1 shadow-[0_20px_60px_-20px_rgba(16,185,129,0.45)]`}>
        <div className="grid h-full w-full place-items-center rounded-full border border-white/10 bg-zinc-950/95 backdrop-blur-sm">
          <div className="text-center">
            <div className="font-mono text-4xl sm:text-5xl font-black tabular-nums text-white leading-none">{clamped}</div>
            <div className="mt-1 text-[10px] sm:text-[11px] uppercase tracking-[0.35em] text-zinc-400">{label}</div>
          </div>
        </div>
      </div>
    </div>
  );
}

function VerdictBadge({ verdict, labels }: { verdict: string; labels: Record<string, string> }) {
  const styles: Record<string, string> = {
    credible: "bg-emerald-50 dark:bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border-emerald-200 dark:border-emerald-500/20",
    mixed: "bg-amber-50 dark:bg-amber-500/10 text-amber-600 dark:text-amber-400 border-amber-200 dark:border-amber-500/20",
    unreliable: "bg-red-50 dark:bg-red-500/10 text-red-600 dark:text-red-400 border-red-200 dark:border-red-500/20",
    unverifiable: "bg-zinc-50 dark:bg-zinc-500/10 text-zinc-600 dark:text-zinc-400 border-zinc-200 dark:border-zinc-500/20",
  };
  return (
    <span className={`inline-block px-2.5 py-1 rounded-md text-xs font-semibold tracking-wide uppercase border ${styles[verdict] || styles.unverifiable}`}>
      {labels[verdict] || verdict}
    </span>
  );
}

function MetricCard({ label, value, detail }: { label: string; value: string; detail: string }) {
  return (
    <div className="rounded-2xl border border-zinc-200/80 bg-white/80 px-4 py-3 shadow-lg shadow-black/5 backdrop-blur-sm dark:border-white/10 dark:bg-white/5 dark:shadow-black/10">
      <div className="text-[10px] uppercase tracking-[0.3em] text-zinc-500 dark:text-zinc-400">{label}</div>
      <div className="mt-2 text-xl font-semibold text-zinc-900 dark:text-white">{value}</div>
      <div className="mt-1 text-xs leading-relaxed text-zinc-600 dark:text-zinc-400">{detail}</div>
    </div>
  );
}

function SummaryPill({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-2xl border border-zinc-200/80 dark:border-zinc-800 bg-white/70 dark:bg-zinc-900/50 px-4 py-3 shadow-sm">
      <div className="text-[10px] uppercase tracking-[0.3em] text-zinc-400 dark:text-zinc-500">{label}</div>
      <div className="mt-2 text-base font-semibold text-zinc-900 dark:text-zinc-100">{value}</div>
    </div>
  );
}

function sourceSummaryOnly(summary: string): string {
  return summary.replace(/\sAI\s\(\d+%\):[\s\S]*$/u, "").trim();
}

function looksLikeVietnamese(text: string): boolean {
  return /[àáạảãâầấậẩẫăằắặẳẵèéẹẻẽêềếệểễìíịỉĩòóọỏõôồốộổỗơờớợởỡùúụủũưừứựửữỳýỵỷỹđ]/iu.test(text)
    || /\b(Tìm thấy|nguồn|xác nhận|phản bác|trung lập|bằng chứng|cho thấy|tuy nhiên|không cung cấp|lãi suất)\b/iu.test(text);
}

function summaryForLocale(summary: string, locale: "VN" | "EN"): string {
  const clean = sourceSummaryOnly(summary);
  if (locale === "VN" || !looksLikeVietnamese(clean)) return clean;

  const found = clean.match(/Tìm thấy\s+(\d+)\s+nguồn liên quan/i);
  const counts = clean.match(/(\d+)\s+nguồn xác nhận,\s+(\d+)\s+nguồn phản bác,\s+(\d+)\s+trung lập/i);
  const cross = clean.match(/Cross-check:\s+(\d+)\s+domain,\s+(\d+)\s+engine/i);
  const parts: string[] = [];

  if (found) parts.push(`Found ${found[1]} related sources.`);
  if (counts) parts.push(`${counts[1]} confirming sources, ${counts[2]} refuting sources, ${counts[3]} neutral sources.`);
  if (cross) parts.push(`Cross-check: ${cross[1]} domains, ${cross[2]} engines.`);
  if (/Không tìm thấy nguồn tin liên quan/i.test(clean)) parts.push("No related web sources found.");
  if (/nguồn uy tín/i.test(clean)) parts.push("High-reliability sources are included in the evidence stack.");
  if (/nguồn phản bác đáng kể|cần thận trọng/i.test(clean)) parts.push("Significant refuting sources were found; use caution.");

  return parts.length > 0 ? parts.join(" ") : "Evidence summary is available. Rerun verification to regenerate the full summary in English.";
}

function looksLikeEnglishAiSummary(summary: string): boolean {
  return /\b(provided|evidence|claims|therefore|insufficient|truthfulness|related|assess)\b/iu.test(summary);
}

function verdictText(result: FactCheckResult, t: LocaleText): string {
  return t.verdictLabels[result.verdict] || result.verdict;
}

function getAiStatusCopy(locale: "EN" | "VN", result: FactCheckResult) {
  if (result.ai_analysis) {
    const hideStaleEnglish = locale === "VN" && looksLikeEnglishAiSummary(result.ai_analysis.summary);
    const hideVietnamese = locale === "EN" && looksLikeVietnamese(result.ai_analysis.summary);
    return {
      title: locale === "EN" ? "AI assessment" : "Phân tích AI",
      body: hideVietnamese
        ? "AI analysis was generated in Vietnamese for this cached result. Rerun verification to regenerate the assessment in English."
        : hideStaleEnglish
          ? "AI đã phản biện trên bằng chứng đã thu thập. Hãy chạy lại xác thực để nhận bản phân tích tiếng Việt theo logic mới."
          : result.ai_analysis.summary,
      hint:
        locale === "EN"
          ? "AI challenges only the collected Google/DDG evidence and never invents sources."
          : "AI chỉ phản biện trên bằng chứng Google/DDG đã thu thập và không tự tạo nguồn.",
      tone: "border-cyan-500/20 bg-cyan-500/8",
      labelClass: "text-cyan-500",
      confidence: `${result.ai_analysis.confidence}%`,
    };
  }

  const status = result.ai_status;
  const isError = status?.state === "request_failed";
  const isDisabled = status?.state === "missing_api_key";
  return {
    title: locale === "EN" ? "AI reviewer status" : "Trạng thái AI reviewer",
    body:
      status?.message ||
      (locale === "EN"
        ? "AI reviewer did not run for this request."
        : "AI reviewer chưa chạy cho lượt kiểm tra này."),
    hint: isDisabled
      ? locale === "EN"
        ? "Add FACTCHECK_GITHUB_TOKEN, GITHUB_TOKEN, or GH_TOKEN in .env, or sign in with gh auth login, then restart the Fact-Check Worker."
        : "Thêm FACTCHECK_GITHUB_TOKEN, GITHUB_TOKEN hoặc GH_TOKEN vào .env, hoặc đăng nhập gh auth login, rồi restart Fact-Check Worker."
      : locale === "EN"
        ? "AI only judges the collected evidence. It stays off when no usable evidence exists."
        : "AI chỉ chấm trên bằng chứng đã thu thập. Nếu không có evidence đủ dùng thì AI sẽ bỏ qua.",
    tone: isError ? "border-red-500/20 bg-red-500/8" : isDisabled ? "border-amber-500/20 bg-amber-500/8" : "border-zinc-200 dark:border-zinc-800 bg-zinc-50/80 dark:bg-zinc-900/50",
    labelClass: isError ? "text-red-500" : isDisabled ? "text-amber-500" : "text-zinc-500",
    confidence: status?.provider && status?.model ? `${status.provider}:${status.model}` : status?.model || "AI",
  };
}

function StatStack({ sources, t, hasAi }: { sources: Array<{ url: string; reliability: string; engine?: string; agrees: boolean | null }>; t: LocaleText; hasAi: boolean }) {
  const domains = new Set<string>();
  const engines = new Set<string>();
  let confirming = 0;
  let opposing = 0;
  let high = 0;

  for (const source of sources) {
    const domain = source.url.replace(/^https?:\/\//, "").split("/")[0].replace(/^www\./, "");
    domains.add(domain);
    if (source.engine) engines.add(source.engine);
    if (source.agrees === true) confirming += 1;
    if (source.agrees === false) opposing += 1;
    if (source.reliability === "high") high += 1;
  }

  return (
    <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
      <SummaryPill label={t.sourcesCount} value={`${sources.length} ${t.linksLabel}`} />
      <SummaryPill label="Domain" value={`${domains.size} ${t.sitesLabel}`} />
      <SummaryPill label="Engine" value={`${engines.size + (hasAi ? 1 : 0)} ${t.mixLabel}`} />
      <SummaryPill label={t.signalLabel} value={`${confirming} / ${opposing} / ${high} ${t.highLabel}`} />
    </div>
  );
}

function safeSourceUrl(value: string): string {
  try {
    const url = new URL(value);
    return url.protocol === "http:" || url.protocol === "https:" ? value : "#";
  } catch {
    return "#";
  }
}

function SourceRow({ source, t }: { source: { title: string; url: string; snippet: string; agrees: boolean | null; reliability: string; publisher?: string; rating?: string; engine?: string }; t: LocaleText }) {
  const icon = source.agrees === true ? "✓" : source.agrees === false ? "✗" : "–";
  const iconColor = source.agrees === true ? "text-emerald-500" : source.agrees === false ? "text-red-500" : "text-zinc-400";
  const isIFCN = !!source.publisher;
  const relColor: Record<string, string> = {
    high: "text-emerald-500 dark:text-emerald-400",
    medium: "text-amber-500 dark:text-amber-400",
    low: "text-zinc-400 dark:text-zinc-500",
  };
  return (
    <div className="w-full min-w-0 rounded-2xl border border-zinc-200/80 dark:border-zinc-800 bg-white/75 dark:bg-zinc-950/55 shadow-sm overflow-hidden">
      <div className="h-1.5 bg-gradient-to-r from-zinc-300 via-zinc-200 to-zinc-100 dark:from-zinc-700 dark:via-zinc-800 dark:to-zinc-900" />
      <div className="flex items-start gap-3 p-4">
        <span className={`mt-0.5 font-mono text-sm font-bold ${iconColor}`}>{icon}</span>
        <div className="flex-1 min-w-0">
          <a href={safeSourceUrl(source.url)} target="_blank" rel="noopener noreferrer" className="text-sm sm:text-[15px] font-semibold text-zinc-900 dark:text-zinc-100 hover:text-emerald-500 dark:hover:text-emerald-400 transition-colors truncate block">
            {source.title}
          </a>
          <div className="mt-2 flex items-center gap-1.5 flex-wrap min-w-0">
            {source.engine && (
              <span className="text-[10px] font-semibold uppercase tracking-wider px-1.5 py-0.5 rounded-full bg-zinc-100 dark:bg-zinc-800 text-zinc-500 dark:text-zinc-400 border border-zinc-200 dark:border-zinc-700">
                {source.engine === "google_factcheck"
                  ? t.googleFactCheck
                  : source.engine.replaceAll("_", " ").replace(/\b\w/g, (char) => char.toUpperCase())}
              </span>
            )}
            {isIFCN && (
              <span className="text-[10px] font-semibold uppercase tracking-wider px-1.5 py-0.5 rounded-full bg-emerald-50 dark:bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border border-emerald-200 dark:border-emerald-500/20">
                {t.ifcnCertified}
              </span>
            )}
            {source.rating && <span className={`text-[10px] font-semibold px-1.5 py-0.5 rounded-full border ${source.agrees === true ? "text-emerald-500 border-emerald-200/70 dark:border-emerald-500/20 bg-emerald-50/70 dark:bg-emerald-500/10" : source.agrees === false ? "text-red-500 border-red-200/70 dark:border-red-500/20 bg-red-50/70 dark:bg-red-500/10" : "text-zinc-400 border-zinc-200/70 dark:border-zinc-700 bg-zinc-50/70 dark:bg-zinc-800/50"}`}>{source.rating}</span>}
            <span className={`text-[10px] font-semibold uppercase tracking-wider px-1.5 py-0.5 rounded-full border ${relColor[source.reliability] || ""} bg-white/60 dark:bg-zinc-900/80 border-current/20`}>
              {t.reliabilityLabels[source.reliability as keyof typeof t.reliabilityLabels] || source.reliability}
            </span>
          </div>
          <p className="mt-2 line-clamp-2 text-xs leading-relaxed text-zinc-500 dark:text-zinc-400 sm:text-sm">{source.snippet}</p>
        </div>
      </div>
    </div>
  );
}

function isGarbage(text: string): boolean {
  if (text.length < 5) return true;
  const alphaNum = text.replace(/[^a-zA-Z0-9À-ỹ]/g, "").length;
  if (alphaNum / text.length < 0.4) return true;
  const noisePattern = /[*\\\/|~^]{2,}/;
  if (noisePattern.test(text)) return true;
  const words = text.split(/\s+/);
  const shortSymbolWords = words.filter((w) => w.length <= 2 && /[^a-zA-Z0-9À-ỹ]/.test(w)).length;
  if (shortSymbolWords / words.length > 0.5) return true;
  return false;
}

function cleanOcrText(text: string): string {
  return text
    .replace(/\u0000/g, "")
    .replace(/[ \t]+\n/g, "\n")
    .replace(/\n{3,}/g, "\n\n")
    .replace(/[ \t]{2,}/g, " ")
    .trim();
}

function scoreOcrText(text: string, confidence: number): number {
  if (!text) return -1;
  const normalized = cleanOcrText(text);
  if (!normalized) return -1;
  const alphaNum = normalized.replace(/[^a-zA-Z0-9À-ỹ]/g, "").length;
  const printableRatio = alphaNum / Math.max(normalized.length, 1);
  const wordCount = normalized.split(/\s+/).filter(Boolean).length;
  let score = Number.isFinite(confidence) ? confidence : 0;
  score += Math.min(normalized.length / 16, 18);
  score += Math.min(wordCount, 18) * 1.2;
  score += printableRatio * 14;
  if (normalized.includes("\n")) score += 2;
  if (printableRatio < 0.45) score -= 12;
  return score;
}

async function blobFromCanvas(canvas: HTMLCanvasElement): Promise<Blob> {
  const blob = await new Promise<Blob | null>((resolve) => canvas.toBlob(resolve, "image/png"));
  if (!blob) throw new Error("Failed to prepare OCR image");
  return blob;
}

async function loadImage(file: File): Promise<HTMLImageElement> {
  const url = URL.createObjectURL(file);
  try {
    const img = new Image();
    img.decoding = "async";
    img.src = url;
    await new Promise<void>((resolve, reject) => {
      img.onload = () => resolve();
      img.onerror = () => reject(new Error("Image load failed"));
    });
    if (img.naturalWidth * img.naturalHeight > 40_000_000) {
      throw new Error("Image dimensions are too large");
    }
    return img;
  } finally {
    URL.revokeObjectURL(url);
  }
}

async function renderOcrVariantFromImage(img: HTMLImageElement, options: { cropBottom?: boolean; threshold?: boolean }): Promise<Blob> {
  const sourceY = options.cropBottom ? Math.floor(img.naturalHeight * (1 - OCR_BOTTOM_CROP_RATIO)) : 0;
  const sourceH = options.cropBottom ? Math.max(1, Math.floor(img.naturalHeight * OCR_BOTTOM_CROP_RATIO)) : img.naturalHeight;
  const desiredScale = Math.min(2.6, Math.max(1.25, OCR_MAX_WIDTH / Math.max(img.naturalWidth, 1)));
  const safeScale = Math.sqrt(20_000_000 / Math.max(img.naturalWidth * sourceH, 1));
  const scale = Math.min(desiredScale, Math.max(0.5, safeScale));
  const canvas = document.createElement("canvas");
  canvas.width = Math.round(img.naturalWidth * scale);
  canvas.height = Math.round(sourceH * scale);
  const ctx = canvas.getContext("2d");
  if (!ctx) throw new Error("Canvas unavailable");
  ctx.imageSmoothingEnabled = true;
  ctx.imageSmoothingQuality = "high";
  ctx.filter = options.threshold ? "grayscale(1) contrast(2.1) brightness(1.06)" : "grayscale(1) contrast(1.65) brightness(1.08)";
  ctx.drawImage(img, 0, sourceY, img.naturalWidth, sourceH, 0, 0, canvas.width, canvas.height);
  if (options.threshold) {
    const imageData = ctx.getImageData(0, 0, canvas.width, canvas.height);
    const pixels = imageData.data;
    const threshold = otsuThreshold(imageData);
    for (let i = 0; i < pixels.length; i += 4) {
      const luminance = (pixels[i] * 0.299 + pixels[i + 1] * 0.587 + pixels[i + 2] * 0.114);
      const value = luminance > threshold ? 255 : 0;
      pixels[i] = value;
      pixels[i + 1] = value;
      pixels[i + 2] = value;
      pixels[i + 3] = 255;
    }
    ctx.putImageData(imageData, 0, 0);
  }
  return blobFromCanvas(canvas);
}

function otsuThreshold(imageData: ImageData): number {
  const histogram = new Array<number>(256).fill(0);
  const pixels = imageData.data;
  for (let i = 0; i < pixels.length; i += 4) {
    const luminance = Math.round(pixels[i] * 0.299 + pixels[i + 1] * 0.587 + pixels[i + 2] * 0.114);
    histogram[luminance] += 1;
  }
  const total = pixels.length / 4;
  const sum = histogram.reduce((value, count, index) => value + index * count, 0);
  let backgroundWeight = 0;
  let backgroundSum = 0;
  let bestVariance = -1;
  let threshold = 165;
  for (let index = 0; index < histogram.length; index += 1) {
    backgroundWeight += histogram[index];
    if (!backgroundWeight) continue;
    const foregroundWeight = total - backgroundWeight;
    if (!foregroundWeight) break;
    backgroundSum += index * histogram[index];
    const difference = backgroundSum / backgroundWeight - (sum - backgroundSum) / foregroundWeight;
    const variance = backgroundWeight * foregroundWeight * difference * difference;
    if (variance > bestVariance) [bestVariance, threshold] = [variance, index];
  }
  return threshold;
}

async function buildOcrVariants(file: File, image: HTMLImageElement) {
  return [
    { label: "original", blob: file },
    { label: "enhanced", blob: await renderOcrVariantFromImage(image, { threshold: false }) },
    { label: "threshold", blob: await renderOcrVariantFromImage(image, { threshold: true }) },
    { label: "bottom", blob: await renderOcrVariantFromImage(image, { cropBottom: true }) },
    { label: "bottom-threshold", blob: await renderOcrVariantFromImage(image, { cropBottom: true, threshold: true }) },
  ];
}

async function recognizeBestOcrText(file: File): Promise<string> {
  if (!file.type.startsWith("image/") || file.size > 12 * 1024 * 1024) throw new Error("Unsupported image");
  const Tesseract = await import("tesseract.js");
  const variants = await buildOcrVariants(file, await loadImage(file));
  const worker = await Tesseract.createWorker(OCR_LANGS);
  let bestText = "";
  let bestScore = -1;
  try {
    for (const variant of variants) {
      const { data } = await worker.recognize(variant.blob);
      const cleaned = cleanOcrText(data.text || "");
      const confidence = typeof data.confidence === "number" ? data.confidence : 0;
      const score = scoreOcrText(cleaned, confidence);
      if (cleaned && score > bestScore) [bestScore, bestText] = [score, cleaned];
    }
  } finally {
    await worker.terminate();
  }
  return bestText;
}

export default function FactCheckPage() {
  const { locale } = useLocale();
  const t = TEXT[locale];
  const [text, setText] = useState("");
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<FactCheckResult | null>(null);
  const [error, setError] = useState("");
  const [ocrLoading, setOcrLoading] = useState(false);
  const [dragOver, setDragOver] = useState(false);
  const fileRef = useRef<HTMLInputElement>(null);
  const pollTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => () => {
    if (pollTimerRef.current) clearTimeout(pollTimerRef.current);
  }, []);

  const handleSubmit = useCallback(async () => {
    if (!text.trim()) return;
    if (pollTimerRef.current) {
      clearTimeout(pollTimerRef.current);
      pollTimerRef.current = null;
    }
    setLoading(true);
    setError("");
    setResult(null);
    try {
      const res = await fetch("/api/factcheck", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text: text.trim() }),
      });
      if (!res.ok) throw new Error(`Server error: ${res.status}`);
      const data = await res.json();
      if (!data.ok) throw new Error(data.error || "Request failed");
      const id = data.id;
      if (!id) throw new Error("No ID returned");

      let attempts = 0;
      const poll = async () => {
        try {
          const check = await fetch(`/api/factcheck?id=${id}`);
          if (!check.ok) throw new Error("Poll failed");
          const item = await check.json();
          if (!item) throw new Error("No data returned");

          if (item.status === "done" && item.result) {
            setResult(item.result);
            setLoading(false);
            return;
          }
          if (item.status === "error") {
            setError(item.result?.summary || "Processing error");
            setLoading(false);
            return;
          }
          attempts++;
          if (attempts > 60) {
            setError("Timeout - please try again");
            setLoading(false);
            return;
          }
          pollTimerRef.current = setTimeout(poll, 3000);
        } catch (err) {
          setError(err instanceof Error ? err.message : "Poll error");
          setLoading(false);
        }
      };
      poll();
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Request failed");
      setLoading(false);
    }
  }, [text]);

  const handleImageUpload = useCallback(async (file: File) => {
    setOcrLoading(true);
    setError("");
    setResult(null);
    try {
      const bestText = await recognizeBestOcrText(file);
      if (bestText) {
        setText(bestText);
      } else {
        setError("No text detected in image");
      }
    } catch {
      setError("OCR failed - please paste text manually");
    } finally {
      setOcrLoading(false);
    }
  }, []);

  const handlePaste = useCallback((event: React.ClipboardEvent<HTMLTextAreaElement>) => {
    const imageItem = Array.from(event.clipboardData.items).find((item) => item.type.startsWith("image/"));
    const image = imageItem?.getAsFile();
    if (!image) return;
    event.preventDefault();
    void handleImageUpload(image);
  }, [handleImageUpload]);

  const handleDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      setDragOver(false);
      const file = e.dataTransfer.files?.[0];
      if (file && file.type.startsWith("image/")) handleImageUpload(file);
    },
    [handleImageUpload]
  );

  const cleanClaims = result?.key_claims.filter((c) => !isGarbage(c)) || [];
  const sourceStats = result ? {
    domains: new Set(result.sources.map((s) => s.url.replace(/^https?:\/\//, "").split("/")[0].replace(/^www\./, ""))).size,
    engines: new Set(result.sources.map((s) => s.engine).filter(Boolean)).size + (result.ai_analysis ? 1 : 0),
    confirming: result.sources.filter((s) => s.agrees === true).length,
    opposing: result.sources.filter((s) => s.agrees === false).length,
    high: result.sources.filter((s) => s.reliability === "high").length,
  } : null;
  const aiStatusCard = result ? getAiStatusCopy(locale, result) : null;
  const displaySummary = result ? summaryForLocale(result.summary, locale) : "";

  return (
    <div className="relative">
      <div className="pointer-events-none absolute inset-x-0 top-0 h-[460px] bg-[radial-gradient(circle_at_top_left,_rgba(16,185,129,0.14),_transparent_40%),radial-gradient(circle_at_80%_10%,_rgba(239,68,68,0.10),_transparent_28%),linear-gradient(180deg,rgba(255,255,255,0.02),transparent)] dark:bg-[radial-gradient(circle_at_top_left,_rgba(16,185,129,0.12),_transparent_40%),radial-gradient(circle_at_80%_10%,_rgba(239,68,68,0.12),_transparent_28%),linear-gradient(180deg,rgba(255,255,255,0.02),transparent)]" />
      <div className="relative page-shell">
        <div className="mb-6 grid gap-4 lg:grid-cols-[1.15fr_0.85fr]">
          <div className="rounded-[30px] border border-zinc-200/80 bg-white/85 p-5 sm:p-7 shadow-[0_32px_100px_-30px_rgba(0,0,0,0.22)] backdrop-blur-md dark:border-white/10 dark:bg-zinc-950/75 dark:shadow-[0_32px_100px_-30px_rgba(0,0,0,0.85)]">
            <div className="text-[10px] uppercase tracking-[0.35em] text-zinc-500 dark:text-zinc-500">{t.studio}</div>
            <div className="mt-3 flex items-end justify-between gap-4">
              <div>
                <h1 className="text-3xl sm:text-5xl font-black tracking-tight text-zinc-900 dark:text-white">{t.title}</h1>
                <p className="mt-3 max-w-2xl text-sm sm:text-base text-zinc-600 dark:text-zinc-400 leading-relaxed">{t.subtitle}</p>
              </div>
              <div className="hidden xl:block text-right">
                <div className="text-[10px] uppercase tracking-[0.3em] text-zinc-500 dark:text-zinc-500">{t.realtime}</div>
                <div className="mt-2 inline-flex items-center gap-2 rounded-full border border-emerald-500/20 bg-emerald-500/10 px-3 py-1.5 text-xs font-semibold text-emerald-300">
                  <span className="h-2 w-2 rounded-full bg-emerald-400 shadow-[0_0_16px_rgba(52,211,153,0.7)]" />
                  {t.liveLabel}
                </div>
              </div>
            </div>
            <div className="mt-6 grid gap-3 sm:grid-cols-3">
              <MetricCard label="Search stack" value="Google + DDG + AI" detail={t.engineMix} />
              <MetricCard label={locale === "EN" ? "Authority" : "Uy tín"} value={t.googleFactCheck} detail={t.authority} />
              <MetricCard label="Signal mix" value="Domains + Engines" detail={t.signalMix} />
            </div>
          </div>

          <aside className="rounded-[30px] border border-zinc-200/80 dark:border-zinc-800 bg-white/75 dark:bg-zinc-950/55 p-5 sm:p-6 shadow-sm backdrop-blur-sm">
            <div className="text-[10px] uppercase tracking-[0.35em] text-zinc-400 dark:text-zinc-500">
              {locale === "EN" ? "How it reads" : "Cách hệ thống đọc tin"}
            </div>
            <div className="mt-4 space-y-3">
              <div className="rounded-2xl border border-emerald-500/15 bg-emerald-500/8 px-4 py-3">
                <div className="text-sm font-semibold text-zinc-900 dark:text-zinc-100">{t.parse}</div>
                <p className="mt-1 text-sm text-zinc-500 dark:text-zinc-400">{t.parseDesc}</p>
              </div>
              <div className="rounded-2xl border border-amber-500/15 bg-amber-500/8 px-4 py-3">
                <div className="text-sm font-semibold text-zinc-900 dark:text-zinc-100">{t.crossCheck}</div>
                <p className="mt-1 text-sm text-zinc-500 dark:text-zinc-400">{t.crossCheckDesc}</p>
              </div>
              <div className="rounded-2xl border border-zinc-200 dark:border-zinc-800 bg-zinc-50/80 dark:bg-zinc-900/50 px-4 py-3">
                <div className="text-sm font-semibold text-zinc-900 dark:text-zinc-100">{t.scoreMix}</div>
                <p className="mt-1 text-sm text-zinc-500 dark:text-zinc-400">{t.scoreMixDesc}</p>
              </div>
            </div>
          </aside>
        </div>

        <div className="grid gap-4 lg:grid-cols-[1.02fr_0.98fr]">
          <div className="rounded-[28px] border border-zinc-200/80 dark:border-zinc-800 bg-white/78 dark:bg-zinc-950/55 p-4 sm:p-5 shadow-sm backdrop-blur-sm">
            <div className="flex items-center justify-between gap-3">
              <div>
                <div className="text-[10px] uppercase tracking-[0.32em] text-zinc-400 dark:text-zinc-500">{t.input}</div>
                <h2 className="mt-1 text-lg font-semibold text-zinc-900 dark:text-zinc-100">{t.textOrImage}</h2>
              </div>
              <div className="hidden sm:flex items-center gap-2 text-xs text-zinc-500 dark:text-zinc-400">
                <span className="h-2 w-2 rounded-full bg-emerald-400" />
                Multi-pass OCR
              </div>
            </div>

            <textarea
              className="mt-4 w-full h-36 sm:h-44 rounded-2xl border border-zinc-200/80 dark:border-zinc-800 bg-zinc-50/90 dark:bg-zinc-900/60 px-4 py-4 text-sm sm:text-[15px] leading-relaxed text-zinc-900 dark:text-zinc-100 placeholder:text-zinc-400 focus:outline-none focus:ring-2 focus:ring-emerald-500/40 resize-none shadow-inner shadow-black/5"
              placeholder={t.placeholder}
              value={text}
              onChange={(e) => setText(e.target.value)}
              onPaste={handlePaste}
            />
            <p className="mt-2 text-xs text-zinc-400 dark:text-zinc-500">
              {locale === "EN" ? "Paste an image directly with Ctrl+V" : "Dán ảnh trực tiếp bằng Ctrl+V"}
            </p>

            <div
              className={`mt-4 rounded-2xl border-2 border-dashed px-4 py-4 text-center transition-colors ${
                dragOver
                  ? "border-emerald-500 bg-emerald-50 dark:bg-emerald-500/10"
                  : "border-zinc-200 dark:border-zinc-800 bg-zinc-50/70 dark:bg-zinc-900/40 hover:border-zinc-300 dark:hover:border-zinc-700"
              }`}
              onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
              onDragLeave={() => setDragOver(false)}
              onDrop={handleDrop}
            >
              <input ref={fileRef} type="file" accept="image/*" className="hidden" onChange={(e) => { const file = e.target.files?.[0]; if (file) void handleImageUpload(file); e.target.value = ""; }} />
              <button type="button" onClick={() => fileRef.current?.click()} className="inline-flex items-center gap-2 text-sm font-medium text-zinc-600 dark:text-zinc-300 hover:text-emerald-500 dark:hover:text-emerald-400 transition-colors">
                {ocrLoading ? (
                  <>
                    <svg className="animate-spin h-4 w-4" viewBox="0 0 24 24"><circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" /><path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" /></svg>
                    {t.detectText}
                  </>
                ) : (
                  <>
                    <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" d="M3 16.5v2.25A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75V16.5m-13.5-9L12 3m0 0l4.5 4.5M12 3v13.5" /></svg>
                    {t.uploadImage}
                  </>
                )}
              </button>
              <p className="mt-2 text-xs text-zinc-400 dark:text-zinc-500">{t.dragDrop}</p>
            </div>

            <div className="mt-4 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
              <div className="flex flex-wrap gap-2 text-[10px] uppercase tracking-[0.28em] text-zinc-400 dark:text-zinc-500">
                <span className="rounded-full border border-zinc-200 dark:border-zinc-800 px-2.5 py-1">multi source</span>
                <span className="rounded-full border border-zinc-200 dark:border-zinc-800 px-2.5 py-1">ifcn aware</span>
                <span className="rounded-full border border-zinc-200 dark:border-zinc-800 px-2.5 py-1">mix score</span>
              </div>
              <button
                onClick={handleSubmit}
                disabled={loading || !text.trim()}
                className="inline-flex w-full sm:w-auto items-center justify-center rounded-full bg-emerald-500 px-6 py-3 text-sm font-semibold text-zinc-950 shadow-lg shadow-emerald-500/20 transition-all hover:bg-emerald-400 hover:shadow-emerald-500/30 disabled:cursor-not-allowed disabled:bg-zinc-300 disabled:text-zinc-500 dark:bg-emerald-400 dark:text-zinc-950 dark:hover:bg-emerald-300 dark:disabled:bg-zinc-700 dark:disabled:text-zinc-400"
              >
                {loading ? t.submitting : t.submit}
              </button>
            </div>
          </div>

          <div className="rounded-[28px] border border-zinc-200/80 bg-white/85 p-4 sm:p-5 shadow-[0_20px_50px_-20px_rgba(0,0,0,0.18)] backdrop-blur-sm dark:border-zinc-800 dark:bg-zinc-950/80 dark:shadow-[0_20px_50px_-20px_rgba(0,0,0,0.8)]">
            <div className="text-[10px] uppercase tracking-[0.35em] text-zinc-500 dark:text-zinc-500">
              {locale === "EN" ? "Live preview" : "Xem trước trực tiếp"}
            </div>
            <div className="mt-4 grid gap-3">
              <div className="rounded-3xl border border-zinc-200/70 bg-zinc-50/90 p-4 dark:border-white/10 dark:bg-white/5">
                <div className="flex items-start justify-between gap-4">
                  <div>
                    <div className="text-sm font-semibold text-zinc-900 dark:text-white">{t.scoreLogic}</div>
                    <p className="mt-1 text-sm leading-relaxed text-zinc-600 dark:text-zinc-400">{t.summary}</p>
                  </div>
                  <div className="hidden sm:block rounded-2xl border border-zinc-200/80 bg-white/70 px-3 py-2 text-xs text-zinc-500 dark:border-white/10 dark:bg-white/5 dark:text-zinc-300">
                    `0 - 100`
                  </div>
                </div>
              </div>
              <div className="rounded-3xl border border-zinc-200/70 bg-gradient-to-br from-emerald-50 via-white to-rose-50 p-4 dark:border-white/10 dark:from-emerald-500/10 dark:via-zinc-900/40 dark:to-red-500/10">
                <div className="text-sm font-semibold text-zinc-900 dark:text-white">{t.previewTitle}</div>
                <p className="mt-1 text-sm leading-relaxed text-zinc-600 dark:text-zinc-400">{t.previewDesc}</p>
              </div>
              <div className="rounded-3xl border border-zinc-200/70 bg-zinc-50/90 p-4 dark:border-white/10 dark:bg-white/5">
                <div className="text-sm font-semibold text-zinc-900 dark:text-white">{t.useCase}</div>
                <p className="mt-1 text-sm leading-relaxed text-zinc-600 dark:text-zinc-400">{t.useCaseDesc}</p>
              </div>
            </div>
          </div>
        </div>

      {error && (
        <div className="mt-5 border border-red-200 dark:border-red-500/20 bg-red-50 dark:bg-red-500/10 rounded-2xl px-5 py-4 shadow-sm">
          <p className="text-sm text-red-600 dark:text-red-400">{error}</p>
        </div>
      )}

      {result && (
        <div className="mt-6 space-y-4">
          <div className="grid gap-4 lg:grid-cols-[0.82fr_1.18fr]">
            <div className="min-w-0 rounded-[28px] border border-zinc-200/80 dark:border-zinc-800 bg-white/80 dark:bg-zinc-950/60 p-5 shadow-sm">
              <div className="flex items-start justify-between gap-4">
                <div>
                  <div className="text-[10px] uppercase tracking-[0.35em] text-zinc-400 dark:text-zinc-500">{t.result}</div>
                  <h2 className="mt-1 text-xl font-semibold text-zinc-900 dark:text-zinc-100">{t.resultTitle}</h2>
                </div>
                <VerdictBadge verdict={result.verdict} labels={t.verdictLabels} />
              </div>
              <div className="mt-5 flex flex-col sm:flex-row items-center gap-5">
                <ScoreRing score={result.score} label={t.score} />
                <div className="flex-1 space-y-3">
                  <ScoreBar score={result.score} />
                  <div className="rounded-2xl border border-zinc-200/80 dark:border-zinc-800 bg-zinc-50/70 dark:bg-zinc-900/50 px-4 py-3">
                    <div className="text-[10px] uppercase tracking-[0.3em] text-zinc-400 dark:text-zinc-500">{t.summaryTitle}</div>
                    <p className="mt-2 text-sm leading-relaxed text-zinc-700 dark:text-zinc-300">{displaySummary}</p>
                  </div>
                </div>
              </div>
            </div>
            <div className="min-w-0 space-y-4">
              <div className="min-w-0 rounded-[28px] border border-zinc-200/80 dark:border-zinc-800 bg-white/80 dark:bg-zinc-950/60 p-5 shadow-sm">
                <div className="flex items-center justify-between gap-4">
                  <h2 className="text-sm font-semibold uppercase tracking-wider text-zinc-500 dark:text-zinc-400">{t.crossCheckStats}</h2>
                  <div className="inline-flex items-center gap-2 rounded-full border border-zinc-200 dark:border-zinc-800 bg-zinc-50 dark:bg-zinc-900/60 px-3 py-1 text-xs text-zinc-500 dark:text-zinc-400">
                    <span className="h-2 w-2 rounded-full bg-emerald-400" />
                    {sourceStats ? `${sourceStats.engines} engines / ${sourceStats.domains} domains` : t.noSources}
                  </div>
                </div>
                <div className="mt-4">
                  <StatStack sources={result.sources} t={t} hasAi={Boolean(result.ai_analysis)} />
                </div>
              </div>

              {cleanClaims.length > 0 && (
                <div className="rounded-[28px] border border-zinc-200/80 dark:border-zinc-800 bg-white/80 dark:bg-zinc-950/60 p-5 shadow-sm">
                  <h2 className="text-sm font-semibold uppercase tracking-wider text-zinc-500 dark:text-zinc-400 mb-3">{t.keyClaims}</h2>
                  <ul className="space-y-2">
                    {cleanClaims.map((claim, i) => (
                      <li key={i} className="rounded-2xl border border-zinc-100 dark:border-zinc-800 bg-zinc-50/70 dark:bg-zinc-900/40 px-4 py-3 text-sm text-zinc-700 dark:text-zinc-300 flex items-start gap-3">
                        <span className="mt-0.5 inline-flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-zinc-900 text-[10px] font-bold text-white dark:bg-zinc-100 dark:text-zinc-900">{i + 1}</span>
                        <span className="leading-relaxed">{claim}</span>
                      </li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
          </div>

          <div className="grid gap-4 lg:grid-cols-[1fr_1fr]">
            <div className="min-w-0 rounded-[28px] border border-zinc-200/80 dark:border-zinc-800 bg-white/80 dark:bg-zinc-950/60 p-5 shadow-sm">
              <h2 className="text-sm font-semibold uppercase tracking-wider text-zinc-500 dark:text-zinc-400 mb-3">
                {t.sources} ({result.sources.length})
              </h2>
              {result.sources.length === 0 ? (
                <p className="text-sm text-zinc-400 dark:text-zinc-500">{t.notFound}</p>
              ) : (
                <div className="min-w-0 space-y-3">
                  {result.sources.map((s) => <SourceRow key={s.url} source={s} t={t} />)}
                </div>
              )}
            </div>

            <div className="min-w-0 rounded-[28px] border border-zinc-200/80 bg-white/85 p-5 shadow-sm backdrop-blur-sm dark:border-zinc-800 dark:bg-gradient-to-br dark:from-zinc-950 dark:to-zinc-900 dark:shadow-[0_20px_50px_-20px_rgba(0,0,0,0.8)]">
              <h2 className="text-sm font-semibold uppercase tracking-wider text-zinc-500 dark:text-zinc-400 mb-3">{t.analysis}</h2>
              <p className="text-sm text-zinc-700 dark:text-zinc-300 leading-relaxed whitespace-pre-wrap">{displaySummary}</p>
              {aiStatusCard && (
                <div className={`mt-4 rounded-2xl border px-4 py-3 ${aiStatusCard.tone}`}>
                  <div className="flex items-center justify-between gap-3">
                    <span className={`text-xs font-semibold uppercase tracking-wider ${aiStatusCard.labelClass}`}>
                      {aiStatusCard.title}
                    </span>
                    <span className="font-mono text-xs text-zinc-400">{aiStatusCard.confidence}</span>
                  </div>
                  <p className="mt-2 text-sm leading-relaxed text-zinc-600 dark:text-zinc-300">{aiStatusCard.body}</p>
                  <p className="mt-2 text-[11px] text-zinc-400">{aiStatusCard.hint}</p>
                </div>
              )}
              <div className="mt-4 grid gap-3 sm:grid-cols-2">
                <SummaryPill label={t.verdict} value={verdictText(result, t)} />
                <SummaryPill label={t.score} value={`${result.score}/100`} />
              </div>
            </div>
          </div>
        </div>
      )}
      </div>
    </div>
  );
}
