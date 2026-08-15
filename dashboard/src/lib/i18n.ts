export type Locale = "VN" | "EN";

function normalizeLocale(value: string | null | undefined): Locale {
  if (!value) return "VN";
  return value.toLowerCase().startsWith("en") ? "EN" : "VN";
}

export function detectServerLocaleFromCookie(
  cookieHeader?: string | null,
  acceptLanguage?: string | null,
): Locale {
  const cookie = cookieHeader || "";
  const mode = cookie.match(/(?:^|;\s*)sltp_locale_mode=([^;]+)/)?.[1];
  if (mode === "EN" || mode === "VN") return mode;
  const stored = cookie.match(/(?:^|;\s*)sltp_locale=([^;]+)/)?.[1];
  if (stored === "EN" || stored === "VN") return stored;
  return normalizeLocale(acceptLanguage);
}
