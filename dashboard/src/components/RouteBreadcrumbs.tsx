"use client";

import { OAK_TOOLS } from "@/lib/oak-tools";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useLocale } from "./LocaleProvider";

export function RouteBreadcrumbs() {
  const pathname = usePathname();
  const { locale } = useLocale();
  const isFactResult = pathname.startsWith("/factcheck/") && pathname !== "/factcheck";
  const isNeoTechNested = pathname.startsWith("/neotech/") && pathname !== "/neotech";
  const tool = OAK_TOOLS.find(item => pathname === item.href);
  if (!tool && !isFactResult && !isNeoTechNested) return null;

  const items = tool
    ? [{ href: "/tools", label: locale === "EN" ? "Tools" : "Công cụ" }, { href: "", label: tool.name[locale] }]
    : isFactResult
    ? [
        { href: "/factcheck", label: locale === "EN" ? "Fact Check" : "Xác thực" },
        { href: "", label: locale === "EN" ? "Result" : "Kết quả" },
      ]
    : [
        { href: "/neotech", label: "NeoTech" },
        { href: "", label: locale === "EN" ? "Shared profile" : "Profile chia sẻ" },
      ];

  return (
    <nav className="oak-breadcrumb" aria-label={locale === "EN" ? "Breadcrumb" : "Đường dẫn trang"}>
      <div className="nav-shell oak-breadcrumb-inner">
        <Link href="/engine">OAK</Link>
        {items.map((item) => (
          <span key={`${item.href}-${item.label}`}>
            <i aria-hidden="true">/</i>
            {item.href ? <Link href={item.href}>{item.label}</Link> : <b aria-current="page">{item.label}</b>}
          </span>
        ))}
      </div>
    </nav>
  );
}
