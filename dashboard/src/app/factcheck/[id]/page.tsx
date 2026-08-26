import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { headers } from "next/headers";
import { FactCheckPublicView } from "@/components/factcheck/FactCheckPublicView";
import { FactCheckMediaPublicView } from "@/components/factcheck/FactCheckMediaPublicView";
import type { FactCheckResult } from "@/lib/factcheck/types";
import type { ImageAuthenticityResult } from "@/lib/factcheck/media-types";
import { TEXT } from "@/lib/factcheck/locale-copy";
import { detectServerLocaleFromCookie } from "@/lib/i18n";
import { buildOgDescription, buildOgTitle } from "@/lib/factcheck/presentation";
import { buildMediaOgDescription, buildMediaOgTitle } from "@/lib/factcheck/media-presentation";
import { isValidShareId, publicSharePath } from "@/lib/factcheck/share-id";
import { getSharedFactCheck } from "@/lib/factcheck/share-store";

export const dynamic = "force-dynamic";
export const revalidate = 0;

type PageProps = { params: Promise<{ id: string }> };

export async function generateMetadata({ params }: PageProps): Promise<Metadata> {
  const { id } = await params;
  if (!isValidShareId(id)) {
    return { title: "Fact Check — OAK Gatekeeper", robots: { index: false, follow: false } };
  }

  const lookup = await getSharedFactCheck(id);
  if (lookup.status !== "ok") {
    return { title: "Fact Check — OAK Gatekeeper", robots: { index: false, follow: false } };
  }

  const path = publicSharePath(id);
  const canonical = `https://www.oakgatekeeper.uk${path}`;

  if (lookup.record.resultKind === "media_authenticity") {
    const result = lookup.record.result as ImageAuthenticityResult;
    const title = buildMediaOgTitle(result, result.locale);
    const description = buildMediaOgDescription(result, result.locale);
    return {
      title: `${title} | OAK Gatekeeper`,
      description,
      alternates: { canonical },
      openGraph: {
        title,
        description,
        url: canonical,
        siteName: "OAK Gatekeeper",
        type: "article",
        locale: result.locale === "VN" ? "vi_VN" : "en_GB",
      },
      twitter: { card: "summary_large_image", title, description },
      robots: { index: false, follow: false },
    };
  }

  const result = lookup.record.result as FactCheckResult;
  const title = buildOgTitle(result.verdict, result.claim, result.locale);
  const description = buildOgDescription(result.summary, result.locale);
  return {
    title: `${title} | OAK Gatekeeper`,
    description,
    alternates: { canonical },
    openGraph: {
      title,
      description,
      url: canonical,
      siteName: "OAK Gatekeeper",
      type: "article",
      locale: result.locale === "VN" ? "vi_VN" : "en_GB",
    },
    twitter: { card: "summary_large_image", title, description },
    robots: { index: true, follow: true },
  };
}

export default async function SharedFactCheckPage({ params }: PageProps) {
  const { id } = await params;
  if (!isValidShareId(id)) notFound();

  const lookup = await getSharedFactCheck(id);
  if (lookup.status === "malformed") notFound();

  if (lookup.status === "not_found" || lookup.status === "expired") {
    const headerList = await headers();
    const locale = detectServerLocaleFromCookie(headerList.get("cookie"), headerList.get("accept-language"));
    const t = TEXT[locale];
    const isExpired = lookup.status === "expired";
    return (
      <div className="page-shell oak-fact-screen">
        <div className="oak-fact-public-state">
          <span className="oak-eyebrow">{t.publicEyebrow}</span>
          <h1>{isExpired ? t.expiredTitle : t.notFoundTitle}</h1>
          <p>{isExpired ? t.expiredBody : t.notFoundBody}</p>
          <Link href="/factcheck" className="oak-primary-action oak-fact-submit"><b>{t.checkAnother}</b><i>→</i></Link>
        </div>
      </div>
    );
  }

  if (lookup.status !== "ok") notFound();

  return (
    <div className="page-shell oak-fact-screen">
      {lookup.record.resultKind === "media_authenticity"
        ? <FactCheckMediaPublicView result={lookup.record.result as ImageAuthenticityResult} />
        : (
          <FactCheckPublicView
            result={lookup.record.result as FactCheckResult}
            locale={(lookup.record.result as FactCheckResult).locale}
            showShareCta
            shareUrl={`https://www.oakgatekeeper.uk${publicSharePath(id)}`}
          />
        )}
      <script
        dangerouslySetInnerHTML={{
          __html: `try{window.dispatchEvent(new CustomEvent("oak:analytics",{detail:{event:"factcheck_shared_result_viewed",shareId:${JSON.stringify(id)},ts:Date.now()}}))}catch(e){}`,
        }}
      />
    </div>
  );
}
