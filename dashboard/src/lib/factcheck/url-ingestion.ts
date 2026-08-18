import "server-only";

import { lookup } from "node:dns/promises";
import type { IncomingHttpHeaders, IncomingMessage } from "node:http";
import { request as httpRequest } from "node:http";
import { request as httpsRequest } from "node:https";
import type { Readable } from "node:stream";
import { createBrotliDecompress, createGunzip, createInflate } from "node:zlib";
import { extractArticle } from "./article-extract";
import { areResolvedAddressesPublic, isBlockedHostname, isBlockedIpLiteral, validatePublicHttpUrl, validatePublicRedirect } from "./ssrf";

export type UrlIngestErrorCode =
  | "INVALID_URL"
  | "UNSUPPORTED_URL_SCHEME"
  | "URL_BLOCKED"
  | "URL_FETCH_TIMEOUT"
  | "URL_REDIRECT_BLOCKED"
  | "URL_UNSUPPORTED_CONTENT"
  | "URL_TOO_LARGE"
  | "URL_FETCH_FAILED"
  | "URL_NO_READABLE_CONTENT";

export class UrlIngestError extends Error {
  constructor(public code: UrlIngestErrorCode, message?: string) {
    super(message || code);
    this.name = "UrlIngestError";
  }
}

export interface FactCheckUrlDocument {
  url: string;
  finalUrl: string;
  title: string;
  description?: string;
  publisher?: string;
  publishedAt?: string;
  text: string;
}

type ResolvedAddress = { address: string; family: number };
type HopResponse = { status: number; headers: IncomingHttpHeaders; response: IncomingMessage };

const USER_AGENT = "OAKGatekeeper/1.0 (+https://www.oakgatekeeper.uk; factcheck-url-ingest)";
const MAX_REDIRECTS = 4;
const MAX_BODY_BYTES = 1_500_000;
const FETCH_TIMEOUT_MS = 12_000;

async function resolvePublicAddresses(hostname: string): Promise<ResolvedAddress[]> {
  if (isBlockedHostname(hostname) || isBlockedIpLiteral(hostname)) {
    throw new UrlIngestError("URL_BLOCKED");
  }
  try {
    const records = await lookup(hostname, { all: true, verbatim: true });
    if (!areResolvedAddressesPublic(records)) throw new UrlIngestError("URL_BLOCKED");
    return records;
  } catch (error) {
    if (error instanceof UrlIngestError) throw error;
    throw new UrlIngestError("URL_FETCH_FAILED");
  }
}

function assertSafeUrl(raw: string): URL {
  const result = validatePublicHttpUrl(raw);
  if (!result.ok) throw new UrlIngestError(result.code);
  return result.url;
}

function headerValue(headers: IncomingHttpHeaders, name: string): string | null {
  const value = headers[name.toLowerCase()];
  if (Array.isArray(value)) return value[0] || null;
  return typeof value === "string" ? value : null;
}

function isAllowedContentType(contentType: string | null): boolean {
  if (!contentType) return true;
  const lower = contentType.toLowerCase();
  return lower.includes("text/html")
    || lower.includes("application/xhtml")
    || lower.includes("text/plain");
}

function decodedBodyStream(response: IncomingMessage): Readable {
  const encoding = (headerValue(response.headers, "content-encoding") || "identity").trim().toLowerCase();
  if (!encoding || encoding === "identity") return response;
  if (encoding === "gzip" || encoding === "x-gzip") return response.pipe(createGunzip());
  if (encoding === "deflate") return response.pipe(createInflate());
  if (encoding === "br") return response.pipe(createBrotliDecompress());
  throw new UrlIngestError("URL_UNSUPPORTED_CONTENT");
}

async function readBodyLimited(response: IncomingMessage, maxBytes: number): Promise<string> {
  const length = Number(headerValue(response.headers, "content-length") || 0);
  if (Number.isFinite(length) && length > maxBytes) throw new UrlIngestError("URL_TOO_LARGE");

  const stream = decodedBodyStream(response);
  const chunks: Buffer[] = [];
  let total = 0;
  try {
    for await (const chunk of stream) {
      const buffer = Buffer.isBuffer(chunk) ? chunk : Buffer.from(chunk);
      total += buffer.byteLength;
      if (total > maxBytes) {
        stream.destroy();
        throw new UrlIngestError("URL_TOO_LARGE");
      }
      chunks.push(buffer);
    }
  } catch (error) {
    if (error instanceof UrlIngestError) throw error;
    if (error instanceof Error && (error.name === "AbortError" || (error as NodeJS.ErrnoException).code === "ABORT_ERR")) {
      throw new UrlIngestError("URL_FETCH_TIMEOUT");
    }
    throw new UrlIngestError("URL_FETCH_FAILED");
  }
  return Buffer.concat(chunks, total).toString("utf8");
}

/**
 * One network hop with DNS pinning: validate DNS records, then force the socket
 * lookup to one already-approved address. This closes the validate-then-fetch
 * DNS rebinding window while preserving Host/SNI for the original hostname.
 */
async function requestHop(url: URL, signal: AbortSignal): Promise<HopResponse> {
  const addresses = await resolvePublicAddresses(url.hostname);
  const selected = addresses[0];
  const requestImpl = url.protocol === "https:" ? httpsRequest : httpRequest;

  return new Promise<HopResponse>((resolve, reject) => {
    const request = requestImpl(url, {
      method: "GET",
      signal,
      headers: {
        "User-Agent": USER_AGENT,
        Accept: "text/html,application/xhtml+xml;q=0.9,text/plain;q=0.8,*/*;q=0.1",
        "Accept-Language": "en-US,en;q=0.8,vi;q=0.5",
        "Accept-Encoding": "gzip, deflate, br",
      },
      lookup: ((_hostname: string, _options: unknown, callback: (error: NodeJS.ErrnoException | null, address: string, family: number) => void) => {
        callback(null, selected.address, selected.family);
      }) as never,
    }, (response) => {
      resolve({ status: response.statusCode || 0, headers: response.headers, response });
    });

    request.once("error", (error) => {
      if (error instanceof Error && (error.name === "AbortError" || (error as NodeJS.ErrnoException).code === "ABORT_ERR")) {
        reject(new UrlIngestError("URL_FETCH_TIMEOUT"));
        return;
      }
      reject(new UrlIngestError("URL_FETCH_FAILED"));
    });
    request.end();
  });
}

/** Safe URL → article document. Subject page is never independent evidence. */
export async function ingestUrlForFactCheck(rawUrl: string): Promise<FactCheckUrlDocument> {
  let current = assertSafeUrl(rawUrl);
  current.hash = "";

  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), FETCH_TIMEOUT_MS);

  try {
    let finalResponse: IncomingMessage | null = null;
    let finalHeaders: IncomingHttpHeaders | null = null;

    for (let hop = 0; hop <= MAX_REDIRECTS; hop += 1) {
      let response: HopResponse;
      try {
        response = await requestHop(current, controller.signal);
      } catch (error) {
        if (error instanceof UrlIngestError) throw error;
        throw new UrlIngestError("URL_FETCH_FAILED");
      }

      if ([301, 302, 303, 307, 308].includes(response.status)) {
        const location = headerValue(response.headers, "location");
        response.response.destroy();
        if (!location || hop === MAX_REDIRECTS) throw new UrlIngestError("URL_REDIRECT_BLOCKED");
        const redirect = validatePublicRedirect(current, location);
        if (!redirect.ok) throw new UrlIngestError("URL_REDIRECT_BLOCKED");
        current = redirect.url;
        continue;
      }

      if (response.status >= 400 || response.status < 200) {
        response.response.destroy();
        throw new UrlIngestError("URL_FETCH_FAILED");
      }

      finalResponse = response.response;
      finalHeaders = response.headers;
      break;
    }

    if (!finalResponse || !finalHeaders) throw new UrlIngestError("URL_FETCH_FAILED");
    if (!isAllowedContentType(headerValue(finalHeaders, "content-type"))) {
      finalResponse.destroy();
      throw new UrlIngestError("URL_UNSUPPORTED_CONTENT");
    }

    const body = await readBodyLimited(finalResponse, MAX_BODY_BYTES);
    const article = extractArticle(body, current.toString());
    if (!article) throw new UrlIngestError("URL_NO_READABLE_CONTENT");

    return {
      url: rawUrl.trim(),
      finalUrl: current.toString(),
      title: article.title,
      description: article.description,
      publisher: article.publisher,
      publishedAt: article.publishedAt,
      text: article.text,
    };
  } finally {
    clearTimeout(timer);
  }
}
