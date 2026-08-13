"use client";

import { useState } from "react";
import {
  PUBLIC_INVESTMENT_COMPLIANCE,
  RISK_DISCLOSURE_EN,
  RISK_DISCLOSURE_VN,
} from "@/lib/compliance";

interface Props {
  locale: "EN" | "VN";
}

/**
 * Visible risk disclosure for the public transparency portal.
 * Information-only — not legal advice.
 */
export function InvestmentRiskDisclosure({ locale }: Props) {
  const [open, setOpen] = useState(false);
  const lines = locale === "VN" ? RISK_DISCLOSURE_VN : RISK_DISCLOSURE_EN;
  const title =
    locale === "VN"
      ? "Công bố rủi ro & điều khoản thông tin"
      : "Risk disclosure & information terms";
  const toggle =
    locale === "VN" ? "Xem công bố rủi ro & điều khoản" : "View risk disclosure & terms";
  const modeNote =
    locale === "VN"
      ? `Chế độ portal: ${PUBLIC_INVESTMENT_COMPLIANCE.mode} · chỉ thông tin · không thu tiền · không đặt lệnh`
      : `Portal mode: ${PUBLIC_INVESTMENT_COMPLIANCE.mode} · information only · no money collection · no order execution`;

  return (
    <section
      className="rounded-2xl border border-[var(--terminal-warning)]/35 bg-[var(--terminal-warning)]/8 p-5 sm:p-6"
      aria-labelledby="risk-disclosure-heading"
    >
      <h3 id="risk-disclosure-heading" className="text-sm font-bold text-[var(--foreground)]">
        {title}
      </h3>
      <p className="mt-1 text-[12px] leading-5 text-[var(--muted)]">{modeNote}</p>
      <ul className="mt-3 space-y-2 text-[13px] leading-6 text-[var(--foreground)]">
        {lines.slice(0, 3).map((line, i) => (
          <li key={i} className="flex gap-2">
            <span className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full bg-[var(--terminal-warning)]" aria-hidden />
            <span>{line}</span>
          </li>
        ))}
      </ul>
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="mt-4 rounded-lg border border-[var(--panel-border)] bg-[var(--surface)] px-3 py-2 text-xs font-semibold text-[var(--foreground)] hover:border-[var(--terminal-accent)]"
        aria-expanded={open}
      >
        {toggle}
      </button>
      {open && (
        <div className="mt-3 space-y-2 rounded-xl border border-[var(--panel-border)] bg-[var(--surface)] p-4 text-[13px] leading-6 text-[var(--foreground)]">
          {lines.map((line, i) => (
            <p key={i}>{line}</p>
          ))}
          <p className="text-[11px] text-[var(--muted)]">
            {locale === "VN"
              ? "Nội dung này là biện pháp an toàn sản phẩm, không phải tư vấn pháp lý."
              : "This text is a product-safety guard, not legal advice."}
          </p>
        </div>
      )}
    </section>
  );
}
