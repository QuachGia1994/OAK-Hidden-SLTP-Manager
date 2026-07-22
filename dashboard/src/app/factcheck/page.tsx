"use client";

import { useState, useRef, useCallback, useEffect } from "react";
import type { FactCheckResult } from "@/lib/types";
import { useLocale } from "@/components/LocaleProvider";
import type { PSM } from "tesseract.js";

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
const OCR_MAX_WIDTH = 3200;
const OCR_BOTTOM_CROP_RATIO = 0.58;
const OCR_CENTER_CROP_RATIO = 0.7;
const OCR_CHAR_WHITELIST = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyzÀÁÂÃÈÉÊÌÍÒÓÔÕÙÚÝĂĐĨŨƠƯàáâãèéêìíòóôõùúýăđĩũơưẠ-ỹ0123456789.,:%/()?!+-–—₫đĐ \\n";

function ScoreBar({ score }: { score: number }) {
  const clamped = Math.max(0, Math.min(100, score || 0));
  const fillStyle = clamped >= 80 ? "bg-[var(--terminal-accent)]" : clamped >= 50 ? "bg-[var(--terminal-warning)]" : "bg-[var(--terminal-danger)]";
  return (
    <div className="flex items-center gap-4">
      <div className="flex-1 h-2.5 bg-[var(--surface-raised)] border border-[var(--panel-border)] rounded-full overflow-hidden">
        <div className={`h-full ${fillStyle} rounded-full transition-all duration-500`} style={{ width: `${clamped}%` }} />
      </div>
      <span className="font-mono text-xl font-black tabular-nums text-[var(--foreground)] w-12 text-right">{clamped}</span>
    </div>
  );
}

function ScoreRing({ score, label }: { score: number; label: string }) {
  const clamped = Math.max(0, Math.min(100, score || 0));
  const radius = 47;
  const circumference = 2 * Math.PI * radius;
  const stroke = clamped >= 80 ? "var(--terminal-accent)" : clamped >= 50 ? "var(--terminal-warning)" : "var(--terminal-danger)";
  return (
    <div className="relative grid h-32 w-32 place-items-center sm:h-36 sm:w-36">
      <svg className="absolute inset-0 -rotate-90" viewBox="0 0 112 112" aria-hidden="true">
        <circle className="score-ring-track" cx="56" cy="56" r={radius} fill="none" strokeWidth="5" />
        <circle
          cx="56"
          cy="56"
          r={radius}
          fill="none"
          stroke={stroke}
          strokeWidth="5"
          strokeLinecap="round"
          style={{ strokeDasharray: circumference, strokeDashoffset: circumference * (1 - clamped / 100) }}
        />
      </svg>
      <div className="relative text-center">
        <div className="font-mono text-4xl font-black leading-none tabular-nums text-[var(--foreground)] sm:text-5xl">{clamped}</div>
        <div className="mt-1.5 font-mono text-[10px] uppercase tracking-[0.24em] text-[var(--muted)] sm:text-[11px]">{label}</div>
      </div>
    </div>
  );
}

function VerdictBadge({ verdict, labels }: { verdict: string; labels: Record<string, string> }) {
  return (
    <span className="verdict-tag" data-verdict={verdict}>
      <span className="h-1.5 w-1.5 rounded-full bg-current opacity-80" />
      {labels[verdict] || verdict}
    </span>
  );
}

function MetricCard({ label, value, detail }: { label: string; value: string; detail: string }) {
  return (
    <div className="terminal-stat rounded-xl p-4 border border-[var(--panel-border)] bg-[var(--surface-raised)]">
      <div className="text-[10px] font-mono uppercase tracking-[0.22em] text-[var(--muted)]">{label}</div>
      <div className="mt-2 text-lg sm:text-xl font-black font-mono text-[var(--foreground)]">{value}</div>
      <div className="mt-1 text-xs text-[var(--muted)] leading-relaxed">{detail}</div>
    </div>
  );
}

function SummaryPill({ label, value }: { label: string; value: string }) {
  return (
    <div className="fact-result-surface px-4 py-3 border border-[var(--panel-border)] bg-[var(--surface-raised)] rounded-xl">
      <div className="text-[10px] font-mono uppercase tracking-[0.22em] text-[var(--muted)]">{label}</div>
      <div className="mt-1.5 text-base font-bold font-mono text-[var(--foreground)]">{value}</div>
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
        ? "This older result contains a Vietnamese AI assessment. Run a fresh verification after the worker update to regenerate it in English."
        : hideStaleEnglish
          ? "AI đã phản biện trên bằng chứng đã thu thập. Hãy chạy lại xác thực để nhận bản phân tích tiếng Việt theo logic mới."
          : result.ai_analysis.summary,
      hint:
        locale === "EN"
          ? "AI challenges only the collected Google/DDG evidence and never invents sources."
          : "AI chỉ phản biện trên bằng chứng Google/DDG đã thu thập và không tự tạo nguồn.",
      tone: "border-[var(--terminal-accent)]/30 bg-[var(--surface-raised)]",
      labelClass: "text-[var(--terminal-accent)]",
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
    tone: isError ? "border-[var(--terminal-danger)]/30 bg-[var(--surface-raised)]" : isDisabled ? "border-[var(--terminal-warning)]/30 bg-[var(--surface-raised)]" : "border-[var(--panel-border)] bg-[var(--surface-raised)]",
    labelClass: isError ? "text-[var(--terminal-danger)]" : isDisabled ? "text-[var(--terminal-warning)]" : "text-[var(--muted)]",
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
  const iconColor = source.agrees === true ? "text-[var(--terminal-accent)]" : source.agrees === false ? "text-[var(--terminal-danger)]" : "text-[var(--muted)]";
  const isIFCN = !!source.publisher;
  const relStyle: Record<string, string> = {
    high: "text-[var(--terminal-accent)] border-[var(--terminal-accent)]/30 bg-[var(--terminal-accent)]/10",
    medium: "text-[var(--terminal-warning)] border-[var(--terminal-warning)]/30 bg-[var(--terminal-warning)]/10",
    low: "text-[var(--muted)] border-[var(--panel-border)] bg-[var(--surface)]",
  };
  return (
    <div className="fact-source-row w-full min-w-0 overflow-hidden border border-[var(--panel-border)] bg-[var(--surface-raised)] rounded-xl">
      <div className="h-0.5 bg-[var(--panel-border)]" />
      <div className="flex items-start gap-3.5 p-4 sm:p-5">
        <span className={`mt-0.5 font-mono text-base font-black ${iconColor}`}>{icon}</span>
        <div className="flex-1 min-w-0">
          <a href={safeSourceUrl(source.url)} target="_blank" rel="noopener noreferrer" className="text-sm sm:text-[15px] font-bold text-[var(--foreground)] hover:text-[var(--terminal-accent)] transition-colors truncate block">
            {source.title}
          </a>
          <div className="mt-2 flex items-center gap-2 flex-wrap min-w-0">
            {source.engine && (
              <span className="text-[10px] font-mono font-bold uppercase tracking-wider px-2 py-0.5 rounded-md bg-[var(--surface)] text-[var(--muted)] border border-[var(--panel-border)]">
                {source.engine === "google_factcheck"
                  ? t.googleFactCheck
                  : source.engine.replaceAll("_", " ").replace(/\b\w/g, (char) => char.toUpperCase())}
              </span>
            )}
            {isIFCN && (
              <span className="text-[10px] font-mono font-bold uppercase tracking-wider px-2 py-0.5 rounded-md bg-[var(--terminal-accent)]/10 text-[var(--terminal-accent)] border border-[var(--terminal-accent)]/30">
                {t.ifcnCertified}
              </span>
            )}
            {source.rating && (
              <span className={`text-[10px] font-mono font-bold px-2 py-0.5 rounded-md border ${source.agrees === true ? "text-[var(--terminal-accent)] border-[var(--terminal-accent)]/30 bg-[var(--terminal-accent)]/10" : source.agrees === false ? "text-[var(--terminal-danger)] border-[var(--terminal-danger)]/30 bg-[var(--terminal-danger)]/10" : "text-[var(--muted)] border-[var(--panel-border)] bg-[var(--surface)]"}`}>
                {source.rating}
              </span>
            )}
            <span className={`text-[10px] font-mono font-bold uppercase tracking-wider px-2 py-0.5 rounded-md border ${relStyle[source.reliability] || "text-[var(--muted)] border-[var(--panel-border)]"}`}>
              {t.reliabilityLabels[source.reliability as keyof typeof t.reliabilityLabels] || source.reliability}
            </span>
          </div>
          <p className="mt-2.5 line-clamp-2 text-xs sm:text-sm leading-relaxed text-[var(--muted)]">{source.snippet}</p>
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

async function renderOcrVariantFromImage(img: HTMLImageElement, options: { cropBottom?: boolean; cropCenter?: boolean; threshold?: boolean; invert?: boolean }): Promise<Blob> {
  let sourceY = 0;
  let sourceH = img.naturalHeight;
  if (options.cropBottom) {
    sourceY = Math.floor(img.naturalHeight * (1 - OCR_BOTTOM_CROP_RATIO));
    sourceH = Math.max(1, Math.floor(img.naturalHeight * OCR_BOTTOM_CROP_RATIO));
  } else if (options.cropCenter) {
    sourceH = Math.max(1, Math.floor(img.naturalHeight * OCR_CENTER_CROP_RATIO));
    sourceY = Math.floor((img.naturalHeight - sourceH) / 2);
  }
  const desiredScale = Math.min(3.2, Math.max(1.35, OCR_MAX_WIDTH / Math.max(img.naturalWidth, 1)));
  const safeScale = Math.sqrt(20_000_000 / Math.max(img.naturalWidth * sourceH, 1));
  const scale = Math.min(desiredScale, Math.max(0.5, safeScale));
  const canvas = document.createElement("canvas");
  canvas.width = Math.round(img.naturalWidth * scale);
  canvas.height = Math.round(sourceH * scale);
  const ctx = canvas.getContext("2d");
  if (!ctx) throw new Error("Canvas unavailable");
  ctx.imageSmoothingEnabled = true;
  ctx.imageSmoothingQuality = "high";
  ctx.filter = options.threshold ? "grayscale(1) contrast(2.35) brightness(1.1)" : "grayscale(1) contrast(1.9) brightness(1.12)";
  ctx.drawImage(img, 0, sourceY, img.naturalWidth, sourceH, 0, 0, canvas.width, canvas.height);
  if (options.threshold || options.invert) {
    const imageData = ctx.getImageData(0, 0, canvas.width, canvas.height);
    const pixels = imageData.data;
    const threshold = otsuThreshold(imageData);
    for (let i = 0; i < pixels.length; i += 4) {
      const luminance = (pixels[i] * 0.299 + pixels[i + 1] * 0.587 + pixels[i + 2] * 0.114);
      let value = options.threshold ? (luminance > threshold ? 255 : 0) : luminance;
      if (options.invert) value = 255 - value;
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
    { label: "inverted", blob: await renderOcrVariantFromImage(image, { invert: true }) },
    { label: "center", blob: await renderOcrVariantFromImage(image, { cropCenter: true }) },
    { label: "center-threshold", blob: await renderOcrVariantFromImage(image, { cropCenter: true, threshold: true }) },
    { label: "bottom", blob: await renderOcrVariantFromImage(image, { cropBottom: true }) },
    { label: "bottom-threshold", blob: await renderOcrVariantFromImage(image, { cropBottom: true, threshold: true }) },
  ];
}

async function recognizeBestOcrText(file: File): Promise<string> {
  if (!file.type.startsWith("image/") || file.size > 12 * 1024 * 1024) throw new Error("Unsupported image");
  const Tesseract = await import("tesseract.js");
  const variants = await buildOcrVariants(file, await loadImage(file));
  const worker = await Tesseract.createWorker(OCR_LANGS, 1, {
    legacyCore: false,
    legacyLang: false,
  });
  let bestText = "";
  let bestScore = -1;
  try {
    for (const variant of variants) {
      for (const psm of ["6", "11", "12"] as PSM[]) {
        await worker.setParameters({
          tessedit_pageseg_mode: psm,
          tessedit_char_whitelist: OCR_CHAR_WHITELIST,
          preserve_interword_spaces: "1",
        });
        const { data } = await worker.recognize(variant.blob);
        const cleaned = cleanOcrText(data.text || "");
        const confidence = typeof data.confidence === "number" ? data.confidence : 0;
        const score = scoreOcrText(cleaned, confidence);
        if (cleaned && score > bestScore) [bestScore, bestText] = [score, cleaned];
      }
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
        body: JSON.stringify({
          text: text.trim(),
          locale,
          output_language: locale === "EN" ? "English" : "Vietnamese",
        }),
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
  }, [locale, text]);

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
    <div className="factcheck-screen">
      <div className="relative page-shell">
        <div className="mb-6 grid gap-4 lg:grid-cols-[1.15fr_0.85fr]">
          <div className="fact-hero rounded-2xl p-6 sm:p-8">
            <div className="fact-kicker">{t.studio}</div>
            <div className="mt-3 flex items-end justify-between gap-4">
              <div>
                <h1 className="text-3xl sm:text-5xl font-black tracking-tight text-[var(--foreground)]">{t.title}</h1>
                <p className="mt-3 max-w-2xl text-sm sm:text-base text-[var(--muted)] leading-relaxed">{t.subtitle}</p>
              </div>
              <div className="hidden xl:block text-right">
                <div className="text-[10px] font-mono uppercase tracking-[0.24em] text-[var(--muted)]">{t.realtime}</div>
                <div className="mt-2 inline-flex items-center gap-2 rounded-full border border-[var(--terminal-accent)]/30 bg-[var(--terminal-accent)]/10 px-3.5 py-1.5 text-xs font-mono font-bold text-[var(--terminal-accent)]">
                  <span className="h-2 w-2 rounded-full bg-[var(--terminal-accent)] shadow-[0_0_12px_var(--terminal-accent)]" />
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

          <aside className="fact-panel rounded-2xl p-6 sm:p-7 flex flex-col justify-between">
            <div className="fact-kicker">
              {locale === "EN" ? "How it reads" : "Cách hệ thống đọc tin"}
            </div>
            <div className="mt-4 space-y-3">
              <div className="fact-steps-item p-4" data-step="1">
                <div className="flex items-center justify-between gap-2">
                  <div className="text-sm font-bold text-[var(--foreground)]">{t.parse}</div>
                  <span className="font-mono text-xs font-bold text-[var(--terminal-accent)]">01</span>
                </div>
                <p className="mt-1 text-xs sm:text-sm text-[var(--muted)] leading-relaxed">{t.parseDesc}</p>
              </div>
              <div className="fact-steps-item p-4" data-step="2">
                <div className="flex items-center justify-between gap-2">
                  <div className="text-sm font-bold text-[var(--foreground)]">{t.crossCheck}</div>
                  <span className="font-mono text-xs font-bold text-[var(--terminal-warning)]">02</span>
                </div>
                <p className="mt-1 text-xs sm:text-sm text-[var(--muted)] leading-relaxed">{t.crossCheckDesc}</p>
              </div>
              <div className="fact-steps-item p-4" data-step="3">
                <div className="flex items-center justify-between gap-2">
                  <div className="text-sm font-bold text-[var(--foreground)]">{t.scoreMix}</div>
                  <span className="font-mono text-xs font-bold text-[var(--muted)]">03</span>
                </div>
                <p className="mt-1 text-xs sm:text-sm text-[var(--muted)] leading-relaxed">{t.scoreMixDesc}</p>
              </div>
            </div>
          </aside>
        </div>

        <div className="grid gap-4 lg:grid-cols-[1.02fr_0.98fr]">
          <div className="fact-panel fact-input rounded-2xl p-5 sm:p-6">
            <div className="flex items-center justify-between gap-3">
              <div>
                <div className="text-[10px] font-mono uppercase tracking-[0.24em] text-[var(--muted)]">{t.input}</div>
                <h2 className="mt-1 text-lg font-bold text-[var(--foreground)]">{t.textOrImage}</h2>
              </div>
              <div className="hidden sm:flex items-center gap-2 text-xs font-mono text-[var(--muted)]">
                <span className="h-2 w-2 rounded-full bg-[var(--terminal-accent)]" />
                Multi-pass OCR
              </div>
            </div>

            <textarea
              className="mt-4 w-full h-36 sm:h-44 rounded-xl border border-[var(--panel-border)] bg-[var(--surface-raised)] px-4 py-4 text-sm sm:text-[15px] leading-relaxed text-[var(--foreground)] placeholder:text-[var(--muted)]/60 focus:outline-none focus:ring-2 focus:ring-[var(--terminal-accent)]/40 resize-none"
              placeholder={t.placeholder}
              value={text}
              onChange={(e) => setText(e.target.value)}
              onPaste={handlePaste}
            />
            <p className="mt-2 text-xs text-[var(--muted)]">
              {locale === "EN" ? "Paste an image directly with Ctrl+V" : "Dán ảnh trực tiếp bằng Ctrl+V"}
            </p>

            <div
              className={`fact-upload mt-4 border border-dashed px-4 py-4 text-center ${dragOver ? "drag-active" : ""}`}
              onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
              onDragLeave={() => setDragOver(false)}
              onDrop={handleDrop}
            >
              <input ref={fileRef} type="file" accept="image/*" className="hidden" onChange={(e) => { const file = e.target.files?.[0]; if (file) void handleImageUpload(file); e.target.value = ""; }} />
              <button type="button" onClick={() => fileRef.current?.click()} className="inline-flex items-center gap-2 text-sm font-semibold text-[var(--foreground)] hover:text-[var(--terminal-accent)] transition-colors">
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
              <p className="mt-1.5 text-xs text-[var(--muted)]">{t.dragDrop}</p>
            </div>

            <div className="mt-5 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
              <div className="flex flex-wrap gap-2 text-[10px] font-mono uppercase tracking-[0.2em] text-[var(--muted)]">
                <span className="rounded-md border border-[var(--panel-border)] bg-[var(--surface)] px-2.5 py-1">multi source</span>
                <span className="rounded-md border border-[var(--panel-border)] bg-[var(--surface)] px-2.5 py-1">ifcn aware</span>
                <span className="rounded-md border border-[var(--panel-border)] bg-[var(--surface)] px-2.5 py-1">mix score</span>
              </div>
              <button
                onClick={handleSubmit}
                disabled={loading || !text.trim()}
                className="fact-action inline-flex w-full items-center justify-center px-7 py-3 text-sm font-black transition-all sm:w-auto"
              >
                {loading ? t.submitting : t.submit}
              </button>
            </div>
          </div>

          <div className="fact-panel fact-preview rounded-2xl p-5 sm:p-6">
            <div className="fact-kicker">
              {locale === "EN" ? "Live preview" : "Xem trước trực tiếp"}
            </div>
            <div className="mt-4 grid gap-3">
              <div className="fact-result-surface p-4 border border-[var(--panel-border)] bg-[var(--surface-raised)] rounded-xl">
                <div className="flex items-start justify-between gap-4">
                  <div>
                    <div className="text-sm font-bold text-[var(--foreground)]">{t.scoreLogic}</div>
                    <p className="mt-1 text-sm leading-relaxed text-[var(--muted)]">{t.summary}</p>
                  </div>
                  <div className="hidden sm:block rounded-md border border-[var(--panel-border)] bg-[var(--surface)] px-3 py-1.5 text-xs font-mono font-bold text-[var(--muted)]">
                    0–100
                  </div>
                </div>
              </div>
              <div className="fact-result-surface p-4 border border-[var(--panel-border)] bg-[var(--surface-raised)] rounded-xl">
                <div className="text-sm font-bold text-[var(--foreground)]">{t.previewTitle}</div>
                <p className="mt-1 text-sm leading-relaxed text-[var(--muted)]">{t.previewDesc}</p>
              </div>
              <div className="fact-result-surface p-4 border border-[var(--panel-border)] bg-[var(--surface-raised)] rounded-xl">
                <div className="text-sm font-bold text-[var(--foreground)]">{t.useCase}</div>
                <p className="mt-1 text-sm leading-relaxed text-[var(--muted)]">{t.useCaseDesc}</p>
              </div>
            </div>
          </div>
        </div>

      {error && (
        <div className="fact-panel mt-5 rounded-xl border border-[var(--terminal-danger)]/30 bg-[var(--surface-raised)] px-5 py-4">
          <p className="text-sm font-semibold text-[var(--terminal-danger)]">{error}</p>
        </div>
      )}

      {result && (
        <div className="mt-6 space-y-4">
          <div className="grid gap-4 lg:grid-cols-[0.82fr_1.18fr]">
            <div className="fact-panel min-w-0 rounded-2xl p-6">
              <div className="flex items-start justify-between gap-4">
                <div>
                  <div className="text-[10px] font-mono uppercase tracking-[0.24em] text-[var(--muted)]">{t.result}</div>
                  <h2 className="mt-1 text-xl font-bold text-[var(--foreground)]">{t.resultTitle}</h2>
                </div>
                <VerdictBadge verdict={result.verdict} labels={t.verdictLabels} />
              </div>
              <div className="mt-6 flex flex-col sm:flex-row items-center gap-6">
                <ScoreRing score={result.score} label={t.score} />
                <div className="flex-1 space-y-3 w-full">
                  <ScoreBar score={result.score} />
                  <div className="fact-result-surface px-4 py-3.5 border border-[var(--panel-border)] bg-[var(--surface-raised)] rounded-xl">
                    <div className="text-[10px] font-mono uppercase tracking-[0.24em] text-[var(--muted)]">{t.summaryTitle}</div>
                    <p className="mt-2 text-sm leading-relaxed text-[var(--foreground)]">{displaySummary}</p>
                  </div>
                </div>
              </div>
            </div>
            <div className="min-w-0 space-y-4">
              <div className="fact-panel min-w-0 rounded-2xl p-6">
                <div className="flex items-center justify-between gap-4">
                  <h2 className="text-xs font-mono font-bold uppercase tracking-wider text-[var(--muted)]">{t.crossCheckStats}</h2>
                  <div className="inline-flex items-center gap-2 rounded-md border border-[var(--panel-border)] bg-[var(--surface-raised)] px-3 py-1 text-xs font-mono text-[var(--muted)]">
                    <span className="h-2 w-2 rounded-full bg-[var(--terminal-accent)]" />
                    {sourceStats ? `${sourceStats.engines} engines / ${sourceStats.domains} domains` : t.noSources}
                  </div>
                </div>
                <div className="mt-4">
                  <StatStack sources={result.sources} t={t} hasAi={Boolean(result.ai_analysis)} />
                </div>
              </div>

              {cleanClaims.length > 0 && (
                <div className="fact-panel rounded-2xl p-6">
                  <h2 className="text-xs font-mono font-bold uppercase tracking-wider text-[var(--muted)] mb-3">{t.keyClaims}</h2>
                  <ul className="space-y-2">
                    {cleanClaims.map((claim, i) => (
                      <li key={i} className="fact-result-surface flex items-start gap-3 px-4 py-3 text-sm text-[var(--foreground)] border border-[var(--panel-border)] bg-[var(--surface-raised)] rounded-xl">
                        <span className="mt-0.5 inline-flex h-5 w-5 shrink-0 items-center justify-center rounded-md bg-[var(--surface)] border border-[var(--panel-border)] font-mono text-[10px] font-bold text-[var(--terminal-accent)]">{i + 1}</span>
                        <span className="leading-relaxed">{claim}</span>
                      </li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
          </div>

          <div className="grid gap-4 lg:grid-cols-[1fr_1fr]">
            <div className="fact-panel min-w-0 rounded-2xl p-6">
              <h2 className="text-xs font-mono font-bold uppercase tracking-wider text-[var(--muted)] mb-4">
                {t.sources} ({result.sources.length})
              </h2>
              {result.sources.length === 0 ? (
                <p className="text-sm text-[var(--muted)]">{t.notFound}</p>
              ) : (
                <div className="min-w-0 space-y-3">
                  {result.sources.map((s) => <SourceRow key={s.url} source={s} t={t} />)}
                </div>
              )}
            </div>

            <div className="fact-panel min-w-0 rounded-2xl p-6">
              <h2 className="text-xs font-mono font-bold uppercase tracking-wider text-[var(--muted)] mb-4">{t.analysis}</h2>
              <p className="text-sm text-[var(--foreground)] leading-relaxed whitespace-pre-wrap">{displaySummary}</p>
              {aiStatusCard && (
                <div className={`fact-result-surface mt-4 border px-4 py-3.5 rounded-xl ${aiStatusCard.tone}`}>
                  <div className="flex items-center justify-between gap-3">
                    <span className={`text-xs font-mono font-bold uppercase tracking-wider ${aiStatusCard.labelClass}`}>
                      {aiStatusCard.title}
                    </span>
                    <span className="font-mono text-xs text-[var(--muted)]">{aiStatusCard.confidence}</span>
                  </div>
                  <p className="mt-2 text-sm leading-relaxed text-[var(--foreground)]">{aiStatusCard.body}</p>
                  <p className="mt-2 text-[11px] text-[var(--muted)]">{aiStatusCard.hint}</p>
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
