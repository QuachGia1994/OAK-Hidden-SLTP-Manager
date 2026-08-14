"use client";

import { useRouter } from "next/navigation";

interface AccountOption {
  public_account_id: string;
  alias: string;
}

interface Props {
  locale: "EN" | "VN";
  accounts: AccountOption[];
  selectedAccountId?: string | null;
  compact?: boolean;
}

export function PublicAccountSelector({ locale, accounts, selectedAccountId, compact = false }: Props) {
  const router = useRouter();
  if (!accounts.length) return null;

  return (
    <label className={`block ${compact ? "min-w-0" : "w-full"}`}>
      <span className="sr-only">{locale === "VN" ? "Chọn tài khoản công khai" : "Select public account"}</span>
      <span className="relative block">
        <select
          value={selectedAccountId || ""}
          onChange={(event) => {
            const url = new URL(window.location.href);
            url.searchParams.set("account", event.target.value);
            router.replace(`${url.pathname}?${url.searchParams.toString()}`);
          }}
          className="h-11 w-full appearance-none rounded-xl border border-[var(--panel-border)] bg-[var(--surface-raised)] px-3 pr-11 text-sm font-semibold text-[var(--foreground)] outline-none transition focus:border-[var(--terminal-accent)] focus:ring-2 focus:ring-[var(--terminal-accent)]/20"
          aria-label={locale === "VN" ? "Chọn tài khoản công khai" : "Select public account"}
        >
          {accounts.map((account) => (
            <option key={account.public_account_id} value={account.public_account_id}>
              {account.alias}
            </option>
          ))}
        </select>
        <span className="pointer-events-none absolute inset-y-0 right-3 grid w-6 place-items-center text-[var(--foreground)]" aria-hidden="true">
          <svg viewBox="0 0 20 20" className="h-5 w-5" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="m5 7 5 5 5-5" strokeLinecap="round" strokeLinejoin="round" />
          </svg>
        </span>
      </span>
    </label>
  );
}
