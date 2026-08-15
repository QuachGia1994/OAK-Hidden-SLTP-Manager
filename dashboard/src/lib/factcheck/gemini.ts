import type { FactCheckClaim, FactCheckResult, FactCheckSource, FactCheckVerdict } from "@/lib/factcheck/types";

const VERDICTS = new Set<FactCheckVerdict>(["supported", "contradicted", "mixed", "insufficient"]);

export const FACTCHECK_MODEL = process.env.FACTCHECK_MODEL || "gemini-2.5-flash-lite";
const GEMINI_ENDPOINT = `https://generativelanguage.googleapis.com/v1beta/models/${encodeURIComponent(FACTCHECK_MODEL)}:generateContent`;

const RESPONSE_SCHEMA = {
  type: "OBJECT",
  properties: {
    verdict: { type: "STRING", enum: ["supported", "contradicted", "mixed", "insufficient"] },
    confidence: { type: "INTEGER", minimum: 0, maximum: 100 },
    summary: { type: "STRING" },
    claims: {
      type: "ARRAY",
      items: {
        type: "OBJECT",
        properties: {
          claim: { type: "STRING" },
          verdict: { type: "STRING", enum: ["supported", "contradicted", "mixed", "insufficient"] },
          confidence: { type: "INTEGER", minimum: 0, maximum: 100 },
          explanation: { type: "STRING" },
        },
        required: ["claim", "verdict", "confidence", "explanation"],
      },
    },
  },
  required: ["verdict", "confidence", "summary", "claims"],
};

function systemPrompt(outputLanguage: "Vietnamese" | "English") {
  return [
    "You are OAK Gatekeeper, a strict evidence-first fact checker.",
    "Use Google Search grounding for claims that can be checked on the public web.",
    "Prefer primary sources, official documents, Reuters, AP, BBC, major financial wires, peer-reviewed or institutional sources.",
    "Separate factual claims from opinion, prediction, satire, and unverifiable assertions.",
    "Never invent sources, URLs, dates, quotes, or evidence.",
    "If evidence is weak, conflicting, stale, or absent, verdict must be insufficient or mixed rather than guessed.",
    "Confidence is confidence in the evidence-backed verdict, not a probability that the user is truthful.",
    `Write summary and explanations in ${outputLanguage}.`,
  ].join(" ");
}

function requestBody(text: string, outputLanguage: "Vietnamese" | "English") {
  return {
    systemInstruction: { parts: [{ text: systemPrompt(outputLanguage) }] },
    contents: [{ role: "user", parts: [{ text }] }],
    tools: [{ googleSearch: {} }],
    generationConfig: {
      temperature: 0.1,
      maxOutputTokens: 2400,
      responseMimeType: "application/json",
      responseSchema: RESPONSE_SCHEMA,
    },
  };
}

function clampConfidence(value: unknown): number {
  const number = typeof value === "number" ? value : Number(value);
  if (!Number.isFinite(number)) return 0;
  return Math.max(0, Math.min(100, Math.round(number)));
}

function cleanVerdict(value: unknown): FactCheckVerdict {
  return typeof value === "string" && VERDICTS.has(value as FactCheckVerdict)
    ? value as FactCheckVerdict
    : "insufficient";
}

function cleanClaims(value: unknown): FactCheckClaim[] {
  if (!Array.isArray(value)) return [];
  return value.slice(0, 8).map((item) => {
    const raw = item && typeof item === "object" ? item as Record<string, unknown> : {};
    return {
      claim: String(raw.claim || "").slice(0, 500),
      verdict: cleanVerdict(raw.verdict),
      confidence: clampConfidence(raw.confidence),
      explanation: String(raw.explanation || "").slice(0, 1600),
    };
  }).filter((item) => item.claim.length > 0);
}

function extractText(payload: GeminiResponse): string {
  return (payload.candidates?.[0]?.content?.parts || [])
    .map((part) => part.text || "")
    .join("")
    .trim();
}

function extractSources(payload: GeminiResponse): FactCheckSource[] {
  const chunks = payload.candidates?.[0]?.groundingMetadata?.groundingChunks || [];
  const seen = new Set<string>();
  return chunks.flatMap((chunk) => {
    const web = chunk.web;
    if (!web?.uri || seen.has(web.uri)) return [];
    seen.add(web.uri);
    return [{ title: web.title || "Web source", url: web.uri }];
  }).slice(0, 12);
}

function extractQueries(payload: GeminiResponse): string[] {
  const queries = payload.candidates?.[0]?.groundingMetadata?.webSearchQueries || [];
  return [...new Set(queries.filter((query) => typeof query === "string" && query.trim()))].slice(0, 12);
}

function parseAssessment(payload: GeminiResponse): Omit<FactCheckResult, "sources" | "search_queries" | "model" | "provider" | "grounded"> {
  const text = extractText(payload);
  if (!text) throw new Error("Gemini returned no assessment text");
  const raw = JSON.parse(text) as Record<string, unknown>;
  return {
    verdict: cleanVerdict(raw.verdict),
    confidence: clampConfidence(raw.confidence),
    summary: String(raw.summary || "").slice(0, 3000),
    claims: cleanClaims(raw.claims),
  };
}

export async function runGeminiFactCheck(
  text: string,
  outputLanguage: "Vietnamese" | "English",
  apiKey: string,
): Promise<FactCheckResult> {
  const response = await fetch(GEMINI_ENDPOINT, {
    method: "POST",
    headers: { "Content-Type": "application/json", "x-goog-api-key": apiKey },
    body: JSON.stringify(requestBody(text, outputLanguage)),
    signal: AbortSignal.timeout(45000),
  });
  const payload = await response.json() as GeminiResponse;
  if (!response.ok) throw new GeminiHttpError(response.status, payload.error?.message || `Gemini HTTP ${response.status}`);

  const assessment = parseAssessment(payload);
  const sources = extractSources(payload);
  const grounded = sources.length > 0;
  return {
    ...assessment,
    verdict: grounded ? assessment.verdict : "insufficient",
    confidence: grounded ? assessment.confidence : Math.min(assessment.confidence, 40),
    sources,
    search_queries: extractQueries(payload),
    model: FACTCHECK_MODEL,
    provider: "gemini",
    grounded,
  };
}

export class GeminiHttpError extends Error {
  constructor(public status: number, message: string) {
    super(message);
    this.name = "GeminiHttpError";
  }
}

interface GeminiResponse {
  candidates?: Array<{
    content?: { parts?: Array<{ text?: string }> };
    groundingMetadata?: {
      webSearchQueries?: string[];
      groundingChunks?: Array<{ web?: { uri?: string; title?: string } }>;
    };
  }>;
  error?: { message?: string };
}
