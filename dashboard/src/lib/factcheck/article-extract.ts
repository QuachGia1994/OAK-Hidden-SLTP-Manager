/** HTML → readable article text. No external deps. */

export interface ExtractedArticle {
  title: string;
  description?: string;
  publisher?: string;
  publishedAt?: string;
  text: string;
  canonicalUrl?: string;
}

function decodeEntities(value: string): string {
  return value
    .replace(/&nbsp;/gi, " ")
    .replace(/&amp;/gi, "&")
    .replace(/&lt;/gi, "<")
    .replace(/&gt;/gi, ">")
    .replace(/&quot;/gi, '"')
    .replace(/&#39;|&apos;/gi, "'")
    .replace(/&#(\d+);/g, (_, n) => String.fromCharCode(Number(n)))
    .replace(/&#x([0-9a-f]+);/gi, (_, h) => String.fromCharCode(parseInt(h, 16)));
}

function stripTags(html: string): string {
  return decodeEntities(
    html
      .replace(/<script[\s\S]*?<\/script>/gi, " ")
      .replace(/<style[\s\S]*?<\/style>/gi, " ")
      .replace(/<noscript[\s\S]*?<\/noscript>/gi, " ")
      .replace(/<!--[\s\S]*?-->/g, " ")
      .replace(/<(nav|footer|aside|header|form|iframe|svg)[\s\S]*?<\/\1>/gi, " ")
      .replace(/<[^>]+>/g, " "),
  )
    .replace(/\s+/g, " ")
    .trim();
}

function metaContent(html: string, names: string[]): string {
  for (const name of names) {
    const re = new RegExp(
      `<meta[^>]*(?:name|property)=["']${name}["'][^>]*content=["']([^"']+)["'][^>]*>|<meta[^>]*content=["']([^"']+)["'][^>]*(?:name|property)=["']${name}["'][^>]*>`,
      "i",
    );
    const m = html.match(re);
    if (m) return decodeEntities((m[1] || m[2] || "").trim());
  }
  return "";
}

function tagInner(html: string, tag: string): string {
  const re = new RegExp(`<${tag}(?:\\s[^>]*)?>([\\s\\S]*?)<\\/${tag}>`, "i");
  const m = html.match(re);
  return m ? m[1] : "";
}

function firstMatchInner(html: string, patterns: RegExp[]): string {
  for (const re of patterns) {
    const m = html.match(re);
    if (m?.[1]) return m[1];
  }
  return "";
}

const MAX_TEXT = 40_000;

export function extractArticle(html: string, pageUrl: string): ExtractedArticle | null {
  if (!html || html.length < 40) return null;

  const title =
    metaContent(html, ["og:title", "twitter:title"]) ||
    stripTags(tagInner(html, "title")) ||
    stripTags(firstMatchInner(html, [/<h1[^>]*>([\s\S]*?)<\/h1>/i]));

  const description =
    metaContent(html, ["og:description", "twitter:description", "description"]) || undefined;

  const publisher =
    metaContent(html, ["og:site_name", "application-name"]) ||
    (() => {
      try {
        return new URL(pageUrl).hostname.replace(/^www\./i, "");
      } catch {
        return undefined;
      }
    })();

  const publishedAt =
    metaContent(html, ["article:published_time", "og:updated_time", "pubdate", "publish-date"]) ||
    undefined;

  const canonical =
    (() => {
      const m = html.match(/<link[^>]*rel=["']canonical["'][^>]*href=["']([^"']+)["']/i)
        || html.match(/<link[^>]*href=["']([^"']+)["'][^>]*rel=["']canonical["']/i);
      return m ? decodeEntities(m[1]) : undefined;
    })();

  const articleHtml =
    firstMatchInner(html, [
      /<article[^>]*>([\s\S]*?)<\/article>/i,
      /<main[^>]*>([\s\S]*?)<\/main>/i,
      /<div[^>]*(?:class|id)=["'][^"']*(?:article-body|story-body|entry-content|post-content|article__body|content-body)[^"']*["'][^>]*>([\s\S]*?)<\/div>/i,
    ]) || tagInner(html, "body") || html;

  let text = stripTags(articleHtml);
  // Prefer description+title when body is thin (JS-rendered shells)
  if (text.length < 200 && description) {
    text = [title, description].filter(Boolean).join(". ");
  }
  text = text.slice(0, MAX_TEXT);
  if (text.length < 80 && !title) return null;
  if (text.length < 40) return null;

  return {
    title: (title || "Untitled").slice(0, 300),
    description: description?.slice(0, 500),
    publisher: publisher?.slice(0, 120),
    publishedAt: publishedAt?.slice(0, 80),
    text,
    canonicalUrl: canonical?.slice(0, 2000),
  };
}
