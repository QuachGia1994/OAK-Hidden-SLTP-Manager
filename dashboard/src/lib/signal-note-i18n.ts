export type SignalLocale = "VN" | "EN";

export interface LocalizedHourNote {
  translatedNote: string;
  badgeText: string | null;
  descriptionText: string;
  hasNoGoldBadge: boolean;
}

export function getH11ChartTitle(locale: SignalLocale): string {
  return locale === "EN"
    ? "4 H1 candles (H7 → H10)"
    : "Biểu đồ 4 nến H1 (H7 ➔ H10)";
}

const NO_GOLD_SUFFIX = /(?:;\s*)?🚫 no-gold label/g;

const ENGLISH_REPLACEMENTS: ReadonlyArray<readonly [RegExp, string]> = [
  [/Ưu tiên đi sớm H=(\d+)/g, "Early priority H=$1"],
  [/Ưu tiên đi trễ H=(\d+)/g, "Late priority H=$1"],
  [/Ưu tiên đi H=(\d+)/g, "Priority H=$1"],
  [/Ưu tiên H=(\d+)/g, "Priority H=$1"],
  [/Đảo signal ra Vàng \(XAUUSD\)/g, "Reverse to gold (XAUUSD)"],
  [/Chỉ Vàng \(XAUUSD\)/g, "XAU only"],
  [/H=6: Đảo chiều từ H=2\./g, "H=6: reverse the final H=2 direction."],
  [/XAUUSD theo D-direction H=4/g, "XAUUSD follows H=4 Stock-direction"],
  [/XAUUSD đảo từ H=5 hôm qua/g, "XAUUSD reverses from H=5 yesterday"],
  [/XAUUSD đảo từ H=5 hôm nay/g, "XAUUSD reverses from H=5 today"],
  [/XAUUSD & GBPAUD dùng lại lịch sử của Thứ 2/g, "XAUUSD & GBPAUD reuse Monday's history"],
  [/GBPAUD cùng chiều H=5 hôm qua/g, "GBPAUD follows H=5 yesterday"],
  [/GBPAUD ngược chiều H=5 hôm qua/g, "GBPAUD reverses H=5 yesterday"],
  [/GBP group đảo từ H=5 hôm qua/g, "GBP group reverses from H=5 yesterday"],
  [/GBP cùng chiều H=5 hôm qua \(Thứ 6\)/g, "GBP follows H=5 yesterday (Fri)"],
  [/GBP group cùng chiều H=5 hôm nay \(Thứ 6 đảo\)/g, "GBP group follows H=5 today (Fri reverses)"],
  [/GBP group đảo từ H=5 hôm nay \(Thứ 6\)/g, "GBP group reverses from H=5 today (Fri)"],
  [/GBP group đảo từ H=5 hôm nay/g, "GBP group reverses from H=5 today"],
  [/GBP đảo từ H=5 hôm nay \(Thứ 6\)/g, "GBP reverses from H=5 today (Fri)"],
  [/GBP đảo từ H=5 hôm nay/g, "GBP reverses from H=5 today"],
  [/GBP group cùng chiều H=5 hôm nay/g, "GBP group follows H=5 today"],
  [/\(Thứ 6 cùng chiều\)/g, "(Fri follows)"],
  [/\(Thứ 6 đảo\)/g, "(Fri reverses)"],
  [/Tắt nhóm GBP \(Thứ 4\)/g, "GBP group disabled (Wed)"],
  [/Tắt nhóm GBP/g, "GBP group disabled"],
  [/XAUUSD theo M30 \(13:00-14:30\) \(Thứ 2 \/ Thứ 5 \/ Thứ 6\)/g, "XAUUSD based on M30 (13:00-14:30) (Mon / Thu / Fri)"],
  [/H=11: Phân nhóm H1 \(SW\/BT\) từ H=10,9,8,7/g, "H=11: Classify H1 (SW/BT) from H=10,9,8,7"],
  [/XAUUSD đảo ngược \(Thứ 4 \/ Thứ 5\)/g, "XAUUSD reverses (Wed / Thu)"],
];

function translateToEnglish(note: string): string {
  const translatedH11 = note.replace(
    /H=11: Nhóm (SW|BT) \((.*?)\)/g,
    (_match, group: string, detail: string) =>
      `H=11: ${group} Group (${detail.replace(/Tăng/g, "Up").replace(/Giảm/g, "Down")})`,
  );

  return ENGLISH_REPLACEMENTS.reduce(
    (translated, [pattern, replacement]) => translated.replace(pattern, replacement),
    translatedH11,
  );
}

export function localizeHourNote(
  note: string | null | undefined,
  locale: SignalLocale,
): LocalizedHourNote {
  const rawNote = note?.trim() ?? "";
  const translatedNote = locale === "EN" ? translateToEnglish(rawNote) : rawNote;
  const hasPriorityBadge = rawNote.includes("★");
  const hasNoGoldBadge = rawNote.includes("no-gold");
  const visibleNote = translatedNote.replace(NO_GOLD_SUFFIX, "").trim();
  const noteParts = visibleNote.split("·");

  return {
    translatedNote,
    badgeText: hasPriorityBadge ? noteParts[0].trim() : null,
    descriptionText: hasPriorityBadge ? noteParts.slice(1).join("·").trim() : visibleNote,
    hasNoGoldBadge,
  };
}
