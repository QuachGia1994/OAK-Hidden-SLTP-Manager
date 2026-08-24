import {
  NEOTECH_DEFAULT_STALE_SECONDS,
  canReadNeoTechProfile,
  getNeoTechProfileConfig,
  neoTechCheckKeyboard,
  renderNeoTechCheckPages,
  type NeoTechCheckCommand,
} from "./neotech-compliance-domain.ts";
import type { ComplianceStoredReport } from "./neotech-compliance-service.ts";

export type NeoTechTelegramPage = {
  text: string;
  replyMarkup?: { inline_keyboard: Array<Array<{ text: string; callback_data: string }>> };
};

export async function resolveNeoTechTelegramPage(
  command: NeoTechCheckCommand,
  chatId: string,
  userId: string,
  loadLatest: (slug: string) => Promise<ComplianceStoredReport | null>,
  rawProfiles: string,
  nowSeconds = Math.floor(Date.now() / 1000),
  staleAfterSeconds = NEOTECH_DEFAULT_STALE_SECONDS,
): Promise<NeoTechTelegramPage> {
  let profile;
  try {
    profile = getNeoTechProfileConfig(command.slug, rawProfiles);
  } catch {
    return { text: "⚠️ NeoTech compliance chưa được cấu hình trên server." };
  }
  if (!profile || !canReadNeoTechProfile(profile, chatId, userId)) return { text: "⚠️ Không tìm thấy profile hoặc bạn không có quyền xem báo cáo này." };
  const stored = await loadLatest(profile.slug);
  if (!stored) return { text: `⚠️ @${profile.slug} chưa có báo cáo compliance đã upload.` };
  const rendered = renderNeoTechCheckPages(stored.report, command, nowSeconds, staleAfterSeconds);
  const page = rendered.pages[rendered.requestedPage - 1];
  const canonicalCommand = { ...command, page: rendered.requestedPage };
  return {
    text: `${page}\n\nTrang ${rendered.requestedPage}/${rendered.totalPages}`,
    replyMarkup: neoTechCheckKeyboard(canonicalCommand, rendered.totalPages),
  };
}
