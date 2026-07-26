"use client";

import { useState, useEffect, useCallback, useRef } from "react";
import { useLocale } from "./LocaleProvider";
import { getCompanyName, getMarketCap, getExchange } from "@/lib/stock-names";

export function StockLookupModal({
  initialSymbol,
  isOpen,
  onClose,
}: {
  initialSymbol: string | null;
  isOpen: boolean;
  onClose: () => void;
}) {
  const { locale } = useLocale();
  const t = (vn: string, en: string) => (locale === "EN" ? en : vn);

  const [searchInput, setSearchInput] = useState("");
  const [activeSymbol, setActiveSymbol] = useState<string | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (isOpen && initialSymbol) {
      setSearchInput(initialSymbol.toUpperCase());
      setActiveSymbol(initialSymbol.toUpperCase());
    } else if (isOpen) {
      setSearchInput("");
      setActiveSymbol(null);
      setTimeout(() => inputRef.current?.focus(), 100);
    }
  }, [isOpen, initialSymbol]);

  const doSearch = useCallback(() => {
    const sym = searchInput.trim().toUpperCase();
    if (sym.length >= 1 && sym.length <= 10) {
      setActiveSymbol(sym);
    }
  }, [searchInput]);

  const handleKeyDown = useCallback(
    (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    },
    [onClose],
  );

  useEffect(() => {
    if (isOpen) {
      document.addEventListener("keydown", handleKeyDown);
      document.body.style.overflow = "hidden";
    }
    return () => {
      document.removeEventListener("keydown", handleKeyDown);
      document.body.style.overflow = "";
    };
  }, [isOpen, handleKeyDown]);

  if (!isOpen) return null;

  const sym = activeSymbol || "";
  const companyName = sym ? getCompanyName(sym) : "";
  const marketCap = sym ? getMarketCap(sym, locale) : "";
  const exchange = sym ? getExchange(sym) : "";

  const openLink = (url: string) => {
    window.open(url, "_blank", "noopener,noreferrer");
  };

  const makeLinks = (s: string) => [
    { label: "Tài chính", url: `https://www.google.com/search?q=${s}+t%C3%A0i+ch%C3%ADnh+cafef.vn` },
    { label: "Cổ tức", url: `https://www.google.com/search?q=${s}+c%E1%BB%95+t%E1%BB%A9c+lich-su` },
    { label: "Ngoại tệ", url: `https://www.google.com/search?q=${s}+t%E1%BB%B7+l%E1%BB%87+n%C6%B0%E1%BB%9Bc+ngo%C3%A0i` },
    { label: "Biểu đồ", url: `https://www.google.com/search?q=${s}+chart+stock` },
  ];

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4"
      onClick={(e) => e.target === e.currentTarget && onClose()}
    >
      <div className="absolute inset-0 bg-black/60 backdrop-blur-sm" onClick={onClose} />

      <div className="relative z-10 w-full max-w-md rounded-2xl border border-[var(--panel-border)] bg-[var(--surface)]">
        {/* Header with search */}
        <div className="border-b border-[var(--panel-border)] px-5 py-4">
          <div className="flex items-center justify-between mb-3">
            <h2 className="font-mono text-sm font-black uppercase tracking-[0.15em] text-[var(--muted)]">
              {t("Tra cứu cổ phiếu", "Stock Lookup")}
            </h2>
            <button
              onClick={onClose}
              className="grid h-7 w-7 place-items-center rounded-lg border border-[var(--panel-border)] bg-[var(--surface-raised)] text-[var(--muted)] transition-colors hover:text-[var(--foreground)]"
              aria-label="Close"
            >
              <svg className="h-3.5 w-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
                <path d="M18 6 6 18M6 6l12 12" strokeLinecap="round" strokeLinejoin="round" />
              </svg>
            </button>
          </div>
          <div className="flex gap-2">
            <input
              ref={inputRef}
              type="text"
              value={searchInput}
              onChange={(e) => setSearchInput(e.target.value.toUpperCase())}
              onKeyDown={(e) => {
                if (e.key === "Enter") {
                  doSearch();
                  if (searchInput.trim()) openLink(`https://www.google.com/search?q=${searchInput.trim().toUpperCase()}+c%E1%BB%95+phi%E1%BA%BFu`);
                }
              }}
              placeholder={t("Nhập mã (VD: HPG)...", "Enter ticker (e.g. HPG)...")}
              className="flex-1 rounded-lg border border-[var(--panel-border)] bg-[var(--surface-raised)] px-3 py-2 font-mono text-sm font-bold text-[var(--foreground)] placeholder:text-[var(--muted)]/50 focus:border-[var(--terminal-accent)]/50 focus:outline-none focus:ring-1 focus:ring-[var(--terminal-accent)]/30"
              maxLength={10}
            />
            <button
              onClick={() => {
                doSearch();
                if (searchInput.trim()) openLink(`https://www.google.com/search?q=${searchInput.trim().toUpperCase()}+c%E1%BB%95+phi%E1%BA%BFu`);
              }}
              className="rounded-lg bg-[var(--terminal-accent)] px-4 py-2 font-mono text-xs font-black uppercase text-[#04130F] transition-colors hover:bg-[var(--terminal-accent-strong)]"
            >
              {t("Tra cứu", "Go")}
            </button>
          </div>
        </div>

        {/* Content */}
        <div className="px-5 py-4">
          {!activeSymbol && (
            <div className="py-8 text-center">
              <div className="mx-auto mb-3 grid h-11 w-11 place-items-center rounded-xl border border-[var(--panel-border)] bg-[var(--surface-raised)] text-[var(--muted)]">
                <svg className="h-5 w-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.5}>
                  <path d="M21 21l-5.197-5.197m0 0A7.5 7.5 0 105.196 5.196a7.5 7.5 0 0010.607 10.607z" strokeLinecap="round" strokeLinejoin="round" />
                </svg>
              </div>
              <p className="text-sm text-[var(--muted)]">
                {t("Nhập mã cổ phiếu và nhấn Enter", "Enter a ticker and press Enter")}
              </p>
            </div>
          )}

          {activeSymbol && (
            <div className="space-y-4">
              {/* Stock info */}
              <div className="rounded-xl border border-[var(--panel-border)] bg-[var(--surface-raised)] px-4 py-3">
                <div className="flex items-center gap-3">
                  <span className="font-mono text-xl font-black text-[var(--foreground)]">{sym}</span>
                  {exchange && (
                    <span className="rounded-md border border-[var(--panel-border)] bg-[var(--surface)] px-2 py-0.5 font-mono text-[10px] font-bold uppercase text-[var(--muted)]">
                      {exchange}
                    </span>
                  )}
                </div>
                {companyName && (
                  <p className="mt-1 text-sm text-[var(--muted)]">{companyName}</p>
                )}
                {marketCap && (
                  <p className="mt-0.5 font-mono text-xs text-[var(--terminal-warning)]">
                    {t("Vốn hoá", "Cap")}: {marketCap}
                  </p>
                )}
              </div>

              {/* Quick links */}
              <div>
                <p className="mb-2 text-[10px] font-bold uppercase tracking-[0.15em] text-[var(--muted)]">
                  {t("Xem chi tiết", "View details")}
                </p>
                <div className="grid grid-cols-2 gap-2">
                  {makeLinks(sym).map((link) => (
                    <button
                      key={link.label}
                      onClick={() => openLink(link.url)}
                      className="rounded-lg border border-[var(--panel-border)] bg-[var(--surface-raised)] px-3 py-2.5 text-left text-xs font-semibold text-[var(--foreground)] transition-colors hover:border-[var(--terminal-accent)]/40 hover:bg-[var(--surface)]"
                    >
                      <span className="block text-[var(--muted)]">{link.label}</span>
                      <span className="mt-0.5 block font-mono text-[10px] text-[var(--terminal-accent)]">
                        Google →
                      </span>
                    </button>
                  ))}
                </div>
              </div>

              {/* Open full page button */}
              <button
                onClick={() => openLink(`https://www.google.com/search?q=${sym}+c%E1%BB%95+phi%E1%BA%BFu+t%C3%A0i+ch%C3%ADnh+cafef`)}
                className="w-full rounded-xl bg-[var(--terminal-accent)] py-3 font-mono text-sm font-black uppercase text-[#04130F] transition-colors hover:bg-[var(--terminal-accent-strong)]"
              >
                {t("Tìm kiếm đầy đủ trên Google", "Search full info on Google")}
              </button>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
